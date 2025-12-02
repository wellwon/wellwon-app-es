# Pydantic v2 Configuration Pattern

A complete reference for building type-safe, environment-based configuration in Python applications using Pydantic v2 BaseSettings.

## Overview

This pattern provides:
- Type-safe configuration from environment variables
- Automatic .env file loading
- SecretStr for sensitive values
- Singleton pattern via `@lru_cache`
- JSON schema generation for admin UIs
- Validation with descriptive errors

## Base Configuration Class

Create a base class all configs inherit from:

```python
# base_config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class BaseConfig(BaseSettings):
    """
    Base configuration class for all application configs.

    Features:
    - Automatic .env file loading
    - Environment variable binding
    - Type validation
    - Extra fields ignored (safe for unknown env vars)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
```

## Basic Usage

```python
from functools import lru_cache
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from base_config import BaseConfig


class DatabaseConfig(BaseConfig):
    """Database connection configuration."""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="DB_",
    )

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    name: str = Field(default="myapp", description="Database name")
    user: str = Field(default="postgres", description="Database user")


@lru_cache(maxsize=1)
def get_database_config() -> DatabaseConfig:
    """Cached singleton getter."""
    return DatabaseConfig()
```

Environment variables:
```bash
DB_HOST=production.db.example.com
DB_PORT=5432
DB_NAME=myapp_prod
DB_USER=app_user
```

## Sensitive Values with SecretStr

```python
from pydantic import Field, SecretStr

class AuthConfig(BaseConfig):
    """Authentication configuration."""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="AUTH_",
    )

    jwt_secret: SecretStr = Field(description="JWT signing key")
    api_key: SecretStr = Field(description="External API key")
    password: SecretStr = Field(description="Service password")


# Usage
config = AuthConfig()
print(config.jwt_secret)  # SecretStr('**********')
print(config.jwt_secret.get_secret_value())  # actual-secret-value
print(config.model_dump())  # {"jwt_secret": "**********", ...}
```

## Type Coercion

Pydantic automatically converts environment variables:

```python
class ServerConfig(BaseConfig):
    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="SERVER_",
    )

    # String env var -> int
    port: int = 8080

    # String env var -> bool
    debug: bool = False

    # String env var -> float
    timeout: float = 30.0

    # String env var -> list (comma-separated)
    allowed_hosts: list[str] = ["localhost"]
```

```bash
SERVER_PORT=3000           # "3000" -> 3000
SERVER_DEBUG=true          # "true" -> True
SERVER_TIMEOUT=45.5        # "45.5" -> 45.5
SERVER_ALLOWED_HOSTS=["a.com","b.com"]  # JSON list
```

## Validation

### Field Constraints

```python
from pydantic import Field

class ValidatedConfig(BaseConfig):
    port: int = Field(default=8080, ge=1, le=65535)
    workers: int = Field(default=4, ge=1, le=32)
    timeout: float = Field(default=30.0, gt=0)
    name: str = Field(default="app", min_length=1, max_length=64)
```

### Custom Validators

```python
from pydantic import field_validator

class AdvancedConfig(BaseConfig):
    port: int = 8080
    log_level: str = "INFO"

    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        if v < 1024 and v not in (80, 443):
            raise ValueError("Non-standard privileged port")
        return v

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"Must be one of {valid}")
        return v.upper()
```

## Nested Configurations

### Using Dict Defaults

```python
from typing import Dict

class SnapshotConfig(BaseConfig):
    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="SNAPSHOT_",
    )

    default_interval: int = Field(default=100)

    intervals_by_type: Dict[str, int] = Field(
        default_factory=lambda: {
            "User": 200,
            "Order": 75,
            "Product": 150,
        }
    )
```

### Nested Pydantic Models

```python
from pydantic import BaseModel

class RetrySettings(BaseModel):
    max_attempts: int = 3
    initial_delay_ms: int = 100
    max_delay_ms: int = 5000
    multiplier: float = 2.0

class ServiceConfig(BaseConfig):
    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="SERVICE_",
        env_nested_delimiter="__",
    )

    host: str = "localhost"
    retry: RetrySettings = Field(default_factory=RetrySettings)
```

