# =============================================================================
# File: app/api/routers/user_account_router.py
# Description: User Account Router with CQRS Architecture - FIXED VERSION
# FIXED: Login endpoint now properly creates JWT tokens
# =============================================================================

from __future__ import annotations

import os
import uuid
import logging
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Annotated, Optional, Dict

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.security import HTTPBearer

# Import API models
from app.api.models.user_account_api_models import (
    AuthRequest,
    AuthResponse,
    RegisterRequest,
    UpdateProfileRequest,
    PasswordResetRequest,
    VerifyPasswordPayload,
    ChangePasswordPayload,
    StatusResponse,
    DeleteAccountPayload,
    RefreshTokenRequest,
    RefreshTokenResponse,
    SessionInfo,
    ActiveSessionsResponse,
    DeviceInfo,
    UserProfileResponse,
    TerminateSessionRequest,
    ProfileWithTelegramResponse,
    LinkTelegramRequest,
)

# Security - USE EXISTING SECURITY UTILITIES
from app.security.jwt_auth import (
    JwtTokenManager,
    get_current_user,
    extract_fingerprint_from_request,
    JWT_FINGERPRINT_ENABLED,
)

# CQRS Commands
from app.user_account.commands import (
    CreateUserAccountCommand,
    AuthenticateUserCommand,
    ChangeUserPasswordCommand,
    ResetUserPasswordWithSecretCommand,
    DeleteUserAccountCommand,
    UpdateUserProfileCommand,
)

# CQRS Queries - USE THESE INSTEAD OF DIRECT REDIS ACCESS
from app.user_account.queries import (
    GetUserProfileQuery,
    GetUserActiveSessionsQuery,
    ValidateUserCredentialsQuery,
    CreateUserSessionQuery,
    InvalidateUserSessionQuery,
    InvalidateAllUserSessionsQuery,
    GetActiveSessionCountQuery,
    CheckConcurrentSessionsQuery,
    StoreRefreshTokenFamilyQuery,
    GetRefreshTokenFamilyQuery,
    UpdateRefreshTokenFamilyQuery,
    BlacklistTokenQuery,
    CheckTokenBlacklistQuery,
    DetectTokenReuseQuery,
    LogSecurityEventQuery,
    SessionCreationResult,
    RefreshTokenFamily,
    TokenRotationResult,
)

log = logging.getLogger("wellwon.api.user_account_router")
router = APIRouter()
jwt_manager = JwtTokenManager()
security = HTTPBearer()

# Configuration
FINGERPRINT_COOKIE_NAME = "ww_fp"
FINGERPRINT_EXPIRE_DAYS = 30
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "false").lower() == "true"
FINGERPRINT_VALIDATION_ENABLED = os.getenv("JWT_FINGERPRINT_ENABLED", "true").lower() == "true"
SESSION_COOKIE_NAME = "ww_sid"
MAX_CONCURRENT_SESSIONS = 5
REFRESH_ROTATE_AFTER_DAYS = 7
REFRESH_SLIDING_WINDOW_DAYS = 14


# =============================================================================
# Dependency Injection
# =============================================================================

async def get_command_bus(request: Request):
    """Get command bus from application state"""
    if not hasattr(request.app.state, 'command_bus'):
        raise RuntimeError("Command bus not configured")
    return request.app.state.command_bus


async def get_query_bus(request: Request):
    """Get query bus from application state"""
    if not hasattr(request.app.state, 'query_bus'):
        raise RuntimeError("Query bus not configured")
    return request.app.state.query_bus


# =============================================================================
# Security Helpers
# =============================================================================

def _get_device_info(request: Request) -> Dict[str, str]:
    """Extract device information from request."""
    device_info = {
        "user_agent": request.headers.get("User-Agent", "Unknown"),
        "ip_address": request.client.host if request.client else "Unknown",
        "accept_language": request.headers.get("Accept-Language", "Unknown"),
    }

    # Simple user agent parsing
    user_agent = device_info["user_agent"]

    # Platform detection
    if "Windows" in user_agent:
        device_info["platform"] = "Windows"
    elif "Mac" in user_agent:
        device_info["platform"] = "macOS"
    elif "Linux" in user_agent:
        device_info["platform"] = "Linux"
    elif "Android" in user_agent:
        device_info["platform"] = "Android"
    elif "iPhone" in user_agent or "iPad" in user_agent:
        device_info["platform"] = "iOS"

    # Browser detection
    if "Chrome" in user_agent and "Edg" not in user_agent:
        device_info["browser"] = "Chrome"
    elif "Firefox" in user_agent:
        device_info["browser"] = "Firefox"
    elif "Safari" in user_agent and "Chrome" not in user_agent:
        device_info["browser"] = "Safari"
    elif "Edg" in user_agent:
        device_info["browser"] = "Edge"

    return device_info


