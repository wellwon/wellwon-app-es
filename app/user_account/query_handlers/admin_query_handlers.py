# app/user_account/query_handlers/admin_query_handlers.py
# =============================================================================
# File: app/user_account/query_handlers/admin_query_handlers.py
# Description: Query handlers for admin operations - CQRS COMPLIANT
# =============================================================================

import logging
from typing import TYPE_CHECKING, List

from app.infra.cqrs.decorators import readonly_query
from app.common.base.base_query_handler import BaseQueryHandler
from app.user_account.queries import (
    GetAllUsersAdminQuery,
    AdminUserInfo,
)

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies


# =============================================================================
# Admin Query Handlers - CQRS Compliant
# =============================================================================

@readonly_query(GetAllUsersAdminQuery)
class GetAllUsersAdminQueryHandler(BaseQueryHandler[GetAllUsersAdminQuery, List[AdminUserInfo]]):
    """Handler for getting all users for admin panel - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetAllUsersAdminQuery) -> List[AdminUserInfo]:
        """Get all users for admin panel"""
        users = await self.user_repo.get_all_users_for_admin(
            include_inactive=query.include_inactive,
            limit=query.limit,
            offset=query.offset
        )

        return [
            AdminUserInfo(
                id=user.id,
                first_name=getattr(user, 'first_name', None),
                last_name=getattr(user, 'last_name', None),
                email=user.email,
                is_active=getattr(user, 'is_active', True),
                is_developer=getattr(user, 'is_developer', False),
                created_at=user.created_at,
            )
            for user in users
        ]


# =============================================================================
# EOF
# =============================================================================
