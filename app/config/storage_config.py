# =============================================================================
# File: app/config/storage_config.py
# Description: MinIO/S3 storage configuration
# UPDATED: Using BaseConfig pattern with Pydantic v2
# =============================================================================

from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from app.common.base.base_config import BaseConfig, BASE_CONFIG_DICT


class StorageConfig(BaseConfig):
    """
    Storage configuration for MinIO/S3.
    """

    model_config = SettingsConfigDict(
        **BASE_CONFIG_DICT,
        env_prefix='STORAGE_',
    )

    endpoint_url: str = Field(default="http://localhost:9000", description="MinIO/S3 endpoint")
    access_key: SecretStr = Field(default=SecretStr("minioadmin"), description="Access key")
    secret_key: SecretStr = Field(default=SecretStr("minioadmin"), description="Secret key")
    region: str = Field(default="us-east-1", description="AWS region")
    bucket_name: str = Field(default="wellwon", description="Bucket name")
    use_ssl: bool = Field(default=False, description="Use SSL/TLS")
    public_url: str = Field(default="http://localhost:9000/wellwon", description="Public URL")

    # Performance settings
    connect_timeout: int = Field(default=5, description="Connection timeout (seconds)")
    read_timeout: int = Field(default=30, description="Read timeout (seconds)")
    max_pool_connections: int = Field(default=25, description="Max connection pool size")

    def get_access_key(self) -> str:
        """Get access key as plain string"""
        return self.access_key.get_secret_value()

    def get_secret_key(self) -> str:
        """Get secret key as plain string"""
        return self.secret_key.get_secret_value()


@lru_cache(maxsize=1)
def get_storage_config() -> StorageConfig:
    """Get storage configuration singleton (cached)."""
    return StorageConfig()


def reset_storage_config() -> None:
    """Reset config singleton (for testing)."""
    get_storage_config.cache_clear()
