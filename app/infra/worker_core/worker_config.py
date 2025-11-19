# app/infra/consumers/worker_config.py - UPDATED VERSION
# =============================================================================
# File: app/infra/consumers/worker_config.py
# Description: Worker configuration WITH sync projections support
# =============================================================================

"""
Worker Configuration Module - Updated with Sync Projections

NO Event Store or Projection Rebuilder
Uses CQRS buses for communication
Supports synchronous projections
"""

import os
import socket
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# =============================================================================
# WORKER IDENTITY
# =============================================================================

WORKER_INSTANCE_ID = os.getenv(
    "WORKER_INSTANCE_ID",
    os.getenv("HOSTNAME", f"consumer-worker-{socket.gethostname()}-{os.getpid()}")
)

# =============================================================================
# CORE CONFIGURATION
# =============================================================================

CONSUMER_GROUP_PREFIX = os.getenv("WORKER_GROUP_PREFIX", "synapse_worker")
ENABLE_SAGA_PROCESSING = os.getenv("WORKER_ENABLE_SAGA_PROCESSING", "false").lower() == "true"  # Workers don't process sagas

# Sequence tracking for deduplication
ENABLE_SEQUENCE_TRACKING = os.getenv("WORKER_ENABLE_SEQUENCE_TRACKING", "true").lower() == "true"

# CQRS buses
ENABLE_COMMAND_BUS = os.getenv("WORKER_ENABLE_COMMAND_BUS", "true").lower() == "true"
ENABLE_QUERY_BUS = os.getenv("WORKER_ENABLE_QUERY_BUS", "true").lower() == "true"

# Monitoring and self-healing
ENABLE_GAP_DETECTION = os.getenv("WORKER_ENABLE_GAP_DETECTION", "true").lower() == "true"
ENABLE_SELF_HEALING = os.getenv("WORKER_ENABLE_SELF_HEALING", "true").lower() == "true"

# Administrative capabilities (disabled by default for security)
ENABLE_ADMIN_ENDPOINTS = os.getenv("WORKER_ENABLE_ADMIN_ENDPOINTS", "false").lower() == "true"
ENABLE_OPERATIONAL_TASKS = os.getenv("WORKER_ENABLE_OPERATIONAL_TASKS", "true").lower() == "true"

# Virtual Broker support
ENABLE_VIRTUAL_BROKER = os.getenv("WORKER_ENABLE_VIRTUAL_BROKER", "true").lower() == "true"

# Synchronous projections support
ENABLE_SYNC_PROJECTIONS = os.getenv("WORKER_ENABLE_SYNC_PROJECTIONS", "false").lower() == "true"  # Disabled in workers
SYNC_PROJECTION_TIMEOUT = float(os.getenv("WORKER_SYNC_PROJECTION_TIMEOUT", "2.0"))  # Default 2s timeout
ENABLE_SYNC_PROJECTION_MONITORING = os.getenv("WORKER_ENABLE_SYNC_PROJECTION_MONITORING", "true").lower() == "true"

# =============================================================================
# PROCESSING CONFIGURATION
# =============================================================================

MAX_RETRIES = int(os.getenv("WORKER_MAX_RETRIES", "3"))
RETRY_DELAY_BASE_S = float(os.getenv("WORKER_RETRY_DELAY_S", "1.5"))
BATCH_SIZE = int(os.getenv("WORKER_EVENT_BATCH_SIZE", "100"))
CONSUMER_TIMEOUT_MS = int(os.getenv("WORKER_EVENT_BUS_BLOCK_MS", "5000"))

# Gap detection configuration
GAP_DETECTION_INTERVAL_SECONDS = int(os.getenv("WORKER_GAP_DETECTION_INTERVAL", "300"))  # 5 minutes
GAP_DETECTION_LOOKBACK_HOURS = int(os.getenv("WORKER_GAP_DETECTION_LOOKBACK", "24"))  # 24 hours

# Projection error thresholds
PROJECTION_ERROR_THRESHOLD = int(os.getenv("WORKER_PROJECTION_ERROR_THRESHOLD", "10"))
PROJECTION_ERROR_WINDOW_SECONDS = int(os.getenv("WORKER_PROJECTION_ERROR_WINDOW", "300"))  # 5 minutes

# =============================================================================
# HEALTH & MONITORING
# =============================================================================

