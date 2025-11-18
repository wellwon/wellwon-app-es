# Configuration Architecture Guide (Universal Pattern)

**Version**: 1.0
**Date**: 2025-11-13
**Industry Standard**: Python Enterprise Applications (2025)

---

## Overview

This is a **universal configuration architecture** pattern for Python enterprise applications. It defines how to structure, load, validate, and manage configurations for scalable systems with admin UI support.

**Use this pattern for:**
- Microservices
- Trading platforms
- Enterprise web applications
- Real-time systems
- Multi-tenant SaaS

**Key Benefits:**
- Type-safe configuration access
- Environment variable support (12-factor app)
- Hot-reload without restarts
- Admin UI ready
- Pydantic validation
- Multi-environment support (dev/staging/prod)

---

## Architecture Principles

### 1. **Three-Tier Configuration Model**

```
┌─────────────────────────────────────────────────────────────────┐
│  Type 1: Application Config (Pydantic BaseSettings)            │
│  - Loaded from .env file                                       │
│  - Admin UI editable                                           │
│  - Hot-reload support                                          │
│  Example: wse_config.py, event_store_config.py                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Type 2: Runtime Config (Pydantic BaseModel)                   │
│  - Loaded from PostgreSQL/Redis                                │
│  - Dynamic, changes frequently                                 │
│  - User/entity-specific settings                               │
│  Example: connection_recovery_config.py                        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Type 3: Template Classes (dataclass)                          │
│  - NOT configurations, but templates                           │
│  - Programmatic object creation                                │
│  - Function parameters                                         │
│  Example: reliability_config.py (CircuitBreakerConfig)         │
└─────────────────────────────────────────────────────────────────┘
```

### 2. **Single Source of Truth**
- **Environment variables** → `.env` file → Pydantic BaseSettings
- **Runtime overrides** → Redis/PostgreSQL → Hot-reload
- **No hardcoded values** in code

### 3. **Validation First**
- All configs use Pydantic for validation
- Type hints on all fields
- Boundaries (ge/le) on numeric values
- Custom validators for complex rules

### 4. **Admin UI Ready**
- `to_dict()` for GET endpoints
- `update_from_dict()` for PUT endpoints
- `reload()` for hot-reload after changes
- Config versioning for change tracking

---

## Type 1: Application Config (BaseSettings)

### When to Use:
✅ **System-wide settings** (timeouts, limits, intervals)
✅ **Loaded from environment variables**
✅ **Admin UI editable** with hot-reload
✅ **Same across all instances** (not user-specific)

### Template:

