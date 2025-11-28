# =============================================================================
# File: app/infra/reliability/fallback.py
# Description: Graceful degradation fallback infrastructure for circuit breakers
#              Provides cache-based fallbacks for read operations when circuit OPEN
# =============================================================================

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import TypeVar, Generic, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.infra.persistence.cache_manager import CacheManager

logger = logging.getLogger("tradecore.reliability.fallback")

T = TypeVar('T')


class OperationType(Enum):
    """Operation types for fallback classification"""
    READ = auto()      # Idempotent reads - can use cached data
    WRITE = auto()     # Non-idempotent writes - must fail fast
    STREAMING = auto() # Streaming connections - reconnect logic


@dataclass
class FallbackResult(Generic[T]):
    """
    Result from fallback handler.

    Attributes:
        success: Whether fallback was able to provide data
        data: The fallback data (if success=True)
        is_stale: Whether the data is from cache and potentially stale
        stale_age_seconds: How old the cached data is
        error_message: Error message if fallback failed
        retry_after_seconds: Suggested retry time for client
        source: Where the fallback data came from
    """
    success: bool
    data: Optional[T] = None
    is_stale: bool = False
    stale_age_seconds: Optional[float] = None
    error_message: Optional[str] = None
    retry_after_seconds: Optional[int] = None
    source: str = "fallback"  # "cache", "default", "circuit_open"


@dataclass
class FallbackConfig:
    """Fallback configuration for circuit breakers"""
    enable_cache_fallback: bool = True
    max_stale_seconds: int = 300  # 5 minutes - max age of cached data to use
    default_retry_after: int = 30  # Default retry-after for failed fallbacks
    cache_reads: bool = True  # Whether to cache successful reads for fallback


class FallbackHandler(ABC, Generic[T]):
    """
    Base class for fallback handlers.

    Fallback handlers provide graceful degradation when the circuit breaker
    is OPEN and the broker API is unavailable.
    """

    @abstractmethod
    async def handle(
        self,
        operation_type: OperationType,
        cache_key: str,
        context: Dict[str, Any]
    ) -> FallbackResult[T]:
        """
        Handle fallback when circuit is open.

        Args:
            operation_type: Type of operation (READ, WRITE, STREAMING)
            cache_key: Key to lookup cached data
            context: Additional context (reset_timeout, last_failure_time, etc.)

        Returns:
            FallbackResult with success/failure and data or error info
        """
        pass


