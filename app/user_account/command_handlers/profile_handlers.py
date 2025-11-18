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

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.users.profile_handlers")


# -----------------------------------------------------------------------------
# UpdateUserProfileHandler - WellWon Platform
# -----------------------------------------------------------------------------
@command_handler(UpdateUserProfileCommand)
class UpdateUserProfileHandler(ICommandHandler):
    """Handles the UpdateUserProfileCommand for WellWon platform."""

    def __init__(self, deps: 'HandlerDependencies'):
        self.command_bus = deps.command_bus
        self.query_bus = deps.query_bus
        self.event_bus = deps.event_bus

    async def handle(self, command: UpdateUserProfileCommand) -> None:
        log.info(f"Updating profile for user {command.user_id}")

        # Verify user exists
        user = await self.query_bus.query(
            GetUserProfileQuery(user_id=command.user_id)
        )
        if not user:
            raise ValueError("User not found.")

        # Publish profile updated event
        event = UserProfileUpdated(
            user_id=command.user_id,
            first_name=command.first_name,
            last_name=command.last_name,
            avatar_url=command.avatar_url,
            bio=command.bio,
            phone=command.phone,
        )

        await self.event_bus.publish(
            "transport.user-account-events",
            event.model_dump()
        )

        log.info(f"Profile updated for user {command.user_id}")

# =============================================================================
# EOF
# =============================================================================
