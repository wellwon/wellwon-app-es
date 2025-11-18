# =============================================================================
# File: app/config/snapshot_config.py
# Description: Configuration for event store automatic snapshots (Pydantic v2)
# =============================================================================

from typing import Dict, Optional, Any  # Added Any import
from pydantic import Field
from pydantic_settings import BaseSettings


class SnapshotConfig(BaseSettings):
    """
    Configuration for event store automatic snapshots.

    This configuration controls when and how snapshots are created for aggregates
    in the event store. Snapshots improve read performance by providing a
    materialized state at a specific version, reducing the number of events
    that need to be replayed.
    """

    # =========================================================================
    # Global Snapshot Settings
    # =========================================================================

    enable_auto_snapshots: bool = Field(
        default=True,
        description="Enable automatic snapshot creation"
    )

    enable_async_snapshots: bool = Field(
        default=True,
        description="Create snapshots asynchronously to avoid blocking"
    )

    # =========================================================================
    # Default Snapshot Triggers
    # =========================================================================

    default_event_interval: int = Field(
        default=100,
        description="Create snapshot every N events"
    )

    default_time_interval_hours: int = Field(
        default=24,
        description="Create snapshot every N hours"
    )

    default_size_threshold_mb: float = Field(
        default=10.0,
        description="Create snapshot when events exceed N MB"
    )

    # =========================================================================
    # Per-Aggregate Customization
    # =========================================================================

    aggregate_snapshot_intervals: Dict[str, int] = Field(
        default_factory=lambda: {
            # Financial aggregates - more frequent snapshots
            "VirtualBroker": 100,  # High activity, critical for trading
            "BrokerAccount": 50,  # Critical financial data
            "Order": 75,  # High importance, frequent updates
            "Position": 75,  # High importance, tracks P&L
            "Trade": 100,  # Medium activity

            # Connection and strategy aggregates
            "BrokerConnection": 150,  # Medium activity
            "Strategy": 100,  # Medium activity

            # User aggregates - less frequent snapshots
            "UserAccount": 200,  # Low change frequency
            "User": 200,  # Low change frequency
        },
        description="Custom event intervals per aggregate type"
    )

    # Time intervals per aggregate type (hours)
    aggregate_time_intervals: Dict[str, int] = Field(
        default_factory=lambda: {
            "BrokerAccount": 12,  # More frequent for financial data
            "Position": 12,  # Track positions more frequently
            "Order": 12,  # Active orders need frequent snapshots
            "VirtualBroker": 24,  # Daily snapshots
            "UserAccount": 48,  # Less frequent for user data
            "User": 48,  # Less frequent for user data
        },
        description="Custom time intervals (hours) per aggregate type"
    )

    # Size thresholds per aggregate type (MB)
    aggregate_size_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "VirtualBroker": 5.0,  # Smaller threshold for high-activity aggregates
            "Order": 5.0,  # Orders can accumulate quickly
            "Position": 5.0,  # Positions track many updates
            "BrokerAccount": 10.0,  # Standard threshold
            "Strategy": 10.0,  # Standard threshold
            "UserAccount": 20.0,  # Larger threshold for low-activity aggregates
        },
        description="Custom size thresholds (MB) per aggregate type"
    )

    # =========================================================================
    # Performance Settings
    # =========================================================================

    snapshot_batch_size: int = Field(
        default=10,
        description="Max concurrent snapshot operations"
    )

    snapshot_timeout_seconds: int = Field(
        default=30,
        description="Timeout for snapshot creation"
    )

    snapshot_compression_enabled: bool = Field(
        default=True,
        description="Enable compression for snapshot data"
    )

    snapshot_compression_type: str = Field(
        default="snappy",
        description="Compression type (snappy, gzip, lz4)"
    )

    # =========================================================================
    # Retention Settings
    # =========================================================================

    keep_snapshots_count: int = Field(
        default=3,
        description="Number of snapshots to keep per aggregate"
    )

    snapshot_cleanup_enabled: bool = Field(
        default=True,
        description="Enable old snapshot cleanup"
    )

    snapshot_retention_days: int = Field(
        default=30,
        description="Days to retain old snapshots"
    )

    # =========================================================================
    # Monitoring and Logging
    # =========================================================================

    enable_snapshot_metrics: bool = Field(
        default=True,
        description="Track snapshot metrics"
    )

    log_snapshot_creation: bool = Field(
        default=True,
        description="Log when snapshots are created"
    )

    enable_snapshot_validation: bool = Field(
        default=True,
        description="Validate snapshot integrity after creation"
    )

    alert_on_snapshot_failure: bool = Field(
        default=True,
        description="Send alerts when snapshot creation fails"
    )

    # =========================================================================
    # Advanced Settings
    # =========================================================================

    # Special rules for high-activity periods
    trading_hours_multiplier: float = Field(
        default=0.5,
        description="Multiply intervals by this during trading hours (0.5 = 2x more frequent)"
    )

    # Aggregate-specific rules
    aggregate_special_rules: Dict[str, Dict[str, Any]] = Field(  # Changed from 'any' to 'Any'
        default_factory=lambda: {
            "VirtualBroker": {
                "high_activity_threshold": 50,
                "quiet_hours_interval": 200,
                "check_trading_hours": True,
                "force_snapshot_on_balance_change": 0.1  # 10% balance change
            },
            "BrokerAccount": {
                "balance_change_threshold": 0.01,  # 1% balance change
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
                "pnl_change_threshold": 0.05,  # 5% P&L change
                "snapshot_on_close": True,
                "force_eod_snapshot": True  # End of day snapshot
            }
        },
        description="Special rules for specific aggregates"
    )

    # Snapshot storage settings
    snapshot_storage_backend: str = Field(
        default="kafka",
        description="Storage backend for snapshots (kafka, s3, redis)"
    )

    # For S3 backend
    snapshot_s3_bucket: Optional[str] = Field(
        default=None,
        description="S3 bucket for snapshot storage"
    )

    snapshot_s3_prefix: str = Field(
        default="event-store/snapshots",
        description="S3 key prefix for snapshots"
    )

    # Emergency settings
    disable_snapshots_on_high_load: bool = Field(
        default=True,
        description="Temporarily disable snapshots during high load"
    )

    high_load_threshold_ms: int = Field(
        default=5000,
        description="Response time threshold to consider as high load"
    )

    # =========================================================================
    # Environment Configuration
    # =========================================================================

    model_config = {
        "env_prefix": "SNAPSHOT_",
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "allow",
        "json_encoders": {
            # Add custom encoders if needed
        }
    }


