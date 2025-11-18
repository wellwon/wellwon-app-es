# =============================================================================
# File: app/config/reliability_config.py
# Description: Unified reliability configuration for circuit breakers, retry
#              patterns, rate limiting, and distributed locking across all
#              infrastructure components in 
# ENHANCED: Added Gunicorn-aware PostgreSQL configurations
# =============================================================================

import os
from dataclasses import dataclass
from enum import Enum, auto

# Forward declarations to avoid circular imports
from dataclasses import dataclass as original_dataclass
from typing import Optional, Callable


# We'll define the config classes here to avoid circular imports
@original_dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    name: str
    failure_threshold: int = 5
    success_threshold: int = 3
    reset_timeout_seconds: int = 30
    half_open_max_calls: int = 3
    # Additional config for enhanced features
    window_size: Optional[int] = None
    failure_rate_threshold: Optional[float] = None
    timeout_seconds: Optional[float] = None


@original_dataclass
class RetryConfig:
    """Retry configuration."""
    max_attempts: int = 3
    initial_delay_ms: int = 100
    max_delay_ms: int = 10000
    backoff_factor: float = 2.0
    jitter: bool = True
    retry_condition: Optional[Callable[[Exception], bool]] = None
    # Enhanced config options
    exponential_base: Optional[float] = None
    jitter_type: str = "full"


@original_dataclass
class RateLimiterConfig:
    """Rate limiter configuration."""
    algorithm: str = "token_bucket"
    capacity: int = 100
    refill_rate: float = 10.0
    distributed: bool = True
    # Additional config for compatibility
    max_requests: Optional[int] = None
    time_window: Optional[int] = None


@original_dataclass
class DistributedLockConfig:
    """Distributed lock configuration."""
    namespace: str = "distributed_lock"
    ttl_seconds: int = 30
    max_wait_ms: int = 5000
    retry_times: int = 3
    retry_delay_ms: int = 100
    strategy: str = "wait_with_timeout"  # fail_fast, wait_forever, wait_with_timeout, exponential_backoff
    enable_metrics: bool = True
    enable_auto_cleanup: bool = True
    use_lua_scripts: bool = True
    # Enhanced features
    stale_lock_multiplier: float = 2.0  # Consider lock stale after TTL * multiplier
    use_backoff: Optional[bool] = None  # For compatibility with adapter pool


class ErrorClass(Enum):
    """Error classification for retry decisions"""
    UNKNOWN = auto()
    NETWORK = auto()
    TIMEOUT = auto()
    LOGICAL = auto()
    TRANSIENT = auto()
    PERMANENT = auto()


@dataclass
class ReliabilityConfig:
    """Combined configuration for circuit breaker, retry, rate limiter, and distributed lock"""
    circuit_breaker: CircuitBreakerConfig
    retry: RetryConfig
    rate_limiter: Optional[RateLimiterConfig] = None
    distributed_lock: Optional[DistributedLockConfig] = None


