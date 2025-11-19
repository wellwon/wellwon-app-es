# app/common/exceptions/exceptions.py
# =============================================================================
# Custom exceptions for WellWon Platform
# =============================================================================


class WellWonException(Exception):
    """Base exception for WellWon platform"""
    pass


class PermissionError(WellWonException):
    """Raised when user doesn't have permission for an action"""
    pass


class AuthenticationError(WellWonException):
    """Raised when authentication fails"""
    pass


class AuthorizationError(WellWonException):
    """Raised when authorization fails"""
    pass


class ValidationError(WellWonException):
    """Raised when validation fails"""
    pass


class NotFoundError(WellWonException):
    """Raised when a resource is not found"""
    pass


# Alias for compatibility
ResourceNotFoundError = NotFoundError


class ConflictError(WellWonException):
    """Raised when there's a conflict (e.g., duplicate)"""
    pass


class ProjectionRebuildError(WellWonException):
    """Raised when projection rebuild fails"""
    pass


class DomainError(WellWonException):
    """Raised for domain-specific errors"""
    pass


class InfrastructureError(WellWonException):
    """Raised for infrastructure errors"""
    pass