HEALTH_CHECK_INTERVAL_SEC = int(os.getenv("WORKER_HEALTH_CHECK_INTERVAL_SEC", "60"))
METRICS_PUBLISH_INTERVAL_SEC = int(os.getenv("WORKER_METRICS_INTERVAL_SEC", "300"))
WORKER_HEARTBEAT_TTL = int(os.getenv("WORKER_HEARTBEAT_TTL", "30"))

# Enhanced monitoring
ENABLE_DETAILED_METRICS = os.getenv("WORKER_ENABLE_DETAILED_METRICS", "true").lower() == "true"
ENABLE_PROJECTION_MONITORING = os.getenv("WORKER_ENABLE_PROJECTION_MONITORING", "true").lower() == "true"
ENABLE_SEQUENCE_MONITORING = os.getenv("WORKER_ENABLE_SEQUENCE_MONITORING", "true").lower() == "true"

# =============================================================================
# FILE PATHS
# =============================================================================

READINESS_FILE_PATH = Path(os.getenv("READINESS_FILE_PATH", "/tmp/evo_worker_v06.ready"))
HEALTH_CHECK_FILE_PATH = Path(os.getenv("HEALTH_CHECK_FILE_PATH", "/tmp/evo_worker_v06.health"))

# =============================================================================
# REDIS KEYS
# =============================================================================

WORKER_REGISTRY_KEY = "wellwon:workers:registry"
WORKER_METRICS_KEY = "wellwon:workers:metrics"
SAGA_REDIS_PREFIX = "wellwon:saga:"

# Enhanced Redis keys
GAP_DETECTION_PREFIX = "wellwon:worker:gaps:"
SEQUENCE_CHECKPOINT_PREFIX = "wellwon:worker:checkpoints:"

# Virtual Broker Redis keys
VIRTUAL_BROKER_PREFIX = "wellwon:virtual_broker:"

# Sync projection Redis keys
SYNC_PROJECTION_METRICS_PREFIX = "wellwon:sync_projections:metrics:"
SYNC_PROJECTION_ERRORS_PREFIX = "wellwon:sync_projections:errors:"

# =============================================================================
# INFRASTRUCTURE ENDPOINTS
# =============================================================================

REDPANDA_BOOTSTRAP_SERVERS = os.getenv("REDPANDA_BOOTSTRAP_SERVERS", "localhost:29092")

# Admin endpoints configuration (if enabled)
ADMIN_ENDPOINT_HOST = os.getenv("WORKER_ADMIN_HOST", "127.0.0.1")  # Localhost only by default
ADMIN_ENDPOINT_PORT = int(os.getenv("WORKER_ADMIN_PORT", "8080"))
ADMIN_API_KEY = os.getenv("WORKER_ADMIN_API_KEY", "")  # Required if admin endpoints enabled

# =============================================================================
# TOPIC CONFIGURATION - DOMAIN EVENTS
# =============================================================================

USER_ACCOUNT_EVENTS_TOPIC = os.getenv("USER_ACCOUNT_EVENTS_TOPIC", "transport.user-account-events")

# =============================================================================
# TOPIC CONFIGURATION - SYSTEM
# =============================================================================

WORKER_EVENTS_TOPIC = os.getenv("WORKER_EVENTS_TOPIC", "system.worker-events")
SAGA_EVENTS_TOPIC = os.getenv("SAGA_EVENTS_TOPIC", "saga.events")
DLQ_TOPIC = os.getenv("WORKER_DLQ_TOPIC", "system.dlq.events")
INTEGRATION_EVENTS_TOPIC = os.getenv("INTEGRATION_EVENTS_TOPIC", "transport.integration-events")

# Operational events
GAP_DETECTION_EVENTS_TOPIC = os.getenv("GAP_DETECTION_EVENTS_TOPIC", "system.gap-detection")

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

PROCESSED_EVENTS_TABLE = "processed_events"
PROJECTION_CHECKPOINTS_TABLE = "projection_checkpoints"
GAP_DETECTION_LOG_TABLE = "gap_detection_log"
SYNC_PROJECTION_METRICS_TABLE = "sync_projection_metrics"


# =============================================================================
# UPDATED WORKER CONFIG DATACLASS
# =============================================================================

