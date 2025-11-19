# app/config/worker_consumer_groups.py
"""
Worker Consumer Groups Configuration

Centralized configuration for all worker types and their Kafka consumer groups.
This integrates with eventbus_transport_config.py and matches redpanda_setup.sh exactly.

UPDATED: v0.8 - Fixed all topic inconsistencies and added validation
"""

import os
import socket
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class WorkerType(Enum):
    """All worker types in the system"""
    # Core workers
    EVENT_PROCESSOR = "event-processor"
    DATA_SYNC = "data-sync"  # NEW: Replaces DATA_INTEGRITY + adds sync functionality

    # Legacy (to be removed)
    DATA_INTEGRITY = "data-integrity"  # DEPRECATED: Use DATA_SYNC
    CONNECTION_RECOVERY = "connection-recovery"  # DEPRECATED: Moving to server-side

    # Additional workers
    SAGA_PROCESSOR = "saga-processor"
    NOTIFICATION = "notification"
    MARKET_DATA = "market-data"
    ACCOUNT_SYNC = "account-sync"
    PROJECTION_REBUILDER = "projection-rebuilder"
    HEALTH_MONITOR = "health-monitor"


@dataclass
class WorkerConsumerConfig:
    """Configuration for a specific worker type's consumer group"""

    # Basic identification
    worker_type: WorkerType
    consumer_group: str
    description: str

    # Topics this worker subscribes to
    topics: List[str]

    # Kafka consumer settings
    max_poll_records: int = 500
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 10000
    max_poll_interval_ms: int = 300000

    # Worker-specific settings
    enabled: bool = True
    instances_min: int = 1
    instances_max: int = 10

    # Processing behavior
    auto_offset_reset: str = "latest"
    enable_auto_commit: bool = True
    auto_commit_interval_ms: int = 5000

    # Error handling
    max_retries: int = 3
    retry_backoff_ms: int = 1000
    dead_letter_topic: Optional[str] = None

    # Performance tuning
    fetch_min_bytes: int = 1
    fetch_max_wait_ms: int = 500
    max_partition_fetch_bytes: int = 1048576  # 1MB

    # Additional metadata
    required_infrastructure: List[str] = field(default_factory=lambda: ["postgres", "redis"])
    supports_commands: bool = False
    supports_queries: bool = False

    def get_consumer_config(self, instance_id: Optional[str] = None) -> Dict[str, Any]:
        """Get complete Kafka consumer configuration"""
        config = {
            'group_id': self.consumer_group,
            'session_timeout_ms': self.session_timeout_ms,
            'heartbeat_interval_ms': self.heartbeat_interval_ms,
            'max_poll_interval_ms': self.max_poll_interval_ms,
            'max_poll_records': self.max_poll_records,
            'enable_auto_commit': self.enable_auto_commit,
            'auto_commit_interval_ms': self.auto_commit_interval_ms,
            'auto_offset_reset': self.auto_offset_reset,
            'fetch_min_bytes': self.fetch_min_bytes,
            'fetch_max_wait_ms': self.fetch_max_wait_ms,
            'max_partition_fetch_bytes': self.max_partition_fetch_bytes,
            # Additional stability settings
            'connections_max_idle_ms': 540000,
            'request_timeout_ms': 40000,
            'retry_backoff_ms': self.retry_backoff_ms,
            'metadata_max_age_ms': 300000,
            # Isolation level for exactly-once semantics
            'isolation_level': 'read_committed',
        }

        # Apply instance-specific client_id if provided
        if instance_id:
            config['client_id'] = self.get_client_id(instance_id)

        return config

    def get_client_id(self, instance_id: Optional[str] = None) -> str:
        """Generate unique client ID for this worker instance"""
        if instance_id:
            return f"{self.worker_type.value}-{instance_id}"
        else:
            hostname = socket.gethostname()
            return f"{self.worker_type.value}-{hostname}-{os.getpid()}-{int(time.time())}"

    def get_dead_letter_topic(self) -> str:
        """Get the dead letter topic for this worker"""
        if self.dead_letter_topic:
            return self.dead_letter_topic
        return f"system.dlq.{self.worker_type.value}"

    def validate_config(self) -> List[str]:
        """Validate the configuration and return any issues"""
        issues = []

        # Basic validation
        if not self.topics:
            issues.append(f"Worker {self.worker_type.value} has no topics configured")

        if self.instances_min > self.instances_max:
            issues.append(f"Worker {self.worker_type.value} has min_instances > max_instances")

        if self.session_timeout_ms < self.heartbeat_interval_ms * 2:
            issues.append(f"Worker {self.worker_type.value} session timeout should be at least 2x heartbeat interval")

        if self.max_poll_interval_ms < self.session_timeout_ms:
            issues.append(f"Worker {self.worker_type.value} max poll interval should be >= session timeout")

        # Topic validation
        for topic in self.topics:
            if not topic or not topic.strip():
                issues.append(f"Worker {self.worker_type.value} has empty topic")
            elif not self._is_valid_topic_name(topic):
                issues.append(f"Worker {self.worker_type.value} has invalid topic name: {topic}")

        return issues

    def _is_valid_topic_name(self, topic: str) -> bool:
        """Check if topic name follows naming conventions"""
        valid_prefixes = [
            "transport.", "system.", "saga.",
            "alerts.", "cqrs.", "eventstore.",
            "monitoring.", "broker.", "auth.",
            "worker."  # NEW: Worker operational topics
            # NOTE: "integrity." removed - replaced by worker.data-sync.*
            # NOTE: "realtime." removed - orphan prefix, never used
        ]
        return any(topic.startswith(prefix) for prefix in valid_prefixes)


