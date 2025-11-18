# =============================================================================
# File: app/infra/reliability/poison_pill_detector.py
# Description: Poison Pill Detection for Dead Letter Queue
# Pattern: Distinguish transient vs non-transient errors
# =============================================================================

import logging
from typing import Optional, Tuple
from enum import Enum

log = logging.getLogger("wellwon.reliability.poison_pill")


class ErrorCategory(Enum):
    """Categories of errors for retry decisions"""
    POISON_PILL = "poison_pill"      # Never retry - deterministic failure
    TRANSIENT = "transient"          # Should retry - temporary failure
    UNKNOWN = "unknown"              # Unknown - default to retry (safe)


class PoisonPillDetector:
    """
    Detect poison pill messages (non-retriable errors).

    Poison Pill: A message that ALWAYS fails no matter how many times retried.
    Common causes: Schema violations, malformed data, validation errors.

    Industry Pattern (2024):
    - Redpanda: "Non-transient errors must be detected early"
    - Kafka: "Poison pills are deterministic failures"
    - AWS/Microsoft: "Skip retries for non-transient errors"

    Clean Architecture:
    - Pure utility function (no dependencies)
    - Stateless (thread-safe)
    - Infrastructure layer (not domain)
    """

    # Non-transient errors: ALWAYS fail, skip retries
    POISON_PILL_PATTERNS = [
        # Data validation errors
        "ValidationError",
        "pydantic.ValidationError",
        "pydantic_core._pydantic_core.ValidationError",
        "SchemaViolationError",
        "SchemaValidationError",

        # Deserialization errors
        "JSONDecodeError",
        "json.decoder.JSONDecodeError",
        "UnicodeDecodeError",
        "msgpack.exceptions.UnpackException",

        # Data structure errors
        "KeyError",
        "AttributeError",
        "TypeError: expected",
        "ValueError: invalid",
        "ValueError: could not convert",

        # Business rule violations
        "InvalidOperationError",
        "BusinessRuleViolation",
        "InvariantViolation",

        # Avro/Protobuf schema errors
        "avro.io.AvroTypeException",
        "google.protobuf.message.DecodeError",
    ]

    # Transient errors: Might succeed on retry
    TRANSIENT_PATTERNS = [
        # Network errors
        "ConnectionError",
        "ConnectionRefusedError",
        "ConnectionResetError",
        "BrokenPipeError",

        # Timeout errors
        "TimeoutError",
        "asyncio.TimeoutError",
        "concurrent.futures._base.TimeoutError",
        "RequestTimeout",

        # Service availability
        "ServiceUnavailable",
        "TemporaryFailure",
        "TooManyRequests",
        "RateLimitExceeded",

        # Database/Connection pool errors
        "asyncpg.exceptions.TooManyConnectionsError",
        "asyncpg.exceptions.ConnectionDoesNotExistError",
        "OperationalError",

        # Kafka/Redpanda errors
        "aiokafka.errors.RequestTimedOutError",
        "aiokafka.errors.NotLeaderForPartitionError",
        "aiokafka.errors.KafkaConnectionError",

        # Redis errors
        "redis.exceptions.ConnectionError",
        "redis.exceptions.TimeoutError",
    ]

    @staticmethod
    def detect(
        exception: Optional[Exception] = None,
        error_message: str = ""
    ) -> Tuple[ErrorCategory, str]:
        """
        Detect if error is a poison pill (non-retriable).

        Args:
            exception: The exception object (if available)
            error_message: Error message string

        Returns:
            Tuple of (ErrorCategory, reason/explanation)

        Examples:
            >>> detect(ValidationError("Invalid schema"))
            (ErrorCategory.POISON_PILL, "pydantic.ValidationError")

            >>> detect(TimeoutError("Connection timeout"))
            (ErrorCategory.TRANSIENT, "TimeoutError")
        """
        # Build full error context
        error_type = type(exception).__name__ if exception else "Unknown"
        full_error = f"{error_type}: {error_message}"

        # Check poison pill patterns first (higher priority)
        for pattern in PoisonPillDetector.POISON_PILL_PATTERNS:
            if pattern in full_error:
                log.warning(
                    f"☠️ Poison pill detected: '{pattern}' in error - SKIP RETRY"
                )
                return (ErrorCategory.POISON_PILL, pattern)

        # Check transient patterns
        for pattern in PoisonPillDetector.TRANSIENT_PATTERNS:
            if pattern in full_error:
                log.info(
                    f"✅ Transient error detected: '{pattern}' - ALLOW RETRY"
                )
                return (ErrorCategory.TRANSIENT, pattern)

        # Unknown error - conservative approach: allow retries
        log.warning(
            f"⚠️ Unknown error type: '{error_type}' - DEFAULTING TO RETRY (safe)"
        )
        return (ErrorCategory.UNKNOWN, "unknown_error_type")

    @staticmethod
    def is_poison_pill(
        exception: Optional[Exception] = None,
        error_message: str = ""
    ) -> bool:
        """
        Simple boolean check: Is this a poison pill?

        Returns:
            True if poison pill (skip retries)
            False otherwise (allow retries)
        """
        category, _ = PoisonPillDetector.detect(exception, error_message)
        return category == ErrorCategory.POISON_PILL

    @staticmethod
    def should_retry(
        exception: Optional[Exception] = None,
        error_message: str = ""
    ) -> bool:
        """
        Should this error be retried?

        Returns:
            True if should retry (transient or unknown)
            False if should NOT retry (poison pill)
        """
        return not PoisonPillDetector.is_poison_pill(exception, error_message)

    @staticmethod
    def get_recommended_action(
        exception: Optional[Exception] = None,
        error_message: str = ""
    ) -> str:
        """
        Get recommended action for handling this error.

        Returns:
            Action string for logging/monitoring
        """
        category, reason = PoisonPillDetector.detect(exception, error_message)

        if category == ErrorCategory.POISON_PILL:
            return f"SKIP_RETRY (poison pill: {reason})"
        elif category == ErrorCategory.TRANSIENT:
            return f"RETRY_WITH_BACKOFF (transient: {reason})"
        else:
            return f"RETRY_CAUTIOUSLY (unknown: {reason})"


# Convenience functions for backward compatibility
def is_poison_pill(exception: Optional[Exception] = None, error_message: str = "") -> bool:
    """Standalone function - check if error is poison pill"""
    return PoisonPillDetector.is_poison_pill(exception, error_message)


def should_retry(exception: Optional[Exception] = None, error_message: str = "") -> bool:
    """Standalone function - check if error should be retried"""
    return PoisonPillDetector.should_retry(exception, error_message)
