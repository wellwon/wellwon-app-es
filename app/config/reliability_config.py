# =============================================================================
# File: app/config/reliability_config.py
# Description: Unified reliability configuration for circuit breakers, retry
#              patterns, rate limiting, and distributed locking
# UPDATED: Using BaseConfig pattern with Pydantic v2
# =============================================================================

import os
from functools import lru_cache
from typing import Optional, Callable
from enum import Enum, auto
from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict

from app.common.base.base_config import BaseConfig


# =============================================================================
# Configuration Models (Pydantic BaseModel for type safety)
# =============================================================================

class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration."""
    name: str
    failure_threshold: int = 5
    success_threshold: int = 3
    reset_timeout_seconds: int = 30
    half_open_max_calls: int = 3
    window_size: Optional[int] = None
    failure_rate_threshold: Optional[float] = None
    timeout_seconds: Optional[float] = None


class RetryConfig(BaseModel):
    """Retry configuration."""
    max_attempts: int = 3
    initial_delay_ms: int = 100
    max_delay_ms: int = 10000
    backoff_factor: float = 2.0
    jitter: bool = True
    exponential_base: Optional[float] = None
    jitter_type: str = "full"

    class Config:
        arbitrary_types_allowed = True


class RateLimiterConfig(BaseModel):
    """Rate limiter configuration."""
    algorithm: str = "token_bucket"
    capacity: int = 100
    refill_rate: float = 10.0
    distributed: bool = True
    max_requests: Optional[int] = None
    time_window: Optional[int] = None


class DistributedLockConfig(BaseModel):
    """Distributed lock configuration."""
    namespace: str = "distributed_lock"
    ttl_seconds: int = 30
    max_wait_ms: int = 5000
    retry_times: int = 3
    retry_delay_ms: int = 100
    strategy: str = "wait_with_timeout"
    enable_metrics: bool = True
    enable_auto_cleanup: bool = True
    use_lua_scripts: bool = True
    stale_lock_multiplier: float = 2.0
    use_backoff: Optional[bool] = None


class ReliabilityConfigBundle(BaseModel):
    """Combined configuration for circuit breaker, retry, rate limiter, and distributed lock"""
    circuit_breaker: CircuitBreakerConfig
    retry: Optional[RetryConfig] = None
    rate_limiter: Optional[RateLimiterConfig] = None
    distributed_lock: Optional[DistributedLockConfig] = None


class ErrorClass(Enum):
    """Error classification for retry decisions"""
    UNKNOWN = auto()
    NETWORK = auto()
    TIMEOUT = auto()
    LOGICAL = auto()
    TRANSIENT = auto()
    PERMANENT = auto()


# =============================================================================
# Main Reliability Config (loads from env)
# =============================================================================

class ReliabilitySettings(BaseConfig):
    """
    Global reliability settings loaded from environment.
    Individual service configs are created via ReliabilityConfigs factory.
    """

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix='RELIABILITY_',
    )

    # Global defaults
    default_circuit_breaker_threshold: int = Field(default=5)
    default_circuit_breaker_timeout: int = Field(default=30)
    default_retry_max_attempts: int = Field(default=3)
    default_retry_initial_delay_ms: int = Field(default=100)
    default_rate_limit_capacity: int = Field(default=100)

    # Feature flags
    enable_circuit_breakers: bool = Field(default=True)
    enable_retries: bool = Field(default=True)
    enable_rate_limiting: bool = Field(default=True)
    enable_distributed_locks: bool = Field(default=True)


@lru_cache(maxsize=1)
def get_reliability_settings() -> ReliabilitySettings:
    """Get global reliability settings (cached)."""
    return ReliabilitySettings()


def reset_reliability_settings() -> None:
    """Reset settings singleton (for testing)."""
    get_reliability_settings.cache_clear()


# =============================================================================
# Helper Functions
# =============================================================================

def _detect_multi_worker_server() -> bool:
    """Detect if running under multi-worker server"""
    if 'granian' in os.environ.get('SERVER_SOFTWARE', '').lower():
        return True
    if os.environ.get('WEB_CONCURRENCY'):
        try:
            workers = int(os.environ.get('WEB_CONCURRENCY', '1'))
            if workers > 1:
                return True
        except ValueError:
            pass
    try:
        import psutil
        current_process = psutil.Process()
        cmdline = ' '.join(current_process.cmdline())
        if 'granian' in cmdline:
            return True
    except (ImportError, Exception):
        pass
    return False


def _get_worker_count() -> int:
    """Get estimated worker count"""
    if workers := os.environ.get('GUNICORN_WORKERS'):
        return int(workers)
    if workers := os.environ.get('WEB_CONCURRENCY'):
        return int(workers)
    return 1


def _detect_pool_pressure() -> str:
    """Detect pool pressure level"""
    worker_count = _get_worker_count()
    max_pool = int(os.environ.get('PG_POOL_MAX_SIZE', '20'))
    total_connections = worker_count * max_pool
    if total_connections > 80:
        return "high"
    elif total_connections > 40:
        return "medium"
    return "low"


# =============================================================================
# ReliabilityConfigs Factory Class
# =============================================================================

class ReliabilityConfigs:
    """Pre-configured reliability settings for different services"""

    # =========================================================================
    # Kafka/RedPanda
    # =========================================================================
    @staticmethod
    def kafka_circuit_breaker(name: str) -> CircuitBreakerConfig:
        return CircuitBreakerConfig(
            name=f"kafka_{name}",
            failure_threshold=5,
            reset_timeout_seconds=30,
            half_open_max_calls=3,
            success_threshold=3
        )

    @staticmethod
    def kafka_retry() -> RetryConfig:
        return RetryConfig(
            max_attempts=3,
            initial_delay_ms=100,
            max_delay_ms=10000,
            backoff_factor=2.0,
            jitter=True
        )

    @staticmethod
    def kafka_rate_limiter() -> RateLimiterConfig:
        return RateLimiterConfig(
            algorithm="token_bucket",
            capacity=1000,
            refill_rate=100.0,
            distributed=True
        )

    # =========================================================================
    # Redis
    # =========================================================================
    @staticmethod
    def redis_circuit_breaker(name: str) -> CircuitBreakerConfig:
        return CircuitBreakerConfig(
            name=f"redis_{name}",
            failure_threshold=3,
            reset_timeout_seconds=15,
            half_open_max_calls=3,
            success_threshold=2
        )

    @staticmethod
    def redis_retry() -> RetryConfig:
        return RetryConfig(
            max_attempts=3,
            initial_delay_ms=50,
            max_delay_ms=1000,
            backoff_factor=2.0,
            jitter=True
        )

    @staticmethod
    def redis_rate_limiter() -> RateLimiterConfig:
        return RateLimiterConfig(
            algorithm="token_bucket",
            capacity=5000,
            refill_rate=500.0,
            distributed=False
        )

    # =========================================================================
    # PostgreSQL
    # =========================================================================
    @staticmethod
    def postgres_circuit_breaker(name: str) -> CircuitBreakerConfig:
        is_multi_worker = _detect_multi_worker_server()
        if is_multi_worker:
            return CircuitBreakerConfig(
                name=f"postgres_{name}",
                failure_threshold=10,
                reset_timeout_seconds=60,
                half_open_max_calls=5,
                success_threshold=3,
                window_size=20,
                failure_rate_threshold=0.5
            )
        return CircuitBreakerConfig(
            name=f"postgres_{name}",
            failure_threshold=5,
            reset_timeout_seconds=30,
            half_open_max_calls=3,
            success_threshold=3
        )

    @staticmethod
    def postgres_retry() -> RetryConfig:
        pool_pressure = _detect_pool_pressure()
        if pool_pressure == "high":
            return RetryConfig(
                max_attempts=5,
                initial_delay_ms=50,
                max_delay_ms=2000,
                backoff_factor=1.5,
                jitter=True,
                jitter_type="full"
            )
        return RetryConfig(
            max_attempts=3,
            initial_delay_ms=100,
            max_delay_ms=5000,
            backoff_factor=2.0,
            jitter=True
        )

    @staticmethod
    def postgres_pool_acquisition_retry() -> RetryConfig:
        return RetryConfig(
            max_attempts=10,
            initial_delay_ms=10,
            max_delay_ms=500,
            backoff_factor=1.2,
            jitter=True,
            jitter_type="decorrelated"
        )

    @staticmethod
    def postgres_deadlock_retry() -> RetryConfig:
        return RetryConfig(
            max_attempts=5,
            initial_delay_ms=0,
            max_delay_ms=100,
            backoff_factor=1.5,
            jitter=True
        )

    @staticmethod
    def postgres_rate_limiter() -> RateLimiterConfig:
        worker_count = _get_worker_count()
        base_capacity = 100
        capacity = base_capacity // max(1, worker_count)
        return RateLimiterConfig(
            algorithm="token_bucket",
            capacity=capacity,
            refill_rate=capacity / 10.0,
            distributed=True
        )

    # =========================================================================
    # Broker API
    # =========================================================================
    @staticmethod
    def broker_api_circuit_breaker(broker_id: str) -> CircuitBreakerConfig:
        return CircuitBreakerConfig(
            name=f"broker_{broker_id}_api",
            failure_threshold=5,
            reset_timeout_seconds=60,
            half_open_max_calls=2,
            success_threshold=3,
            window_size=20,
            failure_rate_threshold=0.5
        )

    @staticmethod
    def broker_api_retry() -> RetryConfig:
        return RetryConfig(
            max_attempts=3,
            initial_delay_ms=500,
            max_delay_ms=30000,
            backoff_factor=2.0,
            jitter=True,
            jitter_type="full"
        )

    @staticmethod
    def broker_api_rate_limiter(broker_id: str) -> RateLimiterConfig:
        broker_limits = {
            "alpaca": {"capacity": 200, "refill_rate": 10.0},
            "interactive_brokers": {"capacity": 50, "refill_rate": 1.0},
            "td_ameritrade": {"capacity": 120, "refill_rate": 2.0},
            "schwab": {"capacity": 100, "refill_rate": 2.0},
            "etrade": {"capacity": 100, "refill_rate": 2.0},
        }
        limits = broker_limits.get(broker_id, {"capacity": 100, "refill_rate": 1.0})
        return RateLimiterConfig(
            algorithm="token_bucket",
            capacity=limits["capacity"],
            refill_rate=limits["refill_rate"],
            distributed=True
        )

    # =========================================================================
    # WSE (WebSocket Event System)
    # =========================================================================
    @staticmethod
    def wse_circuit_breaker(conn_id: str = "default") -> CircuitBreakerConfig:
        return CircuitBreakerConfig(
            name=f"wse_{conn_id}",
            failure_threshold=10,
            success_threshold=3,
            reset_timeout_seconds=30,
            half_open_max_calls=5,
            window_size=50,
            failure_rate_threshold=0.3
        )

    @staticmethod
    def wse_rate_limiter() -> RateLimiterConfig:
        return RateLimiterConfig(
            algorithm="token_bucket",
            capacity=1000,
            refill_rate=100.0,
            distributed=False
        )

    @staticmethod
    def wse_user_rate_limiter(is_premium: bool = False) -> RateLimiterConfig:
        if is_premium:
            return RateLimiterConfig(capacity=5000, refill_rate=500.0, distributed=False)
        return RateLimiterConfig(capacity=1000, refill_rate=100.0, distributed=False)

    @staticmethod
    def wse_ip_rate_limiter() -> RateLimiterConfig:
        return RateLimiterConfig(capacity=10000, refill_rate=1000.0, distributed=False)

    @staticmethod
    def wse_reliability() -> ReliabilityConfigBundle:
        return ReliabilityConfigBundle(
            circuit_breaker=ReliabilityConfigs.wse_circuit_breaker(),
            retry=None,
            rate_limiter=ReliabilityConfigs.wse_rate_limiter()
        )

    # =========================================================================
    # Distributed Locks
    # =========================================================================
    @staticmethod
    def event_store_distributed_lock() -> DistributedLockConfig:
        return DistributedLockConfig(
            namespace="aggregate_lock",
            ttl_seconds=30,
            max_wait_ms=5000,
            retry_times=100,
            retry_delay_ms=50,
            strategy="wait_with_timeout",
            enable_auto_cleanup=True,
            stale_lock_multiplier=2.0
        )

    @staticmethod
    def event_bus_distributed_lock() -> DistributedLockConfig:
        return DistributedLockConfig(
            namespace="event_bus:message",
            ttl_seconds=10,
            max_wait_ms=1000,
            retry_times=3,
            retry_delay_ms=100,
            strategy="fail_fast",
            enable_metrics=True
        )

    @staticmethod
    def adapter_pool_distributed_lock() -> DistributedLockConfig:
        return DistributedLockConfig(
            namespace="adapter_pool:lock",
            ttl_seconds=30,
            max_wait_ms=10000,
            retry_times=3,
            retry_delay_ms=100,
            strategy="exponential_backoff",
            use_backoff=True,
            enable_metrics=True
        )

    @staticmethod
    def cache_distributed_lock() -> DistributedLockConfig:
        return DistributedLockConfig(
            namespace="cache:lock",
            ttl_seconds=5,
            max_wait_ms=1000,
            retry_times=5,
            retry_delay_ms=50,
            strategy="wait_with_timeout"
        )

    @staticmethod
    def saga_distributed_lock() -> DistributedLockConfig:
        return DistributedLockConfig(
            namespace="saga:execution",
            ttl_seconds=60,
            max_wait_ms=30000,
            retry_times=10,
            retry_delay_ms=200,
            strategy="exponential_backoff"
        )

    @staticmethod
    def schema_init_lock() -> DistributedLockConfig:
        return DistributedLockConfig(
            namespace="db:schema_init",
            ttl_seconds=60,
            max_wait_ms=120000,
            retry_delay_ms=500,
            retry_times=240,
            strategy="wait_with_timeout",
            use_lua_scripts=True,
            enable_metrics=True
        )

    # =========================================================================
    # Combined Configurations
    # =========================================================================
    @staticmethod
    def event_store_reliability() -> ReliabilityConfigBundle:
        return ReliabilityConfigBundle(
            circuit_breaker=ReliabilityConfigs.kafka_circuit_breaker("event_store"),
            retry=ReliabilityConfigs.kafka_retry(),
            rate_limiter=ReliabilityConfigs.kafka_rate_limiter(),
            distributed_lock=ReliabilityConfigs.event_store_distributed_lock()
        )

    @staticmethod
    def event_bus_reliability() -> ReliabilityConfigBundle:
        return ReliabilityConfigBundle(
            circuit_breaker=ReliabilityConfigs.kafka_circuit_breaker("event_bus"),
            retry=ReliabilityConfigs.kafka_retry(),
            rate_limiter=ReliabilityConfigs.kafka_rate_limiter(),
            distributed_lock=ReliabilityConfigs.event_bus_distributed_lock()
        )

    @staticmethod
    def cache_reliability() -> ReliabilityConfigBundle:
        return ReliabilityConfigBundle(
            circuit_breaker=ReliabilityConfigs.redis_circuit_breaker("cache"),
            retry=ReliabilityConfigs.redis_retry(),
            rate_limiter=ReliabilityConfigs.redis_rate_limiter(),
            distributed_lock=ReliabilityConfigs.cache_distributed_lock()
        )

    @staticmethod
    def database_reliability() -> ReliabilityConfigBundle:
        return ReliabilityConfigBundle(
            circuit_breaker=ReliabilityConfigs.postgres_circuit_breaker("main_db"),
            retry=ReliabilityConfigs.postgres_retry(),
            rate_limiter=ReliabilityConfigs.postgres_rate_limiter()
        )

    @staticmethod
    def broker_reliability(broker_id: str) -> ReliabilityConfigBundle:
        return ReliabilityConfigBundle(
            circuit_breaker=ReliabilityConfigs.broker_api_circuit_breaker(broker_id),
            retry=ReliabilityConfigs.broker_api_retry(),
            rate_limiter=ReliabilityConfigs.broker_api_rate_limiter(broker_id),
            distributed_lock=ReliabilityConfigs.adapter_pool_distributed_lock()
        )

    # =========================================================================
    # Connection Recovery
    # =========================================================================
    @staticmethod
    def connection_recovery_circuit_breaker(broker_id: str) -> CircuitBreakerConfig:
        return CircuitBreakerConfig(
            name=f"{broker_id}_recovery",
            failure_threshold=5,
            success_threshold=3,
            reset_timeout_seconds=30,
            timeout_seconds=30,
            half_open_max_calls=3,
            window_size=10,
            failure_rate_threshold=0.5
        )

    @staticmethod
    def connection_recovery_retry() -> RetryConfig:
        return RetryConfig(
            max_attempts=3,
            initial_delay_ms=100,
            max_delay_ms=30000,
            backoff_factor=2.0,
            exponential_base=2.0,
            jitter=True,
            jitter_type="full"
        )

    @staticmethod
    def connection_recovery_rate_limiter() -> RateLimiterConfig:
        return RateLimiterConfig(
            algorithm="token_bucket",
            capacity=100,
            refill_rate=10.0,
            distributed=True
        )

    # =========================================================================
    # Telegram
    # =========================================================================
    @staticmethod
    def telegram_circuit_breaker() -> CircuitBreakerConfig:
        return CircuitBreakerConfig(
            name="telegram_api",
            failure_threshold=5,
            success_threshold=2,
            reset_timeout_seconds=60,
            half_open_max_calls=3,
            window_size=20,
            failure_rate_threshold=0.5
        )

    @staticmethod
    def telegram_retry() -> RetryConfig:
        return RetryConfig(
            max_attempts=3,
            initial_delay_ms=1000,
            max_delay_ms=60000,
            backoff_factor=2.0,
            jitter=True,
            jitter_type="full"
        )

    @staticmethod
    def telegram_global_rate_limiter() -> RateLimiterConfig:
        return RateLimiterConfig(capacity=60, refill_rate=30.0, distributed=True)

    @staticmethod
    def telegram_per_chat_rate_limiter() -> RateLimiterConfig:
        return RateLimiterConfig(capacity=3, refill_rate=1.0, distributed=False)

    @staticmethod
    def telegram_per_group_rate_limiter() -> RateLimiterConfig:
        return RateLimiterConfig(
            algorithm="sliding_window",
            capacity=20,
            time_window=60,
            distributed=False
        )

    @staticmethod
    def telegram_reliability() -> ReliabilityConfigBundle:
        return ReliabilityConfigBundle(
            circuit_breaker=ReliabilityConfigs.telegram_circuit_breaker(),
            retry=ReliabilityConfigs.telegram_retry(),
            rate_limiter=ReliabilityConfigs.telegram_global_rate_limiter()
        )

    # =========================================================================
    # Storage (MinIO/S3)
    # =========================================================================
    @staticmethod
    def storage_circuit_breaker() -> CircuitBreakerConfig:
        return CircuitBreakerConfig(
            name="storage_minio",
            failure_threshold=5,
            success_threshold=3,
            reset_timeout_seconds=30,
            half_open_max_calls=3,
            window_size=20,
            failure_rate_threshold=0.5
        )

    @staticmethod
    def storage_retry() -> RetryConfig:
        return RetryConfig(
            max_attempts=3,
            initial_delay_ms=100,
            max_delay_ms=5000,
            backoff_factor=2.0,
            jitter=True,
            jitter_type="full"
        )

    @staticmethod
    def storage_reliability() -> ReliabilityConfigBundle:
        return ReliabilityConfigBundle(
            circuit_breaker=ReliabilityConfigs.storage_circuit_breaker(),
            retry=ReliabilityConfigs.storage_retry(),
            rate_limiter=None
        )

    # =========================================================================
    # Webhook
    # =========================================================================
    @staticmethod
    def webhook_rate_limiter() -> RateLimiterConfig:
        return RateLimiterConfig(
            algorithm="sliding_window",
            capacity=60,
            time_window=60,
            distributed=True
        )

    # =========================================================================
    # Error Classification
    # =========================================================================
    @staticmethod
    def classify_error(error: Exception) -> ErrorClass:
        if error is None:
            return ErrorClass.UNKNOWN
        error_str = str(error).lower()

        if any(term in error_str for term in ["connection refused", "no such host", "network is unreachable", "broken pipe"]):
            return ErrorClass.NETWORK
        if any(term in error_str for term in ["timeout", "deadline exceeded"]):
            return ErrorClass.TIMEOUT
        if any(term in error_str for term in ["syntax error", "invalid", "constraint", "wrongtype"]):
            return ErrorClass.LOGICAL
        if any(term in error_str for term in ["deadlock", "too many connections", "temporary"]):
            return ErrorClass.TRANSIENT
        if hasattr(error, '__permanent__') and error.__permanent__:
            return ErrorClass.PERMANENT
        return ErrorClass.UNKNOWN

    @staticmethod
    def should_retry_error(error: Exception) -> bool:
        error_class = ReliabilityConfigs.classify_error(error)
        return error_class in [ErrorClass.NETWORK, ErrorClass.TIMEOUT, ErrorClass.TRANSIENT, ErrorClass.UNKNOWN]

    @staticmethod
    def _should_retry_kafka(error: Exception) -> bool:
        if error is None:
            return False
        error_str = str(error)
        if any(term in error_str for term in ["REBALANCE", "SASL", "AUTH"]):
            return False
        return ReliabilityConfigs.should_retry_error(error)

    @staticmethod
    def _should_retry_redis(error: Exception) -> bool:
        if error is None:
            return False
        error_str = str(error)
        if any(term in error_str for term in ["WRONGTYPE", "ERR invalid", "ERR syntax"]):
            return False
        return ReliabilityConfigs.should_retry_error(error)

    @staticmethod
    def _should_retry_postgres(error: Exception) -> bool:
        if error is None:
            return False
        error_str = str(error)
        if "deadlock detected" in error_str:
            return True
        if any(term in error_str for term in ["syntax error", "violates unique constraint", "violates foreign key", "violates check constraint"]):
            return False
        return ReliabilityConfigs.should_retry_error(error)

    @staticmethod
    def _should_retry_broker_api(error: Exception) -> bool:
        if error is None:
            return False
        error_str = str(error)
        if any(term in error_str for term in ["401", "403", "unauthorized", "forbidden"]):
            return False
        if any(term in error_str for term in ["400", "bad request", "invalid parameter"]):
            return False
        if any(term in error_str for term in ["429", "rate limit", "too many requests"]):
            return True
        return ReliabilityConfigs.should_retry_error(error)

    @staticmethod
    def _should_retry_telegram(error: Exception) -> bool:
        if error is None:
            return False
        error_str = str(error).lower()
        if any(term in error_str for term in [
            "chat not found", "bot was blocked", "user is deactivated",
            "chat_write_forbidden", "need administrator rights",
            "message is too long", "topic_closed", "topic_deleted",
            "invalid token", "unauthorized"
        ]):
            return False
        if "flood" in error_str or "retry after" in error_str:
            return True
        if any(term in error_str for term in ["timeout", "connection", "network", "503", "500"]):
            return True
        return ReliabilityConfigs.should_retry_error(error)

    @staticmethod
    def _should_retry_storage(error: Exception) -> bool:
        if error is None:
            return False
        error_str = str(error).lower()
        if any(term in error_str for term in [
            "accessdenied", "invalidaccesskeyid", "signaturesdoesnotmatch",
            "403", "401", "nosuchbucket"
        ]):
            return False
        if any(term in error_str for term in [
            "timeout", "connection", "503", "500", "slowdown",
            "serviceunavailable", "internalerror"
        ]):
            return True
        return ReliabilityConfigs.should_retry_error(error)


# =============================================================================
# Backward Compatibility Aliases
# =============================================================================

# Alias for backward compatibility
ReliabilityConfig = ReliabilityConfigBundle
