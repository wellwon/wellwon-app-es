# =============================================================================
# File: app/infra/persistence/scylladb/client.py
# Description: Async ScyllaDB/Cassandra client with circuit breaker, retry,
#              shard-aware routing, and prepared statements cache.
# =============================================================================
# • Production-ready async ScyllaDB client
# • Uses cassandra-driver with asyncio integration
# • Supports shard-aware routing for ScyllaDB
# • Integrated with reliability infrastructure (circuit breaker, retry)
# • Prepared statements cache for performance
# • Health monitoring and metrics
# =============================================================================

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple, Union, TypeVar, Callable
from contextlib import asynccontextmanager
from functools import wraps, lru_cache
from collections import OrderedDict
import threading
import logging

# Cassandra driver imports
try:
    from cassandra.cluster import (
        Cluster,
        Session,
        ExecutionProfile,
        EXEC_PROFILE_DEFAULT,
    )
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.policies import (
        DCAwareRoundRobinPolicy,
        TokenAwarePolicy,
        RetryPolicy as CassandraRetryPolicy,
        ConstantReconnectionPolicy,
    )
    from cassandra.query import (
        PreparedStatement,
        SimpleStatement,
        ConsistencyLevel as CassandraConsistencyLevel,
        dict_factory,
    )
    from cassandra import OperationTimedOut, Unavailable, ReadTimeout, WriteTimeout
    from cassandra.io.asyncioreactor import AsyncioConnection

    CASSANDRA_AVAILABLE = True
except ImportError:
    CASSANDRA_AVAILABLE = False
    Cluster = None
    Session = None
    ExecutionProfile = None
    EXEC_PROFILE_DEFAULT = None
    PlainTextAuthProvider = None
    DCAwareRoundRobinPolicy = None
    TokenAwarePolicy = None
    CassandraRetryPolicy = None
    ConstantReconnectionPolicy = None
    PreparedStatement = None
    SimpleStatement = None
    CassandraConsistencyLevel = None
    dict_factory = None
    OperationTimedOut = Exception
    Unavailable = Exception
    ReadTimeout = Exception
    WriteTimeout = Exception
    AsyncioConnection = None

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
        ReliabilityConfigs,
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
    ReliabilityConfigs = None
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
CONSISTENCY_MAP = {
    "ANY": 0,
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "QUORUM": 4,
    "ALL": 5,
    "LOCAL_QUORUM": 6,
    "EACH_QUORUM": 7,
    "LOCAL_ONE": 10,
}


