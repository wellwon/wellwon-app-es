# =============================================================================
# File: app/config/storage_config.py
# Description: MinIO/S3 storage configuration
# =============================================================================

from pydantic_settings import BaseSettings


class StorageConfig(BaseSettings):
    """
    Storage configuration for MinIO/S3.

    Environment variables (prefix: STORAGE_):
        STORAGE_ENDPOINT_URL - MinIO/S3 endpoint
        STORAGE_ACCESS_KEY - Access key
        STORAGE_SECRET_KEY - Secret key
        STORAGE_REGION - AWS region
        STORAGE_BUCKET_NAME - Bucket name
        STORAGE_USE_SSL - Use SSL/TLS
        STORAGE_PUBLIC_URL - Public URL for file access
        STORAGE_CONNECT_TIMEOUT - Connection timeout (seconds)
        STORAGE_READ_TIMEOUT - Read timeout (seconds)
        STORAGE_MAX_POOL_CONNECTIONS - Max connection pool size
        STORAGE_MAX_RETRIES - Max retry attempts
    """

    endpoint_url: str = "http://localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    region: str = "us-east-1"
    bucket_name: str = "wellwon"
    use_ssl: bool = False
    public_url: str = "http://localhost:9000/wellwon"

    # Performance settings (retry handled by reliability package)
    connect_timeout: int = 5
    read_timeout: int = 30
    max_pool_connections: int = 25

    class Config:
        env_prefix = "STORAGE_"


# Singleton instance
_storage_config: StorageConfig | None = None


def get_storage_config() -> StorageConfig:
    """Get storage configuration singleton"""
    global _storage_config
    if _storage_config is None:
        _storage_config = StorageConfig()
    return _storage_config
