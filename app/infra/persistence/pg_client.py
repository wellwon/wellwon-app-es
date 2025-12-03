# =============================================================================
# File: app/infra/persistence/pg_client.py  — Refactored
# =============================================================================
# Multi-Database AsyncPG Pool Helper using reliability package and config
# Maintains full backward compatibility with v0.3 API
# =============================================================================

from __future__ import annotations

import asyncio
import logging
import pathlib
import os
import random
from typing import Optional, Any, List, AsyncIterator, Dict, Union, Tuple, Type, Callable, Awaitable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from enum import Enum, auto
from datetime import datetime, timezone
import time

import asyncpg
from asyncpg.exceptions import PostgresError, ConnectionDoesNotExistError

from app.config.pg_client_config import get_database_config, DatabaseConfig, Database
from app.config.reliability_config import ReliabilityConfigs
from app.infra.reliability.circuit_breaker import CircuitBreaker
from app.infra.reliability.retry import retry_async

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    def load_dotenv():
        """Stub for when dotenv is not installed"""
        pass

log = logging.getLogger("wellwon.app.infra.pg_client")

# =============================================================================
# Transaction Context (ContextVar for async context)
# =============================================================================

# CRITICAL FIX (2025-11-05): ContextVar to hold current transaction connection
# This allows projectors to use the same connection as the transaction context
_current_transaction_connection: ContextVar[Optional[asyncpg.Connection]] = ContextVar(
    'transaction_connection', default=None
)

# =============================================================================
# Performance Monitoring Configuration (loaded from config)
# =============================================================================

# Rate limiting for pool exhaustion warnings (avoid spam)
_POOL_EXHAUSTION_LAST_WARNED: Dict[str, float] = {}
_POOL_EXHAUSTION_WARNING_INTERVAL = 10.0  # Warn at most every 10 seconds per pool

def _get_monitoring_thresholds():
    """Get monitoring thresholds from config (lazy load to avoid circular imports)"""
    try:
        config = get_config()
        return (
            config.slow_query_threshold_ms,
            config.pool_exhaustion_threshold,
            config.long_transaction_threshold_ms,
            config.slow_acquire_threshold_ms
        )
    except (AttributeError, RuntimeError, ImportError):  # Config not initialized or circular import
        # Fallback to env vars if config not available
        return (
            float(os.getenv("DB_SLOW_QUERY_THRESHOLD_MS", "1000")),
            float(os.getenv("DB_POOL_EXHAUSTION_THRESHOLD", "0.9")),
            float(os.getenv("DB_LONG_TRANSACTION_THRESHOLD_MS", "2000")),
            float(os.getenv("DB_SLOW_ACQUIRE_THRESHOLD_MS", "500"))
        )


# =============================================================================
# Database Registry (Multi-Database Support)
# =============================================================================
# Database enum is imported from config (Database.MAIN, Database.REFERENCE, etc.)
# To add new database:
# 1. Add enum entry in app/config/pg_client_config.py
# 2. Add DSN field and pool property in PostgresConfig
# 3. Registry will auto-initialize on first use

# Global pool registry and locks (dynamically populated)
_POOLS: Dict[str, Optional[asyncpg.Pool]] = {}
_POOL_LOCKS: Dict[str, asyncio.Lock] = {}

# Initialize known databases
for db in Database:
    _POOLS[db.value] = None
    _POOL_LOCKS[db.value] = asyncio.Lock()

# v0.3 compatibility: Global pool instance and lock for main database
_POOL: Optional[asyncpg.Pool] = None
_POOL_LOCK = asyncio.Lock()

# Circuit breakers for each database (lazily initialized)
_CIRCUIT_BREAKERS: Dict[str, CircuitBreaker] = {}

# Retry configurations for each database (initialize with None for all databases)
_RETRY_CONFIGS: Dict[str, Any] = {db.value: None for db in Database}

# Global config instance
_CONFIG: Optional[DatabaseConfig] = None

# Legacy compatibility
_MAIN_CIRCUIT_BREAKER: Optional[CircuitBreaker] = None
_RETRY_CONFIG: Optional[Any] = None


# -----------------------------------------------------------------------------
# Circuit Breaker State (from original)
# -----------------------------------------------------------------------------
class CircuitState(Enum):
    """Possible states of a circuit breaker"""
    CLOSED = auto()  # Normal operation - requests pass through
    OPEN = auto()  # Failing - requests are blocked
    HALF_OPEN = auto()  # Testing recovery - limited requests allowed


# -----------------------------------------------------------------------------
# Configuration and Circuit Breakers
# -----------------------------------------------------------------------------
def get_config() -> DatabaseConfig:
    """Get database configuration"""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = get_database_config()
    return _CONFIG


def set_config(config: DatabaseConfig) -> None:
    """Set database configuration (for testing)"""
    global _CONFIG
    _CONFIG = config


def get_circuit_breaker(database: str) -> CircuitBreaker:
    """Get circuit breaker for specific database"""
    global _CIRCUIT_BREAKERS, _MAIN_CIRCUIT_BREAKER

    if database not in _CIRCUIT_BREAKERS:
        config = ReliabilityConfigs.postgres_circuit_breaker(database)
        _CIRCUIT_BREAKERS[database] = CircuitBreaker(config)

        # Sync with global for main database
        if database == Database.MAIN:
            _MAIN_CIRCUIT_BREAKER = _CIRCUIT_BREAKERS[database]

    return _CIRCUIT_BREAKERS[database]


def get_retry_config(database: str = Database.MAIN):
    """Get retry configuration for specific database"""
    global _RETRY_CONFIGS, _RETRY_CONFIG

    if _RETRY_CONFIGS[database] is None:
        _RETRY_CONFIGS[database] = ReliabilityConfigs.postgres_retry()

        # Sync with global for main database
        if database == Database.MAIN:
            _RETRY_CONFIG = _RETRY_CONFIGS[database]

    return _RETRY_CONFIGS[database]


# v0.3 compatibility functions
def get_global_circuit_breaker() -> CircuitBreaker:
    """Get the global circuit breaker (v0.3 compatibility)"""
    global _MAIN_CIRCUIT_BREAKER
    if _MAIN_CIRCUIT_BREAKER is None:
        _MAIN_CIRCUIT_BREAKER = get_circuit_breaker(Database.MAIN)
    return _MAIN_CIRCUIT_BREAKER


