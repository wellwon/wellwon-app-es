# app/config/dlq_config.py
"""
Configuration for DLQ Service that matches existing database schema
UPDATED: DLQ now enabled by default with full functionality
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class DLQStorageMode(Enum):
    """DLQ storage strategies"""
    DATABASE_ONLY = "database"  # Direct to DB
    KAFKA_ONLY = "kafka"  # Only Kafka topic
    HYBRID = "hybrid"  # Both Kafka and DB


@dataclass
class DLQConfig:
    """
    DLQ Service configuration matching existing dlq_events table
    """
    # Basic settings - ENABLED BY DEFAULT
    enabled: bool = True  # DLQ is active by default
    storage_mode: DLQStorageMode = DLQStorageMode.HYBRID

    # Queue settings - optimal for production
    queue_size: int = 50000
    batch_size: int = 200
    flush_interval_seconds: float = 2.0

    # Kafka settings
    kafka_topic: str = "system.dlq.events"
    enable_kafka_forward: bool = True

    # Database settings
    table_name: str = "dlq_events"

    # Retry settings
    max_retry_count: int = 3
    retry_delay_seconds: int = 60

    # Recovery settings
    enable_auto_recovery: bool = True
    recovery_check_interval: int = 300  # 5 minutes

    # Monitoring
    enable_metrics: bool = True
    log_dropped_events: bool = False  # Don't spam logs in production
    dropped_events_threshold: int = 1000

    # Performance tuning
    emergency_persist_threshold: int = 45000  # When queue is 90% full
    max_batch_wait_seconds: float = 5.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            "enabled": self.enabled,
            "storage_mode": self.storage_mode.value,
            "queue_size": self.queue_size,
            "batch_size": self.batch_size,
            "flush_interval_seconds": self.flush_interval_seconds,
            "kafka_topic": self.kafka_topic,
            "enable_kafka_forward": self.enable_kafka_forward,
            "table_name": self.table_name,
            "max_retry_count": self.max_retry_count,
            "enable_auto_recovery": self.enable_auto_recovery,
            "enable_metrics": self.enable_metrics
        }


# Configuration profiles for different environments
class DLQProfiles:
    """Preset configuration profiles"""

    @staticmethod
    def development() -> DLQConfig:
        """Development config - everything enabled for debugging"""
        return DLQConfig(
            enabled=True,
            storage_mode=DLQStorageMode.HYBRID,
            batch_size=10,  # Small batch for fast response
            flush_interval_seconds=0.5,  # Fast flush
            enable_metrics=True,
            log_dropped_events=True,
            enable_auto_recovery=True
        )

    @staticmethod
    def testing() -> DLQConfig:
        """Testing config - DB only, no Kafka"""
        return DLQConfig(
            enabled=True,
            storage_mode=DLQStorageMode.DATABASE_ONLY,
            batch_size=5,
            flush_interval_seconds=0.1,
            enable_kafka_forward=False,
            enable_metrics=True,
            enable_auto_recovery=False
        )

    @staticmethod
    def production() -> DLQConfig:
        """Production config - fully functional mode"""
        return DLQConfig(
            enabled=True,  # ENABLED in production!
            storage_mode=DLQStorageMode.HYBRID,  # Both Kafka and DB
            batch_size=200,  # Optimal batch size
            flush_interval_seconds=2.0,  # Balance between latency and performance
            queue_size=50000,  # Large queue for high loads
            emergency_persist_threshold=45000,  # 90% of queue size
            enable_metrics=True,  # Metrics enabled
            log_dropped_events=False,  # Don't spam logs in production
            dropped_events_threshold=1000,
            enable_kafka_forward=True,  # Kafka forwarding enabled
            enable_auto_recovery=True,  # Auto recovery enabled
            recovery_check_interval=300  # Check every 5 minutes
        )

    @staticmethod
    def high_load() -> DLQConfig:
        """High load config - for extreme loads"""
        return DLQConfig(
            enabled=True,
            storage_mode=DLQStorageMode.KAFKA_ONLY,  # Kafka only for speed
            batch_size=500,
            flush_interval_seconds=5.0,
            queue_size=100000,
            enable_kafka_forward=True,
            enable_metrics=True,
            log_dropped_events=False,
            enable_auto_recovery=True,
            emergency_persist_threshold=90000
        )


# Main function to get config
def get_dlq_config(profile: Optional[str] = None) -> DLQConfig:
    """
    Get DLQ configuration

    Args:
        profile: Profile name (development, testing, production, high_load)
                If not specified - uses production profile by default
    """
    # Use production profile by default
    if not profile:
        return DLQProfiles.production()

    profile_map = {
        "development": DLQProfiles.development,
        "testing": DLQProfiles.testing,
        "production": DLQProfiles.production,
        "high_load": DLQProfiles.high_load
    }

    profile_func = profile_map.get(profile.lower())
    if profile_func:
        return profile_func()

    # If profile not found - return production
    return DLQProfiles.production()


# Table documentation
DLQ_TABLE_COLUMNS = {
    # Primary fields
    "id": "UUID PRIMARY KEY DEFAULT gen_random_uuid()",
    "original_event_id": "UUID",
    "event_type": "TEXT",
    "topic_name": "TEXT",
    "raw_payload": "JSONB NOT NULL",
    "error_message": "TEXT",
    "error_type": "TEXT",
    "consumer_name": "TEXT",
    "retry_count": "INT DEFAULT 0",
    "last_attempted_at": "TIMESTAMP WITH TIME ZONE",

    # Enhanced tracking
    "saga_id": "UUID",
    "causation_id": "UUID",
    "correlation_id": "UUID",
    "aggregate_id": "UUID",
    "aggregate_type": "TEXT",
    "sequence_number": "BIGINT",

    # Classification
    "dlq_reason": "TEXT",
    "dlq_category": "TEXT",
    "recoverable": "BOOLEAN DEFAULT TRUE",

    # Recovery tracking
    "recovery_attempted": "BOOLEAN DEFAULT FALSE",
    "recovery_attempted_at": "TIMESTAMP WITH TIME ZONE",
    "recovery_success": "BOOLEAN",

    # Unified DLQ columns
    "source_system": "TEXT DEFAULT 'sql'",
    "original_topic": "TEXT",
    "reprocess_count": "INT DEFAULT 0",
    "last_reprocess_at": "TIMESTAMP WITH TIME ZONE",

    "created_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
    "payload_size": "INT"
}


# Source system values matching existing schema
class DLQSourceSystem(Enum):
    """Source systems that can send to DLQ"""
    EVENT_PROCESSOR = "event_processor"
    OUTBOX = "outbox"
    EVENT_STORE = "event_store"
    SAGA = "saga"
    PROJECTION = "projection"
    WORKER = "worker"
    API = "api"
    SQL = "sql"  # Default in DB
    KAFKA = "kafka"


# DLQ categories matching what should go in dlq_category column
class DLQCategory(Enum):
    """Error categories for dlq_category column"""
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    VALIDATION = "validation"
    AUTHORIZATION = "authorization"
    PROCESSING = "processing"
    SERIALIZATION = "serialization"
    DATABASE = "database"
    EXTERNAL_SERVICE = "external_service"
    BUSINESS_LOGIC = "business_logic"
    UNKNOWN = "unknown"


# DLQ reasons matching what should go in dlq_reason column
class DLQReason(Enum):
    """Reasons for DLQ for dlq_reason column"""
    PROCESSING_FAILED = "processing_failed"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    VALIDATION_FAILED = "validation_failed"
    HANDLER_NOT_FOUND = "handler_not_found"
    TIMEOUT_EXCEEDED = "timeout_exceeded"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    DEPENDENCY_FAILURE = "dependency_failure"
    UNKNOWN_ERROR = "unknown_error"