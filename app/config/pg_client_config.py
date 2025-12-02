# app/config/pg_client_config.py
# =============================================================================
# File: app/config/pg_client_config.py
# Description: Database configuration for PostgreSQL pool
# UPDATED: Using BaseConfig pattern with Pydantic v2
# =============================================================================

from functools import lru_cache
import os
import multiprocessing
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict

from app.common.base.base_config import BaseConfig, BASE_CONFIG_DICT
from app.config.logging_config import get_logger

log = get_logger("wellwon.config.pg_client")


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


class PoolConfig(BaseModel):
    """PostgreSQL connection pool configuration (nested model)"""
    # Basic pool settings
    min_size: int = Field(default=20, description="Minimum pool size")
    max_size: int = Field(default=100, description="Maximum pool size")
    timeout: float = Field(default=5.0, description="Pool acquisition timeout in seconds")
    command_timeout: float = Field(default=10.0, description="Default command timeout")

    # Pool behavior
    min_idle: int = Field(default=5, description="Keep some connections ready")
    max_idle_time: float = Field(default=300.0, description="Close idle connections after seconds")
    max_lifetime: float = Field(default=3600.0, description="Close connections after seconds")
    max_queries: int = Field(default=50000, description="Close connection after this many queries")

    # Connection setup
    server_settings: Optional[Dict[str, str]] = Field(default=None)
    init_commands: Optional[List[str]] = Field(default=None)

    # Performance
    statement_cache_size: int = Field(default=100)
    max_cached_statement_lifetime: int = Field(default=300)
    max_inactive_connection_lifetime: float = Field(default=300.0)

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
        commands = self.init_commands or []

        async def init_connection(conn):
            for cmd in commands:
                await conn.execute(cmd)

        return init_connection


class PostgresConfig(BaseConfig):
    """PostgreSQL database configuration for WellWon"""

    model_config = SettingsConfigDict(
        **BASE_CONFIG_DICT,
        env_prefix='PG_',
    )

    # Connection string
    main_dsn: Optional[str] = Field(
        default=None,
        alias="POSTGRES_DSN",
        description="Main database DSN"
    )

    # Pool configuration
    pool_min_size: int = Field(default=20, description="Pool min size")
    pool_max_size: int = Field(default=100, description="Pool max size")
    pool_timeout: float = Field(default=5.0, description="Pool timeout")
    pool_command_timeout: float = Field(default=10.0, description="Pool command timeout")

    # Features
    run_schemas_on_startup: bool = Field(default=True)

    # Health check
    health_check_interval: float = Field(default=30.0)
    health_check_query: str = Field(default="SELECT 1")
    health_check_timeout: float = Field(default=5.0)

    # Connection retry
    connection_retry_attempts: int = Field(default=3)
    connection_retry_delay: float = Field(default=0.5)

    # Auto-scaling
    auto_scale_pools: bool = Field(default=True)
    max_total_connections: int = Field(default=500)

    # Performance monitoring
    slow_query_threshold_ms: float = Field(default=1000.0)
    pool_exhaustion_threshold: float = Field(default=0.9)
    long_transaction_threshold_ms: float = Field(default=2000.0)
    slow_acquire_threshold_ms: float = Field(default=500.0)

    # Statement cache
    statement_cache_size: int = Field(default=100)
    max_cached_statement_lifetime: int = Field(default=300)
    max_queries: int = Field(default=50000)

    @property
    def main_pool(self) -> PoolConfig:
        """Get main pool configuration"""
        return PoolConfig(
            min_size=self.pool_min_size,
            max_size=self.pool_max_size,
            timeout=self.pool_timeout,
            command_timeout=self.pool_command_timeout,
            statement_cache_size=self.statement_cache_size,
            max_cached_statement_lifetime=self.max_cached_statement_lifetime,
            max_queries=self.max_queries,
        )

    def get_main_dsn(self) -> Optional[str]:
        """Get main DSN"""
        return self.main_dsn


# =============================================================================
# Worker Detection Utilities
# =============================================================================