```python
# app/config/xyz_config.py
from typing import Optional, List, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class XYZConfig(BaseSettings):
    """
    XYZ System Configuration

    Features:
    - Environment variable support (XYZ_ prefix)
    - Pydantic validation
    - Hot-reload support
    - Admin UI ready
    """

    # =========================================================================
    # Section 1: Core Settings
    # =========================================================================

    enabled: bool = Field(
        default=True,
        description="Enable XYZ system"
    )

    timeout_seconds: int = Field(
        default=30,
        ge=5,      # Greater than or equal to 5
        le=300,    # Less than or equal to 300
        description="Operation timeout in seconds"
    )

    max_connections: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum concurrent connections"
    )

    batch_size: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Processing batch size"
    )

    # =========================================================================
    # Section 2: Advanced Settings
    # =========================================================================

    enable_caching: bool = Field(
        default=True,
        description="Enable result caching"
    )

    cache_ttl_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Cache TTL in seconds"
    )

    allowed_hosts: List[str] = Field(
        default=["localhost", "127.0.0.1"],
        description="Allowed hosts for connections"
    )

    # =========================================================================
    # Custom Validators
    # =========================================================================

    @field_validator('timeout_seconds')
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Ensure timeout is reasonable"""
        if v < 5:
            raise ValueError("Timeout must be at least 5 seconds")
        if v > 300:
            raise ValueError("Timeout must not exceed 5 minutes")
        return v

    # =========================================================================
    # Pydantic Configuration
    # =========================================================================

    model_config = SettingsConfigDict(
        env_file=".env",                # Load from .env file
        env_prefix="XYZ_",              # Environment variable prefix
        case_sensitive=False,           # Case-insensitive env vars
        extra="ignore",                 # Ignore extra env vars
        validate_assignment=True,       # Validate on property updates
    )

    # =========================================================================
    # Helper Methods (Admin UI Support)
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary (for admin UI GET)"""
        return self.model_dump()

    def update_from_dict(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration from dictionary (for admin UI PUT)

        Args:
            updates: Dictionary of field updates

        Raises:
            ValidationError: If updates violate validation rules
        """
        for key, value in updates.items():
            if hasattr(self, key):
                setattr(self, key, value)  # Pydantic validates automatically!

    @classmethod
    def from_env(cls) -> 'XYZConfig':
        """
        Create configuration from environment variables.

        Environment variables:
        - XYZ_ENABLED=true
        - XYZ_TIMEOUT_SECONDS=60
        - XYZ_MAX_CONNECTIONS=200

        Returns:
            XYZConfig instance with environment overrides
        """
        return cls()


# =============================================================================
# Singleton Instance (with hot-reload support)
# =============================================================================

_xyz_config: Optional[XYZConfig] = None
_config_version: int = 0


def get_xyz_config(reload: bool = False) -> XYZConfig:
    """
    Get XYZ configuration singleton.

    Args:
        reload: Force reload from environment/Redis (default: False)

    Returns:
        XYZConfig: Configuration instance

    Usage:
        config = get_xyz_config()
        timeout = config.timeout_seconds  # Type-safe!

        # Hot-reload after admin changes:
        config = get_xyz_config(reload=True)
    """
    global _xyz_config, _config_version

    if _xyz_config is None or reload:
        _xyz_config = XYZConfig.from_env()
        _config_version += 1

    return _xyz_config


def reload_xyz_config() -> XYZConfig:
    """
    Force reload configuration (hot-reload).

    Call this after:
    - Admin UI updates
    - Redis config changes
    - Environment variable changes (in dev)

    Returns:
        XYZConfig: Reloaded configuration instance
    """
    return get_xyz_config(reload=True)


def get_config_version() -> int:
    """
    Get current config version (increments on reload).

    Use this to detect config changes in long-running tasks.

    Returns:
        int: Current config version number
    """
    return _config_version


# =============================================================================
# Backward Compatibility Helpers (Optional)
# =============================================================================

def get_xyz_setting(key: str, default: Any = None) -> Any:
    """
    Get XYZ setting by key (backward compatibility).

    Args:
        key: Setting key (e.g., "timeout_seconds")
        default: Default value if not found

    Returns:
        Setting value or default
    """
    config = get_xyz_config()
    return getattr(config, key, default)
```

### Environment Variables (.env):

```bash
# .env file
XYZ_ENABLED=true
XYZ_TIMEOUT_SECONDS=60
XYZ_MAX_CONNECTIONS=200
XYZ_BATCH_SIZE=20
XYZ_ENABLE_CACHING=true
XYZ_CACHE_TTL_SECONDS=600
XYZ_ALLOWED_HOSTS=["localhost","api.example.com"]
```

### Usage in Code:

```python
from app.config.xyz_config import get_xyz_config

# Type-safe access
config = get_xyz_config()
timeout = config.timeout_seconds  # IDE autocomplete works!
max_conn = config.max_connections

# After admin UI update
config = reload_xyz_config()
```

### Admin API Endpoints:

