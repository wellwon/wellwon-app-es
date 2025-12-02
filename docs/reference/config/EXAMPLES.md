# Configuration Examples

Copy-paste examples for common configuration patterns using Pydantic v2 BaseSettings.

## Base Configuration Class

```python
# config/base_config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseConfig(BaseSettings):
    """Base configuration class."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
```

## Database Configuration

```python
# config/database_config.py
from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from config.base_config import BaseConfig


class DatabaseConfig(BaseConfig):
    """PostgreSQL database configuration."""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="DB_",
    )

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    name: str = Field(default="myapp", description="Database name")
    user: str = Field(default="postgres", description="Database user")
    password: SecretStr = Field(description="Database password")

    min_pool_size: int = Field(default=5, description="Min connection pool size")
    max_pool_size: int = Field(default=20, description="Max connection pool size")
    command_timeout: float = Field(default=60.0, description="Command timeout (s)")

    @property
    def connection_string(self) -> str:
        """Build connection string."""
        pwd = self.password.get_secret_value()
        return f"postgresql://{self.user}:{pwd}@{self.host}:{self.port}/{self.name}"


@lru_cache(maxsize=1)
def get_database_config() -> DatabaseConfig:
    return DatabaseConfig()
```

```bash
# .env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp
DB_USER=app_user
DB_PASSWORD=secret123
DB_MAX_POOL_SIZE=30
```

## Redis Configuration

```python
# config/redis_config.py
from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from config.base_config import BaseConfig


class RedisConfig(BaseConfig):
    """Redis configuration."""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="REDIS_",
    )

    url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    password: SecretStr | None = Field(
        default=None,
        description="Redis password (optional)"
    )

    max_connections: int = Field(default=100, description="Connection pool size")
    socket_timeout: float = Field(default=5.0, description="Socket timeout (s)")
    socket_connect_timeout: float = Field(default=5.0, description="Connect timeout (s)")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")
    health_check_interval: int = Field(default=30, description="Health check interval (s)")


@lru_cache(maxsize=1)
def get_redis_config() -> RedisConfig:
    return RedisConfig()
```

```bash
# .env
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=optional_password
REDIS_MAX_CONNECTIONS=150
```

## JWT Authentication Configuration

```python
# config/jwt_config.py
from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from config.base_config import BaseConfig


class JWTConfig(BaseConfig):
    """JWT authentication configuration."""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="JWT_",
    )

    secret_key: SecretStr = Field(description="JWT signing secret key")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=30,
        description="Access token expiry (minutes)"
    )
    refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token expiry (days)"
    )
    issuer: str = Field(default="myapp", description="Token issuer")
    audience: str = Field(default="myapp-users", description="Token audience")


@lru_cache(maxsize=1)
def get_jwt_config() -> JWTConfig:
    return JWTConfig()
```

```bash
# .env
JWT_SECRET_KEY=your-256-bit-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
```

## Worker/Background Task Configuration

```python
# config/worker_config.py
from functools import lru_cache
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from config.base_config import BaseConfig


class WorkerConfig(BaseConfig):
    """Background worker configuration."""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="WORKER_",
    )

    poll_interval_ms: int = Field(default=100, description="Event poll interval (ms)")
    batch_size: int = Field(default=100, description="Events per batch")
    max_concurrent: int = Field(default=10, description="Max concurrent handlers")
    consumer_group: str = Field(default="workers", description="Consumer group name")

    retry_max_attempts: int = Field(default=3, description="Max retry attempts")
    retry_delay_ms: int = Field(default=1000, description="Initial retry delay (ms)")
    retry_multiplier: float = Field(default=2.0, description="Exponential backoff multiplier")

    enable_dlq: bool = Field(default=True, description="Enable dead letter queue")
    dlq_retention_hours: int = Field(default=168, description="DLQ retention (hours)")


@lru_cache(maxsize=1)
def get_worker_config() -> WorkerConfig:
    return WorkerConfig()
```

## Circuit Breaker Configuration (Pydantic BaseModel)

