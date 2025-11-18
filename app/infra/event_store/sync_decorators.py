# app/infra/event_store/sync_decorators.py
# =============================================================================
# File: app/infra/event_store/sync_decorators.py
# Description: Auto-registration decorators for synchronous projections
#              Works only with EventEnvelope - no adapters or legacy support
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

log = logging.getLogger("tradecore.sync_projections.decorators")

# Configuration
DEFAULT_TIMEOUT = 2.0  # seconds
DEFAULT_PRIORITY = 10  # lower number = higher priority
MAX_METRIC_KEYS = 1000  # Maximum number of event types to track metrics for

# Thread-safe lock for registry access
_REGISTRY_LOCK = threading.Lock()

@dataclass
class ProjectionHandler:
    """Metadata for a sync projection handler"""
    handler_func: Callable[[Any, EventEnvelope], Awaitable[None]]
    event_type: str
    domain: str
    projector_class: Optional[Type] = None
    method_name: Optional[str] = None
    timeout: float = DEFAULT_TIMEOUT
    priority: int = DEFAULT_PRIORITY
    description: Optional[str] = None
    module: Optional[str] = None


# Global registry for sync projection handlers
_SYNC_PROJECTION_HANDLERS: Dict[str, List[ProjectionHandler]] = {}

# Performance tracking
_PROJECTION_METRICS: Dict[str, List[float]] = {}
_PROJECTION_ERRORS: Dict[str, int] = {}


def sync_projection(
        event_type: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        priority: int = DEFAULT_PRIORITY,
        description: Optional[str] = None
):
    """
    Decorator for marking methods as synchronous projection handlers.
    All handlers receive EventEnvelope objects.

    Usage:
        class UserProjector:
            @sync_projection("UserAccountCreated")
            async def on_user_created(self, envelope: EventEnvelope):
                user_id = envelope.aggregate_id
                event_data = envelope.event_data
                # Handle event
                pass

            @sync_projection("UserAccountDeleted", priority=1, timeout=3.0)
            async def on_user_deleted(self, envelope: EventEnvelope):
                # High priority handler with longer timeout
                pass

    Args:
        event_type: The event type to handle
        timeout: Maximum execution time in seconds
        priority: Execution priority (lower = higher priority)
        description: Optional description for documentation
    """

    def decorator(func: Callable) -> Callable:
        # Extract domain from module path
        module = inspect.getmodule(func)
        module_name = module.__name__ if module else ""

        # Extract domain name from module path (e.g., app.user_account.projectors -> user_account)
        domain = "unknown"
        if "." in module_name:
            parts = module_name.split(".")
            for i, part in enumerate(parts):
                if part in ["user_account", "broker_connection", "broker_account", "virtual_broker", "order",
                            "position"]:
                    domain = part
                    break

        # Create handler metadata
        handler = ProjectionHandler(
            handler_func=func,
            event_type=event_type,
            domain=domain,
            method_name=func.__name__,
            timeout=timeout,
            priority=priority,
            description=description or func.__doc__,
            module=module_name
        )

        # Register in global registry - THREAD-SAFE
        with _REGISTRY_LOCK:
            if event_type not in _SYNC_PROJECTION_HANDLERS:
                _SYNC_PROJECTION_HANDLERS[event_type] = []

            _SYNC_PROJECTION_HANDLERS[event_type].append(handler)

            # Mark the function as a sync projection handler
            func._is_sync_projection = True
            func._projection_metadata = handler

            log.debug(
                f"Registered sync projection: {func.__name__} "
                f"for {event_type} in {domain} "
                f"(priority: {priority}, timeout: {timeout}s)"
            )

        # Return the original function unchanged
        return func

    return decorator