def get_global_retry_config():
    """Get the global retry configuration (v0.3 compatibility)"""
    global _RETRY_CONFIG
    if _RETRY_CONFIG is None:
        _RETRY_CONFIG = get_retry_config(Database.MAIN)
    return _RETRY_CONFIG


# -----------------------------------------------------------------------------
# DSN Resolution
# -----------------------------------------------------------------------------
def get_postgres_dsn() -> str:
    """Get PostgreSQL DSN for main database (v0.3 compatibility)"""
    config = get_config()
    dsn = config.main_dsn
    if not dsn:
        # Fallback to env vars
        dsn = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("POSTGRES_DSN is not set. Please define it in your environment or .env file.")
    return dsn


def get_postgres_dsn_for_db(database: str = Database.MAIN) -> str:
    """Get PostgreSQL DSN for specified database"""
    config = get_config()

    # Use config's get_dsn() method for proper database routing
    dsn = config.get_dsn(Database(database))

    if not dsn:
        raise RuntimeError(
            f"DSN not configured for database '{database}'. "
            f"Set POSTGRES_{database.upper()}_DSN in environment."
        )

    return dsn


# =============================================================================
# Pool Management
# =============================================================================

async def init_db_pool(
        dsn_or_url: Optional[str] = None,
        min_size: int = int(os.getenv("PG_POOL_MIN_SIZE", "20")),  # Updated default
        max_size: int = int(os.getenv("PG_POOL_MAX_SIZE", "100")),  # Updated default
        pool_acquire_timeout_sec: float = float(os.getenv("PG_POOL_TIMEOUT_SEC", "30.0")),
        default_command_timeout_sec: float = float(os.getenv("PG_COMMAND_TIMEOUT_SEC", "60.0")),
        **pool_kwargs: Any
) -> asyncpg.Pool:
    """Initialize the global asyncpg pool with circuit breaker and retry support. Idempotent."""
    return await init_pool_for_db(
        Database.MAIN,
        dsn_or_url=dsn_or_url,
        min_size=min_size,
        max_size=max_size,
        pool_acquire_timeout_sec=pool_acquire_timeout_sec,
        default_command_timeout_sec=default_command_timeout_sec,
        **pool_kwargs
    )


async def init_pool_for_db(
        database: str = Database.MAIN,
        dsn_or_url: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        pool_acquire_timeout_sec: Optional[float] = None,
        default_command_timeout_sec: Optional[float] = None,
        **pool_kwargs: Any
) -> asyncpg.Pool:
    """Initialize a database pool for the specified database"""
    global _POOLS, _POOL

    config = get_config()

    # Get pool configuration for specified database
    pool_config = config.get_pool_config(Database(database))

    # Get defaults from env if not provided (database-specific env vars)
    if database == Database.REFERENCE:
        min_size = min_size or int(os.getenv("PG_REFERENCE_POOL_MIN_SIZE", str(pool_config.min_size)))
        max_size = max_size or int(os.getenv("PG_REFERENCE_POOL_MAX_SIZE", str(pool_config.max_size)))
        pool_acquire_timeout_sec = pool_acquire_timeout_sec or float(
            os.getenv("PG_REFERENCE_POOL_TIMEOUT_SEC", str(pool_config.timeout)))
        default_command_timeout_sec = default_command_timeout_sec or float(
            os.getenv("PG_REFERENCE_POOL_COMMAND_TIMEOUT_SEC", str(pool_config.command_timeout)))
    else:  # MAIN or other databases
        min_size = min_size or int(os.getenv("PG_POOL_MIN_SIZE", str(pool_config.min_size)))
        max_size = max_size or int(os.getenv("PG_POOL_MAX_SIZE", str(pool_config.max_size)))
        pool_acquire_timeout_sec = pool_acquire_timeout_sec or float(
            os.getenv("PG_POOL_TIMEOUT_SEC", str(pool_config.timeout)))
        default_command_timeout_sec = default_command_timeout_sec or float(
            os.getenv("PG_COMMAND_TIMEOUT_SEC", str(pool_config.command_timeout)))

    # Initialize circuit breaker and retry config if needed
    circuit_breaker = get_circuit_breaker(database)
    retry_config = get_retry_config(database)

    # Check if circuit breaker allows execution
    if not circuit_breaker.can_execute():
        log.warning(
            f"Circuit breaker preventing {database} pool initialization. "
            f"Circuit state: {circuit_breaker.get_state_sync()}"
        )
        raise ConnectionError(f"Circuit breaker is open for {database} database")

    # NOTE (Granian multi-worker): asyncio.Lock() only synchronizes within ONE process.
    # Each Granian worker is a SEPARATE process and MUST create its own connection pool.
    # Pools cannot be shared between processes. This lock prevents double-initialization
    # within a single worker, which is sufficient for pool creation.
    # For schema execution, we use distributed Redis lock (see run_schema_for_db).
    async with _POOL_LOCKS[database]:
        # Double-check: only init if pool doesn't exist yet
        if _POOLS[database] is None or _POOLS[database].is_closing():
            dsn = dsn_or_url or get_postgres_dsn_for_db(database)

            # Define connection init callback for JSONB codec
            async def init_connection(conn):
                """Initialize connection with JSONB codec for automatic dict<->JSONB conversion"""
                import json
                await conn.set_type_codec(
                    'jsonb',
                    encoder=json.dumps,
                    decoder=json.loads,
                    schema='pg_catalog'
                )

            # Build pool parameters from config
            params = pool_config.to_asyncpg_params()
            # Override with provided values
            params.update({
                "min_size": min_size,
                "max_size": max_size,
                "timeout": pool_acquire_timeout_sec,
                "command_timeout": default_command_timeout_sec,
                "init": init_connection,  # Add JSONB codec setup
                **pool_kwargs
            })

            log.info(f"Initializing {database} PostgreSQL pool (hidden DSN): {dsn.split('@')[-1]}")

            # Define pool creation with circuit breaker
            async def create_pool():
                try:
                    pool = await asyncpg.create_pool(dsn=dsn, **params)  # type: ignore[misc]

                    # Verify connection with a test query
                    async with pool.acquire() as conn:
                        await conn.fetchval("SELECT 1")

                    return pool
                except Exception as err:
                    circuit_breaker.record_failure(str(err))
                    raise

            try:
                # Create pool with retry
                _POOLS[database] = await retry_async(
                    create_pool,
                    retry_config=retry_config,
                    context=f"{database} PostgreSQL pool initialization"
                )

                # Record success in circuit breaker
                circuit_breaker.record_success()

                log.info(f"{database} PostgreSQL pool ready. Min/Max size: {min_size}/{max_size}")

                # v0.3 compatibility: Update global _POOL for main database
                if database == Database.MAIN:
                    _POOL = _POOLS[database]

            except Exception as e:
                log.critical(f"Failed to init {database} PostgreSQL pool: {e}", exc_info=True)
                _POOLS[database] = None
                if database == Database.MAIN:
                    _POOL = None
                raise RuntimeError(f"{database} PostgreSQL pool init error: {e}") from e

    return _POOLS[database]  # type: ignore[return-value]


