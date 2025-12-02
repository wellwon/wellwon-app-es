# =============================================================================
# File: app/user_account/command_handlers/admin_handlers.py
# Description: Admin command handlers for user management (pure Event Sourcing)
# Handlers: UpdateUserAdminStatus
# =============================================================================

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.user_account.commands import UpdateUserAdminStatusCommand

from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler
from app.user_account.aggregate import UserAccountAggregate

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.users.admin_handlers")


# -----------------------------------------------------------------------------
# UpdateUserAdminStatusHandler - Pure Event Sourcing
# -----------------------------------------------------------------------------
@command_handler(UpdateUserAdminStatusCommand)
class UpdateUserAdminStatusHandler(BaseCommandHandler):
    """
    Handles the UpdateUserAdminStatusCommand using pure Event Sourcing.

    Loads user aggregate from Event Store and updates admin status.
    Used by admin panel to update user status (is_active, is_developer).
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.user-account-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UpdateUserAdminStatusCommand) -> None:
        log.info(
            f"Admin {command.admin_user_id} updating status for user {command.user_id}: "
            f"is_active={command.is_active}, is_developer={command.is_developer}"
        )

        # Load aggregate from Event Store
        user_aggregate = await self.load_aggregate(command.user_id, "UserAccount", UserAccountAggregate)

        # Verify user exists
        if user_aggregate.version == 0:
            raise ValueError("User not found.")

        # Call aggregate command method
        user_aggregate.update_admin_status(
            admin_user_id=command.admin_user_id,
            is_active=command.is_active,
            is_developer=command.is_developer,
            user_type=command.user_type,
            role=command.role,
        )

        # Publish events with version tracking
        await self.publish_events(
            aggregate=user_aggregate,
            aggregate_id=command.user_id,
            command=command
        )

        log.info(f"Admin status updated for user {command.user_id}")


# =============================================================================
# EOF
# =============================================================================
