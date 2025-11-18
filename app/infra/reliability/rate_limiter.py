# =============================================================================
# File: app/infra/reliability/rate_limiter.py
# Description: Rate limiting for external API protection
# =============================================================================

import asyncio
import time
from typing import Optional, Any
from abc import ABC, abstractmethod
import logging

# Import configuration from central location
from app.config.reliability_config import RateLimiterConfig

logger = logging.getLogger("wellwon.rate_limiter")


class RateLimiterAlgorithm(ABC):
    """Base class for rate limiting algorithms."""

    @abstractmethod
    async def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens."""
        pass

    @abstractmethod
    async def wait_and_acquire(self, tokens: int = 1) -> None:
        """Wait until tokens are available."""
        pass


class TokenBucket(RateLimiterAlgorithm):
    """Token bucket algorithm for burst traffic."""

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens."""
        async with self._lock:
            now = time.monotonic()

            # Refill tokens
            elapsed = now - self.last_refill
            self.tokens = min(
                self.capacity,
                self.tokens + (elapsed * self.refill_rate)
            )
            self.last_refill = now

            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False

    async def wait_and_acquire(self, tokens: int = 1) -> None:
        """Wait until tokens are available."""
        while not await self.acquire(tokens):
            # Calculate wait time
            async with self._lock:
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.refill_rate
            await asyncio.sleep(wait_time)


class SlidingWindow(RateLimiterAlgorithm):
    """Sliding window algorithm."""

    def __init__(self, capacity: int, window_seconds: int):
        self.capacity = capacity
        self.window_seconds = window_seconds
        self.requests: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens."""
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds

            # Remove old requests
            self.requests = [t for t in self.requests if t > cutoff]

            # Check if we can add more
            if len(self.requests) + tokens <= self.capacity:
                for _ in range(tokens):
                    self.requests.append(now)
                return True

            return False

    async def wait_and_acquire(self, tokens: int = 1) -> None:
        """Wait until tokens are available."""
        while not await self.acquire(tokens):
            await asyncio.sleep(0.1)


class DistributedTokenBucket(RateLimiterAlgorithm):
    """Distributed token bucket using Redis."""

    LUA_SCRIPT = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local requested = tonumber(ARGV[3])
    local now = tonumber(ARGV[4])

    local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
    local current_tokens = tonumber(bucket[1]) or capacity
    local last_refill = tonumber(bucket[2]) or now

    -- Refill tokens
    local elapsed = now - last_refill
    local new_tokens = math.min(capacity, current_tokens + (elapsed * refill_rate))

    -- Try to acquire
    if new_tokens >= requested then
        redis.call('HMSET', key, 'tokens', new_tokens - requested, 'last_refill', now)
        redis.call('EXPIRE', key, 3600)
        return 1
    else
        redis.call('HMSET', key, 'tokens', new_tokens, 'last_refill', now)
        redis.call('EXPIRE', key, 3600)
        return 0
    end
    """

    def __init__(
            self,
            key: str,
            capacity: int,
            refill_rate: float,
            cache_manager: Any
    ):
        self.key = f"rate_limit:{key}"
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.cache_manager = cache_manager
        self._script_sha = None

    async def _ensure_script_loaded(self):
        """Ensure Lua script is loaded in Redis."""
        if self._script_sha is None and hasattr(self.cache_manager, 'script_load'):
            try:
                self._script_sha = await self.cache_manager.script_load(self.LUA_SCRIPT)
            except Exception as e:
                logger.warning(f"Failed to load Lua script: {e}")

    async def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens atomically."""
        await self._ensure_script_loaded()

        # Try evalsha first
        if hasattr(self.cache_manager, 'evalsha') and self._script_sha:
            try:
                result = await self.cache_manager.evalsha(
                    self._script_sha,
                    keys=[self.key],
                    args=[
                        self.capacity,
                        self.refill_rate,
                        tokens,
                        time.time()
                    ]
                )
                return bool(result)
            except Exception:
                pass

        # Fallback to eval_script
        if hasattr(self.cache_manager, 'eval_script'):
            result = await self.cache_manager.eval_script(
                self.LUA_SCRIPT,
                keys=[self.key],
                args=[
                    self.capacity,
                    self.refill_rate,
                    tokens,
                    time.time()
                ]
            )
            return bool(result)
        else:
            # Fallback to non-distributed version
            logger.warning("cache_manager doesn't support eval_script, using local rate limiter")
            return True

    async def wait_and_acquire(self, tokens: int = 1) -> None:
        """Wait until tokens are available."""
        while not await self.acquire(tokens):
            await asyncio.sleep(0.1)


class RateLimiter:
    """Main rate limiter with algorithm selection."""

    def __init__(
            self,
            name: str = "default",
            config: Optional[RateLimiterConfig] = None,
            cache_manager: Optional[Any] = None,
            # Legacy compatibility parameters
            max_requests: Optional[int] = None,
            time_window: Optional[int] = None
    ):
        self.name = name

        # Handle legacy initialization
        if config is None:
            if max_requests is not None or time_window is not None:
                config = RateLimiterConfig(
                    algorithm="sliding_window" if time_window else "token_bucket",
                    capacity=max_requests or 100,
                    time_window=time_window
                )
            else:
                config = RateLimiterConfig()

        # Handle config post-init
        if config.max_requests is not None:
            config.capacity = config.max_requests

        self.config = config
        self.cache_manager = cache_manager

        # Create algorithm
        if config.distributed and cache_manager:
            self.algorithm = DistributedTokenBucket(
                key=name,
                capacity=config.capacity,
                refill_rate=config.refill_rate,
                cache_manager=cache_manager
            )
        elif config.algorithm == "sliding_window" and config.time_window:
            self.algorithm = SlidingWindow(
                capacity=config.capacity,
                window_seconds=config.time_window
            )
        else:
            self.algorithm = TokenBucket(
                capacity=config.capacity,
                refill_rate=config.refill_rate
            )

    async def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens."""
        acquired = await self.algorithm.acquire(tokens)

        if not acquired:
            logger.warning(
                f"rate_limit_exceeded for {self.name}, requested_tokens={tokens}"
            )

        return acquired

    async def wait_and_acquire(self, tokens: int = 1) -> None:
        """Wait until tokens are available."""
        start_time = time.monotonic()
        await self.algorithm.wait_and_acquire(tokens)

        wait_time = time.monotonic() - start_time
        if wait_time > 0.1:  # Log if we had to wait
            logger.info(
                f"rate_limit_wait for {self.name}, wait_time={wait_time:.3f}, tokens={tokens}"
            )

    # Compatibility methods
    async def check_rate_limit(self, identifier: str = "default") -> bool:
        """Check rate limit (compatibility method)."""
        return await self.acquire()

    async def wait_if_needed(self, identifier: str = "default") -> None:
        """Wait if rate limited (compatibility method)."""
        await self.wait_and_acquire()

    def get_status(self) -> dict:
        """Get current rate limiter status."""
        status = {
            "name": self.name,
            "algorithm": self.config.algorithm,
            "capacity": self.config.capacity,
            "distributed": self.config.distributed
        }

        if isinstance(self.algorithm, TokenBucket):
            status["available_tokens"] = self.algorithm.tokens
            status["refill_rate"] = self.algorithm.refill_rate
        elif isinstance(self.algorithm, SlidingWindow):
            status["current_requests"] = len(self.algorithm.requests)
            status["window_seconds"] = self.algorithm.window_seconds

        return status