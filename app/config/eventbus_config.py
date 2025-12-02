# app/config/eventbus_config.py
"""
Event Bus and Transport Configuration
UPDATED: Using BaseConfig pattern with Pydantic v2
"""

from functools import lru_cache
from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import SettingsConfigDict

from app.common.base.base_config import BaseConfig


class TopicType(str, Enum):
    """Topic type enumeration"""
    STREAM = "stream"
    SYSTEM = "system"
    SAGA = "saga"
    CQRS = "cqrs"
    EVENTSTORE = "eventstore"
    ALERTS = "alerts"


class TopicConfig(BaseModel):
    """Configuration for a specific topic"""
    name: str
    type: TopicType
    partitions: int = 1
    replication_factor: int = 1
    retention_ms: int = 604800000  # 7 days
    cleanup_policy: str = "delete"
    compression_type: str = "snappy"
    max_message_bytes: int = 1048576  # 1MB
    consumer_group: Optional[str] = None
    min_insync_replicas: int = 1
    unclean_leader_election_enable: bool = False
    segment_ms: int = 3600000  # 1 hour
    flush_messages: int = 10000
    flush_ms: int = 1000


class EventBusConfig(BaseConfig):
    """
    Event Bus configuration using Pydantic v2 BaseConfig pattern.
    Combines Kafka config, producer/consumer settings, and topic management.
    """

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix='REDPANDA_',
    )

    # =========================================================================
    # Connection Settings
    # =========================================================================
    bootstrap_servers: str = Field(
        default="localhost:29092",
        description="Kafka/RedPanda bootstrap servers"
    )
    client_id: str = Field(
        default="wellwon",
        description="Client identifier"
    )

    # =========================================================================
    # Producer Settings - Optimized for Throughput
    # =========================================================================
    producer_acks: str = Field(default="all", description="all, 1, 0")
    producer_compression_type: str = Field(default="lz4", description="lz4, snappy, zstd")
    producer_batch_size: int = Field(default=262144, description="256KB batch size")
    producer_linger_ms: int = Field(default=10, description="Linger time in ms")
    producer_buffer_memory: int = Field(default=67108864, description="64MB buffer")
    producer_max_in_flight_requests: int = Field(default=5)
    producer_retries: int = Field(default=3)
    producer_retry_backoff_ms: int = Field(default=100)

    # =========================================================================
    # Consumer Settings - Optimized for Stability
    # =========================================================================
    consumer_group_id_prefix: str = Field(default="synapse_worker")
    consumer_auto_offset_reset: str = Field(default="earliest")
    consumer_enable_auto_commit: bool = Field(default=False)
    consumer_max_poll_records: int = Field(default=500)
    consumer_fetch_min_bytes: int = Field(default=1, description="1 byte for instant SYNC events")
    consumer_fetch_max_wait_ms: int = Field(default=50, description="50ms for fast polling")
    consumer_session_timeout_ms: int = Field(default=45000, description="45 seconds")
    consumer_heartbeat_interval_ms: int = Field(default=3000, description="3 seconds")
    consumer_partition_assignment_strategy: str = Field(default="sticky")
    consumer_isolation_level: str = Field(default="read_committed")

    # Commit settings
    commit_interval_ms: int = Field(default=500)
    commit_batch_size: int = Field(default=250)

    # =========================================================================
    # Transactions (Exactly-Once Semantics)
    # =========================================================================
    enable_transactions: bool = Field(default=True)
    transactional_id_prefix: str = Field(default="wellwon-txn")
    transaction_timeout_ms: int = Field(default=90000, description="90 seconds")

    # =========================================================================
    # Security
    # =========================================================================
    security_protocol: str = Field(default="PLAINTEXT")
    sasl_mechanism: Optional[str] = Field(default=None)
    sasl_username: Optional[str] = Field(default=None)
    sasl_password: Optional[SecretStr] = Field(default=None)
    ssl_ca_location: Optional[str] = Field(default=None)
    ssl_cert_location: Optional[str] = Field(default=None)
    ssl_key_location: Optional[str] = Field(default=None)

    # =========================================================================
    # Circuit Breaker Settings
    # =========================================================================
    circuit_breaker_failure_threshold: int = Field(default=5)
    circuit_breaker_success_threshold: int = Field(default=3)
    circuit_breaker_timeout_seconds: int = Field(default=60)
    circuit_breaker_half_open_calls: int = Field(default=3)

    # =========================================================================
    # Retry Settings
    # =========================================================================
    retry_max_attempts: int = Field(default=3)
    retry_initial_delay_ms: int = Field(default=100)
    retry_max_delay_ms: int = Field(default=2000)
    retry_backoff_factor: float = Field(default=2.0)

    # =========================================================================
    # Consumer Processing
    # =========================================================================
    consumer_poll_timeout_ms: int = Field(default=1000)
    consumer_max_retries: int = Field(default=3)
    consumer_retry_delay_ms: int = Field(default=1000)

    # =========================================================================
    # Dead Letter Queue
    # =========================================================================
    enable_dlq: bool = Field(default=True)
    dlq_max_retries: int = Field(default=3)
    dlq_topic_suffix: str = Field(default=".dlq")

    # =========================================================================
    # Monitoring
    # =========================================================================
    enable_metrics: bool = Field(default=True)
    metrics_publish_interval_seconds: int = Field(default=60)

    # =========================================================================
    # Feature Flags
    # =========================================================================
    enable_distributed_tracing: bool = Field(default=True)
    enable_message_deduplication: bool = Field(default=True)
    enable_schema_validation: bool = Field(default=True)

    # =========================================================================
    # Transport/Outbox Settings
    # =========================================================================
    outbox_enabled: bool = Field(default=True)
    outbox_poll_interval_seconds: int = Field(default=5)
    outbox_batch_size: int = Field(default=100)
    outbox_max_retries: int = Field(default=3)
    outbox_retry_delay_seconds: int = Field(default=60)

    # Serialization
    default_serializer: str = Field(default="json")
    enable_compression: bool = Field(default=True)
    include_metadata_headers: bool = Field(default=True)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def get_consumer_group(self, topic_name: str) -> str:
        """Get consumer group for a topic"""
        topics = get_default_topics()
        if topic_name in topics and topics[topic_name].consumer_group:
            return topics[topic_name].consumer_group
        clean_name = topic_name.replace(".", "-")
        return f"{self.consumer_group_id_prefix}-{clean_name}"

    def get_sasl_password_value(self) -> Optional[str]:
        """Get SASL password as plain string"""
        return self.sasl_password.get_secret_value() if self.sasl_password else None


