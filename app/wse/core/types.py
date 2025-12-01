# =============================================================================
# File: app/wse/core/types.py
# Description: WSE Type Definitions (Enums, Protocols, Dataclasses)
# =============================================================================

"""
WSE Core Types

Type definitions for WebSocket Event System:
- EventPriority: Priority levels for events
- DeliveryGuarantee: Delivery semantics
- EventHandler: Protocol for event handlers
- EventMetadata: Event metadata
- Subscription: Subscription configuration
- SubscriptionStats: Subscription statistics
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional, Protocol, Set


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class EventPriority(Enum):
    """Event priority levels"""
    CRITICAL = 10
    HIGH = 8
    NORMAL = 5
    LOW = 3
    BACKGROUND = 1


class DeliveryGuarantee(Enum):
    """Event delivery guarantees"""
    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


class MessageCategory(Enum):
    """
    Message category for WSE Protocol v2.

    Categories:
        S (Snapshot): Full state dump for initial sync or reconnect
        U (Update): Incremental delta updates (default)
        WSE (System): Protocol/system messages (ping, pong, errors, etc.)
    """
    SNAPSHOT = "S"
    UPDATE = "U"
    SYSTEM = "WSE"


# System event types that belong to WSE category (protocol/infrastructure messages)
WSE_SYSTEM_EVENT_TYPES = frozenset({
    # Connection lifecycle
    'server_ready',
    'server_hello',
    'client_hello',
    'client_hello_ack',
    'connection_state_change',
    'connection_state_response',
    'connection_stats',
    'connection_quality',

    # Ping/Pong heartbeat
    'ping',
    'PING',
    'pong',
    'PONG',
    'heartbeat',

    # Subscription management
    'subscription',
    'subscription_update',
    'subscription_request',

    # Sync/snapshot completion
    'sync_request',
    'sync_response',
    'snapshot_complete',

    # Health and metrics
    'health_check',
    'health_check_request',
    'health_check_response',
    'metrics_request',
    'metrics_response',

    # Configuration
    'config_request',
    'config_response',
    'config_update',
    'config_update_response',

    # Security
    'encryption_request',
    'encryption_response',
    'key_rotation_request',
    'key_rotation_response',

    # Batching
    'batch',
    'batch_message',
    'batch_message_result',

    # Debug/diagnostics
    'debug_request',
    'debug_response',
    'debug_handlers',
    'sequence_stats_request',
    'sequence_stats_response',

    # Errors and warnings
    'error',
    'rate_limit_warning',

    # System status
    'system_status',
    'system_status_request',
    'system_announcement',

    # Priority messages (system routing)
    'priority_message',
})

# Snapshot event types (full state dump) - identified by 'snapshot' in name
# These are detected dynamically by checking if 'snapshot' is in the event type


# ─────────────────────────────────────────────────────────────────────────────
# Protocols
# ─────────────────────────────────────────────────────────────────────────────

class EventHandler(Protocol):
    """Protocol for event handlers"""

    async def __call__(self, event: Dict[str, Any]) -> None: ...


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EventMetadata:
    """Metadata for events"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    priority: EventPriority = EventPriority.NORMAL
    ttl: Optional[int] = None  # seconds
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    source: Optional[str] = None
    compressed: bool = False
    encrypted: bool = False
    user_id: Optional[str] = None


@dataclass
class Subscription:
    """Represents an event subscription"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subscriber_id: str = ""
    topics: Set[str] = field(default_factory=set)
    handler: EventHandler = None
    filters: Dict[str, Any] = field(default_factory=dict)
    transform: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True
    delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE
    max_retries: int = 3
    retry_delay: float = 1.0
    dead_letter_topic: Optional[str] = None
    batch_size: int = 100
    batch_timeout: float = 0.1
    # CRITICAL: Track last delivered to prevent duplicates
    last_delivered_id: Optional[str] = None
    last_delivery_time: Optional[datetime] = None


@dataclass
class SubscriptionStats:
    """Statistics for a subscription"""
    messages_received: int = 0
    messages_processed: int = 0
    messages_failed: int = 0
    messages_filtered: int = 0
    messages_transformed: int = 0
    messages_duplicate: int = 0
    last_message_at: Optional[datetime] = None
    average_processing_time: float = 0.0
    total_processing_time: float = 0.0


# =============================================================================
# EOF
# =============================================================================
