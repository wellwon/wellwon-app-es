# =============================================================================
# File: app/infra/event_bus/redpanda_adapter.py
# Description: FIXED Redpanda/Kafka transport adapter for EventBus
#              for 
#              UPDATED: Integration with worker_consumer_groups.py
# FIXES:
# - Consumer retry now creates new instance on each attempt (fixes "start() twice" error)
# - Proper session timeout configuration
# - Better error handling and cleanup
# - Integration with centralized worker consumer groups configuration
# =============================================================================

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
import uuid
from typing import Dict, Any, Callable, Awaitable, Optional, AsyncIterator, List, Union
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError
# ADDED: Import partition assignors for optimal rebalancing
from aiokafka.coordinator.assignors.roundrobin import RoundRobinPartitionAssignor
from aiokafka.coordinator.assignors.sticky.sticky_assignor import StickyPartitionAssignor
from aiokafka.coordinator.assignors.range import RangePartitionAssignor
# ADDED: Import exactly-once metrics (2025-11-14)
from app.infra.metrics.exactly_once_metrics import (
    record_transactional_producer_created,
    record_transactional_producer_evicted,
    update_transactional_producer_pool_size
)

# Try to import CooperativeStickyAssignor (available in aiokafka 0.8+)
try:
    from aiokafka.coordinator.assignors.cooperative_sticky import CooperativeStickyAssignor
    COOPERATIVE_STICKY_AVAILABLE = True
except ImportError:
    CooperativeStickyAssignor = None  # type: ignore
    COOPERATIVE_STICKY_AVAILABLE = False

# Import base transport adapter
from app.infra.event_bus.transport_adapter import TransportAdapter, HealthCheck

# Import NEW reliability patterns from /app/infra/reliability/
from app.infra.reliability.circuit_breaker import (
    CircuitBreakerConfig, CircuitState, get_circuit_breaker
)
from app.infra.reliability.retry import retry_async, RetryConfig

# Import configuration
from app.config.eventbus_transport_config import (
    EventBusConfig, TransportConfig
)

# Import Topic Manager for automatic topic creation
from app.infra.event_bus.topic_manager import TopicManager, TopicSpec

# Import worker consumer groups configuration
try:
    from app.infra.worker_core.consumer_groups import (
        WorkerConsumerGroups, WorkerType, WorkerConsumerConfig
    )
    WORKER_GROUPS_AVAILABLE = True
except ImportError:
    WorkerConsumerGroups = None  # type: ignore
    WorkerType = None  # type: ignore
    WorkerConsumerConfig = None  # type: ignore
    WORKER_GROUPS_AVAILABLE = False

log = logging.getLogger("tradecore.redpanda_adapter")


def json_default(obj: Any) -> Any:
    """
    Custom JSON serializer for objects not serializable by default json code.
    Handles UUID, datetime, Decimal, Enum, and other common types.
    """
    if isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, Enum):
        return obj.value
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    else:
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def safe_json_dumps(data: Any) -> str:
    """
    Safely serialize data to JSON, handling common Python types.
    """
    try:
        return json.dumps(data, default=json_default, ensure_ascii=False)
    except Exception as e:
        log.error(f"Failed to serialize data to JSON: {e}. Data type: {type(data)}")
        try:
            return json.dumps(str(data))
        except Exception:
            return '{"error": "Failed to serialize event data"}'


@dataclass
class ConsumerInfo:
    """Information about an active consumer"""
    consumer: AIOKafkaConsumer
    handler: Callable[[Dict[str, Any]], Awaitable[None]]
    task: Optional[asyncio.Task] = None
    created_at: float = 0.0
    messages_processed: int = 0
    last_message_time: float = 0.0
    errors: int = 0
    stop_event: asyncio.Event = None
    consecutive_empty_fetches: int = 0
    last_backoff_seconds: float = 0.0
    worker_type: Optional[WorkerType] = None  # Track which worker type this consumer is for

    def __post_init__(self):
        if self.stop_event is None:
            self.stop_event = asyncio.Event()
        if self.created_at == 0.0:
            self.created_at = time.time()


class TopicType(Enum):
    """Topic type for Redpanda/Kafka durable streams (PUBSUB mode removed Nov 13, 2025)"""
    STREAM = "stream"  # Durable streams with committed offsets


