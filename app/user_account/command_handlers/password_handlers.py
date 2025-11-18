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
from app.infra.cqrs.decorators import command_handler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.users.password_handlers")


# -----------------------------------------------------------------------------
# ChangeUserPasswordHandler - Pure CQRS
# -----------------------------------------------------------------------------
@command_handler(ChangeUserPasswordCommand)
class ChangeUserPasswordHandler(ICommandHandler):
    """Handles the ChangeUserPasswordCommand using only buses."""

    def __init__(self, deps: 'HandlerDependencies'):
        self.command_bus = deps.command_bus
        self.query_bus = deps.query_bus
        self.event_bus = deps.event_bus

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

        # Publish password changed event
        event = UserPasswordChanged(
            user_id=command.user_id,
            new_hashed_password=new_hashed_password,
        )

        await self.event_bus.publish(
            "transport.user-account-events",
            event.model_dump()
        )

        log.info(f"Password changed for user: {command.user_id}")


# -----------------------------------------------------------------------------
# ResetUserPasswordWithSecretHandler - Pure CQRS
# -----------------------------------------------------------------------------
@command_handler(ResetUserPasswordWithSecretCommand)
class ResetUserPasswordWithSecretHandler(ICommandHandler):
    """Handles the ResetUserPasswordWithSecretCommand using only buses."""

    def __init__(self, deps: 'HandlerDependencies'):
        self.command_bus = deps.command_bus
        self.query_bus = deps.query_bus
        self.event_bus = deps.event_bus

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

        # Publish password reset event
        event = UserPasswordResetViaSecret(
            user_id=user.id,
            new_hashed_password=new_hashed_password,
        )

        await self.event_bus.publish(
            "transport.user-account-events",
            event.model_dump()
        )

        log.info(f"Password reset for user: {user.id}")

# =============================================================================
# EOF
# =============================================================================