def detect_server_type() -> ServerType:
    """Detect the server type we're running under"""
    if 'granian' in os.environ.get('SERVER_SOFTWARE', '').lower():
        return ServerType.GRANIAN

    try:
        import psutil
        current_process = psutil.Process()
        cmdline = ' '.join(current_process.cmdline())
        if 'granian' in cmdline:
            return ServerType.GRANIAN
    except (ImportError, AttributeError) as e:
        log.debug(f"Could not detect server via psutil: {e}")
    except Exception as e:
        if 'psutil' in str(type(e).__module__):
            log.debug(f"psutil error during server detection: {e}")
        else:
            raise

    return ServerType.UNKNOWN


def get_worker_count() -> int:
    """Get the number of workers"""
    if workers := os.environ.get('WEB_CONCURRENCY'):
        return int(workers)

    server_type = detect_server_type()
    if server_type == ServerType.GRANIAN:
        try:
            import psutil
            granian_workers = len([p for p in psutil.process_iter(['name', 'cmdline'])
                                   if 'granian' in ' '.join(p.info['cmdline']).lower()])
            if granian_workers > 1:
                return granian_workers - 1
        except (ImportError, AttributeError) as e:
            log.debug(f"Could not count workers via psutil: {e}")
        except Exception as e:
            if 'psutil' in str(type(e).__module__):
                log.debug(f"psutil error during worker count: {e}")
            else:
                raise

        return multiprocessing.cpu_count()

    return 1


def calculate_pool_size(
        base_min: int,
        base_max: int,
        worker_count: int,
        max_total_connections: int = 100
) -> tuple[int, int]:
    """Calculate optimal pool size based on worker count."""
    available_connections = int(max_total_connections * 0.8)
    max_per_worker = max(1, available_connections // worker_count)
    adjusted_max = min(base_max, max_per_worker)
    adjusted_min = min(base_min, adjusted_max // 2)
    adjusted_min = max(1, adjusted_min)
    adjusted_max = max(2, adjusted_max)

    log.info(
        f"Pool sizing: {worker_count} workers, "
        f"base {base_min}-{base_max} -> adjusted {adjusted_min}-{adjusted_max}"
    )

    return adjusted_min, adjusted_max


# =============================================================================
# Factory Function
# =============================================================================

@lru_cache(maxsize=1)
def get_postgres_config() -> PostgresConfig:
    """Get PostgreSQL configuration singleton (cached)."""
    server_type = detect_server_type()
    worker_count = get_worker_count()
    log.info(f"Server type: {server_type}, Worker count: {worker_count}")

    config = PostgresConfig()

    # Auto-scale pool sizes if enabled
    if config.auto_scale_pools:
        pool_min, pool_max = calculate_pool_size(
            config.pool_min_size,
            config.pool_max_size,
            worker_count,
            config.max_total_connections
        )

        # Update config with calculated values
        config = PostgresConfig(
            **config.model_dump(exclude={'pool_min_size', 'pool_max_size'}),
            pool_min_size=pool_min,
            pool_max_size=pool_max,
        )

    log.info(f"Database pool configured: {config.pool_min_size}-{config.pool_max_size}")

    return config


def reset_postgres_config() -> None:
    """Reset config singleton (for testing)."""
    get_postgres_config.cache_clear()


# =============================================================================
# Backward Compatibility Aliases
# =============================================================================

# Type alias for backward compatibility
DatabaseConfig = PostgresConfig


def get_database_config():
    """Alias for get_postgres_config (backward compatibility)."""
    return get_postgres_config()


def get_pool_config(database: str = 'main') -> PoolConfig:
    """Get pool configuration"""
    config = get_postgres_config()
    return config.main_pool


def get_dsn(database: str = 'main') -> Optional[str]:
    """Get DSN"""
    config = get_postgres_config()
    return config.get_main_dsn()


def get_pool_stats() -> Dict[str, Any]:
    """Get current pool configuration stats"""
    config = get_postgres_config()
    server_type = detect_server_type()
    worker_count = get_worker_count()

    return {
        "server_type": server_type.value,
        "worker_count": worker_count,
        "auto_scale_enabled": config.auto_scale_pools,
        "max_total_connections": config.max_total_connections,
        "pool": {
            "min_size": config.pool_min_size,
            "max_size": config.pool_max_size,
            "total_max": config.pool_max_size * worker_count
        },
        "total_connections": config.pool_max_size * worker_count
    }