class CacheFallbackHandler(FallbackHandler[T]):
    """
    Fallback handler that returns cached data for read operations.

    Behavior by operation type:
    - READ: Try to return cached data if available and not too stale
    - WRITE: Fail fast with retry-after header
    - STREAMING: Fail fast (streaming should handle reconnection separately)
    """

    def __init__(
        self,
        cache_manager: Optional['CacheManager'] = None,
        config: Optional[FallbackConfig] = None
    ):
        self._cache_manager = cache_manager
        self._config = config or FallbackConfig()

        # Statistics
        self._stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "stale_returns": 0,
            "write_rejections": 0
        }

    async def handle(
        self,
        operation_type: OperationType,
        cache_key: str,
        context: Dict[str, Any]
    ) -> FallbackResult[T]:
        """
        Handle fallback based on operation type.

        For READ operations: Try to return cached data
        For WRITE operations: Fail fast with retry-after
        For STREAMING: Fail fast (handled separately)
        """
        # WRITE operations must fail fast
        if operation_type == OperationType.WRITE:
            self._stats["write_rejections"] += 1
            retry_after = self._calculate_retry_after(context)

            logger.info(
                f"Fallback rejected WRITE operation, cache_key={cache_key}, "
                f"retry_after={retry_after}s"
            )

            return FallbackResult(
                success=False,
                error_message="Service temporarily unavailable - write operations not allowed during circuit open",
                retry_after_seconds=retry_after,
                source="circuit_open"
            )

        # STREAMING operations should also fail fast
        if operation_type == OperationType.STREAMING:
            retry_after = self._calculate_retry_after(context)

            return FallbackResult(
                success=False,
                error_message="Service temporarily unavailable - streaming will reconnect automatically",
                retry_after_seconds=retry_after,
                source="circuit_open"
            )

        # READ operations: Try cache fallback
        if not self._config.enable_cache_fallback or not self._cache_manager:
            self._stats["cache_misses"] += 1

            return FallbackResult(
                success=False,
                error_message="Cache fallback not available",
                retry_after_seconds=self._calculate_retry_after(context),
                source="fallback_exhausted"
            )

        # Try to get cached data
        try:
            cached = await self._cache_manager.get_json(cache_key)

            if cached is None:
                self._stats["cache_misses"] += 1

                logger.debug(f"Cache miss for fallback, cache_key={cache_key}")

                return FallbackResult(
                    success=False,
                    error_message="No cached data available",
                    retry_after_seconds=self._calculate_retry_after(context),
                    source="cache_miss"
                )

            # Check if data is too stale
            stale_age = self._calculate_stale_age(cached)

            if stale_age > self._config.max_stale_seconds:
                self._stats["cache_misses"] += 1

                logger.debug(
                    f"Cached data too stale, cache_key={cache_key}, "
                    f"age={stale_age:.1f}s, max={self._config.max_stale_seconds}s"
                )

                return FallbackResult(
                    success=False,
                    error_message=f"Cached data too old ({int(stale_age)}s)",
                    retry_after_seconds=self._calculate_retry_after(context),
                    source="cache_stale"
                )

            # Return cached data with stale indicator
            self._stats["cache_hits"] += 1
            self._stats["stale_returns"] += 1

            logger.info(
                f"Returning stale cached data, cache_key={cache_key}, "
                f"age={stale_age:.1f}s"
            )

            # Extract the actual data from cache wrapper
            data = cached.get("data") if isinstance(cached, dict) else cached

            return FallbackResult(
                success=True,
                data=data,
                is_stale=True,
                stale_age_seconds=stale_age,
                source="cache"
            )

        except Exception as e:
            logger.error(f"Error accessing cache for fallback: {e}")
            self._stats["cache_misses"] += 1

            return FallbackResult(
                success=False,
                error_message=f"Cache access error: {str(e)}",
                retry_after_seconds=self._calculate_retry_after(context),
                source="cache_error"
            )

    def _calculate_retry_after(self, context: Dict[str, Any]) -> int:
        """
        Calculate retry-after based on circuit breaker state.

        Uses the circuit breaker's reset timeout and time since last failure
        to estimate when the circuit might close.
        """
        reset_timeout = context.get("reset_timeout_seconds", self._config.default_retry_after)
        last_failure_time = context.get("last_failure_time")

        if last_failure_time:
            if isinstance(last_failure_time, datetime):
                elapsed = (datetime.now(timezone.utc) - last_failure_time).total_seconds()
            else:
                elapsed = 0

            remaining = max(0, reset_timeout - elapsed)
            # Add small buffer to account for timing variations
            return int(remaining) + 5

        return reset_timeout

    def _calculate_stale_age(self, cached: Dict[str, Any]) -> float:
        """Calculate how old the cached data is in seconds."""
        cached_at = cached.get("cached_at")

        if cached_at is None:
            # No timestamp - assume max stale
            return self._config.max_stale_seconds + 1

        if isinstance(cached_at, str):
            try:
                cached_at = datetime.fromisoformat(cached_at.replace('Z', '+00:00'))
            except ValueError:
                return self._config.max_stale_seconds + 1

        if isinstance(cached_at, datetime):
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)

            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            return max(0, age)

        return self._config.max_stale_seconds + 1

    def get_stats(self) -> Dict[str, Any]:
        """Get fallback handler statistics."""
        total = self._stats["cache_hits"] + self._stats["cache_misses"]
        hit_rate = self._stats["cache_hits"] / total if total > 0 else 0.0

        return {
            **self._stats,
            "total_requests": total,
            "cache_hit_rate": hit_rate,
            "config": {
                "enable_cache_fallback": self._config.enable_cache_fallback,
                "max_stale_seconds": self._config.max_stale_seconds,
                "default_retry_after": self._config.default_retry_after
            }
        }


class NoOpFallbackHandler(FallbackHandler[T]):
    """
    No-op fallback handler that always fails.

    Use this when you want circuit breaker protection but no fallback.
    """

    async def handle(
        self,
        operation_type: OperationType,
        cache_key: str,
        context: Dict[str, Any]
    ) -> FallbackResult[T]:
        """Always returns failure - no fallback available."""
        return FallbackResult(
            success=False,
            error_message="No fallback available",
            retry_after_seconds=context.get("reset_timeout_seconds", 30),
            source="no_fallback"
        )


# =============================================================================
# CACHE WRAPPER UTILITIES
# =============================================================================

def wrap_for_cache(data: Any, ttl_seconds: int = 300) -> Dict[str, Any]:
    """
    Wrap data with metadata for cache fallback support.

    Use this when caching broker responses to enable fallback later.

    Args:
        data: The data to cache
        ttl_seconds: How long the data should be considered fresh

    Returns:
        Dict with data and cache metadata
    """
    return {
        "data": data,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "ttl_seconds": ttl_seconds
    }


def build_cache_key(
    broker_id: str,
    operation: str,
    **params
) -> str:
    """
    Build a cache key for broker operations.

    Args:
        broker_id: Broker identifier (alpaca, tradestation, etc.)
        operation: Operation name (get_quote, get_positions, etc.)
        **params: Additional parameters to include in key

    Returns:
        Cache key string
    """
    key_parts = [f"broker:{broker_id}", operation]

    # Sort params for consistent key generation
    for k, v in sorted(params.items()):
        if v is not None:
            key_parts.append(f"{k}:{v}")

    return ":".join(key_parts)