def _generate_fingerprint() -> tuple[str, str]:
    """Generate a fingerprint and its hash."""
    fingerprint = secrets.token_urlsafe(32)
    hashed_fingerprint = hashlib.sha256(fingerprint.encode()).hexdigest()
    return fingerprint, hashed_fingerprint


def _validate_fingerprint(request: Request, token_fingerprint: Optional[str]) -> bool:
    """Validate token fingerprint against cookie."""
    # Skip validation in dev mode
    if not FINGERPRINT_VALIDATION_ENABLED:
        return True

    if not token_fingerprint:
        log.debug("Fingerprint validation failed: no token fingerprint")
        return False

    cookie_fingerprint = request.cookies.get(FINGERPRINT_COOKIE_NAME)
    if not cookie_fingerprint:
        log.debug("Fingerprint validation failed: no cookie fingerprint")
        return False

    # Use security utilities for validation
    expected = hashlib.sha256(cookie_fingerprint.encode()).hexdigest()
    is_valid = secrets.compare_digest(expected, token_fingerprint)

    if not is_valid:
        log.debug(f"Fingerprint validation failed: hash mismatch (expected={expected[:16]}..., token={token_fingerprint[:16]}...)")
    else:
        log.debug("Fingerprint validation successful")

    return is_valid


# =============================================================================
# AUTH ENDPOINTS WITH PROPER JWT TOKEN CREATION
# =============================================================================

