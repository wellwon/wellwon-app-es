# app/user_account/query_handlers/auth_query_handlers.py
# =============================================================================
# File: app/user_account/query_handlers/auth_query_handlers.py
# Description: Query handlers for authentication operations - CQRS COMPLIANT
#
# All handlers inherit from BaseQueryHandler for consistent patterns.
# =============================================================================

import logging
import json
from typing import TYPE_CHECKING, Any
from datetime import timezone, datetime

from app.infra.cqrs.query_bus import IQueryHandler
from app.infra.cqrs.cqrs_decorators import query_handler, readonly_query, cached_query_handler, readonly_query
from app.common.base.base_query_handler import BaseQueryHandler
from app.user_account.queries import (
    ValidateUserCredentialsQuery,
    HashPasswordQuery,
    VerifyPasswordHashQuery,
    GetUserAuthDetailsQuery,
    GetUserSecuritySettingsQuery,
    GetUserAuthHistoryQuery,
    ValidateUserSessionQuery,
)
from app.common.exceptions.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies


# =============================================================================
# Authentication Query Handlers - CQRS Compliant
# =============================================================================

@query_handler(ValidateUserCredentialsQuery)
class ValidateUserCredentialsQueryHandler(BaseQueryHandler[ValidateUserCredentialsQuery, dict[str, Any]]):
    """Handler for validating user credentials - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo
        self.user_auth_service = deps.user_auth_service

    async def handle(self, query: ValidateUserCredentialsQuery) -> dict[str, Any]:
        """Validate user password"""
        # Same-domain query for profile
        profile = await self.user_repo.get_user_profile_by_user_id(query.user_id)

        if not profile:
            return {
                'valid': False,
                'reason': 'User not found',
                'user_id': str(query.user_id)
            }

        # Same-domain query for auth details
        auth_details = await self.user_repo.get_user_auth_details_by_username(profile.username)

        if not auth_details:
            return {
                'valid': False,
                'reason': 'Authentication details not found',
                'user_id': str(query.user_id),
                'username': profile.username
            }

        # Use service for crypto operations (not a query)
        is_valid = self.user_auth_service.verify_user_password(
            query.password,
            auth_details.hashed_password
        )

        return {
            'valid': is_valid,
            'user_id': str(query.user_id),
            'username': profile.username,
            'email': profile.email,
            'role': profile.role
        }


@query_handler(HashPasswordQuery)
class HashPasswordQueryHandler(BaseQueryHandler[HashPasswordQuery, str]):
    """Handler for hashing passwords - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_auth_service = deps.user_auth_service

    async def handle(self, query: HashPasswordQuery) -> str:
        """Hash the password using bcrypt"""
        return self.user_auth_service.hash_user_password(query.password)


@query_handler(VerifyPasswordHashQuery)
class VerifyPasswordHashQueryHandler(BaseQueryHandler[VerifyPasswordHashQuery, bool]):
    """Handler for verifying password hashes - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_auth_service = deps.user_auth_service

    async def handle(self, query: VerifyPasswordHashQuery) -> bool:
        """Verify password against hash"""
        return self.user_auth_service.verify_user_password(
            query.plain_password,
            query.hashed_password
        )


@readonly_query(GetUserAuthDetailsQuery)
class GetUserAuthDetailsQueryHandler(BaseQueryHandler[GetUserAuthDetailsQuery, dict[str, Any]]):
    """Handler for getting user auth details - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo
        self.cache_manager = deps.cache_manager

    async def handle(self, query: GetUserAuthDetailsQuery) -> dict[str, Any]:
        """Get user authentication details"""
        profile = await self.user_repo.get_user_profile_by_user_id(query.user_id)

        profile = self.handle_not_found(
            resource=profile,
            resource_type="User",
            resource_id=query.user_id
        )

        auth_details = {
            'user_id': str(query.user_id),
            'username': profile.username,
            'email': profile.email,
            'is_active': profile.is_active,
            'email_verified': getattr(profile, 'email_verified', False),
            'mfa_enabled': getattr(profile, 'mfa_enabled', False),
            'role': profile.role,
            'created_at': profile.created_at.isoformat(),
            'last_login': profile.last_login.isoformat() if profile.last_login else None
        }

        # Get auth data if password hash is requested
        if query.include_password_hash:
            auth_data = await self.user_repo.get_user_auth_details_by_username(profile.username)
            if auth_data:
                auth_details['password_hash'] = auth_data.hashed_password
                auth_details['password_updated_at'] = getattr(auth_data, 'last_password_change', None)

        # Get session info if requested
        if query.include_session_info:
            # Get active session count from cache
            session_key = self.cache_manager._make_key('auth', 'user', 'sessions', str(query.user_id))
            session_families = await self.cache_manager.get_json(session_key) or []
            auth_details['active_sessions'] = len(session_families)

            # Get last session activity
            if session_families:
                auth_details['last_session_activity'] = None  # Would need to check each session

        return auth_details


