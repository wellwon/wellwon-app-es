# =============================================================================
#  File: app/api/models/user_account_api_models.py
#  WellWon API Models - User Account & Authentication
# =============================================================================
#  Complete Pydantic models for user account and auth endpoints
#  Includes all models previously duplicated in router
# =============================================================================

from __future__ import annotations

from typing import Optional, Dict, Any, List, Annotated
from datetime import datetime, timezone
from enum import Enum

from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    EmailStr,
    field_validator,
    StringConstraints,
    model_validator
)

# ──────────────────────────────────────────────────────────────────────────────
#  TYPE ALIASES (Pydantic v2 style)
# ──────────────────────────────────────────────────────────────────────────────

Username = Annotated[str, StringConstraints(min_length=3, max_length=100, pattern=r'^[a-zA-Z0-9_.@+-]+$')]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]
StrongPassword = Annotated[str, StringConstraints(min_length=12, max_length=128)]
SecretPhrase = Annotated[str, StringConstraints(min_length=6, max_length=100)]


# ──────────────────────────────────────────────────────────────────────────────
#  ENUMS
# ──────────────────────────────────────────────────────────────────────────────
class TokenType(str, Enum):
    """JWT token types."""
    ACCESS = "access"
    REFRESH = "refresh"


class AuthEventType(str, Enum):
    """Security event types."""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    LOGOUT_ALL = "logout_all"
    TOKEN_REFRESHED = "token_refreshed"
    TOKEN_REVOKED = "token_revoked"
    TOKEN_REUSE_DETECTED = "token_reuse_detected"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_DELETED = "account_deleted"
    SESSION_LIMIT_EXCEEDED = "session_limit_exceeded"


# ──────────────────────────────────────────────────────────────────────────────
#  AUTHENTICATION MODELS
# ──────────────────────────────────────────────────────────────────────────────
class AuthRequest(BaseModel):
    """Login request."""
    username: Username = Field(description="Username (alphanumeric, underscore, hyphen only)")
    password: Password = Field(description="User password")
    mfa_code: Optional[str] = Field(default=None, description="MFA code if enabled")
    device_info: Optional[Dict[str, Any]] = Field(default=None, description="Device information for session tracking")
    remember_me: bool = Field(default=False, description="Extended session duration")


class AuthResponse(BaseModel):
    """Enhanced login response with session info."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")
    scope: Optional[str] = None
    requires_mfa: bool = False
    session_id: str
    active_sessions: int = Field(default=1, description="Number of active sessions for this user")


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Enhanced refresh token response."""
    access_token: str
    refresh_token: Optional[str] = Field(default=None, description="New refresh token if rotated")
    token_type: str = "Bearer"
    expires_in: int
    token_rotated: bool = Field(default=False, description="Whether refresh token was rotated")


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTRATION
# ──────────────────────────────────────────────────────────────────────────────
# noinspection PyMethodParameters
class RegisterRequest(BaseModel):
    """User registration."""
    username: Username
    email: EmailStr
    password: Password
    secret: Optional[str] = Field(default="default_secret", min_length=6, max_length=100, description="Secret phrase for password recovery (optional)")
    terms_accepted: bool = True
    marketing_consent: bool = False
    referral_code: Optional[str] = None
    # WellWon profile fields (optional, collected during registration)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)

    @field_validator('password')
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength."""
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?/\\' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v

    @field_validator('terms_accepted')
    def must_accept_terms(cls, v: bool) -> bool:
        """Ensure terms are accepted."""
        if not v:
            raise ValueError('Terms of service must be accepted')
        return v


# ──────────────────────────────────────────────────────────────────────────────
#  PASSWORD MANAGEMENT
# ──────────────────────────────────────────────────────────────────────────────
# noinspection PyMethodParameters
class PasswordResetRequest(BaseModel):
    """Password reset."""
    username: str
    secret: str
    new_password: StrongPassword
    reset_token: Optional[str] = None

    @field_validator('new_password')
    def validate_password_strength(cls, v: str) -> str:
        """Reuse password validation from RegisterRequest."""
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?/\\' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v


class VerifyPasswordPayload(BaseModel):
    """Password verification."""
    password: Password
    operation: Optional[str] = None


# noinspection PyMethodParameters
class ChangePasswordPayload(BaseModel):
    """Password change."""
    old_password: Password
    new_password: StrongPassword
    revoke_all_sessions: bool = True

    @model_validator(mode='after')
    def validate_passwords(self) -> 'ChangePasswordPayload':
        """Ensure the new password is different."""
        if self.old_password == self.new_password:
            raise ValueError('New password must be different from current password')
        return self

    @field_validator('new_password')
    def validate_password_strength(cls, v: str) -> str:
        """Validate new password strength."""
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?/\\' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v


# ──────────────────────────────────────────────────────────────────────────────
#  USER PROFILE
# ──────────────────────────────────────────────────────────────────────────────
class UserProfileResponse(BaseModel):
    """User profile information for WellWon platform."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    user_id: str
    username: str
    email: EmailStr
    role: str
    is_active: bool = True
    email_verified: bool = False
    mfa_enabled: bool = False
    created_at: datetime
    last_login: Optional[datetime] = None
    last_password_change: Optional[datetime] = None
    security_alerts_enabled: bool = True
    active_sessions_count: int = Field(default=0, description="Number of active sessions")
    preferences: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # WellWon Platform fields
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    phone: Optional[str] = None
    user_type: str = Field(default="entrepreneur", description="WellWon user type: ww_admin, ww_manager, entrepreneur, investor")
    user_number: Optional[int] = None


