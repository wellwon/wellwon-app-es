# app/user_account/queries.py
# =============================================================================
# File: app/user_account/queries.py
# Description: All query definitions for User Account domain
# UPDATED: Added password operation queries
# =============================================================================

from typing import Any, Optional
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.infra.cqrs.query_bus import Query
from app.user_account.enums import UserType, DEFAULT_USER_TYPE


# =============================================================================
# User Account Query Definitions
# =============================================================================

class GetUserProfileQuery(Query):
    """Get complete user profile"""
    user_id: uuid.UUID
    include_preferences: bool = True
    include_security_settings: bool = False


class GetUserByUsernameQuery(Query):
    """Find user by username"""
    username: str


class GetUserByEmailQuery(Query):
    """Find user by email"""
    email: str


class ValidateUserCredentialsQuery(Query):
    """Validate user password for sensitive operations"""
    user_id: uuid.UUID
    password: str


# =============================================================================
# Password Operation Queries (NEW)
# =============================================================================

class HashPasswordQuery(Query):
    """Hash a password using the system's password hashing"""
    password: str


class VerifyPasswordHashQuery(Query):
    """Verify a password against a hash"""
    plain_password: str
    hashed_password: str


# =============================================================================
# Existing queries continue below...
# =============================================================================

class GetUserActiveSessionsQuery(Query):
    """Get all active sessions for user"""
    user_id: uuid.UUID
    include_expired: bool = False


class GetUserSecuritySettingsQuery(Query):
    """Get user security settings"""
    user_id: uuid.UUID


class GetUserSessionHistoryQuery(Query):
    """Get user login/session history"""
    user_id: uuid.UUID
    limit: int = 50
    include_failed_attempts: bool = True


class CheckUserExistsQuery(Query):
    """Check if user exists by username or email"""
    username: Optional[str] = None
    email: Optional[str] = None


class GetUserNotificationPreferencesQuery(Query):
    """Get user notification preferences"""
    user_id: uuid.UUID


class GetUserResourcesQuery(Query):
    """Get all resources (connections and accounts) for a user for deletion tracking"""
    user_id: uuid.UUID
    saga_id: Optional[uuid.UUID] = None


# =============================================================================
# Auth Service Specific Queries
# =============================================================================

class GetUserAuthDetailsQuery(Query):
    """Get user authentication details"""
    user_id: uuid.UUID
    include_password_hash: bool = False
    include_session_info: bool = True


class GetUserCredentialsSummaryQuery(Query):
    """Get summary of user's stored credentials"""
    user_id: uuid.UUID
    include_expiry_info: bool = True


class ValidateUserSessionQuery(Query):
    """Validate user session for auth operations"""
    user_id: uuid.UUID
    session_id: str
    check_ip: Optional[str] = None


class GetUserAuthHistoryQuery(Query):
    """Get user authentication history"""
    user_id: uuid.UUID
    event_types: list[str]  # ["login", "logout", "token_refresh", "auth_failure"]
    limit: int = 100


# =============================================================================
# Operation Service Specific Queries
# =============================================================================

class GetUserOperationalStatusQuery(Query):
    """Get operational status for user"""
    user_id: uuid.UUID
    include_connection_status: bool = True
    include_account_status: bool = True


class GetUserOperationalLimitsQuery(Query):
    """Get operational limits for user"""
    user_id: uuid.UUID
    limit_type: str  # "api_calls", "orders", "connections"


# =============================================================================
# Monitoring-Specific Queries
# =============================================================================

class GetUsersWithActiveMonitoringQuery(Query):
    """Get users that have active monitoring"""
    include_metrics: bool = True
    limit: int = 100


class GetUserMonitoringStatusQuery(Query):
    """Get monitoring status for a specific user"""
    user_id: uuid.UUID
    include_connection_details: bool = True
    include_account_details: bool = True


class GetUserSystemHealthQuery(Query):
    """Get overall system health for a user"""
    user_id: uuid.UUID
    include_broker_health: bool = True
    include_account_health: bool = True
    include_session_health: bool = True


class GetUsersRequiringAttentionQuery(Query):
    """Get users with issues requiring attention"""
    issue_type: str  # "auth_failure", "stale_connection", "missing_accounts", "all"
    severity_threshold: str = "warning"  # "info", "warning", "error", "critical"
    limit: int = 100


class GetUserActivityMetricsQuery(Query):
    """Get activity metrics for a user"""
    user_id: uuid.UUID
    period_days: int = 30
    include_login_activity: bool = True


class GetUserComplianceStatusQuery(Query):
    """Get compliance status for monitoring"""
    user_id: uuid.UUID
    check_kyc: bool = True
    check_agreements: bool = True


class BatchGetUserStatusQuery(Query):
    """Batch get status for multiple users"""
    user_ids: list[uuid.UUID]
    include_connections: bool = True
    include_accounts: bool = False


class GetInactiveUsersQuery(Query):
    """Get users with no recent activity"""
    inactive_days: int = 30
    include_deleted: bool = False
    limit: int = 100


class GetUserAuditTrailQuery(Query):
    """Get audit trail for user monitoring"""
    user_id: uuid.UUID
    event_types: Optional[list[str]] = None  # Filter by specific events
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 1000


# =============================================================================
# Session Management Queries
# =============================================================================

class CreateUserSessionQuery(Query):
    """Create new user session"""
    user_id: uuid.UUID
    username: str
    role: str
    device_info: dict[str, str]
    remember_me: bool = False
    session_id: Optional[str] = None  # If provided, reuse this session ID


class InvalidateUserSessionQuery(Query):
    """Invalidate specific user session"""
    user_id: uuid.UUID
    session_id: str
    reason: Optional[str] = None


