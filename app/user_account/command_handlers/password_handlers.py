# =============================================================================
# File: app/user_account/command_handlers/password_handlers.py
# Description: Password management command handlers
# Handlers: ChangePassword, ResetPassword
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import TYPE_CHECKING

from app.user_account.commands import (
    ChangeUserPasswordCommand,
    ResetUserPasswordWithSecretCommand,
)

from app.user_account.events import (
    UserPasswordChanged,
    UserPasswordResetViaSecret,
)

from app.user_account.queries import (
    GetUserByUsernameQuery,
    GetUserProfileQuery,
    ValidateUserCredentialsQuery,
    HashPasswordQuery,
    VerifyPasswordHashQuery,
)

from app.infra.cqrs.command_bus import ICommandHandler
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler
from app.user_account.aggregate import UserAccountAggregate

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.users.password_handlers")


# -----------------------------------------------------------------------------
# ChangeUserPasswordHandler - Event Sourcing Pattern
# -----------------------------------------------------------------------------
@command_handler(ChangeUserPasswordCommand)
class ChangeUserPasswordHandler(BaseCommandHandler):
    """Handles the ChangeUserPasswordCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.user-account-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: ChangeUserPasswordCommand) -> None:
        log.info(f"Changing password for user: {command.user_id}")

        # Get user profile using query bus
        user = await self.query_bus.query(
            GetUserProfileQuery(user_id=command.user_id)
        )
        if not user:
            raise ValueError("User not found.")

        # Verify current password using query bus
        credentials_result = await self.query_bus.query(
            ValidateUserCredentialsQuery(
                user_id=command.user_id,
                password=command.current_password
            )
        )

        if not credentials_result['valid']:
            raise ValueError("Current password is incorrect.")

        # Hash new password using query bus
        new_hashed_password = await self.query_bus.query(
            HashPasswordQuery(password=command.new_password)
        )

        # Create aggregate
        user_aggregate = UserAccountAggregate(user_id=command.user_id)

        # Call aggregate command method
        user_aggregate.change_password(new_hashed_password=new_hashed_password)

        # Publish events
        await self.publish_and_commit_events(
            aggregate=user_aggregate,
            aggregate_type="UserAccount",
            expected_version=None,
        )

        log.info(f"Password changed for user: {command.user_id}")


# -----------------------------------------------------------------------------
# ResetUserPasswordWithSecretHandler - Event Sourcing Pattern
# -----------------------------------------------------------------------------
@command_handler(ResetUserPasswordWithSecretCommand)
class ResetUserPasswordWithSecretHandler(BaseCommandHandler):
    """Handles the ResetUserPasswordWithSecretCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.user-account-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: ResetUserPasswordWithSecretCommand) -> None:
        log.info(f"Resetting password for username: {command.username}")

        # Get user by username including auth details
        user = await self.query_bus.query(
            GetUserByUsernameQuery(username=command.username)
        )

        if not user or not user.is_active:
            raise ValueError("User not found or inactive.")

        # Verify secret using query bus
        secret_valid = await self.query_bus.query(
            VerifyPasswordHashQuery(
                user_id=user.id,
                password_hash=user.hashed_secret,
                password=command.secret
            )
        )

        if not secret_valid:
            raise ValueError("Invalid secret word.")

        # Hash new password using query bus
        new_hashed_password = await self.query_bus.query(
            HashPasswordQuery(password=command.new_password)
        )

        # Create aggregate
        user_aggregate = UserAccountAggregate(user_id=user.id)

        # Call aggregate command method
        user_aggregate.reset_password_with_secret(new_hashed_password=new_hashed_password)

        # Publish events
        await self.publish_and_commit_events(
            aggregate=user_aggregate,
            aggregate_type="UserAccount",
            expected_version=None,
        )

        log.info(f"Password reset for user: {user.id}")

# =============================================================================
# EOF
# =============================================================================