@router.post("/login", response_model=AuthResponse)
async def login(
        payload: AuthRequest,
        request: Request,
        response: Response,
        command_bus=Depends(get_command_bus),
        query_bus=Depends(get_query_bus)
) -> AuthResponse:
    """
    User login with enhanced security using CQRS.
    """
    log.info("Login attempt for username=%s", payload.username)

    # Send authentication command
    cmd = AuthenticateUserCommand(
        username=payload.username,
        password=payload.password,
    )

    try:
        # Command returns (user_id, username, role)
        auth_result = await command_bus.send(cmd)
        user_id, username, role = auth_result
        user_id_str = str(user_id)

        # Check concurrent sessions using query
        check_sessions_query = CheckConcurrentSessionsQuery(
            user_id=user_id,
            max_sessions=MAX_CONCURRENT_SESSIONS
        )
        session_check_result = await query_bus.query(check_sessions_query)

        log.info(f"User {username} has {session_check_result['active_sessions']} active sessions before login")

        # Get device info
        device_info = _get_device_info(request)

        # Create session metadata using query
        create_session_query = CreateUserSessionQuery(
            user_id=user_id_str,
            username=username,
            role=role,
            device_info=device_info,
            remember_me=payload.remember_me
        )

        session_result: SessionCreationResult = await query_bus.query(create_session_query)

        # Generate cookie fingerprint for token binding (original mechanism)
        fingerprint, hashed_fingerprint = _generate_fingerprint()

        # Generate context fingerprint (IP-based) for theft detection
        context_fingerprint = extract_fingerprint_from_request(request) if JWT_FINGERPRINT_ENABLED else None

        # Create JWT tokens using the JWT manager
        # Family ID is used for refresh token rotation tracking
        token_family_id = secrets.token_urlsafe(32)

        # Build additional claims for access token
        access_claims = {
            "username": username,
            "role": role,
            "session_id": session_result.session_id,
            "fp": hashed_fingerprint,  # Cookie fingerprint hash for validation
            "family_id": token_family_id,  # Token family for tracking
        }

        # Add context fingerprint if enabled (IP-based theft detection)
        if context_fingerprint:
            access_claims["fgp"] = context_fingerprint

        # Create access token with session metadata
        access_token = jwt_manager.create_access_token(
            subject=user_id_str,
            additional_claims=access_claims,
            expires_delta=timedelta(minutes=15)  # 15 minutes for access token
        )

        # Build additional claims for refresh token
        refresh_claims = {
            "fp": hashed_fingerprint,  # Cookie fingerprint for validation
        }

        # Add context fingerprint to refresh token too
        if context_fingerprint:
            refresh_claims["fgp"] = context_fingerprint

        # Create refresh token with family tracking and fingerprint
        refresh_token = jwt_manager.create_refresh_token(
            subject=user_id_str,
            token_family=token_family_id,
            additional_claims=refresh_claims
        )

        # Store refresh token metadata in Redis via JWT manager
        # This is handled internally by create_refresh_token

        # Set secure cookies
        cookie_max_age = FINGERPRINT_EXPIRE_DAYS * 2 if payload.remember_me else FINGERPRINT_EXPIRE_DAYS

        # Fingerprint cookie (raw value for client to include in requests)
        response.set_cookie(
            key=FINGERPRINT_COOKIE_NAME,
            value=fingerprint,
            max_age=cookie_max_age * 24 * 60 * 60,
            secure=SECURE_COOKIES,
            httponly=True,
            samesite="strict",
            path="/",
        )

        # Session ID cookie
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_result.session_id,
            max_age=cookie_max_age * 24 * 60 * 60,
            secure=SECURE_COOKIES,
            httponly=True,
            samesite="strict",
            path="/",
        )

        # Log security event using query
        log_event_query = LogSecurityEventQuery(
            event_type="login_success",
            user_id=user_id_str,
            ip_address=device_info["ip_address"],
            user_agent=device_info["user_agent"],
            success=True,
            details={
                "session_id": session_result.session_id,
                "family_id": token_family_id
            }
        )
        await query_bus.query(log_event_query)

        log.info(f"Login successful for user={username}, session={session_result.session_id}")

        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=900,  # 15 minutes in seconds
            scope=None,
            requires_mfa=False,
            session_id=session_result.session_id,
            active_sessions=session_result.active_sessions_count,
        )

    except ValueError as exc:
        log.warning("Login failed for user=%s: %s", payload.username, exc)

        # Log failed attempt
        device_info = _get_device_info(request)
        log_event_query = LogSecurityEventQuery(
            event_type="login_failed",
            user_id=payload.username,  # Use username for failed attempts
            ip_address=device_info["ip_address"],
            user_agent=device_info["user_agent"],
            success=False,
            details={"reason": str(exc)}
        )
        await query_bus.query(log_event_query)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc) or "Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as exc:
        log.exception("Unexpected error during login")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service temporarily unavailable",
        ) from exc


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=StatusResponse)
async def register(
        payload: RegisterRequest,
        request: Request,
        command_bus=Depends(get_command_bus),
        query_bus=Depends(get_query_bus)
) -> StatusResponse:
    """
    User registration using command bus.
    """
    log.info("Registration attempt username=%s email=%s", payload.username, payload.email)

    cmd = CreateUserAccountCommand(
        user_id=uuid.uuid4(),
        username=payload.username,
        email=payload.email,
        password=payload.password,
        secret=payload.secret,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )

    try:
        await command_bus.send(cmd)

        # Log security event
        device_info = _get_device_info(request)
        log_event_query = LogSecurityEventQuery(
            event_type="account_created",
            user_id=str(cmd.user_id),
            ip_address=device_info["ip_address"],
            user_agent=device_info["user_agent"],
            success=True,
            details={"username": payload.username}
        )
        await query_bus.query(log_event_query)

        return StatusResponse(status="success", message="User registered successfully")
    except ValueError as exc:
        log.warning("Registration failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/me", response_model=UserProfileResponse)