# =============================================================================
# Default Topics Configuration
# =============================================================================

def get_default_topics() -> Dict[str, TopicConfig]:
    """Get default topic configurations"""
    return {
        # Transport topics
        "transport.user-account-events": TopicConfig(
            name="transport.user-account-events",
            type=TopicType.STREAM,
            partitions=9,
            retention_ms=604800000,
            consumer_group="event-processor-workers"
        ),
        "transport.company-events": TopicConfig(
            name="transport.company-events",
            type=TopicType.STREAM,
            partitions=9,
            retention_ms=604800000,
            consumer_group="event-processor-workers"
        ),
        "transport.chat-events": TopicConfig(
            name="transport.chat-events",
            type=TopicType.STREAM,
            partitions=12,
            retention_ms=604800000,
            consumer_group="event-processor-workers"
        ),

        # System topics
        "system.data-integrity-events": TopicConfig(
            name="system.data-integrity-events",
            type=TopicType.SYSTEM,
            partitions=6,
            retention_ms=604800000,
            consumer_group="data-integrity-workers"
        ),
        "system.data-integrity-metrics": TopicConfig(
            name="system.data-integrity-metrics",
            type=TopicType.SYSTEM,
            partitions=3,
            retention_ms=-1,
            cleanup_policy="compact",
            consumer_group="data-integrity-workers"
        ),
        "system.connection-recovery-metrics": TopicConfig(
            name="system.connection-recovery-metrics",
            type=TopicType.SYSTEM,
            partitions=3,
            retention_ms=604800000,
            consumer_group="connection-recovery-workers"
        ),
        "system.worker-control.data-integrity": TopicConfig(
            name="system.worker-control.data-integrity",
            type=TopicType.SYSTEM,
            partitions=1,
            retention_ms=86400000,
            consumer_group="data-integrity-workers"
        ),
        "system.worker-control.connection-recovery": TopicConfig(
            name="system.worker-control.connection-recovery",
            type=TopicType.SYSTEM,
            partitions=1,
            retention_ms=86400000,
            consumer_group="connection-recovery-workers"
        ),
        "system.worker-heartbeats": TopicConfig(
            name="system.worker-heartbeats",
            type=TopicType.SYSTEM,
            partitions=3,
            retention_ms=3600000,
            consumer_group="health-monitor-workers"
        ),
        "system.projection-rebuild-commands": TopicConfig(
            name="system.projection-rebuild-commands",
            type=TopicType.SYSTEM,
            partitions=3,
            retention_ms=604800000,
            consumer_group="projection-rebuilder-workers"
        ),
        "system.sync-commands": TopicConfig(
            name="system.sync-commands",
            type=TopicType.SYSTEM,
            partitions=3,
            retention_ms=604800000,
            consumer_group="account-sync-workers"
        ),

        # Saga topics
        "saga.events": TopicConfig(
            name="saga.events",
            type=TopicType.SAGA,
            partitions=12,
            retention_ms=2592000000,
            consumer_group="saga-processor-workers"
        ),
        "saga.commands": TopicConfig(
            name="saga.commands",
            type=TopicType.SAGA,
            partitions=6,
            retention_ms=604800000,
            consumer_group="saga-processor-workers"
        ),
        "saga.account-recovery": TopicConfig(
            name="saga.account-recovery",
            type=TopicType.SAGA,
            partitions=6,
            retention_ms=2592000000,
            consumer_group="saga-processor-workers"
        ),

        # Alert topics
        "alerts.data-integrity": TopicConfig(
            name="alerts.data-integrity",
            type=TopicType.ALERTS,
            partitions=3,
            retention_ms=604800000,
            compression_type="lz4",
            consumer_group="notification-workers"
        ),
        "alerts.connection-recovery": TopicConfig(
            name="alerts.connection-recovery",
            type=TopicType.ALERTS,
            partitions=3,
            retention_ms=604800000,
            compression_type="lz4",
            consumer_group="connection-recovery-workers"
        ),
        "alerts.system": TopicConfig(
            name="alerts.system",
            type=TopicType.ALERTS,
            partitions=3,
            retention_ms=604800000,
            compression_type="lz4",
            consumer_group="notification-workers"
        ),

        # CQRS topics
        "cqrs.commands": TopicConfig(
            name="cqrs.commands",
            type=TopicType.CQRS,
            partitions=12,
            retention_ms=604800000,
            consumer_group="saga-processor-workers"
        ),
        "cqrs.queries": TopicConfig(
            name="cqrs.queries",
            type=TopicType.CQRS,
            partitions=9,
            retention_ms=604800000,
            consumer_group="synapse_worker-query-bus"
        ),

        # EventStore topics
        "eventstore.all-events": TopicConfig(
            name="eventstore.all-events",
            type=TopicType.EVENTSTORE,
            partitions=12,
            retention_ms=31536000000,
            compression_type="lz4",
            consumer_group="projection-rebuilder-workers"
        ),

        # DLQ topics
        "system.dlq.events": TopicConfig(
            name="system.dlq.events",
            type=TopicType.SYSTEM,
            partitions=6,
            retention_ms=2592000000,
            max_message_bytes=2097152
        ),
    }