async def execute_sync_projections(
        envelope: EventEnvelope,
        projector_instances: Dict[str, Any],
        timeout_override: Optional[float] = None
) -> Dict[str, Any]:
    """
    Execute all registered sync projections for an event.

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

    # Sort handlers by priority
    sorted_handlers = sorted(handlers, key=lambda h: h.priority)

    start_time = time.time()
    executed = 0
    errors = []

    for handler in sorted_handlers:
        handler_start = time.time()
        timeout = timeout_override or handler.timeout

        try:
            # Get projector instance for this handler's domain
            if handler.domain not in projector_instances:
                log.warning(
                    f"No projector instance for domain {handler.domain}, "
                    f"skipping handler {handler.method_name}"
                )
                continue

            instance = projector_instances[handler.domain]

            # Execute handler with timeout
            await asyncio.wait_for(
                handler.handler_func(instance, envelope),
                timeout=timeout
            )

            executed += 1

            # Track performance - THREAD-SAFE with memory management
            duration = time.time() - handler_start
            with _REGISTRY_LOCK:
                if event_type not in _PROJECTION_METRICS:
                    # Check if we're at limit and need to clean up old metrics
                    if len(_PROJECTION_METRICS) >= MAX_METRIC_KEYS:
                        # Remove oldest 10% of metric keys by average execution time (least recent)
                        sorted_by_count = sorted(
                            _PROJECTION_METRICS.items(),
                            key=lambda x: len(x[1])  # Sort by measurement count
                        )
                        cleanup_count = MAX_METRIC_KEYS // 10
                        for old_key, _ in sorted_by_count[:cleanup_count]:
                            del _PROJECTION_METRICS[old_key]
                        log.info(
                            f"Cleaned up {cleanup_count} old projection metrics "
                            f"(limit: {MAX_METRIC_KEYS})"
                        )

                    _PROJECTION_METRICS[event_type] = []

                _PROJECTION_METRICS[event_type].append(duration)

                # Keep only last 100 measurements
                if len(_PROJECTION_METRICS[event_type]) > 100:
                    _PROJECTION_METRICS[event_type] = _PROJECTION_METRICS[event_type][-100:]

            if duration > timeout * 0.8:  # Warn if close to timeout
                log.warning(
                    f"Sync projection {handler.method_name} for {event_type} "
                    f"took {duration:.3f}s (close to timeout {timeout}s)"
                )

        except asyncio.TimeoutError:
            error_msg = (
                f"Sync projection {handler.method_name} for {event_type} "
                f"timed out after {timeout}s"
            )
            log.error(error_msg)
            errors.append(error_msg)

            # Track errors
            if event_type not in _PROJECTION_ERRORS:
                _PROJECTION_ERRORS[event_type] = 0
            _PROJECTION_ERRORS[event_type] += 1

        except Exception as e:
            error_msg = (
                f"Error in sync projection {handler.method_name} "
                f"for {event_type}: {e}"
            )
            log.error(error_msg, exc_info=True)
            errors.append(error_msg)

            if event_type not in _PROJECTION_ERRORS:
                _PROJECTION_ERRORS[event_type] = 0
            _PROJECTION_ERRORS[event_type] += 1

    total_duration = time.time() - start_time

    if total_duration > 0.5:  # Warn if total time is high
        log.warning(
            f"Sync projections for {event_type} took {total_duration:.3f}s total "
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


def get_all_sync_events() -> Set[str]:
    """
    Get all registered sync event types from @sync_projection decorators.

    Single source of truth: Events that have @sync_projection handlers ARE sync events.
    No need for separate sync_events.py config files.
    """
    return set(_SYNC_PROJECTION_HANDLERS.keys())


def get_sync_handlers(event_type: str) -> List[ProjectionHandler]:
    """Get all handlers for a specific event type"""
    return _SYNC_PROJECTION_HANDLERS.get(event_type, [])


def get_sync_projection_metrics() -> Dict[str, Any]:
    """Get performance metrics for sync projections"""
    # Extract unique domains from handlers
    domains = set()
    for handlers in _SYNC_PROJECTION_HANDLERS.values():
        for handler in handlers:
            if handler.domain and handler.domain != "unknown":
                domains.add(handler.domain)

    metrics = {
        "total_event_types": len(_SYNC_PROJECTION_HANDLERS),
        "total_handlers": sum(len(h) for h in _SYNC_PROJECTION_HANDLERS.values()),
        "domains": sorted(list(domains)),
        "total_sync_events": len(get_all_sync_events()),
        "performance": {},
        "errors": dict(_PROJECTION_ERRORS)
    }

    # Calculate performance statistics
    for event_type, durations in _PROJECTION_METRICS.items():
        if durations:
            metrics["performance"][event_type] = {
                "avg_ms": sum(durations) / len(durations) * 1000,
                "min_ms": min(durations) * 1000,
                "max_ms": max(durations) * 1000,
                "p95_ms": sorted(durations)[int(len(durations) * 0.95)] * 1000 if len(durations) > 20 else max(
                    durations) * 1000,
                "samples": len(durations)
            }

    return metrics


def validate_sync_projections() -> Dict[str, List[str]]:
    """
    Validate sync projection handlers.
    Returns dict of issues found.
    """
    issues = {
        "missing_handlers": [],  # Not used anymore (decorator IS the registration)
        "missing_events": [],     # Not used anymore
        "performance_warnings": []
    }

    # Check for performance issues
    for event_type, durations in _PROJECTION_METRICS.items():
        if durations and sum(durations) / len(durations) > 0.5:  # Avg > 500ms
            issues["performance_warnings"].append(
                f"{event_type}: avg {sum(durations) / len(durations) * 1000:.0f}ms"
            )

    return issues


def clear_registries():
    """Clear all registries - useful for testing"""
    _SYNC_PROJECTION_HANDLERS.clear()
    _PROJECTION_METRICS.clear()
    _PROJECTION_ERRORS.clear()
    log.info("Cleared all sync projection registries")


async def auto_register_sync_projections(
        event_store,
        projector_instances: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Register all decorated sync projections with the event store.

    Args:
        event_store: The RedPandaEventStore instance
        projector_instances: Dict of domain -> projector instance

    Returns:
        Registration statistics
    """
    # Get all sync events from @sync_projection decorators
    all_sync_events = get_all_sync_events()

    if not all_sync_events:
        log.warning("No sync projection handlers registered")
        return {
            "sync_events": 0,
            "handlers_registered": 0,
            "domains": [],
            "validation": validate_sync_projections()
        }

    # Enable sync projections in event store
    event_store.enable_synchronous_projections(all_sync_events)

    # Create wrapper function for event store
    async def projection_handler(envelope: EventEnvelope) -> None:
        await execute_sync_projections(envelope, projector_instances)

    # Register single handler for each event type
    registered = 0
    for event_type in all_sync_events:
        if _SYNC_PROJECTION_HANDLERS.get(event_type):
            event_store.register_sync_projection(event_type, projection_handler)
            registered += 1

    # Extract unique domains
    domains = set()
    for handlers in _SYNC_PROJECTION_HANDLERS.values():
        for handler in handlers:
            # Handle both ProjectionHandler instances and legacy function objects
            if hasattr(handler, 'domain') and handler.domain and handler.domain != "unknown":
                domains.add(handler.domain)

    log.info(
        f"Auto-registered {registered} sync projection handlers "
        f"for {len(all_sync_events)} event types across {len(domains)} domains"
    )

    # Validate configuration
    validation = validate_sync_projections()

    return {
        "sync_events": len(all_sync_events),
        "handlers_registered": registered,
        "domains": sorted(list(domains)),
        "validation": validation
    }