@cached_query_handler(GetUserSecuritySettingsQuery, ttl=300)
class GetUserSecuritySettingsQueryHandler(BaseQueryHandler[GetUserSecuritySettingsQuery, dict[str, Any]]):
    """Handler for getting user security settings - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetUserSecuritySettingsQuery) -> dict[str, Any]:
        """Get security settings"""
        profile = await self.user_repo.get_user_profile_by_user_id(query.user_id)

        profile = self.handle_not_found(
            resource=profile,
            resource_type="User",
            resource_id=query.user_id
        )

        return {
            'user_id': str(query.user_id),
            'mfa_enabled': getattr(profile, 'mfa_enabled', False),
            'security_alerts_enabled': getattr(profile, 'security_alerts_enabled', True),
            'email_verified': getattr(profile, 'email_verified', False),
            'last_password_change': getattr(profile, 'last_password_change', None),
            'allowed_ip_addresses': getattr(profile, 'allowed_ip_addresses', []),
            'session_timeout_minutes': getattr(profile, 'session_timeout_minutes', 60),
            'max_concurrent_sessions': getattr(profile, 'max_concurrent_sessions', 5)
        }


@query_handler(GetUserAuthHistoryQuery)
class GetUserAuthHistoryQueryHandler(BaseQueryHandler[GetUserAuthHistoryQuery, list[dict[str, Any]]]):
    """Handler for getting auth history - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: GetUserAuthHistoryQuery) -> list[dict[str, Any]]:
        """Get user authentication history from cache"""
        history = []

        # Get from cache only - no cross-domain dependencies
        for event_type in query.event_types:
            cache_key = self.cache_manager._make_key('auth', 'history', str(query.user_id), event_type)
            events = await self.cache_manager.get_json(cache_key)

            if events and isinstance(events, list):
                for event in events[:query.limit]:
                    history.append({
                        'user_id': str(query.user_id),
                        'event_type': event_type,
                        'timestamp': event.get('timestamp'),
                        'ip_address': event.get('ip_address'),
                        'user_agent': event.get('user_agent'),
                        'success': event.get('success', True),
                        'details': event.get('details', {})
                    })

        # Sort by timestamp descending
        history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        return history[:query.limit]


@readonly_query(ValidateUserSessionQuery)
class ValidateUserSessionQueryHandler(BaseQueryHandler[ValidateUserSessionQuery, dict[str, Any]]):
    """Handler for validating user session - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: ValidateUserSessionQuery) -> dict[str, Any]:
        """Validate user session from cache"""
        # Check if session exists in cache
        session_key = self.cache_manager._make_key('auth', 'session', query.session_id)
        session_data = await self.cache_manager.get_json(session_key)

        if not session_data:
            return {
                'valid': False,
                'reason': 'Session not found',
                'user_id': str(query.user_id),
                'session_id': query.session_id
            }

        # Validate user ID matches
        if session_data.get('user_id') != str(query.user_id):
            return {
                'valid': False,
                'reason': 'User ID mismatch',
                'user_id': str(query.user_id),
                'session_id': query.session_id
            }

        # Check if session is expired
        expires_at = datetime.fromisoformat(session_data.get('expires_at'))
        if expires_at <= datetime.now(timezone.utc):
            return {
                'valid': False,
                'reason': 'Session expired',
                'user_id': str(query.user_id),
                'session_id': query.session_id,
                'expired_at': expires_at.isoformat()
            }

        # Check IP if provided
        if query.check_ip and session_data.get('ip_address'):
            if session_data['ip_address'] != query.check_ip:
                self.log.warning(f"IP mismatch for session {query.session_id}")

        return {
            'valid': True,
            'user_id': str(query.user_id),
            'session_id': query.session_id,
            'created_at': session_data.get('created_at'),
            'expires_at': expires_at.isoformat(),
            'ip_address': session_data.get('ip_address')
        }

# =============================================================================
# EOF
# =============================================================================