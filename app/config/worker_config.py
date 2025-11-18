# app/config/worker_config.py
"""
Unified Worker Configuration - Advanced Pattern
Pydantic BaseSettings with profiles, worker-type customization, and admin panel support.

Replaces:
- app/infra/worker_core/worker_config.py (old dataclass-based config)
- Parts of app/config/data_integrity_config.py (integrity settings)

Features:
- Pydantic v2 BaseSettings with env var auto-loading
- Profile support (development, production, testing)
- Per-worker-type customization via factory methods
- Database-backed config support (admin panel ready)
- Singleton pattern with get_worker_config() function

Usage:
    # Get config for specific worker type
    config = get_worker_config(WorkerType.EVENT_PROCESSOR, WorkerProfile.PRODUCTION)

    # Or use factory methods
    config = WorkerConfig.event_processor()
    config = WorkerConfig.data_sync()

    # Or get specific profile
    config = WorkerConfig.development()
    config = WorkerConfig.production()
"""

import os
import socket
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Import WorkerType from consumer_groups
from app.infra.worker_core.consumer_groups import WorkerType


# =============================================================================
# ENUMS
# =============================================================================

class WorkerProfile(str, Enum):
    """Configuration profiles for different environments"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


# =============================================================================
# WORKER CONFIG - ADVANCED PATTERN
# =============================================================================

class WorkerConfig(BaseSettings):
    """
    Unified configuration for all worker types.

    This configuration controls:
    - Infrastructure connections (DB, Redis, EventBus)
    - CQRS buses (CommandBus, QueryBus)
    - Processing behavior (batch size, retries, timeouts)
    - Monitoring (health checks, metrics)
    - Features (gap detection, sync projections, integrity checks)
    """

    # Pydantic v2 configuration
    model_config = SettingsConfigDict(
        env_prefix='WORKER_',
        env_file='.env',
        case_sensitive=False,
        extra='ignore'
    )

    # =========================================================================
    # IDENTITY
    # =========================================================================

    worker_id: str = Field(
        default_factory=lambda: os.getenv(
            "WORKER_INSTANCE_ID",
            f"{socket.gethostname()}-{os.getpid()}"
        ),
        description="Unique worker instance identifier"
    )

    worker_type: Optional[str] = Field(
        default=None,
        description="Type of worker (event-processor, data-sync, etc.)"
    )

    instance_id: Optional[str] = Field(
        default=None,
        description="Additional instance identifier"
    )

    profile: WorkerProfile = Field(
        default=WorkerProfile.PRODUCTION,
        description="Configuration profile"
    )

    # =========================================================================
    # INFRASTRUCTURE CONNECTIONS
    # =========================================================================

    # Redpanda/Kafka
    redpanda_servers: str = Field(
        default="localhost:9092",
        description="Redpanda bootstrap servers (use 9092 for Docker, 19092 for native)"
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )

    # PostgreSQL
    postgres_dsn: str = Field(
        default="postgresql://user:pass@localhost/tradecore",
        description="PostgreSQL connection DSN"
    )

    # =========================================================================
    # CONSUMER SETTINGS (Kafka/Redpanda)
    # =========================================================================

    # Consumer group
    consumer_group_prefix: str = Field(
        default="tradecore_worker",
        description="Prefix for consumer group names"
    )

    # Topics
    topics: List[str] = Field(
        default_factory=list,
        description="Topics to consume (set by worker type)"
    )

    # Batch processing
    consumer_batch_size: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Number of events to process per batch"
    )

    max_poll_records: int = Field(
        default=500,
        ge=1,
        le=10000,
        description="Max records to poll from Kafka"
    )

    # Timeouts
    consumer_block_ms: int = Field(
        default=5000,
        ge=1000,
        le=60000,
        description="Consumer poll timeout in milliseconds"
    )

    session_timeout_ms: int = Field(
        default=30000,
        ge=6000,
        le=300000,
        description="Kafka session timeout"
    )

    # =========================================================================
    # PROCESSING BEHAVIOR
    # =========================================================================

    # Retry logic
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed events"
    )

    retry_delay_base_s: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Base delay between retries in seconds"
    )

    retry_exponential_backoff: bool = Field(
        default=True,
        description="Use exponential backoff for retries"
    )

    # Concurrency
    max_concurrent_operations: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum concurrent event processing operations"
    )

    operation_timeout_s: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout for individual operations"
    )

    # =========================================================================
    # FEATURE FLAGS
    # =========================================================================

    # CQRS
    enable_command_bus: bool = Field(
        default=True,
        description="Enable CommandBus for sending commands"
    )

    enable_query_bus: bool = Field(
        default=True,
        description="Enable QueryBus for queries"
    )

    # Saga processing
    enable_saga_processing: bool = Field(
        default=False,
        description="Enable saga processing (typically disabled in workers)"
    )

    # Virtual broker
    enable_virtual_broker: bool = Field(
        default=True,
        description="Enable virtual broker support"
    )

    # Sequence tracking
    enable_sequence_tracking: bool = Field(
        default=True,
        description="Enable event sequence tracking for deduplication"
    )

    # Gap detection and self-healing
    enable_gap_detection: bool = Field(
        default=True,
        description="Enable gap detection in event sequences"
    )

    enable_self_healing: bool = Field(
        default=True,
        description="Enable automatic self-healing for detected gaps"
    )

    gap_detection_interval_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Interval between gap detection checks (5 minutes)"
    )

    gap_detection_lookback_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="How far back to look for gaps (24 hours)"
    )

    # Projection monitoring
    enable_projection_monitoring: bool = Field(
        default=True,
        description="Enable projection health monitoring"
    )

    projection_error_threshold: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Error count threshold before alerting"
    )

    projection_error_window_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Time window for error counting (5 minutes)"
    )

    # Sync projections (for EventProcessor)
    enable_sync_projections: bool = Field(
        default=False,
        description="Enable synchronous projections (server-side only)"
    )

    sync_projection_timeout: float = Field(
        default=2.0,
        ge=0.5,
        le=10.0,
        description="Timeout for sync projections in seconds"
    )

    enable_sync_projection_monitoring: bool = Field(
        default=True,
        description="Monitor sync projection warnings"
    )

    # Data Integrity (for DataSync worker)
    enable_integrity_checks: bool = Field(
        default=False,
        description="Enable data integrity checks (DataSync worker)"
    )

    integrity_check_interval: int = Field(
        default=600,
        ge=60,
        le=3600,
        description="Interval between integrity checks (10 minutes)"
    )

    integrity_check_types: List[str] = Field(
        default_factory=lambda: ["account_existence", "balance_verification", "order_sync"],
        description="Types of integrity checks to perform"
    )

    # Admin capabilities
    enable_admin_endpoints: bool = Field(
        default=False,
        description="Enable admin endpoints (disabled by default for security)"
    )

    enable_operational_tasks: bool = Field(
        default=True,
        description="Enable operational tasks (metrics, health checks)"
    )

    # =========================================================================
    # HEALTH & MONITORING
    # =========================================================================

    health_check_interval: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Seconds between health checks"
    )

    metrics_interval: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Seconds between metrics publishing (5 minutes)"
    )

    heartbeat_ttl: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Worker heartbeat TTL in seconds"
    )

    enable_detailed_metrics: bool = Field(
        default=True,
        description="Enable detailed metrics collection"
    )

    enable_sequence_monitoring: bool = Field(
        default=True,
        description="Monitor event sequence numbers"
    )

    # =========================================================================
    # DEAD LETTER QUEUE
    # =========================================================================

    dlq_enabled: bool = Field(
        default=True,
        description="Enable dead letter queue for failed events"
    )

    dlq_topic: str = Field(
        default="system.dlq",
        description="Dead letter queue topic"
    )

    dlq_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Max retries before sending to DLQ"
    )

    # Note: This field already exists above, keeping for clarity

    # =========================================================================
    # FILE PATHS
    # =========================================================================

    readiness_file_path: Path = Field(
        default=Path("/tmp/tradecore_worker.ready"),
        description="Path to readiness file"
    )

    health_check_file_path: Path = Field(
        default=Path("/tmp/tradecore_worker.health"),
        description="Path to health check file"
    )

    # =========================================================================
    # REDIS KEYS
    # =========================================================================

    worker_registry_key: str = Field(
        default="tradecore:workers:registry",
        description="Redis key for worker registry"
    )

    worker_metrics_key: str = Field(
        default="tradecore:workers:metrics",
        description="Redis key for worker metrics"
    )

    # =========================================================================
    # ADDITIONAL RUNTIME SETTINGS
    # =========================================================================

    # Consumer group (set by worker type)
    consumer_group: Optional[str] = Field(
        default=None,
        description="Kafka consumer group name"
    )

    # System topics (for lifecycle events)
    worker_events_topic: str = Field(
        default="system.worker-events",
        description="Topic for worker lifecycle events"
    )

    saga_events_topic: str = Field(
        default="saga.events",
        description="Topic for saga events"
    )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def get_gap_detection_config(self) -> Dict[str, Any]:
        """Get gap detection configuration"""
        return {
            'enabled': self.enable_gap_detection,
            'interval_seconds': self.gap_detection_interval_seconds,
            'lookback_hours': self.gap_detection_lookback_hours,
        }

    def get_integrity_config(self) -> Dict[str, Any]:
        """Get integrity check configuration"""
        return {
            'enabled': self.enable_integrity_checks,
            'interval': self.integrity_check_interval,
            'check_types': self.integrity_check_types,
        }

    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring configuration"""
        return {
            'health_check_interval': self.health_check_interval,
            'metrics_interval': self.metrics_interval,
            'heartbeat_ttl': self.heartbeat_ttl,
            'enable_detailed_metrics': self.enable_detailed_metrics,
        }

    # =========================================================================
    # PROFILE FACTORY METHODS (without for_ prefix)
    # =========================================================================

    @classmethod
    def development(cls, worker_type: str = None) -> 'WorkerConfig':
        """Development profile - verbose logging, small batches, fast iterations"""
        return cls(
            profile=WorkerProfile.DEVELOPMENT,
            worker_type=worker_type,
            consumer_batch_size=10,
            max_poll_records=50,
            max_retries=1,
            health_check_interval=10,
            metrics_interval=60,
            enable_gap_detection=False,
            enable_self_healing=False,
            enable_detailed_metrics=True,
        )

    @classmethod
    def production(cls, worker_type: str = None) -> 'WorkerConfig':
        """Production profile - optimized for throughput and reliability"""
        return cls(
            profile=WorkerProfile.PRODUCTION,
            worker_type=worker_type,
            consumer_batch_size=500,
            max_poll_records=1000,
            max_retries=3,
            health_check_interval=30,
            metrics_interval=300,
            enable_gap_detection=True,
            enable_self_healing=True,
            enable_detailed_metrics=True,
        )

    @classmethod
    def testing(cls, worker_type: str = None) -> 'WorkerConfig':
        """Testing profile - fast, minimal, deterministic"""
        return cls(
            profile=WorkerProfile.TESTING,
            worker_type=worker_type,
            consumer_batch_size=1,
            max_poll_records=10,
            max_retries=0,
            health_check_interval=5,
            metrics_interval=10,
            enable_gap_detection=False,
            enable_self_healing=False,
            enable_detailed_metrics=False,
        )

    # =========================================================================
    # WORKER TYPE FACTORY METHODS (without for_ prefix)
    # =========================================================================

    @classmethod
    def event_processor(cls, profile: WorkerProfile = WorkerProfile.PRODUCTION) -> 'WorkerConfig':
        """EventProcessor-specific configuration"""
        # Get base config from profile
        if profile == WorkerProfile.DEVELOPMENT:
            config = cls.development(worker_type=WorkerType.EVENT_PROCESSOR.value)
        elif profile == WorkerProfile.TESTING:
            config = cls.testing(worker_type=WorkerType.EVENT_PROCESSOR.value)
        else:
            config = cls.production(worker_type=WorkerType.EVENT_PROCESSOR.value)

        # Apply EventProcessor-specific overrides
        config.consumer_batch_size = 500  # High throughput
        config.max_poll_records = 1000
        config.enable_projection_monitoring = True
        config.enable_sync_projection_monitoring = True
        config.enable_gap_detection = True

        return config

    @classmethod
    def data_sync(cls, profile: WorkerProfile = WorkerProfile.PRODUCTION) -> 'WorkerConfig':
        """DataSync-specific configuration"""
        # Get base config from profile
        if profile == WorkerProfile.DEVELOPMENT:
            config = cls.development(worker_type=WorkerType.DATA_SYNC.value)
        elif profile == WorkerProfile.TESTING:
            config = cls.testing(worker_type=WorkerType.DATA_SYNC.value)
        else:
            config = cls.production(worker_type=WorkerType.DATA_SYNC.value)

        # Apply DataSync-specific overrides
        config.consumer_batch_size = 100  # Moderate throughput
        config.max_poll_records = 100
        config.enable_integrity_checks = True
        config.integrity_check_interval = 600  # 10 minutes
        config.enable_gap_detection = True
        config.enable_sync_projections = False  # DataSync doesn't project

        return config

    @classmethod
    def saga_processor(cls, profile: WorkerProfile = WorkerProfile.PRODUCTION) -> 'WorkerConfig':
        """SagaProcessor-specific configuration"""
        if profile == WorkerProfile.DEVELOPMENT:
            config = cls.development(worker_type=WorkerType.SAGA_PROCESSOR.value)
        elif profile == WorkerProfile.TESTING:
            config = cls.testing(worker_type=WorkerType.SAGA_PROCESSOR.value)
        else:
            config = cls.production(worker_type=WorkerType.SAGA_PROCESSOR.value)

        # Apply SagaProcessor-specific overrides
        config.consumer_batch_size = 50  # Careful processing
        config.max_poll_records = 100
        config.enable_saga_processing = True
        config.max_concurrent_operations = 5  # Sagas are complex

        return config

    # Note: Admin panel config editing will be handled by separate router
    # (app/api/routers/worker_config_router.py - future implementation)


