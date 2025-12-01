# app/user_account/query_handlers/session_query_handlers.py
# =============================================================================
# File: app/user_account/query_handlers/session_query_handlers.py
# Description: Query handlers for session management - CQRS COMPLIANT
#
# All handlers inherit from BaseQueryHandler for consistent patterns.
# =============================================================================

import logging
import uuid
import json
from typing import TYPE_CHECKING, Any
from datetime import datetime, timezone, timedelta

from app.infra.cqrs.query_bus import IQueryHandler
from app.infra.cqrs.cqrs_decorators import query_handler, readonly_query
from app.common.base.base_query_handler import BaseQueryHandler
from app.user_account.queries import (
    GetUserActiveSessionsQuery,
    CreateUserSessionQuery,
    InvalidateUserSessionQuery,
    InvalidateAllUserSessionsQuery,
    GetActiveSessionCountQuery,
    CheckConcurrentSessionsQuery,
    GetRefreshTokenFamilyQuery,
    UpdateRefreshTokenFamilyQuery,
    StoreRefreshTokenFamilyQuery,
    BlacklistTokenQuery,
    CheckTokenBlacklistQuery,
    DetectTokenReuseQuery,
    LogSecurityEventQuery,
    UserSession,
    SessionCreationResult,
    RefreshTokenFamily,
)

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies


# =============================================================================
# Session Management Query Handlers - CQRS Compliant
# =============================================================================

@query_handler(GetUserActiveSessionsQuery)
class GetUserActiveSessionsQueryHandler(BaseQueryHandler[GetUserActiveSessionsQuery, list[UserSession]]):
    """Handler for getting user's active sessions - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: GetUserActiveSessionsQuery) -> list[UserSession]:
        """Get all active sessions from cache"""
        sessions = []
        now = datetime.now(timezone.utc)

        # Get all tokens to match with sessions
        user_tokens_key = self.cache_manager._make_key('auth', 'user', 'tokens', str(query.user_id))
        tokens = await self.cache_manager.get_json(user_tokens_key) or []

        # For each token, get its data
        for jti in tokens:
            token_key = self.cache_manager._make_key('auth', 'refresh', 'token', str(query.user_id), jti)
            token_data = await self.cache_manager.get_json(token_key)

            if not token_data:
                continue

            if not token_data.get('active', False) and not query.include_expired:
                continue

            expires_at = datetime.fromtimestamp(token_data.get('expires_at', 0), tz=timezone.utc)

            if expires_at <= now and not query.include_expired:
                continue

            # Create session info from token data
            sessions.append(UserSession(
                session_id=f"sess_{jti[:8]}",  # Derive session ID from JTI
                family_id=token_data.get('family', ''),
                created_at=datetime.fromtimestamp(token_data.get('issued_at', 0), tz=timezone.utc),
                last_used=datetime.fromtimestamp(token_data.get('issued_at', 0), tz=timezone.utc),
                expires_at=expires_at,
                device_info={},  # Would need to be stored separately
                rotation_count=token_data.get('version', 1) - 1,
                is_current=False  # Will be set by the caller
            ))

        # Sort by last used (most recent first)
        sessions.sort(key=lambda x: x.last_used, reverse=True)

        return sessions


@query_handler(CreateUserSessionQuery)
class CreateUserSessionQueryHandler(BaseQueryHandler[CreateUserSessionQuery, SessionCreationResult]):
    """Handler for storing session metadata - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: CreateUserSessionQuery) -> SessionCreationResult:
        """Store session metadata that complements JWT tokens"""
        # Generate session ID
        session_id = query.session_id or f"sess_{uuid.uuid4().hex}"

        # Store session metadata
        session_key = self.cache_manager._make_key('auth', 'session', 'meta', str(query.user_id), session_id)
        session_data = {
            "session_id": session_id,
            "user_id": str(query.user_id),
            "device_info": query.device_info,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "username": query.username,
            "role": query.role,
            "remember_me": query.remember_me
        }

        # Store with appropriate TTL
        ttl = 30 * 24 * 3600 if query.remember_me else 7 * 24 * 3600  # 30 or 7 days
        await self.cache_manager.set_json(session_key, session_data, ttl)

        # Get current active sessions count from JWT tokens
        user_tokens_key = self.cache_manager._make_key('auth', 'user', 'tokens', str(query.user_id))
        tokens = await self.cache_manager.get_json(user_tokens_key) or []

        # Return metadata (tokens will be created by JWT module)
        return SessionCreationResult(
            session_id=session_id,
            family_id="",  # Not used with JWT module
            access_token="",  # Will be created by JWT module
            refresh_token="",  # Will be created by JWT module
            expires_in=3600,
            active_sessions_count=len(tokens) + 1,  # +1 for the new session
            fingerprint="",  # Will be created in router
            hashed_fingerprint=""  # Will be created in router
        )