```python
from fastapi import APIRouter, HTTPException
from app.config.xyz_config import get_xyz_config, reload_xyz_config

router = APIRouter(prefix="/api/admin")


@router.get("/config/xyz")
async def get_xyz_config_api():
    """Get XYZ configuration (admin UI)"""
    config = get_xyz_config()
    return {
        "data": config.to_dict(),
        "version": get_config_version()
    }


@router.put("/config/xyz")
async def update_xyz_config_api(updates: Dict[str, Any]):
    """
    Update XYZ configuration (admin UI).

    Request body:
    {
        "timeout_seconds": 60,
        "max_connections": 200
    }
    """
    try:
        config = get_xyz_config()

        # Pydantic validates automatically!
        config.update_from_dict(updates)

        # Persist to Redis (optional)
        await redis_client.set(
            "config:xyz",
            config.model_dump_json(),
            ex=86400  # 24h TTL
        )

        # Publish config_changed event for hot-reload across instances
        await event_bus.publish("config:changed", {
            "config": "xyz",
            "version": get_config_version()
        })

        # Reload on current instance
        reload_xyz_config()

        return {
            "status": "updated",
            "version": get_config_version()
        }

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### Hot-Reload Across Instances:

```python
# Event handler for config_changed events
@event_handler("config:changed")
async def on_config_changed(event: ConfigChangedEvent):
    """Handle config change events from other instances"""
    if event.config == "xyz":
        # Reload config on this instance
        reload_xyz_config()
        log.info(f"Reloaded XYZ config to version {get_config_version()}")
```

---

## Type 2: Runtime Config (BaseModel)

### When to Use:
✅ **Stored in PostgreSQL/Redis** (not .env)
✅ **Changes dynamically** via API
✅ **User-specific** or **entity-specific** settings
✅ **Complex nested structures**

### Template:

```python
# app/config/xyz_runtime_config.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any


class EntityConfigModel(BaseModel):
    """Per-entity configuration (e.g., per-user, per-broker)"""
    model_config = ConfigDict(from_attributes=True)

    entity_id: str
    enabled: bool = Field(default=True)

    # Settings specific to this entity
    max_requests_per_minute: int = Field(default=60, ge=1, le=10000)
    timeout_seconds: int = Field(default=30, ge=5, le=300)

    def to_dict_for_storage(self) -> Dict[str, Any]:
        """Convert to dict for database storage"""
        return {
            "entity_id": self.entity_id,
            "enabled": self.enabled,
            "max_requests_per_minute": self.max_requests_per_minute,
            "timeout_seconds": self.timeout_seconds,
        }


