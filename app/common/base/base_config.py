# app/common/base/base_config.py
# =============================================================================
# BaseConfig - Foundation for all TradeCore configuration classes
#
# Industry best practices (Pydantic v2):
# - SettingsConfigDict (not deprecated class Config)
# - Automatic .env file loading
# - Case-insensitive environment variables
# - Nested config support via __ delimiter
# - SecretStr for sensitive values
# - @lru_cache singleton pattern for factory functions
#
# Usage:
#     from app.common.base.base_config import BaseConfig
#     from pydantic_settings import SettingsConfigDict
#     from pydantic import SecretStr
#     from functools import lru_cache
#
#     class MyConfig(BaseConfig):
#         model_config = SettingsConfigDict(
#             **BaseConfig.model_config,
#             env_prefix="MY_"
#         )
#         api_key: SecretStr
#         timeout_ms: int = 5000
#
#     @lru_cache(maxsize=1)
#     def get_my_config() -> MyConfig:
#         return MyConfig()
# =============================================================================

from typing import Any, Dict

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseConfig(BaseSettings):
    """Base configuration class for all TradeCore configs.

    All configuration classes should inherit from this base to ensure:
    1. Consistent .env file loading
    2. Case-insensitive environment variable matching
    3. Proper handling of nested configs via __ delimiter
    4. Standardized serialization for admin panel integration

    Environment Variable Naming:
    - Use domain-specific prefixes (REDIS_, SAGA_, JWT_, etc.)
    - No global TRADECORE_ prefix (project name may change in production)
    - Nested values use __ delimiter (e.g., REDIS__POOL__MAX_SIZE)

    Secrets Handling:
    - All sensitive fields (passwords, keys, tokens) should use SecretStr
    - SecretStr masks values in logs: SecretStr('**********')
    - Access raw value via .get_secret_value() when needed

    Singleton Pattern:
    - Each config should have a factory function with @lru_cache(maxsize=1)
    - This ensures config is parsed once at startup, not on every import

    Admin Panel Integration:
    - model_json_schema() returns JSON Schema for UI generation
    - model_fields provides field metadata (type, default, description)
    - model_dump() returns current values with secrets masked
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
    )

    def to_dict(self, mask_secrets: bool = True) -> Dict[str, Any]:
        """Convert config to dictionary.

        Args:
            mask_secrets: If True (default), SecretStr values are masked.
                         If False, raw values are exposed (use with caution).

        Returns:
            Dictionary representation of the config.
        """
        if mask_secrets:
            return self.model_dump()
        else:
            # Expose secret values - use only for internal operations
            data = {}
            for field_name, field_info in self.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, SecretStr):
                    data[field_name] = value.get_secret_value()
                else:
                    data[field_name] = value
            return data

    def __repr__(self) -> str:
        """Safe repr that masks secrets."""
        class_name = self.__class__.__name__
        fields = []
        for field_name in self.model_fields:
            value = getattr(self, field_name)
            if isinstance(value, SecretStr):
                fields.append(f"{field_name}=SecretStr('**********')")
            else:
                fields.append(f"{field_name}={value!r}")
        return f"{class_name}({', '.join(fields)})"