async def get_pool(ensure_initialized: bool = True) -> asyncpg.Pool:
    """Get the global pool, init if needed (default). (v0.3 compatibility)"""
    return await get_pool_for_db(Database.MAIN, ensure_initialized)


async def get_pool_for_db(database: str = Database.MAIN, ensure_initialized: bool = True) -> asyncpg.Pool:
    """Get the pool for specified database, init if needed"""
    global _POOLS, _POOL

    if _POOLS[database] is None or _POOLS[database].is_closing():
        if ensure_initialized:
            await init_pool_for_db(database)
        else:
            raise RuntimeError(f"{database} PostgreSQL pool not available")

    # v0.3 compatibility: Update global _POOL for main database
    if database == Database.MAIN:
        _POOL = _POOLS[database]

    return _POOLS[database]  # type: ignore[return-value]


async def close_db_pool() -> None:
    """Close the global pool gracefully. (v0.3 compatibility)"""
    await close_pool_for_db(Database.MAIN)


async def close_pool_for_db(database: Optional[str] = None) -> None:
    """Close database pool(s)"""
    global _POOLS, _POOL

    databases = [database] if database else list(_POOLS.keys())

    for db_name in databases:
        async with _POOL_LOCKS[db_name]:
            pool = _POOLS[db_name]
            _POOLS[db_name] = None

            # v0.3 compatibility: Clear global _POOL if closing main
            if db_name == Database.MAIN:
                _POOL = None

            if pool and not pool.is_closing():
                log.info(f"Closing {db_name} PostgreSQL pool...")
                try:
                    await pool.close()
                    log.info(f"{db_name} PostgreSQL pool closed.")
                except Exception as e:
                    log.error(f"Error closing {db_name} pool: {e}", exc_info=True)


# =============================================================================
# Connection Context Manager
# =============================================================================

@asynccontextmanager
async def acquire_connection() -> AsyncIterator[asyncpg.Connection]:
    """Acquire a connection from the pool with circuit breaker protection."""
    async with acquire_connection_for_db(Database.MAIN) as conn:
        yield conn


@asynccontextmanager
async def acquire_connection_for_db(database: str = Database.MAIN) -> AsyncIterator[asyncpg.Connection]:
    """Acquire a connection from the specified database pool with circuit breaker protection."""
    circuit_breaker = get_circuit_breaker(database)
    retry_config = get_retry_config(database)

    # Check if circuit breaker allows execution
    if not circuit_breaker.can_execute():
        log.warning(
            f"Circuit breaker preventing {database} connection acquisition. "
            f"Circuit state: {circuit_breaker.get_state_sync()}"
        )
        raise ConnectionError(f"Circuit breaker is open for {database} database")

    pool = await get_pool_for_db(database)
    conn: Optional[asyncpg.Connection] = None

    # Pool exhaustion check (with rate limiting to avoid spam)
    try:
        config = get_config()
        pool_config = config.main_pool if database == Database.MAIN else config.vb_pool
        max_size = pool_config.max_size

        # Calculate approximate active connections
        # _holders = all connection holders created
        # _queue = free connections waiting
        # Active ≈ _holders - _queue
        _, exhaustion_threshold, _, _ = _get_monitoring_thresholds()

        if hasattr(pool, '_holders') and hasattr(pool, '_queue'):
            # noinspection PyProtectedMember
            total_holders = len(pool._holders)  # type: ignore[attr-defined]
            # noinspection PyProtectedMember
            free_connections = pool._queue.qsize() if hasattr(pool._queue, 'qsize') else 0  # type: ignore[attr-defined]
            active_connections = max(0, total_holders - free_connections)

            # Only warn if above threshold AND haven't warned recently
            if active_connections >= max_size * exhaustion_threshold:
                current_time = time.time()
                last_warned = _POOL_EXHAUSTION_LAST_WARNED.get(database, 0)

                if current_time - last_warned >= _POOL_EXHAUSTION_WARNING_INTERVAL:
                    _POOL_EXHAUSTION_LAST_WARNED[database] = current_time
                    log.warning(
                        f"[POOL EXHAUSTION] {database} pool at {active_connections}/{max_size} active connections "
                        f"({int(active_connections/max_size*100)}% usage, {free_connections} free)"
                    )
    except (AttributeError, TypeError, ZeroDivisionError):  # Pool structure changed or invalid data
        pass  # Don't fail on metrics collection

    acquire_start = time.time()

    try:
        # Acquire connection with retry
        async def get_connection():
            try:
                return await pool.acquire()  # type: ignore[misc]
            except Exception as err:
                circuit_breaker.record_failure(str(err))
                raise

        conn = await retry_async(
            get_connection,
            retry_config=retry_config,
            context=f"{database} connection acquisition"
        )

        # Slow acquisition warning
        acquire_time_ms = (time.time() - acquire_start) * 1000
        _, _, _, slow_acquire_threshold = _get_monitoring_thresholds()
        if acquire_time_ms > slow_acquire_threshold:
            log.warning(
                f"[SLOW POOL ACQUIRE] {database} took {acquire_time_ms:.0f}ms to get connection "
                f"(threshold: {slow_acquire_threshold:.0f}ms)"
            )

        # Record success in circuit breaker
        circuit_breaker.record_success()

        yield conn
    except Exception as e:
        log.error(f"{database} connection acquisition failed: {e}", exc_info=True)
        raise
    finally:
        if conn:
            await pool.release(conn)


