# =============================================================================
# File: app/infra/storage/minio_provider.py
# Description: MinIO/S3 storage provider
# =============================================================================

from __future__ import annotations

import uuid
from contextlib import AsyncExitStack
from typing import Any, Optional

import aioboto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config.logging_config import get_logger
from app.config.reliability_config import ReliabilityConfigs
from app.config.storage_config import StorageConfig, get_storage_config
from app.common.base.base_storage_provider import BaseStorageProvider, UploadResult
from app.infra.reliability.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from app.infra.reliability.retry import retry_async

log = get_logger("wellwon.infra.storage.minio")


class MinIOStorageProvider(BaseStorageProvider):
    """
    MinIO/S3 storage provider.

    Works with both MinIO (development) and AWS S3 (production).
    Uses aioboto3 for async S3 operations.

    Features:
        - S3v4 signature (required for MinIO)
        - Persistent client with connection reuse
        - Circuit breaker (reliability package)
        - Retry with exponential backoff (reliability package)
        - Configurable timeouts
    """

    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or get_storage_config()
        self.session = aioboto3.Session()

        # Boto config (no retry - handled by reliability package)
        self._boto_config = BotoConfig(
            signature_version="s3v4",
            connect_timeout=self.config.connect_timeout,
            read_timeout=self.config.read_timeout,
            max_pool_connections=self.config.max_pool_connections,
            retries={"max_attempts": 0},  # Disabled - using reliability package
        )

        # Reliability components
        self._circuit_breaker = CircuitBreaker(ReliabilityConfigs.storage_circuit_breaker())
        self._retry_config = ReliabilityConfigs.storage_retry()

        # Persistent client (lazy initialized)
        self._client: Optional[Any] = None
        self._exit_stack: Optional[AsyncExitStack] = None

    async def _get_client(self) -> Any:
        """Get or create persistent S3 client (connection reuse)"""
        if self._client is None:
            self._exit_stack = AsyncExitStack()
            self._client = await self._exit_stack.enter_async_context(
                self.session.client(
                    service_name="s3",
                    endpoint_url=self.config.endpoint_url,
                    aws_access_key_id=self.config.access_key,
                    aws_secret_access_key=self.config.secret_key,
                    region_name=self.config.region,
                    config=self._boto_config,
                )
            )
            log.info("MinIO S3 client initialized (persistent connection)")
        return self._client

    async def close(self) -> None:
        """Close the persistent client connection"""
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._client = None
            self._exit_stack = None
            log.info("MinIO S3 client closed")

    async def upload_file(
        self,
        bucket: str,
        file_content: bytes,
        content_type: str,
        original_filename: Optional[str] = None,
    ) -> UploadResult:
        """
        Upload a file to MinIO/S3.

        Args:
            bucket: Storage bucket (used as key prefix)
            file_content: File content as bytes
            content_type: MIME type
            original_filename: Original filename (optional)

        Returns:
            UploadResult with file path and public URL
        """
        # Generate unique filename
        extension = self._get_extension(content_type, original_filename)
        filename = f"{uuid.uuid4().hex[:12]}{extension}"
        key = f"{bucket}/{filename}"

        async def _do_upload():
            s3 = await self._get_client()
            await s3.put_object(
                Bucket=self.config.bucket_name,
                Key=key,
                Body=file_content,
                ContentType=content_type,
            )

        try:
            # Circuit breaker + retry
            await self._circuit_breaker.call(
                retry_async,
                _do_upload,
                retry_config=self._retry_config,
                context="storage.upload_file",
            )

            public_url = f"{self.config.public_url}/{key}"
            log.info(f"File uploaded: {key} -> {public_url}")

            return UploadResult(
                success=True,
                file_path=key,
                public_url=public_url,
            )

        except CircuitBreakerOpenError as e:
            log.error(f"Storage circuit breaker open: {e}")
            return UploadResult(success=False, error="Storage temporarily unavailable")
        except ClientError as e:
            error_msg = str(e)
            log.error(f"S3 client error uploading file: {error_msg}")
            return UploadResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = str(e)
            log.error(f"Failed to upload file: {error_msg}", exc_info=True)
            return UploadResult(success=False, error=error_msg)

    async def delete_file(self, bucket: str, filename: str) -> bool:
        """
        Delete a file from MinIO/S3.

        Args:
            bucket: Storage bucket (key prefix)
            filename: Filename to delete

        Returns:
            True if deleted, False otherwise
        """
        key = f"{bucket}/{filename}"

        async def _do_delete():
            s3 = await self._get_client()
            await s3.delete_object(
                Bucket=self.config.bucket_name,
                Key=key,
            )

        try:
            await self._circuit_breaker.call(
                retry_async,
                _do_delete,
                retry_config=self._retry_config,
                context="storage.delete_file",
            )
            log.info(f"File deleted: {key}")
            return True

        except CircuitBreakerOpenError as e:
            log.error(f"Storage circuit breaker open: {e}")
            return False
        except ClientError as e:
            log.error(f"S3 client error deleting file: {e}")
            return False
        except Exception as e:
            log.error(f"Failed to delete file: {e}", exc_info=True)
            return False

    async def delete_by_url(self, url: str) -> bool:
        """
        Delete a file by its public URL.

        Args:
            url: Public URL of the file

        Returns:
            True if deleted, False otherwise
        """
        # Extract key from URL
        if not url.startswith(self.config.public_url):
            log.warning(f"URL does not match public URL: {url}")
            return False

        key = url[len(self.config.public_url):].lstrip("/")

        async def _do_delete():
            s3 = await self._get_client()
            await s3.delete_object(
                Bucket=self.config.bucket_name,
                Key=key,
            )

        try:
            await self._circuit_breaker.call(
                retry_async,
                _do_delete,
                retry_config=self._retry_config,
                context="storage.delete_by_url",
            )
            log.info(f"File deleted by URL: {key}")
            return True

        except CircuitBreakerOpenError as e:
            log.error(f"Storage circuit breaker open: {e}")
            return False
        except ClientError as e:
            log.error(f"S3 client error deleting file by URL: {e}")
            return False
        except Exception as e:
            log.error(f"Failed to delete file by URL: {e}", exc_info=True)
            return False

    async def file_exists(self, bucket: str, filename: str) -> bool:
        """
        Check if a file exists in MinIO/S3.

        Args:
            bucket: Storage bucket (key prefix)
            filename: Filename to check

        Returns:
            True if exists, False otherwise
        """
        key = f"{bucket}/{filename}"

        async def _do_check():
            s3 = await self._get_client()
            await s3.head_object(
                Bucket=self.config.bucket_name,
                Key=key,
            )

        try:
            await self._circuit_breaker.call(
                retry_async,
                _do_check,
                retry_config=self._retry_config,
                context="storage.file_exists",
            )
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            log.error(f"S3 client error checking file: {e}")
            return False
        except CircuitBreakerOpenError as e:
            log.error(f"Storage circuit breaker open: {e}")
            return False
        except Exception as e:
            log.error(f"Failed to check file existence: {e}", exc_info=True)
            return False

    def get_public_url(self, bucket: str, filename: str) -> str:
        """Get public URL for a file"""
        return f"{self.config.public_url}/{bucket}/{filename}"

    async def ensure_bucket_exists(self) -> bool:
        """
        Ensure the storage bucket exists.

        Returns:
            True if bucket exists or was created, False on error
        """
        async def _do_ensure():
            s3 = await self._get_client()
            try:
                await s3.head_bucket(Bucket=self.config.bucket_name)
                log.info(f"Bucket exists: {self.config.bucket_name}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "404":
                    await s3.create_bucket(Bucket=self.config.bucket_name)
                    log.info(f"Bucket created: {self.config.bucket_name}")
                else:
                    raise

        try:
            await self._circuit_breaker.call(
                retry_async,
                _do_ensure,
                retry_config=self._retry_config,
                context="storage.ensure_bucket_exists",
            )
            return True

        except CircuitBreakerOpenError as e:
            log.error(f"Storage circuit breaker open: {e}")
            return False
        except Exception as e:
            log.error(f"Failed to ensure bucket exists: {e}", exc_info=True)
            return False


# =============================================================================
# Singleton
# =============================================================================

_storage_provider: Optional[MinIOStorageProvider] = None


def get_storage_provider() -> MinIOStorageProvider:
    """Get storage provider singleton"""
    global _storage_provider
    if _storage_provider is None:
        _storage_provider = MinIOStorageProvider()
    return _storage_provider