class WorkerConsumerGroups:
    """Central registry of all worker consumer groups"""

    # Event Processor - Main event processing worker
    EVENT_PROCESSOR = WorkerConsumerConfig(
        worker_type=WorkerType.EVENT_PROCESSOR,
        consumer_group="event-processor-workers",
        description="Processes all domain events and updates read models",
        topics=[
            "transport.user-account-events",
        ],
        max_poll_records=1000,  # High throughput
        auto_offset_reset="earliest",  # Don't miss events
        instances_min=1,  # Single instance for dev (scale in prod)
        instances_max=20,
        fetch_max_wait_ms=100,  # Low latency
        max_partition_fetch_bytes=5242880,  # 5MB for batch processing
        supports_commands=False,  # REMOVED: Pure event consumer, no commands needed
        supports_queries=False,  # REMOVED: Pure event consumer, no queries needed
    )

    # Data Sync Worker - Synchronizes broker data and monitors integrity (v0.8)
    DATA_SYNC = WorkerConsumerConfig(
        worker_type=WorkerType.DATA_SYNC,
        consumer_group="data-sync-workers",
        description="Synchronizes broker data, monitors integrity, and triggers recovery",
        topics=[
            # Worker operational topics (NEW prefix: worker.*)
            "worker.data-sync.sync-requests",      # Background sync requests (tier 2/3)
            "alerts.data-integrity",                # Integrity issues (keep alerts.*)
        ],
        max_poll_records=1000,  # High throughput (matching EventProcessor)
        max_poll_interval_ms=300000,  # 5 minutes
        instances_min=1,  # Single instance for dev (scale in prod)
        instances_max=20,  # Scale to 20 like EventProcessor
        fetch_max_wait_ms=100,  # Low latency (matching EventProcessor)
        max_partition_fetch_bytes=5242880,  # 5MB for batch processing
        enabled=os.getenv("ENABLE_DATA_SYNC_WORKER", "true").lower() == "true",
        supports_commands=True,
        supports_queries=True,
    )

    # Data Integrity Worker - Monitors data consistency (DEPRECATED - use DATA_SYNC)
    DATA_INTEGRITY = WorkerConsumerConfig(
        worker_type=WorkerType.DATA_INTEGRITY,
        consumer_group="data-integrity-workers",
        description="DEPRECATED: Use DATA_SYNC worker instead",
        topics=[
            # Integrity-specific topics (from redpanda_setup.sh)
            "system.data-integrity-events",
            "system.data-integrity-metrics",
            "alerts.data-integrity",

            # Worker control
            "system.worker-control.data-integrity",
        ],
        max_poll_records=100,  # Moderate, careful processing
        instances_min=1,
        instances_max=5,
        session_timeout_ms=45000,  # Longer timeout for complex checks
        max_poll_interval_ms=600000,  # 10 minutes for long operations
        supports_commands=True,
        supports_queries=True,
    )

    # Connection Recovery Worker - REMOVED (moved to server-side)
    # Server StreamingLifecycleManager handles connection recovery directly
    # DEPRECATED - Commented out for now
    #
    # CONNECTION_RECOVERY = WorkerConsumerConfig(
    #     worker_type=WorkerType.CONNECTION_RECOVERY,
    #     consumer_group="connection-recovery-workers",
    #     description="Manages broker connection recovery and reconnection",
    #     topics=[
    #         # Domain events (separate consumer group from event-processor)
    #         "transport.entity-events",  # React to connection state changes
    #
    #         # Recovery commands and status
    #         # NOTE: system.recovery-commands REMOVED (orphan - CQRS replaced with sagas)
    #         # NOTE: system.recovery-status REMOVED (orphan - CQRS replaced with sagas)
    #
    #         # Saga orchestration
    #         "saga.events",
    #         "saga.account-recovery",
    #
    #         # Alerts
    #         "alerts.connection-recovery",
    #         # NOTE: alerts.recovery REMOVED (orphan - never published to)
    #         "alerts.system",
    #
    #         # NOTE: realtime.broker-health REMOVED (orphan topic, never used)
    #
    #         # Worker control
    #         "system.worker-control.connection-recovery",
    #     ],
    #     max_poll_records=50,  # Low, complex operations
    #     max_poll_interval_ms=900000,  # 15 minutes for very long operations
    #     instances_min=1,
    #     instances_max=3,
    #     enable_auto_commit=False,  # Manual commit after successful recovery
    #     supports_commands=True,
    #     supports_queries=True,
    # )

    # Saga Processor - Handles distributed transactions
    SAGA_PROCESSOR = WorkerConsumerConfig(
        worker_type=WorkerType.SAGA_PROCESSOR,
        consumer_group="saga-processor-workers",
        description="Orchestrates distributed transactions and compensations",
        topics=[
            "saga.events",
            "saga.account-recovery",
            "saga.commands",
            "cqrs.commands",  # For saga commands
        ],
        max_poll_records=100,
        instances_min=1,
        instances_max=5,
        enable_auto_commit=False,  # Manual commit for transactional guarantees
        session_timeout_ms=60000,  # 1 minute for complex sagas
        max_poll_interval_ms=1200000,  # 20 minutes for long-running sagas
        supports_commands=True,
        supports_queries=True,
    )

    # Notification Worker - Sends notifications
    NOTIFICATION = WorkerConsumerConfig(
        worker_type=WorkerType.NOTIFICATION,
        consumer_group="notification-workers",
        description="Sends email, SMS, and push notifications",
        topics=[
            # User events that might trigger notifications
            "transport.user-account-events",

            # Alerts
            "alerts.data-integrity",
            "alerts.system",
        ],
        max_poll_records=500,
        instances_min=1,
        instances_max=10,
        auto_offset_reset="latest",  # Only care about new notifications
    )

    # Market Data Worker - Processes market data (DISABLED - broker functionality removed)
    MARKET_DATA = WorkerConsumerConfig(
        worker_type=WorkerType.MARKET_DATA,
        consumer_group="market-data-workers",
        description="DISABLED: Broker functionality removed",
        topics=[],
        max_poll_records=2000,  # Very high throughput
        session_timeout_ms=10000,  # Lower timeout for fast processing
        heartbeat_interval_ms=3000,
        instances_min=2,
        instances_max=50,
        fetch_max_wait_ms=50,  # Ultra low latency
        max_partition_fetch_bytes=10485760,  # 10MB for bulk data
        enabled=False,  # Disabled - broker functionality removed
    )

    # Account Sync Worker - Syncs account data (DISABLED - broker functionality removed)
    ACCOUNT_SYNC = WorkerConsumerConfig(
        worker_type=WorkerType.ACCOUNT_SYNC,
        consumer_group="account-sync-workers",
        description="DISABLED: Broker functionality removed",
        topics=[
            "system.sync-commands",
        ],
        max_poll_records=100,
        max_poll_interval_ms=1800000,  # 30 minutes for batch syncs
        instances_min=1,
        instances_max=5,
        enabled=False,  # Disabled - broker functionality removed
        supports_commands=True,
        supports_queries=True,
    )

    # Projection Rebuilder - Rebuilds read models
    PROJECTION_REBUILDER = WorkerConsumerConfig(
        worker_type=WorkerType.PROJECTION_REBUILDER,
        consumer_group="projection-rebuilder-workers",
        description="Rebuilds read model projections from events",
        topics=[
            "system.projection-rebuild-commands",
            "eventstore.all-events",  # Special topic for rebuilding
        ],
        max_poll_records=1000,
        auto_offset_reset="earliest",  # Always start from beginning
        instances_min=1,
        instances_max=1,  # Usually single instance to avoid conflicts
        enabled=os.getenv("ENABLE_PROJECTION_REBUILDER", "false").lower() == "true",
        enable_auto_commit=False,  # Manual checkpointing
        max_poll_interval_ms=3600000,  # 1 hour for full rebuilds
    )

    # Health Monitor - Monitors system health
    HEALTH_MONITOR = WorkerConsumerConfig(
        worker_type=WorkerType.HEALTH_MONITOR,
        consumer_group="health-monitor-workers",
        description="Monitors overall system health",
        topics=[
            # NOTE: realtime.broker-health REMOVED (orphan topic, never used)
            "system.worker-heartbeats",
            "alerts.system",
            # NOTE: integrity.* topics removed - replaced by worker.data-sync.*
            # "integrity.monitor_started",
            # "integrity.monitor_stopped",
        ],
        max_poll_records=200,
        instances_min=1,
        instances_max=2,
        auto_offset_reset="latest",  # Only care about current health
        fetch_max_wait_ms=1000,  # Quick response for health checks
    )

    @classmethod
    def get_all_configs(cls) -> Dict[WorkerType, WorkerConsumerConfig]:
        """Get all worker configurations"""
        return {
            WorkerType.EVENT_PROCESSOR: cls.EVENT_PROCESSOR,
            WorkerType.DATA_SYNC: cls.DATA_SYNC,
            WorkerType.DATA_INTEGRITY: cls.DATA_INTEGRITY,
            # WorkerType.CONNECTION_RECOVERY: cls.CONNECTION_RECOVERY,  # DEPRECATED
            WorkerType.SAGA_PROCESSOR: cls.SAGA_PROCESSOR,
            WorkerType.NOTIFICATION: cls.NOTIFICATION,
            WorkerType.MARKET_DATA: cls.MARKET_DATA,
            WorkerType.ACCOUNT_SYNC: cls.ACCOUNT_SYNC,
            WorkerType.PROJECTION_REBUILDER: cls.PROJECTION_REBUILDER,
            WorkerType.HEALTH_MONITOR: cls.HEALTH_MONITOR,
        }

    @classmethod
    def get_config(cls, worker_type: WorkerType) -> Optional[WorkerConsumerConfig]:
        """Get configuration for specific worker type"""
        configs = cls.get_all_configs()
        return configs.get(worker_type)

    @classmethod
    def get_enabled_workers(cls) -> List[WorkerConsumerConfig]:
        """Get all enabled worker configurations"""
        return [
            config for config in cls.get_all_configs().values()
            if config.enabled
        ]

    @classmethod
    def get_all_topics(cls) -> Set[str]:
        """Get all unique topics across all workers"""
        topics = set()
        for config in cls.get_all_configs().values():
            topics.update(config.topics)
        return topics

    @classmethod
    def get_workers_for_topic(cls, topic: str) -> List[WorkerType]:
        """Get all workers that consume a specific topic"""
        workers = []
        for worker_type, config in cls.get_all_configs().items():
            if topic in config.topics:
                workers.append(worker_type)
        return workers

    @classmethod
    def validate_all_configs(cls) -> Dict[WorkerType, List[str]]:
        """Validate all enabled worker configurations"""
        issues = {}
        for worker_type, config in cls.get_all_configs().items():
            # Skip validation for disabled workers
            if not config.enabled:
                continue
            worker_issues = config.validate_config()
            if worker_issues:
                issues[worker_type] = worker_issues
        return issues

    @classmethod
    def validate_topics_exist(cls, existing_topics: Set[str]) -> Dict[str, List[str]]:
        """Validate that all configured topics exist in the cluster"""
        missing_topics = {}

        for worker_type, config in cls.get_all_configs().items():
            if not config.enabled:
                continue

            missing = [topic for topic in config.topics if topic not in existing_topics]
            if missing:
                missing_topics[worker_type.value] = missing

        return missing_topics


