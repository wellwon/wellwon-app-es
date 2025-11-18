# =============================================================================
# File: app/infra/reliability/distributed_lock.py
# Description: Unified distributed locking mechanism for all services
#              Provides consistent locking interface across TradeCore
#              with full configuration support
# =============================================================================

import asyncio
import uuid
import time
import os
import random
from typing import Optional, Dict, Any, Union, TypeVar, Generic, List
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

from app.infra.persistence.redis_client import get_global_client
from app.config.reliability_config import DistributedLockConfig, ReliabilityConfigs

import logging

# Use standard logger
logger = logging.getLogger("tradecore.distributed_lock")

T = TypeVar('T')


class LockStrategy(Enum):
    """Lock acquisition strategies"""
    FAIL_FAST = "fail_fast"
    WAIT_FOREVER = "wait_forever"
    WAIT_WITH_TIMEOUT = "wait_with_timeout"
    EXPONENTIAL_BACKOFF = "exponential_backoff"


@dataclass
class LockInfo:
    """Information about an acquired lock"""
    lock_key: str
    lock_value: str
    resource_id: str
    owner_id: str
    acquired_at: datetime
    ttl_seconds: int
    namespace: str

    def is_expired(self) -> bool:
        """Check if lock has expired based on TTL"""
        elapsed = (datetime.now(timezone.utc) - self.acquired_at).total_seconds()
        return elapsed > self.ttl_seconds

    def time_remaining(self) -> float:
        """Get remaining time in seconds"""
        elapsed = (datetime.now(timezone.utc) - self.acquired_at).total_seconds()
        return max(0, self.ttl_seconds - elapsed)


class LockMetrics:
    """Track lock performance metrics"""

    def __init__(self):
        self.acquisitions = 0
        self.failures = 0
        self.releases = 0
        self.timeouts = 0
        self.extensions = 0
        self.wait_times: List[float] = []

    def record_acquisition(self, wait_time_ms: float, success: bool):
        if success:
            self.acquisitions += 1
            self.wait_times.append(wait_time_ms)
            if len(self.wait_times) > 100:
                self.wait_times.pop(0)
        else:
            self.failures += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        if not self.wait_times:
            avg_wait = 0
            p95_wait = 0
        else:
            avg_wait = sum(self.wait_times) / len(self.wait_times)
            sorted_times = sorted(self.wait_times)
            p95_wait = sorted_times[int(len(sorted_times) * 0.95)]

        return {
            "acquisitions": self.acquisitions,
            "failures": self.failures,
            "releases": self.releases,
            "timeouts": self.timeouts,
            "extensions": self.extensions,
            "success_rate": self.acquisitions / (self.acquisitions + self.failures) if (
                                                                                                   self.acquisitions + self.failures) > 0 else 0,
            "avg_wait_ms": avg_wait,
            "p95_wait_ms": p95_wait
        }


class DistributedLockError(Exception):
    """Base exception for distributed lock operations"""
    pass


class LockAcquisitionError(DistributedLockError):
    """Failed to acquire lock"""
    pass


