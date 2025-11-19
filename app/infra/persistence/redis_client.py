# =============================================================================
# File: app/infra/persistence/redis_client.py  — Enhanced Async Redis Client
# =============================================================================
# • Universal async Redis client for FastAPI, microservices, tests, and workers.
# • Supports both singleton (legacy) and per-app (.state.redis) FastAPI patterns.
# • Uses the unified reliability infrastructure (circuit breaker, retry, etc.)
# • Improved error handling and health monitoring.
# • Utility wrappers for KV, Hash, Pub/Sub, Streams, Expiry, batching, and health.
# • Strict type safety, production ready, supports async DI and system metrics.
# • UPDATED: Added hget function and uses central reliability infrastructure
# =============================================================================

from __future__ import annotations

import socket
import asyncio
import json
import logging
import time
import os
from typing import Any, Dict, List, Optional, AsyncIterator, Union, Callable
from contextlib import asynccontextmanager
from enum import Enum, auto

import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError, ResponseError, TimeoutError

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    def load_dotenv():  # type: ignore[misc]
        """Stub for when dotenv is not installed"""
        pass

# Import configuration if available
try:
    from app.config.redis_config import RedisConfig, CircuitBreakerState

    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    RedisConfig = None
    CircuitBreakerState = None

# Import reliability infrastructure
try:
    from app.config.reliability_config import (
        ReliabilityConfigs,
        CircuitBreakerConfig,
        RetryConfig
    )
    from app.infra.reliability.circuit_breaker import (
        CircuitBreaker,
        get_circuit_breaker,
        CircuitBreakerOpenError
    )
    from app.infra.reliability.retry import retry_async

    RELIABILITY_AVAILABLE = True
except ImportError:
    RELIABILITY_AVAILABLE = False
    ReliabilityConfigs = None
    CircuitBreakerConfig = None
    RetryConfig = None
    CircuitBreaker = None
    get_circuit_breaker = None
    retry_async = None
    CircuitBreakerOpenError = Exception

log = logging.getLogger("wellwon.infra.redis_client")

# -----------------------------------------------------------------------------
# Default Configuration (used when RedisConfig is not available)
# -----------------------------------------------------------------------------
# These defaults match the RedisConfig defaults for consistency
DEFAULT_REDIS_URL = "redis://localhost:6379/1"
DEFAULT_SOCKET_TIMEOUT = 15.0
DEFAULT_SOCKET_CONNECT_TIMEOUT = 5.0
DEFAULT_SOCKET_KEEPALIVE_INTERVAL = 60

DEFAULT_CIRCUIT_FAILURE_THRESHOLD = 5
DEFAULT_CIRCUIT_RESET_TIMEOUT = 30
DEFAULT_CIRCUIT_HALF_OPEN_MAX = 3
DEFAULT_CIRCUIT_SUCCESS_THRESHOLD = 3

DEFAULT_RETRY_MAX_ATTEMPTS = 3
DEFAULT_RETRY_INITIAL_DELAY_MS = 100
DEFAULT_RETRY_MAX_DELAY_MS = 2000
DEFAULT_RETRY_BACKOFF_FACTOR = 2.0

# Performance monitoring defaults (industry standard: <1ms optimal, alert at 5-10ms)
DEFAULT_SLOW_COMMAND_THRESHOLD_MS = 5.0

# -----------------------------------------------------------------------------
# Lazy Configuration Loading (avoid circular imports)
# -----------------------------------------------------------------------------
def _get_slow_command_threshold(key: Optional[str] = None) -> float:
    """
    Get slow command threshold from config (lazy load to avoid circular imports).

    Uses adaptive thresholds based on operation type:
    - Saga operations (wellwon_saga:*, saga_aggregate_lock:*): 50ms (large payloads ~6KB)
    - Worker registry (wellwon:workers:registry:*): 30ms (large JSON ~2-4KB)
    - Worker metrics (wellwon:workers:metrics): 30ms (hash operations)
    - Cache operations (wellwon:cache:*): 20ms (serialized objects)
    - Regular operations: 5ms (small payloads <1KB)

    Industry benchmarks:
    - <1ms: Optimal for small keys (<100 bytes)
    - <5ms: Good for medium keys (100-1000 bytes)
    - <20ms: Acceptable for cached objects (1-2KB)
    - <30ms: Acceptable for worker heartbeats (2-4KB)
    - <50ms: Acceptable for large state objects (>5KB)
    """
    if key:
        # Saga operations - large state objects (6KB+)
        if key.startswith("wellwon_saga:") or key.startswith("saga_aggregate_lock:"):
            return 50.0

        # Worker registry - heartbeat payloads (2-4KB)
        if key.startswith("wellwon:workers:registry:"):
            return 30.0

        # Worker metrics - hash operations
        if key.startswith("wellwon:workers:metrics"):
            return 30.0

        # Cache operations - serialized objects (1-2KB)
        if key.startswith("wellwon:cache:"):
            return 20.0

    try:
        if CONFIG_AVAILABLE:
            from app.config.redis_config import RedisConfig
            config = RedisConfig()
            return float(config.slow_command_threshold_ms)
    except (AttributeError, RuntimeError, ImportError):  # Config not initialized or circular import
        pass

    # Fallback to env var
    return float(os.getenv("REDIS_SLOW_COMMAND_THRESHOLD_MS", str(DEFAULT_SLOW_COMMAND_THRESHOLD_MS)))

