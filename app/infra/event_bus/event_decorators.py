# =============================================================================
# File: app/infra/event_bus/event_decorators.py
# Description: Auto-registration decorators for domain events
#              Eliminates manual EVENT_TYPE_TO_PYDANTIC_MODEL registry updates
# =============================================================================

import logging
import inspect
import threading
from typing import Type, Dict, Any, Optional, Set
from functools import wraps
from pydantic import BaseModel

log = logging.getLogger("wellwon.event_bus.decorators")

# Thread-safe lock for registry access
_REGISTRY_LOCK = threading.Lock()

# Global registry for auto-registered domain events
_AUTO_REGISTERED_EVENTS: Dict[str, Type[BaseModel]] = {}

# Track which domains have events
_DOMAIN_EVENTS: Dict[str, Set[str]] = {}

# Event categories
_EVENT_CATEGORIES: Dict[str, str] = {}

# Event metadata
_EVENT_METADATA: Dict[str, Dict[str, Any]] = {}


def domain_event(
        *,
        category: str = "domain",
        description: Optional[str] = None,
        sync: bool = False,
        priority: int = 10
):
    """
    Decorator for auto-registering domain events in the EventBus registry.

    This eliminates the need to manually add events to EVENT_TYPE_TO_PYDANTIC_MODEL
    in event_registry.py. Events are automatically registered when imported.

    Usage:
        @domain_event(category="user")
        class UserAccountCreated(BaseEvent):
            event_type: Literal["UserAccountCreated"] = "UserAccountCreated"
            user_id: UUID
            email: str

        @domain_event(category="broker_connection", sync=True)
        class BrokerConnectionEstablished(BaseEvent):
            event_type: Literal["BrokerConnectionEstablished"] = "BrokerConnectionEstablished"
            connection_id: UUID
            broker_name: str

        @domain_event(category="saga", priority=1)
        class SagaCompleted(BaseEvent):
            event_type: Literal["SagaCompleted"] = "SagaCompleted"
            saga_id: UUID

    Args:
        category: Event category (domain, saga, system, virtual_broker, integrity, streaming)
        description: Optional description for documentation
        sync: Whether this event should be processed synchronously (for SYNC projection)
        priority: Processing priority (lower = higher priority)

    Categories:
        - "domain": Standard domain events (User, Account, Connection, Order, etc.)
        - "saga": Saga orchestration events
        - "system": System/infrastructure events
        - "virtual_broker": Virtual broker specific events
        - "integrity": Data integrity monitoring events
        - "streaming": Real-time streaming events
    """

    def decorator(event_class: Type[BaseModel]) -> Type[BaseModel]:
        # Validate that it's a Pydantic model
        if not issubclass(event_class, BaseModel):
            raise TypeError(
                f"@domain_event can only be applied to Pydantic BaseModel classes. "
                f"{event_class.__name__} is not a BaseModel."
            )

        # Extract event_type from class
        # Try to get it from the model's fields or annotations
        event_type = None

        # Option 1: For Pydantic v2, check model_fields for event_type default value
        if hasattr(event_class, 'model_fields') and 'event_type' in event_class.model_fields:
            field_info = event_class.model_fields['event_type']
            if hasattr(field_info, 'default') and isinstance(field_info.default, str):
                event_type = field_info.default

        # Option 2: Check if event_type is defined as a class attribute (for non-Pydantic classes)
        if not event_type and hasattr(event_class, 'event_type'):
            event_type_value = getattr(event_class, 'event_type')
            # Handle Literal types
            if isinstance(event_type_value, str):
                event_type = event_type_value

        # Option 3: Use class name as fallback
        if not event_type:
            event_type = event_class.__name__

        # Extract domain from module path
        module = inspect.getmodule(event_class)
        module_name = module.__name__ if module else ""

        # Extract domain name from module path (e.g., app.user_account.events -> user_account)
        domain = "unknown"
        if "." in module_name:
            parts = module_name.split(".")
            known_domains = [
                "user_account", "broker_connection", "broker_account", "virtual_broker",
                "order", "position", "portfolio", "automation"
            ]
            for part in parts:
                if part in known_domains:
                    domain = part
                    break

        # Register event in global registry (idempotent) - THREAD-SAFE
        with _REGISTRY_LOCK:
            if event_type in _AUTO_REGISTERED_EVENTS:
                existing_class = _AUTO_REGISTERED_EVENTS[event_type]
                if existing_class is event_class:
                    # Same class, same decorator call - already registered, skip silently
                    # This happens when module is imported multiple times (Python caches it)
                    return event_class
                else:
                    # DIFFERENT class with same event_type - this IS a problem!
                    log.warning(
                        f"Event type '{event_type}' collision: "
                        f"already registered by {existing_class.__module__}.{existing_class.__name__}, "
                        f"now registering {event_class.__module__}.{event_class.__name__}"
                    )

            _AUTO_REGISTERED_EVENTS[event_type] = event_class

            # Track domain events
            if domain not in _DOMAIN_EVENTS:
                _DOMAIN_EVENTS[domain] = set()
            _DOMAIN_EVENTS[domain].add(event_type)

            # Store category
            _EVENT_CATEGORIES[event_type] = category

            # Store metadata
            _EVENT_METADATA[event_type] = {
                "event_class": event_class,
                "category": category,
                "domain": domain,
                "module": module_name,
                "description": description or event_class.__doc__,
                "sync": sync,
                "priority": priority
            }

            log.debug(
                f"Auto-registered event: {event_type} "
                f"(domain={domain}, category={category}, sync={sync})"
            )

            # Add metadata to the class for introspection
            event_class._event_metadata = _EVENT_METADATA[event_type]

        return event_class

    return decorator