@readonly_query(InvalidateUserSessionQuery)
class InvalidateUserSessionQueryHandler(BaseQueryHandler[InvalidateUserSessionQuery, dict[str, Any]]):
    """Handler for invalidating specific session - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: InvalidateUserSessionQuery) -> dict[str, Any]:
        """Invalidate specific user session"""
        # Delete session metadata
        session_key = self.cache_manager._make_key('auth', 'session', 'meta', str(query.user_id), query.session_id)
        deleted = await self.cache_manager.delete(session_key)

        self.log.info(f"Session {query.session_id} metadata deleted for user {query.user_id}, reason: {query.reason}")

        return {
            'success': deleted,
            'user_id': str(query.user_id),
            'session_id': query.session_id,
            'reason': query.reason
        }


@readonly_query(InvalidateAllUserSessionsQuery)
class InvalidateAllUserSessionsQueryHandler(BaseQueryHandler[InvalidateAllUserSessionsQuery, dict[str, Any]]):
    """Handler for invalidating all user sessions - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: InvalidateAllUserSessionsQuery) -> dict[str, Any]:
        """Invalidate all sessions for user"""
        # Delete all session metadata
        pattern = self.cache_manager._make_key('auth', 'session', 'meta', str(query.user_id), '*')
        deleted_meta = await self.cache_manager.delete_pattern(pattern)

        # Get token count before clearing
        user_tokens_key = self.cache_manager._make_key('auth', 'user', 'tokens', str(query.user_id))
        tokens = await self.cache_manager.get_json(user_tokens_key) or []
        token_count = len(tokens)

        # Clear all tokens
        await self.cache_manager.delete(user_tokens_key)

        # Clear individual token data
        for jti in tokens:
            if query.except_current and jti == query.except_current:
                continue
            token_key = self.cache_manager._make_key('auth', 'refresh', 'token', str(query.user_id), jti)
            await self.cache_manager.delete(token_key)

        self.log.info(f"Invalidated {token_count} sessions for user {query.user_id}")

        return {
            'success': True,
            'user_id': str(query.user_id),
            'invalidated_count': token_count,
            'kept_session': query.except_current
        }


@query_handler(GetActiveSessionCountQuery)
class GetActiveSessionCountQueryHandler(BaseQueryHandler[GetActiveSessionCountQuery, dict[str, Any]]):
    """Handler for getting active session count - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: GetActiveSessionCountQuery) -> dict[str, Any]:
        """Get count of active sessions from JWT tokens"""
        # JWT module stores active tokens in this key
        user_tokens_key = self.cache_manager._make_key('auth', 'user', 'tokens', str(query.user_id))
        tokens = await self.cache_manager.get_json(user_tokens_key) or []

        # Count non-expired tokens
        active_count = 0
        now = datetime.now(timezone.utc)

        for jti in tokens:
            # Check if token data exists and is active
            token_key = self.cache_manager._make_key('auth', 'refresh', 'token', str(query.user_id), jti)
            token_data = await self.cache_manager.get_json(token_key)

            if token_data and token_data.get('active', False):
                expires_at = token_data.get('expires_at', 0)
                if isinstance(expires_at, (int, float)) and expires_at > now.timestamp():
                    active_count += 1

        return {
            'user_id': str(query.user_id),
            'active_sessions': active_count,
            'total_sessions': len(tokens)
        }


@query_handler(CheckConcurrentSessionsQuery)
class CheckConcurrentSessionsQueryHandler(BaseQueryHandler[CheckConcurrentSessionsQuery, dict[str, Any]]):
    """Handler for checking concurrent sessions - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.query_bus = deps.query_bus

    async def handle(self, query: CheckConcurrentSessionsQuery) -> dict[str, Any]:
        """Check and enforce concurrent session limits"""
        # Use query bus to get session count
        count_result = await self.query_bus.query(
            GetActiveSessionCountQuery(user_id=query.user_id)
        )

        active_sessions = count_result['active_sessions']

        return {
            'user_id': str(query.user_id),
            'active_sessions': active_sessions,
            'max_sessions': query.max_sessions,
            'limit_exceeded': active_sessions >= query.max_sessions,
            'sessions_to_remove': max(0, active_sessions - query.max_sessions + 1)
        }


@readonly_query(GetRefreshTokenFamilyQuery)
class GetRefreshTokenFamilyQueryHandler(BaseQueryHandler[GetRefreshTokenFamilyQuery, RefreshTokenFamily | None]):
    """Handler for getting refresh token family - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: GetRefreshTokenFamilyQuery) -> RefreshTokenFamily | None:
        """Get refresh token family data"""
        # In new JWT structure, this query might need redesign
        self.log.warning("GetRefreshTokenFamilyQuery not fully implemented for new JWT structure")
        return None


@readonly_query(UpdateRefreshTokenFamilyQuery)
class UpdateRefreshTokenFamilyQueryHandler(BaseQueryHandler[UpdateRefreshTokenFamilyQuery, dict[str, Any]]):
    """Handler for updating refresh token family - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: UpdateRefreshTokenFamilyQuery) -> dict[str, Any]:
        """Update refresh token family after rotation"""
        # This is now handled by JWT module internally
        self.log.warning("UpdateRefreshTokenFamilyQuery should be handled by JWT module")
        return {
            'success': False,
            'reason': 'Operation moved to JWT module',
            'family_id': query.family_id
        }