# =============================================================================
# PER-WORKER-TYPE DEFAULTS REGISTRY
# =============================================================================

WORKER_TYPE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    WorkerType.EVENT_PROCESSOR.value: {
        'consumer_batch_size': 500,
        'max_poll_records': 1000,
        'max_concurrent_operations': 20,
        'enable_projection_monitoring': True,
        'enable_sync_projection_monitoring': True,
        'enable_gap_detection': True,
        'enable_integrity_checks': False,
    },
    WorkerType.DATA_SYNC.value: {
        'consumer_batch_size': 100,
        'max_poll_records': 100,
        'max_concurrent_operations': 5,
        'enable_projection_monitoring': False,
        'enable_sync_projection_monitoring': False,
        'enable_gap_detection': True,
        'enable_integrity_checks': True,
        'integrity_check_interval': 600,
    },
    WorkerType.SAGA_PROCESSOR.value: {
        'consumer_batch_size': 50,
        'max_poll_records': 100,
        'max_concurrent_operations': 5,
        'enable_saga_processing': True,
        'enable_projection_monitoring': False,
        'enable_integrity_checks': False,
    },
}


# =============================================================================
# FACTORY FUNCTION (Singleton Pattern)
# =============================================================================

_worker_config_cache: Dict[str, WorkerConfig] = {}


