# app/config/dlq_config.py
"""
Configuration for DLQ Service that matches existing database schema
UPDATED: Using BaseConfig pattern with Pydantic v2
"""

from functools import lru_cache
from typing import Optional, Dict, Any
from enum import Enum
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from app.common.base.base_config import BaseConfig


class DLQStorageMode(str, Enum):
    """DLQ storage strategies"""
    DATABASE_ONLY = "database"  # Direct to DB
    KAFKA_ONLY = "kafka"  # Only Kafka topic
    HYBRID = "hybrid"  # Both Kafka and DB


class DLQConfig(BaseConfig):
    """
    DLQ Service configuration matching existing dlq_events table
    """

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix='DLQ_',
    )

    # Basic settings - ENABLED BY DEFAULT
    enabled: bool = Field(
        default=True,
        description="DLQ is active by default"
    )

    storage_mode: DLQStorageMode = Field(
        default=DLQStorageMode.HYBRID,
        description="DLQ storage strategy"
    )

    # Queue settings - optimal for production
    queue_size: int = Field(
        default=50000,
        description="Maximum queue size"
    )

    batch_size: int = Field(
        default=200,
        description="Batch size for processing"
    )

    flush_interval_seconds: float = Field(
        default=2.0,
        description="Flush interval in seconds"
    )

    # Kafka settings
    kafka_topic: str = Field(
        default="system.dlq.events",
        description="Kafka topic for DLQ events"
    )

    enable_kafka_forward: bool = Field(
        default=True,
        description="Enable Kafka forwarding"
    )

    # Database settings
    table_name: str = Field(
        default="dlq_events",
        description="Database table name"
    )

    # Retry settings
    max_retry_count: int = Field(
        default=3,
        description="Maximum retry attempts"
    )

    retry_delay_seconds: int = Field(
        default=60,
        description="Delay between retries in seconds"
    )

    # Recovery settings
    enable_auto_recovery: bool = Field(
        default=True,
        description="Enable automatic recovery"
    )

    recovery_check_interval: int = Field(
        default=300,
        description="Recovery check interval in seconds (5 minutes)"
    )

    # Monitoring
    enable_metrics: bool = Field(
        default=True,
        description="Enable metrics collection"
    )

    log_dropped_events: bool = Field(
        default=False,
        description="Log dropped events (can spam logs)"
    )

    dropped_events_threshold: int = Field(
        default=1000,
        description="Threshold for dropped events warning"
    )

    # Performance tuning
    emergency_persist_threshold: int = Field(
        default=45000,
        description="When queue is 90% full"
    )

    max_batch_wait_seconds: float = Field(
        default=5.0,
        description="Maximum wait for batch completion"
    )


# =============================================================================
# Factory Function
# =============================================================================

@lru_cache(maxsize=1)
def get_dlq_config() -> DLQConfig:
    """Get DLQ configuration singleton (cached)."""
    return DLQConfig()


def reset_dlq_config() -> None:
    """Reset config singleton (for testing)."""
    get_dlq_config.cache_clear()


# =============================================================================
# Profile Factory Functions (for specific environments)
# =============================================================================

def create_development_config() -> DLQConfig:
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


def create_testing_config() -> DLQConfig:
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


def create_production_config() -> DLQConfig:
    """Production config - fully functional mode"""
    return DLQConfig(
        enabled=True,
        storage_mode=DLQStorageMode.HYBRID,
        batch_size=200,
        flush_interval_seconds=2.0,
        queue_size=50000,
        emergency_persist_threshold=45000,
        enable_metrics=True,
        log_dropped_events=False,
        dropped_events_threshold=1000,
        enable_kafka_forward=True,
        enable_auto_recovery=True,
        recovery_check_interval=300
    )


def create_high_load_config() -> DLQConfig:
    """High load config - for extreme loads"""
    return DLQConfig(
        enabled=True,
        storage_mode=DLQStorageMode.KAFKA_ONLY,
        batch_size=500,
        flush_interval_seconds=5.0,
        queue_size=100000,
        enable_kafka_forward=True,
        enable_metrics=True,
        log_dropped_events=False,
        enable_auto_recovery=True,
        emergency_persist_threshold=90000
    )


# =============================================================================
# Enums for DLQ Classification
# =============================================================================

class DLQSourceSystem(str, Enum):
    """Source systems that can send to DLQ"""
    EVENT_PROCESSOR = "event_processor"
    OUTBOX = "outbox"
    EVENT_STORE = "event_store"
    SAGA = "saga"
    PROJECTION = "projection"
    WORKER = "worker"
    API = "api"
    SQL = "sql"
    KAFKA = "kafka"


class DLQCategory(str, Enum):
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


class DLQReason(str, Enum):
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