@readonly_query(StoreRefreshTokenFamilyQuery)
class StoreRefreshTokenFamilyQueryHandler(BaseQueryHandler[StoreRefreshTokenFamilyQuery, dict[str, Any]]):
    """Handler for storing refresh token family - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: StoreRefreshTokenFamilyQuery) -> dict[str, Any]:
        """Store refresh token family data"""
        # This is now handled by JWT module when creating tokens
        self.log.warning("StoreRefreshTokenFamilyQuery should be handled by JWT module")
        return {
            'success': False,
            'reason': 'Operation moved to JWT module',
            'family_id': query.family_id
        }


@query_handler(BlacklistTokenQuery)
class BlacklistTokenQueryHandler(BaseQueryHandler[BlacklistTokenQuery, dict[str, Any]]):
    """Handler for blacklisting tokens - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: BlacklistTokenQuery) -> dict[str, Any]:
        """Add token to blacklist"""
        blacklist_key = self.cache_manager._make_key('auth', 'blacklist', query.jti)

        # Calculate TTL (token expiry + buffer)
        ttl = int((query.expires_at - datetime.now(timezone.utc)).total_seconds()) + 3600  # +1 hour buffer

        if ttl > 0:
            await self.cache_manager.set(blacklist_key, "1", ttl)
            return {
                'success': True,
                'jti': query.jti,
                'blacklisted': True
            }

        return {
            'success': False,
            'jti': query.jti,
            'blacklisted': False,
            'reason': 'Token already expired'
        }


@query_handler(CheckTokenBlacklistQuery)
class CheckTokenBlacklistQueryHandler(BaseQueryHandler[CheckTokenBlacklistQuery, dict[str, Any]]):
    """Handler for checking token blacklist - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: CheckTokenBlacklistQuery) -> dict[str, Any]:
        """Check if token is blacklisted"""
        blacklist_key = self.cache_manager._make_key('auth', 'blacklist', query.jti)
        is_blacklisted = await self.cache_manager.exists(blacklist_key)

        return {
            'jti': query.jti,
            'is_blacklisted': is_blacklisted
        }


@readonly_query(DetectTokenReuseQuery)
class DetectTokenReuseQueryHandler(BaseQueryHandler[DetectTokenReuseQuery, dict[str, Any]]):
    """Handler for detecting token reuse - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: DetectTokenReuseQuery) -> dict[str, Any]:
        """Detect token reuse attack"""
        reuse_key = self.cache_manager._make_key('auth', 'token', 'reuse', query.jti)

        # Check if token was recently used
        recently_used = await self.cache_manager.exists(reuse_key)

        if not recently_used:
            # Mark token as used with short TTL
            await self.cache_manager.set(reuse_key, "1", query.reuse_window_minutes * 60)
            return {
                'jti': query.jti,
                'reuse_detected': False
            }

        # Token reuse detected!
        self.log.error(f"TOKEN REUSE DETECTED for JTI: {query.jti}")
        return {
            'jti': query.jti,
            'reuse_detected': True
        }


@query_handler(LogSecurityEventQuery)
class LogSecurityEventQueryHandler(BaseQueryHandler[LogSecurityEventQuery, dict[str, Any]]):
    """Handler for logging security events - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: LogSecurityEventQuery) -> dict[str, Any]:
        """Log security event to cache"""
        # Store in cache for recent events
        event_id = f"evt_{uuid.uuid4().hex}"
        event_key = self.cache_manager._make_key('auth', 'security', 'event', event_id)

        event_data = {
            'event_id': event_id,
            'event_type': query.event_type,
            'user_id': query.user_id,
            'ip_address': query.ip_address,
            'user_agent': query.user_agent,
            'success': query.success,
            'details': query.details or {},
            'session_id': query.session_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Store with 7 day TTL
        await self.cache_manager.set_json(event_key, event_data, 7 * 24 * 3600)

        # Also add to user's event list
        user_events_key = self.cache_manager._make_key('auth', 'security', 'events', 'user', query.user_id)
        user_events = await self.cache_manager.get_json(user_events_key) or []

        # Keep last 100 events
        user_events.insert(0, event_id)
        user_events = user_events[:100]

        await self.cache_manager.set_json(user_events_key, user_events, 7 * 24 * 3600)

        return {
            'success': True,
            'event_id': event_id,
            'logged_at': event_data['timestamp']
        }

# =============================================================================
# EOF
# =============================================================================