async def get_me(
        current_user: Annotated[dict, Depends(get_current_user)],
        request: Request,
        query_bus=Depends(get_query_bus)
) -> UserProfileResponse:
    """
    Get current user profile using query bus.
    """
    try:
        user_uuid = current_user["user_id"]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id") from exc

    # Query user profile
    profile_query = GetUserProfileQuery(user_id=user_uuid)
    profile_data = await query_bus.query(profile_query)

    if not profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get active sessions count
    session_count_query = GetActiveSessionCountQuery(user_id=user_uuid)
    session_count_result = await query_bus.query(session_count_query)

    return UserProfileResponse(
        user_id=str(profile_data.id),
        username=profile_data.username,
        email=profile_data.email,
        role=profile_data.role,
        is_active=profile_data.is_active,
        email_verified=profile_data.email_verified,
        mfa_enabled=profile_data.mfa_enabled,
        created_at=profile_data.created_at,
        last_login=profile_data.last_login,
        last_password_change=profile_data.last_password_change,
        security_alerts_enabled=profile_data.security_alerts_enabled,
        active_sessions_count=session_count_result['active_sessions'],
        preferences=profile_data.preferences,
        metadata=profile_data.metadata,
        # WellWon Platform fields
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        avatar_url=profile_data.avatar_url,
        bio=profile_data.bio,
        phone=profile_data.phone,
        user_type=profile_data.user_type,
        user_number=profile_data.user_number,
        is_developer=profile_data.is_developer,
    )


@router.patch("/profile", response_model=UserProfileResponse)
async def update_profile(
        payload: UpdateProfileRequest,
        current_user: Annotated[dict, Depends(get_current_user)],
        request: Request,
        command_bus=Depends(get_command_bus),
        query_bus=Depends(get_query_bus)
) -> UserProfileResponse:
    """
    Update user profile (WellWon integrated).
    """
    try:
        user_uuid = current_user["user_id"]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id") from exc

    # Update profile fields using UpdateUserProfileCommand
    update_fields = payload.model_dump(exclude_unset=True)
    if update_fields:
        from app.user_account.commands import UpdateUserProfileCommand

        command = UpdateUserProfileCommand(
            user_id=user_uuid,
            first_name=payload.first_name,
            last_name=payload.last_name,
            avatar_url=payload.avatar_url,
            bio=payload.bio,
            phone=payload.phone,
            user_type=payload.user_type,
            is_developer=payload.is_developer
        )

        await command_bus.send(command)
        log.info(f"Profile updated for user {user_uuid}, fields: {list(update_fields.keys())}")

    # Return current profile
    return await get_me(current_user, request, query_bus)


@router.post("/verify-password", response_model=StatusResponse)
async def verify_password(
        payload: VerifyPasswordPayload,
        current_user: Annotated[dict, Depends(get_current_user)],
        query_bus=Depends(get_query_bus)
) -> StatusResponse:
    """
    Verify user password using query bus.
    """
    user_uuid = current_user["user_id"]

    query = ValidateUserCredentialsQuery(
        user_id=user_uuid,
        password=payload.password
    )

    result = await query_bus.query(query)

    if not result['valid']:
        log.warning("Failed password verification for user=%s", current_user["user_id"])
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    return StatusResponse(status="success", message="Password verified")


@router.post("/change-password", response_model=StatusResponse)
async def change_password(
        payload: ChangePasswordPayload,
        current_user: Annotated[dict, Depends(get_current_user)],
        request: Request,
        command_bus=Depends(get_command_bus),
        query_bus=Depends(get_query_bus)
) -> StatusResponse:
    """
    Change user password using command bus.
    """
    user_uuid = current_user["user_id"]

    # First verify old password
    validate_query = ValidateUserCredentialsQuery(
        user_id=user_uuid,
        password=payload.old_password
    )

    validation_result = await query_bus.query(validate_query)
    if not validation_result['valid']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Current password is incorrect")

    # Change password
    cmd = ChangeUserPasswordCommand(
        user_id=user_uuid,
        new_password=payload.new_password,
    )
    await command_bus.send(cmd)

    # Revoke all sessions if requested
    if payload.revoke_all_sessions:
        # Use JWT manager to revoke all refresh tokens
        await jwt_manager.revoke_all_refresh_tokens(current_user["user_id"])

        # Also invalidate session metadata
        invalidate_query = InvalidateAllUserSessionsQuery(user_id=user_uuid)
        await query_bus.query(invalidate_query)
        log.info(f"Revoked all sessions for user {current_user["user_id"]} after password change")

    # Log security event
    device_info = _get_device_info(request)
    log_event_query = LogSecurityEventQuery(
        event_type="password_changed",
        user_id=str(current_user["user_id"]),
        ip_address=device_info["ip_address"],
        user_agent=device_info["user_agent"],
        success=True,
        details={"sessions_revoked": payload.revoke_all_sessions}
    )
    await query_bus.query(log_event_query)

    log.info("Password changed for user=%s", current_user["user_id"])
    return StatusResponse(status="success", message="Password updated successfully")