# =============================================================================
# DB Operation Context Manager
# =============================================================================

@asynccontextmanager
async def db_operation(operation_name: str) -> AsyncIterator[None]:
    """Context manager for database operations with circuit breaker support."""
    async with db_operation_for_db(operation_name, Database.MAIN):
        yield


@asynccontextmanager
async def db_operation_for_db(operation_name: str, database: str = Database.MAIN) -> AsyncIterator[None]:
    """Context manager for database operations with circuit breaker support."""
    circuit_breaker = get_circuit_breaker(database)

    # Check circuit breaker
    if not circuit_breaker.can_execute():
        log.warning(
            f"Circuit breaker preventing {operation_name} on {database}. "
            f"Circuit state: {circuit_breaker.get_state_sync()}"
        )
        raise ConnectionError(f"Circuit breaker is open for {database} database ({operation_name})")

    try:
        yield
        # Record success if we get here
        circuit_breaker.record_success()
    except Exception as e:
        # Record failure
        circuit_breaker.record_failure(str(e))
        log.warning(f"{database} operation '{operation_name}' failed: {e}")
        raise


# =============================================================================
# Enhanced CRUD Wrappers
# =============================================================================

async def fetch(query: str, *args: Any, timeout: Optional[float] = None) -> List[asyncpg.Record]:
    """Execute the query and return all rows with circuit breaker and retry."""
    return await fetch_for_db(query, *args, database=Database.MAIN, timeout=timeout)


async def fetch_for_db(query: str, *args: Any, database: str = Database.MAIN, timeout: Optional[float] = None) -> List[
    asyncpg.Record]:
    """
    Execute the query and return all rows for specified database.
    CRITICAL FIX (2025-11-05): Now checks ContextVar for transaction connection.
    OPTIMIZED (2025-11-10): Separate timing for pool acquisition vs query execution.
    """
    retry_config = get_retry_config(database)
    operation_start_time = time.monotonic()  # Use monotonic for accurate timing

    # CRITICAL FIX: Check if we're inside a transaction context
    transaction_conn = _current_transaction_connection.get()

    if transaction_conn is not None:
        # Use the transaction connection directly
        try:
            # Measure ONLY query execution time (no pool overhead)
            query_exec_start = time.monotonic()
            fetch_result = await transaction_conn.fetch(query, *args, timeout=timeout)
            query_exec_elapsed_ms = (time.monotonic() - query_exec_start) * 1000

            # Slow query logging (query execution only)
            slow_query_threshold, _, _, _ = _get_monitoring_thresholds()
            if query_exec_elapsed_ms > slow_query_threshold:
                log.warning(
                    f"[SLOW QUERY] {database} FETCH (in transaction) took {query_exec_elapsed_ms:.1f}ms: {query[:150]}... | "
                    f"args: {str(args[:3])[:50] if args else 'none'}"
                )

            return fetch_result
        except Exception as ex:
            log.error(f"{database} fetch failed (in transaction): {ex}", exc_info=True)
            raise

    # No transaction context - acquire new connection
    # Measure pool acquisition separately from query execution
    pool_acquire_start = time.monotonic()

    async def _fetch_operation():
        nonlocal pool_acquire_start
        async with db_operation_for_db(f"FETCH {query[:50]}...", database):
            async with acquire_connection_for_db(database) as conn_fetch:
                pool_acquire_ms = (time.monotonic() - pool_acquire_start) * 1000

                # Measure ONLY query execution time (no pool overhead)
                query_exec_start = time.monotonic()
                fetch_result = await conn_fetch.fetch(query, *args, timeout=timeout)
                query_exec_elapsed_ms = (time.monotonic() - query_exec_start) * 1000

                # Slow query logging with separated timings
                slow_query_threshold, _, _, acquire_threshold = _get_monitoring_thresholds()

                # Log slow pool acquisition separately
                if pool_acquire_ms > acquire_threshold:
                    log.warning(
                        f"[SLOW POOL] {database} connection acquisition took {pool_acquire_ms:.1f}ms (threshold: {acquire_threshold}ms)"
                    )

                # Log slow query execution (actual query time only)
                if query_exec_elapsed_ms > slow_query_threshold:
                    log.warning(
                        f"[SLOW QUERY] {database} FETCH took {query_exec_elapsed_ms:.1f}ms (pool: {pool_acquire_ms:.1f}ms): {query[:500]}... | "
                        f"args: {str(args[:10])[:200] if args else 'none'}"
                    )

                return fetch_result

    try:
        result = await retry_async(
            _fetch_operation,
            retry_config=retry_config,
            context=f"{database} FETCH {query[:50]}..."
        )

        # Total operation time (for monitoring overall latency)
        total_elapsed_ms = (time.monotonic() - operation_start_time) * 1000
        if total_elapsed_ms > 1000:  # Log operations over 1 second
            log.info(f"{database} FETCH total operation time: {total_elapsed_ms:.1f}ms")

        return result
    except Exception as ex:
        log.error(f"{database} fetch failed: {ex}", exc_info=True)
        raise


async def fetchrow(query: str, *args: Any, timeout: Optional[float] = None) -> Optional[asyncpg.Record]:
    """Execute query and return single row with circuit breaker and retry."""
    return await fetchrow_for_db(query, *args, database=Database.MAIN, timeout=timeout)


