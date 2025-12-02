# =============================================================================
# File: app/infra/event_bus/event_registry.py
# Description: Event registry with auto-registration support
#              Manual registry contains ONLY system/generic events
#              Domain events are auto-registered via @domain_event decorator
# =============================================================================

from __future__ import annotations
from typing import Dict, Type, Optional
from pydantic import BaseModel, ConfigDict

# --- System Events ---
# WebSocket events removed - not used in event registry
# from app.common.models.wellwon_model import (
#     WebSocketClientConnectedEvent,
#     WebSocketClientDisconnectedEvent
# )

# Import saga events (consolidated in infra/saga)
from app.infra.saga.saga_events import (
    SagaStarted, SagaStepStarted, SagaStepCompleted,
    SagaStepFailed, SagaCompleted, SagaFailed,
    SagaCompensationStarted, SagaCompensationCompleted,
    SagaTimedOut, SagaRetrying
)

# =============================================================================
# SystemEvent - Generic system event class
# =============================================================================

class SystemEvent(BaseModel):
    """
    Generic system event for infrastructure/monitoring events.
    Used when specific event class doesn't exist.
    """
    model_config = ConfigDict(extra='allow')

    event_type: str
    timestamp: Optional[str] = None
    source: Optional[str] = None
    data: Optional[Dict] = None


# =============================================================================
# MANUAL REGISTRY - System/Generic Events ONLY
# =============================================================================
# Domain events (user_account, broker_connection, order, etc.) are now
# auto-registered via @domain_event decorator in events.py files.
# This manual registry contains ONLY:
# - System infrastructure events
# - Generic event mappings (worker_*, data_integrity_*, etc.)
# - WebSocket/streaming events
# - Legacy/compatibility events
# =============================================================================

EVENT_TYPE_TO_PYDANTIC_MODEL: Dict[str, Type[BaseModel]] = {
    # ==========================================================================
    # Data Integrity Monitor Events (BaseEvent dataclasses -> SystemEvent)
    # ==========================================================================
    "IntegrityCheckStarted": SystemEvent,
    "IntegrityCheckCompleted": SystemEvent,
    "IntegrityMetricsUpdate": SystemEvent,
    "IntegrityRecoveryStarted": SystemEvent,
    "IntegrityAlertRaised": SystemEvent,
    "AccountDiscoveryInitiated": SystemEvent,

    # NOTE: AccountDiscoveryStarted, AccountDiscoveryCompleted, AllAccountsRefreshCompleted,
    # BulkArchiveCompleted, BrokerAccountsDeleted are now domain events (auto-registered)

    # ==========================================================================
    # Account Recovery Events
    # ==========================================================================
    "AccountRecoveryTriggered": SystemEvent,
    "AccountRecoveryInitiated": SystemEvent,
    "AccountRecoveryCompleted": SystemEvent,
    "AccountRecoveryFailed": SystemEvent,

    # ==========================================================================
    # Connection Recovery Service Events
    # ==========================================================================
    "ConnectionRecoveryMetrics": SystemEvent,
    "broker_connection_healthy": SystemEvent,

    # ==========================================================================
    # WebSocket Events - Commented out (events not defined)
    # ==========================================================================
    # "WebSocketClientConnected": WebSocketClientConnectedEvent,
    # "WebSocketClientDisconnected": WebSocketClientDisconnectedEvent,

    # ==========================================================================
    # Saga Events (from common/events/saga_events.py)
    # ==========================================================================
    "SagaStarted": SagaStarted,
    "SagaStepStarted": SagaStepStarted,
    "SagaStepCompleted": SagaStepCompleted,
    "SagaStepFailed": SagaStepFailed,
    "SagaCompleted": SagaCompleted,
    "SagaFailed": SagaFailed,
    "SagaCompensationStarted": SagaCompensationStarted,
    "SagaCompensationCompleted": SagaCompensationCompleted,
    "SagaTimedOut": SagaTimedOut,
    "SagaRetrying": SagaRetrying,

    # ==========================================================================
    # Worker Lifecycle Events
    # ==========================================================================
    "worker_started": SystemEvent,
    "worker_stopped": SystemEvent,
    "worker_heartbeat": SystemEvent,
    "worker_error": SystemEvent,

    # ==========================================================================
    # Streaming / Market Data Events (generic handlers)
    # ==========================================================================
    "quote_update": SystemEvent,
    "trade_update": SystemEvent,
    "bar_update": SystemEvent,
    "orderbook_update": SystemEvent,
    "market_status_update": SystemEvent,

    # ==========================================================================
    # Adapter Pool Events
    # ==========================================================================
    "adapter_created": SystemEvent,
    "adapter_removed": SystemEvent,
    "adapter_health_check": SystemEvent,
    "adapter_pool_metrics": SystemEvent,

    # ==========================================================================
    # System Metrics / Monitoring
    # ==========================================================================
    "system_metrics": SystemEvent,
    "health_check": SystemEvent,
    "performance_metrics": SystemEvent,

    # ==========================================================================
    # Legacy / Compatibility Events
    # ==========================================================================
    "generic_system_event": SystemEvent,

    # ==========================================================================
    # CES Events (Compensating Event System - External Change Detection)
    # Pattern: Greg Young's Compensating Events via PostgreSQL triggers
    # These events are generated when data is modified EXTERNALLY (bypassing app)
    # ==========================================================================
    "UserRoleChangedExternally": SystemEvent,
    "UserStatusChangedExternally": SystemEvent,
    "UserTypeChangedExternally": SystemEvent,
    "UserEmailVerifiedExternally": SystemEvent,
    "UserDeveloperStatusChangedExternally": SystemEvent,
    "UserAdminFieldsChangedExternally": SystemEvent,
}