class XYZRuntimeConfigModel(BaseModel):
    """Runtime configuration (stored in database)"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default="xyz_runtime_config")
    version: str = Field(default="1.0.0")

    # Global runtime settings
    enabled: bool = Field(default=True)
    default_timeout: int = Field(default=30, ge=5, le=300)

    # Per-entity configurations
    entity_configs: Dict[str, EntityConfigModel] = Field(default_factory=dict)

    def get_entity_config(self, entity_id: str) -> Optional[EntityConfigModel]:
        """Get configuration for specific entity"""
        return self.entity_configs.get(entity_id)

    def set_entity_config(self, entity_id: str, config: EntityConfigModel) -> None:
        """Set configuration for specific entity"""
        self.entity_configs[entity_id] = config

    def to_dict_for_storage(self) -> Dict[str, Any]:
        """Convert to dict for database storage"""
        return {
            "id": self.id,
            "version": self.version,
            "enabled": self.enabled,
            "default_timeout": self.default_timeout,
            "entity_configs": {
                entity_id: config.to_dict_for_storage()
                for entity_id, config in self.entity_configs.items()
            }
        }


# =============================================================================
# Database Operations
# =============================================================================

async def load_runtime_config_from_db(pg_client) -> XYZRuntimeConfigModel:
    """Load runtime config from PostgreSQL"""
    row = await pg_client.fetchrow(
        "SELECT config_data FROM xyz_runtime_config WHERE id = $1",
        "xyz_runtime_config"
    )
    if row:
        return XYZRuntimeConfigModel(**row["config_data"])
    else:
        # Return default if not found
        return XYZRuntimeConfigModel()


async def save_runtime_config_to_db(
    pg_client,
    config: XYZRuntimeConfigModel
) -> None:
    """Save runtime config to PostgreSQL"""
    await pg_client.execute(
        """
        INSERT INTO xyz_runtime_config (id, config_data, updated_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (id) DO UPDATE
        SET config_data = $2, updated_at = NOW()
        """,
        config.id,
        config.to_dict_for_storage()
    )


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/api/xyz/config/{entity_id}")
async def get_entity_config(entity_id: str, pg_client):
    """Get configuration for specific entity"""
    runtime_config = await load_runtime_config_from_db(pg_client)
    entity_config = runtime_config.get_entity_config(entity_id)

    if not entity_config:
        raise HTTPException(404, "Entity config not found")

    return entity_config.to_dict_for_storage()


@router.put("/api/xyz/config/{entity_id}")
async def update_entity_config(
    entity_id: str,
    updates: Dict[str, Any],
    pg_client
):
    """Update configuration for specific entity"""
    runtime_config = await load_runtime_config_from_db(pg_client)

    # Create or update entity config
    entity_config = EntityConfigModel(entity_id=entity_id, **updates)
    runtime_config.set_entity_config(entity_id, entity_config)

    # Save to database
    await save_runtime_config_to_db(pg_client, runtime_config)

    return {"status": "updated"}
```

---

## Type 3: Template Classes (dataclass)

### When to Use:
✅ **NOT configurations**, but **template classes**
✅ **Programmatic object creation**
✅ **Function parameters** that are structured
✅ **No environment variables** or database storage

### Template:

```python
# app/config/xyz_templates.py
from dataclasses import dataclass
from typing import Optional, Callable


@dataclass
class CircuitBreakerConfig:
    """
    Circuit breaker configuration template.

    NOT a configuration file - used programmatically to create circuit breakers.
    """
    name: str
    failure_threshold: int = 5
    success_threshold: int = 3
    reset_timeout_seconds: int = 30
    half_open_max_calls: int = 3
    window_size: Optional[int] = None


@dataclass
class RetryConfig:
    """
    Retry policy configuration template.

    NOT a configuration file - used programmatically to create retry policies.
    """
    max_attempts: int = 3
    initial_delay_ms: int = 100
    max_delay_ms: int = 10000
    backoff_factor: float = 2.0
    jitter: bool = True
    retry_condition: Optional[Callable[[Exception], bool]] = None


class XYZTemplates:
    """Pre-configured templates for common scenarios"""

    @staticmethod
    def circuit_breaker_for_database(name: str) -> CircuitBreakerConfig:
        """Create circuit breaker config for database operations"""
        return CircuitBreakerConfig(
            name=f"db_{name}",
            failure_threshold=5,
            reset_timeout_seconds=30,
            half_open_max_calls=3,
            success_threshold=3
        )

    @staticmethod
    def retry_for_network() -> RetryConfig:
        """Create retry config for network operations"""
        return RetryConfig(
            max_attempts=3,
            initial_delay_ms=100,
            max_delay_ms=5000,
            backoff_factor=2.0,
            jitter=True
        )


# =============================================================================
# Usage (Programmatic)
# =============================================================================

# Create circuit breaker using template
cb_config = XYZTemplates.circuit_breaker_for_database("postgres")
circuit_breaker = CircuitBreaker(cb_config)

# Create retry policy using template
retry_config = XYZTemplates.retry_for_network()
result = await retry_with_backoff(operation, retry_config)
```

---

## Decision Matrix

| Scenario | Type | Reason |
|----------|------|--------|
| WebSocket heartbeat interval | Type 1 (BaseSettings) | System setting, .env file |
| Database connection pool size | Type 1 (BaseSettings) | System setting, admin UI editable |
| Per-user rate limit | Type 2 (BaseModel) | User-specific, stored in DB |
| Per-broker recovery settings | Type 2 (BaseModel) | Entity-specific, dynamic |
| Circuit breaker for Kafka | Type 3 (dataclass) | Template for object creation |
| Retry policy for HTTP calls | Type 3 (dataclass) | Template for object creation |

---

## Best Practices

### ✅ DO:
1. Use Pydantic Field() with description for all fields
2. Add validation boundaries (ge/le) for numeric values
3. Use meaningful environment variable prefixes
4. Provide from_env() classmethod for BaseSettings
5. Provide to_dict() and update_from_dict() for admin UI
6. Use singleton pattern with hot-reload support
7. Document which config file a value comes from
8. Version your configs for change tracking
9. Add field validators for complex business rules
10. Provide backward compatibility helpers when refactoring

### ❌ DON'T:
1. Don't use plain Dict for application settings
2. Don't mix BaseSettings and BaseModel in one file
3. Don't hardcode values that should be configurable
4. Don't skip validation (always validate!)
5. Don't use dataclass for app settings (use BaseSettings)
6. Don't store secrets in configs (use vault)
7. Don't forget to document environment variables
8. Don't skip type hints

---

## Complete Example Project Structure

```
project/
├── app/
│   ├── config/
│   │   ├── __init__.py
│   │   │
│   │   # Type 1: Application Configs (BaseSettings)
│   │   ├── database_config.py       # PostgreSQL settings
│   │   ├── redis_config.py          # Redis settings
│   │   ├── api_config.py            # API server settings
│   │   ├── wse_config.py            # WebSocket settings
│   │   ├── event_store_config.py    # Event store settings
│   │   │
│   │   # Type 2: Runtime Configs (BaseModel)
│   │   ├── user_preferences_config.py
│   │   ├── broker_recovery_config.py
│   │   │
│   │   # Type 3: Template Classes (dataclass)
│   │   └── reliability_config.py     # Circuit breaker, retry templates
│   │
│   ├── api/
│   │   └── admin/
│   │       └── config_router.py      # Admin API for config management
│   │
│   └── ...
│
├── .env                              # Environment variables
├── .env.example                      # Example env file
└── docs/
    └── CONFIG.md                     # This guide
```

---

## Testing

```python
# tests/config/test_xyz_config.py
import pytest
from pydantic import ValidationError
from app.config.xyz_config import XYZConfig, get_xyz_config


def test_config_defaults():
    """Test default values"""
    config = XYZConfig()
    assert config.timeout_seconds == 30
    assert config.max_connections == 100
    assert config.enabled is True


def test_config_validation():
    """Test validation boundaries"""
    # Valid
    config = XYZConfig(timeout_seconds=60)
    assert config.timeout_seconds == 60

    # Invalid (too low)
    with pytest.raises(ValidationError):
        XYZConfig(timeout_seconds=2)

    # Invalid (too high)
    with pytest.raises(ValidationError):
        XYZConfig(timeout_seconds=500)


def test_config_from_env(monkeypatch):
    """Test loading from environment variables"""
    monkeypatch.setenv("XYZ_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("XYZ_MAX_CONNECTIONS", "200")

    config = XYZConfig.from_env()
    assert config.timeout_seconds == 60
    assert config.max_connections == 200


def test_config_hot_reload():
    """Test hot-reload functionality"""
    config1 = get_xyz_config()
    version1 = get_config_version()

    # Reload
    config2 = reload_xyz_config()
    version2 = get_config_version()

    assert version2 > version1


def test_config_to_dict():
    """Test admin UI export"""
    config = XYZConfig(timeout_seconds=60)
    data = config.to_dict()

    assert data["timeout_seconds"] == 60
    assert "max_connections" in data


def test_config_update_from_dict():
    """Test admin UI update"""
    config = XYZConfig()

    config.update_from_dict({"timeout_seconds": 60})
    assert config.timeout_seconds == 60

    # Invalid update should raise ValidationError
    with pytest.raises(ValidationError):
        config.update_from_dict({"timeout_seconds": 2})
```

---

## Migration Path

### Step 1: Audit Existing Configs
```bash
# Find all config files
find app/config -name "*.py" | sort
```

### Step 2: Classify Each Config
- [ ] Type 1 (BaseSettings) - Application settings
- [ ] Type 2 (BaseModel) - Runtime configs
- [ ] Type 3 (dataclass) - Templates

### Step 3: Refactor One at a Time
1. Create new config following template
2. Add backward compatibility helpers
3. Update imports gradually
4. Test thoroughly
5. Remove old config

### Step 4: Document
- Update environment variable docs
- Add admin API endpoints
- Update developer guide

---

## References

- **Pydantic Settings**: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **12-Factor App**: https://12factor.net/config
- **Environment Variables Best Practices**: https://docs.docker.com/compose/environment-variables/

---

**Last Updated**: 2025-11-13
**Author**: TradeCore Architecture Team
**License**: MIT (for reference purposes)
**Status**: ✅ Production-Ready Universal Pattern