async def fetchrow_for_db(query: str, *args: Any, database: str = Database.MAIN, timeout: Optional[float] = None) -> Optional[
    asyncpg.Record]:
    """
    Execute query and return single row for specified database.
    CRITICAL FIX (2025-11-05): Now checks ContextVar for transaction connection.
    OPTIMIZED (2025-11-10): Separate timing for pool acquisition vs query execution.
    """
    retry_config = get_retry_config(database)
    operation_start_time = time.monotonic()

    # CRITICAL FIX: Check if we're inside a transaction context
    transaction_conn = _current_transaction_connection.get()

    if transaction_conn is not None:
        # Use the transaction connection directly
        try:
            # Measure ONLY query execution time
            query_exec_start = time.monotonic()
            fetchrow_result = await transaction_conn.fetchrow(query, *args, timeout=timeout)
            query_exec_elapsed_ms = (time.monotonic() - query_exec_start) * 1000

            # Slow query logging (query execution only)
            slow_query_threshold, _, _, _ = _get_monitoring_thresholds()
            if query_exec_elapsed_ms > slow_query_threshold:
                log.warning(
                    f"[SLOW QUERY] {database} FETCHROW (in transaction) took {query_exec_elapsed_ms:.1f}ms: {query[:150]}... | "
                    f"args: {str(args[:3])[:50] if args else 'none'}"
                )

            return fetchrow_result
        except Exception as ex:
            log.error(f"{database} fetchrow failed (in transaction): {ex}", exc_info=True)
            raise

    # No transaction context - acquire new connection
    pool_acquire_start = time.monotonic()

    async def _fetchrow_operation():
        nonlocal pool_acquire_start
        async with db_operation_for_db(f"FETCHROW {query[:50]}...", database):
            async with acquire_connection_for_db(database) as conn_row:
                pool_acquire_ms = (time.monotonic() - pool_acquire_start) * 1000

                # Measure ONLY query execution time
                row_query_start = time.monotonic()
                fetchrow_result = await conn_row.fetchrow(query, *args, timeout=timeout)
                row_query_elapsed_ms = (time.monotonic() - row_query_start) * 1000

                # Slow query logging with separated timings
                slow_query_threshold, _, _, acquire_threshold = _get_monitoring_thresholds()

                if pool_acquire_ms > acquire_threshold:
                    log.warning(
                        f"[SLOW POOL] {database} connection acquisition took {pool_acquire_ms:.1f}ms (threshold: {acquire_threshold}ms)"
                    )

                if row_query_elapsed_ms > slow_query_threshold:
                    log.warning(
                        f"[SLOW QUERY] {database} FETCHROW took {row_query_elapsed_ms:.1f}ms (pool: {pool_acquire_ms:.1f}ms): {query[:150]}... | "
                        f"args: {str(args[:3])[:50] if args else 'none'}"
                    )

                return fetchrow_result

    try:
        result = await retry_async(
            _fetchrow_operation,
            retry_config=retry_config,
            context=f"{database} FETCHROW {query[:50]}..."
        )
        return result
    except Exception as ex:
        log.error(f"{database} fetchrow failed: {ex}", exc_info=True)
        raise


async def fetchval(
        query: str,
        *args: Any,
        column: int = 0,
        timeout: Optional[float] = None
) -> Any:
    """Execute a query and return a single value with circuit breaker and retry."""
    return await fetchval_for_db(query, *args, database=Database.MAIN, column=column, timeout=timeout)


async def fetchval_for_db(
        query: str,
        *args: Any,
        database: str = Database.MAIN,
        column: int = 0,
        timeout: Optional[float] = None
) -> Any:
    """Execute query and return single value for specified database."""
    retry_config = get_retry_config(database)
    start_time = time.time()

    async def _fetchval_operation():
        async with db_operation_for_db(f"FETCHVAL {query[:50]}...", database):
            async with acquire_connection_for_db(database) as conn_val:
                return await conn_val.fetchval(query, *args, column=column, timeout=timeout)

    try:
        result = await retry_async(
            _fetchval_operation,
            retry_config=retry_config,
            context=f"{database} FETCHVAL {query[:50]}..."
        )

        # Slow query logging
        elapsed_ms = (time.time() - start_time) * 1000
        slow_threshold, _, _, _ = _get_monitoring_thresholds()
        if elapsed_ms > slow_threshold:
            log.warning(
                f"[SLOW QUERY] {database} FETCHVAL took {elapsed_ms:.0f}ms: {query[:150]}... | "
                f"args: {str(args[:3])[:50] if args else 'none'}"
            )

        return result
    except Exception as ex:
        log.error(f"{database} fetchval failed: {ex}", exc_info=True)
        raise


async def execute(query: str, *args: Any, timeout: Optional[float] = None) -> str:
    """Execute DML/DDL and return status with circuit breaker and retry."""
    return await execute_for_db(query, *args, database=Database.MAIN, timeout=timeout)


async def execute_for_db(query: str, *args: Any, database: str = Database.MAIN, timeout: Optional[float] = None) -> str:
    """
    Execute DML/DDL and return status for specified database.
    CRITICAL FIX (2025-11-05): Now checks ContextVar for transaction connection.
    If a transaction is active, uses the same connection instead of acquiring a new one.
    """
    retry_config = get_retry_config(database)
    start_time = time.time()

    # CRITICAL FIX: Check if we're inside a transaction context
    transaction_conn = _current_transaction_connection.get()

    if transaction_conn is not None:
        # Use the transaction connection directly (no retry, already in transaction)
        try:
            result = await transaction_conn.execute(query, *args, timeout=timeout)

            # Slow query logging
            elapsed_ms = (time.time() - start_time) * 1000
            slow_threshold, _, _, _ = _get_monitoring_thresholds()
            if elapsed_ms > slow_threshold:
                log.warning(
                    f"[SLOW QUERY] {database} EXECUTE (in transaction) took {elapsed_ms:.0f}ms: {query[:150]}... | "
                    f"args: {str(args[:3])[:50] if args else 'none'}"
                )

            return result
        except Exception as ex:
            log.error(f"{database} execute failed (in transaction): {ex}", exc_info=True)
            raise

    # No transaction context - acquire new connection (original behavior)
    async def _execute_operation():
        async with db_operation_for_db(f"EXECUTE {query[:50]}...", database):
            async with acquire_connection_for_db(database) as conn_exec:
                return await conn_exec.execute(query, *args, timeout=timeout)

    try:
        result = await retry_async(
            _execute_operation,
            retry_config=retry_config,
            context=f"{database} EXECUTE {query[:50]}..."
        )

        # Slow query logging
        elapsed_ms = (time.time() - start_time) * 1000
        slow_threshold, _, _, _ = _get_monitoring_thresholds()
        if elapsed_ms > slow_threshold:
            log.warning(
                f"[SLOW QUERY] {database} EXECUTE took {elapsed_ms:.0f}ms: {query[:150]}... | "
                f"args: {str(args[:3])[:50] if args else 'none'}"
            )

        return result
    except Exception as ex:
        log.error(f"{database} execute failed: {ex}", exc_info=True)
        raise


