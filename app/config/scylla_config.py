# =============================================================================
# File: app/config/scylla_config.py
# Description: Configuration for ScyllaDB/Cassandra client with Pydantic v2
# =============================================================================
from typing import Optional, List, Dict, Any, Tuple, Type
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from enum import Enum


class ConsistencyLevel(str, Enum):
    """CQL Consistency levels"""
    ANY = "ANY"
    ONE = "ONE"
    TWO = "TWO"
    THREE = "THREE"
    QUORUM = "QUORUM"
    ALL = "ALL"
    LOCAL_QUORUM = "LOCAL_QUORUM"
    EACH_QUORUM = "EACH_QUORUM"
    LOCAL_ONE = "LOCAL_ONE"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    MONITOR_ONLY = "monitor_only"


# noinspection PyMethodParameters
class ScyllaConfig(BaseSettings):
    """
    Comprehensive configuration for ScyllaDB/Cassandra client.

    This configuration controls:
    - Connection settings
    - Shard awareness (ScyllaDB specific)
    - Circuit breaker behavior
    - Retry policies
    - Performance tuning
    - Monitoring and metrics
    """

    # =========================================================================
    # Connection Settings
    # =========================================================================

    contact_points: str = Field(
        default="localhost",
        description="Comma-separated list of contact points (hosts)"
    )

    port: int = Field(
        default=9042,
        description="CQL native protocol port"
    )

    shard_aware_port: int = Field(
        default=19042,
        description="ScyllaDB shard-aware port (optional)"
    )

    keyspace: str = Field(
        default="wellwon_scylla",
        description="Default keyspace to use"
    )

    # Authentication
    username: Optional[str] = Field(
        default=None,
        description="ScyllaDB username"
    )

    password: Optional[str] = Field(
        default=None,
        description="ScyllaDB password"
    )

    # =========================================================================
    # Connection Pool Settings
    # =========================================================================

    max_connections_per_host: int = Field(
        default=2,
        description="Maximum connections per host"
    )

    core_connections_per_host: int = Field(
        default=1,
        description="Minimum connections per host"
    )

    max_requests_per_connection: int = Field(
        default=256,
        description="Maximum concurrent requests per connection"
    )

    # =========================================================================
    # Timeout Settings
    # =========================================================================

    connect_timeout: float = Field(
        default=10.0,
        description="Connection timeout in seconds"
    )

    request_timeout: float = Field(
        default=30.0,
        description="Request timeout in seconds"
    )

    idle_heartbeat_interval: int = Field(
        default=30,
        description="Heartbeat interval for idle connections (seconds)"
    )

    idle_heartbeat_timeout: int = Field(
        default=5,
        description="Heartbeat timeout (seconds)"
    )

    # =========================================================================
    # Consistency Settings
    # =========================================================================

    default_consistency_read: ConsistencyLevel = Field(
        default=ConsistencyLevel.LOCAL_ONE,
        description="Default consistency level for reads"
    )

    default_consistency_write: ConsistencyLevel = Field(
        default=ConsistencyLevel.LOCAL_QUORUM,
        description="Default consistency level for writes"
    )

    # =========================================================================
    # ScyllaDB Specific (Shard Awareness)
    # =========================================================================

    shard_aware_enabled: bool = Field(
        default=True,
        description="Enable ScyllaDB shard-aware routing"
    )

    token_aware_enabled: bool = Field(
        default=True,
        description="Enable token-aware load balancing"
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

    # =========================================================================
    # SSL/TLS Configuration
    # =========================================================================

    ssl_enabled: bool = Field(
        default=False,
        description="Enable SSL/TLS"
    )

    ssl_ca_cert_path: Optional[str] = Field(
        default=None,
        description="Path to CA certificate"
    )

    ssl_client_cert_path: Optional[str] = Field(
        default=None,
        description="Path to client certificate"
    )

    ssl_client_key_path: Optional[str] = Field(
        default=None,
        description="Path to client key"
    )

    ssl_verify_mode: bool = Field(
        default=True,
        description="Verify server certificate"
    )

    # =========================================================================
    # Performance Tuning
    # =========================================================================

    protocol_version: int = Field(
        default=5,
        description="CQL protocol version"
    )

    compression_enabled: bool = Field(
        default=True,
        description="Enable compression (lz4 or snappy)"
    )

    executor_threads: int = Field(
        default=2,
        description="Number of executor threads"
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
        default="scylla",
        description="Prefix for metric names"
    )

    slow_query_threshold_ms: int = Field(
        default=50,
        description="Log queries slower than this (ms)"
    )

    # =========================================================================
    # Environment Configuration
    # =========================================================================

    model_config = {
        "env_prefix": "SCYLLA_",
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "allow"
    }

    # =========================================================================
    # Validators
    # =========================================================================

    @field_validator('contact_points')
    def validate_contact_points(cls, v):
        """Validate contact points"""
        if not v:
            raise ValueError("contact_points cannot be empty")
        return v

    @field_validator('port')
    def validate_port(cls, v):
        """Validate port range"""
        if not (1 <= v <= 65535):
            raise ValueError("port must be between 1 and 65535")
        return v

    @field_validator('max_connections_per_host')
    def validate_max_connections(cls, v):
        """Ensure max_connections is reasonable"""
        if v < 1:
            raise ValueError("max_connections_per_host must be at least 1")
        if v > 100:
            raise ValueError("max_connections_per_host should not exceed 100")
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

    def get_contact_points_list(self) -> List[str]:
        """Get contact points as a list"""
        return [p.strip() for p in self.contact_points.split(",") if p.strip()]

    def get_auth_provider_kwargs(self) -> Optional[Dict[str, str]]:
        """Get authentication provider kwargs"""
        if self.username and self.password:
            return {
                "username": self.username,
                "password": self.password
            }
        return None

    def get_ssl_context(self):
        """Get SSL context for secure connections"""
        if not self.ssl_enabled:
            return None

        import ssl
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS)

        if self.ssl_ca_cert_path:
            ssl_context.load_verify_locations(self.ssl_ca_cert_path)

        if self.ssl_verify_mode:
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        else:
            ssl_context.verify_mode = ssl.CERT_NONE

        if self.ssl_client_cert_path and self.ssl_client_key_path:
            ssl_context.load_cert_chain(
                self.ssl_client_cert_path,
                self.ssl_client_key_path
            )

        return ssl_context

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

