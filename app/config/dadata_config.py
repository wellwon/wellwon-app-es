# =============================================================================
# File: app/config/dadata_config.py — DaData API Configuration
# UPDATED: Using BaseConfig pattern with Pydantic v2
# =============================================================================

from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from app.common.base.base_config import BaseConfig
from app.config.logging_config import get_logger

log = get_logger("wellwon.config.dadata")


class DaDataConfig(BaseConfig):
    """DaData API configuration"""

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix='DADATA_',
    )

    api_key: SecretStr = Field(default=SecretStr(""), description="DaData API key")
    secret_key: SecretStr = Field(default=SecretStr(""), description="DaData secret key")
    base_url: str = Field(
        default="https://suggestions.dadata.ru/suggestions/api/4_1/rs",
        description="DaData base URL"
    )
    timeout_seconds: int = Field(default=10, description="Request timeout")

    @property
    def find_by_id_url(self) -> str:
        """URL for findById/party endpoint"""
        return f"{self.base_url}/findById/party"

    @property
    def suggest_party_url(self) -> str:
        """URL for suggest/party endpoint"""
        return f"{self.base_url}/suggest/party"

    def get_api_key(self) -> str:
        """Get API key as plain string"""
        return self.api_key.get_secret_value()

    def get_secret_key(self) -> str:
        """Get secret key as plain string"""
        return self.secret_key.get_secret_value()

    def is_configured(self) -> bool:
        """Check if DaData is properly configured"""
        return bool(self.get_api_key() and self.get_secret_key())


@lru_cache(maxsize=1)
def get_dadata_config() -> DaDataConfig:
    """Get DaData configuration singleton (cached)."""
    config = DaDataConfig()
    if not config.is_configured():
        log.warning("DaData API keys not configured. Company lookup will not work.")
    else:
        log.info("DaData configuration loaded successfully")
    return config


def reset_dadata_config() -> None:
    """Reset config singleton (for testing)."""
    get_dadata_config.cache_clear()


def is_dadata_configured() -> bool:
    """Check if DaData is properly configured"""
    return get_dadata_config().is_configured()
