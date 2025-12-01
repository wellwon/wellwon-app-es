# =============================================================================
# File: app/infra/cqrs/projector_decorators.py
# Description: Explicit decorators for projection execution control
#              @sync_projection - executes on SERVER before HTTP response
#              @async_projection - executes on WORKER via Kafka
# =============================================================================

import logging
import inspect
import asyncio
import threading
from typing import Type, Dict, Any, Callable, Optional, List, Set, Awaitable
from dataclasses import dataclass
from functools import wraps
from datetime import datetime
import time

from app.infra.event_store.event_envelope import EventEnvelope

log = logging.getLogger("wellwon.cqrs.projector_decorators")

# Configuration
DEFAULT_SYNC_TIMEOUT = 2.0  # seconds
DEFAULT_PRIORITY = 10  # lower number = higher priority
MAX_METRIC_KEYS = 1000  # Maximum number of event types to track metrics for

# Thread-safe lock for registry access
_REGISTRY_LOCK = threading.Lock()


@dataclass
class ProjectionHandler:
    """Metadata for a projection handler"""
    handler_func: Callable[[Any, EventEnvelope], Awaitable[None]]
    event_type: str
    domain: str
    projector_class: Optional[Type] = None
    method_name: Optional[str] = None
    timeout: Optional[float] = None  # Only for sync projections
    priority: int = DEFAULT_PRIORITY
    description: Optional[str] = None
    module: Optional[str] = None
    is_sync: bool = True  # True for sync, False for async


# Global registries for projection handlers
_SYNC_PROJECTION_HANDLERS: Dict[str, List[ProjectionHandler]] = {}
_ASYNC_PROJECTION_HANDLERS: Dict[str, List[ProjectionHandler]] = {}

# Performance tracking
_PROJECTION_METRICS: Dict[str, List[float]] = {}
_PROJECTION_ERRORS: Dict[str, int] = {}


def _extract_domain(func: Callable) -> str:
    """Extract domain name from module path."""
    module = inspect.getmodule(func)
    module_name = module.__name__ if module else ""

    # Known domain names
    domain_names = ["user_account", "company", "chat", "broker_connection",
                    "broker_account", "virtual_broker", "order", "position"]

    if "." in module_name:
        parts = module_name.split(".")
        for part in parts:
            if part in domain_names:
                return part
    return "unknown"


def sync_projection(
        event_type: str,
        *,
        timeout: float = DEFAULT_SYNC_TIMEOUT,
        priority: int = DEFAULT_PRIORITY,
        description: Optional[str] = None
):
    """
    Decorator for SYNCHRONOUS projection handlers.
    Executes on SERVER before HTTP response (immediate consistency).

    Usage:
        class UserProjector:
            @sync_projection("UserAccountCreated")
            async def on_user_created(self, envelope: EventEnvelope):
                # This runs BEFORE response is sent to client
                pass

    Args:
        event_type: The event type to handle
        timeout: Maximum execution time in seconds (default: 2.0)
        priority: Execution priority (lower = higher priority)
        description: Optional description for documentation
    """
    def decorator(func: Callable) -> Callable:
        domain = _extract_domain(func)
        module = inspect.getmodule(func)
        module_name = module.__name__ if module else ""

        handler = ProjectionHandler(
            handler_func=func,
            event_type=event_type,
            domain=domain,
            method_name=func.__name__,
            timeout=timeout,
            priority=priority,
            description=description or func.__doc__,
            module=module_name,
            is_sync=True
        )

        with _REGISTRY_LOCK:
            if event_type not in _SYNC_PROJECTION_HANDLERS:
                _SYNC_PROJECTION_HANDLERS[event_type] = []
            _SYNC_PROJECTION_HANDLERS[event_type].append(handler)

            func._is_sync_projection = True
            func._projection_metadata = handler

            log.debug(
                f"Registered SYNC projection: {func.__name__} "
                f"for {event_type} in {domain} "
                f"(priority: {priority}, timeout: {timeout}s)"
            )

        return func
    return decorator


