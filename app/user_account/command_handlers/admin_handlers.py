# =============================================================================
# File: app/user_account/command_handlers/admin_handlers.py
# Description: Admin command handlers for user management
# Handlers: UpdateUserAdminStatus
# =============================================================================

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.user_account.commands import UpdateUserAdminStatusCommand
from app.user_account.events import UserAdminStatusUpdated
from app.user_account.queries import GetUserProfileQuery

from app.infra.cqrs.decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler
from app.user_account.aggregate import UserAccountAggregate

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.users.admin_handlers")


# -----------------------------------------------------------------------------
# UpdateUserAdminStatusHandler - Event Sourcing Pattern
# -----------------------------------------------------------------------------
@command_handler(UpdateUserAdminStatusCommand)
class UpdateUserAdminStatusHandler(BaseCommandHandler):
    """Handles the UpdateUserAdminStatusCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.user-account-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: UpdateUserAdminStatusCommand) -> None:
        log.info(f"Admin {command.admin_user_id} updating status for user {command.user_id}")

        # Verify target user exists
        user = await self.query_bus.query(
            GetUserProfileQuery(user_id=command.user_id)
        )
        if not user:
            raise ValueError("Target user not found.")

        # Create aggregate
        user_aggregate = UserAccountAggregate(user_id=command.user_id)

        # Call aggregate command method
        user_aggregate.update_admin_status(
            admin_user_id=command.admin_user_id,
            is_active=command.is_active,
            is_developer=command.is_developer,
        )

        # Publish events
        await self.publish_and_commit_events(
            aggregate=user_aggregate,
            aggregate_type="UserAccount",
            expected_version=None,
        )

        log.info(f"Admin status updated for user {command.user_id} by admin {command.admin_user_id}")


# =============================================================================
# EOF
# =============================================================================
