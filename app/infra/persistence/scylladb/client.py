# =============================================================================
# File: app/infra/persistence/scylladb/client.py
# Description: State-of-the-art async ScyllaDB client using scylla-driver
# =============================================================================
# • Native scylla-driver with shard awareness and tablet awareness
# • True async with execute_async (no run_in_executor)
# • Speculative execution for reduced tail latency
# • Circuit breaker and retry integration
# • Prepared statements cache with LRU eviction
# • Connection pooling metrics and health monitoring
# • RateLimitReached error handling (ScyllaDB 5.1+)
# =============================================================================

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple, Union, TypeVar, Callable
from contextlib import asynccontextmanager
from collections import OrderedDict
import logging

# ScyllaDB driver imports (scylla-driver is a drop-in replacement for cassandra-driver)
try:
    from cassandra.cluster import (
        Cluster,
        Session,
        ExecutionProfile,
        EXEC_PROFILE_DEFAULT,
        ResponseFuture,
    )
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.policies import (
        DCAwareRoundRobinPolicy,
        TokenAwarePolicy,
        ConstantSpeculativeExecutionPolicy,
        RetryPolicy as CassandraRetryPolicy,
        ConstantReconnectionPolicy,
        HostDistance,
    )
    from cassandra.query import (
        PreparedStatement,
        SimpleStatement,
        ConsistencyLevel as CassandraConsistencyLevel,
        dict_factory,
    )
    from cassandra.pool import Host
    from cassandra import (
        OperationTimedOut,
        Unavailable,
        ReadTimeout,
        WriteTimeout,
    )
    from cassandra.io.asyncioreactor import AsyncioConnection

    # ScyllaDB-specific: RateLimitReached error (ScyllaDB 5.1+)
    try:
        from cassandra import RateLimitReached

        RATE_LIMIT_AVAILABLE = True
    except ImportError:
        RateLimitReached = Exception
        RATE_LIMIT_AVAILABLE = False

    SCYLLA_DRIVER_AVAILABLE = True
except ImportError:
    SCYLLA_DRIVER_AVAILABLE = False
    Cluster = None
    Session = None
    ExecutionProfile = None
    EXEC_PROFILE_DEFAULT = None
    ResponseFuture = None
    PlainTextAuthProvider = None
    DCAwareRoundRobinPolicy = None
    TokenAwarePolicy = None
    ConstantSpeculativeExecutionPolicy = None
    CassandraRetryPolicy = None
    ConstantReconnectionPolicy = None
    HostDistance = None
    PreparedStatement = None
    SimpleStatement = None
    CassandraConsistencyLevel = None
    dict_factory = None
    Host = None
    OperationTimedOut = Exception
    Unavailable = Exception
    ReadTimeout = Exception
    WriteTimeout = Exception
    AsyncioConnection = None
    RateLimitReached = Exception
    RATE_LIMIT_AVAILABLE = False

# Import configuration
try:
    from app.config.scylla_config import ScyllaConfig, ConsistencyLevel, CircuitBreakerState

    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    ScyllaConfig = None
    ConsistencyLevel = None
    CircuitBreakerState = None

# Import reliability infrastructure
try:
    from app.config.reliability_config import (
        CircuitBreakerConfig,
        RetryConfig,
    )
    from app.infra.reliability.circuit_breaker import (
        CircuitBreaker,
        get_circuit_breaker,
        CircuitBreakerOpenError,
    )
    from app.infra.reliability.retry import retry_async

    RELIABILITY_AVAILABLE = True
except ImportError:
    RELIABILITY_AVAILABLE = False
    CircuitBreakerConfig = None
    RetryConfig = None
    CircuitBreaker = None
    get_circuit_breaker = None
    CircuitBreakerOpenError = Exception
    retry_async = None

# Import logging
try:
    from app.config.logging_config import get_logger

    log = get_logger("wellwon.infra.scylladb")
except ImportError:
    log = logging.getLogger("wellwon.infra.scylladb")

T = TypeVar('T')