def async_projection(
        event_type: str,
        *,
        priority: int = DEFAULT_PRIORITY,
        description: Optional[str] = None
):
    """
    Decorator for ASYNCHRONOUS projection handlers.
    Executes on WORKER via Kafka (eventual consistency).

    Usage:
        class CompanyProjector:
            @async_projection("CompanyDeleted")
            async def on_company_deleted(self, envelope: EventEnvelope):
                # This runs on Worker, NOT blocking HTTP response
                pass

    Args:
        event_type: The event type to handle
        priority: Execution priority (lower = higher priority)
        description: Optional description for documentation
    """
    def decorator(func: Callable) -> Callable:
        domain = _extract_domain(func)
        module = inspect.getmodule(func)
        module_name = module.__name__ if module else ""

        handler = ProjectionHandler(
            handler_func=func,
            event_type=event_type,
            domain=domain,
            method_name=func.__name__,
            timeout=None,  # No timeout for async - Worker manages this
            priority=priority,
            description=description or func.__doc__,
            module=module_name,
            is_sync=False
        )

        with _REGISTRY_LOCK:
            if event_type not in _ASYNC_PROJECTION_HANDLERS:
                _ASYNC_PROJECTION_HANDLERS[event_type] = []
            _ASYNC_PROJECTION_HANDLERS[event_type].append(handler)

            func._is_async_projection = True
            func._projection_metadata = handler

            log.debug(
                f"Registered ASYNC projection: {func.__name__} "
                f"for {event_type} in {domain} "
                f"(priority: {priority})"
            )

        return func
    return decorator


async def execute_sync_projections(
        envelope: EventEnvelope,
        projector_instances: Dict[str, Any],
        timeout_override: Optional[float] = None
) -> Dict[str, Any]:
    """
    Execute all registered SYNC projections for an event.
    Called on SERVER before HTTP response.

    Args:
        envelope: The event envelope to process
        projector_instances: Dict of domain -> projector instance
        timeout_override: Override handler timeout

    Returns:
        Execution statistics
    """
    event_type = envelope.event_type
    handlers = _SYNC_PROJECTION_HANDLERS.get(event_type, [])

    if not handlers:
        return {
            "event_type": event_type,
            "handlers_found": 0,
            "handlers_executed": 0,
            "success": True
        }

    sorted_handlers = sorted(handlers, key=lambda h: h.priority)
    start_time = time.time()
    executed = 0
    errors = []

    for handler in sorted_handlers:
        handler_start = time.time()
        timeout = timeout_override or handler.timeout or DEFAULT_SYNC_TIMEOUT

        try:
            if handler.domain not in projector_instances:
                log.warning(
                    f"No projector instance for domain {handler.domain}, "
                    f"skipping SYNC handler {handler.method_name}"
                )
                continue

            instance = projector_instances[handler.domain]

            await asyncio.wait_for(
                handler.handler_func(instance, envelope),
                timeout=timeout
            )
            executed += 1

            # Track performance
            duration = time.time() - handler_start
            _track_metrics(event_type, duration, timeout)

        except asyncio.TimeoutError:
            error_msg = (
                f"SYNC projection {handler.method_name} for {event_type} "
                f"timed out after {timeout}s"
            )
            log.error(error_msg)
            errors.append(error_msg)
            _track_error(event_type)

        except Exception as e:
            # Check for RetriableProjectionError
            from app.common.exceptions.projection_exceptions import RetriableProjectionError
            if isinstance(e, RetriableProjectionError):
                log.warning(
                    f"Retriable error in SYNC projection {handler.method_name} "
                    f"for {event_type}: {e}"
                )
                raise

            error_msg = (
                f"Error in SYNC projection {handler.method_name} "
                f"for {event_type}: {e}"
            )
            log.error(error_msg, exc_info=True)
            errors.append(error_msg)
            _track_error(event_type)

    total_duration = time.time() - start_time

    if total_duration > 0.5:
        log.warning(
            f"SYNC projections for {event_type} took {total_duration:.3f}s total "
            f"({executed} handlers)"
        )

    return {
        "event_type": event_type,
        "handlers_found": len(handlers),
        "handlers_executed": executed,
        "total_duration": total_duration,
        "errors": errors,
        "success": len(errors) == 0
    }


