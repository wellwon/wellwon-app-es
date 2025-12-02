# app/config/outbox_config.py
# =============================================================================
# Outbox Service Configuration - OPTIMIZED FOR LOW LATENCY
# UPDATED: Using BaseConfig pattern
# =============================================================================

"""
Outbox Service Configuration

Controls polling intervals, batch sizes, and retry behavior for the
exactly-once event publishing pipeline (EventStore → Transport).

OPTIMIZED (2025-11-05): Tuned for ~500ms total latency while maintaining
100% CQRS/ES/DDD architectural compliance.
"""

from functools import lru_cache
from typing import Dict, Set
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from app.common.base.base_config import BaseConfig


class OutboxConfig(BaseConfig):
    """
    Configuration for Transport Outbox Service.

    This service ensures exactly-once delivery of events from the Event Store
    to transport streams (Redpanda/Redis) for worker consumption.

    OPTIMIZED FOR LOW LATENCY:
    - Poll interval: 50ms (2x faster than default 100ms)
    - Batch size: 20 events (smaller batches = faster processing)
    - Consumer optimizations: 5ms fetch wait, 5 records per poll
    """

    # =========================================================================
    # Polling Configuration - CRITICAL FOR LATENCY
    # =========================================================================

    poll_interval_seconds: float = Field(
        default=0.05,  # OPTIMIZED: 50ms for ~500ms total latency (was 0.1 = 100ms)
        description="How often to poll for pending events (seconds). Lower = faster but higher CPU"
    )

    batch_size: int = Field(
        default=20,  # OPTIMIZED: Smaller batches for lower latency (was 50)
        description="Max events to process per batch. Smaller = faster processing per batch"
    )

    # =========================================================================
    # Retry Configuration
    # =========================================================================

    max_retry_attempts: int = Field(
        default=3,
        description="Maximum retry attempts for failed publishes"
    )

    retry_delay_seconds: int = Field(
        default=5,
        description="Initial delay between retries (seconds)"
    )

    use_exponential_backoff: bool = Field(
        default=True,
        description="Use exponential backoff for retries"
    )

    # =========================================================================
    # Dead Letter Queue Configuration
    # =========================================================================

    dead_letter_after_hours: int = Field(
        default=24,
        description="Move to DLQ after this many hours of failed attempts"
    )

    enable_dlq: bool = Field(
        default=True,
        description="Enable Dead Letter Queue for poison pills"
    )

    # =========================================================================
    # Synchronous Processing (for SYNC events)
    # =========================================================================

    synchronous_mode: bool = Field(
        default=False,
        description="Process all events synchronously (blocks until published)"
    )

    synchronous_event_types: Set[str] = Field(
        default_factory=lambda: {
            # Critical events that need immediate processing
            "BrokerConnectionEstablished",
            "BrokerConnectionInitiated",
            "BrokerTokensSuccessfullyStored",
            "UserAccountCreated",
            "UserAccountDeleted",
        },
        description="Event types to process synchronously (immediate publish)"
    )

    # =========================================================================
    # Adaptive Polling
    # =========================================================================

    enable_adaptive_polling: bool = Field(
        default=True,
        description="Adjust polling interval based on event volume"
    )

    adaptive_poll_min_interval_seconds: float = Field(
        default=0.05,  # 50ms minimum
        description="Minimum adaptive poll interval (seconds)"
    )

    adaptive_poll_max_interval_seconds: float = Field(
        default=1.0,  # 1 second maximum
        description="Maximum adaptive poll interval when idle (seconds)"
    )

    adaptive_poll_empty_threshold: int = Field(
        default=5,
        description="Number of empty polls before increasing interval"
    )

    # =========================================================================
    # Exactly-Once Semantics - Transactional Publishing (NEW)
    # =========================================================================

    enable_transactional_publishing: bool = Field(
        default=False,  # Conservative default - enable explicitly for TRUE exactly-once
        description="Use Kafka transactions for atomic outbox → Kafka publish (TRUE exactly-once)"
    )

    # =========================================================================
    # Monitoring & Metrics
    # =========================================================================

    enable_metrics: bool = Field(
        default=True,
        description="Enable Prometheus metrics collection"
    )

    enable_poison_pill_detection: bool = Field(
        default=True,
        description="Enable poison pill detection for DLQ routing"
    )

    poison_pill_failure_threshold: int = Field(
        default=5,
        description="Number of failures before marking as poison pill"
    )

    log_publish_success: bool = Field(
        default=False,  # Too verbose for production
        description="Log each successful publish (verbose)"
    )

    log_publish_failure: bool = Field(
        default=True,
        description="Log publish failures"
    )

    # =========================================================================
    # Transport Topic Mappings
    # =========================================================================

    custom_topic_mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom event type → transport topic mappings"
    )

    default_transport_topic_prefix: str = Field(
        default="transport",
        description="Prefix for transport topics"
    )

    # =========================================================================
    # Performance Tuning
    # =========================================================================

    connection_pool_size: int = Field(
        default=10,
        description="Connection pool size for Redpanda/Redis"
    )

    publish_timeout_seconds: float = Field(
        default=5.0,
        description="Timeout for individual publish operations"
    )

    enable_compression: bool = Field(
        default=True,
        description="Enable event compression for transport"
    )

    compression_threshold_bytes: int = Field(
        default=1024,  # 1KB
        description="Compress events larger than this (bytes)"
    )

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix='OUTBOX_',
    )


