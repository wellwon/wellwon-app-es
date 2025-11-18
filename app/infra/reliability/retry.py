# =============================================================================
# File: app/infra/reliability/retry.py
# Description: Retry mechanism with exponential backoff and jitter
# =============================================================================

import asyncio
import random
import time
from typing import TypeVar, Generic, Callable, Optional, Any, Union, Type, Tuple
from abc import ABC, abstractmethod
import logging

# Import configuration from central location
from app.config.reliability_config import RetryConfig

logger = logging.getLogger("wellwon.retry")

T = TypeVar('T')

# Backward compatible alias
RetryConfiguration = RetryConfig


# Jitter strategies
class JitterStrategy(ABC):
    """Base class for jitter strategies."""

    @abstractmethod
    def apply(self, base_delay: float) -> float:
        """Apply jitter to base delay."""
        pass


class FullJitter(JitterStrategy):
    """Full jitter: delay = random(0, base_delay)."""

    def apply(self, base_delay: float) -> float:
        return random.uniform(0, base_delay)


class EqualJitter(JitterStrategy):
    """Equal jitter: delay = base_delay/2 + random(0, base_delay/2)."""

    def apply(self, base_delay: float) -> float:
        half = base_delay / 2
        return half + random.uniform(0, half)


class DecorrelatedJitter(JitterStrategy):
    """Decorrelated jitter with memory of previous delay."""

    def __init__(self):
        self.previous_delay: Optional[float] = None

    def apply(self, base_delay: float) -> float:
        if self.previous_delay is None:
            self.previous_delay = base_delay

        max_delay = self.previous_delay * 3
        self.previous_delay = random.uniform(base_delay, max_delay)
        return self.previous_delay


class CompatibleJitter(JitterStrategy):
    """Compatible jitter: ±25% as in original implementation."""

    def apply(self, base_delay: float) -> float:
        jitter_factor = 1.0 + random.uniform(-0.25, 0.25)
        return base_delay * jitter_factor


def get_jitter_strategy(jitter_type: str) -> JitterStrategy:
    """Get jitter strategy by name."""
    strategies = {
        'full': FullJitter(),
        'equal': EqualJitter(),
        'decorrelated': DecorrelatedJitter(),
        'compatible': CompatibleJitter(),
    }
    return strategies.get(jitter_type, CompatibleJitter())


async def retry_async(
        func: Callable[..., T],
        *args,
        retry_config: Optional[RetryConfig] = None,
        context: str = "operation",
        **kwargs
) -> T:
    """Execute async function with retry logic."""
    if retry_config is None:
        retry_config = RetryConfig()

    # Handle config post-init
    if retry_config.exponential_base is not None:
        retry_config.backoff_factor = retry_config.exponential_base

    # Get jitter strategy
    if retry_config.jitter:
        jitter_strategy = get_jitter_strategy(getattr(retry_config, 'jitter_type', 'full'))
    else:
        jitter_strategy = None

    last_exception: Optional[Exception] = None

    for attempt in range(1, retry_config.max_attempts + 1):
        try:
            return await func(*args, **kwargs)

        except Exception as e:
            last_exception = e

            # Check retry condition
            if retry_config.retry_condition and not retry_config.retry_condition(e):
                logger.warning(
                    f"Retry condition not met for {context} after attempt {attempt}. Error: {e}"
                )
                raise

            if attempt >= retry_config.max_attempts:
                logger.warning(
                    f"Retry exhausted for {context} after {attempt} attempts. Last error: {e}"
                )
                raise

            # Calculate delay
            base_delay_ms = min(
                retry_config.initial_delay_ms * (retry_config.backoff_factor ** (attempt - 1)),
                retry_config.max_delay_ms
            )

            # Apply jitter
            if jitter_strategy:
                actual_delay_ms = jitter_strategy.apply(base_delay_ms)
            else:
                actual_delay_ms = base_delay_ms

            delay_seconds = actual_delay_ms / 1000

            logger.info(
                f"Retry attempt {attempt}/{retry_config.max_attempts} for {context} "
                f"after error: {e}. Waiting {delay_seconds:.2f}s before retry."
            )

            await asyncio.sleep(delay_seconds)

    if last_exception:
        raise last_exception
    else:
        raise RuntimeError("Unexpected retry failure")


async def with_retry(
        operation: Callable[..., Any],
        *args: Any,
        retry_config: Optional[RetryConfig] = None,
        context: str = "operation",
        **kwargs: Any
) -> Any:
    """Backward compatible alias for retry_async."""
    return await retry_async(
        operation,
        *args,
        retry_config=retry_config,
        context=context,
        **kwargs
    )