# =============================================================================
# FIXED: Enhanced Transaction Context Manager
# =============================================================================

@asynccontextmanager
async def transaction(timeout: Optional[float] = None):
    """
    Create a database transaction context manager.
    FIXED: Proper asyncpg transaction handling without is_active()

    Usage:
        async with transaction() as conn:
            await conn.execute("INSERT INTO ...")

    Args:
        timeout: Optional timeout in seconds for the transaction

    Yields:
        The connection object (not transaction)
    """
    async with transaction_for_db(Database.MAIN, timeout=timeout) as conn:
        yield conn


@asynccontextmanager
async def transaction_for_db(database: str = Database.MAIN, timeout: Optional[float] = None):
    """
    FIXED: Transaction context manager using asyncpg's built-in transaction handling.

    This implementation properly handles asyncpg transactions without using is_active().
    The transaction is automatically committed on successful context exit and rolled
    back on exception.
    """
    circuit_breaker = get_circuit_breaker(database)
    retry_config = ReliabilityConfigs.postgres_deadlock_retry()

    # Check if circuit breaker allows execution
    if not circuit_breaker.can_execute():
        log.warning(
            f"Circuit breaker preventing transaction on {database}. "
            f"Circuit state: {circuit_breaker.get_state_sync()}"
        )
        raise ConnectionError(f"Circuit breaker is open for {database} database (transaction)")

    pool = await get_pool_for_db(database)

    # Acquire connection with retry
    async def acquire_conn():
        try:
            return await pool.acquire(timeout=timeout)  # type: ignore[misc]
        except Exception as err:
            circuit_breaker.record_failure(str(err))
            raise

    conn = await retry_async(
        acquire_conn,
        retry_config=retry_config,
        context=f"{database} transaction connection acquisition"
    )

    tx_start = time.time()

    # CRITICAL FIX (2025-11-05): Set ContextVar so all pg_db_proxy calls use this connection
    token = _current_transaction_connection.set(conn)

    try:
        # Use asyncpg's transaction context manager
        async with conn.transaction():  # type: ignore[attr-defined]
            # Yield the connection for queries
            yield conn
            # Transaction automatically commits here if no exception

        # Transaction duration monitoring
        tx_duration_ms = (time.time() - tx_start) * 1000
        _, _, long_tx_threshold, _ = _get_monitoring_thresholds()
        if tx_duration_ms > long_tx_threshold:
            log.warning(
                f"[LONG TRANSACTION] {database} transaction took {tx_duration_ms:.0f}ms "
                f"(threshold: {long_tx_threshold:.0f}ms)"
            )

        # Record success after successful commit
        circuit_breaker.record_success()

    except Exception as e:
        # Transaction automatically rolls back on exception
        circuit_breaker.record_failure(f"Transaction error: {str(e)}")
        log.error(f"Transaction failed for {database}: {e}")
        raise
    finally:
        # CRITICAL FIX: Reset ContextVar to previous value
        _current_transaction_connection.reset(token)
        # Always release the connection
        await pool.release(conn)


# =============================================================================
# CES (Compensating Event System) App Context Bypass
# =============================================================================
# These functions set the wellwon.app_context session variable to bypass CES
# triggers. CES triggers should ONLY fire for external/manual database changes
# (e.g., DBA running queries directly), NOT for application-driven changes.
#
# When the app modifies data through normal operations (user clicks button,
# API call, etc.), we set app_context = 'true' so CES triggers know to skip
# compensation event generation.
#
# Usage:
#   async with with_app_context() as conn:
#       await conn.execute("UPDATE users SET ...")
#
#   # Or for single queries:
#   await execute_with_app_context("DELETE FROM users WHERE id = $1", user_id)
# =============================================================================

@asynccontextmanager
async def with_app_context(database: str = Database.MAIN) -> AsyncIterator[asyncpg.Connection]:
    """
    Context manager that sets wellwon.app_context to bypass CES triggers.

    All queries executed within this context will have the app_context session
    variable set, which CES triggers check to determine if they should fire.

    CES triggers should ONLY fire for external changes (DBA queries), not for
    application-driven changes (user clicking buttons, API calls, etc.).

    Usage:
        async with with_app_context() as conn:
            await conn.execute("UPDATE users SET status = 'active' WHERE id = $1", user_id)
            await conn.execute("DELETE FROM old_sessions WHERE user_id = $1", user_id)
            # CES triggers will NOT fire for these changes

    Args:
        database: Which database to use (default: main)

    Yields:
        asyncpg.Connection with app_context set for the transaction
    """
    async with transaction_for_db(database) as conn:
        # Set the app_context session variable
        # SET LOCAL only affects the current transaction
        await conn.execute("SET LOCAL wellwon.app_context = 'true'")
        log.debug(f"CES bypass: app_context set for {database} transaction")
        yield conn
        # Transaction commits automatically, app_context resets on commit


async def execute_with_app_context(
    query: str,
    *args: Any,
    database: str = Database.MAIN,
    timeout: Optional[float] = None
) -> str:
    """
    Execute a single query with app_context set to bypass CES triggers.

    This is a convenience wrapper for executing a single DML/DDL statement
    while bypassing CES compensation event generation.

    CES triggers should ONLY fire for external changes (DBA queries), not for
    application-driven changes (user clicking buttons, API calls, etc.).

    Usage:
        # Single statement - CES triggers will NOT fire
        await execute_with_app_context(
            "UPDATE users SET last_login = NOW() WHERE id = $1",
            user_id
        )

        # For multiple statements, prefer with_app_context() context manager

    Args:
        query: SQL query to execute
        *args: Query parameters
        database: Which database to use (default: main)
        timeout: Optional query timeout

    Returns:
        Query execution status string (e.g., "UPDATE 1")
    """
    async with with_app_context(database) as conn:
        return await conn.execute(query, *args, timeout=timeout)