# -----------------------------------------------------------------------------
# Fallback implementations when reliability package is not available
# -----------------------------------------------------------------------------
if not RELIABILITY_AVAILABLE:
    class CircuitState(Enum):
        """Possible states of a circuit breaker"""
        CLOSED = auto()
        OPEN = auto()
        HALF_OPEN = auto()


    class CircuitBreakerOpenError(Exception):
        """Raised when circuit breaker is open"""
        pass


    class FallbackCircuitBreaker:
        """Minimal circuit breaker for when reliability package is not available"""

        def __init__(self, name: str):
            self.name = name
            self.state = CircuitState.CLOSED

        def can_execute(self) -> bool:
            return self.state != CircuitState.OPEN

        def record_success(self) -> None:
            self.state = CircuitState.CLOSED

        def record_failure(self, error_details: Optional[str] = None) -> None:
            log.warning(f"Circuit breaker {self.name} recording failure: {error_details}")

        def get_metrics(self) -> Dict[str, Any]:
            return {"name": self.name, "state": self.state.name}


    class FallbackRetryConfig:
        """Minimal retry config for when reliability package is not available"""

        def __init__(self):
            self.max_attempts = DEFAULT_RETRY_MAX_ATTEMPTS
            self.initial_delay_ms = DEFAULT_RETRY_INITIAL_DELAY_MS
            self.max_delay_ms = DEFAULT_RETRY_MAX_DELAY_MS
            self.backoff_factor = DEFAULT_RETRY_BACKOFF_FACTOR


    async def fallback_retry_async(
            func: Callable[..., Any],
            *args,
            retry_config: Optional[Any] = None,
            context: str = "operation",
            **kwargs
    ) -> Any:
        """Minimal retry implementation"""
        config = retry_config or FallbackRetryConfig()
        last_exception = None

        for attempt in range(1, config.max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt >= config.max_attempts:
                    log.warning(f"Retry exhausted for {context} after {attempt} attempts. Last error: {e}")
                    raise

                delay_ms = min(
                    config.initial_delay_ms * (config.backoff_factor ** (attempt - 1)),
                    config.max_delay_ms
                )
                delay_seconds = delay_ms / 1000

                log.info(f"Retry attempt {attempt}/{config.max_attempts} for {context}. Waiting {delay_seconds:.2f}s")
                await asyncio.sleep(delay_seconds)

        raise last_exception if last_exception else RuntimeError("Unexpected retry failure")

# -----------------------------------------------------------------------------
# Global Singleton (legacy/compat)
# -----------------------------------------------------------------------------
_MAIN_REDIS_CLIENT: Optional[redis.Redis] = None
_CLIENT_INIT_LOCK = asyncio.Lock()
_MAIN_CIRCUIT_BREAKER: Optional[Union[CircuitBreaker, FallbackCircuitBreaker]] = None
_RETRY_CONFIG: Optional[Union[RetryConfig, FallbackRetryConfig]] = None
_REDIS_CONFIG: Optional[RedisConfig] = None


async def init_global_client(config: Optional[RedisConfig] = None, **kwargs: Any) -> redis.Redis:
    """Idempotent global singleton init, PING tested. Use in legacy/stateless code."""
    global _MAIN_REDIS_CLIENT, _MAIN_CIRCUIT_BREAKER, _RETRY_CONFIG, _REDIS_CONFIG

    # Store config for later use
    if config:
        _REDIS_CONFIG = config

    if _MAIN_REDIS_CLIENT is not None:
        try:
            await _MAIN_REDIS_CLIENT.ping()
            return _MAIN_REDIS_CLIENT
        except (RedisError, OSError):
            await close_global_client()

    async with _CLIENT_INIT_LOCK:
        if _MAIN_REDIS_CLIENT is None:
            # Use provided config or create default
            if config:
                _REDIS_CONFIG = config
            elif CONFIG_AVAILABLE and _REDIS_CONFIG is None:
                _REDIS_CONFIG = RedisConfig()

            # Initialize circuit breaker
            if _MAIN_CIRCUIT_BREAKER is None:
                if RELIABILITY_AVAILABLE and ReliabilityConfigs:
                    # Use the pre-configured Redis circuit breaker
                    cb_config = ReliabilityConfigs.redis_circuit_breaker("global")
                    _MAIN_CIRCUIT_BREAKER = get_circuit_breaker("redis_global", cb_config)
                else:
                    # Use fallback
                    _MAIN_CIRCUIT_BREAKER = FallbackCircuitBreaker("redis_global")

            # Initialize retry config
            if _RETRY_CONFIG is None:
                if RELIABILITY_AVAILABLE and ReliabilityConfigs:
                    # Use the pre-configured Redis retry settings
                    _RETRY_CONFIG = ReliabilityConfigs.redis_retry()
                else:
                    # Use fallback
                    _RETRY_CONFIG = FallbackRetryConfig()

            # Build Redis client
            if CONFIG_AVAILABLE and _REDIS_CONFIG:
                _MAIN_REDIS_CLIENT = _build_redis_client_from_config(_REDIS_CONFIG, **kwargs)
            else:
                _MAIN_REDIS_CLIENT = _build_redis_client(**kwargs)

            # Test connection with retry
            async def test_ping():
                return await _MAIN_REDIS_CLIENT.ping()

            try:
                if RELIABILITY_AVAILABLE:
                    await retry_async(test_ping, retry_config=_RETRY_CONFIG, context="Redis init ping")
                else:
                    await fallback_retry_async(test_ping, retry_config=_RETRY_CONFIG, context="Redis init ping")

                _MAIN_CIRCUIT_BREAKER.record_success()
                log.info("Global Redis client initialized and ping OK.")
            except Exception as e:
                _MAIN_CIRCUIT_BREAKER.record_failure(str(e))
                log.error(f"Failed to initialize Redis client: {e}")
                _MAIN_REDIS_CLIENT = None
                raise

    return _MAIN_REDIS_CLIENT


async def close_global_client() -> None:
    global _MAIN_REDIS_CLIENT
    if _MAIN_REDIS_CLIENT:
        try:
            await _MAIN_REDIS_CLIENT.aclose()
            log.info("Global Redis client closed.")
        except Exception as e:
            log.warning(f"Error closing global Redis client: {e}", exc_info=True)
    _MAIN_REDIS_CLIENT = None


def get_global_client() -> redis.Redis:
    if _MAIN_REDIS_CLIENT is None:
        raise RuntimeError("Redis client not initialized. Call init_global_client() first.")
    return _MAIN_REDIS_CLIENT


def get_global_circuit_breaker() -> Union[CircuitBreaker, FallbackCircuitBreaker]:
    global _MAIN_CIRCUIT_BREAKER
    if _MAIN_CIRCUIT_BREAKER is None:
        if RELIABILITY_AVAILABLE and ReliabilityConfigs:
            cb_config = ReliabilityConfigs.redis_circuit_breaker("global")
            _MAIN_CIRCUIT_BREAKER = get_circuit_breaker("redis_global", cb_config)
        else:
            _MAIN_CIRCUIT_BREAKER = FallbackCircuitBreaker("redis_global")
    return _MAIN_CIRCUIT_BREAKER


def get_global_retry_config() -> Union[RetryConfig, FallbackRetryConfig]:
    global _RETRY_CONFIG
    if _RETRY_CONFIG is None:
        if RELIABILITY_AVAILABLE and ReliabilityConfigs:
            _RETRY_CONFIG = ReliabilityConfigs.redis_retry()
        else:
            _RETRY_CONFIG = FallbackRetryConfig()
    return _RETRY_CONFIG


# -----------------------------------------------------------------------------
# Per-App Client for FastAPI (recommended for all new code)
# -----------------------------------------------------------------------------
def _build_redis_client(**kwargs) -> redis.Redis:
    """Build Redis client with legacy configuration (backward compatibility)"""
    # Get config from environment or use defaults
    config = None
    if CONFIG_AVAILABLE:
        try:
            config = RedisConfig()  # This will load from environment variables
        except (ValueError, RuntimeError, ImportError):  # Config validation or import errors
            pass  # Fall back to defaults

    if config:
        return _build_redis_client_from_config(config, **kwargs)

    # Fallback to defaults if config not available
    opts = {
        "decode_responses": True,
        "socket_timeout": DEFAULT_SOCKET_TIMEOUT,
        "socket_connect_timeout": DEFAULT_SOCKET_CONNECT_TIMEOUT,
        "socket_keepalive": DEFAULT_SOCKET_KEEPALIVE_INTERVAL > 0,
        **kwargs
    }

    if opts["socket_keepalive"]:
        keepalive_opts = {}
        if hasattr(socket, "TCP_KEEPIDLE"):
            keepalive_opts[socket.TCP_KEEPIDLE] = DEFAULT_SOCKET_KEEPALIVE_INTERVAL
        if hasattr(socket, "TCP_KEEPINTVL"):
            keepalive_opts[socket.TCP_KEEPINTVL] = max(1, DEFAULT_SOCKET_KEEPALIVE_INTERVAL // 3)
        if hasattr(socket, "TCP_KEEPCNT"):
            keepalive_opts[socket.TCP_KEEPCNT] = 3
        if keepalive_opts:
            opts["socket_keepalive_options"] = keepalive_opts

    return redis.from_url(DEFAULT_REDIS_URL, **opts)


def _build_redis_client_from_config(config: RedisConfig, **kwargs) -> redis.Redis:
    """Build Redis client from RedisConfig"""
    opts = config.get_connection_kwargs()
    opts.update(kwargs)  # Allow overrides

    # Add socket keepalive options
    if config.socket_keepalive:
        keepalive_opts = config.get_socket_keepalive_options()
        if keepalive_opts:
            opts["socket_keepalive_options"] = keepalive_opts

    return redis.from_url(config.redis_url, **opts)


async def init_app_redis(app, config: Optional[RedisConfig] = None, **kwargs) -> redis.Redis:
    """
    Per-app Redis client for FastAPI lifespan.
    Usage: await init_app_redis(app)
    Sets app.state.redis, app.state.redis_circuit_breaker, and app.state.redis_retry_config.
    """
    # Store config in app state
    if config:
        app.state.redis_config = config
    elif not hasattr(app.state, "redis_config") and CONFIG_AVAILABLE:
        app.state.redis_config = RedisConfig()

    config = getattr(app.state, "redis_config", None)

    # Initialize circuit breaker for this app
    if not hasattr(app.state, "redis_circuit_breaker"):
        if RELIABILITY_AVAILABLE and ReliabilityConfigs:
            cb_config = ReliabilityConfigs.redis_circuit_breaker("app")
            app.state.redis_circuit_breaker = get_circuit_breaker("redis_app", cb_config)
        else:
            app.state.redis_circuit_breaker = FallbackCircuitBreaker("redis_app")

    # Initialize retry config for this app
    if not hasattr(app.state, "redis_retry_config"):
        if RELIABILITY_AVAILABLE and ReliabilityConfigs:
            app.state.redis_retry_config = ReliabilityConfigs.redis_retry()
        else:
            app.state.redis_retry_config = FallbackRetryConfig()

    # Check if Redis client already exists and is working
    if getattr(app.state, "redis", None) is not None:
        try:
            # Only proceed if circuit breaker allows it
            if not app.state.redis_circuit_breaker.can_execute():
                log.warning(f"Circuit breaker preventing Redis ping.")
                app.state.redis = None
            else:
                # Test connection with retry
                async def test_ping():
                    return await app.state.redis.ping()

                if RELIABILITY_AVAILABLE:
                    await retry_async(test_ping, retry_config=app.state.redis_retry_config, context="Redis app ping")
                else:
                    await fallback_retry_async(test_ping, retry_config=app.state.redis_retry_config,
                                               context="Redis app ping")

                app.state.redis_circuit_breaker.record_success()
                log.info("App Redis client already initialized and ping OK.")
                return app.state.redis
        except Exception as e:
            app.state.redis_circuit_breaker.record_failure(str(e))
            app.state.redis = None

    # Create new Redis client
    if config:
        app.state.redis = _build_redis_client_from_config(config, **kwargs)
    else:
        app.state.redis = _build_redis_client(**kwargs)

    # Test connection with retry
    try:
        async def test_ping():
            return await app.state.redis.ping()

        if RELIABILITY_AVAILABLE:
            await retry_async(test_ping, retry_config=app.state.redis_retry_config, context="Redis app initial ping")
        else:
            await fallback_retry_async(test_ping, retry_config=app.state.redis_retry_config,
                                       context="Redis app initial ping")

        app.state.redis_circuit_breaker.record_success()
        log.info("FastAPI app.state.redis client connected.")
    except Exception as e:
        app.state.redis_circuit_breaker.record_failure(str(e))
        log.error(f"Failed to initialize app Redis client: {e}")
        app.state.redis = None
        raise

    return app.state.redis


async def close_app_redis(app) -> None:
    client = getattr(app.state, "redis", None)  # Renamed to avoid shadowing global redis_client
    if client:
        try:
            await client.aclose()
            log.info("FastAPI app.state.redis client closed.")
        except Exception as e:
            log.warning(f"Error closing app.state.redis: {e}", exc_info=True)
        finally:
            app.state.redis = None


def get_app_redis(app) -> redis.Redis:
    client = getattr(app.state, "redis", None)  # Renamed to avoid shadowing global redis_client
    if client is None:
        raise RuntimeError("app.state.redis not initialized. Did you call init_app_redis() in lifespan?")
    return client


def get_app_circuit_breaker(app) -> Union[CircuitBreaker, FallbackCircuitBreaker]:
    if not hasattr(app.state, "redis_circuit_breaker"):
        if RELIABILITY_AVAILABLE and ReliabilityConfigs:
            cb_config = ReliabilityConfigs.redis_circuit_breaker("app")
            app.state.redis_circuit_breaker = get_circuit_breaker("redis_app", cb_config)
        else:
            app.state.redis_circuit_breaker = FallbackCircuitBreaker("redis_app")
    return app.state.redis_circuit_breaker


def get_app_retry_config(app) -> Union[RetryConfig, FallbackRetryConfig]:
    if not hasattr(app.state, "redis_retry_config"):
        if RELIABILITY_AVAILABLE and ReliabilityConfigs:
            app.state.redis_retry_config = ReliabilityConfigs.redis_retry()
        else:
            app.state.redis_retry_config = FallbackRetryConfig()
    return app.state.redis_retry_config


# -----------------------------------------------------------------------------
# Context Managers for Improved Error Handling
# -----------------------------------------------------------------------------
@asynccontextmanager
async def redis_operation(
        operation_name: str,
        r: Optional[redis.Redis] = None,
        circuit_breaker: Optional[Union[CircuitBreaker, FallbackCircuitBreaker]] = None,
        retry_config: Optional[Union[RetryConfig, FallbackRetryConfig]] = None  # Reserved for future use
) -> AsyncIterator[redis.Redis]:
    """Context manager for Redis operations with circuit breaker support. Retry is handled by callers."""
    _ = retry_config  # Reserved for future use
    r = r or get_global_client()
    circuit_breaker = circuit_breaker or get_global_circuit_breaker()

    # Check circuit breaker
    if not circuit_breaker.can_execute():
        log.warning(f"Circuit breaker preventing {operation_name}.")
        raise CircuitBreakerOpenError(f"Circuit breaker is open for Redis operations ({operation_name})")

    try:
        yield r
        # Record success if we get here
        circuit_breaker.record_success()
    except Exception as e:
        # Record failure
        circuit_breaker.record_failure(str(e))
        log.warning(f"Redis operation '{operation_name}' failed: {e}")
        raise


# -----------------------------------------------------------------------------
# Lazy Proxy (legacy support)
# -----------------------------------------------------------------------------
class _RedisProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_global_client(), name)


redis_client: _RedisProxy = _RedisProxy()


# -----------------------------------------------------------------------------
# Enhanced KV Operations with Circuit Breaker and Retry
# -----------------------------------------------------------------------------
async def ping(r: Optional[redis.Redis] = None) -> bool:
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    # Define ping operation with circuit breaker
    async def _ping_operation():
        if not circuit_breaker.can_execute():
            log.warning(f"Circuit breaker preventing Redis PING.")
            return False

        try:
            result = await r.ping()
            circuit_breaker.record_success()
            return result
        except Exception as e:
            circuit_breaker.record_failure(str(e))
            raise

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            return await retry_async(_ping_operation, retry_config=retry_config, context="Redis PING")
        else:
            return await fallback_retry_async(_ping_operation, retry_config=retry_config, context="Redis PING")
    except (RedisError, OSError, CircuitBreakerOpenError):  # Redis connection or circuit breaker errors
        return False


async def safe_get(key: str, r: Optional[redis.Redis] = None) -> Optional[str]:
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    start_time = time.time()

    # Define get operation with circuit breaker
    async def _get_operation():
        async with redis_operation(f"GET {key}", r, circuit_breaker):
            return await r.get(key)

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            result = await retry_async(_get_operation, retry_config=retry_config, context=f"Redis GET {key}")
        else:
            result = await fallback_retry_async(_get_operation, retry_config=retry_config, context=f"Redis GET {key}")

        # Latency monitoring
        elapsed_ms = (time.time() - start_time) * 1000
        threshold = _get_slow_command_threshold(key)
        if elapsed_ms > threshold:
            log.warning(f"[SLOW REDIS] GET took {elapsed_ms:.1f}ms: {key[:100]}")

        return result
    except Exception as e:
        log.warning(f"Redis GET failed for '{key}': {e}")
        return None


async def safe_set(
        key: str,
        value: Union[str, bytes, int, float],
        ttl_seconds: Optional[int] = None,
        r: Optional[redis.Redis] = None,
        nx: bool = False,
        xx: bool = False
) -> bool:
    """
    Set a value in Redis with circuit breaker and retry support.

    Args:
        key: Redis key
        value: Value to set
        ttl_seconds: Optional TTL in seconds
        r: Optional Redis client instance
        nx: Only set if key doesn't exist (SET IF NOT EXISTS)
        xx: Only set if key exists (SET IF EXISTS)

    Returns:
        True if the key was set, False otherwise
    """
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    start_time = time.time()

    # Define set operation with circuit breaker
    async def _set_operation():
        async with redis_operation(f"SET {key} NX={nx} XX={xx}", r, circuit_breaker):
            # For simple SET without conditions
            if not nx and not xx and not ttl_seconds:
                await r.set(key, value)
                return True

            # For SET with TTL but no conditions
            elif not nx and not xx and ttl_seconds:
                await r.setex(key, ttl_seconds, value)
                return True

            # For conditional SET operations
            else:
                # Build kwargs
                kwargs = {}
                if ttl_seconds:
                    kwargs['ex'] = ttl_seconds
                if nx:
                    kwargs['nx'] = True
                if xx:
                    kwargs['xx'] = True

                set_result = await r.set(key, value, **kwargs)

                # Redis returns:
                # - True/OK for successful SET
                # - None for failed NX/XX condition
                return set_result is not None

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            result = await retry_async(_set_operation, retry_config=retry_config, context=f"Redis SET {key}")
        else:
            result = await fallback_retry_async(_set_operation, retry_config=retry_config, context=f"Redis SET {key}")

        # Latency monitoring
        elapsed_ms = (time.time() - start_time) * 1000
        threshold = _get_slow_command_threshold(key)
        if elapsed_ms > threshold:
            log.warning(f"[SLOW REDIS] SET took {elapsed_ms:.1f}ms: {key[:100]}")

        return result
    except Exception as e:
        log.warning(f"Redis SET failed for '{key}': {e}")
        return False


async def safe_delete(*keys: str, r: Optional[redis.Redis] = None) -> int:
    if not keys:
        return 0

    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    # Define delete operation with circuit breaker
    async def _delete_operation():
        async with redis_operation(f"DELETE {keys}", r, circuit_breaker):
            return await r.delete(*keys)

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            return await retry_async(_delete_operation, retry_config=retry_config, context=f"Redis DELETE {keys}")
        else:
            return await fallback_retry_async(_delete_operation, retry_config=retry_config,
                                              context=f"Redis DELETE {keys}")
    except Exception as e:
        log.warning(f"Redis DELETE failed for {keys}: {e}")
        return 0


async def exists(key: str, r: Optional[redis.Redis] = None) -> bool:
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    # Define exists operation with circuit breaker
    async def _exists_operation():
        async with redis_operation(f"EXISTS {key}", r, circuit_breaker):
            return bool(await r.exists(key))

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            return await retry_async(_exists_operation, retry_config=retry_config, context=f"Redis EXISTS {key}")
        else:
            return await fallback_retry_async(_exists_operation, retry_config=retry_config,
                                              context=f"Redis EXISTS {key}")
    except Exception as e:
        log.warning(f"Redis EXISTS failed for '{key}': {e}")
        return False


async def expire(key: str, ttl_seconds: int, r: Optional[redis.Redis] = None) -> bool:
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    # Define expire operation with circuit breaker
    async def _expire_operation():
        async with redis_operation(f"EXPIRE {key}", r, circuit_breaker):
            return await r.expire(key, ttl_seconds)

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            return await retry_async(_expire_operation, retry_config=retry_config, context=f"Redis EXPIRE {key}")
        else:
            return await fallback_retry_async(_expire_operation, retry_config=retry_config,
                                              context=f"Redis EXPIRE {key}")
    except Exception as e:
        log.warning(f"Redis EXPIRE failed for '{key}': {e}")
        return False


# -----------------------------------------------------------------------------
# Enhanced Hash Operations
# -----------------------------------------------------------------------------
async def hget(key: str, field: str, r: Optional[redis.Redis] = None) -> Optional[str]:
    """
    Get a single field from a hash.

    Args:
        key: Redis key
        field: Field name in the hash
        r: Optional Redis client instance

    Returns:
        Field value or None if not found
    """
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    # Define hget operation with circuit breaker
    async def _hget_operation():
        async with redis_operation(f"HGET {key}.{field}", r, circuit_breaker):
            return await r.hget(key, field)

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            return await retry_async(_hget_operation, retry_config=retry_config, context=f"Redis HGET {key}.{field}")
        else:
            return await fallback_retry_async(_hget_operation, retry_config=retry_config,
                                              context=f"Redis HGET {key}.{field}")
    except Exception as e:
        log.warning(f"Redis HGET failed for '{key}.{field}': {e}")
        return None


async def hgetall(key: str, r: Optional[redis.Redis] = None) -> Dict[str, Any]:
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    start_time = time.time()

    # Define hgetall operation with circuit breaker
    async def _hgetall_operation():
        async with redis_operation(f"HGETALL {key}", r, circuit_breaker):
            return await r.hgetall(key)

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            result = await retry_async(_hgetall_operation, retry_config=retry_config, context=f"Redis HGETALL {key}")
        else:
            result = await fallback_retry_async(_hgetall_operation, retry_config=retry_config,
                                              context=f"Redis HGETALL {key}")

        # Latency monitoring (HGETALL can be slow with large hashes)
        elapsed_ms = (time.time() - start_time) * 1000
        threshold = _get_slow_command_threshold(key)
        if elapsed_ms > threshold:
            field_count = len(result) if result else 0
            log.warning(f"[SLOW REDIS] HGETALL took {elapsed_ms:.1f}ms: {key[:100]} ({field_count} fields)")

        return result
    except Exception as e:
        log.warning(f"Redis HGETALL failed for '{key}': {e}")
        return {}


async def hset(key: str, mapping: Dict[str, Any], r: Optional[redis.Redis] = None) -> int:
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    # Define hset operation with circuit breaker
    async def _hset_operation():
        async with redis_operation(f"HSET {key}", r, circuit_breaker):
            return await r.hset(key, mapping=mapping)

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            return await retry_async(_hset_operation, retry_config=retry_config, context=f"Redis HSET {key}")
        else:
            return await fallback_retry_async(_hset_operation, retry_config=retry_config, context=f"Redis HSET {key}")
    except Exception as e:
        log.warning(f"Redis HSET failed for '{key}': {e}")
        return 0


async def hdel(key: str, *fields: str, r: Optional[redis.Redis] = None) -> int:
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    # Define hdel operation with circuit breaker
    async def _hdel_operation():
        async with redis_operation(f"HDEL {key}", r, circuit_breaker):
            return await r.hdel(key, *fields)

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            return await retry_async(_hdel_operation, retry_config=retry_config, context=f"Redis HDEL {key}")
        else:
            return await fallback_retry_async(_hdel_operation, retry_config=retry_config, context=f"Redis HDEL {key}")
    except Exception as e:
        log.warning(f"Redis HDEL failed for '{key}': {e}")
        return 0


async def hincrby(key: str, field: str, amount: int = 1, r: Optional[redis.Redis] = None) -> int:
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    # Define hincrby operation with circuit breaker
    async def _hincrby_operation():
        async with redis_operation(f"HINCRBY {key}.{field}", r, circuit_breaker):
            return await r.hincrby(key, field, amount)

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            return await retry_async(_hincrby_operation, retry_config=retry_config,
                                     context=f"Redis HINCRBY {key}.{field}")
        else:
            return await fallback_retry_async(_hincrby_operation, retry_config=retry_config,
                                              context=f"Redis HINCRBY {key}.{field}")
    except Exception as e:
        log.warning(f"Redis HINCRBY failed for '{key}.{field}': {e}")
        return 0


def pipeline(transaction: bool = False, r: Optional[redis.Redis] = None):
    r = r or get_global_client()
    return r.pipeline(transaction=transaction)


# -----------------------------------------------------------------------------
# Enhanced Pub/Sub Helpers
# -----------------------------------------------------------------------------
async def publish(channel: str, message: Union[Dict[str, Any], str, bytes], r: Optional[redis.Redis] = None) -> int:
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    payload = json.dumps(message) if isinstance(message, dict) else message

    # Define publish operation with circuit breaker
    async def _publish_operation():
        async with redis_operation(f"PUBLISH {channel}", r, circuit_breaker):
            return await r.publish(channel, payload)

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            return await retry_async(_publish_operation, retry_config=retry_config, context=f"Redis PUBLISH {channel}")
        else:
            return await fallback_retry_async(_publish_operation, retry_config=retry_config,
                                              context=f"Redis PUBLISH {channel}")
    except Exception as e:
        log.warning(f"Redis PUBLISH failed on '{channel}': {e}")
        return 0


async def subscribe(channel: str, r: Optional[redis.Redis] = None) -> AsyncIterator[Union[Dict[str, Any], str]]:
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()

    # Check circuit breaker before subscribing
    if not circuit_breaker.can_execute():
        log.warning(f"Circuit breaker preventing SUBSCRIBE to '{channel}'.")
        raise CircuitBreakerOpenError(f"Circuit breaker is open for Redis operations (SUBSCRIBE {channel})")

    # Create PubSub client
    try:
        pubsub = r.pubsub(ignore_subscribe_messages=True)
        await pubsub.subscribe(channel)
        circuit_breaker.record_success()
        log.info(f"Subscribed to Redis channel '{channel}'")

        try:
            while True:
                # Check circuit breaker periodically
                if not circuit_breaker.can_execute():
                    log.warning(f"Circuit breaker interrupting subscription to '{channel}'.")
                    break

                try:
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if msg and msg.get("type") == "message":
                        circuit_breaker.record_success()
                        data = msg["data"]
                        if isinstance(data, (bytes, str)):
                            try:
                                yield json.loads(data)
                            except json.JSONDecodeError:
                                yield data
                    else:
                        await asyncio.sleep(0.1)
                except Exception as e:
                    circuit_breaker.record_failure(str(e))
                    log.warning(f"Error getting message from '{channel}': {e}")
                    await asyncio.sleep(1.0)  # Delay before retry

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            log.info(f"Unsubscribed from Redis channel '{channel}'")

    except Exception as e:
        circuit_breaker.record_failure(str(e))
        log.error(f"Failed to subscribe to '{channel}': {e}")
        raise


# -----------------------------------------------------------------------------
# Enhanced Stream Helpers
# -----------------------------------------------------------------------------
async def xadd(
        stream: str,
        payload: Dict[str, Any],
        maxlen: Optional[int] = 1000,
        approximate_maxlen: bool = True,
        r: Optional[redis.Redis] = None
) -> Optional[str]:
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    start_time = time.time()

    # Define xadd operation with circuit breaker
    async def _xadd_operation():
        async with redis_operation(f"XADD {stream}", r, circuit_breaker):
            return await r.xadd(
                name=stream,
                fields={"data": json.dumps(payload, separators=(",", ":"))},
                maxlen=maxlen,
                approximate=approximate_maxlen
            )

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            result = await retry_async(_xadd_operation, retry_config=retry_config, context=f"Redis XADD {stream}")
        else:
            result = await fallback_retry_async(_xadd_operation, retry_config=retry_config,
                                              context=f"Redis XADD {stream}")

        # Latency monitoring
        elapsed_ms = (time.time() - start_time) * 1000
        threshold = _get_slow_command_threshold(stream)
        if elapsed_ms > threshold:
            log.warning(f"[SLOW REDIS] XADD took {elapsed_ms:.1f}ms: stream={stream[:50]}")

        return result
    except Exception as e:
        log.warning(f"Redis XADD failed for '{stream}': {e}")
        return None


async def xreadgroup(
        stream: str,
        group: str,
        consumer: str,
        last_id: str = ">",
        count: int = 10,
        block_ms: Optional[int] = 5000,
        r: Optional[redis.Redis] = None
) -> List[tuple[str, Dict[str, Any]]]:
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    # Define xreadgroup operation with circuit breaker
    async def _xreadgroup_operation():
        async with redis_operation(f"XREADGROUP {stream}/{group}", r, circuit_breaker):
            raw = await r.xreadgroup(
                groupname=group, consumername=consumer,
                streams={stream: last_id}, count=count, block=block_ms
            )

            results: List[tuple[str, Dict[str, Any]]] = []
            for _, msgs in raw:
                for mid_b, data_map in msgs:
                    mid = mid_b.decode("utf-8") if isinstance(mid_b, bytes) else str(mid_b)
                    data_key = b"data" if isinstance(next(iter(data_map.keys()), b""), bytes) else "data"
                    b = data_map.get(data_key)
                    if b:
                        try:
                            data_str = b.decode("utf-8") if isinstance(b, bytes) else b
                            results.append((mid, json.loads(data_str)))
                        except json.JSONDecodeError:
                            log.error(f"XREADGROUP JSON decode error for '{stream}' msg {mid}")
            return results

    # Execute with retry - only retry ConnectionErrors, not empty results
    try:
        if RELIABILITY_AVAILABLE:
            return await retry_async(_xreadgroup_operation, retry_config=retry_config,
                                     context=f"Redis XREADGROUP {stream}/{group}")
        else:
            return await fallback_retry_async(_xreadgroup_operation, retry_config=retry_config,
                                              context=f"Redis XREADGROUP {stream}/{group}")
    except Exception as e:
        log.warning(f"Redis XREADGROUP failed for '{stream}': {e}")
        return []


async def xack(stream: str, group: str, *message_ids: str, r: Optional[redis.Redis] = None) -> int:
    if not message_ids:
        return 0

    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    # Define xack operation with circuit breaker
    async def _xack_operation():
        async with redis_operation(f"XACK {stream}/{group}", r, circuit_breaker):
            return await r.xack(stream, group, *message_ids)

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            return await retry_async(_xack_operation, retry_config=retry_config, context=f"Redis XACK {stream}/{group}")
        else:
            return await fallback_retry_async(_xack_operation, retry_config=retry_config,
                                              context=f"Redis XACK {stream}/{group}")
    except Exception as e:
        log.warning(f"Redis XACK failed for '{stream}/{group}': {e}")
        return 0


async def xgroup_create_mkstream(
        stream: str,
        group: str,
        start_id: str = "0",
        r: Optional[redis.Redis] = None
) -> bool:
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()
    retry_config = get_global_retry_config()

    # Define xgroup_create operation with circuit breaker
    async def _xgroup_create_operation():
        async with redis_operation(f"XGROUP CREATE {stream}/{group}", r, circuit_breaker):
            try:
                await r.xgroup_create(name=stream, groupname=group, id=start_id, mkstream=True)
                return True
            except ResponseError as resp_err:
                if "BUSYGROUP" in str(resp_err).upper():
                    return True
                raise

    # Execute with retry
    try:
        if RELIABILITY_AVAILABLE:
            result = await retry_async(
                _xgroup_create_operation,
                retry_config=retry_config,
                context=f"Redis XGROUP CREATE {stream}/{group}"
            )
        else:
            result = await fallback_retry_async(
                _xgroup_create_operation,
                retry_config=retry_config,
                context=f"Redis XGROUP CREATE {stream}/{group}"
            )
        log.info(f"Stream group '{group}' ensured for '{stream}'")
        return result
    except Exception as e:
        log.error(f"Redis XGROUP create error for '{stream}': {e}")
        return False


# -----------------------------------------------------------------------------
# Health and Diagnostics
# -----------------------------------------------------------------------------
async def health_check(r: Optional[redis.Redis] = None) -> Dict[str, Any]:
    """
    Comprehensive health check for Redis with circuit breaker metrics.
    Returns health status and detailed diagnostics.
    """
    r = r or get_global_client()
    circuit_breaker = get_global_circuit_breaker()

    try:
        # Simple ping to check if Redis is responsive
        ping_result = await ping(r)

        # Get circuit breaker metrics
        circuit_metrics = circuit_breaker.get_metrics()

        # Consider healthy if ping succeeds
        is_healthy = ping_result

        details = {
            "ping_successful": ping_result,
            "is_healthy": is_healthy,
            "circuit_breaker": circuit_metrics
        }

        # Add Redis info if ping succeeded
        if ping_result:
            try:
                info = await r.info()
                details["redis_version"] = info.get("redis_version")
                details["connected_clients"] = info.get("connected_clients")
                details["used_memory_human"] = info.get("used_memory_human")
                details["total_connections_received"] = info.get("total_connections_received")
            except Exception as e:
                details["info_error"] = str(e)

        return details
    except Exception as e:
        log.error(f"Error during Redis health check: {e}", exc_info=True)
        return {
            "is_healthy": False,
            "error": str(e),
            "circuit_breaker": circuit_breaker.get_metrics() if circuit_breaker else None
        }


# =============================================================================
# Configuration-based Factory Functions
# =============================================================================
def create_redis_client_from_config(config: RedisConfig) -> redis.Redis:
    """Create a Redis client from RedisConfig"""
    return _build_redis_client_from_config(config)


async def create_and_test_redis_client(config: Optional[RedisConfig] = None) -> redis.Redis:
    """Create a Redis client and test the connection"""
    if config:
        client = create_redis_client_from_config(config)
    else:
        client = _build_redis_client()

    # Test connection
    await client.ping()
    return client


# =============================================================================
# FastAPI Convenience Aliases
# =============================================================================
init = init_app_redis
close = close_app_redis

# =============================================================================
# EOF
# =============================================================================