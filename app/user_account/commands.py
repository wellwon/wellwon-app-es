# =============================================================================
# File: app/user_account/commands.py
# Description: Domain commands for User operations in 
# UPDATED: Added saga_id support for all commands
# =============================================================================

from __future__ import annotations
from pydantic import BaseModel, Field, EmailStr, field_validator
import uuid
from typing import Optional


# -----------------------------------------------------------------------------
# Core User Commands
# -----------------------------------------------------------------------------
class CreateUserAccountCommand(BaseModel):
    """Command to create a new user account."""
    user_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Generated user ID")
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Plaintext password for hashing")
    secret: str = Field(..., min_length=4, description="Secret word for password reset")
    role: str = Field(default="user", description="User role (user, admin, etc)")

    # WellWon profile fields (optional, set during registration)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)

    # ADDED: Saga support
    saga_id: Optional[uuid.UUID] = Field(None, description="ID of orchestrating saga if part of larger workflow")

    @field_validator('username')
    @classmethod
    def username_valid(cls, v):
        # Allow email format: alphanumeric with _ - @ . +
        cleaned = v.replace('_', '').replace('-', '').replace('@', '').replace('.', '').replace('+', '')
        if not cleaned.isalnum():
            raise ValueError('Username must be alphanumeric or valid email format')
        return v.lower()


class AuthenticateUserCommand(BaseModel):
    """Command to authenticate a user."""
    username: str
    password: str

    # ADDED: Saga support (though authentication rarely needs it)
    saga_id: Optional[uuid.UUID] = Field(None, description="ID of orchestrating saga if part of larger workflow")


class ChangeUserPasswordCommand(BaseModel):
    """Command to change a user's password."""
    user_id: uuid.UUID
    current_password: str
    new_password: str = Field(..., min_length=8)

    # ADDED: Saga support
    saga_id: Optional[uuid.UUID] = Field(None, description="ID of orchestrating saga if part of larger workflow")


class ResetUserPasswordWithSecretCommand(BaseModel):
    """Command to reset a user's password using their secret word."""
    username: str
    secret: str
    new_password: str = Field(..., min_length=8)

    # ADDED: Saga support
    saga_id: Optional[uuid.UUID] = Field(None, description="ID of orchestrating saga if part of larger workflow")


class DeleteUserAccountCommand(BaseModel):
    """
    Command to delete a user account.
    Triggers cascade deletion via saga orchestration.
    """
    user_id: uuid.UUID
    grace_period: int = Field(
        default=0,
        ge=0,
        description="Grace period in seconds before hard-delete (0 = immediate)"
    )
    reason: Optional[str] = Field(
        default="self_delete",
        description="Reason for deletion (self_delete, admin_delete, etc)"
    )

    # ADDED: Saga support
    saga_id: Optional[uuid.UUID] = Field(None, description="ID of orchestrating saga if part of larger workflow")


class VerifyUserEmailCommand(BaseModel):
    """Command to verify user's email address."""
    user_id: uuid.UUID
    verification_token: str

    # ADDED: Saga support
    saga_id: Optional[uuid.UUID] = Field(None, description="ID of orchestrating saga if part of larger workflow")


# -----------------------------------------------------------------------------
# WellWon Platform Commands
# -----------------------------------------------------------------------------
class UpdateUserProfileCommand(BaseModel):
    """Command to update user profile information (WellWon)."""
    user_id: uuid.UUID
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = Field(None, max_length=1000)
    phone: Optional[str] = Field(None, max_length=20)
    user_type: Optional[str] = None
    is_developer: Optional[bool] = None

    # ADDED: Saga support
    saga_id: Optional[uuid.UUID] = Field(None, description="ID of orchestrating saga if part of larger workflow")

# =============================================================================
# EOF
# =============================================================================