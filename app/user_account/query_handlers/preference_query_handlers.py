# app/user_account/query_handlers/preference_query_handlers.py
# =============================================================================
# File: app/user_account/query_handlers/preference_query_handlers.py
# Description: Query handlers for user preferences & settings - CQRS COMPLIANT
# =============================================================================

import logging
from typing import TYPE_CHECKING, Any

from app.infra.cqrs.query_bus import IQueryHandler
from app.infra.cqrs.decorators import query_handler, readonly_query
from app.common.base.base_query_handler import BaseQueryHandler
from app.user_account.queries import (
    GetUserNotificationPreferencesQuery,
    GetUserSessionHistoryQuery,
)
from app.common.exceptions.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies


# =============================================================================
# Preference Query Handlers - CQRS Compliant
# =============================================================================

@readonly_query(GetUserNotificationPreferencesQuery)
class GetUserNotificationPreferencesQueryHandler(BaseQueryHandler[GetUserNotificationPreferencesQuery, dict[str, Any]]):
    """Handler for getting notification preferences - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        # Only use user domain repository
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetUserNotificationPreferencesQuery) -> dict[str, Any]:
        """Get notification preferences from user profile"""
        profile = await self.user_repo.get_user_profile_by_user_id(query.user_id)

        profile = self.handle_not_found(
            resource=profile,
            resource_type="User",
            resource_id=query.user_id
        )

        # Get preferences from user profile
        preferences = getattr(profile, 'preferences', {})
        notifications = preferences.get('notifications', {})

        return {
            'user_id': str(query.user_id),
            'email_notifications': notifications.get('email', True),
            'sms_notifications': notifications.get('sms', False),
            'push_notifications': notifications.get('push', True),
            'trade_alerts': notifications.get('trade_alerts', True),
            'account_alerts': notifications.get('account_alerts', True),
            'security_alerts': notifications.get('security_alerts', True),
            'marketing_emails': notifications.get('marketing', False),
            'notification_preferences': notifications  # Include raw preferences
        }


@readonly_query(GetUserSessionHistoryQuery)
class GetUserSessionHistoryQueryHandler(BaseQueryHandler[GetUserSessionHistoryQuery, list[dict[str, Any]]]):
    """Handler for getting user session history - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        # Session history might be in cache or audit log
        self.cache_manager = deps.cache_manager

    async def handle(self, query: GetUserSessionHistoryQuery) -> list[dict[str, Any]]:
        """Get session/login history"""
        history = []

        # Try to get from cache first
        cache_key = self.cache_manager._make_key('session', 'history', str(query.user_id))
        cached_history = await self.cache_manager.get_json(cache_key)

        if cached_history and isinstance(cached_history, list):
            # Apply limit
            history = cached_history[:query.limit]

            # Filter by failed attempts if requested
            if not query.include_failed_attempts:
                history = [h for h in history if h.get('success', True)]

        # In a production system, this would query an audit log or session history table
        # For now, we return what we have from cache
        self.log.info(
            f"Session history query for user {query.user_id}: "
            f"Found {len(history)} entries (limit={query.limit})"
        )

        return history

# =============================================================================
# EOF
# =============================================================================