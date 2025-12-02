# app/config/projection_rebuilder_config.py
# =============================================================================
# File: app/config/projection_rebuilder_config.py
# Purpose: Configuration for Projection Rebuilder Service
# UPDATED: Using BaseConfig pattern with Pydantic v2
# =============================================================================

from functools import lru_cache
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from app.common.base.base_config import BaseConfig


class ProjectionRebuilderConfig(BaseConfig):
    """Configuration for Projection Rebuilder Service"""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix='PROJECTION_REBUILDER_',
    )

    # Service enable/disable
    enabled: bool = Field(default=True, description="Enable projection rebuilder")

    # Concurrency settings
    max_concurrent_rebuilds: int = Field(default=3, description="Max concurrent rebuilds")
    worker_pool_size: int = Field(default=4, description="Worker pool size")

    # Circuit breaker settings
    enable_circuit_breaker: bool = Field(default=True, description="Enable circuit breaker")
    circuit_breaker_threshold: int = Field(default=5, description="Failure threshold")
    circuit_breaker_timeout_seconds: int = Field(default=300, description="Reset timeout")
    circuit_breaker_success_threshold: int = Field(default=2, description="Success threshold")

    # Performance settings
    enable_metrics: bool = Field(default=True, description="Enable metrics")
    checkpoint_interval: int = Field(default=30, description="Checkpoint interval (seconds)")
    batch_size: int = Field(default=1000, description="Events per batch")

    # Retry settings
    max_retry_attempts: int = Field(default=3, description="Max retry attempts")
    retry_delay_seconds: int = Field(default=5, description="Retry delay")

    # Rate limiting
    rate_limit_per_projection: int = Field(default=1000, description="Events per second")


@lru_cache(maxsize=1)
def get_projection_rebuilder_config() -> ProjectionRebuilderConfig:
    """Get projection rebuilder configuration singleton (cached)."""
    return ProjectionRebuilderConfig()


def reset_projection_rebuilder_config() -> None:
    """Reset config singleton (for testing)."""
    get_projection_rebuilder_config.cache_clear()


def is_projection_rebuilder_enabled() -> bool:
    """Check if projection rebuilder is enabled"""
    return get_projection_rebuilder_config().enabled
