# Configuration Migration Guide

How to create new configurations or migrate existing ones to the BaseConfig pattern.

## Creating a New Config

### Step 1: Create the Config Class

```python
# app/config/my_service_config.py

from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from app.common.base.base_config import BaseConfig


class MyServiceConfig(BaseConfig):
    """
    Configuration for MyService.

    Environment variables are prefixed with MYSERVICE_
    """

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="MYSERVICE_",
    )

    # Required field (no default)
    api_url: str = Field(description="API endpoint URL")

    # Optional with default
    timeout_seconds: int = Field(
        default=30,
        description="Request timeout in seconds"
    )

    # Sensitive value
    api_key: SecretStr = Field(description="API authentication key")

    # Boolean flag
    enabled: bool = Field(
        default=True,
        description="Enable the service"
    )


@lru_cache(maxsize=1)
def get_my_service_config() -> MyServiceConfig:
    """Cached singleton getter."""
    return MyServiceConfig()
```

### Step 2: Add Environment Variables

```bash
# .env
MYSERVICE_API_URL=https://api.example.com
MYSERVICE_TIMEOUT_SECONDS=60
MYSERVICE_API_KEY=secret-key-here
MYSERVICE_ENABLED=true
```

### Step 3: Use in Your Code

```python
from app.config.my_service_config import get_my_service_config

config = get_my_service_config()
print(config.api_url)
print(config.api_key.get_secret_value())  # Access secret
```

## Migrating from @dataclass

### Before (dataclass)

```python
from dataclasses import dataclass
import os

@dataclass
class OldConfig:
    host: str = "localhost"
    port: int = 8080
    timeout: float = 30.0

def load_config():
    return OldConfig(
        host=os.getenv("HOST", "localhost"),
        port=int(os.getenv("PORT", "8080")),
        timeout=float(os.getenv("TIMEOUT", "30.0")),
    )
```

### After (BaseConfig)

```python
from functools import lru_cache
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from app.common.base.base_config import BaseConfig

class NewConfig(BaseConfig):
    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="",  # No prefix to match existing env vars
    )

    host: str = Field(default="localhost", description="Server host")
    port: int = Field(default=8080, description="Server port")
    timeout: float = Field(default=30.0, description="Timeout in seconds")

@lru_cache(maxsize=1)
def get_config() -> NewConfig:
    return NewConfig()
```

## Migrating from Dict-based Config

For complex nested configurations, use the hybrid approach:

### Before (Dict)

```python
CONFIG = {
    "core": {"enabled": True, "prefix": "myapp"},
    "ttl": {
        "user": {"profile": 3600, "settings": 1800},
        "cache": {"data": 300, "meta": 60},
    }
}

def get_ttl(domain: str, type_: str) -> int:
    return CONFIG["ttl"].get(domain, {}).get(type_, 300)
```

### After (Hybrid)

```python
from functools import lru_cache
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from app.common.base.base_config import BaseConfig

class CoreSettings(BaseConfig):
    """Top-level settings from env vars."""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="MYAPP_",
    )

    enabled: bool = Field(default=True, description="Enable service")
    prefix: str = Field(default="myapp", description="Key prefix")
    default_ttl: int = Field(default=300, description="Default TTL")

@lru_cache(maxsize=1)
def get_core_settings() -> CoreSettings:
    return CoreSettings()

# Keep complex nested structure as dict
TTL_CONFIG = {
    "user": {"profile": 3600, "settings": 1800},
    "cache": {"data": 300, "meta": 60},
}

def get_ttl(domain: str, type_: str) -> int:
    settings = get_core_settings()
    return TTL_CONFIG.get(domain, {}).get(type_, settings.default_ttl)
```

## Common Patterns

### Factory Functions

```python
def create_development_config() -> MyConfig:
    """Create development configuration."""
    return MyConfig(
        debug=True,
        log_level="DEBUG",
        timeout_seconds=5,
    )

def create_production_config() -> MyConfig:
    """Create production configuration."""
    return MyConfig(
        debug=False,
        log_level="INFO",
        timeout_seconds=30,
    )
```

### Validation

```python
from pydantic import field_validator

class ValidatedConfig(BaseConfig):
    port: int = Field(default=8080)

    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError(f"Port must be 1-65535, got {v}")
        return v
```

### Computed Properties

```python
class DatabaseConfig(BaseConfig):
    host: str = "localhost"
    port: int = 5432
    name: str = "mydb"
    user: str = "postgres"
    password: SecretStr

    @property
    def connection_string(self) -> str:
        pwd = self.password.get_secret_value()
        return f"postgresql://{self.user}:{pwd}@{self.host}:{self.port}/{self.name}"
```

## Checklist

When creating or migrating a config:

- [ ] Extend `BaseConfig`
- [ ] Set `env_prefix` in `model_config`
- [ ] Use `Field()` with descriptions
- [ ] Use `SecretStr` for sensitive values
- [ ] Add `@lru_cache(maxsize=1)` getter
- [ ] Update `.env.example` with new variables
- [ ] Test with `python -m py_compile path/to/config.py`
