# app/config/event_store_config.py
# =============================================================================
# File: app/config/event_store_config.py
# Description: Unified Event Store configuration for WellWon
# Backend: KurrentDB (EventStoreDB)
# UPDATED: Using BaseConfig pattern
# =============================================================================

from functools import lru_cache
from typing import Optional, Dict
from pydantic_settings import SettingsConfigDict
from pydantic import Field, SecretStr

from app.common.base.base_config import BaseConfig, BASE_CONFIG_DICT


class EventStoreConfig(BaseConfig):
    """
    Unified Event Store configuration for WellWon.

    Primary backend: KurrentDB (EventStoreDB) for high-performance event sourcing

    Features:
    - Fast aggregate queries (< 1ms vs 5-10s with Kafka)
    - Built-in optimistic concurrency control
    - Native stream-per-aggregate model
    - Efficient snapshots with $maxCount=1 pattern
    - Synchronous projections for critical consistency

    Architecture:
    - KurrentDB: Event store (10-year retention)
    - Redpanda: Transport layer (7-day retention)
    - PostgreSQL: Read models and projections
    """

    model_config = SettingsConfigDict(
        **BASE_CONFIG_DICT,
        env_prefix='KURRENTDB_',
    )

    # =========================================================================
    # Connection Settings
    # =========================================================================
    connection_string: str = "esdb://localhost:12113?tls=false"
    """
    KurrentDB connection string.

    Format: esdb://[username:password@]host:port[?tls=true|false]

    Examples:
    - Development: esdb://localhost:2113?tls=false
    - Production: esdb://admin:changeit@eventstoredb:2113?tls=true
    - Cluster: esdb://node1:2113,node2:2113,node3:2113?tls=true
    """

    username: Optional[str] = None
    """KurrentDB username (if using authentication)"""

    password: Optional[SecretStr] = None
    """KurrentDB password (if using authentication)"""

    # =========================================================================
    # Stream Naming
    # =========================================================================
    stream_prefix: str = ""
    """
    Prefix for all streams (empty by default per KurrentDB best practices).

    KurrentDB uses hyphen (-) to categorize streams: everything before
    the first hyphen is the category. For proper $ce- (category) streams,
    use format: AggregateType-uuid (e.g., BrokerConnection-uuid).

    Adding a prefix breaks category streams! If prefix is needed for
    multi-tenant setups, use underscore: prefix_AggregateType-uuid.

    Stream naming pattern (default, no prefix):
    - Format: {aggregate_type}-{aggregate_id}
    - Examples:
      • BrokerConnection-123e4567-e89b-12d3-a456-426614174000
      • VirtualBrokerAccount-456e7890-e89b-12d3-a456-426614174001
      • Position-789e0123-e89b-12d3-a456-426614174002
    """

    # =========================================================================
    # Snapshot Configuration
    # =========================================================================
    enable_snapshots: bool = True
    """Enable snapshot functionality"""

    enable_auto_snapshots: bool = True
    """
    Enable automatic snapshot creation.

    When enabled, the event store automatically creates snapshots when:
    1. An aggregate exceeds snapshot_interval events
    2. During aggregate save operations

    Background processor also creates snapshots asynchronously.
    """

    snapshot_interval: int = 200
    """
    Default number of events after which to create a snapshot.

    Default: 200 events

    Reasoning:
    - KurrentDB is fast enough that frequent snapshots aren't critical
    - 200 events = ~1-2ms aggregate load time
    - Lower interval = more storage, faster loads
    - Higher interval = less storage, slower loads
    """

    # Per-aggregate snapshot configuration
    aggregate_snapshot_intervals: Dict[str, int] = Field(
        default_factory=lambda: {
            "VirtualBroker": 100,
            "BrokerAccount": 50,
            "Order": 75,
            "Position": 75,
            "Trade": 100,
            "BrokerConnection": 150,
            "Strategy": 100,
            "Automation": 100,
            "UserAccount": 200,
            "User": 200,
        },
        description="Custom snapshot intervals per aggregate type"
    )

    snapshot_stream_suffix: str = "snapshot"
    """
    Suffix for snapshot streams.

    Snapshot stream naming: {stream_prefix}-{snapshot_stream_suffix}-{aggregate_type}-{aggregate_id}

    Example: snapshot-BrokerConnection-123e4567-e89b-12d3-a456-426614174000

    KurrentDB Strategy:
    - Use $maxCount=1 metadata on snapshot streams
    - This automatically keeps only the latest snapshot
    - No manual cleanup required
    """

    # Snapshot retention
    snapshot_retention_count: int = 3
    """Number of snapshots to keep per aggregate"""

    snapshot_cleanup_enabled: bool = True
    """Enable old snapshot cleanup"""

    # Snapshot performance
    enable_async_snapshots: bool = True
    """Create snapshots asynchronously"""

    snapshot_batch_size: int = 10
    """Max concurrent snapshot operations"""

    snapshot_timeout_seconds: int = 30
    """Timeout for snapshot creation"""

    # Snapshot monitoring
    enable_snapshot_metrics: bool = True
    """Enable snapshot metrics collection"""

    log_snapshot_creation: bool = True
    """Log snapshot creation events"""

    # =========================================================================
    # Timeout Settings
    # =========================================================================
    connection_timeout_seconds: int = 5
    """
    Timeout for initial connection to KurrentDB.
    Fast-fail if KurrentDB unavailable to prevent blocking startup.
    """

    read_timeout_seconds: int = 10
    """Timeout for read operations (get events, load aggregate)"""

    write_timeout_seconds: int = 5
    """Timeout for write operations (append events, save snapshot)"""

    subscription_timeout_seconds: int = 60
    """Timeout for subscription operations (catch-up, persistent)"""

    # =========================================================================
    # Retry Settings
    # =========================================================================
    append_retry_max_attempts: int = 3
    """Maximum retry attempts for append operations (on transient failures)"""

    append_retry_initial_delay_ms: int = 100
    """Initial delay for exponential backoff (milliseconds)"""

    append_retry_max_delay_ms: int = 2000
    """Maximum delay for exponential backoff (milliseconds)"""

    retry_multiplier: float = 2.0
    """Retry interval multiplier for exponential backoff"""

    # =========================================================================
    # Synchronous Projections
    # =========================================================================
    enable_sync_projections: bool = True
    """
    Enable synchronous projection processing.

    Synchronous projections run immediately during event append for critical consistency.
    Use for:
    - Financial operations (orders, positions, balances)
    - Authentication and security (user creation, password changes)
    - Race-condition-prone operations (OAuth flows, automation activation)
    """

    sync_projection_timeout: float = 5.0
    """
    Timeout for synchronous projections (seconds).

    SYNC projections run immediately during event append for critical consistency:
    - Account balances
    - Position tracking
    - Order status

    Default: 5 seconds (should complete in < 100ms typically)
    """

    # =========================================================================
    # Performance Tuning
    # =========================================================================
    connection_pool_size: int = 10
    """Connection pool size for KurrentDB clients"""

    enable_stream_caching: bool = True
    """
    Enable stream metadata caching.

    Caches stream versions and metadata to reduce KurrentDB calls.
    Safe because KurrentDB has built-in OCC.
    """

    cache_ttl_seconds: int = 60
    """TTL for stream metadata cache (seconds)"""

    version_cache_enabled: bool = True
    """Enable aggregate version caching"""

    version_cache_ttl_seconds: int = 300
    """Version cache TTL in seconds (5 minutes)"""

    # =========================================================================
    # Enhanced Features
    # =========================================================================

    # Distributed Locking
    enable_locking: bool = True
    """Enable distributed locking for aggregates"""

    lock_timeout_ms: int = 30000
    """Default lock timeout in milliseconds (30 seconds)"""

    lock_retry_attempts: int = 3
    """Number of lock acquisition retry attempts"""

    lock_retry_delay_ms: int = 100
    """Initial delay between lock retries"""

    # Event Sequencing
    enable_sequencing: bool = True
    """Enable global event sequencing"""

    global_sequence_key: str = "event_store:global_sequence"
    """Redis key for global sequence counter"""

    # Saga Support
    enable_saga_tracking: bool = True
    """Enable saga event tracking"""

    # Outbox Pattern
    enable_outbox: bool = True
    """Enable transactional outbox pattern"""

    # =========================================================================
    # Circuit Breaker Configuration
    # =========================================================================
    circuit_breaker_enabled: bool = True
    """Enable circuit breaker for KurrentDB operations"""

    circuit_breaker_failure_threshold: int = 5
    """Number of failures before opening circuit"""

    circuit_breaker_recovery_timeout: int = 60
    """Recovery timeout in seconds"""

    # =========================================================================
    # Feature Flags
    # =========================================================================
    enable_optimistic_concurrency: bool = True
    """
    Enable optimistic concurrency control.

    When enabled, uses KurrentDB's built-in OCC (ExpectedVersion).
    Should always be enabled for production.
    """

    # =========================================================================
    # Monitoring and Metrics
    # =========================================================================
    enable_metrics: bool = True
    """Enable Prometheus metrics for KurrentDB operations"""

    metrics_namespace: str = "wellwon"
    """Prometheus metrics namespace"""

    metrics_subsystem: str = "event_store"
    """Prometheus metrics subsystem"""

    log_stream_operations: bool = False
    """Log all stream operations (very verbose, use for debugging only)"""

    log_append_events: bool = False
    """Log all event appends (verbose, use for debugging only)"""

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def get_stream_name(self, aggregate_type: str, aggregate_id: str) -> str:
        """
        Get stream name for an aggregate.

        Args:
            aggregate_type: Aggregate type (e.g., "user_account", "broker_connection")
            aggregate_id: Aggregate ID (UUID as string)

        Returns:
            Stream name in format: {prefix}-{type}-{id} or {type}-{id}

        Example:
             config.get_stream_name("BrokerConnection", "123")
            'BrokerConnection-123'
        """
        # Convert snake_case to PascalCase for readability
        aggregate_type_pascal = ''.join(word.capitalize() for word in aggregate_type.split('_'))

        if self.stream_prefix:
            return f"{self.stream_prefix}_{aggregate_type_pascal}-{aggregate_id}"
        else:
            return f"{aggregate_type_pascal}-{aggregate_id}"

    def get_snapshot_stream_name(self, aggregate_type: str, aggregate_id: str) -> str:
        """
        Get snapshot stream name for an aggregate.

        Args:
            aggregate_type: Aggregate type (e.g., "user_account", "broker_connection")
            aggregate_id: Aggregate ID (UUID as string)

        Returns:
            Snapshot stream name in format: [prefix_]snapshot_{type}-{id}

        Example:
             config.get_snapshot_stream_name("broker_connection", "123")
            'snapshot_BrokerConnection-123'
        """
        # Convert snake_case to PascalCase
        aggregate_type_pascal = ''.join(word.capitalize() for word in aggregate_type.split('_'))
        prefix = f"{self.stream_prefix}_" if self.stream_prefix else ""
        return f"{prefix}{self.snapshot_stream_suffix}_{aggregate_type_pascal}-{aggregate_id}"

    def get_category_stream_name(self, aggregate_type: str) -> str:
        """
        Get category stream name for projection subscriptions.

        KurrentDB category streams ($ce-{category}) aggregate all events
        of a specific type across all aggregates. Category is everything
        before the first hyphen in the stream name.

        Args:
            aggregate_type: Aggregate type (e.g., "broker_connection")

        Returns:
            Category stream name in format: $ce-{category}
            - Without prefix: $ce-BrokerConnection
            - With prefix: $ce-prefix_BrokerConnection

        Example:
             config.get_category_stream_name("broker_connection")
            '$ce-BrokerConnection'
        """
        # Convert snake_case to PascalCase
        aggregate_type_pascal = ''.join(word.capitalize() for word in aggregate_type.split('_'))

        if self.stream_prefix:
            # With prefix: $ce-prefix_AggregateType
            return f"$ce-{self.stream_prefix}_{aggregate_type_pascal}"
        else:
            # Without prefix: $ce-AggregateType
            return f"$ce-{aggregate_type_pascal}"

    def get_snapshot_interval(self, aggregate_type: str) -> int:
        """Get snapshot interval for specific aggregate type"""
        return self.aggregate_snapshot_intervals.get(
            aggregate_type,
            self.snapshot_interval
        )

    @classmethod
    def from_env(cls) -> "EventStoreConfig":
        """Create config from environment (backward compatibility)"""
        return cls()


# =============================================================================
# Factory Function
# =============================================================================

@lru_cache(maxsize=1)
def get_event_store_config() -> EventStoreConfig:
    """Get Event Store configuration singleton (cached)."""
    return EventStoreConfig()


def reset_event_store_config() -> None:
    """Reset config singleton (for testing)."""
    get_event_store_config.cache_clear()


# Backward compatibility alias
event_store_config = get_event_store_config()