def system_event(
        *,
        description: Optional[str] = None,
        priority: int = 10
):
    """
    Convenience decorator for system events.
    Equivalent to @domain_event(category="system")

    Usage:
        @system_event()
        class WorkerStarted(BaseEvent):
            event_type: Literal["WorkerStarted"] = "WorkerStarted"
            worker_id: str
    """
    return domain_event(category="system", description=description, priority=priority)


def saga_event(
        *,
        description: Optional[str] = None,
        priority: int = 5
):
    """
    Convenience decorator for saga events.
    Equivalent to @domain_event(category="saga", priority=5)

    Saga events typically have higher priority (lower number).

    Usage:
        @saga_event()
        class SagaStepCompleted(BaseEvent):
            event_type: Literal["SagaStepCompleted"] = "SagaStepCompleted"
            saga_id: UUID
            step_name: str
    """
    return domain_event(category="saga", description=description, priority=priority)


def streaming_event(
        *,
        description: Optional[str] = None,
        priority: int = 15
):
    """
    Convenience decorator for streaming/real-time events.
    Equivalent to @domain_event(category="streaming", priority=15)

    Streaming events typically have lower priority (higher number).

    Usage:
        @streaming_event()
        class QuoteUpdate(BaseEvent):
            event_type: Literal["QuoteUpdate"] = "QuoteUpdate"
            symbol: str
            price: Decimal
    """
    return domain_event(category="streaming", description=description, priority=priority)


# =============================================================================
# Registry Access Functions
# =============================================================================

def get_auto_registered_events() -> Dict[str, Type[BaseModel]]:
    """
    Get all auto-registered events.

    Returns:
        Dictionary mapping event_type to Pydantic model class
    """
    return _AUTO_REGISTERED_EVENTS.copy()


def get_domain_events(domain: str) -> Set[str]:
    """
    Get all event types for a specific domain.

    Args:
        domain: Domain name (e.g., "user_account", "broker_connection")

    Returns:
        Set of event type strings for that domain
    """
    return _DOMAIN_EVENTS.get(domain, set()).copy()


def get_event_category(event_type: str) -> Optional[str]:
    """
    Get the category of an event type.

    Args:
        event_type: The event type string

    Returns:
        Category string or None if not found
    """
    return _EVENT_CATEGORIES.get(event_type)


def get_event_metadata(event_type: str) -> Optional[Dict[str, Any]]:
    """
    Get metadata for an event type.

    Args:
        event_type: The event type string

    Returns:
        Metadata dictionary or None if not found
    """
    return _EVENT_METADATA.get(event_type)


def get_sync_events() -> Set[str]:
    """
    Get all event types marked as sync (for SYNC projection).

    Returns:
        Set of event type strings that should be processed synchronously
    """
    return {
        event_type
        for event_type, metadata in _EVENT_METADATA.items()
        if metadata.get("sync", False)
    }


def validate_event_registry() -> Dict[str, Any]:
    """
    Validate the auto-registered event registry.

    Returns:
        Validation report with statistics and any issues found
    """
    report = {
        "total_events": len(_AUTO_REGISTERED_EVENTS),
        "domains": {},
        "categories": {},
        "sync_events": len(get_sync_events()),
        "validation_errors": []
    }

    # Count by domain
    for domain, events in _DOMAIN_EVENTS.items():
        report["domains"][domain] = len(events)

    # Count by category
    for category in set(_EVENT_CATEGORIES.values()):
        count = sum(1 for c in _EVENT_CATEGORIES.values() if c == category)
        report["categories"][category] = count

    # Validate model classes
    for event_type, model_class in _AUTO_REGISTERED_EVENTS.items():
        try:
            if not issubclass(model_class, BaseModel):
                report["validation_errors"].append(
                    f"{event_type}: {model_class} is not a valid Pydantic model"
                )
        except TypeError:
            report["validation_errors"].append(
                f"{event_type}: {model_class} is not a valid class"
            )

    return report


def merge_with_manual_registry(manual_registry: Dict[str, Type[BaseModel]]) -> Dict[str, Type[BaseModel]]:
    """
    Merge auto-registered events with manual registry entries.
    Auto-registered events take precedence.

    Args:
        manual_registry: Manual EVENT_TYPE_TO_PYDANTIC_MODEL dictionary

    Returns:
        Combined registry with auto-registered events taking precedence
    """
    combined = manual_registry.copy()
    combined.update(_AUTO_REGISTERED_EVENTS)

    log.info(
        f"Merged event registry: {len(manual_registry)} manual + "
        f"{len(_AUTO_REGISTERED_EVENTS)} auto = {len(combined)} total"
    )

    return combined


# =============================================================================
# EOF
# =============================================================================
