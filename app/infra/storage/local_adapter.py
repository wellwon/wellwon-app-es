# =============================================================================
# File: app/infra/storage/local_adapter.py
# Description: Local file storage adapter (for development)
# Production should use MinIO/S3
# =============================================================================

from __future__ import annotations

import os
import uuid
import logging
import aiofiles
import aiofiles.os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

log = logging.getLogger("wellwon.infra.storage")


@dataclass
class UploadResult:
    """Result of file upload operation"""
    success: bool
    file_path: Optional[str] = None
    public_url: Optional[str] = None
    error: Optional[str] = None


class LocalStorageAdapter:
    """
    Local file storage adapter for development.

    Stores files in a local directory and serves them via static files endpoint.
    In production, replace with MinIO/S3 adapter.
    """

    def __init__(
        self,
        base_path: str = "storage",
        base_url: str = "/static/storage",
    ):
        self.base_path = Path(base_path)
        self.base_url = base_url.rstrip("/")
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure storage directories exist"""
        directories = [
            self.base_path,
            self.base_path / "company-logos",
            self.base_path / "documents",
            self.base_path / "avatars",
            self.base_path / "chat-files",
            self.base_path / "chat-voice",
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    async def upload_file(
        self,
        bucket: str,
        file_content: bytes,
        content_type: str,
        original_filename: Optional[str] = None,
    ) -> UploadResult:
        """
        Upload a file to local storage.

        Args:
            bucket: Storage bucket (subdirectory)
            file_content: File content as bytes
            content_type: MIME type
            original_filename: Original filename (optional)

        Returns:
            UploadResult with file path and public URL
        """
        try:
            # Determine extension from content type or filename
            extension = self._get_extension(content_type, original_filename)

            # Generate unique filename
            unique_id = uuid.uuid4().hex[:12]
            filename = f"{unique_id}{extension}"

            # Ensure bucket directory exists
            bucket_path = self.base_path / bucket
            bucket_path.mkdir(parents=True, exist_ok=True)

            # Write file
            file_path = bucket_path / filename
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file_content)

            # Build public URL
            public_url = f"{self.base_url}/{bucket}/{filename}"

            log.info(f"File uploaded: {file_path} -> {public_url}")

            return UploadResult(
                success=True,
                file_path=str(file_path),
                public_url=public_url,
            )

        except Exception as e:
            log.error(f"Failed to upload file: {e}", exc_info=True)
            return UploadResult(success=False, error=str(e))

    async def delete_file(self, bucket: str, filename: str) -> bool:
        """
        Delete a file from storage.

        Args:
            bucket: Storage bucket
            filename: Filename to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            file_path = self.base_path / bucket / filename

            if await aiofiles.os.path.exists(file_path):
                await aiofiles.os.remove(file_path)
                log.info(f"File deleted: {file_path}")
                return True

            log.warning(f"File not found for deletion: {file_path}")
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
        try:
            # Extract path from URL
            if not url.startswith(self.base_url):
                log.warning(f"URL does not match base URL: {url}")
                return False

            relative_path = url[len(self.base_url):].lstrip("/")
            file_path = self.base_path / relative_path

            if await aiofiles.os.path.exists(file_path):
                await aiofiles.os.remove(file_path)
                log.info(f"File deleted by URL: {file_path}")
                return True

            log.warning(f"File not found for deletion: {file_path}")
            return False

        except Exception as e:
            log.error(f"Failed to delete file by URL: {e}", exc_info=True)
            return False

    async def file_exists(self, bucket: str, filename: str) -> bool:
        """Check if a file exists"""
        file_path = self.base_path / bucket / filename
        return await aiofiles.os.path.exists(file_path)

    def get_public_url(self, bucket: str, filename: str) -> str:
        """Get public URL for a file"""
        return f"{self.base_url}/{bucket}/{filename}"

    def _get_extension(
        self,
        content_type: str,
        original_filename: Optional[str] = None,
    ) -> str:
        """Get file extension from content type or filename"""
        # Try to get from original filename
        if original_filename:
            ext = Path(original_filename).suffix
            if ext:
                return ext

        # Map content type to extension
        content_type_map = {
            "image/webp": ".webp",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/svg+xml": ".svg",
            "application/pdf": ".pdf",
            "application/json": ".json",
            "text/plain": ".txt",
            "text/csv": ".csv",
            # Audio formats (for voice messages)
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
            "audio/mp3": ".mp3",
            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            # Video formats
            "video/mp4": ".mp4",
            "video/webm": ".webm",
            # Document formats
            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/vnd.ms-excel": ".xls",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
            "application/zip": ".zip",
            "application/x-rar-compressed": ".rar",
        }

        return content_type_map.get(content_type, "")


# =============================================================================
# Singleton instance
# =============================================================================

_storage_adapter: Optional[LocalStorageAdapter] = None


def get_storage_adapter() -> LocalStorageAdapter:
    """Get storage adapter singleton"""
    global _storage_adapter

    if _storage_adapter is None:
        # Get configuration from environment
        base_path = os.getenv("STORAGE_PATH", "storage")
        base_url = os.getenv("STORAGE_URL", "/static/storage")

        _storage_adapter = LocalStorageAdapter(
            base_path=base_path,
            base_url=base_url,
        )

    return _storage_adapter
