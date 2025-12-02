# =============================================================================
# File: app/config/redis_config.py
# Description: Configuration for Redis client with Pydantic v2
# UPDATED: Using BaseConfig pattern
# =============================================================================
import asyncio
from functools import lru_cache
from typing import Optional, Tuple, Type, Dict, Any
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import SettingsConfigDict
from enum import Enum

from app.common.base.base_config import BaseConfig


class RedisMode(str, Enum):
    """Redis deployment mode"""
    STANDALONE = "standalone"
    SENTINEL = "sentinel"
    CLUSTER = "cluster"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    MONITOR_ONLY = "monitor_only"  # Log but don't block


# noinspection PyMethodParameters
class RedisConfig(BaseConfig):
    """
    Comprehensive configuration for Redis client.

    This configuration controls:
    - Connection settings
    - Circuit breaker behavior
    - Retry policies
    - Performance tuning
    - Monitoring and metrics
    """

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix='REDIS_',
    )

    # =========================================================================
    # Connection Settings
    # =========================================================================

    redis_url: str = Field(
        default="redis://localhost:6379/1",
        description="Redis connection URL (db 1 for WellWon)"
    )

    redis_mode: RedisMode = Field(
        default=RedisMode.STANDALONE,
        description="Redis deployment mode"
    )

    # Sentinel settings (only used if mode is SENTINEL)
    sentinel_hosts: Optional[str] = Field(
        default=None,
        description="Comma-separated list of sentinel hosts (host:port)"
    )

    sentinel_master_name: str = Field(
        default="mymaster",
        description="Sentinel master name"
    )

    # Connection pool settings
    max_connections: int = Field(
        default=50,
        description="Maximum number of connections in the pool"
    )

    min_idle_connections: int = Field(
        default=10,
        description="Minimum idle connections to maintain"
    )

    # Socket settings
    socket_timeout: float = Field(
        default=15.0,
        description="Socket timeout in seconds"
    )

    socket_connect_timeout: float = Field(
        default=5.0,
        description="Socket connection timeout in seconds"
    )

    socket_keepalive: bool = Field(
        default=True,
        description="Enable TCP keepalive"
    )

    socket_keepalive_interval: int = Field(
        default=60,
        description="TCP keepalive interval in seconds"
    )

    # =========================================================================
    # Circuit Breaker Configuration
    # =========================================================================

    circuit_breaker_enabled: CircuitBreakerState = Field(
        default=CircuitBreakerState.ENABLED,
        description="Circuit breaker state"
    )

    circuit_failure_threshold: int = Field(
        default=5,
        description="Number of failures before opening circuit"
    )

    circuit_reset_timeout: int = Field(
        default=30,
        description="Seconds before attempting to close circuit"
    )

    circuit_half_open_max_calls: int = Field(
        default=3,
        description="Max calls allowed in half-open state"
    )

    circuit_success_threshold: int = Field(
        default=3,
        description="Successes needed to close circuit"
    )

    # =========================================================================
    # Retry Configuration
    # =========================================================================

    retry_enabled: bool = Field(
        default=True,
        description="Enable automatic retries"
    )

    retry_max_attempts: int = Field(
        default=3,
        description="Maximum retry attempts"
    )

    retry_initial_delay_ms: int = Field(
        default=100,
        description="Initial retry delay in milliseconds"
    )

    retry_max_delay_ms: int = Field(
        default=2000,
        description="Maximum retry delay in milliseconds"
    )

    retry_backoff_factor: float = Field(
        default=2.0,
        description="Exponential backoff multiplier"
    )

    retry_jitter: bool = Field(
        default=True,
        description="Add random jitter to retry delays"
    )

    # Retry on specific errors
    retry_on_timeout: bool = Field(
        default=True,
        description="Retry on timeout errors"
    )

    retry_on_connection_error: bool = Field(
        default=True,
        description="Retry on connection errors"
    )

    # =========================================================================
    # Performance Tuning
    # =========================================================================

    decode_responses: bool = Field(
        default=True,
        description="Automatically decode responses to strings"
    )

    connection_pool_class: Optional[str] = Field(
        default=None,
        description="Custom connection pool class"
    )

    # Response caching
    enable_client_cache: bool = Field(
        default=False,
        description="Enable client-side caching (Redis 6+)"
    )

    client_cache_max_size: int = Field(
        default=10000,
        description="Max items in client cache"
    )

    # Pipeline settings
    pipeline_transaction_default: bool = Field(
        default=False,
        description="Use transactions by default in pipelines"
    )

    # =========================================================================
    # Health Check and Monitoring
    # =========================================================================

    health_check_interval: int = Field(
        default=30,
        description="Seconds between health checks"
    )

    enable_metrics: bool = Field(
        default=True,
        description="Enable metrics collection"
    )

    metrics_prefix: str = Field(
        default="redis",
        description="Prefix for metric names"
    )

    # Performance monitoring (industry standard: <1ms optimal, alert at 5-10ms)
    slow_command_threshold_ms: int = Field(
        default=5,
        description="Log commands slower than this (ms) - industry standard 5ms"
    )

    # =========================================================================
    # Pub/Sub Configuration
    # =========================================================================

    pubsub_ignore_subscribe_messages: bool = Field(
        default=True,
        description="Ignore subscribe/unsubscribe messages"
    )

    pubsub_decode_responses: bool = Field(
        default=True,
        description="Decode pub/sub messages"
    )

    # =========================================================================
    # Stream Configuration
    # =========================================================================

    stream_default_maxlen: int = Field(
        default=1000,
        description="Default max length for streams"
    )

    stream_approximate_maxlen: bool = Field(
        default=True,
        description="Use approximate maxlen for better performance"
    )

    # =========================================================================
    # Security
    # =========================================================================

    redis_password: Optional[SecretStr] = Field(
        default=None,
        description="Redis password"
    )

    redis_username: Optional[str] = Field(
        default=None,
        description="Redis username (Redis 6+)"
    )

    ssl_enabled: bool = Field(
        default=False,
        description="Enable SSL/TLS"
    )

    ssl_certfile: Optional[str] = Field(
        default=None,
        description="SSL certificate file"
    )

    ssl_keyfile: Optional[str] = Field(
        default=None,
        description="SSL key file"
    )

    ssl_ca_certs: Optional[str] = Field(
        default=None,
        description="SSL CA certificates file"
    )

    # =========================================================================
    # Validators
    # =========================================================================

    @field_validator('redis_url')
    def validate_redis_url(cls, v):
        """Validate Redis URL format"""
        if not v:
            raise ValueError("redis_url cannot be empty")
        if not v.startswith(('redis://', 'rediss://', 'unix://')):
            raise ValueError("redis_url must start with redis://, rediss://, or unix://")
        return v

    @field_validator('max_connections')
    def validate_max_connections(cls, v):
        """Ensure max_connections is reasonable"""
        if v < 1:
            raise ValueError("max_connections must be at least 1")
        if v > 1000:
            raise ValueError("max_connections should not exceed 1000")
        return v

    @field_validator('retry_backoff_factor')
    def validate_backoff_factor(cls, v):
        """Ensure backoff factor is reasonable"""
        if v < 1.0:
            raise ValueError("retry_backoff_factor must be at least 1.0")
        if v > 10.0:
            raise ValueError("retry_backoff_factor should not exceed 10.0")
        return v

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def get_connection_kwargs(self) -> Dict[str, Any]:
        """Get kwargs for Redis connection"""
        kwargs = {
            'decode_responses': self.decode_responses,
            'socket_timeout': self.socket_timeout,
            'socket_connect_timeout': self.socket_connect_timeout,
            'socket_keepalive': self.socket_keepalive,
            'max_connections': self.max_connections,
        }

        if self.redis_password:
            kwargs['password'] = self.redis_password.get_secret_value()

        if self.redis_username:
            kwargs['username'] = self.redis_username

        if self.ssl_enabled:
            kwargs['ssl'] = True
            if self.ssl_certfile:
                kwargs['ssl_certfile'] = self.ssl_certfile
            if self.ssl_keyfile:
                kwargs['ssl_keyfile'] = self.ssl_keyfile
            if self.ssl_ca_certs:
                kwargs['ssl_ca_certs'] = self.ssl_ca_certs

        return kwargs

    def get_socket_keepalive_options(self) -> Dict[int, int]:
        """Get socket keepalive options"""
        import socket

        keepalive_opts = {}
        if self.socket_keepalive and self.socket_keepalive_interval > 0:
            if hasattr(socket, "TCP_KEEPIDLE"):
                keepalive_opts[socket.TCP_KEEPIDLE] = self.socket_keepalive_interval
            if hasattr(socket, "TCP_KEEPINTVL"):
                keepalive_opts[socket.TCP_KEEPINTVL] = max(1, self.socket_keepalive_interval // 3)
            if hasattr(socket, "TCP_KEEPCNT"):
                keepalive_opts[socket.TCP_KEEPCNT] = 3

        return keepalive_opts

    def get_retry_exceptions(self) -> Tuple[Type[Exception], ...]:
        """Get exceptions that should trigger retries"""
        from redis.exceptions import (
            RedisError, ConnectionError as RedisConnectionError,
            TimeoutError, ResponseError
        )

        exceptions = []

        if self.retry_on_connection_error:
            exceptions.extend([RedisConnectionError, ConnectionError, OSError])

        if self.retry_on_timeout:
            exceptions.extend([TimeoutError, asyncio.TimeoutError])

        # Always retry on these
        exceptions.append(RedisError)

        return tuple(set(exceptions))

    def should_use_circuit_breaker(self) -> bool:
        """Check if circuit breaker should be active"""
        return self.circuit_breaker_enabled in (
            CircuitBreakerState.ENABLED,
            CircuitBreakerState.MONITOR_ONLY
        )

    def is_circuit_breaker_blocking(self) -> bool:
        """Check if circuit breaker should block requests"""
        return self.circuit_breaker_enabled == CircuitBreakerState.ENABLED


# =============================================================================
# Factory Functions
# =============================================================================

def create_default_config() -> RedisConfig:
    """Create default Redis configuration"""
    return RedisConfig()


def create_production_config() -> RedisConfig:
    """Create production-optimized configuration"""
    return RedisConfig(
        # Larger connection pool
        max_connections=100,
        min_idle_connections=20,

        # More aggressive circuit breaker
        circuit_failure_threshold=10,
        circuit_reset_timeout=60,

        # More retries with longer delays
        retry_max_attempts=5,
        retry_max_delay_ms=5000,

        # Enable all monitoring
        enable_metrics=True,
        slow_command_threshold_ms=50,

        # Performance tuning
        enable_client_cache=True,
        client_cache_max_size=50000,
    )


def create_development_config() -> RedisConfig:
    """Create development-optimized configuration"""
    return RedisConfig(
        # Smaller connection pool
        max_connections=20,
        min_idle_connections=5,

        # Less aggressive circuit breaker
        circuit_failure_threshold=3,
        circuit_reset_timeout=10,

        # Fewer retries
        retry_max_attempts=2,
        retry_initial_delay_ms=50,

        # More logging
        slow_command_threshold_ms=10,
    )


def create_testing_config() -> RedisConfig:
    """Create testing-optimized configuration"""
    return RedisConfig(
        # Minimal connections
        max_connections=10,
        min_idle_connections=1,

        # Disable circuit breaker for predictability
        circuit_breaker_enabled=CircuitBreakerState.DISABLED,

        # No retries for faster failures
        retry_enabled=False,

        # Faster timeouts
        socket_timeout=5.0,
        socket_connect_timeout=2.0,
    )


# =============================================================================
# Validation Functions
# =============================================================================

def validate_config(config: RedisConfig) -> None:
    """
    Validate Redis configuration for common issues.

    Raises:
        ValueError: If configuration is invalid
    """
    # Connection validation
    if config.max_connections < config.min_idle_connections:
        raise ValueError("max_connections must be >= min_idle_connections")

    # Circuit breaker validation
    if config.circuit_failure_threshold < 1:
        raise ValueError("circuit_failure_threshold must be at least 1")

    if config.circuit_success_threshold < 1:
        raise ValueError("circuit_success_threshold must be at least 1")

    if config.circuit_half_open_max_calls < 1:
        raise ValueError("circuit_half_open_max_calls must be at least 1")

    # Retry validation
    if config.retry_enabled:
        if config.retry_max_attempts < 1:
            raise ValueError("retry_max_attempts must be at least 1")

        if config.retry_initial_delay_ms < 0:
            raise ValueError("retry_initial_delay_ms cannot be negative")

        if config.retry_max_delay_ms < config.retry_initial_delay_ms:
            raise ValueError("retry_max_delay_ms must be >= retry_initial_delay_ms")

    # Sentinel validation
    if config.redis_mode == RedisMode.SENTINEL:
        if not config.sentinel_hosts:
            raise ValueError("sentinel_hosts required for SENTINEL mode")


# =============================================================================
# Factory Function
# =============================================================================

@lru_cache(maxsize=1)
def get_redis_config() -> RedisConfig:
    """Get Redis configuration singleton (cached)."""
    return RedisConfig()


def reset_redis_config() -> None:
    """Reset config singleton (for testing)."""
    get_redis_config.cache_clear()