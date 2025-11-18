# app/config/pg_client_config.py
# =============================================================================
# File: app/config/pg_client_config.py
# Description: Database configuration for PostgreSQL pools
# ENHANCED: Auto-detection of Gunicorn workers for pool sizing
# =============================================================================

import os
import multiprocessing
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
import logging

logger = logging.getLogger("tradecore.config.pg_client")


class EnvironmentProfile(str, Enum):
    """Environment profiles"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    HIGH_PERFORMANCE = "high_performance"
    TESTING = "testing"


class ServerType(str, Enum):
    """Server types for pool optimization"""
    GRANIAN = "granian"
    DEV_SERVER = "dev_server"
    UNKNOWN = "unknown"


@dataclass
class PoolConfig:
    """PostgreSQL connection pool configuration"""
    # Basic pool settings
    min_size: int = 20  # Reasonable minimum for production
    max_size: int = 100  # Proper default for real applications
    timeout: float = 5.0  # Pool acquisition timeout in seconds
    command_timeout: float = 10.0  # Default command timeout

    # Pool behavior
    min_idle: int = 5  # Keep some connections ready
    max_idle_time: float = 300.0  # Close idle connections after 5 minutes
    max_lifetime: float = 3600.0  # Close connections after 1 hour
    max_queries: int = 50000  # Close connection after this many queries

    # Connection setup
    server_settings: Optional[Dict[str, str]] = None
    init_commands: Optional[List[str]] = None

    # Performance
    statement_cache_size: int = 100
    max_cached_statement_lifetime: int = 300
    max_inactive_connection_lifetime: float = 300.0

    def to_asyncpg_params(self) -> Dict[str, Any]:
        """Convert to asyncpg pool parameters"""
        params = {
            'min_size': self.min_size,
            'max_size': self.max_size,
            'timeout': self.timeout,
            'command_timeout': self.command_timeout,
            'statement_cache_size': self.statement_cache_size,
            'max_cached_statement_lifetime': self.max_cached_statement_lifetime,
            'max_inactive_connection_lifetime': self.max_inactive_connection_lifetime,
            'max_queries': self.max_queries,
        }

        if self.server_settings:
            params['server_settings'] = self.server_settings

        if self.init_commands:
            params['init'] = self._create_init_function()

        return params

    def _create_init_function(self) -> Callable:
        """Create init function for connection setup"""

        async def init_connection(conn):
            for cmd in self.init_commands:
                await conn.execute(cmd)

        return init_connection


@dataclass
class DatabaseConfig:
    """Complete database configuration"""
    # Connection strings (from env)
    main_dsn: Optional[str] = None
    vb_dsn: Optional[str] = None

    # Pool configurations
    main_pool: Optional[PoolConfig] = None
    vb_pool: Optional[PoolConfig] = None

    # Features
    enable_vb_database: bool = True
    run_schemas_on_startup: bool = True
    schema_paths: Optional[Dict[str, str]] = None

    # Health check
    health_check_interval: float = 30.0
    health_check_query: str = "SELECT 1"
    health_check_timeout: float = 5.0

    # Connection retry
    connection_retry_attempts: int = 3
    connection_retry_delay: float = 0.5

    # Auto-scaling
    auto_scale_pools: bool = True
    max_total_connections: int = 500  # Reasonable default for production PostgreSQL

    # Performance monitoring
    slow_query_threshold_ms: float = 1000.0  # Log queries slower than this
    pool_exhaustion_threshold: float = 0.9  # Warn when pool reaches 90% capacity
    long_transaction_threshold_ms: float = 2000.0  # Log transactions longer than this
    slow_acquire_threshold_ms: float = 500.0  # Log slow connection acquisitions

    def __post_init__(self):
        if self.main_pool is None:
            self.main_pool = PoolConfig()  # Uses new defaults: 20-100

        if self.vb_pool is None:
            self.vb_pool = PoolConfig(
                min_size=10,  # Smaller pool for VB
                max_size=50
            )

        if self.schema_paths is None:
            self.schema_paths = {
                'main': 'database/tradecore.sql',
                'vb': 'database/tradecore_vb.sql'
            }


# Worker detection utilities
def detect_server_type() -> ServerType:
    """Detect the server type we're running under"""
    # Check for Granian (ASGI server)
    if 'granian' in os.environ.get('SERVER_SOFTWARE', '').lower():
        return ServerType.GRANIAN

    # Check if granian is in the process
    try:
        import psutil
        current_process = psutil.Process()
        cmdline = ' '.join(current_process.cmdline())
        if 'granian' in cmdline:
            return ServerType.GRANIAN
    except (ImportError, AttributeError) as e:
        logger.debug(f"Could not detect server via psutil: {e}")
    except Exception as e:
        # Catch any psutil-specific errors
        if 'psutil' in str(type(e).__module__):
            logger.debug(f"psutil error during server detection: {e}")
        else:
            raise

    return ServerType.UNKNOWN


