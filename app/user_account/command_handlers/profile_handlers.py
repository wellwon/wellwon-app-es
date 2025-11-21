# =============================================================================
# File: app/user_account/command_handlers/profile_handlers.py
# Description: User profile management command handlers (WellWon Platform)
# Handlers: UpdateProfile
# =============================================================================

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.user_account.commands import UpdateUserProfileCommand
from app.user_account.events import UserProfileUpdated
from app.user_account.queries import GetUserProfileQuery

from app.infra.cqrs.command_bus import ICommandHandler
from app.infra.cqrs.decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler
from app.user_account.aggregate import UserAccountAggregate

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.users.profile_handlers")


# -----------------------------------------------------------------------------
# UpdateUserProfileHandler - Event Sourcing Pattern
# -----------------------------------------------------------------------------
@command_handler(UpdateUserProfileCommand)
class UpdateUserProfileHandler(BaseCommandHandler):
    """Handles the UpdateUserProfileCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.user-account-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: UpdateUserProfileCommand) -> None:
        log.info(f"Updating profile for user {command.user_id}")

        # Verify user exists
        user = await self.query_bus.query(
            GetUserProfileQuery(user_id=command.user_id)
        )
        if not user:
            raise ValueError("User not found.")

        # Create aggregate
        user_aggregate = UserAccountAggregate(user_id=command.user_id)

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

        # Publish events
        await self.publish_and_commit_events(
            aggregate=user_aggregate,
            aggregate_type="UserAccount",
            expected_version=None,
        )

        log.info(f"Profile updated for user {command.user_id}")

# =============================================================================
# EOF
# =============================================================================