@dataclass
class WorkerConfig:
    """
    Worker configuration with CQRS buses and sync projections support.
    NO Event Store or Projection Rebuilder access.
    """
    # Identity
    worker_id: str = field(default_factory=lambda: WORKER_INSTANCE_ID)
    consumer_group_prefix: str = CONSUMER_GROUP_PREFIX

    # Core features
    enable_saga_processing: bool = ENABLE_SAGA_PROCESSING
    enable_sequence_tracking: bool = ENABLE_SEQUENCE_TRACKING
    enable_virtual_broker: bool = ENABLE_VIRTUAL_BROKER

    # CQRS buses
    enable_command_bus: bool = ENABLE_COMMAND_BUS
    enable_query_bus: bool = ENABLE_QUERY_BUS

    # Gap detection and self-healing
    enable_gap_detection: bool = ENABLE_GAP_DETECTION
    enable_self_healing: bool = ENABLE_SELF_HEALING
    gap_detection_interval_seconds: int = GAP_DETECTION_INTERVAL_SECONDS
    gap_detection_lookback_hours: int = GAP_DETECTION_LOOKBACK_HOURS

    # Synchronous projections
    enable_sync_projections: bool = ENABLE_SYNC_PROJECTIONS
    sync_projection_timeout: float = SYNC_PROJECTION_TIMEOUT
    enable_sync_projection_monitoring: bool = ENABLE_SYNC_PROJECTION_MONITORING

    # Projection monitoring
    projection_error_threshold: int = PROJECTION_ERROR_THRESHOLD
    projection_error_window_seconds: int = PROJECTION_ERROR_WINDOW_SECONDS

    # Administrative capabilities
    enable_admin_endpoints: bool = ENABLE_ADMIN_ENDPOINTS
    enable_operational_tasks: bool = ENABLE_OPERATIONAL_TASKS
    admin_endpoint_host: str = ADMIN_ENDPOINT_HOST
    admin_endpoint_port: int = ADMIN_ENDPOINT_PORT
    admin_api_key: str = ADMIN_API_KEY

    # Processing
    max_retries: int = MAX_RETRIES
    retry_delay_base_s: float = RETRY_DELAY_BASE_S
    consumer_batch_size: int = BATCH_SIZE
    consumer_block_ms: int = CONSUMER_TIMEOUT_MS

    # Health & Monitoring
    health_check_interval: int = HEALTH_CHECK_INTERVAL_SEC
    metrics_interval: int = METRICS_PUBLISH_INTERVAL_SEC
    heartbeat_ttl: int = WORKER_HEARTBEAT_TTL
    enable_detailed_metrics: bool = ENABLE_DETAILED_METRICS
    enable_projection_monitoring: bool = ENABLE_PROJECTION_MONITORING
    enable_sequence_monitoring: bool = ENABLE_SEQUENCE_MONITORING

    # Paths
    readiness_file_path: Path = READINESS_FILE_PATH
    health_check_file_path: Path = HEALTH_CHECK_FILE_PATH

    # Infrastructure
    redpanda_servers: str = REDPANDA_BOOTSTRAP_SERVERS

    # Topics to consume
    topics: List[str] = field(default_factory=lambda: [
        USER_ACCOUNT_EVENTS_TOPIC,
    ])

    # System topics
    worker_events_topic: str = WORKER_EVENTS_TOPIC
    saga_events_topic: str = SAGA_EVENTS_TOPIC
    dlq_topic: str = DLQ_TOPIC
    integration_events_topic: str = INTEGRATION_EVENTS_TOPIC
    gap_detection_events_topic: str = GAP_DETECTION_EVENTS_TOPIC

    # Database
    processed_events_table: str = PROCESSED_EVENTS_TABLE
    projection_checkpoints_table: str = PROJECTION_CHECKPOINTS_TABLE
    gap_detection_log_table: str = GAP_DETECTION_LOG_TABLE
    sync_projection_metrics_table: str = SYNC_PROJECTION_METRICS_TABLE

    # Redis keys
    worker_registry_key: str = WORKER_REGISTRY_KEY
    worker_metrics_key: str = WORKER_METRICS_KEY
    saga_redis_prefix: str = SAGA_REDIS_PREFIX
    gap_detection_prefix: str = GAP_DETECTION_PREFIX
    sequence_checkpoint_prefix: str = SEQUENCE_CHECKPOINT_PREFIX
    virtual_broker_prefix: str = VIRTUAL_BROKER_PREFIX
    sync_projection_metrics_prefix: str = SYNC_PROJECTION_METRICS_PREFIX
    sync_projection_errors_prefix: str = SYNC_PROJECTION_ERRORS_PREFIX

    # Additional config
    extra_config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Post-initialization validation and adjustments"""
        # Remove saga topic if saga processing disabled
        if not self.enable_saga_processing and SAGA_EVENTS_TOPIC in self.topics:
            self.topics.remove(SAGA_EVENTS_TOPIC)

        # Validate admin endpoint security
        if self.enable_admin_endpoints and not self.admin_api_key:
            raise ValueError(
                "WORKER_ADMIN_API_KEY must be set when admin endpoints are enabled for security"
            )

    def get_gap_detection_config(self) -> Dict[str, Any]:
        """Get gap detection specific configuration"""
        return {
            "enabled": self.enable_gap_detection,
            "interval_seconds": self.gap_detection_interval_seconds,
            "lookback_hours": self.gap_detection_lookback_hours,
            "redis_prefix": f"{self.gap_detection_prefix}{self.worker_id}:",
            "events_topic": self.gap_detection_events_topic
        }

    def get_admin_config(self) -> Dict[str, Any]:
        """Get admin endpoint configuration"""
        return {
            "enabled": self.enable_admin_endpoints,
            "host": self.admin_endpoint_host,
            "port": self.admin_endpoint_port,
            "api_key": self.admin_api_key,
            "operational_tasks": self.enable_operational_tasks
        }

    def get_virtual_broker_config(self) -> Dict[str, Any]:
        """Get virtual broker specific configuration (DISABLED - broker functionality removed)"""
        return {
            "enabled": False,
            "topic": None,
            "redis_prefix": f"{self.virtual_broker_prefix}{self.worker_id}:"
        }

    def get_sync_projection_config(self) -> Dict[str, Any]:
        """Get sync projection specific configuration"""
        return {
            "enabled": self.enable_sync_projections,
            "timeout": self.sync_projection_timeout,
            "monitoring_enabled": self.enable_sync_projection_monitoring,
            "metrics_prefix": f"{self.sync_projection_metrics_prefix}{self.worker_id}:",
            "errors_prefix": f"{self.sync_projection_errors_prefix}{self.worker_id}:"
        }

    def should_register_projection(self, projection_name: str) -> bool:
        """Check if a projection should be registered based on configuration"""
        # Virtual broker projections
        if projection_name.startswith("virtual_") and not self.enable_virtual_broker:
            return False

        # Saga projections
        if projection_name.startswith("saga_") and not self.enable_saga_processing:
            return False

        return True


def create_worker_config(**overrides) -> WorkerConfig:
    """
    Factory function to create WorkerConfig with optional overrides.
    """
    config = WorkerConfig()

    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            config.extra_config[key] = value

    return config


# Default config instance
DEFAULT_WORKER_CONFIG = create_worker_config()


# =============================================================================
# FEATURE FLAGS
# =============================================================================

class WorkerFeatureFlags:
    """Feature flags for enabling/disabling worker capabilities"""

    # Core features
    CQRS_BUSES_ENABLED = ENABLE_COMMAND_BUS and ENABLE_QUERY_BUS
    SEQUENCE_TRACKING_ENABLED = ENABLE_SEQUENCE_TRACKING
    GAP_DETECTION_ENABLED = ENABLE_GAP_DETECTION
    SELF_HEALING_ENABLED = ENABLE_SELF_HEALING
    SYNC_PROJECTIONS_ENABLED = ENABLE_SYNC_PROJECTIONS

    # Domain features
    VIRTUAL_BROKER_ENABLED = ENABLE_VIRTUAL_BROKER
    SAGA_PROCESSING_ENABLED = ENABLE_SAGA_PROCESSING

    # Admin features
    ADMIN_ENDPOINTS_ENABLED = ENABLE_ADMIN_ENDPOINTS

    @classmethod
    def get_enabled_phases(cls) -> List[str]:
        """Get list of enabled features"""
        features = []
        if cls.CQRS_BUSES_ENABLED:
            features.append("CQRS Buses")
        if cls.SEQUENCE_TRACKING_ENABLED:
            features.append("Sequence Tracking")
        if cls.GAP_DETECTION_ENABLED:
            features.append("Gap Detection")
        if cls.SELF_HEALING_ENABLED:
            features.append("Self Healing")
        if cls.SYNC_PROJECTIONS_ENABLED:
            features.append("Sync Projections")
        return features

    @classmethod
    def get_enabled_domains(cls) -> List[str]:
        """Get list of enabled domain features"""
        domains = []
        if cls.VIRTUAL_BROKER_ENABLED:
            domains.append("Virtual Broker")
        if cls.SAGA_PROCESSING_ENABLED:
            domains.append("Saga Processing")
        return domains

# =============================================================================
# EOF
# =============================================================================