# Helper functions for easy access
def get_worker_consumer_config(worker_type: WorkerType) -> Optional[WorkerConsumerConfig]:
    """Get consumer configuration for a worker type"""
    return WorkerConsumerGroups.get_config(worker_type)


def get_worker_topics(worker_type: WorkerType) -> List[str]:
    """Get topics that a worker should subscribe to"""
    config = get_worker_consumer_config(worker_type)
    return config.topics if config else []


def create_redpanda_adapter_for_worker(
        worker_type: WorkerType,
        instance_id: Optional[str] = None,
        event_bus_config: Optional[Any] = None
):
    """
    Create a properly configured RedpandaTransportAdapter for a worker.

    This is the main integration point with RedpandaTransportAdapter.
    """
    from app.infra.event_bus.redpanda_adapter import RedpandaTransportAdapter

    # Get worker config
    worker_config = get_worker_consumer_config(worker_type)
    if not worker_config:
        raise ValueError(f"No configuration found for worker type: {worker_type}")

    if not worker_config.enabled:
        raise ValueError(f"Worker type {worker_type} is not enabled")

    # Get event bus config
    if not event_bus_config:
        from app.config.eventbus_transport_config import event_bus_config as default_config
        event_bus_config = default_config

    # Create consumer config from worker settings
    consumer_config = worker_config.get_consumer_config(instance_id)

    # Remove group_id as it's set per subscription
    consumer_config.pop('group_id', None)

    # Create adapter with worker-specific configuration
    adapter = RedpandaTransportAdapter(
        bootstrap_servers=event_bus_config.kafka.bootstrap_servers,
        client_id=worker_config.get_client_id(instance_id),
        producer_config=None,  # Workers typically don't produce
        consumer_config=consumer_config,
        event_bus_config=event_bus_config,
        worker_type=worker_type
    )

    return adapter