class InvalidateAllUserSessionsQuery(Query):
    """Invalidate all sessions for user"""
    user_id: uuid.UUID
    except_current: Optional[str] = None  # Session ID to keep active


class GetActiveSessionCountQuery(Query):
    """Get count of active sessions for user"""
    user_id: uuid.UUID


class CheckConcurrentSessionsQuery(Query):
    """Check and enforce concurrent session limits"""
    user_id: uuid.UUID
    max_sessions: int = 5


class StoreRefreshTokenFamilyQuery(Query):
    """Store refresh token family data"""
    family_id: str
    user_id: uuid.UUID
    session_id: str
    device_info: dict[str, str]
    jti: str
    expires_at: datetime
    username: str
    role: str


class GetRefreshTokenFamilyQuery(Query):
    """Get refresh token family data"""
    family_id: str


class UpdateRefreshTokenFamilyQuery(Query):
    """Update refresh token family after rotation"""
    family_id: str
    new_jti: str
    rotation_count: int
    expires_at: datetime


class BlacklistTokenQuery(Query):
    """Add token to blacklist"""
    jti: str
    expires_at: datetime


class CheckTokenBlacklistQuery(Query):
    """Check if token is blacklisted"""
    jti: str


class DetectTokenReuseQuery(Query):
    """Detect token reuse attack"""
    jti: str
    reuse_window_minutes: int = 5


class LogSecurityEventQuery(Query):
    """Log security event"""
    event_type: str
    user_id: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    details: Optional[dict[str, Any]] = None
    session_id: Optional[str] = None


# =============================================================================
# Query Result Types
# =============================================================================

class UserProfile(BaseModel):
    """User profile data"""
    id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool
    email_verified: bool
    mfa_enabled: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    last_password_change: Optional[datetime] = None
    security_alerts_enabled: bool
    preferences: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # WellWon Platform fields
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    phone: Optional[str] = None
    user_type: str = DEFAULT_USER_TYPE.value
    user_number: Optional[int] = None


class UserSession(BaseModel):
    """Active user session"""
    session_id: str
    family_id: str
    created_at: datetime
    last_used: datetime
    expires_at: datetime
    device_info: dict[str, str] = Field(default_factory=dict)
    rotation_count: int
    is_current: bool


class UserMonitoringStatus(BaseModel):
    """Monitoring status for a user"""
    user_id: uuid.UUID
    is_monitored: bool
    monitoring_level: str  # "basic", "standard", "premium"
    total_connections: int
    active_connections: int
    total_accounts: int
    health_status: str  # "healthy", "warning", "error", "critical"
    last_activity: Optional[datetime] = None
    issues: list[dict[str, Any]] = Field(default_factory=list)
    monitoring_metadata: dict[str, Any] = Field(default_factory=dict)


class UserSystemHealth(BaseModel):
    """Overall system health for a user"""
    user_id: uuid.UUID
    overall_status: str  # "healthy", "degraded", "critical"
    last_check_time: datetime
    session_health: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


class UserActivityMetrics(BaseModel):
    """Activity metrics for monitoring"""
    user_id: uuid.UUID
    period_days: int
    total_logins: int
    unique_login_days: int
    average_session_duration_minutes: float
    activity_trend: str  # "increasing", "stable", "decreasing"
    last_activity_time: Optional[datetime] = None


class UserComplianceStatus(BaseModel):
    """Compliance status for monitoring"""
    user_id: uuid.UUID
    is_compliant: bool
    kyc_status: str  # "verified", "pending", "failed", "not_started"
    agreements_signed: bool
    compliance_issues: list[dict[str, Any]] = Field(default_factory=list)
    last_review_date: Optional[datetime] = None
    next_review_date: Optional[datetime] = None


class UserAuditEntry(BaseModel):
    """Audit trail entry"""
    id: uuid.UUID
    user_id: uuid.UUID
    event_type: str
    event_details: dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None


class UserAuthDetails(BaseModel):
    """User authentication details"""
    user_id: uuid.UUID
    username: str
    email: str
    is_active: bool
    email_verified: bool
    mfa_enabled: bool
    role: str
    active_sessions: int
    last_session_activity: Optional[datetime] = None
    password_updated_at: Optional[datetime] = None


class UserOperationalStatus(BaseModel):
    """User operational status"""
    user_id: uuid.UUID
    is_active: bool
    is_operational: bool
    role: str
    restrictions: list[str] = Field(default_factory=list)
    connection_status: Optional[dict[str, Any]] = None
    account_status: Optional[dict[str, Any]] = None


# =============================================================================
# Session Management Result Types
# =============================================================================

class SessionCreationResult(BaseModel):
    """Result of session creation"""
    session_id: str
    family_id: str
    access_token: str
    refresh_token: str
    expires_in: int
    active_sessions_count: int
    fingerprint: str  # Raw fingerprint for cookie
    hashed_fingerprint: str  # For token


class RefreshTokenFamily(BaseModel):
    """Refresh token family data"""
    family_id: str
    user_id: uuid.UUID
    session_id: str
    device_info: dict[str, str]
    created_at: datetime
    last_used: datetime
    current_jti: str
    expires_at: datetime
    rotation_count: int
    is_active: bool
    username: str
    role: str


class TokenRotationResult(BaseModel):
    """Result of token rotation"""
    new_access_token: str
    new_refresh_token: Optional[str] = None
    token_rotated: bool
    expires_in: int


class SecurityEventResult(BaseModel):
    """Security event logging result"""
    event_id: str
    logged_at: datetime
    success: bool