@router.post("/forgot-password", response_model=StatusResponse)
async def forgot_password(
        payload: PasswordResetRequest,
        request: Request,
        command_bus=Depends(get_command_bus),
        query_bus=Depends(get_query_bus)
) -> StatusResponse:
    """
    Reset password with secret using command bus.
    """
    cmd = ResetUserPasswordWithSecretCommand(
        username=payload.username,
        secret=payload.secret,
        new_password=payload.new_password,
    )

    try:
        await command_bus.send(cmd)

        # Log security event
        device_info = _get_device_info(request)
        log_event_query = LogSecurityEventQuery(
            event_type="password_reset",
            user_id=payload.username,
            ip_address=device_info["ip_address"],
            user_agent=device_info["user_agent"],
            success=True,
            details={}
        )
        await query_bus.query(log_event_query)

        return StatusResponse(status="success", message="Password has been reset")
    except ValueError as e:
        log.warning("Password reset failed for username=%s: %s", payload.username, e)
        return StatusResponse(status="success", message="If the account exists, password has been reset")


@router.post("/logout", response_model=StatusResponse)
async def logout_user(
        current_user: Annotated[dict, Depends(get_current_user)],
        request: Request,
        response: Response,
        query_bus=Depends(get_query_bus)
) -> StatusResponse:
    """
    Logout current session using queries.
    """
    # Extract session info from token
    auth_header = request.headers.get("Authorization", "")
    session_id = None
    jti = None

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt_manager.decode_token_payload(token)
            session_id = payload.get("session_id")
            jti = payload.get("jti")

            # Blacklist the access token
            if jti:
                expires_at = datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc)
                blacklist_query = BlacklistTokenQuery(jti=jti, expires_at=expires_at)
                await query_bus.query(blacklist_query)
        except Exception as e:
            log.warning(f"Error processing token during logout: {e}")

    # Get session from cookie if not in token
    if not session_id:
        session_id = request.cookies.get(SESSION_COOKIE_NAME)

    # Invalidate the current session
    if session_id:
        invalidate_query = InvalidateUserSessionQuery(
            user_id=current_user["user_id"],
            session_id=session_id,
            reason="User logout"
        )
        await query_bus.query(invalidate_query)

    # Clear cookies
    response.delete_cookie(
        key=FINGERPRINT_COOKIE_NAME,
        path="/",
        secure=SECURE_COOKIES,
        httponly=True,
        samesite="strict",
    )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=SECURE_COOKIES,
        httponly=True,
        samesite="strict",
    )

    # Log security event
    device_info = _get_device_info(request)
    log_event_query = LogSecurityEventQuery(
        event_type="logout",
        user_id=str(current_user["user_id"]),
        ip_address=device_info["ip_address"],
        user_agent=device_info["user_agent"],
        success=True,
        details={"session_id": session_id}
    )
    await query_bus.query(log_event_query)

    # Emit UserLoggedOut event for streaming lifecycle management
    try:
        event_bus = request.app.state.event_bus
        if event_bus:
            await event_bus.publish("transport.user-account-events", {
                "event_type": "UserLoggedOut",
                "user_id": str(current_user["user_id"]),
                "session_id": session_id,
                "logout_at": datetime.now(timezone.utc).isoformat()
            })
            log.debug(f"UserLoggedOut event emitted for user {current_user["user_id"]}")
    except Exception as e:
        # Log error but don't fail logout operation
        log.error(f"Failed to emit UserLoggedOut event for user {current_user["user_id"]}: {e}")

    log.info(f"User logged out: {current_user["user_id"]}")
    return StatusResponse(status="success", message="Logged out successfully")