def retry_sync(
        func: Callable[..., T],
        *args,
        retry_config: Optional[RetryConfig] = None,
        context: str = "operation",
        **kwargs
) -> T:
    """Execute synchronous function with retry logic."""
    if retry_config is None:
        retry_config = RetryConfig()

    # Handle config post-init
    if retry_config.exponential_base is not None:
        retry_config.backoff_factor = retry_config.exponential_base

    # Get jitter strategy
    if retry_config.jitter:
        jitter_strategy = get_jitter_strategy(getattr(retry_config, 'jitter_type', 'full'))
    else:
        jitter_strategy = None

    last_exception: Optional[Exception] = None

    for attempt in range(1, retry_config.max_attempts + 1):
        try:
            return func(*args, **kwargs)

        except Exception as e:
            last_exception = e

            # Check retry condition
            if retry_config.retry_condition and not retry_config.retry_condition(e):
                logger.warning(
                    f"Retry condition not met for {context} after attempt {attempt}. Error: {e}"
                )
                raise

            if attempt >= retry_config.max_attempts:
                logger.warning(
                    f"Retry exhausted for {context} after {attempt} attempts. Last error: {e}"
                )
                raise

            # Calculate delay
            base_delay_ms = min(
                retry_config.initial_delay_ms * (retry_config.backoff_factor ** (attempt - 1)),
                retry_config.max_delay_ms
            )

            # Apply jitter
            if jitter_strategy:
                actual_delay_ms = jitter_strategy.apply(base_delay_ms)
            else:
                actual_delay_ms = base_delay_ms

            delay_seconds = actual_delay_ms / 1000

            logger.info(
                f"Retry attempt {attempt}/{retry_config.max_attempts} for {context} "
                f"after error: {e}. Waiting {delay_seconds:.2f}s before retry."
            )

            time.sleep(delay_seconds)

    if last_exception:
        raise last_exception
    else:
        raise RuntimeError("Unexpected retry failure")


# Permanent error marking
class PermanentError(Exception):
    """An error that should not be retried"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__permanent__ = True


def mark_permanent(error: Exception) -> Exception:
    """Mark an exception as permanent (should not be retried)"""
    error.__permanent__ = True
    return error


def is_permanent(error: Exception) -> bool:
    """Check if an exception is marked as permanent"""
    return getattr(error, '__permanent__', False)


class Retry(Generic[T]):
    """Enhanced retry with configurable backoff and jitter."""

    def __init__(self, name: str, config: RetryConfig):
        self.name = name
        self.config = config

        # Handle config post-init
        if config.exponential_base is not None:
            config.backoff_factor = config.exponential_base

        # Select jitter strategy
        if config.jitter:
            self.jitter_strategy = get_jitter_strategy(
                getattr(config, 'jitter_type', 'compatible')
            )
        else:
            self.jitter_strategy = None

    async def execute(
            self,
            func: Callable[..., T],
            *args,
            retry_on: Optional[Union[Type[Exception], Tuple[Type[Exception], ...]]] = None,
            **kwargs
    ) -> T:
        """Execute function with retry logic."""
        # Create a temporary config with retry condition
        if retry_on:
            if isinstance(retry_on, tuple):
                retry_condition = lambda e: isinstance(e, retry_on)
            else:
                retry_condition = lambda e: isinstance(e, retry_on)

            # Create new config with retry condition
            temp_config = RetryConfig(
                max_attempts=self.config.max_attempts,
                initial_delay_ms=self.config.initial_delay_ms,
                max_delay_ms=self.config.max_delay_ms,
                backoff_factor=self.config.backoff_factor,
                jitter=self.config.jitter,
                retry_condition=retry_condition,
                jitter_type=getattr(self.config, 'jitter_type', 'compatible')
            )
        else:
            temp_config = self.config

        return await retry_async(
            func,
            *args,
            retry_config=temp_config,
            context=self.name,
            **kwargs
        )


# For backward compatibility with event_bus.retry
class RetryPolicy:
    """Legacy retry policy class for compatibility."""

    def __init__(
            self,
            config: RetryConfig,
            retry_on_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
            logger: Optional[Any] = None
    ):
        self.config = config
        self.retry_on_exceptions = retry_on_exceptions
        self.logger = logger or logging.getLogger(__name__)

    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute with retry."""
        retry = Retry("retry_policy", self.config)
        return await retry.execute(
            func,
            *args,
            retry_on=self.retry_on_exceptions,
            **kwargs
        )