# Environment variable overrides
def apply_env_overrides(config: WorkerConsumerConfig) -> WorkerConsumerConfig:
    """Apply environment variable overrides to worker config"""
    env_prefix = f"WORKER_{config.worker_type.name}_"

    # Override consumer group if specified
    group_override = os.getenv(f"{env_prefix}CONSUMER_GROUP")
    if group_override:
        config.consumer_group = group_override

    # Override enabled state
    enabled_override = os.getenv(f"{env_prefix}ENABLED")
    if enabled_override is not None:
        config.enabled = enabled_override.lower() == "true"

    # Override Kafka settings
    session_timeout = os.getenv(f"{env_prefix}SESSION_TIMEOUT_MS")
    if session_timeout:
        config.session_timeout_ms = int(session_timeout)

    max_poll_records = os.getenv(f"{env_prefix}MAX_POLL_RECORDS")
    if max_poll_records:
        config.max_poll_records = int(max_poll_records)

    max_poll_interval = os.getenv(f"{env_prefix}MAX_POLL_INTERVAL_MS")
    if max_poll_interval:
        config.max_poll_interval_ms = int(max_poll_interval)

    # Override scaling
    min_instances = os.getenv(f"{env_prefix}MIN_INSTANCES")
    if min_instances:
        config.instances_min = int(min_instances)

    max_instances = os.getenv(f"{env_prefix}MAX_INSTANCES")
    if max_instances:
        config.instances_max = int(max_instances)

    # Override retry settings
    max_retries = os.getenv(f"{env_prefix}MAX_RETRIES")
    if max_retries:
        config.max_retries = int(max_retries)

    retry_backoff = os.getenv(f"{env_prefix}RETRY_BACKOFF_MS")
    if retry_backoff:
        config.retry_backoff_ms = int(retry_backoff)

    return config


# Apply environment overrides to all configs at module load time
for worker_type, config in WorkerConsumerGroups.get_all_configs().items():
    apply_env_overrides(config)

# Validate all configurations on module load
validation_issues = WorkerConsumerGroups.validate_all_configs()
if validation_issues:
    logger.warning(f"Worker configuration validation issues found: {validation_issues}")

# Export commonly used functions
__all__ = [
    'WorkerType',
    'WorkerConsumerConfig',
    'WorkerConsumerGroups',
    'get_worker_consumer_config',
    'get_worker_topics',
    'create_redpanda_adapter_for_worker',
    'apply_env_overrides',
]