class ReliabilityConfigs:
    """Pre-configured reliability settings for different services"""

    # Kafka/RedPanda configurations
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
            jitter=True,
            retry_condition=lambda err: ReliabilityConfigs._should_retry_kafka(err)
        )

    @staticmethod
    def kafka_rate_limiter() -> RateLimiterConfig:
        return RateLimiterConfig(
            algorithm="token_bucket",
            capacity=1000,  # 1000 requests per refill
            refill_rate=100.0,  # 100 tokens per second
            distributed=True
        )

    # Redis configurations
    @staticmethod
    def redis_circuit_breaker(name: str) -> CircuitBreakerConfig:
        return CircuitBreakerConfig(
            name=f"redis_{name}",
            failure_threshold=3,  # More aggressive for Redis
            reset_timeout_seconds=15,
            half_open_max_calls=3,
            success_threshold=2
        )

    @staticmethod
    def redis_retry() -> RetryConfig:
        return RetryConfig(
            max_attempts=3,
            initial_delay_ms=50,  # Faster for Redis
            max_delay_ms=1000,
            backoff_factor=2.0,
            jitter=True,
            retry_condition=lambda err: ReliabilityConfigs._should_retry_redis(err)
        )

    @staticmethod
    def redis_rate_limiter() -> RateLimiterConfig:
        return RateLimiterConfig(
            algorithm="token_bucket",
            capacity=5000,  # Higher for Redis
            refill_rate=500.0,  # 500 tokens per second
            distributed=False  # Local rate limiting for Redis
        )

    # PostgreSQL configurations - ENHANCED for different scenarios
    @staticmethod
    def postgres_circuit_breaker(name: str) -> CircuitBreakerConfig:
        """Standard PostgreSQL circuit breaker"""
        # Check if we're running under multi-worker server (Granian, Gunicorn, etc.)
        is_multi_worker = _detect_multi_worker_server()

        if is_multi_worker:
            # More forgiving under multi-worker server due to connection pool competition
            return CircuitBreakerConfig(
                name=f"postgres_{name}",
                failure_threshold=10,  # Higher threshold
                reset_timeout_seconds=60,  # Longer reset time
                half_open_max_calls=5,
                success_threshold=3,
                window_size=20,
                failure_rate_threshold=0.5
            )
        else:
            # Standard config for single process
            return CircuitBreakerConfig(
                name=f"postgres_{name}",
                failure_threshold=5,
                reset_timeout_seconds=30,
                half_open_max_calls=3,
                success_threshold=3
            )

    @staticmethod
    def postgres_retry() -> RetryConfig:
        """Standard PostgreSQL retry config"""
        # Check environment for pool pressure
        pool_pressure = _detect_pool_pressure()

        if pool_pressure == "high":
            # More aggressive retry for high pool pressure
            return RetryConfig(
                max_attempts=5,
                initial_delay_ms=50,  # Start faster
                max_delay_ms=2000,  # Cap lower
                backoff_factor=1.5,  # Less aggressive backoff
                jitter=True,
                jitter_type="full",
                retry_condition=lambda err: ReliabilityConfigs._should_retry_postgres(err)
            )
        else:
            # Standard retry
            return RetryConfig(
                max_attempts=3,
                initial_delay_ms=100,
                max_delay_ms=5000,
                backoff_factor=2.0,
                jitter=True,
                retry_condition=lambda err: ReliabilityConfigs._should_retry_postgres(err)
            )

    @staticmethod
    def postgres_pool_acquisition_retry() -> RetryConfig:
        """Special config for connection pool acquisition"""
        return RetryConfig(
            max_attempts=10,  # Many attempts for pool acquisition
            initial_delay_ms=10,  # Very fast initial retry
            max_delay_ms=500,  # Cap at 500ms
            backoff_factor=1.2,  # Gentle backoff
            jitter=True,
            jitter_type="decorrelated",  # Better for pool contention
            retry_condition=lambda err: "timeout" in str(err).lower() or "pool" in str(err).lower()
        )

    @staticmethod
    def postgres_deadlock_retry() -> RetryConfig:
        """Special config for deadlock handling"""
        return RetryConfig(
            max_attempts=5,  # More attempts for deadlock
            initial_delay_ms=0,  # Immediate retry for deadlock
            max_delay_ms=100,
            backoff_factor=1.5,
            jitter=True,
            retry_condition=lambda err: "deadlock detected" in str(err).lower()
        )

    @staticmethod
    def postgres_rate_limiter() -> RateLimiterConfig:
        """PostgreSQL rate limiter - adjusts based on worker count"""
        worker_count = _get_worker_count()

        # Adjust capacity based on workers
        base_capacity = 100
        capacity = base_capacity // max(1, worker_count)

        return RateLimiterConfig(
            algorithm="token_bucket",
            capacity=capacity,
            refill_rate=capacity / 10.0,  # Refill over 10 seconds
            distributed=True
        )

    # Broker API configurations
    @staticmethod
    def broker_api_circuit_breaker(broker_id: str) -> CircuitBreakerConfig:
        return CircuitBreakerConfig(
            name=f"broker_{broker_id}_api",
            failure_threshold=5,
            reset_timeout_seconds=60,
            half_open_max_calls=2,
            success_threshold=3,
            # Enhanced features
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
            jitter_type="full",
            retry_condition=lambda err: ReliabilityConfigs._should_retry_broker_api(err)
        )

    @staticmethod
    def broker_api_rate_limiter(broker_id: str) -> RateLimiterConfig:
        """Rate limiter config per broker (they have different limits)"""
        broker_limits = {
            "alpaca": {"capacity": 200, "refill_rate": 10.0},  # 200 req/bucket, 10/sec
            "interactive_brokers": {"capacity": 50, "refill_rate": 1.0},  # Conservative
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

    # WSE (WebSocket Event System) specific configurations
    @staticmethod
    def wse_circuit_breaker(conn_id: str = "default") -> CircuitBreakerConfig:
        """Circuit breaker for WSE connections"""
        return CircuitBreakerConfig(
            name=f"wse_{conn_id}",
            failure_threshold=10,  # More tolerant for WSE
            success_threshold=3,
            reset_timeout_seconds=30,
            half_open_max_calls=5,
            window_size=50,
            failure_rate_threshold=0.3  # 30% failure rate
        )

    @staticmethod
    def wse_rate_limiter() -> RateLimiterConfig:
        """Rate limiter for WSE messages (per connection)"""
        return RateLimiterConfig(
            algorithm="token_bucket",
            capacity=1000,  # From wse_config connection.rate_limit_capacity
            refill_rate=100.0,  # From wse_config connection.rate_limit_refill_rate
            distributed=False  # Local to each connection
        )

    @staticmethod
    def wse_user_rate_limiter(is_premium: bool = False) -> RateLimiterConfig:
        """Rate limiter for WSE users (per user across connections)"""
        if is_premium:
            return RateLimiterConfig(
                algorithm="token_bucket",
                capacity=5000,  # Premium users get 5x capacity
                refill_rate=500.0,  # 5x refill rate
                distributed=False
            )
        else:
            return RateLimiterConfig(
                algorithm="token_bucket",
                capacity=1000,  # Standard users
                refill_rate=100.0,  # Standard rate
                distributed=False
            )

    @staticmethod
    def wse_ip_rate_limiter() -> RateLimiterConfig:
        """Rate limiter for WSE IP addresses (DDoS protection)"""
        return RateLimiterConfig(
            algorithm="token_bucket",
            capacity=10000,  # 10x connection limit for IP-level
            refill_rate=1000.0,  # 10x refill rate
            distributed=False  # Per-server rate limiting
        )

    @staticmethod
    def wse_reliability() -> ReliabilityConfig:
        """Complete reliability config for WSE system"""
        return ReliabilityConfig(
            circuit_breaker=ReliabilityConfigs.wse_circuit_breaker(),
            retry=None,  # WSE doesn't use retry (it's connection-based)
            rate_limiter=ReliabilityConfigs.wse_rate_limiter()
        )

    # Distributed Lock configurations
    @staticmethod
    def event_store_distributed_lock() -> DistributedLockConfig:
        """Lock config for EventStore aggregates"""
        return DistributedLockConfig(
            namespace="aggregate_lock",
            ttl_seconds=30,
            max_wait_ms=5000,
            retry_times=100,  # More retries for critical operations
            retry_delay_ms=50,
            strategy="wait_with_timeout",
            enable_auto_cleanup=True,
            stale_lock_multiplier=2.0
        )

    @staticmethod
    def event_bus_distributed_lock() -> DistributedLockConfig:
        """Lock config for EventBus message processing"""
        return DistributedLockConfig(
            namespace="event_bus:message",
            ttl_seconds=10,
            max_wait_ms=1000,
            retry_times=3,
            retry_delay_ms=100,
            strategy="fail_fast",  # Don't wait for message processing
            enable_metrics=True
        )

    @staticmethod
    def adapter_pool_distributed_lock() -> DistributedLockConfig:
        """Lock config for AdapterPool operations"""
        return DistributedLockConfig(
            namespace="adapter_pool:lock",
            ttl_seconds=30,
            max_wait_ms=10000,
            retry_times=3,
            retry_delay_ms=100,
            strategy="exponential_backoff",
            use_backoff=True,  # AdapterPool compatibility
            enable_metrics=True
        )

    @staticmethod
    def cache_distributed_lock() -> DistributedLockConfig:
        """Lock config for cache operations (stampede prevention)"""
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
        """Lock config for saga execution"""
        return DistributedLockConfig(
            namespace="saga:execution",
            ttl_seconds=60,  # Longer for complex operations
            max_wait_ms=30000,
            retry_times=10,
            retry_delay_ms=200,
            strategy="exponential_backoff"
        )

    @staticmethod
    def schema_init_lock() -> DistributedLockConfig:
        """Lock config for database schema initialization (multi-worker safety)"""
        return DistributedLockConfig(
            namespace="db:schema_init",
            ttl_seconds=60,  # Schema execution can take up to 60 seconds
            max_wait_ms=120000,  # Wait up to 2 minutes for another worker to finish
            retry_delay_ms=500,  # Check every 500ms if schema is done
            retry_times=240,  # 240 * 500ms = 120 seconds max wait
            strategy="wait_with_timeout",
            use_lua_scripts=True,
            enable_metrics=True
        )

    # Combined configurations for services
    @staticmethod
    def event_store_reliability() -> ReliabilityConfig:
        return ReliabilityConfig(
            circuit_breaker=ReliabilityConfigs.kafka_circuit_breaker("event_store"),
            retry=ReliabilityConfigs.kafka_retry(),
            rate_limiter=ReliabilityConfigs.kafka_rate_limiter(),
            distributed_lock=ReliabilityConfigs.event_store_distributed_lock()
        )

    @staticmethod
    def event_bus_reliability() -> ReliabilityConfig:
        return ReliabilityConfig(
            circuit_breaker=ReliabilityConfigs.kafka_circuit_breaker("event_bus"),
            retry=ReliabilityConfigs.kafka_retry(),
            rate_limiter=ReliabilityConfigs.kafka_rate_limiter(),
            distributed_lock=ReliabilityConfigs.event_bus_distributed_lock()
        )

    @staticmethod
    def cache_reliability() -> ReliabilityConfig:
        return ReliabilityConfig(
            circuit_breaker=ReliabilityConfigs.redis_circuit_breaker("cache"),
            retry=ReliabilityConfigs.redis_retry(),
            rate_limiter=ReliabilityConfigs.redis_rate_limiter(),
            distributed_lock=ReliabilityConfigs.cache_distributed_lock()
        )

    @staticmethod
    def database_reliability() -> ReliabilityConfig:
        """Enhanced database reliability config"""
        return ReliabilityConfig(
            circuit_breaker=ReliabilityConfigs.postgres_circuit_breaker("main_db"),
            retry=ReliabilityConfigs.postgres_retry(),
            rate_limiter=ReliabilityConfigs.postgres_rate_limiter()
            # No distributed lock for DB - it has its own locking
        )

    @staticmethod
    def broker_reliability(broker_id: str) -> ReliabilityConfig:
        """Get reliability config for a specific broker"""
        return ReliabilityConfig(
            circuit_breaker=ReliabilityConfigs.broker_api_circuit_breaker(broker_id),
            retry=ReliabilityConfigs.broker_api_retry(),
            rate_limiter=ReliabilityConfigs.broker_api_rate_limiter(broker_id),
            distributed_lock=ReliabilityConfigs.adapter_pool_distributed_lock()
        )

    # Connection recovery specific configurations
    @staticmethod
    def connection_recovery_circuit_breaker(broker_id: str) -> CircuitBreakerConfig:
        """Circuit breaker for connection recovery operations"""
        return CircuitBreakerConfig(
            name=f"{broker_id}_recovery",
            failure_threshold=5,
            success_threshold=3,
            reset_timeout_seconds=30,
            timeout_seconds=30,  # Alias support
            half_open_max_calls=3,
            window_size=10,
            failure_rate_threshold=0.5
        )

    @staticmethod
    def connection_recovery_retry() -> RetryConfig:
        """Retry config for connection recovery"""
        return RetryConfig(
            max_attempts=3,
            initial_delay_ms=100,
            max_delay_ms=30000,
            backoff_factor=2.0,
            exponential_base=2.0,  # Alias support
            jitter=True,
            jitter_type="full"
        )

    @staticmethod
    def connection_recovery_rate_limiter() -> RateLimiterConfig:
        """Rate limiter for recovery attempts"""
        return RateLimiterConfig(
            algorithm="token_bucket",
            capacity=100,
            refill_rate=10.0,
            distributed=True
        )

    # Webhook configurations
    @staticmethod
    def webhook_rate_limiter() -> RateLimiterConfig:
        """Rate limiter for webhook endpoints (per automation)"""
        return RateLimiterConfig(
            algorithm="sliding_window",
            capacity=60,  # 60 requests per window
            time_window=60,  # 60 seconds (1 minute)
            distributed=True
        )

    # Error classification
    @staticmethod
    def classify_error(error: Exception) -> ErrorClass:
        """Classify an error to determine retry behavior"""
        if error is None:
            return ErrorClass.UNKNOWN

        error_str = str(error).lower()

        # Network errors
        if any(term in error_str for term in [
            "connection refused", "no such host",
            "network is unreachable", "broken pipe"
        ]):
            return ErrorClass.NETWORK

        # Timeout errors
        if any(term in error_str for term in ["timeout", "deadline exceeded"]):
            return ErrorClass.TIMEOUT

        # Logical errors (should not retry)
        if any(term in error_str for term in [
            "syntax error", "invalid", "constraint", "wrongtype"
        ]):
            return ErrorClass.LOGICAL

        # Transient errors (should retry)
        if any(term in error_str for term in [
            "deadlock", "too many connections", "temporary"
        ]):
            return ErrorClass.TRANSIENT

        # Check if marked as permanent
        if hasattr(error, '__permanent__') and error.__permanent__:
            return ErrorClass.PERMANENT

        return ErrorClass.UNKNOWN

    @staticmethod
    def should_retry_error(error: Exception) -> bool:
        """Determine if an error should be retried based on its class"""
        error_class = ReliabilityConfigs.classify_error(error)
        return error_class in [ErrorClass.NETWORK, ErrorClass.TIMEOUT,
                               ErrorClass.TRANSIENT, ErrorClass.UNKNOWN]

    # Private helper methods
    @staticmethod
    def _should_retry_kafka(error: Exception) -> bool:
        """Kafka-specific retry logic"""
        if error is None:
            return False

        error_str = str(error)
        # Don't retry on rebalancing or auth errors
        if any(term in error_str for term in ["REBALANCE", "SASL", "AUTH"]):
            return False

        return ReliabilityConfigs.should_retry_error(error)

    @staticmethod
    def _should_retry_redis(error: Exception) -> bool:
        """Redis-specific retry logic"""
        if error is None:
            return False

        error_str = str(error)
        # Don't retry on logical errors
        if any(term in error_str for term in ["WRONGTYPE", "ERR invalid", "ERR syntax"]):
            return False

        return ReliabilityConfigs.should_retry_error(error)

    @staticmethod
    def _should_retry_postgres(error: Exception) -> bool:
        """PostgreSQL-specific retry logic"""
        if error is None:
            return False

        error_str = str(error)
        # Immediate retry for deadlocks
        if "deadlock detected" in error_str:
            return True

        # Don't retry syntax errors or constraint violations
        if any(term in error_str for term in [
            "syntax error", "violates unique constraint",
            "violates foreign key", "violates check constraint"
        ]):
            return False

        return ReliabilityConfigs.should_retry_error(error)

    @staticmethod
    def _should_retry_broker_api(error: Exception) -> bool:
        """Broker API specific retry logic"""
        if error is None:
            return False

        error_str = str(error)

        # Don't retry on auth errors
        if any(term in error_str for term in ["401", "403", "unauthorized", "forbidden"]):
            return False

        # Don't retry on bad requests
        if any(term in error_str for term in ["400", "bad request", "invalid parameter"]):
            return False

        # Retry on rate limits
        if any(term in error_str for term in ["429", "rate limit", "too many requests"]):
            return True

        return ReliabilityConfigs.should_retry_error(error)


# Helper functions for environment detection
def _detect_multi_worker_server() -> bool:
    """Detect if running under multi-worker server (Granian)"""
    # Check for Granian
    if 'granian' in os.environ.get('SERVER_SOFTWARE', '').lower():
        return True

    # Check for WEB_CONCURRENCY (standard multi-worker indicator)
    if os.environ.get('WEB_CONCURRENCY'):
        try:
            workers = int(os.environ.get('WEB_CONCURRENCY', '1'))
            if workers > 1:
                return True
        except ValueError:
            pass

    # Check process name
    try:
        import psutil
        current_process = psutil.Process()
        cmdline = ' '.join(current_process.cmdline())
        # Check for granian
        if 'granian' in cmdline:
            # Look for --workers flag
            if '--workers' in cmdline or '-w' in cmdline:
                return True
            return True  # Assume multi-worker if granian detected
    except ImportError:
        pass  # psutil not installed
    except Exception as e:
        # Catch any psutil-specific errors
        if 'psutil' in str(type(e).__module__):
            pass  # psutil error, ignore
        else:
            raise

    return False


def _get_worker_count() -> int:
    """Get estimated worker count"""
    # From environment
    if workers := os.environ.get('GUNICORN_WORKERS'):
        return int(workers)

    if workers := os.environ.get('WEB_CONCURRENCY'):
        return int(workers)

    # Default
    return 1


def _detect_pool_pressure() -> str:
    """Detect pool pressure level"""
    # Check if we have many workers
    worker_count = _get_worker_count()

    # Check pool size configuration
    max_pool = int(os.environ.get('PG_POOL_MAX_SIZE', '20'))

    # Calculate pressure
    total_connections = worker_count * max_pool

    if total_connections > 80:
        return "high"
    elif total_connections > 40:
        return "medium"
    else:
        return "low"

# =============================================================================
# EOF
# =============================================================================