# =============================================================================
# File: app/config/wse_config.py
# Description: WebSocket Event System - Technical Configuration
#              Enterprise pattern with admin UI support and hot-reload
# UPDATED: Using BaseConfig pattern
# =============================================================================

from functools import lru_cache
from typing import Dict, Any, Optional, List
from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict
from enum import Enum

from app.common.base.base_config import BaseConfig


# =============================================================================
# Enums
# =============================================================================

class EventPriority(str, Enum):
    """Event priority levels"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"
    BACKGROUND = "BACKGROUND"


# =============================================================================
# WSE Configuration Class (Pydantic BaseSettings)
# =============================================================================

class WSEConfig(BaseConfig):
    """
    WebSocket Event System Configuration (Enterprise Pattern)

    Features:
    - Pydantic validation with type hints
    - Environment variable support (WSE_ prefix)
    - .env file loading
    - Hot-reload support via Redis
    - Admin UI ready (GET/PUT endpoints)
    - Runtime overrides from database

    Usage:
        # In code:
        from app.config.wse_config import get_wse_config

        config = get_wse_config()
        heartbeat = config.heartbeat_interval  # Type-safe!

        # In admin API:
        config.update_setting("heartbeat_interval", 20)
        await config.reload()  # Hot-reload across all instances
    """

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix='WSE_',
        validate_assignment=True,  # Validate on property updates
    )

    # =========================================================================
    # Connection & Protocol Settings
    # =========================================================================

    protocol_version: int = Field(
        default=2,
        description="WebSocket protocol version"
    )

    heartbeat_interval: int = Field(
        default=15,
        ge=5,
        le=60,
        description="Heartbeat/ping interval in seconds (from wse_connection.py:34)"
    )

    ping_timeout: int = Field(
        default=10,
        ge=5,
        le=30,
        description="Wait for pong response timeout in seconds"
    )

    idle_timeout: int = Field(
        default=40,
        ge=20,
        le=300,
        description="Idle connection timeout in seconds (from wse_connection.py:35)"
    )

    close_timeout: int = Field(
        default=5,
        ge=1,
        le=30,
        description="Graceful close timeout in seconds"
    )

    stale_timeout: int = Field(
        default=3600,
        ge=600,
        le=7200,
        description="Mark connection as stale after N seconds (from wse_manager.py:309)"
    )

    max_connections_per_user: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Max WebSocket connections per user (Industry standard 2025: 1 with multiplexing)"
    )

    # Rate limiting (regular users)
    rate_limit_capacity: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Token bucket capacity for regular users"
    )

    rate_limit_refill_rate: float = Field(
        default=100.0,
        ge=10.0,
        le=1000.0,
        description="Token bucket refill rate (messages per second)"
    )

    # Premium user rate limiting
    premium_rate_limit_capacity: int = Field(
        default=5000,
        ge=1000,
        le=20000,
        description="Token bucket capacity for premium users"
    )

    premium_rate_limit_refill_rate: float = Field(
        default=500.0,
        ge=100.0,
        le=2000.0,
        description="Token bucket refill rate for premium users"
    )

    # IP-based rate limiting (DDoS protection)
    ip_rate_limit_capacity: int = Field(
        default=10000,
        ge=1000,
        le=50000,
        description="Token bucket capacity per IP"
    )

    ip_rate_limit_refill_rate: float = Field(
        default=1000.0,
        ge=100.0,
        le=5000.0,
        description="Token bucket refill rate per IP"
    )

    # Message size limits
    max_message_size: int = Field(
        default=1024 * 1024,  # 1MB
        ge=64 * 1024,
        le=10 * 1024 * 1024,
        description="Maximum message size in bytes"
    )

    max_frame_size: int = Field(
        default=64 * 1024,  # 64KB
        ge=8 * 1024,
        le=1024 * 1024,
        description="Maximum WebSocket frame size in bytes"
    )

    # =========================================================================
    # Message Batching & Compression
    # =========================================================================

    batching_enabled: bool = Field(
        default=True,
        description="Enable message batching"
    )

    batch_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Max messages per batch (from wse_connection.py:118)"
    )

    batch_timeout_ms: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Flush batch after N milliseconds even if not full"
    )

    compression_enabled: bool = Field(
        default=True,
        description="Enable gzip compression"
    )

    compression_threshold: int = Field(
        default=1024,
        ge=256,
        le=8192,
        description="Compress if message > N bytes (from wse_connection.py:38, wse_compression.py:23)"
    )

    compression_level: int = Field(
        default=6,
        ge=1,
        le=9,
        description="Gzip compression level (1-9, 6 is balanced)"
    )

    min_compression_ratio: float = Field(
        default=0.9,
        ge=0.5,
        le=1.0,
        description="Minimum compression ratio to consider beneficial"
    )

    # =========================================================================
    # Event Queue & Buffering
    # =========================================================================

    max_queue_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Max events in memory per connection (ACTUAL: wse_queue.py:24 uses 1000!)"
    )

    high_priority_weight: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Process N high priority messages before 1 normal"
    )

    memory_limit_mb: int = Field(
        default=50,
        ge=10,
        le=500,
        description="Max memory for queue in MB"
    )

    priority_critical: int = Field(
        default=10,
        description="Priority level for CRITICAL messages"
    )

    priority_high: int = Field(
        default=8,
        description="Priority level for HIGH messages"
    )

    priority_normal: int = Field(
        default=5,
        description="Priority level for NORMAL messages"
    )

    priority_low: int = Field(
        default=3,
        description="Priority level for LOW messages"
    )

    priority_background: int = Field(
        default=1,
        description="Priority level for BACKGROUND messages"
    )

    drop_on_overflow: bool = Field(
        default=True,
        description="Drop oldest events if queue is full"
    )

    overflow_strategy: str = Field(
        default="drop_oldest",
        description="Strategy when queue is full: drop_oldest, drop_newest, block"
    )

    buffered_event_age_limit: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Cleanup buffered events older than N seconds (from wse_event_sequencer.py:236)"
    )

    # =========================================================================
    # Event Filtering & Control
    # =========================================================================

    control_events: List[str] = Field(
        default=[
            "subscription_acknowledged",
            "subscription_update",
            "error",
            "connection_state_change",
            "server_hello",
            "health_check_response",
            "heartbeat",
            "PONG",
            "snapshot_complete",
        ],
        description="Events that bypass normal processing (control plane)"
    )

    startup_filter_duration: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Startup grace period in seconds (from wse_connection.py:303)"
    )

    startup_filter_age_threshold: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Filter events older than N seconds during startup (from wse_connection.py:338)"
    )

    startup_filtered_events: List[str] = Field(
        default=[
            "broker_connection_update",
            "broker_status_update",
        ],
        description="Heavy events to filter during startup"
    )

    # =========================================================================
    # Monitoring & Health Checks
    # =========================================================================

    monitoring_start_delay_seconds: int = Field(
        default=2,
        ge=0,
        le=30,
        description="Delay before starting broker monitoring"
    )

    health_check_interval: int = Field(
        default=30,
        ge=10,
        le=300,
        description="Health check interval in seconds (ACTUAL: wse_connection.py:36 uses 30s!)"
    )

    connection_health_timeout: int = Field(
        default=30,
        ge=10,
        le=120,
        description="Mark connection unhealthy if no response after N seconds"
    )

    metrics_flush_interval: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Metrics collection interval in seconds (from wse_connection.py:37)"
    )

    cleanup_interval: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Connection cleanup interval in seconds (from wse_manager.py:301)"
    )

    sequencer_cleanup_interval: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Event sequencer cleanup interval in seconds (from wse_event_sequencer.py:261)"
    )

    sequence_cleanup_interval: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Sequence tracking cleanup interval in seconds (from wse_connection.py:742)"
    )

    prevent_duplicate_tasks: bool = Field(
        default=True,
        description="Prevent duplicate monitoring tasks"
    )

    # =========================================================================
    # Redis Pub/Sub Settings
    # =========================================================================

    pubsub_topic_prefix: str = Field(
        default="wse:",
        description="Topic prefix for namespacing (from pubsub_bus.py:149)"
    )

    pubsub_use_pattern_subscribe: bool = Field(
        default=True,
        description="Use PSUBSCRIBE for pattern matching"
    )

    pubsub_auto_reconnect: bool = Field(
        default=True,
        description="Auto-reconnect on Redis Pub/Sub disconnect"
    )

    pubsub_reconnect_delay: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Reconnection delay in seconds"
    )

    pubsub_max_reconnect_attempts: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum reconnection attempts"
    )

    # =========================================================================
    # Performance & Optimization
    # =========================================================================

    use_background_tasks: bool = Field(
        default=True,
        description="Use asyncio.create_task for handlers"
    )

    max_concurrent_handlers: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Max parallel event handlers"
    )

    cache_topic_normalizations: bool = Field(
        default=True,
        description="Cache topic_map lookups"
    )

    cache_event_mappings: bool = Field(
        default=True,
        description="Cache event type transformations"
    )

    deduplicate_events: bool = Field(
        default=True,
        description="Prevent duplicate event sends"
    )

    dedup_window_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Remember event IDs for N seconds"
    )

    seen_message_ids_limit: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Max message IDs to track (from wse_connection.py:155)"
    )

    seen_message_ids_cleanup_threshold: int = Field(
        default=5000,
        ge=1000,
        le=50000,
        description="Cleanup when exceeds N (from wse_connection.py:745)"
    )

    event_sequencer_window_size: int = Field(
        default=10000,
        ge=1000,
        le=100000,
        description="Event sequencer dedup window size (from wse_event_sequencer.py:29)"
    )

    event_sequencer_max_out_of_order: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Max out-of-order buffer size (from wse_event_sequencer.py:29)"
    )

    quote_throttle_ms: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Max 10 quotes/sec per symbol (from market_data_publisher.py:64)"
    )

    significant_price_change_threshold: float = Field(
        default=0.001,
        ge=0.0001,
        le=0.1,
        description="0.1% price change bypasses throttle (from market_data_publisher.py:65)"
    )

    # =========================================================================
    # Reliability & Error Handling
    # =========================================================================

    circuit_breaker_enabled: bool = Field(
        default=True,
        description="Enable circuit breaker for WSE operations"
    )

    circuit_breaker_threshold: int = Field(
        default=10,
        ge=3,
        le=50,
        description="Failures before opening circuit"
    )

    circuit_breaker_timeout: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Seconds before retry after circuit open"
    )

    retry_transient_errors: bool = Field(
        default=True,
        description="Retry on transient errors"
    )

    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Max retry attempts"
    )

    retry_delay_ms: int = Field(
        default=100,
        ge=10,
        le=5000,
        description="Exponential backoff base delay in milliseconds"
    )

    track_error_metrics: bool = Field(
        default=True,
        description="Track error metrics"
    )

    max_error_samples: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Keep last N errors"
    )

    # =========================================================================
    # Development & Debugging
    # =========================================================================

    log_all_events: bool = Field(
        default=False,
        description="Log every event (very verbose!)"
    )

    log_slow_handlers: bool = Field(
        default=True,
        description="Log handlers taking > threshold"
    )

    slow_handler_threshold_ms: int = Field(
        default=500,
        ge=100,
        le=5000,
        description="Warn if handler takes > N milliseconds"
    )

    high_processing_time_warning_ms: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Log warning if WSE processing > N milliseconds (from wse_connection.py:499)"
    )

    high_processing_time_info_ms: int = Field(
        default=50,
        ge=10,
        le=500,
        description="Log info if WSE processing > N milliseconds (from wse_connection.py:500)"
    )

    expose_metrics_endpoint: bool = Field(
        default=True,
        description="Expose /api/wse/metrics endpoint"
    )

    expose_debug_endpoint: bool = Field(
        default=True,
        description="Expose /api/wse/debug endpoint"
    )

    mock_redis_in_tests: bool = Field(
        default=False,
        description="Use fakeredis for tests"
    )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def get_priority_level(self, priority_name: str) -> int:
        """Get numeric priority level from name (e.g., 'CRITICAL' -> 10)"""
        priority_map = {
            "CRITICAL": self.priority_critical,
            "HIGH": self.priority_high,
            "NORMAL": self.priority_normal,
            "LOW": self.priority_low,
            "BACKGROUND": self.priority_background,
        }
        return priority_map.get(priority_name.upper(), self.priority_normal)

    def get_priority_levels(self) -> Dict[str, int]:
        """Get all priority levels as dict"""
        return {
            "CRITICAL": self.priority_critical,
            "HIGH": self.priority_high,
            "NORMAL": self.priority_normal,
            "LOW": self.priority_low,
            "BACKGROUND": self.priority_background,
        }

    def is_control_event(self, event_type: str) -> bool:
        """Check if event is a control event (bypass normal processing)"""
        return event_type in self.control_events

    def should_filter_during_startup(self, event_type: str, connection_age_seconds: float) -> bool:
        """Check if event should be filtered during connection startup"""
        if connection_age_seconds > self.startup_filter_duration:
            return False
        return event_type in self.startup_filtered_events

    def to_dict(self) -> Dict[str, Any]:
        """Export config as dictionary (for admin UI)"""
        return self.model_dump()

    def update_from_dict(self, updates: Dict[str, Any]) -> None:
        """Update config from dictionary (for admin UI hot-reload)"""
        for key, value in updates.items():
            if hasattr(self, key):
                setattr(self, key, value)

# =============================================================================
# Factory Function
# =============================================================================

@lru_cache(maxsize=1)
def get_wse_config() -> WSEConfig:
    """Get WSE configuration singleton (cached)."""
    return WSEConfig()


def reset_wse_config() -> None:
    """Reset config singleton (for testing/hot-reload)."""
    get_wse_config.cache_clear()


def reload_wse_config() -> WSEConfig:
    """Force reload configuration (hot-reload)."""
    reset_wse_config()
    return get_wse_config()


# =============================================================================
# Backward Compatibility Helpers (for existing code)
# =============================================================================

def get_connection_setting(key: str, default: Any = None) -> Any:
    """Get connection setting (backward compatibility)"""
    config = get_wse_config()
    return getattr(config, key, default)


def get_batching_setting(key: str, default: Any = None) -> Any:
    """Get batching setting (backward compatibility)"""
    config = get_wse_config()

    # Map old keys to new attribute names
    key_map = {
        "batch_size": "batch_size",
        "batch_timeout_ms": "batch_timeout_ms",
        "compression_threshold": "compression_threshold",
        "compression_level": "compression_level",
        "min_compression_ratio": "min_compression_ratio",
    }

    attr_name = key_map.get(key, key)
    return getattr(config, attr_name, default)


def get_queue_setting(key: str, default: Any = None) -> Any:
    """Get queue setting (backward compatibility)"""
    config = get_wse_config()

    key_map = {
        "max_queue_size": "max_queue_size",
        "buffered_event_age_limit": "buffered_event_age_limit",
    }

    attr_name = key_map.get(key, key)
    return getattr(config, attr_name, default)


def get_filtering_setting(key: str, default: Any = None) -> Any:
    """Get filtering setting (backward compatibility)"""
    config = get_wse_config()

    key_map = {
        "startup_filter_duration": "startup_filter_duration",
        "startup_filter_age_threshold": "startup_filter_age_threshold",
    }

    attr_name = key_map.get(key, key)
    return getattr(config, attr_name, default)


def get_monitoring_setting(key: str, default: Any = None) -> Any:
    """Get monitoring setting (backward compatibility)"""
    config = get_wse_config()

    key_map = {
        "health_check_interval": "health_check_interval",
        "metrics_flush_interval": "metrics_flush_interval",
        "cleanup_interval": "cleanup_interval",
        "sequencer_cleanup_interval": "sequencer_cleanup_interval",
        "sequence_cleanup_interval": "sequence_cleanup_interval",
    }

    attr_name = key_map.get(key, key)
    return getattr(config, attr_name, default)


def get_performance_setting(key: str, default: Any = None) -> Any:
    """Get performance setting (backward compatibility)"""
    config = get_wse_config()

    key_map = {
        "seen_message_ids_limit": "seen_message_ids_limit",
        "seen_message_ids_cleanup_threshold": "seen_message_ids_cleanup_threshold",
        "event_sequencer_window_size": "event_sequencer_window_size",
        "event_sequencer_max_out_of_order": "event_sequencer_max_out_of_order",
        "quote_throttle_ms": "quote_throttle_ms",
        "significant_price_change_threshold": "significant_price_change_threshold",
    }

    attr_name = key_map.get(key, key)
    return getattr(config, attr_name, default)


def get_debug_setting(key: str, default: Any = None) -> Any:
    """Get debug setting (backward compatibility)"""
    config = get_wse_config()

    key_map = {
        "high_processing_time_warning_ms": "high_processing_time_warning_ms",
        "high_processing_time_info_ms": "high_processing_time_info_ms",
    }

    attr_name = key_map.get(key, key)
    return getattr(config, attr_name, default)


def is_control_event(event_type: str) -> bool:
    """Check if event is a control event (backward compatibility)"""
    config = get_wse_config()
    return config.is_control_event(event_type)


def should_filter_during_startup(event_type: str, connection_age_seconds: float) -> bool:
    """Check if event should be filtered during startup (backward compatibility)"""
    config = get_wse_config()
    return config.should_filter_during_startup(event_type, connection_age_seconds)


def get_priority_level(priority_name: str) -> int:
    """Get numeric priority level from name (backward compatibility)"""
    config = get_wse_config()
    return config.get_priority_level(priority_name)


# =============================================================================
# EOF
# =============================================================================