async def fetch_with_app_context(
    query: str,
    *args: Any,
    database: str = Database.MAIN,
    timeout: Optional[float] = None
) -> List[asyncpg.Record]:
    """
    Execute a SELECT query with app_context set.

    While SELECT queries typically don't trigger CES (no data modification),
    this function is provided for consistency and for cases where you need
    to SELECT within the same transaction as DML operations.

    Args:
        query: SQL SELECT query
        *args: Query parameters
        database: Which database to use (default: main)
        timeout: Optional query timeout

    Returns:
        List of records
    """
    async with with_app_context(database) as conn:
        return await conn.fetch(query, *args, timeout=timeout)


async def fetchrow_with_app_context(
    query: str,
    *args: Any,
    database: str = Database.MAIN,
    timeout: Optional[float] = None
) -> Optional[asyncpg.Record]:
    """
    Execute a SELECT query returning single row with app_context set.

    Args:
        query: SQL SELECT query
        *args: Query parameters
        database: Which database to use (default: main)
        timeout: Optional query timeout

    Returns:
        Single record or None
    """
    async with with_app_context(database) as conn:
        return await conn.fetchrow(query, *args, timeout=timeout)


# =============================================================================
# Enhanced Schema Bootstrap (Dev/CI)
# =============================================================================

async def run_schema_from_file(file_path_str: str = "app/database/wellwon.sql") -> None:
    """Execute DDL statements from a SQL file with circuit breaker and retry."""
    await run_schema_for_db(file_path_str, Database.MAIN)


async def run_schema_for_db(file_path_str: str, database: str = Database.MAIN) -> None:
    """Execute DDL statements from a SQL file for specified database."""
    circuit_breaker = get_circuit_breaker(database)
    retry_config = get_retry_config(database)

    # Check if circuit breaker allows execution
    if not circuit_breaker.can_execute():
        log.warning(
            f"Circuit breaker preventing schema execution on {database}. "
            f"Circuit state: {circuit_breaker.get_state_sync()}"
        )
        raise ConnectionError(f"Circuit breaker is open for {database} database (schema execution)")

    path = pathlib.Path(file_path_str)
    if not path.is_file():
        raise FileNotFoundError(f"Schema file not found: {file_path_str}")

    sql = path.read_text(encoding="utf-8").strip()
    if not sql:
        log.warning(f"Schema file {file_path_str} is empty")
        return

    # CRITICAL FIX (Granian multi-worker): Use distributed lock to prevent concurrent schema execution
    # When running with multiple workers (--workers 4), each worker process tries to run schema
    # simultaneously, causing "tuple concurrently updated" errors. This lock ensures only ONE
    # worker executes the schema while others wait.
    try:
        from app.infra.reliability.distributed_lock import DistributedLock
        from app.config.reliability_config import ReliabilityConfigs

        # Use schema-specific lock with 60 second TTL (schema execution can take time)
        lock_config = ReliabilityConfigs.schema_init_lock()
        lock = DistributedLock(lock_config)

        # Lock resource: schema file path + database name
        lock_resource = f"schema_init_{database}_{pathlib.Path(file_path_str).name}"

        async with lock.lock_context(lock_resource, ttl_seconds=60):
            log.info(f"Acquired schema execution lock for {database} (worker-safe)")

            async def execute_schema():
                async with acquire_connection_for_db(database) as conn:
                    await conn.execute(sql)
                return True

            try:
                await retry_async(
                    execute_schema,
                    retry_config=retry_config,
                    context=f"{database} schema execution from {file_path_str}"
                )

                # Record success in circuit breaker
                circuit_breaker.record_success()

                log.info(f"Schema from {file_path_str} applied to {database} successfully")
            except Exception as e:
                # Record failure in circuit breaker
                circuit_breaker.record_failure(str(e))

                log.error(f"{database} schema execution failed: {e}", exc_info=True)
                raise

    except ImportError:
        # Fallback if distributed lock not available (shouldn't happen in production)
        log.warning(f"Distributed lock not available, running schema without lock (NOT SAFE for multi-worker)")

        async def execute_schema():
            async with acquire_connection_for_db(database) as conn:
                await conn.execute(sql)
            return True

        try:
            await retry_async(
                execute_schema,
                retry_config=retry_config,
                context=f"{database} schema execution from {file_path_str}"
            )

            # Record success in circuit breaker
            circuit_breaker.record_success()

            log.info(f"Schema from {file_path_str} applied to {database} successfully")
        except Exception as e:
            # Record failure in circuit breaker
            circuit_breaker.record_failure(str(e))

            log.error(f"{database} schema execution failed: {e}", exc_info=True)
            raise


# =============================================================================
# Health and Diagnostics
# =============================================================================
async def health_check() -> dict:
    """
    Perform PostgreSQL health check to ensure the connection is working properly.

    Returns:
        dict: Health status including connections info and latency
    """
    return await health_check_for_db(Database.MAIN)


