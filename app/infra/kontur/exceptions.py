# =============================================================================
# File: app/infra/kontur/exceptions.py
# Description: Exception hierarchy for Kontur Declarant API
# =============================================================================

from typing import Optional


class KonturError(Exception):
    """Base exception for Kontur API errors"""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


# =============================================================================
# Client Errors (4xx) - Don't retry
# =============================================================================

class KonturClientError(KonturError):
    """Base class for 4xx client errors"""
    pass


class KonturBadRequestError(KonturClientError):
    """400 Bad Request - Invalid request parameters or body"""
    pass


class KonturAuthenticationError(KonturClientError):
    """401 Unauthorized - Missing or invalid API key"""
    pass


class KonturSessionExpiredError(KonturClientError):
    """401 Unauthorized - Session expired (can retry with re-auth)"""
    pass


class KonturAuthorizationError(KonturClientError):
    """403 Forbidden - Valid API key but access denied to resource"""
    pass


class KonturNotFoundError(KonturClientError):
    """404 Not Found - Resource doesn't exist"""
    pass


class KonturRateLimitError(KonturClientError):
    """429 Too Many Requests - Rate limit exceeded (should retry with backoff)"""
    pass


class KonturValidationError(KonturClientError):
    """Data validation error"""
    pass


# =============================================================================
# Server Errors (5xx) - Retry
# =============================================================================

class KonturServerError(KonturError):
    """Base class for 5xx server errors"""
    pass


# =============================================================================
# Network Errors - Retry
# =============================================================================

class KonturNetworkError(KonturError):
    """Network connectivity errors"""
    pass


class KonturTimeoutError(KonturError):
    """Request timeout"""
    pass


# =============================================================================
# Infrastructure Errors
# =============================================================================

class KonturCircuitBreakerOpen(KonturError):
    """Circuit breaker is open - service is temporarily unavailable"""
    pass


class KonturBulkheadRejected(KonturError):
    """Bulkhead rejected request - too many concurrent operations"""
    pass


# =============================================================================
# Generic API Error
# =============================================================================

class KonturAPIError(KonturError):
    """Generic API error"""
    pass
