# Configuration System

TradeCore uses a unified configuration pattern based on Pydantic v2 BaseSettings.

## Overview

All configuration classes extend `BaseConfig` from `app/common/base/base_config.py`, providing:

- **Type-safe settings** from environment variables
- **Automatic .env file loading**
- **SecretStr** for sensitive values (passwords, API keys)
- **Singleton pattern** via `@lru_cache`
- **Admin panel ready** (model_json_schema, model_dump)

## Quick Start

```python
from app.common.base.base_config import BaseConfig
from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict
from functools import lru_cache

class MyConfig(BaseConfig):
    """Configuration description."""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix="MY_"  # All env vars prefixed with MY_
    )

    host: str = Field(default="localhost", description="Server host")
    port: int = Field(default=8080, description="Server port")
    api_key: SecretStr = Field(description="API key (required)")

@lru_cache(maxsize=1)
def get_my_config() -> MyConfig:
    """Cached singleton getter."""
    return MyConfig()
```

## Configuration Files

| Config | Env Prefix | Description |
|--------|-----------|-------------|
| `redis_config.py` | `REDIS_` | Redis connection settings |
| `saga_config.py` | `SAGA_` | Saga orchestration settings |
| `worker_config.py` | `WORKER_` | Background worker settings |
| `event_store_config.py` | `KURRENTDB_` | KurrentDB event store settings |
| `outbox_config.py` | `OUTBOX_` | Transactional outbox settings |
| `wse_config.py` | `WSE_` | WebSocket engine settings |
| `snapshot_config.py` | `SNAPSHOT_` | Event store snapshot settings |
| `projection_rebuilder_config.py` | `PROJECTION_` | Projection rebuilder settings |
| `dlq_config.py` | `DLQ_` | Dead letter queue settings |
| `jwt_config.py` | `JWT_` | JWT authentication settings |
| `eventbus_transport_config.py` | `EVENTBUS_` | EventBus transport settings |
| `pg_client_config.py` | `PG_CLIENT_` | PostgreSQL client settings |
| `reliability_config.py` | (no prefix) | Circuit breaker, retry, rate limiter |
| `cache_config.py` | `CACHE_` | Cache settings (hybrid approach) |

## Related Documentation

- [BASE_CONFIG.md](./BASE_CONFIG.md) - BaseConfig class reference
- [CONFIG_REFERENCE.md](./CONFIG_REFERENCE.md) - All env variables reference
- [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) - How to create new configs
