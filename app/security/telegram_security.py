# =============================================================================
# File: app/security/telegram_security.py
# Description: Telegram-specific security utilities
# =============================================================================
# Security features for Telegram integration:
#   - Webhook signature verification (X-Telegram-Bot-Api-Secret-Token)
#   - IP filtering for webhook requests (Telegram IP ranges)
#   - Message deduplication (prevent duplicate processing)
#   - Idempotency key management (prevent duplicate operations)
# =============================================================================

from __future__ import annotations

import hashlib
import ipaddress
import time
from typing import Optional, Set, Tuple
from dataclasses import dataclass

from app.config.logging_config import get_logger

log = get_logger("wellwon.security.telegram")

# =============================================================================
# Telegram IP Ranges (Official)
# =============================================================================
# https://core.telegram.org/bots/webhooks
# Telegram sends webhook requests from these IP ranges only

TELEGRAM_IP_RANGES: Tuple[str, ...] = (
    "149.154.160.0/20",
    "91.108.4.0/22",
)

# Pre-computed networks for fast lookup
_TELEGRAM_NETWORKS: Optional[Tuple[ipaddress.IPv4Network, ...]] = None


def _get_telegram_networks() -> Tuple[ipaddress.IPv4Network, ...]:
    """Lazy-load and cache Telegram IP networks."""
    global _TELEGRAM_NETWORKS
    if _TELEGRAM_NETWORKS is None:
        _TELEGRAM_NETWORKS = tuple(
            ipaddress.IPv4Network(cidr) for cidr in TELEGRAM_IP_RANGES
        )
    return _TELEGRAM_NETWORKS


# =============================================================================
# Webhook Signature Verification
# =============================================================================

def verify_webhook_secret(
    request_secret: Optional[str],
    expected_secret: str
) -> bool:
    """
    Verify the X-Telegram-Bot-Api-Secret-Token header.

    Telegram includes this header in webhook requests when secret_token
    is specified during webhook setup.

    Args:
        request_secret: Value from X-Telegram-Bot-Api-Secret-Token header
        expected_secret: The secret_token configured during webhook setup

    Returns:
        True if secrets match, False otherwise
    """
    if not expected_secret:
        # No secret configured - allow all (not recommended for production)
        log.warning("Webhook secret not configured - skipping verification")
        return True

    if not request_secret:
        log.warning("Webhook request missing X-Telegram-Bot-Api-Secret-Token header")
        return False

    # Constant-time comparison to prevent timing attacks
    import hmac
    return hmac.compare_digest(request_secret, expected_secret)


# =============================================================================
# IP Filtering
# =============================================================================

def is_telegram_ip(ip_address: str) -> bool:
    """
    Check if an IP address belongs to Telegram's IP ranges.

    Use this to filter webhook requests - only accept requests
    from known Telegram IPs.

    Args:
        ip_address: IP address string (e.g., "149.154.167.50")

    Returns:
        True if IP is from Telegram, False otherwise
    """
    try:
        ip = ipaddress.IPv4Address(ip_address)
        networks = _get_telegram_networks()

        for network in networks:
            if ip in network:
                return True

        return False

    except ipaddress.AddressValueError:
        log.warning(f"Invalid IP address format: {ip_address}")
        return False
    except Exception as e:
        log.error(f"Error checking IP {ip_address}: {e}")
        return False


def get_client_ip(
    x_forwarded_for: Optional[str],
    x_real_ip: Optional[str],
    remote_addr: str
) -> str:
    """
    Extract client IP from request headers.

    Handles reverse proxy scenarios where the real client IP
    is in X-Forwarded-For or X-Real-IP headers.

    Args:
        x_forwarded_for: X-Forwarded-For header value
        x_real_ip: X-Real-IP header value
        remote_addr: Direct remote address

    Returns:
        Best guess at client IP
    """
    # X-Forwarded-For contains: client, proxy1, proxy2, ...
    if x_forwarded_for:
        # Take the first (leftmost) IP - the original client
        return x_forwarded_for.split(",")[0].strip()

    if x_real_ip:
        return x_real_ip.strip()

    return remote_addr


