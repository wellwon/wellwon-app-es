# app/user_account/query_handlers/profile_query_handlers.py
# =============================================================================
# File: app/user_account/query_handlers/profile_query_handlers.py
# Description: Query handlers for user profile operations - CQRS COMPLIANT
#
# All handlers inherit from BaseQueryHandler for consistent patterns.
# =============================================================================

import logging
from typing import TYPE_CHECKING, Any, Optional
from datetime import timezone, datetime

from app.infra.cqrs.query_bus import IQueryHandler
from app.infra.cqrs.decorators import query_handler, readonly_query, cached_query_handler, readonly_query
from app.common.base.base_query_handler import BaseQueryHandler
from app.user_account.queries import (
    GetUserProfileQuery,
    GetUserByUsernameQuery,
    GetUserByEmailQuery,
    CheckUserExistsQuery,
    GetUserResourcesQuery,
    UserProfile,
)
from app.common.exceptions.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies


# =============================================================================
# Profile Query Handlers - CQRS Compliant
# =============================================================================

@cached_query_handler(GetUserProfileQuery, ttl=120)
class GetUserProfileQueryHandler(BaseQueryHandler[GetUserProfileQuery, UserProfile]):
    """Handler for getting user profile - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo
        self.query_bus = deps.query_bus

    async def handle(self, query: GetUserProfileQuery) -> UserProfile:
        """Get user profile data"""
        profile = await self.user_repo.get_user_profile_by_user_id(query.user_id)

        profile = self.handle_not_found(
            resource=profile,
            resource_type="User profile",
            resource_id=query.user_id
        )

        return UserProfile(
            id=profile.id,
            username=profile.username,
            email=profile.email,
            role=profile.role,
            is_active=profile.is_active,
            email_verified=getattr(profile, 'email_verified', False),
            mfa_enabled=getattr(profile, 'mfa_enabled', False),
            created_at=profile.created_at,
            last_login=profile.last_login,
            last_password_change=getattr(profile, 'last_password_change', None),
            security_alerts_enabled=getattr(profile, 'security_alerts_enabled', True),
            preferences=getattr(profile, 'preferences', {}) if query.include_preferences else {},
            metadata=getattr(profile, 'metadata', {})
        )


@query_handler(GetUserByUsernameQuery)
class GetUserByUsernameQueryHandler(BaseQueryHandler[GetUserByUsernameQuery, Optional[UserProfile]]):
    """Handler for finding user by username - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetUserByUsernameQuery) -> UserProfile | None:
        """Find user by username"""
        # Same-domain query
        auth_data = await self.user_repo.get_user_auth_details_by_username(query.username)

        if not auth_data:
            return None

        return UserProfile(
            id=auth_data.user_id,
            username=auth_data.username,
            email=auth_data.email,
            role=auth_data.role,
            is_active=auth_data.is_active,
            email_verified=auth_data.email_verified,
            mfa_enabled=auth_data.mfa_enabled,
            created_at=auth_data.created_at,
            last_login=auth_data.last_login,
            last_password_change=auth_data.last_password_change,
            security_alerts_enabled=auth_data.security_alerts_enabled,
            preferences={},
            metadata={}
        )


@readonly_query(GetUserByEmailQuery)
class GetUserByEmailQueryHandler(BaseQueryHandler[GetUserByEmailQuery, Optional[UserProfile]]):
    """Handler for finding user by email - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetUserByEmailQuery) -> UserProfile | None:
        """Find user by email"""
        # Same-domain query
        auth_data = await self.user_repo.get_user_auth_details_by_email(query.email)

        if not auth_data:
            return None

        return UserProfile(
            id=auth_data.user_id,
            username=auth_data.username,
            email=auth_data.email,
            role=auth_data.role,
            is_active=auth_data.is_active,
            email_verified=auth_data.email_verified,
            mfa_enabled=auth_data.mfa_enabled,
            created_at=auth_data.created_at,
            last_login=auth_data.last_login,
            last_password_change=auth_data.last_password_change,
            security_alerts_enabled=auth_data.security_alerts_enabled,
            preferences={},
            metadata={}
        )


@readonly_query(CheckUserExistsQuery)
class CheckUserExistsQueryHandler(BaseQueryHandler[CheckUserExistsQuery, dict[str, bool]]):
    """Handler for checking if user exists - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo

    async def handle(self, query: CheckUserExistsQuery) -> dict[str, bool]:
        """Check user existence"""
        exists_by_username = False
        exists_by_email = False

        if query.username:
            user = await self.user_repo.get_user_auth_details_by_username(query.username)
            exists_by_username = user is not None

        if query.email:
            # TODO: Implement email check when repository method is available
            self.log.warning("CheckUserExistsQuery: Email check not yet implemented")
            exists_by_email = False

        return {
            'exists': exists_by_username or exists_by_email,
            'exists_by_username': exists_by_username,
            'exists_by_email': exists_by_email
        }


@readonly_query(GetUserResourcesQuery)
class GetUserResourcesQueryHandler(BaseQueryHandler[GetUserResourcesQuery, Optional[dict[str, Any]]]):
    """Handler for getting USER DOMAIN resources only - CLEAN DOMAIN BOUNDARIES"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetUserResourcesQuery) -> dict[str, Any]:
        """
        Get user domain resources only - saga handles cross-domain orchestration.

        CQRS/ES: When called from saga context (saga_id present), return None instead of
        raising exception if user not found. This handles eventual consistency where user
        may be deleted from read model before saga executes.
        """
        user_id = query.user_id

        # Get user profile from our domain
        profile = await self.user_repo.get_user_profile_by_user_id(user_id)

        if not profile:
            # CQRS/ES: If called from saga, user may already be deleted - return None gracefully
            if query.saga_id:
                self.log.info(
                    f"GetUserResourcesQuery: User {user_id} not found in read model "
                    f"(saga context: {query.saga_id}). Returning None for eventual consistency."
                )
                return None

            # Regular query (not from saga) - raise exception as expected
            raise ResourceNotFoundError(f"User not found: {user_id}")

        # Get user-specific data only
        auth_data = await self.user_repo.get_user_auth_details_by_username(profile.username)

        # Get user's broker mappings (stored in user domain)
        account_mappings = await self.user_repo.get_account_mappings(user_id)
        connected_brokers = await self.user_repo.get_connected_brokers(user_id)

        self.log.info(f"GetUserResourcesQuery for user {user_id}: Returning user domain data only")

        return {
            'user_id': str(user_id),
            'username': profile.username,
            'email': profile.email,
            'role': profile.role,
            'is_active': profile.is_active,
            'email_verified': getattr(profile, 'email_verified', False),
            'created_at': profile.created_at.isoformat(),
            'account_mappings': account_mappings or {},
            'connected_brokers': connected_brokers or [],
            'saga_id': str(query.saga_id) if query.saga_id else None
        }

# =============================================================================
# EOF
# =============================================================================