```bash
SERVICE_HOST=api.example.com
SERVICE_RETRY__MAX_ATTEMPTS=5
SERVICE_RETRY__INITIAL_DELAY_MS=200
```

## Factory Functions

```python
def create_default_config() -> ServiceConfig:
    """Create default configuration."""
    return ServiceConfig()


def create_development_config() -> ServiceConfig:
    """Development-optimized configuration."""
    return ServiceConfig(
        debug=True,
        log_level="DEBUG",
        timeout_seconds=5,
    )


def create_production_config() -> ServiceConfig:
    """Production-optimized configuration."""
    return ServiceConfig(
        debug=False,
        log_level="WARNING",
        timeout_seconds=30,
    )


def create_testing_config() -> ServiceConfig:
    """Testing-optimized configuration."""
    return ServiceConfig(
        debug=True,
        log_level="DEBUG",
        timeout_seconds=1,
    )
```

## JSON Schema for Admin UIs

```python
config = ServiceConfig()

# Get JSON schema for UI generation
schema = config.model_json_schema()
# {
#   "properties": {
#     "host": {"default": "localhost", "description": "...", "type": "string"},
#     ...
#   },
#   "required": [...],
#   "type": "object"
# }

# Get current values (SecretStr values masked)
values = config.model_dump()
# {"host": "localhost", "api_key": "**********", ...}
```

## Hybrid Approach for Complex Configs

When you have deeply nested configuration that doesn't map well to environment variables:

```python
from functools import lru_cache
from typing import Dict, Any
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from base_config import BaseConfig


class CacheSettings(BaseConfig):
    """Top-level cache settings from env."""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="CACHE_",
    )

    enabled: bool = Field(default=True, description="Enable caching")
    key_prefix: str = Field(default="app", description="Cache key prefix")
    default_ttl: int = Field(default=300, description="Default TTL seconds")


@lru_cache(maxsize=1)
def get_cache_settings() -> CacheSettings:
    return CacheSettings()


# Complex nested structure stays as dict
TTL_CONFIG: Dict[str, Any] = {
    "user": {"profile": 3600, "settings": 1800},
    "product": {"detail": 300, "list": 60},
    "search": {"results": 120, "suggestions": 30},
}


def get_ttl(domain: str, type_: str) -> int:
    """Get TTL with fallback to settings default."""
    settings = get_cache_settings()
    return TTL_CONFIG.get(domain, {}).get(type_, settings.default_ttl)
```

## Best Practices

1. **Always use `@lru_cache(maxsize=1)`** for singleton pattern
2. **Use `SecretStr`** for passwords, API keys, tokens, secrets
3. **Provide `description`** in Field() for documentation
4. **Set sensible defaults** for optional fields
5. **Use `env_prefix`** to namespace environment variables
6. **Keep secrets out of version control** - use .env or environment
7. **Validate early** - fail fast on invalid configuration
8. **Document all variables** in README or config reference

## Migration from Legacy Patterns

### From dataclass

```python
# Before
@dataclass
class Config:
    host: str = "localhost"
    port: int = 8080

# After
class Config(BaseConfig):
    model_config = SettingsConfigDict(**BaseConfig.model_config)
    host: str = Field(default="localhost")
    port: int = Field(default=8080)
```

### From os.getenv

```python
# Before
host = os.getenv("HOST", "localhost")
port = int(os.getenv("PORT", "8080"))

# After
class Config(BaseConfig):
    host: str = "localhost"
    port: int = 8080

config = Config()  # Reads HOST, PORT automatically
```

### From dict config

```python
# Before
CONFIG = {"host": "localhost", "port": 8080}

# After
class Config(BaseConfig):
    host: str = "localhost"
    port: int = 8080

# Or hybrid if deeply nested (see above)
```