# =============================================================================
# Consistency Level Mapping
# =============================================================================
def map_consistency_level(level: Union[str, ConsistencyLevel]) -> int:
    """Map ConsistencyLevel enum to cassandra-driver consistency level."""
    if SCYLLA_DRIVER_AVAILABLE and CassandraConsistencyLevel:
        level_str = level.value if hasattr(level, 'value') else str(level)
        return getattr(CassandraConsistencyLevel, level_str, CassandraConsistencyLevel.LOCAL_ONE)
    return 10  # Default to LOCAL_ONE


# =============================================================================
# Fallback Implementations
# =============================================================================
if not RELIABILITY_AVAILABLE:
    class FallbackCircuitBreaker:
        """Minimal circuit breaker for when reliability package is not available."""

        def __init__(self, name: str):
            self.name = name
            self._state = "CLOSED"

        def can_execute(self) -> bool:
            return self._state != "OPEN"

        def record_success(self) -> None:
            self._state = "CLOSED"

        def record_failure(self, error_details: Optional[str] = None) -> None:
            log.warning(f"Circuit breaker {self.name} recording failure: {error_details}")

        def get_metrics(self) -> Dict[str, Any]:
            return {"name": self.name, "state": self._state}


    class FallbackRetryConfig:
        """Minimal retry config for when reliability package is not available."""

        def __init__(self):
            self.max_attempts = 3
            self.initial_delay_ms = 100
            self.max_delay_ms = 2000
            self.backoff_factor = 2.0


    async def fallback_retry_async(
            func: Callable[..., Any],
            *args,
            retry_config: Optional[Any] = None,
            context: str = "operation",
            **kwargs
    ) -> Any:
        """Minimal retry implementation."""
        config = retry_config or FallbackRetryConfig()
        last_exception = None

        for attempt in range(1, config.max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt >= config.max_attempts:
                    log.warning(f"Retry exhausted for {context} after {attempt} attempts")
                    raise

                delay_ms = min(
                    config.initial_delay_ms * (config.backoff_factor ** (attempt - 1)),
                    config.max_delay_ms
                )
                await asyncio.sleep(delay_ms / 1000)

        raise last_exception if last_exception else RuntimeError("Unexpected retry failure")


# =============================================================================
# ScyllaDB Reliability Configuration
# =============================================================================
class ScyllaReliabilityConfigs:
    """Pre-configured reliability settings for ScyllaDB operations."""

    @staticmethod
    def scylla_circuit_breaker(name: str = "scylla") -> CircuitBreakerConfig:
        """Circuit breaker config for ScyllaDB."""
        if RELIABILITY_AVAILABLE and CircuitBreakerConfig:
            return CircuitBreakerConfig(
                name=f"scylla_{name}",
                failure_threshold=5,
                success_threshold=3,
                reset_timeout_seconds=30,
                half_open_max_calls=3,
                window_size=20,
                failure_rate_threshold=0.5
            )
        return None

    @staticmethod
    def scylla_retry() -> RetryConfig:
        """Retry config for ScyllaDB operations."""
        if RELIABILITY_AVAILABLE and RetryConfig:
            return RetryConfig(
                max_attempts=3,
                initial_delay_ms=100,
                max_delay_ms=2000,
                backoff_factor=2.0,
                jitter=True,
                jitter_type="full",
                retry_condition=lambda err: ScyllaReliabilityConfigs._should_retry_scylla(err)
            )
        return None

    @staticmethod
    def _should_retry_scylla(error: Exception) -> bool:
        """Determine if ScyllaDB error should be retried."""
        if error is None:
            return False

        # Don't retry rate limit errors - back off instead
        if RATE_LIMIT_AVAILABLE and isinstance(error, RateLimitReached):
            return False

        error_str = str(error).lower()

        # Retry on timeout errors
        if any(term in error_str for term in ["timeout", "timed out", "deadline"]):
            return True

        # Retry on availability errors
        if any(term in error_str for term in ["unavailable", "no host available"]):
            return True

        # Retry on overloaded errors
        if "overloaded" in error_str:
            return True

        # Don't retry on syntax or schema errors
        if any(term in error_str for term in ["syntax", "invalid", "keyspace", "table"]):
            return False

        return True


# =============================================================================
# Async Future Wrapper
# =============================================================================
class AsyncResultWrapper:
    """
    Wraps cassandra ResponseFuture for native async/await support.

    This avoids run_in_executor overhead by using the driver's native async.
    """

    def __init__(self, future: ResponseFuture):
        self._future = future
        self._loop = asyncio.get_event_loop()

    def __await__(self):
        return self._get_result().__await__()

    async def _get_result(self) -> List[Dict[str, Any]]:
        """Wait for result using asyncio Event."""
        event = asyncio.Event()
        result_holder = {"result": None, "error": None}

        def on_success(rows):
            result_holder["result"] = rows
            self._loop.call_soon_threadsafe(event.set)

        def on_error(exc):
            result_holder["error"] = exc
            self._loop.call_soon_threadsafe(event.set)

        self._future.add_callbacks(on_success, on_error)

        await event.wait()

        if result_holder["error"]:
            raise result_holder["error"]

        return list(result_holder["result"]) if result_holder["result"] else []


# =============================================================================
# ScyllaDB Client
# =============================================================================
class ScyllaClient:
    """
    State-of-the-art async ScyllaDB client with scylla-driver.

    Features:
    - Native async with execute_async (no thread pool overhead)
    - Shard awareness - routes to correct shard within node
    - Tablet awareness - intelligent routing for tablet-based tables
    - Speculative execution - reduces tail latency
    - Circuit breaker for fault tolerance
    - Retry with exponential backoff
    - Prepared statements cache with LRU eviction
    - RateLimitReached error handling (ScyllaDB 5.1+)
    - Connection pooling metrics
    - Health monitoring with shard stats
    """

    def __init__(
            self,
            config: Optional[ScyllaConfig] = None,
            circuit_breaker: Optional[Union[CircuitBreaker, FallbackCircuitBreaker]] = None,
            retry_config: Optional[Union[RetryConfig, FallbackRetryConfig]] = None,
    ):
        """
        Initialize ScyllaDB client.

        Args:
            config: ScyllaDB configuration
            circuit_breaker: Optional circuit breaker instance
            retry_config: Optional retry configuration
        """
        if not SCYLLA_DRIVER_AVAILABLE:
            raise ImportError(
                "scylla-driver is not installed. "
                "Install it with: pip install scylla-driver"
            )

        # Configuration
        self.config = config or (ScyllaConfig() if CONFIG_AVAILABLE else None)
        if self.config is None:
            raise ValueError("ScyllaConfig is required but not available")

        # Cluster and session
        self._cluster: Optional[Cluster] = None
        self._session: Optional[Session] = None

        # Prepared statements cache with LRU eviction
        self._prepared_statements: OrderedDict[str, PreparedStatement] = OrderedDict()
        self._prepared_lock = asyncio.Lock()
        self._max_prepared_statements = 1000

        # Reliability components
        if circuit_breaker:
            self._circuit_breaker = circuit_breaker
        elif RELIABILITY_AVAILABLE:
            cb_config = ScyllaReliabilityConfigs.scylla_circuit_breaker("client")
            self._circuit_breaker = get_circuit_breaker("scylla_client", cb_config)
        else:
            self._circuit_breaker = FallbackCircuitBreaker("scylla_client")

        if retry_config:
            self._retry_config = retry_config
        elif RELIABILITY_AVAILABLE:
            self._retry_config = ScyllaReliabilityConfigs.scylla_retry()
        else:
            self._retry_config = FallbackRetryConfig()

        # Metrics
        self._query_count = 0
        self._error_count = 0
        self._rate_limit_count = 0
        self._slow_query_threshold_ms = self.config.slow_query_threshold_ms

        # Shard awareness tracking
        self._is_shard_aware = False
        self._shard_stats: Dict[str, Any] = {}

        log.info(f"ScyllaClient initialized for keyspace: {self.config.keyspace}")

    async def connect(self) -> None:
        """Connect to ScyllaDB cluster with shard awareness."""
        if self._session is not None:
            return

        try:
            # Build execution profiles
            read_profile = ExecutionProfile(
                load_balancing_policy=self._create_load_balancing_policy(),
                consistency_level=map_consistency_level(self.config.default_consistency_read),
                request_timeout=self.config.request_timeout,
                row_factory=dict_factory,
                # Speculative execution for reads - reduces tail latency
                speculative_execution_policy=ConstantSpeculativeExecutionPolicy(
                    delay=0.05,  # 50ms delay before speculative retry
                    max_attempts=2
                ) if self.config.token_aware_enabled else None,
            )

            write_profile = ExecutionProfile(
                load_balancing_policy=self._create_load_balancing_policy(),
                consistency_level=map_consistency_level(self.config.default_consistency_write),
                request_timeout=self.config.request_timeout,
                row_factory=dict_factory,
            )

            profiles = {
                EXEC_PROFILE_DEFAULT: read_profile,
                'read': read_profile,
                'write': write_profile,
            }

            # Choose port based on shard awareness setting
            port = self.config.shard_aware_port if self.config.shard_aware_enabled else self.config.port

            # Build cluster options
            cluster_kwargs = {
                'contact_points': self.config.get_contact_points_list(),
                'port': port,
                'execution_profiles': profiles,
                'connect_timeout': self.config.connect_timeout,
                'idle_heartbeat_interval': self.config.idle_heartbeat_interval,
                'idle_heartbeat_timeout': self.config.idle_heartbeat_timeout,
                'reconnection_policy': ConstantReconnectionPolicy(
                    delay=self.config.retry_initial_delay_ms / 1000,
                    max_attempts=self.config.retry_max_attempts
                ),
                'connection_class': AsyncioConnection,
                'executor_threads': self.config.executor_threads,
            }

            # Shard awareness - disable if needed (rare cases)
            if not self.config.shard_aware_enabled:
                cluster_kwargs['shard_aware_options'] = {'disable': True}

            # Authentication
            auth_kwargs = self.config.get_auth_provider_kwargs()
            if auth_kwargs:
                cluster_kwargs['auth_provider'] = PlainTextAuthProvider(**auth_kwargs)

            # SSL
            ssl_context = self.config.get_ssl_context()
            if ssl_context:
                cluster_kwargs['ssl_context'] = ssl_context

            # Protocol version
            if self.config.protocol_version:
                cluster_kwargs['protocol_version'] = self.config.protocol_version

            # Compression
            if self.config.compression_enabled:
                cluster_kwargs['compression'] = True

            # Create cluster
            self._cluster = Cluster(**cluster_kwargs)

            # Connect to keyspace
            loop = asyncio.get_event_loop()
            self._session = await loop.run_in_executor(
                None,
                lambda: self._cluster.connect(self.config.keyspace)
            )

            # Check shard awareness (ScyllaDB-specific feature)
            self._is_shard_aware = self._cluster.is_shard_aware()
            if self._is_shard_aware:
                self._shard_stats = self._cluster.shard_aware_stats()
                log.info(f"Shard awareness: ENABLED, stats: {self._shard_stats}")
            else:
                log.warning("Shard awareness: DISABLED (cluster may not support it)")

            self._circuit_breaker.record_success()
            log.info(
                f"Connected to ScyllaDB cluster: {self.config.contact_points}:{port} "
                f"(shard_aware={self._is_shard_aware})"
            )

        except Exception as e:
            self._circuit_breaker.record_failure(str(e))
            log.error(f"Failed to connect to ScyllaDB: {e}")
            raise

    def _create_load_balancing_policy(self):
        """Create load balancing policy with token awareness."""
        # Base policy - DC-aware round robin
        base_policy = DCAwareRoundRobinPolicy()

        # Wrap with token-aware for shard routing
        if self.config.token_aware_enabled:
            return TokenAwarePolicy(base_policy)

        return base_policy

    async def close(self) -> None:
        """Close connection to ScyllaDB cluster."""
        if self._session:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._session.shutdown)
                log.info("ScyllaDB session closed")
            except Exception as e:
                log.warning(f"Error closing ScyllaDB session: {e}")
            finally:
                self._session = None

        if self._cluster:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._cluster.shutdown)
                log.info("ScyllaDB cluster closed")
            except Exception as e:
                log.warning(f"Error closing ScyllaDB cluster: {e}")
            finally:
                self._cluster = None

        # Clear prepared statements cache
        self._prepared_statements.clear()

    async def execute(
            self,
            query: str,
            parameters: Optional[Union[Dict[str, Any], Tuple, List]] = None,
            consistency: Optional[str] = None,
            timeout: Optional[float] = None,
            execution_profile: str = EXEC_PROFILE_DEFAULT,
            is_idempotent: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Execute a CQL query with native async.

        Args:
            query: CQL query string
            parameters: Query parameters (dict for named, tuple/list for positional)
            consistency: Optional consistency level override
            timeout: Optional timeout override in seconds
            execution_profile: Execution profile name ('read', 'write', or default)
            is_idempotent: Mark query as idempotent for speculative execution

        Returns:
            List of rows as dictionaries
        """
        if self._session is None:
            await self.connect()

        # Check circuit breaker
        if not self._circuit_breaker.can_execute():
            raise CircuitBreakerOpenError("ScyllaDB circuit breaker is open")

        start_time = time.time()

        async def _execute_query():
            nonlocal start_time
            start_time = time.time()

            try:
                # Build statement
                statement = SimpleStatement(query, is_idempotent=is_idempotent)

                # Apply consistency override if specified
                if consistency:
                    statement.consistency_level = map_consistency_level(consistency)

                # Execute with native async
                if parameters:
                    future = self._session.execute_async(
                        statement,
                        parameters,
                        timeout=timeout,
                        execution_profile=execution_profile,
                    )
                else:
                    future = self._session.execute_async(
                        statement,
                        timeout=timeout,
                        execution_profile=execution_profile,
                    )

                # Await result using native async wrapper
                result = await AsyncResultWrapper(future)

                self._query_count += 1
                self._circuit_breaker.record_success()

                return result

            except RateLimitReached as e:
                # ScyllaDB 5.1+ rate limiting
                self._rate_limit_count += 1
                self._error_count += 1
                log.warning(f"Rate limit reached: {e}")
                raise

            except Exception as e:
                self._error_count += 1
                self._circuit_breaker.record_failure(str(e))
                raise

        # Execute with retry
        try:
            if RELIABILITY_AVAILABLE and retry_async:
                result = await retry_async(
                    _execute_query,
                    retry_config=self._retry_config,
                    context=f"ScyllaDB execute: {query[:50]}..."
                )
            else:
                result = await fallback_retry_async(
                    _execute_query,
                    retry_config=self._retry_config,
                    context=f"ScyllaDB execute: {query[:50]}..."
                )

            # Log slow queries
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > self._slow_query_threshold_ms:
                log.warning(f"[SLOW SCYLLA] Query took {elapsed_ms:.1f}ms: {query[:100]}")

            return result

        except Exception as e:
            log.error(f"ScyllaDB execute failed: {e}")
            raise

    async def execute_prepared(
            self,
            query: str,
            parameters: Optional[Union[Dict[str, Any], Tuple, List]] = None,
            consistency: Optional[str] = None,
            timeout: Optional[float] = None,
            execution_profile: str = EXEC_PROFILE_DEFAULT,
            is_idempotent: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Execute a prepared statement with native async.

        Prepared statements are cached for performance.

        Args:
            query: CQL query string
            parameters: Query parameters
            consistency: Optional consistency level override
            timeout: Optional timeout override in seconds
            execution_profile: Execution profile name
            is_idempotent: Mark query as idempotent for speculative execution

        Returns:
            List of rows as dictionaries
        """
        if self._session is None:
            await self.connect()

        # Check circuit breaker
        if not self._circuit_breaker.can_execute():
            raise CircuitBreakerOpenError("ScyllaDB circuit breaker is open")

        # Get or create prepared statement
        prepared = await self._get_prepared_statement(query)

        start_time = time.time()

        async def _execute_prepared():
            nonlocal start_time
            start_time = time.time()

            try:
                # Create bound statement
                if parameters:
                    bound = prepared.bind(parameters)
                else:
                    bound = prepared.bind([])

                # Set idempotent flag
                bound.is_idempotent = is_idempotent

                # Apply consistency override if specified
                if consistency:
                    bound.consistency_level = map_consistency_level(consistency)

                # Execute with native async
                future = self._session.execute_async(
                    bound,
                    timeout=timeout,
                    execution_profile=execution_profile,
                )

                # Await result using native async wrapper
                result = await AsyncResultWrapper(future)

                self._query_count += 1
                self._circuit_breaker.record_success()

                return result

            except RateLimitReached as e:
                self._rate_limit_count += 1
                self._error_count += 1
                log.warning(f"Rate limit reached: {e}")
                raise

            except Exception as e:
                self._error_count += 1
                self._circuit_breaker.record_failure(str(e))
                raise

        # Execute with retry
        try:
            if RELIABILITY_AVAILABLE and retry_async:
                result = await retry_async(
                    _execute_prepared,
                    retry_config=self._retry_config,
                    context=f"ScyllaDB prepared: {query[:50]}..."
                )
            else:
                result = await fallback_retry_async(
                    _execute_prepared,
                    retry_config=self._retry_config,
                    context=f"ScyllaDB prepared: {query[:50]}..."
                )

            # Log slow queries
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > self._slow_query_threshold_ms:
                log.warning(f"[SLOW SCYLLA] Prepared query took {elapsed_ms:.1f}ms: {query[:100]}")

            return result

        except Exception as e:
            log.error(f"ScyllaDB prepared execute failed: {e}")
            raise

    async def _get_prepared_statement(self, query: str) -> PreparedStatement:
        """Get or create a prepared statement with LRU eviction."""
        if query in self._prepared_statements:
            # Move to end (most recently used)
            self._prepared_statements.move_to_end(query)
            return self._prepared_statements[query]

        async with self._prepared_lock:
            # Double-check after acquiring lock
            if query in self._prepared_statements:
                self._prepared_statements.move_to_end(query)
                return self._prepared_statements[query]

            try:
                loop = asyncio.get_event_loop()
                prepared = await loop.run_in_executor(
                    None,
                    lambda: self._session.prepare(query)
                )

                # LRU eviction: remove oldest if at capacity
                while len(self._prepared_statements) >= self._max_prepared_statements:
                    oldest_query, _ = self._prepared_statements.popitem(last=False)
                    log.debug(f"Evicted prepared statement (LRU): {oldest_query[:50]}...")

                self._prepared_statements[query] = prepared
                log.debug(
                    f"Prepared statement cached "
                    f"({len(self._prepared_statements)}/{self._max_prepared_statements}): {query[:50]}..."
                )
                return prepared

            except Exception as e:
                log.error(f"Failed to prepare statement: {e}")
                raise

    async def execute_batch(
            self,
            statements: List[Tuple[str, Optional[Union[Dict, Tuple, List]]]],
            batch_type: str = "UNLOGGED",
            consistency: Optional[str] = None,
            timeout: Optional[float] = None,
    ) -> None:
        """
        Execute a batch of statements.

        Args:
            statements: List of (query, parameters) tuples
            batch_type: LOGGED, UNLOGGED, or COUNTER
            consistency: Optional consistency level override
            timeout: Optional timeout override in seconds
        """
        if self._session is None:
            await self.connect()

        if not self._circuit_breaker.can_execute():
            raise CircuitBreakerOpenError("ScyllaDB circuit breaker is open")

        from cassandra.query import BatchStatement, BatchType

        batch_type_map = {
            "LOGGED": BatchType.LOGGED,
            "UNLOGGED": BatchType.UNLOGGED,
            "COUNTER": BatchType.COUNTER,
        }

        async def _execute_batch():
            try:
                batch = BatchStatement(batch_type=batch_type_map.get(batch_type, BatchType.UNLOGGED))

                if consistency:
                    batch.consistency_level = map_consistency_level(consistency)

                for query, params in statements:
                    if params:
                        batch.add(SimpleStatement(query), params)
                    else:
                        batch.add(SimpleStatement(query))

                # Execute with native async
                future = self._session.execute_async(batch, timeout=timeout)
                await AsyncResultWrapper(future)

                self._query_count += len(statements)
                self._circuit_breaker.record_success()

            except RateLimitReached as e:
                self._rate_limit_count += 1
                self._error_count += 1
                raise

            except Exception as e:
                self._error_count += 1
                self._circuit_breaker.record_failure(str(e))
                raise

        try:
            if RELIABILITY_AVAILABLE and retry_async:
                await retry_async(
                    _execute_batch,
                    retry_config=self._retry_config,
                    context="ScyllaDB batch execute"
                )
            else:
                await fallback_retry_async(
                    _execute_batch,
                    retry_config=self._retry_config,
                    context="ScyllaDB batch execute"
                )
        except Exception as e:
            log.error(f"ScyllaDB batch execute failed: {e}")
            raise

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check on ScyllaDB connection.

        Includes shard awareness status and connection pool stats.
        """
        # noinspection SqlNoDataSourceInspection,SqlResolve
        health_query = "SELECT now() FROM system.local"

        try:
            if self._session is None:
                return {
                    "is_healthy": False,
                    "error": "Not connected",
                    "circuit_breaker": self._circuit_breaker.get_metrics(),
                }

            # Execute simple query to check connectivity
            start_time = time.time()
            await self.execute(health_query)
            latency_ms = (time.time() - start_time) * 1000

            # Update shard stats
            if self._cluster:
                self._is_shard_aware = self._cluster.is_shard_aware()
                self._shard_stats = self._cluster.shard_aware_stats() if self._is_shard_aware else {}

            # Get connection pool info
            pool_stats = self._get_connection_pool_stats()

            return {
                "is_healthy": True,
                "latency_ms": round(latency_ms, 2),
                "keyspace": self.config.keyspace,
                "contact_points": self.config.get_contact_points_list(),
                "port": self.config.shard_aware_port if self.config.shard_aware_enabled else self.config.port,
                "query_count": self._query_count,
                "error_count": self._error_count,
                "rate_limit_count": self._rate_limit_count,
                "prepared_statements_cached": len(self._prepared_statements),
                "shard_aware": self._is_shard_aware,
                "shard_stats": self._shard_stats,
                "connection_pool": pool_stats,
                "circuit_breaker": self._circuit_breaker.get_metrics(),
            }

        except Exception as e:
            log.error(f"ScyllaDB health check failed: {e}")
            return {
                "is_healthy": False,
                "error": str(e),
                "circuit_breaker": self._circuit_breaker.get_metrics(),
            }

    def _get_connection_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        if not self._cluster:
            return {}

        stats = {
            "hosts": [],
            "total_connections": 0,
            "total_in_flight": 0,
        }

        try:
            metadata = self._cluster.metadata
            if metadata and metadata.all_hosts():
                for host in metadata.all_hosts():
                    host_info = {
                        "address": str(host.address),
                        "datacenter": host.datacenter,
                        "rack": host.rack,
                        "is_up": host.is_up,
                    }

                    # Get pool for this host if available
                    pool = self._session.get_pool_state() if self._session else None
                    if pool:
                        host_pool = pool.get(host)
                        if host_pool:
                            host_info["open_connections"] = host_pool.open_count
                            host_info["in_flight"] = host_pool.in_flight
                            stats["total_connections"] += host_pool.open_count
                            stats["total_in_flight"] += host_pool.in_flight

                    stats["hosts"].append(host_info)

        except Exception as e:
            log.debug(f"Could not get pool stats: {e}")

        return stats

    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics."""
        return {
            "query_count": self._query_count,
            "error_count": self._error_count,
            "rate_limit_count": self._rate_limit_count,
            "prepared_statements_cached": len(self._prepared_statements),
            "is_connected": self._session is not None,
            "shard_aware": self._is_shard_aware,
            "shard_stats": self._shard_stats,
            "circuit_breaker": self._circuit_breaker.get_metrics(),
        }

    def is_shard_aware(self) -> bool:
        """Check if cluster supports shard awareness."""
        return self._is_shard_aware

    def get_shard_stats(self) -> Dict[str, Any]:
        """
        Get shard awareness statistics.

        Returns dict with host -> {shards_count, connected} mapping.
        Use to verify all shards are connected.
        """
        if self._cluster and self._is_shard_aware:
            self._shard_stats = self._cluster.shard_aware_stats()
        return self._shard_stats

    def verify_all_shards_connected(self) -> bool:
        """
        Verify all shards on all nodes are connected.

        Returns True if connected to all shards of all ScyllaDB nodes.
        """
        stats = self.get_shard_stats()
        if not stats:
            return False

        return all(
            v.get("shards_count", 0) == v.get("connected", 0)
            for v in stats.values()
        )


# =============================================================================
# Global Singleton
# =============================================================================
_GLOBAL_SCYLLA_CLIENT: Optional[ScyllaClient] = None
_CLIENT_INIT_LOCK = asyncio.Lock()


async def init_global_scylla_client(config: Optional[ScyllaConfig] = None) -> ScyllaClient:
    """Initialize global ScyllaDB client singleton."""
    global _GLOBAL_SCYLLA_CLIENT

    if _GLOBAL_SCYLLA_CLIENT is not None:
        return _GLOBAL_SCYLLA_CLIENT

    async with _CLIENT_INIT_LOCK:
        if _GLOBAL_SCYLLA_CLIENT is None:
            _GLOBAL_SCYLLA_CLIENT = ScyllaClient(config)
            await _GLOBAL_SCYLLA_CLIENT.connect()
            log.info("Global ScyllaDB client initialized")

    return _GLOBAL_SCYLLA_CLIENT


async def close_global_scylla_client() -> None:
    """Close global ScyllaDB client."""
    global _GLOBAL_SCYLLA_CLIENT

    if _GLOBAL_SCYLLA_CLIENT is not None:
        await _GLOBAL_SCYLLA_CLIENT.close()
        _GLOBAL_SCYLLA_CLIENT = None
        log.info("Global ScyllaDB client closed")


def get_scylla_client() -> ScyllaClient:
    """Get global ScyllaDB client."""
    if _GLOBAL_SCYLLA_CLIENT is None:
        raise RuntimeError(
            "ScyllaDB client not initialized. "
            "Call init_global_scylla_client() first."
        )
    return _GLOBAL_SCYLLA_CLIENT


# =============================================================================
# Context Manager
# =============================================================================
@asynccontextmanager
async def scylla_client_context(config: Optional[ScyllaConfig] = None):
    """Context manager for ScyllaDB client."""
    client = ScyllaClient(config)
    try:
        await client.connect()
        yield client
    finally:
        await client.close()


# =============================================================================
# FastAPI Integration
# =============================================================================
async def init_app_scylla(app, config: Optional[ScyllaConfig] = None) -> ScyllaClient:
    """Initialize ScyllaDB client for FastAPI app."""
    if hasattr(app.state, 'scylla_client') and app.state.scylla_client is not None:
        return app.state.scylla_client

    client = ScyllaClient(config)
    await client.connect()
    app.state.scylla_client = client
    log.info("FastAPI app.state.scylla_client initialized")
    return client


async def close_app_scylla(app) -> None:
    """Close ScyllaDB client for FastAPI app."""
    client = getattr(app.state, 'scylla_client', None)
    if client:
        await client.close()
        app.state.scylla_client = None
        log.info("FastAPI app.state.scylla_client closed")


def get_app_scylla(app) -> ScyllaClient:
    """Get ScyllaDB client from FastAPI app."""
    client = getattr(app.state, 'scylla_client', None)
    if client is None:
        raise RuntimeError(
            "app.state.scylla_client not initialized. "
            "Did you call init_app_scylla() in lifespan?"
        )
    return client


# =============================================================================
# EOF
# =============================================================================