# =============================================================================
# File: app/infra/telegram/file_cache.py
# Description: Cache Telegram file_ids to avoid re-uploading
# =============================================================================
# When you upload a file to Telegram, you get a file_id.
# Reusing file_id for same content = no re-upload = faster + saves bandwidth.
# =============================================================================

from __future__ import annotations

import hashlib
from typing import Optional, Any
from dataclasses import dataclass

from app.config.logging_config import get_logger

log = get_logger("wellwon.telegram.file_cache")


@dataclass
class CachedFile:
    """Cached Telegram file info."""
    file_id: str
    file_unique_id: str
    file_type: str  # photo, document, voice, video
    content_hash: str


class TelegramFileCache:
    """
    Redis-backed cache for Telegram file_ids.

    Key: content hash (SHA256 of file content or URL)
    Value: file_id from Telegram

    Usage:
        cache = TelegramFileCache(redis)

        # Check cache before upload
        file_id = await cache.get(content_hash)
        if file_id:
            # Use cached file_id
            await bot.send_document(chat_id, file_id)
        else:
            # Upload and cache
            result = await bot.send_document(chat_id, file_bytes)
            await cache.set(content_hash, result.document.file_id, "document")
    """

    PREFIX = "tg:file_cache"
    TTL = 60 * 60 * 24 * 30  # 30 days (Telegram keeps file_ids valid for a while)

    def __init__(self, redis_client: Any):
        self._redis = redis_client

    def _key(self, content_hash: str) -> str:
        return f"{self.PREFIX}:{content_hash}"

    @staticmethod
    def hash_content(content: bytes) -> str:
        """Hash file content."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def hash_url(url: str) -> str:
        """Hash URL for caching."""
        return hashlib.sha256(url.encode()).hexdigest()

    async def get(self, content_hash: str) -> Optional[str]:
        """Get cached file_id by content hash."""
        try:
            file_id = await self._redis.get(self._key(content_hash))
            if file_id:
                log.debug(f"File cache hit: {content_hash[:16]}...")
                return file_id.decode() if isinstance(file_id, bytes) else file_id
            return None
        except Exception as e:
            log.warning(f"File cache get error: {e}")
            return None

    async def set(
        self,
        content_hash: str,
        file_id: str,
        file_type: str = "document"
    ) -> None:
        """Cache file_id."""
        try:
            await self._redis.set(
                self._key(content_hash),
                file_id,
                ex=self.TTL
            )
            log.debug(f"File cached: {content_hash[:16]}... -> {file_id[:20]}...")
        except Exception as e:
            log.warning(f"File cache set error: {e}")

    async def delete(self, content_hash: str) -> None:
        """Remove from cache."""
        try:
            await self._redis.delete(self._key(content_hash))
        except Exception:
            pass


# Singleton
_cache: Optional[TelegramFileCache] = None


def get_file_cache(redis_client: Any) -> TelegramFileCache:
    """Get file cache singleton."""
    global _cache
    if _cache is None:
        _cache = TelegramFileCache(redis_client)
    return _cache