async def health_check_for_db(database: str = Database.MAIN) -> dict:
    """Perform health check on specified database"""
    start_time = time.time()
    health_status = {
        "database": database,
        "is_healthy": False,
        "latency_ms": 0,
        "details": {},
        "pool_info": {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Check if pool exists
    if _POOLS[database] is None:
        health_status["details"] = {
            "status": "error",
            "message": f"{database} PostgreSQL connection pool not initialized"
        }
        return health_status

    try:
        config = get_config()
        # Get pool metrics safely without relying on internal attributes
        pool_info = {}

        # Try to safely access pool size information - avoid accessing _size directly
        try:
            # For newer asyncpg versions, use more stable attributes
            pool = _POOLS[database]
            if hasattr(pool, 'get_size'):
                pool_info["size"] = await pool.get_size()  # type: ignore[misc]
            elif hasattr(pool, 'size'):
                pool_info["size"] = pool.size
            else:
                # Fallback - just state we can't determine size
                pool_info["size"] = "unknown"

            # Get min/max size safely
            pool_config = config.main_pool
            pool_info["min_size"] = pool_config.min_size
            pool_info["max_size"] = pool_config.max_size
        except Exception as size_err:
            log.debug(f"Unable to determine pool size info: {size_err}")
            pool_info["size"] = "unknown"
            pool_info["min_size"] = "unknown"
            pool_info["max_size"] = "unknown"

        health_status["pool_info"] = pool_info

        # Test the connection with a simple query
        async with _POOLS[database].acquire() as conn:
            await conn.execute(config.health_check_query)
            latency_ms = int((time.time() - start_time) * 1000)

            # Get PostgreSQL server version
            pg_version = await conn.fetchval("SHOW server_version")
            db_name = await conn.fetchval("SELECT current_database()")

            health_status.update({
                "is_healthy": True,
                "latency_ms": latency_ms,
                "details": {
                    "status": "ok",
                    "message": f"{database} PostgreSQL connection successful in {latency_ms}ms",
                    "pg_version": pg_version,
                    "database_name": db_name
                }
            })

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        health_status.update({
            "is_healthy": False,
            "latency_ms": latency_ms,
            "details": {
                "status": "error",
                "message": f"{database} PostgreSQL connection failed: {str(e)}",
                "error_type": type(e).__name__
            }
        })
        # Record failure in circuit breaker
        cb = get_circuit_breaker(database)
        if cb:
            cb.record_failure()
            health_status["circuit_breaker"] = cb.get_metrics()
        log.error(f"Error during {database} PostgreSQL health check: {e}", exc_info=True)

    return health_status


async def health_check_all() -> Dict[str, dict]:
    """Perform health check on all databases"""
    results = {}
    for database in _POOLS.keys():
        results[database] = await health_check_for_db(database)
    return results


# =============================================================================
# Convenience Proxy & Aliases for FastAPI
# =============================================================================

class _DBProxy:
    """Proxy for main database operations"""
    fetch = staticmethod(fetch)
    fetchrow = staticmethod(fetchrow)
    fetchval = staticmethod(fetchval)
    execute = staticmethod(execute)
    transaction = staticmethod(transaction)
    health_check = staticmethod(health_check)
    # CES bypass functions
    with_app_context = staticmethod(with_app_context)
    execute_with_app_context = staticmethod(execute_with_app_context)
    fetch_with_app_context = staticmethod(fetch_with_app_context)
    fetchrow_with_app_context = staticmethod(fetchrow_with_app_context)


# Database proxy
db = _DBProxy()

# Aliases for FastAPI imports (v0.3 compatibility)
init = init_db_pool
close = close_db_pool
run_schema = run_schema_from_file


# Initialize database
async def init_all(**kwargs):
    """Initialize database pool"""
    await init_pool_for_db(Database.MAIN, **kwargs)


# Close database
async def close_all():
    """Close database pool"""
    await close_pool_for_db()


# =============================================================================
# Legacy Classes for Compatibility
# =============================================================================

class RetryConfiguration:
    """Legacy retry configuration class for compatibility"""

    def __init__(
            self,
            max_attempts: int = 3,
            initial_delay_ms: int = 100,
            max_delay_ms: int = 2000,
            backoff_factor: float = 2.0,
            jitter: bool = True,
            retry_exceptions: Optional[Union[Tuple[Type[Exception], ...], Type[Exception]]] = None
    ):
        self.max_attempts = max_attempts
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms
        self.backoff_factor = backoff_factor
        self.jitter = jitter

        # Normalize retry_exceptions to a tuple
        if retry_exceptions is None:
            self.retry_exceptions = (PostgresError, ConnectionDoesNotExistError, OSError, ConnectionError)
        elif isinstance(retry_exceptions, tuple):
            self.retry_exceptions = retry_exceptions
        else:
            self.retry_exceptions = (retry_exceptions,)

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if a retry should be attempted for this exception."""
        if attempt >= self.max_attempts:
            return False

        return isinstance(exception, self.retry_exceptions)

    def calculate_delay(self, attempt: int) -> float:
        """Calculate the delay for a specific retry attempt (in seconds)."""
        delay_ms = min(
            self.initial_delay_ms * (self.backoff_factor ** (attempt - 1)),
            self.max_delay_ms
        )

        if self.jitter:
            # Add jitter of ±25%
            jitter_factor = 1.0 + random.uniform(-0.25, 0.25)
            delay_ms *= jitter_factor

        # Convert to seconds
        return delay_ms / 1000


# Legacy function for compatibility
async def with_retry(
        operation: Callable[..., Awaitable[Any]],
        *args: Any,
        retry_config: Optional[RetryConfiguration] = None,
        context: str = "operation",
        **kwargs: Any
) -> Any:
    """Execute an async operation with retry logic. (Legacy compatibility)"""
    # Convert legacy config to new format if needed
    if retry_config and isinstance(retry_config, RetryConfiguration):
        from app.config.reliability_config import RetryConfig
        new_config = RetryConfig(
            max_attempts=retry_config.max_attempts,
            initial_delay_ms=retry_config.initial_delay_ms,
            max_delay_ms=retry_config.max_delay_ms,
            backoff_factor=retry_config.backoff_factor,
            jitter=retry_config.jitter
        )
        return await retry_async(operation, *args, retry_config=new_config, context=context, **kwargs)
    else:
        return await retry_async(operation, *args, retry_config=retry_config, context=context, **kwargs)


# =============================================================================
# Metrics and Monitoring
# =============================================================================

def get_all_circuit_breaker_metrics() -> Dict[str, Dict[str, Any]]:
    """Get metrics for all database circuit breakers"""
    metrics = {}
    for db_name, breaker in _CIRCUIT_BREAKERS.items():
        metrics[db_name] = breaker.get_metrics()
    return metrics


# =============================================================================
# Environment Variables Documentation
# =============================================================================

"""
Environment variables for database configuration:

# Database connection
POSTGRES_DSN=postgresql://user:password@localhost:5432/wellwon
DATABASE_URL=postgresql://user:password@localhost:5432/wellwon

# Pool configuration
PG_POOL_MIN_SIZE=20     # Production default
PG_POOL_MAX_SIZE=100    # Production default
PG_POOL_TIMEOUT_SEC=30.0
PG_COMMAND_TIMEOUT_SEC=60.0

# Environment selection
ENVIRONMENT=development    # or production, high_performance

# Pool sizing
DB_AUTO_SCALE_POOLS=true
DB_MAX_TOTAL_CONNECTIONS=500  # Should match PostgreSQL max_connections
"""

# =============================================================================
# EOF
# =============================================================================