def get_worker_config(
    worker_type: WorkerType,
    profile: WorkerProfile = WorkerProfile.PRODUCTION,
    use_cache: bool = True
) -> WorkerConfig:
    """
    Get worker configuration for specific type and profile.

    Uses singleton pattern with caching for performance.

    Args:
        worker_type: Type of worker
        profile: Configuration profile (dev/prod/test)
        use_cache: Use cached config if available

    Returns:
        WorkerConfig instance customized for worker type
    """
    cache_key = f"{worker_type.value}:{profile.value}"

    # Return cached config if available
    if use_cache and cache_key in _worker_config_cache:
        return _worker_config_cache[cache_key]

    # Create new config based on worker type
    if worker_type == WorkerType.EVENT_PROCESSOR:
        config = WorkerConfig.event_processor(profile)
    elif worker_type == WorkerType.DATA_SYNC:
        config = WorkerConfig.data_sync(profile)
    elif worker_type == WorkerType.SAGA_PROCESSOR:
        config = WorkerConfig.saga_processor(profile)
    else:
        # Default config for other worker types
        if profile == WorkerProfile.DEVELOPMENT:
            config = WorkerConfig.development(worker_type.value)
        elif profile == WorkerProfile.TESTING:
            config = WorkerConfig.testing(worker_type.value)
        else:
            config = WorkerConfig.production(worker_type.value)

    # Cache and return
    if use_cache:
        _worker_config_cache[cache_key] = config

    return config


def create_worker_config(
    worker_id: str = None,
    consumer_group_prefix: str = None,
    topics: List[str] = None,
    **kwargs
) -> WorkerConfig:
    """
    Create worker config with custom overrides.

    Backward compatibility function for existing code.
    """
    config_dict = {}

    if worker_id:
        config_dict['worker_id'] = worker_id
    if consumer_group_prefix:
        config_dict['consumer_group_prefix'] = consumer_group_prefix
    if topics:
        config_dict['topics'] = topics

    # Merge with additional kwargs
    config_dict.update(kwargs)

    return WorkerConfig(**config_dict)


def clear_config_cache():
    """Clear configuration cache (useful for testing)"""
    global _worker_config_cache
    _worker_config_cache.clear()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'WorkerConfig',
    'WorkerProfile',
    'WORKER_TYPE_DEFAULTS',
    'get_worker_config',
    'create_worker_config',
    'clear_config_cache',
]