# =============================================================================
# Message Deduplication
# =============================================================================

@dataclass
class DeduplicationResult:
    """Result of deduplication check."""
    is_duplicate: bool
    first_seen_at: Optional[float] = None


class MessageDeduplicator:
    """
    In-memory message deduplication with TTL.

    For production, use Redis-based implementation (TelegramRedisDeduplicator).
    This class is for testing or single-instance deployments.

    Deduplication key: telegram_chat_id:telegram_message_id
    """

    def __init__(self, ttl_seconds: int = 300, max_size: int = 10000):
        """
        Initialize deduplicator.

        Args:
            ttl_seconds: Time-to-live for dedup entries (default: 5 minutes)
            max_size: Maximum cache size (oldest entries evicted)
        """
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._cache: dict[str, float] = {}  # key -> timestamp

    def _generate_key(self, chat_id: int, message_id: int) -> str:
        """Generate deduplication key."""
        return f"tg:dedup:{chat_id}:{message_id}"

    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        now = time.time()
        cutoff = now - self._ttl

        # Remove expired
        expired_keys = [k for k, ts in self._cache.items() if ts < cutoff]
        for key in expired_keys:
            del self._cache[key]

        # Evict oldest if over max size
        if len(self._cache) > self._max_size:
            # Sort by timestamp, remove oldest
            sorted_items = sorted(self._cache.items(), key=lambda x: x[1])
            to_remove = len(self._cache) - self._max_size
            for key, _ in sorted_items[:to_remove]:
                del self._cache[key]

    def check_and_mark(self, chat_id: int, message_id: int) -> DeduplicationResult:
        """
        Check if message is duplicate and mark as seen.

        Args:
            chat_id: Telegram chat ID
            message_id: Telegram message ID

        Returns:
            DeduplicationResult indicating if duplicate
        """
        self._cleanup_expired()

        key = self._generate_key(chat_id, message_id)
        now = time.time()

        if key in self._cache:
            return DeduplicationResult(
                is_duplicate=True,
                first_seen_at=self._cache[key]
            )

        # Mark as seen
        self._cache[key] = now
        return DeduplicationResult(is_duplicate=False, first_seen_at=now)

    def is_duplicate(self, chat_id: int, message_id: int) -> bool:
        """Quick check if message is duplicate (without marking)."""
        key = self._generate_key(chat_id, message_id)
        if key not in self._cache:
            return False

        # Check if expired
        if time.time() - self._cache[key] > self._ttl:
            del self._cache[key]
            return False

        return True


# =============================================================================
# Redis-based Deduplication (Production)
# =============================================================================

class TelegramRedisDeduplicator:
    """
    Redis-based message deduplication for production.

    Uses Redis SET with TTL for distributed deduplication.
    Works across multiple application instances.
    """

    def __init__(
        self,
        redis_client,
        ttl_seconds: int = 300,
        key_prefix: str = "tg:dedup"
    ):
        """
        Initialize Redis deduplicator.

        Args:
            redis_client: Async Redis client instance
            ttl_seconds: TTL for dedup keys (default: 5 minutes)
            key_prefix: Redis key prefix
        """
        self._redis = redis_client
        self._ttl = ttl_seconds
        self._prefix = key_prefix

    def _generate_key(self, chat_id: int, message_id: int) -> str:
        """Generate Redis key."""
        return f"{self._prefix}:{chat_id}:{message_id}"

    async def check_and_mark(self, chat_id: int, message_id: int) -> DeduplicationResult:
        """
        Check if message is duplicate and mark as seen (atomic).

        Uses Redis SETNX for atomic check-and-set.

        Args:
            chat_id: Telegram chat ID
            message_id: Telegram message ID

        Returns:
            DeduplicationResult indicating if duplicate
        """
        key = self._generate_key(chat_id, message_id)
        now = time.time()

        # SETNX returns True if key was set (not duplicate)
        # Returns False if key already exists (duplicate)
        was_set = await self._redis.set(
            key,
            str(now),
            nx=True,  # Only set if not exists
            ex=self._ttl  # Expire after TTL
        )

        if was_set:
            return DeduplicationResult(is_duplicate=False, first_seen_at=now)

        # Key exists - it's a duplicate
        first_seen = await self._redis.get(key)
        first_seen_ts = float(first_seen) if first_seen else None

        return DeduplicationResult(is_duplicate=True, first_seen_at=first_seen_ts)

    async def is_duplicate(self, chat_id: int, message_id: int) -> bool:
        """Quick check if message is duplicate."""
        key = self._generate_key(chat_id, message_id)
        return await self._redis.exists(key) > 0