# =============================================================================
# Factory Functions
# =============================================================================

def create_default_snapshot_config() -> SnapshotConfig:
    """Create a default snapshot configuration"""
    return SnapshotConfig()


def create_production_snapshot_config() -> SnapshotConfig:
    """Create a production-optimized snapshot configuration"""
    return SnapshotConfig(
        # More aggressive snapshotting in production
        default_event_interval=50,
        default_time_interval_hours=12,
        default_size_threshold_mb=5.0,

        # Higher performance settings
        snapshot_batch_size=20,
        enable_async_snapshots=True,

        # Better retention
        keep_snapshots_count=5,
        snapshot_retention_days=60,

        # Enhanced monitoring
        enable_snapshot_metrics=True,
        enable_snapshot_validation=True,
        alert_on_snapshot_failure=True
    )


def create_development_snapshot_config() -> SnapshotConfig:
    """Create a development-optimized snapshot configuration"""
    return SnapshotConfig(
        # Less frequent snapshots in development
        default_event_interval=200,
        default_time_interval_hours=48,
        default_size_threshold_mb=20.0,

        # Lower performance settings
        snapshot_batch_size=5,
        enable_async_snapshots=False,  # Synchronous for easier debugging

        # Minimal retention
        keep_snapshots_count=2,
        snapshot_retention_days=7,

        # Less monitoring
        enable_snapshot_metrics=False,
        alert_on_snapshot_failure=False
    )


