# BaseConfig Class Reference

The `BaseConfig` class is the foundation for all configuration classes in TradeCore.

## Location

```python
from app.common.base.base_config import BaseConfig
```

## Implementation

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class BaseConfig(BaseSettings):
    """
    Base configuration class for all TradeCore configs.

    Features:
    - Automatic .env file loading
    - Environment variable binding
    - Type validation
    - Extra fields ignored (safe for unknown env vars)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore unknown env vars
        case_sensitive=False,
    )
```

## Usage Pattern

### Basic Config

```python
from app.common.base.base_config import BaseConfig
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from functools import lru_cache

class DatabaseConfig(BaseConfig):
    """Database connection configuration."""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="DB_",
    )

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    name: str = Field(default="mydb", description="Database name")

@lru_cache(maxsize=1)
def get_database_config() -> DatabaseConfig:
    return DatabaseConfig()
```

### With SecretStr

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

    # Access secret value when needed:
    # config.jwt_secret.get_secret_value()
```

### With Nested Dict Defaults

```python
from typing import Dict

class SnapshotConfig(BaseConfig):
    """Snapshot configuration with per-aggregate settings."""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="SNAPSHOT_",
    )

    default_interval: int = Field(default=100, description="Default snapshot interval")

    aggregate_intervals: Dict[str, int] = Field(
        default_factory=lambda: {
            "Order": 75,
            "Position": 75,
            "User": 200,
        },
        description="Custom intervals per aggregate type"
    )
```

## Key Features

### 1. Automatic Environment Variable Binding

Environment variables are automatically mapped to config fields:

```bash
# .env file
DB_HOST=production.db.example.com
DB_PORT=5432
```

```python
class DatabaseConfig(BaseConfig):
    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="DB_",
    )

    host: str = "localhost"  # Reads DB_HOST
    port: int = 5432         # Reads DB_PORT
```

### 2. Type Coercion

Pydantic automatically converts environment variables:

```bash
DB_PORT=5432           # String in env
DEBUG=true             # String in env
TIMEOUT=30.5           # String in env
```

```python
port: int = 5432       # Converted to int
debug: bool = False    # Converted to bool
timeout: float = 30.0  # Converted to float
```

### 3. Validation

```python
from pydantic import Field, field_validator

class ServerConfig(BaseConfig):
    port: int = Field(default=8080, ge=1, le=65535)

    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        if v < 1024 and v != 80 and v != 443:
            raise ValueError("Privileged ports require root")
        return v
```

### 4. JSON Schema Generation (Admin Panel)

```python
config = DatabaseConfig()

# Get JSON schema for UI generation
schema = config.model_json_schema()

# Get current values (excludes SecretStr values)
values = config.model_dump()
```

## Environment Variable Naming

| Field Name | Env Prefix | Environment Variable |
|------------|-----------|---------------------|
| `host` | `DB_` | `DB_HOST` |
| `max_connections` | `DB_` | `DB_MAX_CONNECTIONS` |
| `use_ssl` | `DB_` | `DB_USE_SSL` |

## Best Practices

1. **Always use `@lru_cache`** for singleton pattern
2. **Use `SecretStr`** for passwords, API keys, tokens
3. **Provide `description`** in Field() for documentation
4. **Set sensible defaults** for optional fields
5. **Use `env_prefix`** to namespace environment variables