async def execute_async_projections(
        envelope: EventEnvelope,
        projector_instances: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute all registered ASYNC projections for an event.
    Called on WORKER via Kafka.

    Args:
        envelope: The event envelope to process
        projector_instances: Dict of domain -> projector instance

    Returns:
        Execution statistics
    """
    event_type = envelope.event_type
    handlers = _ASYNC_PROJECTION_HANDLERS.get(event_type, [])

    if not handlers:
        return {
            "event_type": event_type,
            "handlers_found": 0,
            "handlers_executed": 0,
            "success": True
        }

    sorted_handlers = sorted(handlers, key=lambda h: h.priority)
    start_time = time.time()
    executed = 0
    errors = []

    for handler in sorted_handlers:
        handler_start = time.time()

        try:
            if handler.domain not in projector_instances:
                log.warning(
                    f"No projector instance for domain {handler.domain}, "
                    f"skipping ASYNC handler {handler.method_name}"
                )
                continue

            instance = projector_instances[handler.domain]

            await handler.handler_func(instance, envelope)
            executed += 1

            duration = time.time() - handler_start
            log.debug(
                f"ASYNC projection {handler.method_name} completed for {event_type} "
                f"in {duration:.3f}s"
            )

        except Exception as e:
            error_msg = (
                f"Error in ASYNC projection {handler.method_name} "
                f"for {event_type}: {e}"
            )
            log.error(error_msg, exc_info=True)
            errors.append(error_msg)
            _track_error(event_type)
            raise  # Re-raise for Worker retry mechanism

    total_duration = time.time() - start_time

    return {
        "event_type": event_type,
        "handlers_found": len(handlers),
        "handlers_executed": executed,
        "total_duration": total_duration,
        "errors": errors,
        "success": len(errors) == 0
    }


def _track_metrics(event_type: str, duration: float, timeout: float):
    """Track projection performance metrics."""
    with _REGISTRY_LOCK:
        if event_type not in _PROJECTION_METRICS:
            if len(_PROJECTION_METRICS) >= MAX_METRIC_KEYS:
                sorted_by_count = sorted(
                    _PROJECTION_METRICS.items(),
                    key=lambda x: len(x[1])
                )
                cleanup_count = MAX_METRIC_KEYS // 10
                for old_key, _ in sorted_by_count[:cleanup_count]:
                    del _PROJECTION_METRICS[old_key]
            _PROJECTION_METRICS[event_type] = []

        _PROJECTION_METRICS[event_type].append(duration)

        if len(_PROJECTION_METRICS[event_type]) > 100:
            _PROJECTION_METRICS[event_type] = _PROJECTION_METRICS[event_type][-100:]

    if duration > timeout * 0.8:
        log.warning(
            f"Projection for {event_type} took {duration:.3f}s "
            f"(close to timeout {timeout}s)"
        )


def _track_error(event_type: str):
    """Track projection errors."""
    with _REGISTRY_LOCK:
        if event_type not in _PROJECTION_ERRORS:
            _PROJECTION_ERRORS[event_type] = 0
        _PROJECTION_ERRORS[event_type] += 1


# =============================================================================
# Registry Query Functions
# =============================================================================

def get_all_sync_events() -> Set[str]:
    """Get all event types with @sync_projection handlers."""
    return set(_SYNC_PROJECTION_HANDLERS.keys())


def get_all_async_events() -> Set[str]:
    """Get all event types with @async_projection handlers."""
    return set(_ASYNC_PROJECTION_HANDLERS.keys())


def get_sync_handlers(event_type: str) -> List[ProjectionHandler]:
    """Get all sync handlers for a specific event type."""
    return _SYNC_PROJECTION_HANDLERS.get(event_type, [])


def get_async_handlers(event_type: str) -> List[ProjectionHandler]:
    """Get all async handlers for a specific event type."""
    return _ASYNC_PROJECTION_HANDLERS.get(event_type, [])


def has_sync_handler(event_type: str) -> bool:
    """Check if event has a sync handler."""
    return event_type in _SYNC_PROJECTION_HANDLERS


def has_async_handler(event_type: str) -> bool:
    """Check if event has an async handler."""
    return event_type in _ASYNC_PROJECTION_HANDLERS


# =============================================================================
# Metrics and Validation
# =============================================================================

def get_sync_projection_metrics() -> Dict[str, Any]:
    """Get performance metrics for sync projections."""
    sync_domains = set()
    async_domains = set()

    for handlers in _SYNC_PROJECTION_HANDLERS.values():
        for handler in handlers:
            if handler.domain and handler.domain != "unknown":
                sync_domains.add(handler.domain)

    for handlers in _ASYNC_PROJECTION_HANDLERS.values():
        for handler in handlers:
            if handler.domain and handler.domain != "unknown":
                async_domains.add(handler.domain)

    metrics = {
        "sync": {
            "event_types": len(_SYNC_PROJECTION_HANDLERS),
            "total_handlers": sum(len(h) for h in _SYNC_PROJECTION_HANDLERS.values()),
            "domains": sorted(list(sync_domains)),
        },
        "async": {
            "event_types": len(_ASYNC_PROJECTION_HANDLERS),
            "total_handlers": sum(len(h) for h in _ASYNC_PROJECTION_HANDLERS.values()),
            "domains": sorted(list(async_domains)),
        },
        "performance": {},
        "errors": dict(_PROJECTION_ERRORS)
    }

    for event_type, durations in _PROJECTION_METRICS.items():
        if durations:
            metrics["performance"][event_type] = {
                "avg_ms": sum(durations) / len(durations) * 1000,
                "min_ms": min(durations) * 1000,
                "max_ms": max(durations) * 1000,
                "p95_ms": sorted(durations)[int(len(durations) * 0.95)] * 1000
                         if len(durations) > 20 else max(durations) * 1000,
                "samples": len(durations)
            }

    return metrics


def validate_projections() -> Dict[str, List[str]]:
    """Validate projection handlers configuration."""
    issues = {
        "duplicate_handlers": [],
        "performance_warnings": [],
        "missing_domains": []
    }

    # Check for events with both sync AND async handlers (may be intentional)
    sync_events = set(_SYNC_PROJECTION_HANDLERS.keys())
    async_events = set(_ASYNC_PROJECTION_HANDLERS.keys())
    both = sync_events & async_events
    if both:
        log.info(f"Events with both SYNC and ASYNC handlers: {both}")

    # Check for performance issues
    for event_type, durations in _PROJECTION_METRICS.items():
        if durations and sum(durations) / len(durations) > 0.5:
            issues["performance_warnings"].append(
                f"{event_type}: avg {sum(durations) / len(durations) * 1000:.0f}ms"
            )

    return {k: v for k, v in issues.items() if v}


def clear_registries():
    """Clear all registries - useful for testing."""
    with _REGISTRY_LOCK:
        _SYNC_PROJECTION_HANDLERS.clear()
        _ASYNC_PROJECTION_HANDLERS.clear()
        _PROJECTION_METRICS.clear()
        _PROJECTION_ERRORS.clear()
    log.info("Cleared all projection registries")


# =============================================================================
# Auto-registration for Event Store
# =============================================================================

async def auto_register_sync_projections(
        event_store,
        projector_instances: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Register sync projections with the event store.
    Only registers events for domains that have projector instances.

    Args:
        event_store: The EventStore instance
        projector_instances: Dict of domain -> projector instance

    Returns:
        Registration statistics
    """
    all_sync_events = get_all_sync_events()

    if not all_sync_events:
        log.warning("No @sync_projection handlers registered")
        return {
            "sync_events": 0,
            "handlers_registered": 0,
            "domains": [],
            "validation": validate_projections()
        }

    # Filter to only include events for domains with projector instances
    filtered_sync_events = set()
    for event_type in all_sync_events:
        handlers = _SYNC_PROJECTION_HANDLERS.get(event_type, [])
        for handler in handlers:
            if handler.domain in projector_instances:
                filtered_sync_events.add(event_type)
                break

    log.info(
        f"Filtered SYNC events: {len(filtered_sync_events)} of {len(all_sync_events)} "
        f"(domains with projectors: {list(projector_instances.keys())})"
    )

    if not filtered_sync_events:
        return {
            "sync_events": 0,
            "handlers_registered": 0,
            "domains": list(projector_instances.keys()),
            "validation": validate_projections()
        }

    # Enable sync projections in event store
    event_store.enable_synchronous_projections(filtered_sync_events)

    async def projection_handler(envelope: EventEnvelope) -> None:
        await execute_sync_projections(envelope, projector_instances)

    registered = 0
    for event_type in filtered_sync_events:
        if _SYNC_PROJECTION_HANDLERS.get(event_type):
            event_store.register_sync_projection(event_type, projection_handler)
            registered += 1

    domains = set()
    for handlers in _SYNC_PROJECTION_HANDLERS.values():
        for handler in handlers:
            if handler.domain and handler.domain != "unknown":
                domains.add(handler.domain)

    log.info(
        f"Auto-registered {registered} SYNC projection handlers "
        f"for {len(all_sync_events)} event types across {len(domains)} domains"
    )

    return {
        "sync_events": len(all_sync_events),
        "handlers_registered": registered,
        "domains": sorted(list(domains)),
        "validation": validate_projections()
    }


# =============================================================================
# Performance Monitoring Decorator
# =============================================================================

def monitor_projection(func: Callable) -> Callable:
    """
    Additional decorator for detailed projection monitoring.

    Usage:
        @sync_projection("UserAccountCreated")
        @monitor_projection
        async def on_user_created(self, envelope: EventEnvelope):
            pass
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        event_envelope = None

        for arg in args:
            if isinstance(arg, EventEnvelope):
                event_envelope = arg
                break

        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            if event_envelope:
                log.info(
                    f"Projection {func.__name__} completed for "
                    f"{event_envelope.event_type} in {duration:.3f}s"
                )
            return result

        except Exception as e:
            duration = time.time() - start_time
            if event_envelope:
                log.error(
                    f"Projection {func.__name__} failed for "
                    f"{event_envelope.event_type} after {duration:.3f}s: {e}"
                )
            raise

    return wrapper


# =============================================================================
# Projector Info
# =============================================================================

def get_projector_info() -> Dict[str, Any]:
    """Get information about all registered projectors."""
    info = {
        "sync": {"domains": {}, "total_handlers": 0, "total_events": len(_SYNC_PROJECTION_HANDLERS)},
        "async": {"domains": {}, "total_handlers": 0, "total_events": len(_ASYNC_PROJECTION_HANDLERS)}
    }

    # Sync handlers
    for event_type, handlers in _SYNC_PROJECTION_HANDLERS.items():
        for handler in handlers:
            domain = handler.domain
            if domain not in info["sync"]["domains"]:
                info["sync"]["domains"][domain] = {"handlers": [], "event_types": set()}

            info["sync"]["domains"][domain]["handlers"].append({
                "method": handler.method_name,
                "event_type": handler.event_type,
                "priority": handler.priority,
                "timeout": handler.timeout
            })
            info["sync"]["domains"][domain]["event_types"].add(handler.event_type)
            info["sync"]["total_handlers"] += 1

    # Async handlers
    for event_type, handlers in _ASYNC_PROJECTION_HANDLERS.items():
        for handler in handlers:
            domain = handler.domain
            if domain not in info["async"]["domains"]:
                info["async"]["domains"][domain] = {"handlers": [], "event_types": set()}

            info["async"]["domains"][domain]["handlers"].append({
                "method": handler.method_name,
                "event_type": handler.event_type,
                "priority": handler.priority
            })
            info["async"]["domains"][domain]["event_types"].add(handler.event_type)
            info["async"]["total_handlers"] += 1

    # Convert sets to lists for JSON serialization
    for mode in ["sync", "async"]:
        for domain in info[mode]["domains"]:
            info[mode]["domains"][domain]["event_types"] = list(
                info[mode]["domains"][domain]["event_types"]
            )

    return info


# =============================================================================
# Backwards Compatibility Exports
# =============================================================================

# For compatibility with existing code using sync_decorators
SYNC_PROJECTION_REGISTRY = _SYNC_PROJECTION_HANDLERS
ASYNC_PROJECTION_REGISTRY = _ASYNC_PROJECTION_HANDLERS

# =============================================================================
# EOF
# =============================================================================
