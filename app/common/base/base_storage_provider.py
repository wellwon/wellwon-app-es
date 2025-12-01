# =============================================================================
# File: app/common/base/base_storage_provider.py
# Description: Abstract base class for storage providers
# =============================================================================

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class UploadResult:
    """Result of file upload operation"""

    success: bool
    file_path: Optional[str] = None
    public_url: Optional[str] = None
    error: Optional[str] = None


class BaseStorageProvider(ABC):
    """
    Abstract base class for storage providers.

    Implementations:
        - MinIOStorageProvider (MinIO/S3)
    """

    @abstractmethod
    async def upload_file(
        self,
        bucket: str,
        file_content: bytes,
        content_type: str,
        original_filename: Optional[str] = None,
    ) -> UploadResult:
        """
        Upload a file to storage.

        Args:
            bucket: Storage bucket (subdirectory/prefix)
            file_content: File content as bytes
            content_type: MIME type
            original_filename: Original filename (optional)

        Returns:
            UploadResult with file path and public URL
        """
        pass

    @abstractmethod
    async def delete_file(self, bucket: str, filename: str) -> bool:
        """
        Delete a file from storage.

        Args:
            bucket: Storage bucket
            filename: Filename to delete

        Returns:
            True if deleted, False otherwise
        """
        pass

    @abstractmethod
    async def delete_by_url(self, url: str) -> bool:
        """
        Delete a file by its public URL.

        Args:
            url: Public URL of the file

        Returns:
            True if deleted, False otherwise
        """
        pass

    @abstractmethod
    async def file_exists(self, bucket: str, filename: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            bucket: Storage bucket
            filename: Filename to check

        Returns:
            True if exists, False otherwise
        """
        pass

    @abstractmethod
    def get_public_url(self, bucket: str, filename: str) -> str:
        """
        Get public URL for a file.

        Args:
            bucket: Storage bucket
            filename: Filename

        Returns:
            Public URL string
        """
        pass

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