# =============================================================================
# AUTO-REGISTRATION SUPPORT (Nov 2025)
# =============================================================================
# Domain events are auto-registered from @domain_event decorators in events.py
# The decorator system automatically populates the registry on import.
# =============================================================================

try:
    from app.infra.event_bus.event_decorators import (
        get_auto_registered_events,
        merge_with_manual_registry
    )
    _AUTO_REGISTRATION_AVAILABLE = True
except ImportError:
    _AUTO_REGISTRATION_AVAILABLE = False
    get_auto_registered_events = None
    merge_with_manual_registry = None

# Merge manual and auto-registered events
# Auto-registered events (via @domain_event decorator) take precedence over manual entries
if _AUTO_REGISTRATION_AVAILABLE and merge_with_manual_registry:
    _MANUAL_REGISTRY = EVENT_TYPE_TO_PYDANTIC_MODEL.copy()
    EVENT_TYPE_TO_PYDANTIC_MODEL = merge_with_manual_registry(_MANUAL_REGISTRY)


# =============================================================================
# Registry Access Functions
# =============================================================================

def get_event_model(event_type: str) -> Optional[Type[BaseModel]]:
    """
    Get Pydantic model class for an event type.

    This function uses LATE BINDING to ensure auto-registered events are included
    even if they were registered after this module was first imported.

    Args:
        event_type: The event type string (e.g., "UserAccountCreated")

    Returns:
        Pydantic model class or None if not found
    """
    # First check merged registry (fast path)
    if event_type in EVENT_TYPE_TO_PYDANTIC_MODEL:
        return EVENT_TYPE_TO_PYDANTIC_MODEL[event_type]

    # Late binding: check auto-registered events for events registered after import
    if _AUTO_REGISTRATION_AVAILABLE and get_auto_registered_events:
        auto_events = get_auto_registered_events()
        if event_type in auto_events:
            return auto_events[event_type]

    return None


def is_registered_event(event_type: str) -> bool:
    """Check if an event type is registered"""
    return event_type in EVENT_TYPE_TO_PYDANTIC_MODEL


def get_all_event_types() -> list[str]:
    """Get list of all registered event types"""
    return list(EVENT_TYPE_TO_PYDANTIC_MODEL.keys())


def get_registry_stats() -> dict:
    """Get statistics about the event registry"""
    auto_count = 0
    manual_count = len(_MANUAL_REGISTRY) if _AUTO_REGISTRATION_AVAILABLE else len(EVENT_TYPE_TO_PYDANTIC_MODEL)

    if _AUTO_REGISTRATION_AVAILABLE and get_auto_registered_events:
        auto_count = len(get_auto_registered_events())

    return {
        "total_events": len(EVENT_TYPE_TO_PYDANTIC_MODEL),
        "auto_registered": auto_count,
        "manual_entries": manual_count,
        "auto_registration_enabled": _AUTO_REGISTRATION_AVAILABLE
    }


# =============================================================================
# EOF
# =============================================================================