@router.post("/logout-all", response_model=StatusResponse)
async def logout_all_sessions(
        current_user: Annotated[dict, Depends(get_current_user)],
        response: Response,
        request: Request,
        query_bus=Depends(get_query_bus)
) -> StatusResponse:
    """
    Logout from all devices/sessions using queries.
    """
    # Revoke all refresh tokens via JWT manager
    await jwt_manager.revoke_all_refresh_tokens(current_user["user_id"])

    # Invalidate all session metadata
    invalidate_query = InvalidateAllUserSessionsQuery(user_id=current_user["user_id"])
    result = await query_bus.query(invalidate_query)

    # Clear cookies from current session
    response.delete_cookie(
        key=FINGERPRINT_COOKIE_NAME,
        path="/",
        secure=SECURE_COOKIES,
        httponly=True,
        samesite="strict",
    )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=SECURE_COOKIES,
        httponly=True,
        samesite="strict",
    )

    # Log security event
    device_info = _get_device_info(request)
    log_event_query = LogSecurityEventQuery(
        event_type="logout_all",
        user_id=str(current_user["user_id"]),
        ip_address=device_info["ip_address"],
        user_agent=device_info["user_agent"],
        success=True,
        details={"sessions_invalidated": result.get('invalidated_count', 0)}
    )
    await query_bus.query(log_event_query)

    log.info(f"All sessions terminated for user: {current_user["user_id"]}")
    return StatusResponse(status="success", message="Logged out from all devices")


@router.get("/sessions", response_model=ActiveSessionsResponse)
async def get_active_sessions(
        current_user: Annotated[dict, Depends(get_current_user)],
        request: Request,
        query_bus=Depends(get_query_bus)
) -> ActiveSessionsResponse:
    """
    Get list of active sessions using query bus.
    """
    user_uuid = current_user["user_id"]

    # Query active sessions
    sessions_query = GetUserActiveSessionsQuery(user_id=user_uuid)
    sessions_data = await query_bus.query(sessions_query)

    # Get current session from cookie
    current_session = request.cookies.get(SESSION_COOKIE_NAME)

    # Map sessions to response format
    active_sessions = []
    for session in sessions_data:
        device_info = DeviceInfo(
            user_agent=session.device_info.get("user_agent", "Unknown"),
            ip_address=session.device_info.get("ip_address", "Unknown"),
            accept_language=session.device_info.get("accept_language", "Unknown"),
            platform=session.device_info.get("platform"),
            browser=session.device_info.get("browser"),
        )

        session_info = SessionInfo(
            session_id=session.session_id,
            family_id=session.family_id,
            created_at=session.created_at,
            last_used=session.last_used,
            expires_at=session.expires_at,
            device_info=device_info,
            is_current=session.session_id == current_session,
            rotation_count=session.rotation_count,
        )
        active_sessions.append(session_info)

    # Sort by last used
    active_sessions.sort(key=lambda x: x.last_used, reverse=True)

    return ActiveSessionsResponse(
        sessions=active_sessions,
        total_count=len(active_sessions),
        max_allowed=MAX_CONCURRENT_SESSIONS,
    )


@router.post("/sessions/{session_id}/terminate", response_model=StatusResponse)
async def terminate_session(
        session_id: str,
        current_user: Annotated[dict, Depends(get_current_user)],
        request: Request,
        query_bus=Depends(get_query_bus)
) -> StatusResponse:
    """
    Terminate a specific session using queries.
    """
    # Invalidate the specific session
    invalidate_query = InvalidateUserSessionQuery(
        user_id=current_user["user_id"],
        session_id=session_id,
        reason="User terminated session"
    )
    result = await query_bus.query(invalidate_query)

    if not result.get('success'):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already terminated"
        )

    log.info(f"Session {session_id} terminated for user {current_user["user_id"]}")
    return StatusResponse(status="success", message="Session terminated successfully")


