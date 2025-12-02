# =============================================================================
# File: app/user_account/command_handlers/profile_handlers.py
# Description: User profile management command handlers (pure Event Sourcing)
# Handlers: UpdateProfile
# =============================================================================

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.user_account.commands import UpdateUserProfileCommand
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler
from app.user_account.aggregate import UserAccountAggregate

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.users.profile_handlers")


# -----------------------------------------------------------------------------
# UpdateUserProfileHandler - Pure Event Sourcing
# -----------------------------------------------------------------------------
@command_handler(UpdateUserProfileCommand)
class UpdateUserProfileHandler(BaseCommandHandler):
    """
    Handles the UpdateUserProfileCommand using pure Event Sourcing.

    Loads user aggregate from Event Store and updates profile.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.user-account-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UpdateUserProfileCommand) -> None:
        log.info(f"Updating profile for user {command.user_id}")

        # Load aggregate from Event Store
        user_aggregate = await self.load_aggregate(command.user_id, "UserAccount", UserAccountAggregate)

        # Verify user exists
        if user_aggregate.version == 0:
            raise ValueError("User not found.")

        # Call aggregate command method
        user_aggregate.update_profile(
            first_name=command.first_name,
            last_name=command.last_name,
            avatar_url=command.avatar_url,
            bio=command.bio,
            phone=command.phone,
            user_type=command.user_type,
            is_developer=command.is_developer,
        )

        # Publish events with version tracking
        await self.publish_events(
            aggregate=user_aggregate,
            aggregate_id=command.user_id,
            command=command
        )

        log.info(f"Profile updated for user {command.user_id}")

# =============================================================================
# EOF
# =============================================================================