```python
# config/reliability_config.py
from pydantic import BaseModel, Field


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker pattern configuration."""

    model_config = {"frozen": False, "extra": "ignore"}

    name: str
    failure_threshold: int = Field(default=5, description="Failures before opening")
    success_threshold: int = Field(default=3, description="Successes to close")
    reset_timeout_seconds: int = Field(default=30, description="Timeout before half-open")
    half_open_max_calls: int = Field(default=3, description="Calls allowed in half-open")


class RetryConfig(BaseModel):
    """Retry pattern configuration."""

    model_config = {"frozen": False, "extra": "ignore"}

    max_attempts: int = Field(default=3, description="Maximum retry attempts")
    initial_delay_ms: int = Field(default=100, description="Initial delay (ms)")
    max_delay_ms: int = Field(default=5000, description="Maximum delay (ms)")
    multiplier: float = Field(default=2.0, description="Backoff multiplier")
    jitter: bool = Field(default=True, description="Add random jitter")


# Factory class with presets
class ReliabilityConfigs:
    """Factory for reliability configurations."""

    @staticmethod
    def default_circuit_breaker(name: str) -> CircuitBreakerConfig:
        return CircuitBreakerConfig(name=name)

    @staticmethod
    def aggressive_circuit_breaker(name: str) -> CircuitBreakerConfig:
        return CircuitBreakerConfig(
            name=name,
            failure_threshold=3,
            reset_timeout_seconds=60,
        )

    @staticmethod
    def default_retry() -> RetryConfig:
        return RetryConfig()

    @staticmethod
    def fast_retry() -> RetryConfig:
        return RetryConfig(
            max_attempts=5,
            initial_delay_ms=50,
            max_delay_ms=1000,
        )
```

## Hybrid Configuration (Settings + Dict)

```python
# config/cache_config.py
from functools import lru_cache
from typing import Dict, Any
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from config.base_config import BaseConfig


class CacheSettings(BaseConfig):
    """Top-level cache settings from env."""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="CACHE_",
    )

    enabled: bool = Field(default=True, description="Enable caching")
    key_prefix: str = Field(default="app", description="Cache key prefix")
    default_ttl: int = Field(default=300, description="Default TTL (s)")
    debug_mode: bool = Field(default=False, description="Debug mode")


@lru_cache(maxsize=1)
def get_cache_settings() -> CacheSettings:
    return CacheSettings()


# Complex nested TTL structure (too deep for env vars)
TTL_CONFIG: Dict[str, Dict[str, int]] = {
    "user": {"profile": 3600, "settings": 1800, "permissions": 900},
    "product": {"detail": 300, "list": 60, "search": 120},
    "api": {"response": 300, "schema": 3600},
}


def get_ttl(domain: str, type_: str) -> int:
    """Get TTL with fallback to default."""
    settings = get_cache_settings()
    return TTL_CONFIG.get(domain, {}).get(type_, settings.default_ttl)


def override_from_env() -> None:
    """Apply Pydantic settings + direct env overrides."""
    settings = get_cache_settings()

    # Pydantic handles CACHE_ENABLED, CACHE_KEY_PREFIX, etc.

    # Direct env overrides for TTLs
    import os
    if env_val := os.getenv('CACHE_TTL_USER_PROFILE'):
        TTL_CONFIG['user']['profile'] = int(env_val)
    if env_val := os.getenv('CACHE_TTL_PRODUCT_DETAIL'):
        TTL_CONFIG['product']['detail'] = int(env_val)


# Initialize on import
override_from_env()
```

## Environment-Specific Factory Functions

```python
# config/app_config.py
from functools import lru_cache
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from config.base_config import BaseConfig


class AppConfig(BaseConfig):
    """Application configuration."""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="APP_",
    )

    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    workers: int = Field(default=4, description="Worker processes")


def create_default_config() -> AppConfig:
    return AppConfig()


def create_development_config() -> AppConfig:
    return AppConfig(
        debug=True,
        log_level="DEBUG",
        workers=1,
    )


def create_production_config() -> AppConfig:
    return AppConfig(
        debug=False,
        log_level="WARNING",
        workers=8,
    )


def create_testing_config() -> AppConfig:
    return AppConfig(
        debug=True,
        log_level="DEBUG",
        workers=1,
    )


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    """Get config based on ENVIRONMENT env var."""
    import os
    env = os.getenv("ENVIRONMENT", "development")

    factories = {
        "development": create_development_config,
        "production": create_production_config,
        "testing": create_testing_config,
    }

    factory = factories.get(env, create_default_config)
    return factory()
```

## Complete .env Example

```bash
# .env

# Environment
ENVIRONMENT=development

# Application
APP_DEBUG=true
APP_LOG_LEVEL=DEBUG
APP_WORKERS=2

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp_dev
DB_USER=developer
DB_PASSWORD=dev_password

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50

# JWT
JWT_SECRET_KEY=dev-secret-key-change-in-production
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Worker
WORKER_POLL_INTERVAL_MS=100
WORKER_BATCH_SIZE=50

# Cache
CACHE_ENABLED=true
CACHE_KEY_PREFIX=myapp
CACHE_DEFAULT_TTL=300
CACHE_DEBUG_MODE=true
```
