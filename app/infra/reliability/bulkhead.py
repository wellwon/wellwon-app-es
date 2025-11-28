# =============================================================================
# File: app/infra/reliability/bulkhead.py
# Description: Distributed bulkhead pattern implementation for resource isolation
#              Prevents one slow/failing broker from blocking operations on others
# =============================================================================

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import TypeVar, Generic, Callable, Optional, Dict, Any, TYPE_CHECKING

from app.config.reliability_config import BulkheadConfig, ReliabilityConfigs

if TYPE_CHECKING:
    from app.infra.reliability.distributed_lock import SemaphoreManager

logger = logging.getLogger("tradecore.reliability.bulkhead")

T = TypeVar('T')


# =============================================================================
# EXCEPTIONS
# =============================================================================

class BulkheadError(Exception):
    """Base exception for bulkhead errors"""
    pass


class BulkheadRejectedError(BulkheadError):
    """Raised when bulkhead rejects execution due to capacity limits"""

    def __init__(self, bulkhead_name: str, reason: str):
        self.bulkhead_name = bulkhead_name
        self.reason = reason
        super().__init__(f"Bulkhead '{bulkhead_name}' rejected: {reason}")


class BulkheadTimeoutError(BulkheadError):
    """Raised when waiting for bulkhead slot times out"""

    def __init__(self, bulkhead_name: str, timeout_ms: int):
        self.bulkhead_name = bulkhead_name
        self.timeout_ms = timeout_ms
        super().__init__(f"Bulkhead '{bulkhead_name}' timeout after {timeout_ms}ms")


# =============================================================================
# METRICS (optional - graceful degradation if not available)
# =============================================================================