class RedpandaTransportAdapter(TransportAdapter):
    """
    FIXED Redpanda/Kafka transport adapter for EventBus.

    Main fixes:
    - Consumer creation retry now creates new instance each time
    - Proper session timeout handling
    - Better cleanup on errors
    - Integration with worker consumer groups configuration
    """

    def __init__(
            self,
            bootstrap_servers: Optional[str] = None,
            client_id: Optional[str] = None,
            producer_config: Optional[Dict[str, Any]] = None,
            consumer_config: Optional[Dict[str, Any]] = None,
            # New optional parameters for configuration
            event_bus_config: Optional[EventBusConfig] = None,
            transport_config: Optional[TransportConfig] = None,
            worker_type: Optional[WorkerType] = None,  # For worker-specific configuration
    ):
        # Use centralized config if provided, otherwise create from env
        self._event_bus_config = event_bus_config or EventBusConfig.from_env()
        self._transport_config = transport_config or TransportConfig.from_env()
        self._worker_type = worker_type

        # Override with explicit parameters if provided
        self._bootstrap_servers = bootstrap_servers or self._event_bus_config.kafka.bootstrap_servers
        self._client_id = client_id or self._event_bus_config.kafka.client_id
        self._producer: Optional[AIOKafkaProducer] = None
        self._producer_started = False
        self._consumers: Dict[str, ConsumerInfo] = {}
        self._running = True
        self._consumer_tasks: List[asyncio.Task] = []
        self._initialization_lock = asyncio.Lock()

        # NEW: Kafka Transactions support (Exactly-Once Semantics)
        kafka_config = self._event_bus_config.kafka
        self._enable_transactions = kafka_config.enable_transactions
        self._transactional_id_prefix = kafka_config.transactional_id_prefix
        self._transaction_timeout_ms = kafka_config.transaction_timeout_ms
        self._transactional_producers: Dict[str, AIOKafkaProducer] = {}  # transactional_id -> producer

        # ISSUE #2 FIX: Producer pool limit to prevent memory leaks
        self._max_transactional_producers = int(os.getenv("KAFKA_MAX_TRANSACTIONAL_PRODUCERS", "100"))
        self._transactional_producer_usage: Dict[str, int] = {}  # Track usage count for LRU eviction

        # Initialize producer pool metrics
        update_transactional_producer_pool_size(0, self._max_transactional_producers)

        # ADDED: Topic Manager for automatic topic creation
        self._topic_manager: Optional[TopicManager] = None
        self._topics_initialized = False

        # Health monitoring
        self._last_successful_connection = time.time()
        self._connection_errors = 0
        self._messages_sent = 0
        self._messages_received = 0
        self._last_error_time = 0.0

        # NEW: Circuit breakers using new reliability patterns
        # Create circuit breaker configuration
        self._circuit_breaker_config = CircuitBreakerConfig(
            name="redpanda_transport",
            failure_threshold=5,
            success_threshold=3,
            reset_timeout_seconds=30,
            half_open_max_calls=3,
        )

        # Get circuit breaker instance
        self._circuit_breaker = get_circuit_breaker(
            "redpanda_transport",
            config=self._circuit_breaker_config
        )

        # NEW: Retry configuration using new patterns
        self._retry_config = RetryConfig(
            max_attempts=self._event_bus_config.publish_retry_max_attempts,
            initial_delay_ms=self._event_bus_config.publish_retry_initial_delay_ms,
            max_delay_ms=self._event_bus_config.publish_retry_max_delay_ms,
            backoff_factor=self._event_bus_config.publish_retry_backoff_factor,
        )

        # Commit configuration for batching
        self._commit_interval_ms = self._event_bus_config.kafka.commit_interval_ms
        self._commit_batch_size = self._event_bus_config.kafka.commit_batch_size

        # Producer config
        kafka_config = self._event_bus_config.kafka
        self._producer_config = {
            "bootstrap_servers": self._bootstrap_servers,
            "client_id": self._client_id,
            "acks": self._parse_acks(kafka_config.producer_acks),
            "compression_type": kafka_config.producer_compression_type,
            "linger_ms": kafka_config.producer_linger_ms,
            "max_batch_size": kafka_config.producer_batch_size,
            "enable_idempotence": True,
            # NOTE (2025-11-14): max_in_flight_requests_per_connection not exposed in aiokafka 0.12.0
            # aiokafka uses internal defaults compatible with idempotence
            "retry_backoff_ms": kafka_config.producer_retry_backoff_ms,
            "request_timeout_ms": 30000,
            "max_request_size": 1048576,
        }

        # Update producer config if provided
        if producer_config:
            self._producer_config.update(producer_config)

        # CRITICAL FIX (2025-11-14): Validate acks=all when idempotence enabled
        # Kafka requires acks=all for exactly-once semantics with idempotent producers
        acks_value = self._producer_config["acks"]
        if acks_value != -1 and acks_value != "all":
            log.warning(
                f"PRODUCTION WARNING: enable_idempotence=True requires acks='all' (got: {acks_value}). "
                f"Exactly-once delivery may not be guaranteed. See Kafka documentation: "
                f"https://kafka.apache.org/documentation/#producerconfigs_enable.idempotence"
            )

        # ADDED: Get partition assignment strategy
        assignor_strategy = self._get_partition_assignor(
            kafka_config.consumer_partition_assignment_strategy
        )

        # Consumer config template with OPTIMIZED settings
        self._consumer_config_template = {
            'bootstrap_servers': self._bootstrap_servers,
            'client_id': f"{self._client_id}-consumer",

            # Session/heartbeat: Optimized for stability
            'session_timeout_ms': kafka_config.consumer_session_timeout_ms,  # 45s default
            'heartbeat_interval_ms': kafka_config.consumer_heartbeat_interval_ms,  # 3s default

            # Commit/offset: Manual control
            'enable_auto_commit': kafka_config.consumer_enable_auto_commit,
            'auto_offset_reset': kafka_config.consumer_auto_offset_reset,

            # Polling: Optimized for throughput
            'max_poll_records': kafka_config.consumer_max_poll_records,  # 500 default
            'max_poll_interval_ms': 600000,  # 10 minutes (increased from 5 min)

            # Fetch: Optimized for batching
            'fetch_min_bytes': kafka_config.consumer_fetch_min_bytes,  # 10KB default
            'fetch_max_wait_ms': kafka_config.consumer_fetch_max_wait_ms,  # 500ms default

            # Connection management
            'connections_max_idle_ms': 540000,  # 9 minutes
            'request_timeout_ms': 605000,  # Just over 10 minutes

            # ADDED: Partition assignment strategy (StickyPartitionAssignor)
            # Minimizes partition movement during rebalances
            'partition_assignment_strategy': assignor_strategy,

            # NEW: Exactly-Once Semantics - Isolation level
            # read_committed: Only read messages from committed transactions
            # read_uncommitted: Read all messages (at-least-once behavior)
            'isolation_level': kafka_config.consumer_isolation_level,
        }

        # Update consumer config if provided
        if consumer_config:
            self._consumer_config_template.update(consumer_config)

        # Apply worker-specific configuration if available
        if self._worker_type and WORKER_GROUPS_AVAILABLE:
            self._apply_worker_config()

        # Topic prefix for better organization
        self._topic_prefix = os.getenv('KAFKA_TOPIC_PREFIX', '')

        log.info(
            f"RedpandaTransportAdapter initialized with servers={bootstrap_servers}, "
            f"client_id={client_id}, worker_type={worker_type}, "
            f"partition_assignor={kafka_config.consumer_partition_assignment_strategy}, "
            f"using new reliability patterns"
        )

    @staticmethod
    def _get_partition_assignor(strategy: str) -> tuple:
        """
        Convert partition assignment strategy string to assignor class tuple.

        Args:
            strategy: Strategy name ("sticky", "cooperative-sticky", "roundrobin", "range")

        Returns:
            Tuple of assignor classes in preference order

        Benefits of CooperativeStickyAssignor (Kafka 2.4+):
        - Incremental cooperative rebalancing (no stop-the-world)
        - Avoids "assigned to multiple consumers" warnings during rebalance
        - Zero downtime during partition reassignment
        - Better for high-throughput systems

        Fallback to StickyPartitionAssignor if cooperative not available:
        - Minimizes partition movement during rebalancing
        - Reduces stop-the-world effect
        - Faster rebalancing (3-5s vs 30-60s)
        """
        strategy = strategy.lower()

        # Use CooperativeStickyAssignor if available and requested
        if strategy == "sticky" and COOPERATIVE_STICKY_AVAILABLE:
            log.info("Using CooperativeStickyAssignor (incremental cooperative rebalancing)")
            return (CooperativeStickyAssignor,)

        # Fallback to traditional assignors
        assignor_map = {
            "sticky": (StickyPartitionAssignor,),
            "roundrobin": (RoundRobinPartitionAssignor,),
            "range": (RangePartitionAssignor,),
        }

        if strategy not in assignor_map:
            log.warning(
                f"Unknown partition assignment strategy '{strategy}', "
                f"falling back to 'sticky'"
            )
            strategy = "sticky"

        assignor_name = assignor_map[strategy][0].__name__
        log.info(f"Using partition assignment strategy: {strategy} ({assignor_name})")
        return assignor_map[strategy]

    async def initialize_topics(
        self,
        enable_auto_create: bool = True,
        custom_topics: Optional[List[TopicSpec]] = None
    ) -> Dict[str, str]:
        """
        Initialize Topic Manager and create topics if needed.

        This method should be called during application startup to ensure
        all required topics exist with correct configuration.

        Args:
            enable_auto_create: Auto-create topics if they don't exist
            custom_topics: Additional custom topics to create

        Returns:
            Dict with creation results: {topic_name: status}

        Usage:
            adapter = RedpandaAdapter(...)
            results = await adapter.initialize_topics()
            # Results: {"eventstore.user-account-events": "created", ...}
        """
        if self._topics_initialized:
            log.info("Topics already initialized")
            return {}

        try:
            log.info("Initializing Topic Manager...")

            # Create Topic Manager
            self._topic_manager = TopicManager(
                bootstrap_servers=self._bootstrap_servers,
                custom_topics=custom_topics,
                enable_auto_create=enable_auto_create
            )

            # Create topics
            if enable_auto_create:
                log.info("Creating topics...")
                results = await self._topic_manager.ensure_topics_exist()

                created_count = sum(1 for status in results.values() if status == "created")
                existing_count = sum(1 for status in results.values() if status == "exists")
                error_count = sum(1 for status in results.values() if status.startswith("error"))

                log.info(
                    f"Topic initialization complete: "
                    f"{created_count} created, {existing_count} existing, {error_count} errors"
                )

                # Validate retention policies
                log.info("Validating retention policies...")
                validation_results = self._topic_manager.validate_retention_policies()

                invalid_count = sum(
                    1 for result in validation_results.values()
                    if isinstance(result, dict) and not result.get('valid', True)
                )

                if invalid_count > 0:
                    log.warning(
                        f"WARNING: {invalid_count} topics have retention policy mismatches. "
                        f"Run rpk topic alter to fix."
                    )

                self._topics_initialized = True
                return results
            else:
                log.info("Topic auto-creation disabled")
                self._topics_initialized = True
                return {}

        except Exception as e:
            log.error(f"Failed to initialize topics: {e}", exc_info=True)
            raise

    def _apply_worker_config(self) -> None:
        """Apply worker-specific configuration from worker_consumer_groups.py"""
        if not WORKER_GROUPS_AVAILABLE or not self._worker_type:
            return

        worker_config = WorkerConsumerGroups.get_config(self._worker_type)
        if not worker_config:
            return

        # Update consumer template with worker-specific settings
        consumer_config_overrides = worker_config.get_consumer_config()
        self._consumer_config_template.update({
            k: v for k, v in consumer_config_overrides.items()
            if k != 'group_id'  # Don't override group_id in template
        })

        # Update client ID to include worker type
        self._client_id = worker_config.get_client_id()

        log.info(f"Applied worker configuration for {self._worker_type.value}")

    @staticmethod
    def _parse_acks(acks_value: str) -> Union[int, str]:
        """Parse ACKS configuration value to proper type"""
        if acks_value.lower() == 'all':
            return 'all'
        try:
            acks_int = int(acks_value)
            if acks_int in [0, 1, -1]:
                return acks_int
            else:
                log.warning(f"Invalid acks value {acks_int}, defaulting to 1")
                return 1
        except ValueError:
            log.warning(f"Invalid acks value '{acks_value}', defaulting to 1")
            return 1

    async def _ensure_producer(self) -> AIOKafkaProducer:
        """Ensure producer is initialized and started"""
        async with self._initialization_lock:
            if self._producer is None or not self._producer_started:
                if self._producer is None:
                    self._producer = AIOKafkaProducer(**self._producer_config)

                if not self._producer_started:
                    # Start producer with circuit breaker protection
                    async def start_producer():
                        await self._producer.start()
                        self._producer_started = True
                        self._last_successful_connection = time.time()
                        log.info("Kafka producer started successfully")
                        return self._producer

                    try:
                        # Use retry_async from new reliability patterns
                        await retry_async(
                            start_producer,
                            retry_config=self._retry_config,
                            context="Starting Kafka producer"
                        )
                    except Exception:
                        self._connection_errors += 1
                        self._last_error_time = time.time()
                        self._producer_started = False
                        raise

        return self._producer

    async def _create_transactional_producer(self, transactional_id: str) -> AIOKafkaProducer:
        """
        Create and initialize a transactional producer for exactly-once semantics.

        ISSUE #2 FIX: Pool limit enforced - evicts LRU producer when pool full.

        Args:
            transactional_id: Unique transactional ID (must be unique per producer instance)

        Returns:
            Initialized transactional producer

        Note:
            Redpanda/Kafka requires unique transactional_id per producer instance.
            The same transactional_id cannot be used by multiple producers simultaneously.
        """
        # Check if we already have this transactional producer
        if transactional_id in self._transactional_producers:
            # Update usage count for LRU tracking
            self._transactional_producer_usage[transactional_id] = \
                self._transactional_producer_usage.get(transactional_id, 0) + 1
            return self._transactional_producers[transactional_id]

        # ISSUE #2 FIX: Enforce pool limit
        if len(self._transactional_producers) >= self._max_transactional_producers:
            # Evict least recently used producer
            lru_id = min(
                self._transactional_producer_usage.keys(),
                key=lambda k: self._transactional_producer_usage[k]
            )
            log.warning(
                f"Transactional producer pool full ({self._max_transactional_producers}). "
                f"Evicting LRU producer: {lru_id}"
            )

            # Stop and remove LRU producer
            lru_producer = self._transactional_producers.pop(lru_id)
            self._transactional_producer_usage.pop(lru_id)
            try:
                await lru_producer.stop()
            except Exception as e:
                log.error(f"Error stopping evicted producer {lru_id}: {e}")

            # Record eviction metric
            record_transactional_producer_evicted()
            update_transactional_producer_pool_size(
                len(self._transactional_producers),
                self._max_transactional_producers
            )

        # Create transactional producer config
        # NOTE: When transactional_id is set, aiokafka automatically enables:
        # - enable_idempotence=True
        # - acks='all'
        # - max_in_flight_requests=5
        # So we only set transactional_id + transaction_timeout_ms + optional performance tuning
        txn_producer_config = {
            'bootstrap_servers': self._bootstrap_servers,
            'client_id': self._client_id,
            'transactional_id': transactional_id,
            'transaction_timeout_ms': self._transaction_timeout_ms,
            # Optional performance tuning (safe for transactional mode)
            'compression_type': self._producer_config.get('compression_type', 'snappy'),
            'linger_ms': self._producer_config.get('linger_ms', 10),
            'max_batch_size': self._producer_config.get('max_batch_size', 16384),
        }

        # Create producer
        producer = AIOKafkaProducer(**txn_producer_config)

        # Start and initialize transactions
        try:
            await producer.start()
            await producer.begin_transaction()  # Initialize transaction support
            log.info(f"Transactional producer initialized: {transactional_id}")

            # Store producer with initial usage count
            self._transactional_producers[transactional_id] = producer
            self._transactional_producer_usage[transactional_id] = 1

            # Record creation metrics
            record_transactional_producer_created()
            update_transactional_producer_pool_size(
                len(self._transactional_producers),
                self._max_transactional_producers
            )

            return producer

        except Exception as e:
            log.error(f"Failed to initialize transactional producer {transactional_id}: {e}")
            try:
                await producer.stop()
            except:
                pass
            raise

    def _get_topic_name(self, channel: str, _topic_type: TopicType) -> str:
        """
        Convert channel name to Kafka topic name.

        SIMPLIFIED (Nov 12, 2025): All topics now use consistent naming with prefixes.
        - transport.* for domain events (broker-connection-events, order-events, etc.)
        - system.* for system events (dlq.events, worker-heartbeats, etc.)
        - saga.* for saga orchestration
        - alerts.* for alerts
        - cqrs.* for command/query bus
        - eventstore.* for event store

        NOTE: realtime.* prefix REMOVED (Nov 13, 2025) - orphan topics deleted
        WSE uses Redis Pub/Sub (wse:*), not Redpanda realtime.* topics

        No more topic mapping/conversion needed - just validation.
        """

        # Handle already fully qualified topic names (most common case after standardization)
        if channel.startswith(
                ('transport.', 'system.', 'eventstore.', 'saga.',
                 'alerts.', 'integrity.', 'monitoring.', 'broker.', 'worker.',
                 'recovery.', 'cqrs.')):
            # Apply custom prefix if configured (for testing/multi-tenant environments)
            if self._topic_prefix:
                return f"{self._topic_prefix}{channel}"
            return channel

        # If we have transport config, check event routing (for event types)
        if self._transport_config:
            # This might be an event type, check routing
            topic = self._transport_config.get_topic_for_event(channel)
            if topic:
                return topic

        # Fallback: add appropriate prefix based on topic type
        # This handles any legacy topics that don't have prefixes yet
        cleaned = channel.replace(':', '.').replace('_', '-').lower()

        # All topics are STREAM mode (PUBSUB mode removed Nov 13, 2025)
        if not cleaned.startswith(('transport.', 'system.', 'saga.', 'cqrs.', 'eventstore.', 'alerts.')):
            # Default to transport prefix for unprefixed topics
            cleaned = f"transport.{cleaned}"

        # Apply custom prefix if configured
        if self._topic_prefix:
            cleaned = f"{self._topic_prefix}{cleaned}"

        return cleaned

    def _get_consumer_group_for_topic(self, topic: str, provided_group: Optional[str] = None) -> str:
        """
        Get the appropriate consumer group for a topic with validation.

        HIGH FIX #3 (2025-11-14): Validate consumer group names against Kafka limits.
        """
        # If group is explicitly provided, use it
        if provided_group:
            group_id = provided_group
        # Check if we have a worker type and worker groups are available
        elif self._worker_type and WORKER_GROUPS_AVAILABLE:
            worker_config = WorkerConsumerGroups.get_config(self._worker_type)
            if worker_config and topic in worker_config.topics:
                group_id = worker_config.consumer_group
            else:
                # Fallback if worker config doesn't have this topic
                group_id = self._event_bus_config.get_consumer_group(topic) if self._event_bus_config else None
        # Check event bus config for topic-specific consumer group
        elif self._event_bus_config:
            group_id = self._event_bus_config.get_consumer_group(topic)
        else:
            # Default fallback
            group_id = f"{self._event_bus_config.kafka.consumer_group_id_prefix}-{topic.replace('.', '-')}"

        # HIGH FIX #3 (2025-11-14): Validate consumer group name
        # Kafka limits: max 255 characters, only alphanumeric + . - _
        if len(group_id) > 255:
            log.warning(
                f"Consumer group name too long ({len(group_id)} chars): {group_id}. "
                f"Kafka limit is 255 characters. Truncating."
            )
            group_id = group_id[:255]

        # Validate characters (allow alphanumeric, dot, dash, underscore)
        import re
        if not re.match(r'^[a-zA-Z0-9._-]+$', group_id):
            log.warning(
                f"Consumer group name contains invalid characters: {group_id}. "
                f"Allowed: alphanumeric, dot, dash, underscore. Sanitizing."
            )
            # Sanitize by replacing invalid chars with dash
            group_id = re.sub(r'[^a-zA-Z0-9._-]', '-', group_id)

        return group_id

    async def _wrapped_send(self, topic: str, value: bytes, key: Optional[bytes] = None) -> Any:
        """Send message with circuit breaker protection"""
        # Check circuit breaker
        if not self._circuit_breaker.can_execute():
            raise ConnectionError(f"Circuit breaker is open for topic {topic}")

        try:
            producer = await self._ensure_producer()

            # Send with circuit breaker protection
            async def send_message():
                return await producer.send_and_wait(topic, value=value, key=key)

            result = await self._circuit_breaker.execute_async(send_message)

            self._messages_sent += 1
            self._last_successful_connection = time.time()

            return result
        except Exception as e:
            self._connection_errors += 1
            self._last_error_time = time.time()

            # If it's a connection error, mark producer as not started
            if isinstance(e, (KafkaConnectionError, ConnectionError, OSError)):
                self._producer_started = False

            raise

    async def publish(self, channel: str, event: Dict[str, Any]) -> None:
        """Publish to a durable stream"""
        if not self._running:
            raise RuntimeError(f"RedpandaAdapter is closing, cannot publish to {channel}")

        topic = self._get_topic_name(channel, TopicType.STREAM)

        try:
            # Serialize event
            event_bytes = safe_json_dumps(event).encode('utf-8')

            # Use event_id as key for partitioning if available
            key = None
            if event_id := event.get('event_id'):
                key = str(event_id).encode('utf-8')

            # Send with retry using new patterns
            await retry_async(
                self._wrapped_send,
                topic, event_bytes, key,
                retry_config=self._retry_config,
                context=f"Send to stream '{topic}'"
            )

            log.debug(
                f"Published to stream '{topic}': "
                f"{event.get('event_type')}/{event.get('event_id')}"
            )

        except Exception as e:
            log.error(f"Failed to publish to stream '{topic}': {e}", exc_info=True)
            raise

    async def publish_batch(
            self,
            channel: str,
            events: List[Dict[str, Any]],
            partition_key: Optional[str] = None
    ) -> None:
        """Publish batch of events"""
        if not self._running:
            raise RuntimeError(f"RedpandaAdapter is closing, cannot batch publish to {channel}")

        if not events:
            return

        # All topics use STREAM mode (PUBSUB removed Nov 13, 2025)
        topic = self._get_topic_name(channel, TopicType.STREAM)

        producer = await self._ensure_producer()

        try:
            # Batch send with circuit breaker
            async def send_batch():
                send_futures = []
                for event in events:
                    event_bytes = safe_json_dumps(event).encode('utf-8')

                    # Use partition key or event_id for partitioning
                    key = None
                    if partition_key:
                        key = partition_key.encode('utf-8')
                    elif event_id := event.get('event_id'):
                        key = str(event_id).encode('utf-8')

                    # Send without waiting (batch send)
                    future = await producer.send(topic, value=event_bytes, key=key)
                    send_futures.append(future)

                # Wait for all sends to complete
                await asyncio.gather(*[future.get_result() for future in send_futures])

            await self._circuit_breaker.execute_async(send_batch)

            self._messages_sent += len(events)
            log.debug(f"Published batch of {len(events)} events to '{topic}'")

        except Exception as e:
            log.error(f"Failed to publish batch to '{topic}': {e}", exc_info=True)
            raise

    async def stream_consume(
            self,
            channel: str,
            handler: Callable[[Dict[str, Any]], Awaitable[None]],
            group: str,
            consumer: str,
            batch_size: int = 10,
            block_ms: int = 5000
    ) -> None:
        """Consume from durable stream with persistent consumer group."""
        if not self._running:
            log.warning(f"Cannot consume stream '{channel}': adapter is shutting down")
            return

        topic = self._get_topic_name(channel, TopicType.STREAM)

        # Get appropriate consumer group
        group_id = self._get_consumer_group_for_topic(topic, group)

        # Apply worker-specific configuration if available
        max_poll_records = batch_size
        if self._worker_type and WORKER_GROUPS_AVAILABLE:
            worker_config = WorkerConsumerGroups.get_config(self._worker_type)
            if worker_config:
                max_poll_records = worker_config.max_poll_records

        # Create consumer and let it run in background (don't block!)
        consumer_info = await self._create_consumer(
            topic, group_id, handler,
            auto_offset_reset='earliest',  # Start from beginning for streams
            max_poll_records=max_poll_records
        )

        if consumer_info:
            consumer_info.worker_type = self._worker_type

        # FIXED: Don't await the task - it runs indefinitely in background
        # The consumer task will be managed by _active_consumers and cleaned up on shutdown
        if consumer_info and consumer_info.task:
            log.info(f"Stream consumer for '{channel}' started in background (group: {group_id})")

    async def _create_consumer(
            self,
            topic: str,
            group_id: str,
            handler: Callable[[Dict[str, Any]], Awaitable[None]],
            auto_offset_reset: str = 'latest',
            max_poll_records: int = 10
    ) -> Optional[ConsumerInfo]:
        """Create and start a Kafka consumer - FIXED VERSION"""
        consumer_config = {
            **self._consumer_config_template,
            'group_id': group_id,
            'auto_offset_reset': auto_offset_reset,
            'max_poll_records': max_poll_records,
        }

        # Apply worker-specific overrides if available
        if self._worker_type and WORKER_GROUPS_AVAILABLE:
            worker_config = WorkerConsumerGroups.get_config(self._worker_type)
            if worker_config and topic in worker_config.topics:
                worker_consumer_config = worker_config.get_consumer_config()
                consumer_config.update({
                    k: v for k, v in worker_consumer_config.items()
                    if k != 'group_id'  # Don't override the group_id we already set
                })

        # FIX: Create new consumer instance on each retry attempt
        async def create_and_start_consumer():
            # Create NEW consumer for each attempt
            new_consumer = AIOKafkaConsumer(
                topic,
                **consumer_config
            )

            try:
                await new_consumer.start()
                log.info(f"Consumer started for topic '{topic}' with group '{group_id}'")
                return new_consumer
            except Exception as exc:
                # If start fails, stop the consumer to clean up
                try:
                    # Use timeout to prevent hanging on stop() - known aiokafka bug
                    await asyncio.wait_for(new_consumer.stop(), timeout=5.0)
                except asyncio.TimeoutError:
                    log.warning("Consumer stop timed out after 5s during error cleanup")
                except Exception:
                    pass
                raise exc

        # Start consumer with retry using new patterns
        consumer = None
        try:
            consumer = await retry_async(
                create_and_start_consumer,
                retry_config=self._retry_config,
                context=f"Starting consumer for topic '{topic}'"
            )

        except Exception as e:
            log.error(f"Failed to start consumer for '{topic}': {e}", exc_info=True)
            raise

        # Store consumer info
        consumer_info = ConsumerInfo(
            consumer=consumer,
            handler=handler,
            created_at=time.time(),
            worker_type=self._worker_type
        )

        consumer_key = f"{topic}:{group_id}"
        self._consumers[consumer_key] = consumer_info

        # Start consumer loop task - choose transactional or standard based on config
        if self._enable_transactions:
            # Use transactional consumer loop for exactly-once semantics
            from app.infra.event_bus.consumer_transactional import consumer_loop_transactional

            task = asyncio.create_task(
                consumer_loop_transactional(self, consumer_key, consumer_info),
                name=f"consumer-txn-{topic}-{group_id}"
            )
            log.info(f"Started TRANSACTIONAL consumer for {topic} (group={group_id})")
        else:
            # Use standard consumer loop (at-least-once + idempotent handlers)
            # HIGH FIX #4 (2025-11-14): Prominent warning about at-least-once delivery
            log.error(
                f"PRODUCTION WARNING: EXACTLY-ONCE DISABLED for {topic} (group={group_id}). "
                f"Using standard consumer loop with AT-LEAST-ONCE delivery semantics. "
                f"Duplicate processing is POSSIBLE. Handler MUST be idempotent. "
                f"To enable exactly-once: Set REDPANDA_ENABLE_TRANSACTIONS=true "
                f"Current config: enable_transactions={self._enable_transactions}"
            )
            task = asyncio.create_task(
                self._consumer_loop(consumer_key, consumer_info),
                name=f"consumer-{topic}-{group_id}"
            )

        consumer_info.task = task
        self._consumer_tasks.append(task)

        return consumer_info

    async def _consumer_loop(self, consumer_key: str, consumer_info: ConsumerInfo) -> None:
        """Main consumer loop with smart commit strategy"""
        consumer = consumer_info.consumer
        handler = consumer_info.handler

        # Commit tracking
        messages_since_last_commit = 0
        last_commit_time = time.time()
        commit_interval_seconds = self._commit_interval_ms / 1000.0
        has_uncommitted_messages = False

        consecutive_errors = 0
        max_consecutive_errors = 5
        backoff_base = 2

        # Backoff configuration for empty topics
        # PERFORMANCE FIX (Nov 12, 2025): Reduced backoff for SYNC event delivery
        # OLD: 2s initial, 30s max caused 1-7s lag for saga triggers
        # NEW: 50ms initial, 1s max for near-instant event delivery
        empty_poll_initial_backoff = 0.05  # 50ms (was: 2s) - 40x faster
        empty_poll_max_backoff = 1.0  # 1s (was: 30s) - 30x faster
        empty_poll_backoff_multiplier = 1.5
        empty_polls_before_logging = 10

        try:
            while self._running and not consumer_info.stop_event.is_set():
                try:
                    # Fetch messages with timeout
                    timeout_ms = self._event_bus_config.consumer_poll_timeout_ms
                    max_records = self._consumer_config_template.get('max_poll_records', 500)

                    records = await consumer.getmany(
                        timeout_ms=timeout_ms,
                        max_records=max_records
                    )

                    if not records:
                        # Handle empty fetch
                        consumer_info.consecutive_empty_fetches += 1

                        # Calculate backoff time
                        if consumer_info.consecutive_empty_fetches == 1:
                            backoff_seconds = empty_poll_initial_backoff
                        else:
                            backoff_seconds = min(
                                empty_poll_initial_backoff * (empty_poll_backoff_multiplier ** (
                                        consumer_info.consecutive_empty_fetches - 1)),
                                empty_poll_max_backoff
                            )

                        consumer_info.last_backoff_seconds = backoff_seconds

                        # Only log periodically
                        if consumer_info.consecutive_empty_fetches % empty_polls_before_logging == 1:
                            log.debug(
                                f"No messages for {consumer_key}, backing off for {backoff_seconds:.1f}s "
                                f"(consecutive empty: {consumer_info.consecutive_empty_fetches})"
                            )

                        # DON'T COMMIT ON EMPTY FETCHES - Just sleep
                        await asyncio.sleep(backoff_seconds)
                        continue

                    # Reset empty fetch counter when we get messages
                    if consumer_info.consecutive_empty_fetches > 0:
                        log.debug(
                            f"Messages received for {consumer_key} after {consumer_info.consecutive_empty_fetches} empty polls"
                        )
                        consumer_info.consecutive_empty_fetches = 0
                        consumer_info.last_backoff_seconds = 0.0

                    # Reset error counter on successful fetch
                    if consecutive_errors > 0:
                        log.info(f"Kafka consumer recovered after {consecutive_errors} errors")
                        consecutive_errors = 0

                    # Process messages in parallel (per partition) while maintaining partition ordering
                    # This processes different partitions concurrently, but preserves message order within each partition
                    async def process_partition_messages(topic_partition, messages):
                        """Process all messages from a single partition sequentially"""
                        partition_messages_count = 0
                        for msg in messages:
                            if consumer_info.stop_event.is_set():
                                return partition_messages_count

                            try:
                                # Deserialize message
                                event_data = json.loads(msg.value.decode('utf-8'))

                                # Call handler
                                await handler(event_data)

                                # Update metrics (atomic increments)
                                partition_messages_count += 1

                            except json.JSONDecodeError as decode_error:
                                log.error(
                                    f"Failed to decode message from {topic_partition.topic} "
                                    f"partition {topic_partition.partition}: {decode_error}"
                                )
                                consumer_info.errors += 1
                            except Exception as handler_error:
                                log.error(
                                    f"Handler error for message from {topic_partition.topic}: {handler_error}",
                                    exc_info=True
                                )
                                consumer_info.errors += 1

                        return partition_messages_count

                    # Process all partitions in parallel (preserves ordering within partitions)
                    partition_tasks = [
                        process_partition_messages(tp, msgs)
                        for tp, msgs in records.items()
                    ]

                    # Wait for all partitions to complete
                    partition_results = await asyncio.gather(*partition_tasks, return_exceptions=True)

                    # Aggregate results
                    messages_in_batch = sum(r for r in partition_results if isinstance(r, int))

                    # Update global metrics
                    self._messages_received += messages_in_batch
                    consumer_info.messages_processed += messages_in_batch
                    consumer_info.last_message_time = time.time()
                    if messages_in_batch > 0:
                        has_uncommitted_messages = True

                    # Update commit tracking
                    messages_since_last_commit += messages_in_batch

                    # Commit based on batch size OR time interval
                    current_time = time.time()
                    time_since_last_commit = current_time - last_commit_time

                    should_commit_by_size = messages_since_last_commit >= self._commit_batch_size
                    should_commit_by_time = (has_uncommitted_messages and
                                             time_since_last_commit >= commit_interval_seconds)

                    if should_commit_by_size or should_commit_by_time:
                        try:
                            await consumer.commit()

                            if should_commit_by_size:
                                log.debug(
                                    f"Size-based commit: {messages_since_last_commit} messages for {consumer_key}")
                            else:
                                log.debug(
                                    f"Time-based commit: {messages_since_last_commit} messages after {time_since_last_commit:.1f}s for {consumer_key}")

                            messages_since_last_commit = 0
                            has_uncommitted_messages = False
                            last_commit_time = current_time

                        except Exception as e:
                            log.error(f"Failed to commit offsets for {consumer_key}: {e}")

                except asyncio.CancelledError:
                    # Final commit before shutdown
                    if has_uncommitted_messages:
                        try:
                            await consumer.commit()
                            log.info(
                                f"Final commit for {consumer_key} on shutdown ({messages_since_last_commit} messages)")
                        except Exception as e:
                            log.error(f"Failed final commit on cancellation: {e}")
                    log.info(f"Consumer loop cancelled for {consumer_key}")
                    break

                except (KafkaConnectionError, ConnectionError, OSError) as e:
                    consecutive_errors += 1
                    self._connection_errors += 1

                    log.error(
                        f"Kafka connection error in consumer loop for {consumer_key}: {e}. "
                        f"Consecutive errors: {consecutive_errors}/{max_consecutive_errors}"
                    )

                    if consecutive_errors >= max_consecutive_errors:
                        log.warning(
                            f"Too many consecutive errors ({consecutive_errors}) "
                            f"for consumer {consumer_key}. Restarting consumer with extended backoff..."
                        )
                        # Extended backoff before restart (30-60 seconds)
                        restart_backoff = 30 + (random.random() * 30)
                        await asyncio.sleep(restart_backoff)

                        # Reset error counter and continue loop (consumer will be recreated on next iteration)
                        consecutive_errors = 0
                        log.info(f"Restarting consumer {consumer_key} after extended backoff")
                        continue

                    # Exponential backoff with jitter
                    backoff = min(backoff_base ** consecutive_errors, 60)
                    jitter = backoff * 0.1 * (2 * asyncio.get_event_loop().time() % 1 - 1)
                    await asyncio.sleep(backoff + jitter)

                except Exception as e:
                    consecutive_errors += 1
                    log.error(
                        f"Unexpected error in consumer loop for {consumer_key}: {e}",
                        exc_info=True
                    )

                    if consecutive_errors >= max_consecutive_errors:
                        log.error(f"Too many errors, stopping consumer {consumer_key}")
                        break

                    await asyncio.sleep(min(backoff_base ** consecutive_errors, 30))

        finally:
            # Final commit if needed
            if has_uncommitted_messages:
                try:
                    await consumer.commit()
                    log.info(
                        f"Final commit for {consumer_key} in finally block ({messages_since_last_commit} messages)")
                except Exception as e:
                    log.error(f"Failed final commit for {consumer_key}: {e}")

            log.info(f"Consumer loop ended for {consumer_key}")

    async def _cleanup_consumer(self, consumer_key: str) -> None:
        """Clean up a consumer"""
        consumer_info = self._consumers.pop(consumer_key, None)
        if consumer_info:
            try:
                if consumer_info.consumer:
                    # Use timeout to prevent hanging on stop() - known aiokafka bug
                    # This is critical for graceful shutdown during reload/Ctrl-C
                    await asyncio.wait_for(consumer_info.consumer.stop(), timeout=5.0)
                    log.info(f"Stopped consumer for {consumer_key}")
            except asyncio.TimeoutError:
                log.warning(f"Consumer stop timed out after 5s for {consumer_key}, forcing cleanup")
            except Exception as e:
                log.error(f"Error stopping consumer {consumer_key}: {e}")

            # Remove from task list
            if consumer_info.task in self._consumer_tasks:
                self._consumer_tasks.remove(consumer_info.task)

    async def stream(self, channel: str) -> AsyncIterator[Dict[str, Any]]:
        """Raw streaming iterator"""
        # Create a one-off consumer for raw streaming
        topic = self._get_topic_name(channel, TopicType.STREAM)

        consumer_config = {
            **self._consumer_config_template,
            'group_id': f"raw-stream-{uuid.uuid4().hex[:8]}",
            'auto_offset_reset': 'latest',
            'enable_auto_commit': False,
        }

        consumer = AIOKafkaConsumer(topic, **consumer_config)

        try:
            await consumer.start()
            log.info(f"Started raw stream consumer for topic '{topic}'")

            while self._running:
                try:
                    # Use getone() for streaming interface
                    msg = await asyncio.wait_for(
                        consumer.getone(),
                        timeout=self._event_bus_config.consumer_poll_timeout_ms / 1000.0
                    )

                    try:
                        event_data = json.loads(msg.value.decode('utf-8'))
                        yield event_data
                    except json.JSONDecodeError:
                        log.error(f"Failed to decode message from {topic}")

                except asyncio.TimeoutError:
                    # No message within timeout, continue
                    continue
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log.error(f"Error in raw stream for '{channel}': {e}")
                    await asyncio.sleep(1)

        finally:
            try:
                # Use timeout to prevent hanging on stop() - known aiokafka bug
                await asyncio.wait_for(consumer.stop(), timeout=5.0)
                log.info(f"Stopped raw stream consumer for topic '{topic}'")
            except asyncio.TimeoutError:
                log.warning(f"Raw stream consumer stop timed out after 5s for topic '{topic}'")
            except Exception as e:
                log.error(f"Error stopping raw stream consumer: {e}")

    async def close(self) -> None:
        """Gracefully shut down the adapter"""
        log.info("Shutting down RedpandaTransportAdapter...")
        self._running = False

        # Signal all consumers to stop
        for consumer_info in self._consumers.values():
            consumer_info.stop_event.set()

        # Cancel all consumer tasks
        for task in self._consumer_tasks:
            if not task.done():
                task.cancel()

        if self._consumer_tasks:
            results = await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    log.error(f"Consumer task {i} ended with error: {result}")

        # Stop and clean up all consumers
        for consumer_key, consumer_info in list(self._consumers.items()):
            await self._cleanup_consumer(consumer_key)

        # Clear the consumers dictionary
        self._consumers.clear()
        self._consumer_tasks.clear()

        # Stop all transactional producers
        if self._transactional_producers:
            log.info(f"Stopping {len(self._transactional_producers)} transactional producers...")
            for txn_id, txn_producer in list(self._transactional_producers.items()):
                try:
                    await txn_producer.stop()
                    log.info(f"Transactional producer stopped: {txn_id}")
                except Exception as e:
                    log.error(f"Error stopping transactional producer {txn_id}: {e}")

            self._transactional_producers.clear()

        # Stop producer
        if self._producer and self._producer_started:
            try:
                await self._producer.stop()
                log.info("Kafka producer stopped")
            except Exception as e:
                log.error(f"Error stopping producer: {e}")
            finally:
                self._producer_started = False

        self._producer = None

        log.info("RedpandaTransportAdapter shutdown complete")

    async def ping(self) -> bool:
        """Test connectivity to Redpanda/Kafka"""
        try:
            # Try to ensure producer (which will start it if needed)
            producer = await self._ensure_producer()

            # If we got here, producer is started
            # Get client
            client = producer.client

            # Fetch cluster metadata
            await client.force_metadata_update()

            # Check if we have any brokers
            cluster = client.cluster
            brokers = cluster.brokers()

            return len(brokers) > 0
        except Exception as e:
            log.error(f"Kafka ping failed: {e}")
            return False

    async def health_check(self) -> HealthCheck:
        """Check health of Redpanda/Kafka connections"""
        try:
            # Test connectivity
            ping_result = await self.ping()

            # Get circuit breaker status
            circuit_state = self._circuit_breaker.get_state()
            circuit_metrics = self._circuit_breaker.get_metrics()

            # Count active consumers
            active_consumers = sum(
                1 for c in self._consumers.values()
                if c.task and not c.task.done() and not c.stop_event.is_set()
            )

            # Calculate error rate
            total_consumer_messages = sum(c.messages_processed for c in self._consumers.values())
            total_consumer_errors = sum(c.errors for c in self._consumers.values())
            error_rate = (total_consumer_errors / total_consumer_messages * 100) if total_consumer_messages > 0 else 0

            # Overall health
            is_healthy = (
                    ping_result and
                    self._connection_errors < 10 and
                    circuit_state != CircuitState.OPEN and
                    error_rate < 5.0  # Less than 5% error rate
            )

            # Time since last error
            time_since_last_error = None
            if self._last_error_time > 0:
                time_since_last_error = time.time() - self._last_error_time

            details = {
                "ping_successful": ping_result,
                "producer_started": self._producer_started,
                "connection_errors": self._connection_errors,
                "last_successful_connection": self._last_successful_connection,
                "seconds_since_last_success": time.time() - self._last_successful_connection,
                "time_since_last_error": time_since_last_error,
                "messages_sent": self._messages_sent,
                "messages_received": self._messages_received,
                "active_consumers": active_consumers,
                "total_consumers": len(self._consumers),
                "consumer_error_rate": round(error_rate, 2),
                "running": self._running,
                "bootstrap_servers": self._bootstrap_servers,
                "circuit_breaker": circuit_metrics.__dict__ if circuit_metrics else None,
                "worker_type": self._worker_type.value if self._worker_type else None,
            }

            # Add per-consumer health
            if self._consumers:
                consumer_health = {}
                for key, info in self._consumers.items():
                    consumer_health[key] = {
                        "messages_processed": info.messages_processed,
                        "errors": info.errors,
                        "last_message_age": time.time() - info.last_message_time if info.last_message_time > 0 else None,
                        "active": info.task and not info.task.done() and not info.stop_event.is_set(),
                        "consecutive_empty_fetches": info.consecutive_empty_fetches,
                        "current_backoff": info.last_backoff_seconds,
                        "worker_type": info.worker_type.value if info.worker_type else None
                    }
                details["consumers"] = consumer_health

            return HealthCheck(is_healthy=is_healthy, details=details)

        except Exception as e:
            log.error(f"Error during Redpanda health check: {e}", exc_info=True)
            return HealthCheck(
                is_healthy=False,
                details={
                    "error": str(e),
                    "connection_errors": self._connection_errors,
                    "running": self._running,
                    "circuit_breaker": self._circuit_breaker.get_metrics().__dict__ if self._circuit_breaker else None
                }
            )


# Factory function for creating worker-specific adapters
def create_worker_adapter(
        worker_type: WorkerType,
        instance_id: Optional[str] = None,
        event_bus_config: Optional[EventBusConfig] = None,
        _transport_config: Optional[TransportConfig] = None
) -> RedpandaTransportAdapter:
    """
    Create a RedpandaTransportAdapter configured for a specific worker type.

    This integrates with worker_consumer_groups.py for proper configuration.
    """
    if not WORKER_GROUPS_AVAILABLE:
        raise ImportError("worker_consumer_groups module not available")

    from app.infra.worker_core.consumer_groups import create_redpanda_adapter_for_worker

    # Use the centralized factory function
    return create_redpanda_adapter_for_worker(
        worker_type=worker_type,
        instance_id=instance_id,
        event_bus_config=event_bus_config
    )