@router.post("/delete", response_model=StatusResponse)
async def delete_account(
        payload: DeleteAccountPayload,
        current_user: Annotated[dict, Depends(get_current_user)],
        response: Response,
        request: Request,
        command_bus=Depends(get_command_bus),
        query_bus=Depends(get_query_bus)
) -> StatusResponse:
    """
    Delete user account using command bus.
    """
    user_uuid = current_user["user_id"]

    # Verify password
    validate_query = ValidateUserCredentialsQuery(
        user_id=user_uuid,
        password=payload.password
    )

    validation_result = await query_bus.query(validate_query)
    if not validation_result['valid']:
        log.warning("Failed account deletion attempt for user=%s", current_user["user_id"])
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    # Revoke all refresh tokens
    await jwt_manager.revoke_all_refresh_tokens(current_user["user_id"])

    # Clear all sessions
    invalidate_query = InvalidateAllUserSessionsQuery(user_id=user_uuid)
    await query_bus.query(invalidate_query)

    # Clear auth cookies
    response.delete_cookie(
        key=FINGERPRINT_COOKIE_NAME,
        path="/",
        secure=SECURE_COOKIES,
        httponly=True,
        samesite="strict",
    )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=SECURE_COOKIES,
        httponly=True,
        samesite="strict",
    )

    # Execute the delete command
    delete_cmd = DeleteUserAccountCommand(user_id=user_uuid)
    await command_bus.send(delete_cmd)

    # Log security event
    device_info = _get_device_info(request)
    log_event_query = LogSecurityEventQuery(
        event_type="account_deleted",
        user_id=str(current_user["user_id"]),
        ip_address=device_info["ip_address"],
        user_agent=device_info["user_agent"],
        success=True,
        details={"reason": payload.reason, "feedback": payload.feedback}
    )
    await query_bus.query(log_event_query)

    log.info("Account deletion initiated for user=%s", current_user["user_id"])
    return StatusResponse(
        status="accepted",
        message="Account scheduled for deletion. You have 30 days to reactivate.",
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(
        body: RefreshTokenRequest,
        request: Request,
        response: Response,
        query_bus=Depends(get_query_bus)
) -> RefreshTokenResponse:
    """
    Refresh access token using JWT manager's built-in rotation.
    """
    try:
        # Validate fingerprint before refresh
        refresh_payload = jwt_manager.decode_token_payload(body.refresh_token)
        if refresh_payload and not _validate_fingerprint(request, refresh_payload.get("fp")):
            log.warning("Fingerprint mismatch for refresh token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token binding",
            )

        # Use JWT manager's refresh token rotation
        new_access_token, new_refresh_token = await jwt_manager.refresh_tokens(body.refresh_token)

        # Log security event
        device_info = _get_device_info(request)
        user_id = refresh_payload.get("sub") if refresh_payload else None

        if user_id:
            log_event_query = LogSecurityEventQuery(
                event_type="token_refreshed",
                user_id=user_id,
                ip_address=device_info["ip_address"],
                user_agent=device_info["user_agent"],
                success=True,
                details={"rotated": bool(new_refresh_token)}
            )
            await query_bus.query(log_event_query)

        return RefreshTokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="Bearer",
            expires_in=900,  # 15 minutes
            token_rotated=bool(new_refresh_token),
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# =============================================================================
# TELEGRAM INTEGRATION ENDPOINTS
# =============================================================================

@router.get("/profiles/with-telegram", response_model=list[ProfileWithTelegramResponse])
async def get_profiles_with_telegram(
        current_user: Annotated[dict, Depends(get_current_user)],
) -> list[ProfileWithTelegramResponse]:
    """
    Get all user profiles for mentions feature.

    Returns users with their telegram_user_id for @mention functionality in chat.
    Users with linked Telegram accounts appear first.
    """
    from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo

    try:
        profiles = await UserAccountReadRepo.get_profiles_with_telegram()

        return [
            ProfileWithTelegramResponse(
                user_id=p["user_id"],
                first_name=p["first_name"],
                last_name=p["last_name"],
                avatar_url=p["avatar_url"],
                role_label=p["role_label"],
                telegram_user_id=p["telegram_user_id"],
            )
            for p in profiles
        ]

    except Exception as e:
        log.error(f"Failed to get profiles with telegram: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profiles"
        )


@router.post("/link-telegram", response_model=StatusResponse)
async def link_telegram_account(
        payload: LinkTelegramRequest,
        current_user: Annotated[dict, Depends(get_current_user)],
) -> StatusResponse:
    """
    Link a Telegram user ID to the current WellWon account.

    This enables @mentions to notify users via Telegram.
    """
    from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo

    try:
        user_uuid = current_user["user_id"]
        success = await UserAccountReadRepo.update_telegram_user_id(
            user_id=user_uuid,
            telegram_user_id=payload.telegram_user_id
        )

        if success:
            log.info(f"User {current_user["user_id"]} linked to Telegram user {payload.telegram_user_id}")
            return StatusResponse(
                status="success",
                message="Telegram account linked successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to link Telegram account"
            )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID"
        ) from exc
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to link Telegram account: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to link Telegram account"
        )


# =============================================================================
# EOF
# =============================================================================