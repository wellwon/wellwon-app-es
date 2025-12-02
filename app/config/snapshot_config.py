# =============================================================================
# File: app/config/snapshot_config.py
# Description: Configuration for event store automatic snapshots
# UPDATED: Using BaseConfig pattern with Pydantic v2
# =============================================================================

from functools import lru_cache
from typing import Dict, Optional, Any
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from app.common.base.base_config import BaseConfig, BASE_CONFIG_DICT


class SnapshotConfig(BaseConfig):
    """
    Configuration for event store automatic snapshots.
    """

    model_config = SettingsConfigDict(
        **BASE_CONFIG_DICT,
        env_prefix='SNAPSHOT_',
    )

    # =========================================================================
    # Global Snapshot Settings
    # =========================================================================
    enable_auto_snapshots: bool = Field(default=True, description="Enable automatic snapshot creation")
    enable_async_snapshots: bool = Field(default=True, description="Create snapshots asynchronously")

    # =========================================================================
    # Default Snapshot Triggers
    # =========================================================================
    default_event_interval: int = Field(default=100, description="Create snapshot every N events")
    default_time_interval_hours: int = Field(default=24, description="Create snapshot every N hours")
    default_size_threshold_mb: float = Field(default=10.0, description="Create snapshot when events exceed N MB")

    # =========================================================================
    # Per-Aggregate Customization
    # =========================================================================
    aggregate_snapshot_intervals: Dict[str, int] = Field(
        default_factory=lambda: {
            "VirtualBroker": 100,
            "BrokerAccount": 50,
            "Order": 75,
            "Position": 75,
            "Trade": 100,
            "BrokerConnection": 150,
            "Strategy": 100,
            "UserAccount": 200,
            "User": 200,
        },
        description="Custom event intervals per aggregate type"
    )

    aggregate_time_intervals: Dict[str, int] = Field(
        default_factory=lambda: {
            "BrokerAccount": 12,
            "Position": 12,
            "Order": 12,
            "VirtualBroker": 24,
            "UserAccount": 48,
            "User": 48,
        },
        description="Custom time intervals (hours) per aggregate type"
    )

    aggregate_size_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "VirtualBroker": 5.0,
            "Order": 5.0,
            "Position": 5.0,
            "BrokerAccount": 10.0,
            "Strategy": 10.0,
            "UserAccount": 20.0,
        },
        description="Custom size thresholds (MB) per aggregate type"
    )

    # =========================================================================
    # Performance Settings
    # =========================================================================
    snapshot_batch_size: int = Field(default=10, description="Max concurrent snapshot operations")
    snapshot_timeout_seconds: int = Field(default=30, description="Timeout for snapshot creation")
    snapshot_compression_enabled: bool = Field(default=True, description="Enable compression")
    snapshot_compression_type: str = Field(default="snappy", description="snappy, gzip, lz4")

    # =========================================================================
    # Retention Settings
    # =========================================================================
    keep_snapshots_count: int = Field(default=3, description="Number of snapshots to keep per aggregate")
    snapshot_cleanup_enabled: bool = Field(default=True, description="Enable old snapshot cleanup")
    snapshot_retention_days: int = Field(default=30, description="Days to retain old snapshots")

    # =========================================================================
    # Monitoring and Logging
    # =========================================================================
    enable_snapshot_metrics: bool = Field(default=True, description="Track snapshot metrics")
    log_snapshot_creation: bool = Field(default=True, description="Log when snapshots are created")
    enable_snapshot_validation: bool = Field(default=True, description="Validate snapshot integrity")
    alert_on_snapshot_failure: bool = Field(default=True, description="Send alerts on failure")

    # =========================================================================
    # Advanced Settings
    # =========================================================================
    trading_hours_multiplier: float = Field(default=0.5, description="Multiply intervals during trading hours")

    aggregate_special_rules: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "VirtualBroker": {
                "high_activity_threshold": 50,
                "quiet_hours_interval": 200,
                "check_trading_hours": True,
                "force_snapshot_on_balance_change": 0.1
            },
            "BrokerAccount": {
                "balance_change_threshold": 0.01,
                "force_daily_snapshot": True,
                "snapshot_on_withdrawal": True,
                "snapshot_on_deposit": True
            },
            "Order": {
                "completed_orders_threshold": 20,
                "include_open_orders": False,
                "snapshot_on_fill": True,
                "snapshot_on_cancel": True
            },
            "Position": {
                "pnl_change_threshold": 0.05,
                "snapshot_on_close": True,
                "force_eod_snapshot": True
            }
        },
        description="Special rules for specific aggregates"
    )

    # Storage settings
    snapshot_storage_backend: str = Field(default="kafka", description="kafka, s3, redis")
    snapshot_s3_bucket: Optional[str] = Field(default=None, description="S3 bucket for snapshots")
    snapshot_s3_prefix: str = Field(default="event-store/snapshots", description="S3 key prefix")

    # Emergency settings
    disable_snapshots_on_high_load: bool = Field(default=True, description="Disable during high load")
    high_load_threshold_ms: int = Field(default=5000, description="Response time threshold")