def map_consistency_level(level: Union[str, ConsistencyLevel]) -> int:
    """Map ConsistencyLevel enum to cassandra-driver consistency level."""
    if CASSANDRA_AVAILABLE and CassandraConsistencyLevel:
        level_str = level.value if hasattr(level, 'value') else str(level)
        return getattr(CassandraConsistencyLevel, level_str, CassandraConsistencyLevel.LOCAL_ONE)
    return CONSISTENCY_MAP.get(str(level).upper(), 10)  # Default to LOCAL_ONE


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
# ScyllaDB Client
# =============================================================================
class ScyllaClient:
    """
    Async ScyllaDB client with circuit breaker, retry, and prepared statements.

    Features:
    - Async query execution with asyncio
    - Prepared statements cache for performance
    - Circuit breaker for fault tolerance
    - Retry with exponential backoff
    - Shard-aware routing (ScyllaDB specific)
    - Token-aware load balancing
    - Health monitoring
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
        if not CASSANDRA_AVAILABLE:
            raise ImportError(
                "cassandra-driver is not installed. "
                "Install it with: pip install cassandra-driver"
            )

        # Configuration
        self.config = config or (ScyllaConfig() if CONFIG_AVAILABLE else None)
        if self.config is None:
            raise ValueError("ScyllaConfig is required but not available")

        # Cluster and session
        self._cluster: Optional[Cluster] = None
        self._session: Optional[Session] = None

        # Prepared statements cache with LRU eviction (max 1000 statements)
        self._prepared_statements: OrderedDict[str, PreparedStatement] = OrderedDict()
        self._prepared_lock = asyncio.Lock()
        self._max_prepared_statements = 1000  # Prevent unbounded memory growth

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
        self._slow_query_threshold_ms = self.config.slow_query_threshold_ms

        log.info(f"ScyllaClient initialized for keyspace: {self.config.keyspace}")

    async def connect(self) -> None:
        """Connect to ScyllaDB cluster."""
        if self._session is not None:
            return

        try:
            # Build execution profiles
            read_profile = ExecutionProfile(
                load_balancing_policy=self._create_load_balancing_policy(),
                consistency_level=map_consistency_level(self.config.default_consistency_read),
                request_timeout=self.config.request_timeout,
                row_factory=dict_factory,
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

            # Build cluster options
            cluster_kwargs = {
                'contact_points': self.config.get_contact_points_list(),
                'port': self.config.port,
                'execution_profiles': profiles,
                'connect_timeout': self.config.connect_timeout,
                'idle_heartbeat_interval': self.config.idle_heartbeat_interval,
                'idle_heartbeat_timeout': self.config.idle_heartbeat_timeout,
                'reconnection_policy': ConstantReconnectionPolicy(
                    delay=self.config.retry_initial_delay_ms / 1000,
                    max_attempts=self.config.retry_max_attempts
                ),
                'connection_class': AsyncioConnection,
            }

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

            self._circuit_breaker.record_success()
            log.info(f"Connected to ScyllaDB cluster: {self.config.contact_points}")

        except Exception as e:
            self._circuit_breaker.record_failure(str(e))
            log.error(f"Failed to connect to ScyllaDB: {e}")
            raise

    def _create_load_balancing_policy(self):
        """Create load balancing policy based on configuration."""
        # Base policy - DC-aware round robin
        base_policy = DCAwareRoundRobinPolicy()

        # Wrap with token-aware if enabled
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
    ) -> List[Dict[str, Any]]:
        """
        Execute a CQL query with circuit breaker and retry.

        Args:
            query: CQL query string
            parameters: Query parameters (dict for named, tuple/list for positional)
            consistency: Optional consistency level override
            timeout: Optional timeout override in seconds
            execution_profile: Execution profile name ('read', 'write', or default)

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
                statement = SimpleStatement(query)

                # Apply consistency override if specified
                if consistency:
                    statement.consistency_level = map_consistency_level(consistency)

                # Execute query
                loop = asyncio.get_event_loop()
                if parameters:
                    result = await loop.run_in_executor(
                        None,
                        lambda: self._session.execute(
                            statement,
                            parameters,
                            timeout=timeout,
                            execution_profile=execution_profile,
                        )
                    )
                else:
                    result = await loop.run_in_executor(
                        None,
                        lambda: self._session.execute(
                            statement,
                            timeout=timeout,
                            execution_profile=execution_profile,
                        )
                    )

                self._query_count += 1
                self._circuit_breaker.record_success()

                return list(result) if result else []

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
    ) -> List[Dict[str, Any]]:
        """
        Execute a prepared statement with circuit breaker and retry.

        Prepared statements are cached for performance.

        Args:
            query: CQL query string
            parameters: Query parameters
            consistency: Optional consistency level override
            timeout: Optional timeout override in seconds
            execution_profile: Execution profile name

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

                # Apply consistency override if specified
                if consistency:
                    bound.consistency_level = map_consistency_level(consistency)

                # Execute
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._session.execute(
                        bound,
                        timeout=timeout,
                        execution_profile=execution_profile,
                    )
                )

                self._query_count += 1
                self._circuit_breaker.record_success()

                return list(result) if result else []

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
                log.debug(f"Prepared statement cached ({len(self._prepared_statements)}/{self._max_prepared_statements}): {query[:50]}...")
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

                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self._session.execute(batch, timeout=timeout)
                )

                self._query_count += len(statements)
                self._circuit_breaker.record_success()

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
        Perform health check on ScyllaDB connection.

        Returns:
            Health status and metrics
        """
        try:
            if self._session is None:
                return {
                    "is_healthy": False,
                    "error": "Not connected",
                    "circuit_breaker": self._circuit_breaker.get_metrics(),
                }

            # Execute simple query to check connectivity
            start_time = time.time()
            result = await self.execute("SELECT now() FROM system.local")
            latency_ms = (time.time() - start_time) * 1000

            return {
                "is_healthy": True,
                "latency_ms": round(latency_ms, 2),
                "keyspace": self.config.keyspace,
                "contact_points": self.config.get_contact_points_list(),
                "query_count": self._query_count,
                "error_count": self._error_count,
                "prepared_statements_cached": len(self._prepared_statements),
                "circuit_breaker": self._circuit_breaker.get_metrics(),
            }

        except Exception as e:
            log.error(f"ScyllaDB health check failed: {e}")
            return {
                "is_healthy": False,
                "error": str(e),
                "circuit_breaker": self._circuit_breaker.get_metrics(),
            }

    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics."""
        return {
            "query_count": self._query_count,
            "error_count": self._error_count,
            "prepared_statements_cached": len(self._prepared_statements),
            "is_connected": self._session is not None,
            "circuit_breaker": self._circuit_breaker.get_metrics(),
        }


# =============================================================================
# Global Singleton
# =============================================================================
_GLOBAL_SCYLLA_CLIENT: Optional[ScyllaClient] = None
_CLIENT_INIT_LOCK = asyncio.Lock()


async def init_global_scylla_client(config: Optional[ScyllaConfig] = None) -> ScyllaClient:
    """
    Initialize global ScyllaDB client singleton.

    Args:
        config: Optional ScyllaDB configuration

    Returns:
        ScyllaClient instance
    """
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
    """
    Get global ScyllaDB client.

    Raises:
        RuntimeError: If client not initialized
    """
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
    """
    Context manager for ScyllaDB client.

    Usage:
        async with scylla_client_context() as client:
            result = await client.execute("SELECT * FROM messages")
    """
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
    """
    Initialize ScyllaDB client for FastAPI app.

    Sets app.state.scylla_client.

    Args:
        app: FastAPI application
        config: Optional ScyllaDB configuration

    Returns:
        ScyllaClient instance
    """
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