# =============================================================================
# Idempotency Key Management
# =============================================================================

class IdempotencyKeyManager:
    """
    Manage idempotency keys for Telegram operations.

    Prevents duplicate operations (e.g., creating same group twice)
    by storing operation results with idempotency keys.
    """

    def __init__(
        self,
        redis_client,
        ttl_seconds: int = 3600,  # 1 hour default
        key_prefix: str = "tg:idempotency"
    ):
        """
        Initialize idempotency key manager.

        Args:
            redis_client: Async Redis client instance
            ttl_seconds: TTL for idempotency keys (default: 1 hour)
            key_prefix: Redis key prefix
        """
        self._redis = redis_client
        self._ttl = ttl_seconds
        self._prefix = key_prefix

    def _generate_key(self, operation: str, idempotency_key: str) -> str:
        """Generate Redis key."""
        return f"{self._prefix}:{operation}:{idempotency_key}"

    async def check_idempotency(
        self,
        operation: str,
        idempotency_key: str
    ) -> Optional[str]:
        """
        Check if operation was already performed.

        Args:
            operation: Operation type (e.g., "create_group", "send_message")
            idempotency_key: Unique key for this operation

        Returns:
            Cached result if operation was performed, None otherwise
        """
        key = self._generate_key(operation, idempotency_key)
        result = await self._redis.get(key)
        return result.decode() if result else None

    async def store_result(
        self,
        operation: str,
        idempotency_key: str,
        result: str
    ) -> None:
        """
        Store operation result for idempotency.

        Args:
            operation: Operation type
            idempotency_key: Unique key for this operation
            result: Result to cache (JSON string recommended)
        """
        key = self._generate_key(operation, idempotency_key)
        await self._redis.set(key, result, ex=self._ttl)

    async def check_and_store(
        self,
        operation: str,
        idempotency_key: str,
        result: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Atomic check-and-store for idempotency.

        Args:
            operation: Operation type
            idempotency_key: Unique key for this operation
            result: Result to store if not duplicate

        Returns:
            Tuple of (is_new, cached_result)
            - (True, None) if this is a new operation
            - (False, cached_result) if operation was already performed
        """
        key = self._generate_key(operation, idempotency_key)

        # Try to set with NX (only if not exists)
        was_set = await self._redis.set(key, result, nx=True, ex=self._ttl)

        if was_set:
            return (True, None)

        # Key exists - return cached result
        cached = await self._redis.get(key)
        return (False, cached.decode() if cached else None)


# =============================================================================
# Utility Functions
# =============================================================================

def generate_idempotency_key(*args) -> str:
    """
    Generate an idempotency key from arguments.

    Uses SHA256 hash of concatenated arguments.

    Args:
        *args: Values to include in key (will be converted to strings)

    Returns:
        Hex digest of SHA256 hash
    """
    combined = ":".join(str(arg) for arg in args)
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def generate_message_hash(
    chat_id: int,
    content: str,
    sender_id: Optional[int] = None
) -> str:
    """
    Generate a hash for message content.

    Useful for detecting duplicate content (different message IDs but same content).

    Args:
        chat_id: Telegram chat ID
        content: Message content
        sender_id: Optional sender ID

    Returns:
        Hex digest of SHA256 hash
    """
    parts = [str(chat_id), content]
    if sender_id:
        parts.append(str(sender_id))

    combined = ":".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:32]