# =============================================================================
# Factory Function
# =============================================================================

@lru_cache(maxsize=1)
def get_snapshot_config() -> SnapshotConfig:
    """Get snapshot configuration singleton (cached)."""
    return SnapshotConfig()


def reset_snapshot_config() -> None:
    """Reset config singleton (for testing)."""
    get_snapshot_config.cache_clear()


# =============================================================================
# Helper Functions
# =============================================================================

def get_snapshot_interval_for_aggregate(aggregate_type: str) -> int:
    """Get the event interval for a specific aggregate type"""
    config = get_snapshot_config()
    return config.aggregate_snapshot_intervals.get(
        aggregate_type,
        config.default_event_interval
    )


def get_time_interval_for_aggregate(aggregate_type: str) -> int:
    """Get the time interval (hours) for a specific aggregate type"""
    config = get_snapshot_config()
    return config.aggregate_time_intervals.get(
        aggregate_type,
        config.default_time_interval_hours
    )


def get_size_threshold_for_aggregate(aggregate_type: str) -> float:
    """Get the size threshold (MB) for a specific aggregate type"""
    config = get_snapshot_config()
    return config.aggregate_size_thresholds.get(
        aggregate_type,
        config.default_size_threshold_mb
    )


def should_force_snapshot(
        aggregate_type: str,
        event_type: str,
        event_data: Dict[str, Any]
) -> bool:
    """Check if a snapshot should be forced based on special rules."""
    config = get_snapshot_config()
    special_rules = config.aggregate_special_rules.get(aggregate_type, {})

    if aggregate_type == "Order":
        if event_type in ["OrderFilled", "OrderCancelled"] and special_rules.get("snapshot_on_fill"):
            return True
    elif aggregate_type == "Position":
        if event_type == "PositionClosed" and special_rules.get("snapshot_on_close"):
            return True
    elif aggregate_type == "BrokerAccount":
        if event_type in ["Withdrawal", "Deposit"] and special_rules.get("snapshot_on_withdrawal"):
            return True

    return False


def validate_snapshot_config() -> None:
    """Validate snapshot configuration for common issues."""
    config = get_snapshot_config()

    if config.default_event_interval < 1:
        raise ValueError("default_event_interval must be at least 1")
    if config.default_time_interval_hours < 0.1:
        raise ValueError("default_time_interval_hours must be at least 0.1")
    if config.default_size_threshold_mb <= 0:
        raise ValueError("default_size_threshold_mb must be positive")
    if config.snapshot_batch_size < 1:
        raise ValueError("snapshot_batch_size must be at least 1")
    if config.snapshot_timeout_seconds < 1:
        raise ValueError("snapshot_timeout_seconds must be at least 1")
    if config.keep_snapshots_count < 1:
        raise ValueError("keep_snapshots_count must be at least 1")

    valid_compression = {"snappy", "gzip", "lz4", "none"}
    if config.snapshot_compression_type not in valid_compression:
        raise ValueError(f"snapshot_compression_type must be one of {valid_compression}")

    valid_backends = {"kafka", "s3", "redis"}
    if config.snapshot_storage_backend not in valid_backends:
        raise ValueError(f"snapshot_storage_backend must be one of {valid_backends}")

    if config.snapshot_storage_backend == "s3" and not config.snapshot_s3_bucket:
        raise ValueError("snapshot_s3_bucket must be specified when using S3 backend")


# Backward compatibility
def load_snapshot_config_from_env() -> SnapshotConfig:
    """Deprecated: Use get_snapshot_config() instead"""
    return get_snapshot_config()


def create_default_snapshot_config() -> SnapshotConfig:
    """Create a default snapshot configuration"""
    return SnapshotConfig()
