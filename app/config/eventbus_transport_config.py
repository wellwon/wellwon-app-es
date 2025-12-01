# app/config/eventbus_transport_config.py
"""
Event Bus and Transport Configuration

Centralized configuration for event bus, transport layer, and messaging infrastructure.
Updated to include all topics from worker_consumer_groups.py
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class TopicType(Enum):
    """Topic type enumeration (all topics use STREAM mode)"""
    STREAM = "stream"  # For event streaming (transport.*)
    SYSTEM = "system"  # For system topics (system.*)
    SAGA = "saga"  # For saga orchestration (saga.*)
    CQRS = "cqrs"  # For command/query bus (cqrs.*)
    EVENTSTORE = "eventstore"  # For event store (eventstore.*)
    ALERTS = "alerts"  # For alerts (alerts.*)


@dataclass
class KafkaConfig:
    """
    Kafka/RedPanda connection configuration

    OPTIMIZED FOR PRODUCTION (2025 Best Practices):
    - LZ4 compression for balance of speed/ratio (40-60% better than snappy)
    - 256KB batches for high throughput (16x increase from default)
    - 10ms linger for optimal batching without excessive latency
    - 64MB buffer for better buffering capacity
    """
    bootstrap_servers: str = "localhost:29092"
    client_id: str = "wellwon-synapse"

    # ========================================================================
    # Producer settings - OPTIMIZED FOR THROUGHPUT
    # ========================================================================
    producer_acks: str = "all"  # all, 1, 0 (all = max durability)

    # Compression: LZ4 for optimal balance (was: snappy)
    # LZ4: 50-60% compression, fast CPU usage
    # Snappy: 30-40% compression, fastest CPU
    # ZSTD: 70-80% compression, high CPU usage
    producer_compression_type: str = "lz4"

    # Batch size: Increased for throughput (was: 16KB)
    # Industry standard: 128-256KB for high-volume systems
    producer_batch_size: int = 262144  # 256KB

    # Linger: Keep at 10ms for balance (good default)
    # 0ms = immediate (low latency), 50-100ms = max throughput
    producer_linger_ms: int = 10

    # Buffer memory: Increased for better buffering (was: 32MB)
    producer_buffer_memory: int = 67108864  # 64MB

    # Max in flight: Keep at 5 (good for throughput + ordering)
    producer_max_in_flight_requests: int = 5

    # Retries: Keep at 3 (reliable delivery)
    producer_retries: int = 3
    producer_retry_backoff_ms: int = 100

    # ========================================================================
    # Consumer settings - OPTIMIZED FOR STABILITY & THROUGHPUT
    # ========================================================================
    consumer_group_id_prefix: str = "synapse_worker"
    consumer_auto_offset_reset: str = "earliest"
    consumer_enable_auto_commit: bool = False

    # Max poll records: Increased for throughput (was: 500)
    # Allows processing more messages per poll cycle
    consumer_max_poll_records: int = 500

    # Fetch settings: PERFORMANCE FIX (Nov 12, 2025) - Optimized for SYNC events
    # OLD: fetch_min_bytes=10KB caused 500ms lag for small events
    # NEW: fetch_min_bytes=1 byte for instant delivery (SYNC events < 1KB)
    consumer_fetch_min_bytes: int = 1  # 1 byte (was: 10KB) - instant delivery for SYNC events
    consumer_fetch_max_wait_ms: int = 50  # 50ms (was: 500ms) - 10x faster polling

    # Session timeout: Increased for stability (was: 10s)
    # Longer timeout reduces false rebalances due to transient GC pauses
    # Industry standard: 45s for production systems
    consumer_session_timeout_ms: int = 45000  # 45 seconds

    # Heartbeat: Keep at 3s (1/15 of session timeout - Kafka recommendation)
    consumer_heartbeat_interval_ms: int = 3000

    # Partition assignment strategy: Use Sticky for minimal partition movement
    # "sticky" = StickyPartitionAssignor (minimizes rebalance disruption)
    # Will be converted to assignor class in RedpandaAdapter
    consumer_partition_assignment_strategy: str = "sticky"  # sticky (best for production - minimizes partition movement), roundrobin, range

    # Commit settings
    commit_interval_ms: int = 500
    commit_batch_size: int = 250

    # ========================================================================
    # Kafka Transactions (Exactly-Once Semantics) - NEW
    # ========================================================================
    enable_transactions: bool = True  # Enable Kafka transactions for exactly-once
    transactional_id_prefix: str = "wellwon-txn"  # Prefix for transactional IDs
    # ISSUE #1 FIX: Increased from 60s to 90s for production reliability
    # Handles large batches + external API calls (broker adapters, database ops)
    # NOTE: Industry standard is 900s (15min), but our fast processing (<30s typical)
    # + 500ms commit interval means 90s provides 3x safety margin with faster failure detection
    transaction_timeout_ms: int = 90000  # 90 seconds (optimized for fast event processing)
    consumer_isolation_level: str = "read_committed"  # Only read committed messages

    # Security
    security_protocol: str = "PLAINTEXT"  # PLAINTEXT, SSL, SASL_PLAINTEXT, SASL_SSL
    sasl_mechanism: Optional[str] = None
    sasl_username: Optional[str] = None
    sasl_password: Optional[str] = None
    ssl_ca_location: Optional[str] = None
    ssl_cert_location: Optional[str] = None
    ssl_key_location: Optional[str] = None

    @classmethod
    def from_env(cls) -> 'KafkaConfig':
        """Create config from environment variables"""
        return cls(
            bootstrap_servers=os.getenv("REDPANDA_BOOTSTRAP_SERVERS", "localhost:29092"),
            client_id=os.getenv("REDPANDA_CLIENT_ID", "wellwon"),

            # Producer settings - OPTIMIZED DEFAULTS (can be overridden via env)
            producer_acks=os.getenv("REDPANDA_ACKS", "all"),
            producer_compression_type=os.getenv("REDPANDA_COMPRESSION_TYPE", "lz4"),  # Changed from snappy
            producer_batch_size=int(os.getenv("REDPANDA_BATCH_SIZE", "256")) * 1024,  # Changed from 25KB to 256KB
            producer_linger_ms=int(os.getenv("REDPANDA_LINGER_MS", "10")),  # Changed from 1ms to 10ms
            producer_buffer_memory=int(os.getenv("REDPANDA_BUFFER_MEMORY", "67108864")),  # Changed from 32MB to 64MB
            producer_max_in_flight_requests=int(os.getenv("REDPANDA_MAX_IN_FLIGHT_REQUESTS", "5")),
            producer_retries=int(os.getenv("REDPANDA_RETRIES", "3")),
            producer_retry_backoff_ms=int(os.getenv("REDPANDA_RETRY_BACKOFF_MS", "100")),

            # Consumer settings - OPTIMIZED DEFAULTS (can be overridden via env)
            consumer_group_id_prefix=os.getenv("WORKER_GROUP_PREFIX", "synapse_worker"),
            consumer_auto_offset_reset=os.getenv("REDPANDA_AUTO_OFFSET_RESET", "earliest"),
            consumer_enable_auto_commit=os.getenv("REDPANDA_ENABLE_AUTO_COMMIT", "false").lower() == "true",
            consumer_max_poll_records=int(os.getenv("REDPANDA_MAX_POLL_RECORDS", "500")),  # Increased from 50
            consumer_fetch_min_bytes=int(os.getenv("REDPANDA_FETCH_MIN_BYTES", "1")),  # PERF FIX: 1 byte (was 10KB) for instant SYNC events
            consumer_fetch_max_wait_ms=int(os.getenv("REDPANDA_FETCH_MAX_WAIT_MS", "50")),  # PERF FIX: 50ms (was 500ms) for 10x faster polling
            consumer_session_timeout_ms=int(os.getenv("REDPANDA_SESSION_TIMEOUT_MS", "45000")),  # Increased from 3s to 45s
            consumer_heartbeat_interval_ms=int(os.getenv("REDPANDA_HEARTBEAT_INTERVAL_MS", "3000")),  # Increased from 1s to 3s
            consumer_partition_assignment_strategy=os.getenv("REDPANDA_PARTITION_ASSIGNMENT_STRATEGY", "sticky"),  # NEW

            # Commit settings
            commit_interval_ms=int(os.getenv("REDPANDA_COMMIT_INTERVAL_MS", "500")),
            commit_batch_size=int(os.getenv("REDPANDA_COMMIT_BATCH_SIZE", "250")),

            # Kafka Transactions (NEW - Exactly-Once Semantics)
            enable_transactions=os.getenv("REDPANDA_ENABLE_TRANSACTIONS", "true").lower() == "true",
            transactional_id_prefix=os.getenv("REDPANDA_TRANSACTIONAL_ID_PREFIX", "wellwon-txn"),
            transaction_timeout_ms=int(os.getenv("REDPANDA_TRANSACTION_TIMEOUT_MS", "90000")),  # FIX: 60s→90s
            consumer_isolation_level=os.getenv("REDPANDA_CONSUMER_ISOLATION_LEVEL", "read_committed"),

            # Security
            security_protocol=os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
            sasl_mechanism=os.getenv("KAFKA_SASL_MECHANISM", None),
            sasl_username=os.getenv("KAFKA_SASL_USERNAME", None),
            sasl_password=os.getenv("KAFKA_SASL_PASSWORD", None),
        )


@dataclass
class TopicConfig:
    """Configuration for a specific topic"""
    name: str
    type: TopicType
    partitions: int = 1
    replication_factor: int = 1
    retention_ms: int = 604800000  # 7 days default
    cleanup_policy: str = "delete"
    compression_type: str = "snappy"
    max_message_bytes: int = 1048576  # 1MB

    # Consumer group configuration
    consumer_group: Optional[str] = None

    # Reliability settings
    min_insync_replicas: int = 1
    unclean_leader_election_enable: bool = False

    # Performance settings
    segment_ms: int = 3600000  # 1 hour
    flush_messages: int = 10000
    flush_ms: int = 1000


@dataclass
class EventBusConfig:
    """Event Bus configuration"""
    # Kafka configuration
    kafka: KafkaConfig = field(default_factory=KafkaConfig)

    # Topic configurations
    topics: Dict[str, TopicConfig] = field(default_factory=dict)

    # Circuit breaker settings for publishing
    publish_circuit_breaker_failure_threshold: int = 5
    publish_circuit_breaker_success_threshold: int = 3
    publish_circuit_breaker_timeout_seconds: int = 60
    publish_circuit_breaker_half_open_calls: int = 3

    # Retry settings for publishing
    publish_retry_max_attempts: int = 3
    publish_retry_initial_delay_ms: int = 100
    publish_retry_max_delay_ms: int = 2000
    publish_retry_backoff_factor: float = 2.0

    # Consumer settings
    consumer_poll_timeout_ms: int = 1000
    consumer_max_retries: int = 3
    consumer_retry_delay_ms: int = 1000

    # Dead letter queue settings
    enable_dlq: bool = True
    dlq_max_retries: int = 3
    dlq_topic_suffix: str = ".dlq"

    # Monitoring
    enable_metrics: bool = True
    metrics_publish_interval_seconds: int = 60

    # Feature flags
    enable_distributed_tracing: bool = True
    enable_message_deduplication: bool = True
    enable_schema_validation: bool = True

    def __post_init__(self):
        """Initialize default topic configurations"""
        if not self.topics:
            self._init_default_topics()

    def _init_default_topics(self):
        """Initialize default topic configurations with worker consumer groups integration"""
        # Import here to avoid circular dependency
        try:
            from app.infra.worker_core.consumer_groups import WorkerConsumerGroups

            # Get all worker configurations
            all_worker_configs = WorkerConsumerGroups.get_all_configs()

            # Create a mapping of topics to their consumer groups
            topic_to_consumer_group = {}
            for worker_config in all_worker_configs.values():
                topic_to_consumer_group[worker_config.consumer_group] = worker_config.consumer_group
        except ImportError:
            # Fallback if worker_consumer_groups is not available
            topic_to_consumer_group = {}

        # Transport topics
        self.topics.update({
            "transport.user-account-events": TopicConfig(
                name="transport.user-account-events",
                type=TopicType.STREAM,
                partitions=9,
                retention_ms=604800000,  # 7 days
                consumer_group="event-processor-workers"  # From WorkerConsumerGroups
            ),
            "transport.company-events": TopicConfig(
                name="transport.company-events",
                type=TopicType.STREAM,
                partitions=9,
                retention_ms=604800000,  # 7 days
                consumer_group="event-processor-workers"  # Worker processes company ASYNC projections
            ),
            "transport.chat-events": TopicConfig(
                name="transport.chat-events",
                type=TopicType.STREAM,
                partitions=12,  # More partitions for higher message volume
                retention_ms=604800000,  # 7 days
                consumer_group="event-processor-workers"  # Worker processes chat ASYNC projections
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
                retention_ms=-1,  # Infinite (compacted)
                cleanup_policy="compact",
                consumer_group="data-integrity-workers"
            ),
            "system.connection-recovery-metrics": TopicConfig(
                name="system.connection-recovery-metrics",
                type=TopicType.SYSTEM,
                partitions=3,
                retention_ms=604800000,  # 7 days
                cleanup_policy="delete",
                consumer_group="connection-recovery-workers"
            ),
            # NOTE: system.recovery-commands REMOVED (orphan - CQRS replaced with saga.account-recovery)
            # NOTE: system.recovery-status REMOVED (orphan - CQRS replaced with saga.account-recovery)
            "system.worker-control.data-integrity": TopicConfig(
                name="system.worker-control.data-integrity",
                type=TopicType.SYSTEM,
                partitions=1,
                retention_ms=86400000,  # 1 day
                consumer_group="data-integrity-workers"
            ),
            "system.worker-control.connection-recovery": TopicConfig(
                name="system.worker-control.connection-recovery",
                type=TopicType.SYSTEM,
                partitions=1,
                retention_ms=86400000,  # 1 day
                consumer_group="connection-recovery-workers"
            ),
            "system.worker-heartbeats": TopicConfig(
                name="system.worker-heartbeats",
                type=TopicType.SYSTEM,
                partitions=3,
                retention_ms=3600000,  # 1 hour
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
                retention_ms=2592000000,  # 30 days
                consumer_group="saga-processor-workers"
            ),
            "saga.commands": TopicConfig(
                name="saga.commands",
                type=TopicType.SAGA,
                partitions=6,
                retention_ms=604800000,  # 7 days
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
            # NOTE: alerts.recovery REMOVED (orphan - nobody publishes to it)
            "alerts.connection-recovery": TopicConfig(
                name="alerts.connection-recovery",
                type=TopicType.ALERTS,
                partitions=3,
                retention_ms=604800000,  # 7 days
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

            # NOTE: realtime.* topics REMOVED (Nov 13, 2025)
            # These Redpanda topics were NEVER used by WSE
            # WSE uses Redis Pub/Sub (wse:* channels) for WebSocket coordination
            # Redpanda is ONLY for domain events (transport.*) and system events (system.*, saga.*, etc.)

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
                retention_ms=31536000000,  # 365 days (1 year)
                compression_type="lz4",
                consumer_group="projection-rebuilder-workers"
            ),

            # Event Store topics
            # NOTE: Removed eventstore.* topics - KurrentDB now handles event storage
            # Redpanda is used ONLY for transport layer (transport.* topics)

            # DLQ topics
            "system.dlq.events": TopicConfig(
                name="system.dlq.events",
                type=TopicType.SYSTEM,
                partitions=6,
                retention_ms=2592000000,  # 30 days
                max_message_bytes=2097152  # 2MB for errors
            ),
        })

    def get_topic_config(self, topic_name: str) -> Optional[TopicConfig]:
        """Get configuration for a specific topic"""
        return self.topics.get(topic_name)

    def get_consumer_group(self, topic_name: str) -> str:
        """Get consumer group for a topic, preferring worker consumer groups config"""
        topic_config = self.get_topic_config(topic_name)
        if topic_config and topic_config.consumer_group:
            return topic_config.consumer_group

        # Fallback to pattern-based consumer group
        clean_name = topic_name.replace(".", "-")
        return f"{self.kafka.consumer_group_id_prefix}-{clean_name}"

    def get_consumer_group_for_worker(self, worker_type: str) -> Optional[str]:
        """Get consumer group name for a specific worker type"""
        try:
            from app.infra.worker_core.consumer_groups import WorkerConsumerGroups, WorkerType
            worker_config = WorkerConsumerGroups.get_config(WorkerType(worker_type))
            return worker_config.consumer_group if worker_config else None
        except (ImportError, ValueError):
            return None

    @classmethod
    def from_env(cls) -> 'EventBusConfig':
        """Create config from environment variables with defaults"""
        config = cls(
            kafka=KafkaConfig.from_env(),

            # Circuit breaker settings
            publish_circuit_breaker_failure_threshold=int(os.getenv("REDPANDA_CIRCUIT_FAILURE_THRESHOLD", "5")),
            publish_circuit_breaker_success_threshold=int(os.getenv("REDPANDA_CIRCUIT_SUCCESS_THRESHOLD", "3")),
            publish_circuit_breaker_timeout_seconds=int(os.getenv("REDPANDA_CIRCUIT_RESET_TIMEOUT", "10")),
            publish_circuit_breaker_half_open_calls=int(os.getenv("REDPANDA_CIRCUIT_HALF_OPEN_MAX", "3")),

            # Retry settings
            publish_retry_max_attempts=int(os.getenv("REDPANDA_RETRY_MAX_ATTEMPTS", "3")),
            publish_retry_initial_delay_ms=int(os.getenv("REDPANDA_RETRY_INITIAL_DELAY_MS", "50")),
            publish_retry_max_delay_ms=int(os.getenv("REDPANDA_RETRY_MAX_DELAY_MS", "500")),
            publish_retry_backoff_factor=float(os.getenv("REDPANDA_RETRY_BACKOFF_FACTOR", "2.0")),

            # Consumer settings
            consumer_poll_timeout_ms=int(os.getenv("REDPANDA_CONSUMER_TIMEOUT_MS", "250")),
            consumer_max_retries=int(os.getenv("WORKER_MAX_RETRIES", "3")),
            consumer_retry_delay_ms=int(float(os.getenv("WORKER_RETRY_DELAY_S", "0.5")) * 1000),

            # DLQ settings
            enable_dlq=os.getenv("ENABLE_DLQ", "true").lower() == "true",
            dlq_max_retries=int(os.getenv("DLQ_MAX_RETRIES", "3")),

            # Monitoring
            enable_metrics=os.getenv("ENABLE_METRICS", "true").lower() == "true",
            metrics_publish_interval_seconds=int(os.getenv("METRICS_COLLECTION_INTERVAL_SEC", "30")),
        )
        config._init_default_topics()
        return config

    @classmethod
    def for_testing(cls) -> 'EventBusConfig':
        """Configuration optimized for testing"""
        config = cls(
            kafka=KafkaConfig(
                bootstrap_servers="localhost:29092",
                producer_retries=1,
                consumer_session_timeout_ms=6000,
            ),
            publish_retry_max_attempts=1,
            publish_circuit_breaker_failure_threshold=10,
            enable_metrics=False,
            enable_dlq=False,
        )
        # Reduce partitions for testing
        for topic in config.topics.values():
            topic.partitions = 1
        return config

    @classmethod
    def for_production(cls) -> 'EventBusConfig':
        """Configuration optimized for production"""
        return cls(
            kafka=KafkaConfig(
                producer_acks="all",
                producer_compression_type="snappy",
                producer_max_in_flight_requests=5,
                min_insync_replicas=2,
            ),
            publish_circuit_breaker_failure_threshold=5,
            publish_retry_max_attempts=3,
            enable_dlq=True,
            enable_metrics=True,
            enable_distributed_tracing=True,
            enable_message_deduplication=True,
            enable_schema_validation=True,
        )


@dataclass
class TransportConfig:
    """Transport layer configuration"""
    # Default transport topics (for outbox pattern)
    default_transport_topics: List[str] = field(default_factory=lambda: [
        "transport.user-account-events",
        "transport.company-events",
        "transport.chat-events",
    ])

    # Outbox settings
    outbox_enabled: bool = True
    outbox_poll_interval_seconds: int = 5
    outbox_batch_size: int = 100
    outbox_max_retries: int = 3
    outbox_retry_delay_seconds: int = 60

    # Event routing rules
    event_routing: Dict[str, str] = field(default_factory=dict)

    # Serialization
    default_serializer: str = "json"  # json, avro, protobuf
    enable_compression: bool = True

    # Headers
    include_metadata_headers: bool = True
    custom_headers: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize event routing rules"""
        if not self.event_routing:
            self._init_default_routing()

    def _init_default_routing(self):
        """Initialize default event routing rules"""
        self.event_routing = {
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

            # Worker control events
            "WorkerControlCommand": "system.worker-control.{worker_type}",
            "WorkerHeartbeat": "system.worker-heartbeats",

            # Projection rebuild events
            "ProjectionRebuildRequested": "system.projection-rebuild-commands",
            "ProjectionRebuildCompleted": "saga.events",
        }

    def get_topic_for_event(self, event_type: str, **kwargs) -> Optional[str]:
        """Get the topic for a specific event type with optional formatting"""
        topic_template = self.event_routing.get(event_type)
        if topic_template and "{" in topic_template:
            # Format template with provided kwargs
            try:
                return topic_template.format(**kwargs)
            except KeyError:
                return None
        return topic_template

    @classmethod
    def from_env(cls) -> 'TransportConfig':
        """Create config from environment variables"""
        # Handle float values for poll interval
        poll_interval_str = os.getenv("OUTBOX_POLL_INTERVAL", "5")
        try:
            # First try to parse as float, then convert to int (ceiling)
            poll_interval_float = float(poll_interval_str)
            poll_interval_seconds = max(1, int(poll_interval_float))  # Minimum 1 second
        except ValueError:
            poll_interval_seconds = 5  # Default fallback

        return cls(
            outbox_enabled=os.getenv("OUTBOX_ENABLED", "true").lower() == "true",
            outbox_poll_interval_seconds=poll_interval_seconds,
            outbox_batch_size=int(os.getenv("OUTBOX_BATCH_SIZE", "100")),
        )


# Default configurations
default_event_bus_config = EventBusConfig()
default_transport_config = TransportConfig()

# Environment-based configurations
event_bus_config = EventBusConfig.from_env()
transport_config = TransportConfig.from_env()