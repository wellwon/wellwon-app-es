# =============================================================================
# File: app/config/kontur_config.py — Kontur Declarant API Configuration
# UPDATED: Using BaseConfig pattern with Pydantic v2
# =============================================================================

from functools import lru_cache
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import SettingsConfigDict

from app.common.base.base_config import BaseConfig, BASE_CONFIG_DICT
from app.config.logging_config import get_logger

log = get_logger("wellwon.config.kontur")


class KonturConfig(BaseConfig):
    """Kontur Declarant API configuration"""

    model_config = SettingsConfigDict(
        **BASE_CONFIG_DICT,
        env_prefix='KONTUR_',
    )

    # Authentication
    api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Kontur API key (X-Kontur-ApiKey header)"
    )

    # Environment
    environment: str = Field(
        default="production",
        description="Environment: production or test"
    )

    base_url_production: str = Field(
        default="https://api-d.kontur.ru",
        description="Production base URL"
    )

    base_url_test: str = Field(
        default="https://api-d.testkontur.ru",
        description="Test base URL"
    )

    # Timeouts
    timeout_seconds: int = Field(default=30, description="Default request timeout")
    long_timeout_seconds: int = Field(default=120, description="Long operations timeout")
    upload_timeout_seconds: int = Field(default=300, description="File upload timeout")

    # Rate Limiting (Kontur-specific)
    max_requests_per_second: float = Field(default=10.0, description="Global rate limit")
    max_requests_per_minute: int = Field(default=500, description="Per-minute limit")

    # Retry Configuration
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_initial_delay_ms: int = Field(default=1000, description="Initial retry delay")
    retry_max_delay_ms: int = Field(default=30000, description="Maximum retry delay")

    # Circuit Breaker
    circuit_breaker_failure_threshold: int = Field(default=5, description="Failures before opening")
    circuit_breaker_reset_timeout: int = Field(default=60, description="Reset timeout in seconds")

    # Caching
    enable_cache: bool = Field(default=True, description="Enable response caching")
    cache_ttl_options: int = Field(default=3600, description="Cache TTL for options (1 hour)")
    cache_ttl_docflows: int = Field(default=300, description="Cache TTL for docflows (5 min)")
    cache_ttl_templates: int = Field(default=86400, description="Cache TTL for templates (24h)")

    # Feature Flags
    enable_circuit_breaker: bool = Field(default=True)
    enable_retry: bool = Field(default=True)
    enable_rate_limiting: bool = Field(default=True)
    enable_bulkhead: bool = Field(default=True)
    enable_fallback: bool = Field(default=True)

    @model_validator(mode='after')
    def validate_https_urls(self) -> 'KonturConfig':
        """Enforce HTTPS for all URLs (security requirement)"""
        for url_field in ['base_url_production', 'base_url_test']:
            url = getattr(self, url_field)
            if url and not url.startswith('https://'):
                raise ValueError(
                    f"{url_field} must use HTTPS protocol for security. "
                    f"Got: {url}"
                )
        return self

    @property
    def base_url(self) -> str:
        """Get base URL based on environment"""
        return self.base_url_test if self.environment == "test" else self.base_url_production

    @property
    def api_url(self) -> str:
        """Get full API URL with version"""
        return f"{self.base_url}/common/v1"

    def get_api_key(self) -> str:
        """Get API key as plain string"""
        return self.api_key.get_secret_value()

    def is_configured(self) -> bool:
        """Check if Kontur is properly configured"""
        return bool(self.get_api_key())


@lru_cache(maxsize=1)
def get_kontur_config() -> KonturConfig:
    """Get Kontur configuration singleton (cached)."""
    config = KonturConfig()
    if not config.is_configured():
        log.warning("Kontur API key not configured. Kontur features will not work.")
    # Config loading logged by adapter initialization, no need to log here
    return config


def reset_kontur_config() -> None:
    """Reset config singleton (for testing)."""
    get_kontur_config.cache_clear()


def is_kontur_configured() -> bool:
    """Check if Kontur is properly configured"""
    return get_kontur_config().is_configured()