def get_worker_count() -> int:
    """Get the number of workers"""
    # Try to get from environment (universal worker count variable)
    if workers := os.environ.get('WEB_CONCURRENCY'):
        return int(workers)

    # Granian: Check --workers flag from process
    server_type = detect_server_type()
    if server_type == ServerType.GRANIAN:
        # Try to detect from process (granian spawns worker processes)
        try:
            import psutil
            granian_workers = len([p for p in psutil.process_iter(['name', 'cmdline'])
                                    if 'granian' in ' '.join(p.info['cmdline']).lower()])
            if granian_workers > 1:
                return granian_workers - 1  # Subtract master process
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not count workers via psutil: {e}")
        except Exception as e:
            # Catch any psutil-specific errors
            if 'psutil' in str(type(e).__module__):
                logger.debug(f"psutil error during worker count: {e}")
            else:
                raise

        # Default to CPU count for Granian
        return multiprocessing.cpu_count()

    # Single worker for dev/test
    return 1


def calculate_pool_size(
        base_min: int,
        base_max: int,
        worker_count: int,
        max_total_connections: int = 100
) -> tuple[int, int]:
    """
    Calculate optimal pool size based on worker count.

    Formula:
    - Total connections = worker_count * max_size
    - We want to stay under PostgreSQL's max_connections
    - Leave some connections for admin/monitoring (20%)

    For production PostgreSQL should have at least 500-1000 connections!
    """
    # Reserve 20% for admin tasks
    available_connections = int(max_total_connections * 0.8)

    # Calculate per-worker max
    max_per_worker = max(1, available_connections // worker_count)

    # Adjust base sizes
    adjusted_max = min(base_max, max_per_worker)
    adjusted_min = min(base_min, adjusted_max // 2)  # Min is half of max

    # Ensure reasonable minimums
    adjusted_min = max(1, adjusted_min)
    adjusted_max = max(2, adjusted_max)

    logger.info(
        f"Pool sizing: {worker_count} workers, "
        f"base {base_min}-{base_max} -> adjusted {adjusted_min}-{adjusted_max}"
    )

    return adjusted_min, adjusted_max


# Database profiles for different environments
class DatabaseProfiles:
    """Pre-configured database profiles with auto-scaling support"""

    @staticmethod
    def development() -> DatabaseConfig:
        """Development profile with reasonable pools"""
        worker_count = get_worker_count()
        # Development still needs decent pools for testing
        main_min, main_max = calculate_pool_size(10, 50, worker_count, max_total_connections=200)
        vb_min, vb_max = calculate_pool_size(5, 25, worker_count, max_total_connections=200)

        return DatabaseConfig(
            main_pool=PoolConfig(
                min_size=main_min,
                max_size=main_max,
                timeout=5.0,
                command_timeout=30.0,
                max_idle_time=600.0,  # 10 minutes
                statement_cache_size=50,
                # Use only safe commands that don't require superuser privileges
                init_commands=[
                    "SET application_name = 'tradecore_dev'",
                    "SET statement_timeout = '30s'",  # Safe timeout for dev
                ]
            ),
            vb_pool=PoolConfig(
                min_size=vb_min,
                max_size=vb_max,
                timeout=5.0,
                command_timeout=30.0
            ),
            health_check_interval=60.0,  # Less frequent in dev
            max_total_connections=200,  # Even dev needs decent connections
        )

    @staticmethod
    def production() -> DatabaseConfig:
        """Production profile with proper sizing for real workloads"""
        worker_count = get_worker_count()
        # Reasonable base values for production
        # Assuming PostgreSQL configured with 500+ max_connections
        main_min, main_max = calculate_pool_size(50, 200, worker_count, max_total_connections=500)
        vb_min, vb_max = calculate_pool_size(20, 100, worker_count, max_total_connections=500)

        return DatabaseConfig(
            main_pool=PoolConfig(
                min_size=main_min,
                max_size=main_max,
                timeout=10.0,
                command_timeout=60.0,
                min_idle=max(10, main_min // 2),  # Keep more connections ready
                max_idle_time=1800.0,  # 30 minutes - keep connections longer
                max_lifetime=7200.0,  # 2 hours
                max_queries=100000,
                statement_cache_size=200,
                # These server settings are hints, not commands
                server_settings={
                    'jit': 'on',
                    'max_parallel_workers_per_gather': '4',
                },
                init_commands=[
                    "SET application_name = 'tradecore_prod'",
                    "SET statement_timeout = '60s'",
                    "SET lock_timeout = '10s'",
                    "SET idle_in_transaction_session_timeout = '30s'",
                ]
            ),
            vb_pool=PoolConfig(
                min_size=vb_min,
                max_size=vb_max,
                timeout=10.0,
                command_timeout=60.0,
                min_idle=max(5, vb_min // 2),
                max_idle_time=1800.0,
            ),
            health_check_interval=30.0,
            health_check_timeout=10.0,
            max_total_connections=500,  # Proper production value
        )

    @staticmethod
    def high_performance() -> DatabaseConfig:
        """High performance profile for serious production loads"""
        worker_count = get_worker_count()
        # High base values - requires PostgreSQL with 1000+ max_connections
        main_min, main_max = calculate_pool_size(100, 400, worker_count, max_total_connections=1000)
        vb_min, vb_max = calculate_pool_size(50, 200, worker_count, max_total_connections=1000)

        return DatabaseConfig(
            main_pool=PoolConfig(
                min_size=main_min,
                max_size=main_max,
                timeout=2.0,  # Fast fail
                command_timeout=5.0,
                min_idle=max(20, main_min // 2),  # Keep many connections ready
                max_idle_time=3600.0,  # Keep connections for 1 hour
                max_lifetime=14400.0,  # 4 hours
                statement_cache_size=500,  # Large statement cache
                # These server settings are hints, not commands
                server_settings={
                    'jit': 'off',  # Disable JIT for consistent latency
                    'random_page_cost': '1.1',  # Assume fast SSD
                    'effective_io_concurrency': '200',  # NVMe optimized
                    'max_parallel_workers_per_gather': '8',
                },
                init_commands=[
                    "SET application_name = 'tradecore_hp'",
                    "SET statement_timeout = '5s'",  # Fail fast
                    "SET lock_timeout = '2s'",
                    "SET tcp_keepalives_idle = '60'",
                    "SET tcp_keepalives_interval = '10'",
                    "SET tcp_keepalives_count = '6'",
                ]
            ),
            vb_pool=PoolConfig(
                min_size=vb_min,
                max_size=vb_max,
                timeout=2.0,
                command_timeout=5.0,
                min_idle=max(10, vb_min // 2),
                max_idle_time=3600.0,
            ),
            health_check_interval=15.0,  # More frequent checks
            health_check_timeout=2.0,
            connection_retry_attempts=1,  # Fail fast, don't retry much
            connection_retry_delay=0.1,
            max_total_connections=1000,  # Serious production PostgreSQL
        )

    @staticmethod
    def testing() -> DatabaseConfig:
        """Testing profile with minimal resources"""
        return DatabaseConfig(
            main_pool=PoolConfig(
                min_size=1,
                max_size=5,
                timeout=30.0,  # Long timeout for debugging
                command_timeout=120.0,
                statement_cache_size=10,
            ),
            vb_pool=PoolConfig(
                min_size=1,
                max_size=3,
                timeout=30.0,
                command_timeout=120.0,
            ),
            enable_vb_database=False,  # Usually disabled in tests
            health_check_interval=300.0,  # Rare checks in tests
            auto_scale_pools=False,  # No auto-scaling in tests
        )


# Global configuration instance
_db_config: Optional[DatabaseConfig] = None


def get_database_config() -> DatabaseConfig:
    """Get database configuration with env overrides"""
    global _db_config

    if _db_config is None:
        # Log worker detection
        server_type = detect_server_type()
        worker_count = get_worker_count()
        logger.info(f"Server type: {server_type}, Worker count: {worker_count}")

        # Select profile based on environment
        env = os.getenv('ENVIRONMENT', 'development').lower()

        if env == 'production':
            _db_config = DatabaseProfiles.production()
        elif env == 'high_performance':
            _db_config = DatabaseProfiles.high_performance()
        elif env == 'testing':
            _db_config = DatabaseProfiles.testing()
        else:
            _db_config = DatabaseProfiles.development()

        # Apply env overrides
        _apply_env_overrides(_db_config)

        # Log final configuration
        logger.info(
            f"Database pools configured - Main: {_db_config.main_pool.min_size}-{_db_config.main_pool.max_size}, "
            f"VB: {_db_config.vb_pool.min_size}-{_db_config.vb_pool.max_size}"
        )

    return _db_config


def set_database_config(config: DatabaseConfig) -> None:
    """Set database configuration (mainly for testing)"""
    global _db_config
    _db_config = config


def reset_database_config() -> None:
    """Reset database configuration (mainly for testing)"""
    global _db_config
    _db_config = None


def _apply_env_overrides(config: DatabaseConfig) -> None:
    """Apply environment variable overrides to configuration"""

    # Connection strings (sensitive data stays in .env)
    config.main_dsn = os.getenv('POSTGRES_DSN') or os.getenv('DATABASE_URL')
    config.vb_dsn = os.getenv('VB_POSTGRES_DSN') or os.getenv('VB_DATABASE_URL')

    # Check if auto-scaling should be disabled
    if val := os.getenv('DB_AUTO_SCALE_POOLS'):
        config.auto_scale_pools = val.lower() in ('true', '1', 'yes', 'on')

    # Max total connections override
    if val := os.getenv('DB_MAX_TOTAL_CONNECTIONS'):
        config.max_total_connections = int(val)

    # Manual pool size overrides (these bypass auto-scaling)
    if os.getenv('PG_POOL_MIN_SIZE') or os.getenv('PG_POOL_MAX_SIZE'):
        config.auto_scale_pools = False  # Disable auto-scaling if manual override

    # Main pool overrides
    if val := os.getenv('PG_POOL_MIN_SIZE'):
        config.main_pool.min_size = int(val)
    if val := os.getenv('PG_POOL_MAX_SIZE'):
        config.main_pool.max_size = int(val)
    if val := os.getenv('PG_POOL_TIMEOUT_SEC'):
        config.main_pool.timeout = float(val)
    if val := os.getenv('PG_COMMAND_TIMEOUT_SEC'):
        config.main_pool.command_timeout = float(val)

    # VB pool overrides
    if val := os.getenv('VB_PG_POOL_MIN_SIZE'):
        config.vb_pool.min_size = int(val)
    if val := os.getenv('VB_PG_POOL_MAX_SIZE'):
        config.vb_pool.max_size = int(val)
    if val := os.getenv('VB_PG_POOL_TIMEOUT_SEC'):
        config.vb_pool.timeout = float(val)
    if val := os.getenv('VB_PG_COMMAND_TIMEOUT_SEC'):
        config.vb_pool.command_timeout = float(val)

    # Feature flags
    if val := os.getenv('ENABLE_VB_DATABASE'):
        config.enable_vb_database = val.lower() in ('true', '1', 'yes', 'on')

    # Health check settings
    if val := os.getenv('DB_HEALTH_CHECK_INTERVAL'):
        config.health_check_interval = float(val)
    if val := os.getenv('DB_HEALTH_CHECK_TIMEOUT'):
        config.health_check_timeout = float(val)
    if val := os.getenv('DB_HEALTH_CHECK_QUERY'):
        config.health_check_query = val

    # Retry settings
    if val := os.getenv('DB_CONNECTION_RETRY_ATTEMPTS'):
        config.connection_retry_attempts = int(val)
    if val := os.getenv('DB_CONNECTION_RETRY_DELAY'):
        config.connection_retry_delay = float(val)

    # Performance monitoring thresholds
    if val := os.getenv('DB_SLOW_QUERY_THRESHOLD_MS'):
        config.slow_query_threshold_ms = float(val)
    if val := os.getenv('DB_POOL_EXHAUSTION_THRESHOLD'):
        config.pool_exhaustion_threshold = float(val)
    if val := os.getenv('DB_LONG_TRANSACTION_THRESHOLD_MS'):
        config.long_transaction_threshold_ms = float(val)
    if val := os.getenv('DB_SLOW_ACQUIRE_THRESHOLD_MS'):
        config.slow_acquire_threshold_ms = float(val)

    # Performance settings (override pool configs)
    if val := os.getenv('DB_STATEMENT_CACHE_SIZE'):
        config.main_pool.statement_cache_size = int(val)
        config.vb_pool.statement_cache_size = int(val)

    if val := os.getenv('DB_MAX_CACHED_STATEMENT_LIFETIME'):
        config.main_pool.max_cached_statement_lifetime = int(val)
        config.vb_pool.max_cached_statement_lifetime = int(val)

    if val := os.getenv('DB_MAX_QUERIES'):
        config.main_pool.max_queries = int(val)
        config.vb_pool.max_queries = int(val)

    # Build VB DSN from components if not provided directly
    if not config.vb_dsn and config.enable_vb_database:
        host = os.getenv('VB_POSTGRES_HOST', os.getenv('POSTGRES_HOST', 'localhost'))
        port = os.getenv('VB_POSTGRES_PORT', os.getenv('POSTGRES_PORT', '5432'))
        user = os.getenv('VB_POSTGRES_USER', os.getenv('POSTGRES_USER', 'postgres'))
        password = os.getenv('VB_POSTGRES_PASSWORD', os.getenv('POSTGRES_PASSWORD', ''))
        database = os.getenv('VB_DATABASE_NAME', 'tradecore_vb')

        if password:
            config.vb_dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        else:
            config.vb_dsn = f"postgresql://{user}@{host}:{port}/{database}"


# Utility functions
def get_pool_config(database: str = 'main') -> PoolConfig:
    """Get pool configuration for specific database"""
    config = get_database_config()
    return config.main_pool if database == 'main' else config.vb_pool


def get_dsn(database: str = 'main') -> Optional[str]:
    """Get DSN for specific database"""
    config = get_database_config()
    return config.main_dsn if database == 'main' else config.vb_dsn


def is_vb_enabled() -> bool:
    """Check if VB database is enabled"""
    config = get_database_config()
    return config.enable_vb_database


def get_pool_stats() -> Dict[str, Any]:
    """Get current pool configuration stats"""
    config = get_database_config()
    server_type = detect_server_type()
    worker_count = get_worker_count()

    return {
        "server_type": server_type.value,
        "worker_count": worker_count,
        "auto_scale_enabled": config.auto_scale_pools,
        "max_total_connections": config.max_total_connections,
        "main_pool": {
            "min_size": config.main_pool.min_size,
            "max_size": config.main_pool.max_size,
            "total_max": config.main_pool.max_size * worker_count
        },
        "vb_pool": {
            "min_size": config.vb_pool.min_size,
            "max_size": config.vb_pool.max_size,
            "total_max": config.vb_pool.max_size * worker_count
        },
        "total_connections": (config.main_pool.max_size + config.vb_pool.max_size) * worker_count
    }


# =============================================================================
# EOF
# =============================================================================

"""
POSTGRESQL CONFIGURATION FOR PRODUCTION:

1. Edit postgresql.conf:
   max_connections = 500         # Minimum for production
   shared_buffers = 4GB         # 25% of RAM
   effective_cache_size = 12GB  # 75% of RAM
   work_mem = 64MB
   maintenance_work_mem = 1GB

2. For high-load (10k+ concurrent users):
   max_connections = 1000
   # And use PgBouncer for connection pooling

3. Environment variables:
   ENVIRONMENT=production       # or high_performance
   DB_MAX_TOTAL_CONNECTIONS=500 # Match PostgreSQL max_connections
"""