# =============================================================================
# File: app/infra/kontur/error_classifier.py
# Description: Error classification for Kontur Declarant API
# =============================================================================

from typing import Optional

from app.infra.kontur.exceptions import (
    KonturAuthenticationError,
    KonturAuthorizationError,
    KonturBadRequestError,
    KonturNotFoundError,
    KonturRateLimitError,
    KonturServerError,
    KonturNetworkError,
    KonturTimeoutError,
    KonturValidationError,
)


def classify_kontur_error(error: Exception) -> str:
    """
    Classify Kontur API error for retry decision.

    Returns:
        Error classification string:
        - "auth_error": Authentication failed (don't retry)
        - "authorization_error": Access forbidden (don't retry)
        - "validation_error": Bad request/validation (don't retry)
        - "not_found": Resource not found (don't retry)
        - "rate_limit": Rate limit exceeded (retry with backoff)
        - "server_error": Server error (retry)
        - "network_error": Network issue (retry)
        - "timeout": Request timeout (retry)
        - "unknown": Unknown error (retry to be safe)
    """
    if isinstance(error, KonturAuthenticationError):
        return "auth_error"

    if isinstance(error, KonturAuthorizationError):
        return "authorization_error"

    if isinstance(error, (KonturBadRequestError, KonturValidationError)):
        return "validation_error"

    if isinstance(error, KonturNotFoundError):
        return "not_found"

    if isinstance(error, KonturRateLimitError):
        return "rate_limit"

    if isinstance(error, KonturServerError):
        return "server_error"

    if isinstance(error, KonturNetworkError):
        return "network_error"

    if isinstance(error, KonturTimeoutError):
        return "timeout"

    return "unknown"


def should_retry_kontur(error: Exception) -> bool:
    """
    Determine if a Kontur API error should be retried.

    Retry logic:
    - Don't retry: Authentication, authorization, validation, not found
    - Retry: Server errors, network errors, timeouts, rate limits
    - Unknown errors: Retry (better to retry and fail than not retry and lose operation)

    Args:
        error: Exception to classify

    Returns:
        True if error should be retried, False otherwise
    """
    error_class = classify_kontur_error(error)

    # Don't retry client errors (except rate limit)
    if error_class in ["auth_error", "authorization_error", "validation_error"]:
        return False

    # Not found: Usually don't retry, but could be transient
    # For Kontur, treat as non-retriable since resource IDs are deterministic
    if error_class == "not_found":
        return False

    # Retry server errors, network errors, timeouts, rate limits
    if error_class in ["server_error", "network_error", "timeout", "rate_limit"]:
        return True

    # Unknown errors: Retry to be safe
    return True


def extract_retry_after(error: Exception) -> Optional[int]:
    """
    Extract Retry-After value from error if available.

    Args:
        error: Exception that may contain retry_after attribute

    Returns:
        Retry-after value in seconds, or None
    """
    if isinstance(error, KonturRateLimitError) and hasattr(error, 'retry_after'):
        return error.retry_after

    return None