# =============================================================================
# Factory Function
# =============================================================================

@lru_cache(maxsize=1)
def get_outbox_config() -> OutboxConfig:
    """Get outbox configuration singleton (cached)."""
    return OutboxConfig()


def reset_outbox_config() -> None:
    """Reset config singleton (for testing)."""
    get_outbox_config.cache_clear()


# =============================================================================
# Profile Factory Functions (for specific environments)
# =============================================================================

def create_production_config() -> OutboxConfig:
    """
    Create production-optimized configuration.
    Balanced between latency and resource usage.
    """
    return OutboxConfig(
        poll_interval_seconds=0.05,  # Keep 50ms for fast response
        batch_size=30,  # Slightly larger batches for efficiency
        max_retry_attempts=5,  # More retries in production
        enable_metrics=True,
        enable_poison_pill_detection=True,
        log_publish_success=False,  # Too verbose
        log_publish_failure=True,
    )


def create_development_config() -> OutboxConfig:
    """
    Create development-optimized configuration.
    Faster feedback, more logging.
    """
    return OutboxConfig(
        poll_interval_seconds=0.05,  # Fast polling for dev
        batch_size=10,  # Small batches for easy debugging
        max_retry_attempts=3,
        enable_metrics=False,  # Less overhead in dev
        log_publish_success=True,  # Verbose logging for debugging
        log_publish_failure=True,
    )


def create_testing_config() -> OutboxConfig:
    """
    Create testing-optimized configuration.
    Immediate processing, no retries, predictable behavior.
    """
    return OutboxConfig(
        poll_interval_seconds=0.01,  # 10ms for ultra-fast tests
        batch_size=1,  # Process one at a time for predictability
        max_retry_attempts=1,  # Don't retry in tests
        use_exponential_backoff=False,
        enable_adaptive_polling=False,  # Deterministic polling
        synchronous_mode=True,  # Block until published
        enable_metrics=False,
        log_publish_success=True,
        log_publish_failure=True,
    )


def create_high_throughput_config() -> OutboxConfig:
    """
    Create high-throughput configuration.
    Optimized for large event volumes, not latency.
    """
    return OutboxConfig(
        poll_interval_seconds=0.2,  # Slower polling
        batch_size=100,  # Large batches
        max_retry_attempts=5,
        enable_adaptive_polling=True,
        adaptive_poll_max_interval_seconds=2.0,  # Back off more
        enable_compression=True,
        compression_threshold_bytes=512,  # Compress more
    )




# =============================================================================
# Validation Functions
# =============================================================================

def validate_outbox_config(config: OutboxConfig) -> None:
    """
    Validate outbox configuration.

    Raises:
        ValueError: If configuration is invalid
    """
    if config.poll_interval_seconds < 0.01:
        raise ValueError("poll_interval_seconds must be at least 0.01 (10ms)")

    if config.poll_interval_seconds > 60:
        raise ValueError("poll_interval_seconds cannot exceed 60 seconds")

    if config.batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    if config.batch_size > 1000:
        raise ValueError("batch_size cannot exceed 1000")

    if config.max_retry_attempts < 0:
        raise ValueError("max_retry_attempts cannot be negative")

    if config.publish_timeout_seconds < 0.1:
        raise ValueError("publish_timeout_seconds must be at least 0.1")

    if config.adaptive_poll_min_interval_seconds > config.adaptive_poll_max_interval_seconds:
        raise ValueError("adaptive_poll_min_interval must be <= adaptive_poll_max_interval")


# =============================================================================
# Helper Functions
# =============================================================================

def get_outbox_config_summary(config: OutboxConfig) -> Dict[str, any]:
    """Get human-readable summary of outbox configuration"""
    return {
        "latency_profile": "low" if config.poll_interval_seconds <= 0.05 else "medium" if config.poll_interval_seconds <= 0.1 else "high",
        "poll_interval_ms": int(config.poll_interval_seconds * 1000),
        "batch_size": config.batch_size,
        "estimated_latency_ms": estimate_latency(config),
        "throughput_profile": "high" if config.batch_size >= 50 else "medium" if config.batch_size >= 20 else "low",
        "adaptive_polling": config.enable_adaptive_polling,
        "retry_attempts": config.max_retry_attempts,
        "dlq_enabled": config.enable_dlq,
        "metrics_enabled": config.enable_metrics,
    }


def estimate_latency(config: OutboxConfig) -> int:
    """
    Estimate average latency in milliseconds.

    Formula: poll_interval + processing_time + publish_time
    """
    poll_latency = config.poll_interval_seconds * 1000  # Convert to ms
    processing_latency = config.batch_size * 2  # ~2ms per event
    publish_latency = 100  # Base Redpanda latency

    return int(poll_latency + processing_latency + publish_latency)


# =============================================================================
# EOF
# =============================================================================