# =============================================================================
# Event Routing Configuration
# =============================================================================

def get_event_routing() -> Dict[str, str]:
    """Get default event routing rules"""
    return {
        # User events
        "UserAccountCreated": "transport.user-account-events",
        "UserAccountDeleted": "transport.user-account-events",
        "UserPasswordChanged": "transport.user-account-events",
        "UserEmailVerified": "transport.user-account-events",
        "UserProfileUpdated": "transport.user-account-events",

        # Company events
        "CompanyCreated": "transport.company-events",
        "CompanyUpdated": "transport.company-events",
        "CompanyArchived": "transport.company-events",
        "CompanyRestored": "transport.company-events",
        "CompanyDeleted": "transport.company-events",
        "UserAddedToCompany": "transport.company-events",
        "UserRemovedFromCompany": "transport.company-events",
        "TelegramSupergroupCreated": "transport.company-events",
        "TelegramSupergroupDeleted": "transport.company-events",
        "CompanyBalanceUpdated": "transport.company-events",

        # Chat events
        "ChatCreated": "transport.chat-events",
        "ChatUpdated": "transport.chat-events",
        "ChatArchived": "transport.chat-events",
        "ChatRestored": "transport.chat-events",
        "ChatHardDeleted": "transport.chat-events",
        "MessageSent": "transport.chat-events",
        "MessageEdited": "transport.chat-events",
        "MessageDeleted": "transport.chat-events",
        "ParticipantAdded": "transport.chat-events",
        "ParticipantRemoved": "transport.chat-events",
        "ParticipantLeft": "transport.chat-events",
        "TelegramChatLinked": "transport.chat-events",
        "TelegramMessageReceived": "transport.chat-events",

        # System events
        "WorkerControlCommand": "system.worker-control.{worker_type}",
        "WorkerHeartbeat": "system.worker-heartbeats",
        "ProjectionRebuildRequested": "system.projection-rebuild-commands",
        "ProjectionRebuildCompleted": "saga.events",
    }


def get_topic_for_event(event_type: str, **kwargs) -> Optional[str]:
    """Get the topic for a specific event type"""
    routing = get_event_routing()
    topic_template = routing.get(event_type)
    if topic_template and "{" in topic_template:
        try:
            return topic_template.format(**kwargs)
        except KeyError:
            return None
    return topic_template


# =============================================================================
# Factory Function
# =============================================================================

@lru_cache(maxsize=1)
def get_eventbus_config() -> EventBusConfig:
    """Get event bus configuration singleton (cached)."""
    return EventBusConfig()


def reset_eventbus_config() -> None:
    """Reset config singleton (for testing)."""
    get_eventbus_config.cache_clear()


# =============================================================================
# Backward Compatibility
# =============================================================================

# Aliases for backward compatibility
def get_event_bus_config() -> EventBusConfig:
    """Alias for get_eventbus_config"""
    return get_eventbus_config()


def get_transport_config() -> EventBusConfig:
    """Alias - transport config is now part of EventBusConfig"""
    return get_eventbus_config()


# Legacy module-level instances
event_bus_config = get_eventbus_config()
transport_config = get_eventbus_config()