# Performance monitoring decorator
def monitor_projection(func: Callable) -> Callable:
    """
    Additional decorator to add detailed monitoring to a projection handler.

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

        # Extract envelope from args
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


# Helper function to get projector info
def get_projector_info() -> Dict[str, Any]:
    """Get information about registered projectors"""
    info = {
        "domains": {},
        "total_handlers": 0,
        "total_events": len(_SYNC_PROJECTION_HANDLERS)
    }

    for event_type, handlers in _SYNC_PROJECTION_HANDLERS.items():
        for handler in handlers:
            domain = handler.domain
            if domain not in info["domains"]:
                info["domains"][domain] = {
                    "handlers": [],
                    "event_types": set()
                }

            info["domains"][domain]["handlers"].append({
                "method": handler.method_name,
                "event_type": handler.event_type,
                "priority": handler.priority,
                "timeout": handler.timeout
            })
            info["domains"][domain]["event_types"].add(handler.event_type)
            info["total_handlers"] += 1

    # Convert sets to lists for JSON serialization
    for domain in info["domains"]:
        info["domains"][domain]["event_types"] = list(info["domains"][domain]["event_types"])

    return info


# Export for compatibility (used by KurrentDBEventStore)
SYNC_PROJECTION_REGISTRY = _SYNC_PROJECTION_HANDLERS

# =============================================================================
# EOF
# =============================================================================