def create_testing_snapshot_config() -> SnapshotConfig:
    """Create a testing-optimized snapshot configuration"""
    return SnapshotConfig(
        # Very frequent snapshots for testing
        default_event_interval=10,
        default_time_interval_hours=1,
        default_size_threshold_mb=1.0,

        # Synchronous for predictability
        enable_async_snapshots=False,
        snapshot_batch_size=1,

        # Minimal retention
        keep_snapshots_count=1,
        snapshot_cleanup_enabled=False,

        # Full monitoring for tests
        enable_snapshot_metrics=True,
        log_snapshot_creation=True,
        enable_snapshot_validation=True
    )


# =============================================================================
# Validation Functions
# =============================================================================

def validate_snapshot_config(config: SnapshotConfig) -> None:
    """
    Validate snapshot configuration for common issues.

    Raises:
        ValueError: If configuration is invalid
    """
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

    if config.trading_hours_multiplier <= 0 or config.trading_hours_multiplier > 2:
        raise ValueError("trading_hours_multiplier must be between 0 and 2")

    # Validate compression type
    valid_compression = {"snappy", "gzip", "lz4", "none"}
    if config.snapshot_compression_type not in valid_compression:
        raise ValueError(f"snapshot_compression_type must be one of {valid_compression}")

    # Validate storage backend
    valid_backends = {"kafka", "s3", "redis"}
    if config.snapshot_storage_backend not in valid_backends:
        raise ValueError(f"snapshot_storage_backend must be one of {valid_backends}")

    # If using S3, bucket must be specified
    if config.snapshot_storage_backend == "s3" and not config.snapshot_s3_bucket:
        raise ValueError("snapshot_s3_bucket must be specified when using S3 backend")


# =============================================================================
# Helper Functions
# =============================================================================

def get_snapshot_interval_for_aggregate(
        config: SnapshotConfig,
        aggregate_type: str
) -> int:
    """Get the event interval for a specific aggregate type"""
    return config.aggregate_snapshot_intervals.get(
        aggregate_type,
        config.default_event_interval
    )


def get_time_interval_for_aggregate(
        config: SnapshotConfig,
        aggregate_type: str
) -> int:
    """Get the time interval (hours) for a specific aggregate type"""
    return config.aggregate_time_intervals.get(
        aggregate_type,
        config.default_time_interval_hours
    )


def get_size_threshold_for_aggregate(
        config: SnapshotConfig,
        aggregate_type: str
) -> float:
    """Get the size threshold (MB) for a specific aggregate type"""
    return config.aggregate_size_thresholds.get(
        aggregate_type,
        config.default_size_threshold_mb
    )


def should_force_snapshot(
        config: SnapshotConfig,
        aggregate_type: str,
        event_type: str,
        event_data: Dict[str, Any]
) -> bool:
    """
    Check if a snapshot should be forced based on special rules.

    Args:
        config: Snapshot configuration
        aggregate_type: Type of aggregate
        event_type: Type of event
        event_data: Event data

    Returns:
        True if snapshot should be forced
    """
    special_rules = config.aggregate_special_rules.get(aggregate_type, {})

    # Check for specific event types that force snapshots
    if aggregate_type == "Order":
        if event_type in ["OrderFilled", "OrderCancelled"] and special_rules.get("snapshot_on_fill"):
            return True

    elif aggregate_type == "Position":
        if event_type == "PositionClosed" and special_rules.get("snapshot_on_close"):
            return True

    elif aggregate_type == "BrokerAccount":
        if event_type in ["Withdrawal", "Deposit"] and special_rules.get("snapshot_on_withdrawal"):
            return True

    # Add more special rules as needed

    return False


# =============================================================================
# Environment Variable Helper
# =============================================================================

def load_snapshot_config_from_env() -> SnapshotConfig:
    """
    Load snapshot configuration from environment variables.

    Environment variables should be prefixed with SNAPSHOT_
    For example:
    - SNAPSHOT_ENABLE_AUTO_SNAPSHOTS=true
    - SNAPSHOT_DEFAULT_EVENT_INTERVAL=100
    """
    return SnapshotConfig()

# =============================================================================
# EOF
# =============================================================================