class DistributedLock(Generic[T]):
    """
    Unified distributed lock implementation using Redis.

    Features:
    - Configuration-driven behavior
    - Multiple acquisition strategies
    - Automatic cleanup of stale locks
    - Lock extension support
    - Performance metrics
    - Lua scripts for atomic operations
    - Generic resource ID support (UUID, string, etc.)
    - Full backward compatibility
    """

    # Lua scripts
    ACQUIRE_SCRIPT = """
    local key = KEYS[1]
    local value = ARGV[1]
    local ttl = tonumber(ARGV[2])

    if redis.call("exists", key) == 0 then
        redis.call("set", key, value, "EX", ttl)
        return 1
    else
        return 0
    end
    """

    RELEASE_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    EXTEND_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("expire", KEYS[1], ARGV[2])
    else
        return 0
    end
    """

    def __init__(self, config: Optional[DistributedLockConfig] = None):
        self.config = config or DistributedLockConfig()
        self._metrics = LockMetrics() if self.config.enable_metrics else None
        self._held_locks: Dict[str, LockInfo] = {}

        # Parse strategy
        self.strategy = LockStrategy(self.config.strategy)

        # Generate unique owner ID
        task = asyncio.current_task()
        task_name = task.get_name() if task else "no-task"
        self.owner_id = f"{uuid.uuid4().hex[:8]}-{task_name}:{os.getpid()}"

        # Start cleanup task if enabled
        if self.config.enable_auto_cleanup:
            asyncio.create_task(self._auto_cleanup_task())

    def _get_lock_key(self, resource_id: Union[str, uuid.UUID, T]) -> str:
        """Generate Redis key for the lock"""
        return f"{self.config.namespace}:{str(resource_id)}"

    def _generate_lock_value(self) -> str:
        """Generate unique lock value"""
        return f"{self.owner_id}:{uuid.uuid4().hex}:{int(time.time() * 1000)}"

    async def _check_and_cleanup_stale_lock(self, lock_key: str, current_value: str) -> bool:
        """Check if a lock is stale and clean it up if necessary"""
        if not current_value or not self.config.enable_auto_cleanup:
            return False

        try:
            parts = current_value.split(":")
            if len(parts) >= 3:
                timestamp = int(parts[-1])
                lock_age_ms = (time.time() * 1000) - timestamp

                # Use configured multiplier
                stale_threshold = self.config.ttl_seconds * 1000 * self.config.stale_lock_multiplier

                if lock_age_ms > stale_threshold:
                    logger.warning(
                        f"Found stale lock {lock_key} (age: {lock_age_ms / 1000:.1f}s), cleaning up"
                    )
                    redis = await get_global_client()
                    await redis.delete(lock_key)
                    return True
        except Exception as e:
            logger.debug(f"Error checking lock staleness: {e}")

        return False

    async def acquire(
            self,
            resource_id: Union[str, uuid.UUID, T],
            ttl_seconds: Optional[int] = None,
            timeout_ms: Optional[int] = None,
            retry_times: Optional[int] = None,
            use_backoff: Optional[bool] = None
    ) -> Optional[Union[LockInfo, str]]:
        """
        Acquire a distributed lock.

        Args:
            resource_id: Resource to lock (string, UUID, or any stringifiable type)
            ttl_seconds: Lock TTL (uses config default if not specified)
            timeout_ms: Max wait time (uses config default if not specified)
            retry_times: Override retry attempts
            use_backoff: Override backoff setting (for adapter pool compatibility)

        Returns:
            LockInfo if acquired (or lock token string for backward compatibility)
        """
        ttl_seconds = ttl_seconds or self.config.ttl_seconds
        timeout_ms = timeout_ms or self.config.max_wait_ms
        retry_times = retry_times or self.config.retry_times

        # Handle backoff override
        if use_backoff is not None:
            strategy = LockStrategy.EXPONENTIAL_BACKOFF if use_backoff else self.strategy
        else:
            strategy = self.strategy

        lock_key = self._get_lock_key(resource_id)
        lock_value = self._generate_lock_value()

        start_time = time.time() * 1000
        attempt = 0

        while attempt < retry_times:
            attempt += 1

            try:
                redis = await get_global_client()

                # Try to acquire lock
                if self.config.use_lua_scripts:
                    acquired = await redis.eval(
                        self.ACQUIRE_SCRIPT,
                        1,
                        lock_key,
                        lock_value,
                        ttl_seconds
                    )
                else:
                    acquired = await redis.set(
                        lock_key,
                        lock_value,
                        nx=True,
                        ex=ttl_seconds
                    )

                if acquired:
                    lock_info = LockInfo(
                        lock_key=lock_key,
                        lock_value=lock_value,
                        resource_id=str(resource_id),
                        owner_id=self.owner_id,
                        acquired_at=datetime.now(timezone.utc),
                        ttl_seconds=ttl_seconds,
                        namespace=self.config.namespace
                    )

                    self._held_locks[lock_key] = lock_info

                    wait_time = time.time() * 1000 - start_time
                    if self._metrics:
                        self._metrics.record_acquisition(wait_time, True)

                    logger.debug(
                        f"Acquired lock for {resource_id} "
                        f"(attempt: {attempt}, wait: {wait_time:.1f}ms)"
                    )

                    # Return lock_value for backward compatibility with adapter pool
                    if self.config.namespace.startswith("adapter_pool"):
                        return lock_value
                    else:
                        return lock_info

                # Check for stale lock
                current_value = await redis.get(lock_key)
                if await self._check_and_cleanup_stale_lock(lock_key, current_value):
                    continue

                # Check strategy
                if strategy == LockStrategy.FAIL_FAST:
                    break

                # Check timeout
                elapsed = time.time() * 1000 - start_time
                if strategy == LockStrategy.WAIT_WITH_TIMEOUT and elapsed > timeout_ms:
                    if self._metrics:
                        self._metrics.timeouts += 1
                    break

                # Calculate delay
                if strategy == LockStrategy.EXPONENTIAL_BACKOFF:
                    base_delay = self.config.retry_delay_ms / 1000
                    delay = min(base_delay * (2 ** (attempt - 1)), 1.0)
                    # Add jitter
                    delay *= (0.5 + random.random() * 0.5)
                else:
                    delay = self.config.retry_delay_ms / 1000

                # Don't sleep on last attempt
                if attempt < retry_times:
                    await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"Error acquiring lock for {resource_id}: {e}")
                if attempt >= retry_times:
                    break
                await asyncio.sleep(self.config.retry_delay_ms / 1000)

        # Failed to acquire
        wait_time = time.time() * 1000 - start_time
        if self._metrics:
            self._metrics.record_acquisition(wait_time, False)

        logger.debug(f"Failed to acquire lock for {resource_id} after {wait_time:.1f}ms")
        return None

    async def release(self, lock_info: Union[LockInfo, str], key: Optional[str] = None) -> bool:
        """
        Release a distributed lock.

        Args:
            lock_info: LockInfo object or lock token string (for compatibility)
            key: Resource key (only needed if lock_info is a string token)

        Returns:
            True if released successfully
        """
        try:
            redis = await get_global_client()

            # Handle both LockInfo and string token
            if isinstance(lock_info, str):
                # Backward compatibility mode
                if not key:
                    # Try to find the lock in held_locks by token value
                    lock_key = None
                    for held_key, held_info in self._held_locks.items():
                        if held_info.lock_value == lock_info:
                            lock_key = held_key
                            break

                    if not lock_key:
                        # If not found in held_locks, we can't proceed
                        return False

                    lock_value = lock_info
                else:
                    lock_key = f"{self.config.namespace}:{key}"
                    lock_value = lock_info
            else:
                lock_key = lock_info.lock_key
                lock_value = lock_info.lock_value

            if self.config.use_lua_scripts:
                result = await redis.eval(
                    self.RELEASE_SCRIPT,
                    1,
                    lock_key,
                    lock_value
                )
                released = bool(result)
            else:
                current_value = await redis.get(lock_key)
                if current_value == lock_value:
                    await redis.delete(lock_key)
                    released = True
                else:
                    released = False

            if released:
                self._held_locks.pop(lock_key, None)
                if self._metrics:
                    self._metrics.releases += 1
                logger.debug(f"Released lock for {lock_key}")

            return released

        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
            return False

    async def extend(self, lock_info: Union[LockInfo, str], additional_seconds: int, key: Optional[str] = None) -> bool:
        """
        Extend lock TTL.

        Args:
            lock_info: LockInfo object or lock token string
            additional_seconds: Additional time in seconds
            key: Resource key (only needed if lock_info is a string token)

        Returns:
            True if extended successfully
        """
        try:
            redis = await get_global_client()

            # Handle both LockInfo and string token
            if isinstance(lock_info, str):
                if not key:
                    logger.error("Key required when extending with token string")
                    return False

                lock_key = f"{self.config.namespace}:{key}"
                lock_value = lock_info
                new_ttl = self.config.ttl_seconds + additional_seconds
            else:
                lock_key = lock_info.lock_key
                lock_value = lock_info.lock_value
                new_ttl = lock_info.ttl_seconds + additional_seconds

            if self.config.use_lua_scripts:
                result = await redis.eval(
                    self.EXTEND_SCRIPT,
                    1,
                    lock_key,
                    lock_value,
                    new_ttl
                )
                extended = bool(result)
            else:
                current_value = await redis.get(lock_key)
                if current_value == lock_value:
                    extended = await redis.expire(lock_key, new_ttl)
                else:
                    extended = False

            if extended:
                if isinstance(lock_info, LockInfo):
                    lock_info.ttl_seconds = new_ttl
                if self._metrics:
                    self._metrics.extensions += 1
                logger.debug(f"Extended lock for {lock_key} by {additional_seconds}s")

            return extended

        except Exception as e:
            logger.error(f"Error extending lock: {e}")
            return False

    @asynccontextmanager
    async def lock_context(
            self,
            resource_id: Union[str, uuid.UUID, T],
            ttl_seconds: Optional[int] = None,
            timeout_ms: Optional[int] = None
    ):
        """
        Context manager for distributed lock.

        Usage:
            async with lock.lock_context("my-resource"):
                # Do work under lock
                pass
        """
        lock_info = await self.acquire(resource_id, ttl_seconds, timeout_ms)

        if not lock_info:
            raise LockAcquisitionError(f"Failed to acquire lock for {resource_id}")

        try:
            yield lock_info
        finally:
            await self.release(lock_info)

    async def is_locked(self, resource_id: Union[str, uuid.UUID, T]) -> bool:
        """Check if resource is currently locked"""
        try:
            redis = await get_global_client()
            lock_key = self._get_lock_key(resource_id)
            value = await redis.get(lock_key)
            return value is not None
        except Exception as e:
            logger.error(f"Error checking lock status: {e}")
            return False

    async def force_release(self, resource_id: Union[str, uuid.UUID, T]) -> bool:
        """
        Force release a lock (admin operation).
        Should only be used when certain the lock holder is dead.
        """
        try:
            redis = await get_global_client()
            lock_key = self._get_lock_key(resource_id)
            deleted = await redis.delete(lock_key)

            if deleted:
                logger.warning(f"Force released lock for {resource_id}")

            return bool(deleted)

        except Exception as e:
            logger.error(f"Error force releasing lock: {e}")
            return False

    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """Get lock metrics"""
        return self._metrics.get_stats() if self._metrics else None

    async def _auto_cleanup_task(self):
        """Background task to clean up stale held locks"""
        while True:
            try:
                await asyncio.sleep(60)

                stale_locks = []
                for lock_key, lock_info in self._held_locks.items():
                    if lock_info.is_expired():
                        stale_locks.append(lock_key)

                for lock_key in stale_locks:
                    logger.info(f"Cleaning up stale held lock: {lock_key}")
                    self._held_locks.pop(lock_key, None)

            except Exception as e:
                logger.error(f"Error in auto cleanup task: {e}")


# Backward compatibility classes
class DistributedLockManager(DistributedLock[uuid.UUID]):
    """EventStore compatibility class"""

    def __init__(
            self,
            namespace: str = "aggregate_lock",
            default_ttl_ms: int = 30000,
            max_wait_ms: int = 5000,
            retry_delay_ms: int = 50,
            enable_auto_cleanup: bool = True
    ):
        config = DistributedLockConfig(
            namespace=namespace,
            ttl_seconds=default_ttl_ms // 1000,
            max_wait_ms=max_wait_ms,
            retry_delay_ms=retry_delay_ms,
            enable_auto_cleanup=enable_auto_cleanup,
            retry_times=max_wait_ms // retry_delay_ms  # Calculate retry times
        )
        super().__init__(config)
        self.default_ttl_ms = default_ttl_ms

    async def acquire_lock(
            self,
            aggregate_id: uuid.UUID,
            ttl_ms: Optional[int] = None,
            wait: bool = True
    ) -> 'LockInfo':
        """EventStore compatible acquire method"""
        ttl_seconds = (ttl_ms or self.default_ttl_ms) // 1000

        if not wait:
            # Use fail-fast strategy
            self.strategy = LockStrategy.FAIL_FAST

        result = await self.acquire(aggregate_id, ttl_seconds=ttl_seconds)

        if not result:
            raise LockAcquisitionError(f"Failed to acquire lock for aggregate {aggregate_id}")

        return result

    async def release_lock(self, lock_info: LockInfo) -> bool:
        """EventStore compatible release method"""
        return await self.release(lock_info)

    @asynccontextmanager
    async def lock_aggregate(
            self,
            aggregate_id: uuid.UUID,
            ttl_ms: Optional[int] = None,
            wait: bool = True
    ):
        """EventStore compatible context manager"""
        lock_info = await self.acquire_lock(aggregate_id, ttl_ms, wait)
        try:
            yield lock_info
        finally:
            await self.release_lock(lock_info)


class SemaphoreManager:
    """Distributed semaphore manager"""

    def __init__(self, redis_prefix: str = "semaphore:"):
        self.redis_prefix = redis_prefix
        self._semaphore_metrics: Dict[str, Dict[str, int]] = {}

    @asynccontextmanager
    async def semaphore(self, name: str, limit: int = 5, timeout: float = 30.0):
        """
        Distributed semaphore context manager
        """
        redis = await get_global_client()
        semaphore_key = f"{self.redis_prefix}{name}"
        member = str(uuid.uuid4())

        if name not in self._semaphore_metrics:
            self._semaphore_metrics[name] = {
                "acquisitions": 0,
                "timeouts": 0,
                "current": 0
            }

        self._semaphore_metrics[name]["acquisitions"] += 1
        acquired = False
        start_time = time.time()

        try:
            # Lua script for atomic semaphore acquisition
            lua_acquire = """
            local key = KEYS[1]
            local member = ARGV[1]
            local limit = tonumber(ARGV[2])
            local ttl = tonumber(ARGV[3])

            -- Clean up expired members
            redis.call("zremrangebyscore", key, 0, redis.call("time")[1] - ttl)

            local count = redis.call("zcard", key)
            if count < limit then
                redis.call("zadd", key, redis.call("time")[1], member)
                redis.call("expire", key, ttl)
                return 1
            else
                return 0
            end
            """

            retry_delay = 0.1
            max_retries = int(timeout / retry_delay)

            for attempt in range(max_retries):
                acquired = await redis.eval(
                    lua_acquire,
                    1,
                    semaphore_key,
                    member,
                    limit,
                    300  # 5 min TTL
                )

                if acquired:
                    self._semaphore_metrics[name]["current"] += 1
                    wait_time = time.time() - start_time
                    logger.debug(f"Acquired semaphore {name} after {wait_time:.1f}s")
                    break

                if attempt < max_retries - 1:
                    delay = min(retry_delay * (1.5 ** min(attempt, 10)), 1.0)
                    await asyncio.sleep(delay + random.uniform(0, 0.1))

            if not acquired:
                self._semaphore_metrics[name]["timeouts"] += 1
                raise asyncio.TimeoutError(f"Semaphore {name} acquisition timeout")

            yield

        finally:
            if acquired:
                try:
                    lua_release = """
                    local key = KEYS[1]
                    local member = ARGV[1]
                    return redis.call("zrem", key, member)
                    """

                    released = await redis.eval(lua_release, 1, semaphore_key, member)
                    if released:
                        self._semaphore_metrics[name]["current"] -= 1
                        logger.debug(f"Released semaphore {name}")
                except Exception as e:
                    logger.error(f"Error releasing semaphore {name}: {e}")


# Service-specific lock factories
def create_event_store_lock() -> DistributedLockManager:
    """Create lock for EventStore aggregates"""
    config = ReliabilityConfigs.event_store_distributed_lock()
    return DistributedLockManager(
        namespace=config.namespace,
        default_ttl_ms=config.ttl_seconds * 1000,
        max_wait_ms=config.max_wait_ms,
        retry_delay_ms=config.retry_delay_ms,
        enable_auto_cleanup=config.enable_auto_cleanup
    )


def create_event_bus_lock() -> DistributedLock[str]:
    """Create lock for EventBus message processing"""
    config = ReliabilityConfigs.event_bus_distributed_lock()
    return DistributedLock(config)


def create_adapter_pool_lock() -> DistributedLock[str]:
    """Create lock for AdapterPool operations"""
    config = ReliabilityConfigs.adapter_pool_distributed_lock()
    return DistributedLock(config)


def create_cache_lock() -> DistributedLock[str]:
    """Create lock for cache operations"""
    config = ReliabilityConfigs.cache_distributed_lock()
    return DistributedLock(config)


def create_saga_lock() -> DistributedLock[str]:
    """Create lock for saga execution"""
    config = ReliabilityConfigs.saga_distributed_lock()
    return DistributedLock(config)


# Global lock manager instance
_default_lock_manager: Optional[DistributedLockManager] = None


def get_lock_manager() -> DistributedLockManager:
    """Get the default lock manager instance (EventStore compatibility)"""
    global _default_lock_manager
    if _default_lock_manager is None:
        _default_lock_manager = create_event_store_lock()
    return _default_lock_manager

# =============================================================================
# EOF
# =============================================================================