# =============================================================================
# File: app/infra/reliability/circuit_breaker.py
# Description: Circuit breaker pattern implementation
# =============================================================================

import asyncio
import time
from datetime import datetime, timezone
from enum import Enum, auto
from typing import TypeVar, Generic, Callable, Optional, Any, Dict
from collections import deque
import logging

# Import configuration from central location
from app.config.reliability_config import CircuitBreakerConfig

# Import metrics if available
try:
    from app.infra.metrics.circuit_breaker import (
        circuit_breaker_state,
        circuit_breaker_failures,
        circuit_breaker_trips,
        circuit_breaker_call_duration
    )

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    # Define as None for code completion
    circuit_breaker_state = None
    circuit_breaker_failures = None
    circuit_breaker_trips = None
    circuit_breaker_call_duration = None

logger = logging.getLogger("wellwon.circuit_breaker")

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


class CircuitBreaker(Generic[T]):
    """Circuit Breaker implementation."""

    def __init__(
            self,
            config: CircuitBreakerConfig,
            cache_manager: Optional[Any] = None
    ):
        self.name = config.name
        self.config = config
        self.cache_manager = cache_manager

        # Core state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0

        # Enhanced features
        self._call_metrics: Optional[deque] = None
        if config.window_size:
            self._call_metrics = deque(maxlen=config.window_size)

        self._lock = asyncio.Lock()

        # Support both reset_timeout_seconds and timeout_seconds
        if config.timeout_seconds is not None:
            self.config.reset_timeout_seconds = config.timeout_seconds

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if not self._can_execute():
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")

        start_time = time.monotonic()

        try:
            result = await func(*args, **kwargs)
            duration = time.monotonic() - start_time
            await self._on_success(duration)
            return result

        except Exception as e:
            duration = time.monotonic() - start_time
            await self._on_failure(duration, str(e))
            raise

    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        return self._can_execute()

    def _can_execute(self) -> bool:
        """Internal check if operation can be executed."""
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info(f"circuit_breaker_half_open for {self.name}")

                # Emit metrics
                if METRICS_AVAILABLE and circuit_breaker_state is not None:
                    circuit_breaker_state.labels(name=self.name).set(2)  # 2 = HALF_OPEN

                return True
            return False

        # HALF_OPEN state
        if self._half_open_calls < self.config.half_open_max_calls:
            self._half_open_calls += 1
            return True
        return False

    def record_success(self) -> None:
        """Record successful call."""
        asyncio.create_task(self._on_success(0))

    def record_failure(self, error_details: Optional[str] = None) -> None:
        """Record failed call."""
        asyncio.create_task(self._on_failure(0, error_details))

    async def _on_success(self, duration: float) -> None:
        """Handle successful call."""
        async with self._lock:
            if self._call_metrics is not None:
                self._call_metrics.append((True, duration))

            self._failure_count = 0
            self._success_count += 1

            # Emit metrics
            if METRICS_AVAILABLE and circuit_breaker_call_duration is not None:
                circuit_breaker_call_duration.labels(name=self.name, result='success').observe(duration)

            if self._state == CircuitState.HALF_OPEN:
                if self._success_count >= self.config.success_threshold:
                    await self._transition_to_closed()

    async def _on_failure(self, duration: float, error_details: Optional[str] = None) -> None:
        """Handle failed call."""
        async with self._lock:
            if self._call_metrics is not None:
                self._call_metrics.append((False, duration))

            self._failure_count += 1
            self._last_failure_time = datetime.now(timezone.utc)

            # Log error details if provided
            if error_details:
                logger.debug(f"Circuit breaker {self.name} failure: {error_details}")

            # Emit metrics
            if METRICS_AVAILABLE:
                if circuit_breaker_failures is not None:
                    circuit_breaker_failures.labels(name=self.name).inc()
                if circuit_breaker_call_duration is not None:
                    circuit_breaker_call_duration.labels(name=self.name, result='failure').observe(duration)

            if self._state == CircuitState.HALF_OPEN:
                await self._transition_to_open()

            elif self._state == CircuitState.CLOSED:
                should_open = False

                if self._failure_count >= self.config.failure_threshold:
                    should_open = True

                elif (self.config.failure_rate_threshold is not None and
                      self._call_metrics is not None and
                      len(self._call_metrics) >= self.config.window_size):
                    failure_rate = self._calculate_failure_rate()
                    if failure_rate >= self.config.failure_rate_threshold:
                        should_open = True

                if should_open:
                    await self._transition_to_open()

    def _calculate_failure_rate(self) -> float:
        """Calculate current failure rate from sliding window."""
        if not self._call_metrics:
            return 0.0

        failures = sum(1 for success, _ in self._call_metrics if not success)
        return failures / len(self._call_metrics)

    def _should_attempt_reset(self) -> bool:
        """Check if timeout has passed."""
        if self._last_failure_time is None:
            return True

        elapsed = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
        return elapsed >= self.config.reset_timeout_seconds

    async def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

        logger.info(f"circuit_breaker_closed for {self.name}")

        # Emit metrics
        if METRICS_AVAILABLE and circuit_breaker_state is not None:
            circuit_breaker_state.labels(name=self.name).set(0)  # 0 = CLOSED

        if self.cache_manager:
            await self.cache_manager.set(
                f"circuit_breaker:{self.name}:state",
                "CLOSED",
                ttl=3600
            )

    async def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        self._state = CircuitState.OPEN
        self._success_count = 0

        logger.warning(f"circuit_breaker_opened for {self.name}")

        # Emit metrics
        if METRICS_AVAILABLE:
            if circuit_breaker_state is not None:
                circuit_breaker_state.labels(name=self.name).set(1)  # 1 = OPEN
            if circuit_breaker_trips is not None:
                circuit_breaker_trips.labels(name=self.name).inc()

        if self.cache_manager:
            await self.cache_manager.set(
                f"circuit_breaker:{self.name}:state",
                "OPEN",
                ttl=3600
            )

    async def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state and metrics."""
        async with self._lock:
            state_info = {
                "name": self.name,
                "state": self._state.name,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time.isoformat() if self._last_failure_time else None,
            }

            if self._call_metrics is not None:
                state_info.update({
                    "failure_rate": self._calculate_failure_rate(),
                    "metrics_window": len(self._call_metrics)
                })

            return state_info

    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics (sync method)."""
        return {
            "name": self.name,
            "state": self._state.name,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
        }

    def get_state_sync(self) -> str:
        """Get current state synchronously (for compatibility)."""
        return self._state.name

    async def execute_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Alias for call()."""
        return await self.call(func, *args, **kwargs)


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreakerError(Exception):
    """Base circuit breaker error."""
    pass


# Global registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        cache_manager: Optional[Any] = None
) -> CircuitBreaker:
    """Get or create a circuit breaker instance."""
    if name not in _circuit_breakers:
        if config is None:
            config = CircuitBreakerConfig(name=name)

        _circuit_breakers[name] = CircuitBreaker(config, cache_manager)

    return _circuit_breakers[name]


def get_all_circuit_breaker_metrics() -> Dict[str, Dict[str, Any]]:
    """Get metrics for all circuit breakers."""
    metrics = {}

    for name, breaker in _circuit_breakers.items():
        try:
            metrics[name] = breaker.get_metrics()
        except Exception as e:
            logger.error(f"Error getting metrics for circuit breaker {name}: {e}")
            metrics[name] = {"error": str(e)}

    return metrics