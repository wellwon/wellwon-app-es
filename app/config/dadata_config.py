# =============================================================================
# File: app/config/dadata_config.py — DaData API Configuration
# =============================================================================

import os
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("wellwon.config.dadata")


@dataclass
class DaDataConfig:
    """DaData API configuration"""
    api_key: str
    secret_key: str
    base_url: str = "https://suggestions.dadata.ru/suggestions/api/4_1/rs"
    timeout_seconds: int = 10

    def __post_init__(self):
        """Validate configuration"""
        if not self.api_key:
            raise ValueError("DADATA_API_KEY is required")
        if not self.secret_key:
            raise ValueError("DADATA_SECRET_KEY is required")

    @property
    def find_by_id_url(self) -> str:
        """URL for findById/party endpoint"""
        return f"{self.base_url}/findById/party"

    @property
    def suggest_party_url(self) -> str:
        """URL for suggest/party endpoint"""
        return f"{self.base_url}/suggest/party"


# Global config instance
_config: Optional[DaDataConfig] = None


def get_dadata_config() -> DaDataConfig:
    """Get DaData configuration (cached)"""
    global _config

    if _config is None:
        api_key = os.getenv("DADATA_API_KEY", "")
        secret_key = os.getenv("DADATA_SECRET_KEY", "")

        if not api_key or not secret_key:
            log.warning("DaData API keys not configured. Company lookup will not work.")
            # Return config with empty keys - will fail on actual use
            _config = DaDataConfig(
                api_key=api_key or "not-configured",
                secret_key=secret_key or "not-configured"
            )
        else:
            _config = DaDataConfig(api_key=api_key, secret_key=secret_key)
            log.info("DaData configuration loaded successfully")

    return _config


def is_dadata_configured() -> bool:
    """Check if DaData is properly configured"""
    api_key = os.getenv("DADATA_API_KEY", "")
    secret_key = os.getenv("DADATA_SECRET_KEY", "")
    return bool(api_key and secret_key)