try:
    from app.infra.metrics.broker_adapter import (
        bulkhead_active_count,
        bulkhead_queued_count,
        bulkhead_rejected_total,
        bulkhead_timeouts_total,
        bulkhead_wait_seconds,
        bulkhead_utilization,
        bulkhead_acquisitions_total
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    bulkhead_active_count = None
    bulkhead_queued_count = None
    bulkhead_rejected_total = None
    bulkhead_timeouts_total = None
    bulkhead_wait_seconds = None
    bulkhead_utilization = None
    bulkhead_acquisitions_total = None


# =============================================================================
# BULKHEAD IMPLEMENTATION
# =============================================================================

class Bulkhead(Generic[T]):
    """
    Distributed bulkhead pattern implementation for resource isolation.

    Uses Redis-based distributed semaphore (SemaphoreManager) to coordinate
    across multiple server instances.

    Features:
    - Per-broker concurrent request limits
    - Configurable timeout when bulkhead full
    - Prometheus metrics integration
    - Works across multiple server instances (Redis-backed)

    Usage:
        bulkhead = await get_broker_bulkhead("alpaca")

        # Context manager style
        async with bulkhead.acquire():
            result = await broker_api_call()

        # Or execute style
        result = await bulkhead.execute(broker_api_call, arg1, arg2)
    """

    def __init__(
        self,
        config: BulkheadConfig,
        semaphore_manager: Optional['SemaphoreManager'] = None
    ):
        self.name = config.name
        self.config = config
        self._semaphore_manager = semaphore_manager

        # Local tracking (for metrics and state reporting)
        self._active_count = 0
        self._queued_count = 0
        self._rejected_count = 0
        self._timeout_count = 0
        self._total_acquisitions = 0
        self._lock = asyncio.Lock()

        logger.debug(
            f"Bulkhead '{self.name}' initialized: "
            f"max_concurrent={config.max_concurrent}, "
            f"timeout_ms={config.timeout_ms}"
        )

    @asynccontextmanager
    async def acquire(self, timeout_ms: Optional[int] = None):
        """
        Acquire a slot from the bulkhead.

        Args:
            timeout_ms: Override default timeout (in milliseconds)

        Raises:
            BulkheadTimeoutError: If timeout waiting for slot
            BulkheadRejectedError: If bulkhead full and cannot queue

        Yields:
            None - use as context manager
        """
        timeout = (timeout_ms or self.config.timeout_ms) / 1000.0
        start_time = time.monotonic()

        # Track queued state
        async with self._lock:
            self._queued_count += 1
            if METRICS_AVAILABLE:
                bulkhead_queued_count.labels(name=self.name).set(self._queued_count)

        try:
            if self._semaphore_manager and self.config.distributed:
                # Use distributed semaphore (Redis-backed)
                try:
                    async with self._semaphore_manager.semaphore(
                        name=self.config.name,
                        limit=self.config.max_concurrent,
                        timeout=timeout
                    ):
                        # Track active state
                        async with self._lock:
                            self._queued_count -= 1
                            self._active_count += 1
                            self._total_acquisitions += 1

                            if METRICS_AVAILABLE:
                                bulkhead_queued_count.labels(name=self.name).set(self._queued_count)
                                bulkhead_active_count.labels(name=self.name).set(self._active_count)
                                bulkhead_acquisitions_total.labels(name=self.name).inc()
                                bulkhead_utilization.labels(name=self.name).set(
                                    self._active_count / self.config.max_concurrent
                                )

                        # Record wait time
                        wait_time = time.monotonic() - start_time
                        if METRICS_AVAILABLE:
                            bulkhead_wait_seconds.labels(name=self.name).observe(wait_time)

                        try:
                            yield
                        finally:
                            async with self._lock:
                                self._active_count -= 1
                                if METRICS_AVAILABLE:
                                    bulkhead_active_count.labels(name=self.name).set(self._active_count)
                                    bulkhead_utilization.labels(name=self.name).set(
                                        self._active_count / self.config.max_concurrent
                                    )

                except asyncio.TimeoutError:
                    async with self._lock:
                        self._queued_count -= 1
                        self._timeout_count += 1
                        if METRICS_AVAILABLE:
                            bulkhead_queued_count.labels(name=self.name).set(self._queued_count)
                            bulkhead_timeouts_total.labels(name=self.name).inc()

                    logger.warning(
                        f"Bulkhead '{self.name}' timeout after {timeout}s"
                    )
                    raise BulkheadTimeoutError(self.name, int(timeout * 1000))

            else:
                # Fallback to local asyncio.Semaphore (single instance)
                await self._acquire_local(timeout, start_time)
                yield

        except (BulkheadTimeoutError, BulkheadRejectedError):
            raise
        except Exception as e:
            # Auth errors (401/403) are client-side errors, not infrastructure issues
            # Industry standard: Don't log them as ERROR - they're expected failures
            if self._is_auth_error(e):
                logger.debug(f"Bulkhead '{self.name}' auth error (client-side): {e}")
            else:
                logger.error(f"Bulkhead '{self.name}' error: {e}")
            raise

    @staticmethod
    def _is_auth_error(exception: Exception) -> bool:
        """
        Check if exception is an authentication error.

        Industry standard: Auth errors (401/403) are client-side problems,
        not infrastructure issues. They should not be logged as ERROR.
        """
        # Check for BrokerAuthError type
        try:
            from app.common.exceptions.exceptions import BrokerAuthError
            if isinstance(exception, BrokerAuthError):
                return True
        except ImportError:
            pass

        # Check error message for auth patterns
        error_msg = str(exception).lower()
        auth_patterns = ['401', '403', 'unauthorized', 'forbidden', 'auth failed', 'authentication']
        return any(pattern in error_msg for pattern in auth_patterns)

    async def _acquire_local(self, timeout: float, start_time: float):
        """Fallback local semaphore acquisition (non-distributed)"""
        # This is a simplified local-only implementation
        # In production, the distributed semaphore should be used
        logger.debug(f"Using local semaphore for bulkhead '{self.name}'")

        async with self._lock:
            self._queued_count -= 1
            self._active_count += 1
            self._total_acquisitions += 1

            if METRICS_AVAILABLE:
                bulkhead_queued_count.labels(name=self.name).set(self._queued_count)
                bulkhead_active_count.labels(name=self.name).set(self._active_count)
                bulkhead_acquisitions_total.labels(name=self.name).inc()

        wait_time = time.monotonic() - start_time
        if METRICS_AVAILABLE:
            bulkhead_wait_seconds.labels(name=self.name).observe(wait_time)

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        timeout_ms: Optional[int] = None,
        **kwargs
    ) -> T:
        """
        Execute function within bulkhead isolation.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            timeout_ms: Override default timeout
            **kwargs: Keyword arguments for func

        Returns:
            Result of func

        Raises:
            BulkheadTimeoutError: If timeout waiting for slot
        """
        async with self.acquire(timeout_ms=timeout_ms):
            return await func(*args, **kwargs)

    def get_state(self) -> Dict[str, Any]:
        """Get current bulkhead state for monitoring."""
        return {
            "name": self.name,
            "max_concurrent": self.config.max_concurrent,
            "max_queue_size": self.config.max_queue_size,
            "timeout_ms": self.config.timeout_ms,
            "distributed": self.config.distributed,
            "active_count": self._active_count,
            "queued_count": self._queued_count,
            "available_slots": max(0, self.config.max_concurrent - self._active_count),
            "utilization": self._active_count / self.config.max_concurrent if self.config.max_concurrent > 0 else 0,
            "rejected_count": self._rejected_count,
            "timeout_count": self._timeout_count,
            "total_acquisitions": self._total_acquisitions
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics for health checks."""
        return {
            "active": self._active_count,
            "queued": self._queued_count,
            "max_concurrent": self.config.max_concurrent,
            "rejected": self._rejected_count,
            "timeouts": self._timeout_count,
            "utilization": self._active_count / self.config.max_concurrent if self.config.max_concurrent > 0 else 0
        }


# =============================================================================
# BULKHEAD REGISTRY
# =============================================================================

class BulkheadRegistry:
    """
    Registry for managing per-broker bulkheads.

    Provides centralized access to bulkheads and metrics aggregation.
    """

    def __init__(self):
        self._bulkheads: Dict[str, Bulkhead] = {}
        self._semaphore_manager: Optional['SemaphoreManager'] = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self):
        """Initialize registry with SemaphoreManager"""
        if self._initialized:
            return

        try:
            from app.infra.reliability.distributed_lock import SemaphoreManager
            self._semaphore_manager = SemaphoreManager(redis_prefix="bulkhead:")
            self._initialized = True
            logger.info("BulkheadRegistry initialized with distributed semaphore")
        except Exception as e:
            logger.warning(f"Could not initialize distributed semaphore: {e}. Using local mode.")
            self._initialized = True

    async def get_or_create(
        self,
        broker_id: str,
        config: Optional[BulkheadConfig] = None
    ) -> Bulkhead:
        """
        Get existing bulkhead or create new one for broker.

        Args:
            broker_id: Broker identifier (alpaca, tradestation, etc.)
            config: Optional custom config (uses ReliabilityConfigs if not provided)

        Returns:
            Bulkhead instance for the broker
        """
        await self.initialize()

        async with self._lock:
            if broker_id not in self._bulkheads:
                if config is None:
                    config = ReliabilityConfigs.broker_bulkhead(broker_id)

                self._bulkheads[broker_id] = Bulkhead(
                    config=config,
                    semaphore_manager=self._semaphore_manager
                )

                logger.info(
                    f"Created bulkhead for broker '{broker_id}': "
                    f"max_concurrent={config.max_concurrent}"
                )

            return self._bulkheads[broker_id]

    def get(self, broker_id: str) -> Optional[Bulkhead]:
        """Get bulkhead if it exists (without creating)."""
        return self._bulkheads.get(broker_id)

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get state of all bulkheads."""
        return {
            broker_id: bulkhead.get_state()
            for broker_id, bulkhead in self._bulkheads.items()
        }

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all bulkheads."""
        return {
            broker_id: bulkhead.get_metrics()
            for broker_id, bulkhead in self._bulkheads.items()
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary metrics across all bulkheads."""
        total_active = sum(b._active_count for b in self._bulkheads.values())
        total_queued = sum(b._queued_count for b in self._bulkheads.values())
        total_rejected = sum(b._rejected_count for b in self._bulkheads.values())
        total_timeouts = sum(b._timeout_count for b in self._bulkheads.values())

        utilizations = [
            b._active_count / b.config.max_concurrent
            for b in self._bulkheads.values()
            if b.config.max_concurrent > 0
        ]
        avg_utilization = sum(utilizations) / len(utilizations) if utilizations else 0

        return {
            "total_bulkheads": len(self._bulkheads),
            "total_active": total_active,
            "total_queued": total_queued,
            "total_rejected": total_rejected,
            "total_timeouts": total_timeouts,
            "average_utilization": avg_utilization,
            "brokers": list(self._bulkheads.keys())
        }


# =============================================================================
# GLOBAL REGISTRY AND FACTORY FUNCTIONS
# =============================================================================

_registry: Optional[BulkheadRegistry] = None


def get_bulkhead_registry() -> BulkheadRegistry:
    """Get or create the global bulkhead registry."""
    global _registry
    if _registry is None:
        _registry = BulkheadRegistry()
    return _registry


async def get_broker_bulkhead(broker_id: str) -> Bulkhead:
    """
    Get bulkhead for a specific broker.

    Convenience function that creates bulkhead if needed.

    Args:
        broker_id: Broker identifier (alpaca, tradestation, etc.)

    Returns:
        Bulkhead instance for the broker
    """
    registry = get_bulkhead_registry()
    return await registry.get_or_create(broker_id)
