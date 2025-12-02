# app/config/saga_config.py
"""
Centralized configuration for all saga-related settings.
Replaces individual environment variables with a clean, maintainable config.
UPDATED: Using Pydantic v2 with BaseConfig pattern
"""

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from datetime import timedelta

from app.common.base.base_config import BaseConfig, BASE_CONFIG_DICT


class SagaConfig(BaseConfig):
    """
    Saga configuration with sensible defaults.
    Only the essential parameters that might need tuning.
    Updated for Pydantic v2 with BaseConfig pattern.
    """

    model_config = SettingsConfigDict(
        **BASE_CONFIG_DICT,
        env_prefix='SAGA_',
    )

    # =========================================================================
    # CORE SAGA SETTINGS
    # =========================================================================

    # Global defaults
    default_timeout_seconds: int = Field(
        default=60,
        description="Default timeout for sagas in seconds"
    )
    default_retry_count: int = Field(
        default=3,
        description="Default number of retries for saga steps"
    )
    default_retry_delay_seconds: float = Field(
        default=1.0,
        description="Default delay between retries in seconds"
    )

    # Virtual broker acceleration factor
    virtual_broker_speed_factor: float = Field(
        default=0.1,
        description="Speed multiplier for virtual brokers (0.1 = 10x faster)"
    )

    # =========================================================================
    # SAGA-SPECIFIC TIMEOUTS (in seconds)
    # =========================================================================

    # Connection/Disconnection timeouts
    connection_timeout: int = Field(
        default=30,
        description="Timeout for broker connection saga"
    )
    disconnection_timeout: int = Field(
        default=120,
        description="Timeout for broker disconnection saga"
    )

    # User operations timeout
    user_deletion_timeout: int = Field(
        default=180,
        description="Timeout for user deletion saga (3 minutes)"
    )

    # Recovery operations timeout
    account_recovery_timeout: int = Field(
        default=300,
        description="Timeout for account recovery saga (5 minutes)"
    )

    # Order execution timeout
    order_execution_timeout: int = Field(
        default=90,
        description="Timeout for order execution saga (90 seconds)"
    )

    # =========================================================================
    # CONCURRENCY & LOCKING
    # =========================================================================

    # Lock TTLs (in seconds)
    saga_lock_ttl: int = Field(
        default=300,
        description="Default TTL for saga aggregate locks"
    )
    virtual_broker_lock_ttl: int = Field(
        default=30,
        description="Shorter TTL for virtual broker locks"
    )

    # Race condition prevention
    connection_conflict_window_seconds: float = Field(
        default=0.5,
        description="Time window to detect conflicting connection events"
    )
    disconnection_grace_period_seconds: float = Field(
        default=1.0,
        description="Grace period before processing disconnection"
    )

    # =========================================================================
    # SMART RETRY & PENDING QUEUE
    # =========================================================================

    # Pending saga queue
    pending_queue_enabled: bool = Field(
        default=True,
        description="Enable smart retry with pending queue"
    )
    pending_queue_check_interval_seconds: float = Field(
        default=0.5,
        description="How often to check pending saga queue"
    )
    pending_saga_max_age_seconds: int = Field(
        default=300,
        description="Maximum time a saga can wait in pending queue"
    )
    pending_saga_max_retries: int = Field(
        default=5,
        description="Maximum retry attempts from pending queue"
    )

    # =========================================================================
    # MONITORING & CLEANUP
    # =========================================================================

    # Cleanup settings
    cleanup_interval_seconds: int = Field(
        default=60,
        description="How often to run cleanup tasks"
    )
    event_tracker_retention_minutes: int = Field(
        default=5,
        description="How long to keep event tracking data"
    )
    stale_lock_check_enabled: bool = Field(
        default=True,
        description="Enable checking for stale locks"
    )

    # Stale saga detection (DEADLOCK FIX Nov 16, 2025)
    stale_saga_detection_enabled: bool = Field(
        default=True,
        description="Enable detection and cleanup of stale sagas blocking reconnection for ALL brokers"
    )
    stale_saga_timeout_threshold_seconds: int = Field(
        default=120,
        description="Consider a saga stale if locked for longer than this (2x default timeout = 120s)"
    )

    # =========================================================================
    # PERFORMANCE OPTIMIZATIONS
    # =========================================================================

    # Delays and optimizations
    cold_start_delay_ms: int = Field(
        default=0,
        description="PERFORMANCE FIX (Nov 12, 2025): Removed cold start delay (was 100ms) - SYNC events need instant saga triggering"
    )
    virtual_broker_cold_start_delay_ms: int = Field(
        default=0,
        description="PERFORMANCE FIX (Nov 12, 2025): Removed cold start delay (was 25ms) - SYNC events need instant saga triggering"
    )

    # Event propagation wait times
    event_propagation_wait_seconds: float = Field(
        default=1.5,
        description="Time to wait for event propagation"
    )
    virtual_broker_event_wait_seconds: float = Field(
        default=0.15,
        description="OPTIMIZED: Reduced wait for virtual broker events (SYNC projections complete in <500ms, PostgreSQL commit: 50-150ms)"
    )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def get_timeout_for_saga(self, saga_type: str, is_virtual: bool = False) -> timedelta:
        """Get timeout for specific saga type with virtual broker optimization"""

        # Map saga types to their specific timeouts
        timeout_map = {
            "BrokerConnectionSaga": self.connection_timeout,
            "BrokerDisconnectionSaga": self.disconnection_timeout,
            "UserDeletionSaga": self.user_deletion_timeout,
            "AccountRecoverySaga": self.account_recovery_timeout,
            "OrderExecutionSaga": self.order_execution_timeout,
        }

        # Get base timeout or use default
        base_timeout = timeout_map.get(saga_type, self.default_timeout_seconds)

        # Apply virtual broker acceleration
        if is_virtual:
            timeout = int(base_timeout * self.virtual_broker_speed_factor)
            # Ensure minimum timeout of 5 seconds
            timeout = max(timeout, 5)
        else:
            timeout = base_timeout

        return timedelta(seconds=timeout)

    def get_lock_ttl(self, is_virtual: bool = False) -> int:
        """Get lock TTL based on broker type"""
        return self.virtual_broker_lock_ttl if is_virtual else self.saga_lock_ttl

    def get_cold_start_delay_ms(self, is_virtual: bool = False) -> int:
        """Get cold start delay based on broker type"""
        return self.virtual_broker_cold_start_delay_ms if is_virtual else self.cold_start_delay_ms

    def get_event_wait_time(self, is_virtual: bool = False) -> float:
        """Get event propagation wait time based on broker type"""
        return self.virtual_broker_event_wait_seconds if is_virtual else self.event_propagation_wait_seconds


@lru_cache(maxsize=1)
def get_saga_config() -> SagaConfig:
    """Get saga configuration singleton (cached)."""
    return SagaConfig()


# Export for convenience
saga_config = get_saga_config()