def create_default_config() -> ScyllaConfig:
    """Create default ScyllaDB configuration"""
    return ScyllaConfig()


def create_production_config() -> ScyllaConfig:
    """Create production-optimized configuration"""
    return ScyllaConfig(
        # Larger connection pool
        max_connections_per_host=4,
        core_connections_per_host=2,

        # More aggressive circuit breaker
        circuit_failure_threshold=10,
        circuit_reset_timeout=60,

        # More retries with longer delays
        retry_max_attempts=5,
        retry_max_delay_ms=5000,

        # Enable all monitoring
        enable_metrics=True,
        slow_query_threshold_ms=100,

        # Performance tuning
        compression_enabled=True,
        executor_threads=4,
    )


def create_development_config() -> ScyllaConfig:
    """Create development-optimized configuration"""
    return ScyllaConfig(
        # Smaller connection pool
        max_connections_per_host=2,
        core_connections_per_host=1,

        # Less aggressive circuit breaker
        circuit_failure_threshold=3,
        circuit_reset_timeout=10,

        # Fewer retries
        retry_max_attempts=2,
        retry_initial_delay_ms=50,

        # More logging
        slow_query_threshold_ms=20,
    )


def create_testing_config() -> ScyllaConfig:
    """Create testing-optimized configuration"""
    return ScyllaConfig(
        # Minimal connections
        max_connections_per_host=1,
        core_connections_per_host=1,

        # Disable circuit breaker for predictability
        circuit_breaker_enabled=CircuitBreakerState.DISABLED,

        # No retries for faster failures
        retry_enabled=False,

        # Faster timeouts
        connect_timeout=5.0,
        request_timeout=10.0,
    )


# =============================================================================
# Validation Functions
# =============================================================================

def validate_config(config: ScyllaConfig) -> None:
    """
    Validate ScyllaDB configuration for common issues.

    Raises:
        ValueError: If configuration is invalid
    """
    # Connection validation
    if config.max_connections_per_host < config.core_connections_per_host:
        raise ValueError("max_connections_per_host must be >= core_connections_per_host")

    # Circuit breaker validation
    if config.circuit_failure_threshold < 1:
        raise ValueError("circuit_failure_threshold must be at least 1")

    if config.circuit_success_threshold < 1:
        raise ValueError("circuit_success_threshold must be at least 1")

    # Retry validation
    if config.retry_enabled:
        if config.retry_max_attempts < 1:
            raise ValueError("retry_max_attempts must be at least 1")

        if config.retry_initial_delay_ms < 0:
            raise ValueError("retry_initial_delay_ms cannot be negative")

        if config.retry_max_delay_ms < config.retry_initial_delay_ms:
            raise ValueError("retry_max_delay_ms must be >= retry_initial_delay_ms")


# =============================================================================
# Environment Variable Helper
# =============================================================================

def load_scylla_config_from_env() -> ScyllaConfig:
    """
    Load ScyllaDB configuration from environment variables.

    Environment variables should be prefixed with SCYLLA_
    For example:
    - SCYLLA_CONTACT_POINTS=scylla-1,scylla-2,scylla-3
    - SCYLLA_KEYSPACE=wellwon_scylla
    - SCYLLA_USERNAME=scylla
    - SCYLLA_PASSWORD=secret
    """
    return ScyllaConfig()
