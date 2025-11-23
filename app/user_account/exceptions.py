# =============================================================================
# File: app/user_account/exceptions.py
# Description: Domain-specific exceptions for UserAccount domain
# =============================================================================

from app.common.exceptions.exceptions import DomainError, ResourceNotFoundError


class UserAccountError(DomainError):
    """Base exception for UserAccount domain"""
    pass


class UserAlreadyExistsError(UserAccountError):
    """Raised when attempting to create a user that already exists"""
    pass


class UserNotFoundError(ResourceNotFoundError):
    """Raised when user is not found by ID, username, or email"""
    pass


class InvalidCredentialsError(UserAccountError):
    """Raised when authentication credentials are invalid"""
    pass


class UserInactiveError(UserAccountError):
    """Raised when attempting operation on inactive/deleted user"""
    pass


class EmailNotVerifiedError(UserAccountError):
    """Raised when email verification is required for operation"""
    pass


class PasswordValidationError(UserAccountError):
    """Raised when password doesn't meet security requirements"""
    pass


class SecretValidationError(UserAccountError):
    """Raised when secret word is invalid or doesn't match"""
    pass


class InvalidOperationError(UserAccountError):
    """Raised when operation is not allowed in current state"""
    pass


class EmailAlreadyVerifiedError(UserAccountError):
    """Raised when attempting to verify already verified email"""
    pass


# =============================================================================
# EOF
# =============================================================================