class UpdateProfileRequest(BaseModel):
    """Profile update request."""
    email: Optional[EmailStr] = None
    security_alerts_enabled: Optional[bool] = None
    mfa_enabled: Optional[bool] = None
    preferences: Optional[Dict[str, Any]] = None

    # WellWon Platform fields
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = Field(None, max_length=1000)
    phone: Optional[str] = Field(None, max_length=20)


# ──────────────────────────────────────────────────────────────────────────────
#  STATUS RESPONSES
# ──────────────────────────────────────────────────────────────────────────────
class StatusResponse(BaseModel):
    """Generic status response."""
    status: str
    message: Optional[str] = None
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ──────────────────────────────────────────────────────────────────────────────
#  ACCOUNT DELETION
# ──────────────────────────────────────────────────────────────────────────────
# noinspection PyMethodParameters
class DeleteAccountPayload(BaseModel):
    """Account deletion request."""
    password: Password
    confirmation_phrase: str = Field(description="Type 'DELETE MY ACCOUNT' to confirm")
    reason: Optional[str] = None
    feedback: Optional[str] = None

    @field_validator('confirmation_phrase')
    def validate_confirmation(cls, v: str) -> str:
        """Validate confirmation phrase."""
        if v != "DELETE MY ACCOUNT":
            raise ValueError("Please type 'DELETE MY ACCOUNT' to confirm")
        return v


class AccountDeletionStatusResponse(BaseModel):
    """Deletion status."""
    status: str
    scheduled_deletion_date: datetime
    grace_period_days: int = 30
    can_be_cancelled: bool = True
    data_export_available: bool = True


# ──────────────────────────────────────────────────────────────────────────────
#  SESSION MANAGEMENT
# ──────────────────────────────────────────────────────────────────────────────
class DeviceInfo(BaseModel):
    """Device information for session tracking."""
    user_agent: str = "Unknown"
    ip_address: str = "Unknown"
    accept_language: str = "Unknown"
    platform: Optional[str] = None
    browser: Optional[str] = None


class SessionInfo(BaseModel):
    """Enhanced session information."""
    session_id: str
    family_id: str
    created_at: datetime
    last_used: datetime
    expires_at: datetime
    device_info: DeviceInfo
    location: Optional[Dict[str, Any]] = None
    is_current: bool = False
    rotation_count: int = 0


class ActiveSessionsResponse(BaseModel):
    """Active sessions list."""
    sessions: List[SessionInfo]
    total_count: int
    max_allowed: int = 5


class TerminateSessionRequest(BaseModel):
    """Request to terminate a specific session."""
    session_id: str
    reason: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
#  SECURITY & AUDIT
# ──────────────────────────────────────────────────────────────────────────────
class SecurityEventResponse(BaseModel):
    """Security event."""
    event_id: str
    event_type: AuthEventType
    user_id: str
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    success: bool
    details: Optional[Dict[str, Any]] = None


# ──────────────────────────────────────────────────────────────────────────────
#  TOKEN INTROSPECTION
# ──────────────────────────────────────────────────────────────────────────────
class TokenValidationResponse(BaseModel):
    """Token introspection response."""
    valid: bool
    active: bool
    token_type: Optional[TokenType] = None
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None
    sub: Optional[str] = None
    username: Optional[str] = None
    scope: Optional[str] = None
    session_id: Optional[str] = None
    fingerprint_valid: bool = False