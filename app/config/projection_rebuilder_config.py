# app/config/projection_rebuilder_config.py
# =============================================================================
# File: app/config/projection_rebuilder_config.py
# Purpose: Configuration for Projection Rebuilder Service
# Description: Manages settings for projection rebuilding and event replay
# =============================================================================

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProjectionRebuilderConfig:
    """Configuration for Projection Rebuilder Service"""

    # Service enable/disable
    enabled: bool = field(default_factory=lambda: os.getenv("PROJECTION_REBUILDER_ENABLED", "true").lower() == "true")

    # Concurrency settings
    max_concurrent_rebuilds: int = 3
    worker_pool_size: int = 4

    # Circuit breaker settings
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_seconds: int = 300
    circuit_breaker_success_threshold: int = 2

    # Performance settings
    enable_metrics: bool = True
    checkpoint_interval: int = 30  # Seconds between checkpoints
    batch_size: int = 1000  # Events per batch

    # Retry settings
    max_retry_attempts: int = 3
    retry_delay_seconds: int = 5

    # Rate limiting
    rate_limit_per_projection: int = 1000  # Events per second

    @classmethod
    def from_env(cls) -> "ProjectionRebuilderConfig":
        """Create config from environment variables"""
        return cls()


# Singleton instance
_rebuilder_config: Optional[ProjectionRebuilderConfig] = None


def get_projection_rebuilder_config() -> ProjectionRebuilderConfig:
    """Get or create the projection rebuilder configuration"""
    global _rebuilder_config
    if _rebuilder_config is None:
        _rebuilder_config = ProjectionRebuilderConfig.from_env()
    return _rebuilder_config


def is_projection_rebuilder_enabled() -> bool:
    """Check if projection rebuilder is enabled"""
    return get_projection_rebuilder_config().enabled