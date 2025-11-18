# =============================================================================
# File: app/user_account/command_handlers/auth_handlers.py
# Description: Authentication and user lifecycle command handlers
# Handlers: Create, Authenticate, Delete, VerifyEmail
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import Tuple, TYPE_CHECKING

from app.user_account.commands import (
    CreateUserAccountCommand,
    AuthenticateUserCommand,
    DeleteUserAccountCommand,
    VerifyUserEmailCommand,
)

from app.user_account.events import (
    UserAccountCreated,
    UserAuthenticationSucceeded,
    UserAuthenticationFailed,
    UserAccountDeleted,
    UserEmailVerified,
)

from app.user_account.queries import (
    GetUserByUsernameQuery,
    GetUserProfileQuery,
    ValidateUserCredentialsQuery,
    HashPasswordQuery,
)

from app.infra.cqrs.command_bus import ICommandHandler
from app.infra.cqrs.decorators import command_handler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.users.auth_handlers")


# -----------------------------------------------------------------------------
# CreateUserHandler - Pure CQRS
# -----------------------------------------------------------------------------
@command_handler(CreateUserAccountCommand)
class CreateUserAccountHandler(ICommandHandler):
    """Handles the CreateUserAccountCommand using only buses."""

    def __init__(self, deps: 'HandlerDependencies'):
        self.command_bus = deps.command_bus
        self.query_bus = deps.query_bus
        self.event_bus = deps.event_bus

    async def handle(self, command: CreateUserAccountCommand) -> uuid.UUID:
        log.info(f"Creating user account for username: {command.username}")

        # Check if username exists using query bus
        existing_user = await self.query_bus.query(
            GetUserByUsernameQuery(username=command.username)
        )
        if existing_user:
            raise ValueError(f"Username '{command.username}' already exists.")

        # Hash password using query bus
        hashed_password = await self.query_bus.query(
            HashPasswordQuery(password=command.password)
        )
        log.info(f"DEBUG HANDLER: password='{command.password}' (len={len(command.password)}), hashed_password starts with: {hashed_password[:20]}")

        # Hash secret using query bus
        hashed_secret = await self.query_bus.query(
            HashPasswordQuery(password=command.secret)
        )
        log.info(f"DEBUG HANDLER: secret='{command.secret}' (len={len(command.secret)}), hashed_secret starts with: {hashed_secret[:20]}")

        # Create and publish UserAccountCreated event
        event = UserAccountCreated(
            user_id=command.user_id,
            username=command.username,
            email=command.email,
            role=command.role,
            hashed_password=hashed_password,
            hashed_secret=hashed_secret,
        )

        await self.event_bus.publish(
            "transport.user-account-events",
            event.model_dump()
        )

        log.info(f"User account created with ID: {command.user_id}")
        return command.user_id


# -----------------------------------------------------------------------------
# AuthenticateUserHandler - Pure CQRS
# -----------------------------------------------------------------------------
@command_handler(AuthenticateUserCommand)
class AuthenticateUserHandler(ICommandHandler):
    """
    Handles the AuthenticateUserCommand using only buses.
    Authentication is a query-like operation but returns data.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        self.command_bus = deps.command_bus
        self.query_bus = deps.query_bus
        self.event_bus = deps.event_bus

    async def handle(self, command: AuthenticateUserCommand) -> Tuple[uuid.UUID, str, str]:
        log.info(f"Authenticating user: {command.username}")

        # Get user by username using query bus
        user = await self.query_bus.query(
            GetUserByUsernameQuery(username=command.username)
        )

        log.info(f"DEBUG AUTH: GetUserByUsernameQuery returned: {user is not None}, is_active={user.is_active if user else 'N/A'}")

        if not user or not user.is_active:
            # Publish failed authentication event
            event = UserAuthenticationFailed(
                username_attempted=command.username,
                reason="User not found or inactive"
            )
            await self.event_bus.publish(
                "transport.user-account-events",
                event.model_dump()
            )
            raise ValueError("Invalid username or password.")

        # Validate credentials using query bus
        credentials_result = await self.query_bus.query(
            ValidateUserCredentialsQuery(
                user_id=user.id,
                password=command.password
            )
        )

        if not credentials_result['valid']:
            # Publish failed authentication event
            event = UserAuthenticationFailed(
                username_attempted=command.username,
                reason="Invalid password"
            )
            await self.event_bus.publish(
                "transport.user-account-events",
                event.model_dump()
            )
            raise ValueError("Invalid username or password.")

        # Publish success event (projection will update last login)
        event = UserAuthenticationSucceeded(
            user_id=user.id,
            username=user.username,
            role=user.role,
        )
        await self.event_bus.publish(
            "transport.user-account-events",
            event.model_dump()
        )

        log.info(f"User '{command.username}' authenticated successfully")
        return user.id, user.username, user.role


# -----------------------------------------------------------------------------
# DeleteUserHandler - Pure CQRS with TRUE SAGA Pattern
# -----------------------------------------------------------------------------
@command_handler(DeleteUserAccountCommand)
class DeleteUserHandler(ICommandHandler):
    """
    Handles the DeleteUserAccountCommand using TRUE SAGA Pattern.
    ENRICHED EVENT: Includes owned resource IDs to eliminate query_bus dependency in saga.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        self.command_bus = deps.command_bus
        self.query_bus = deps.query_bus
        self.event_bus = deps.event_bus

    async def handle(self, command: DeleteUserAccountCommand) -> None:
        log.info(f"Deleting user account: {command.user_id}, reason: {command.reason}")

        # Verify user exists
        user = await self.query_bus.query(
            GetUserProfileQuery(user_id=command.user_id)
        )
        if not user:
            raise ValueError("User not found.")

        # TRUE SAGA PATTERN: Enrich event with owned resource IDs
        # This eliminates the need for query_bus in saga (performance + reliability)

        # Check for virtual broker connection
        has_virtual_broker = False
        from app.broker_connection.queries import GetBrokerConnectionsForUserQuery
        try:
            connections = await self.query_bus.query(
                GetBrokerConnectionsForUserQuery(user_id=command.user_id)
            )
            has_virtual_broker = any(conn.broker_id == "virtual_broker" for conn in connections)

            # Collect owned resource IDs
            owned_connection_ids = [conn.id for conn in connections]
        except Exception as e:
            log.warning(f"Could not fetch broker connections for user {command.user_id}: {e}")
            owned_connection_ids = []

        # Collect owned broker account IDs
        owned_account_ids = []
        try:
            from app.broker_account.queries import GetAccountsForUserQuery
            accounts = await self.query_bus.query(
                GetAccountsForUserQuery(user_id=command.user_id)
            )
            owned_account_ids = [acc.id for acc in accounts]
        except Exception as e:
            log.warning(f"Could not fetch broker accounts for user {command.user_id}: {e}")

        # ENRICHED EVENT with all owned resource IDs
        event = UserAccountDeleted(
            user_id=command.user_id,
            reason=command.reason,
            grace_period=command.grace_period,
            has_virtual_broker=has_virtual_broker,
            owned_connection_ids=owned_connection_ids,
            owned_account_ids=owned_account_ids,
            owned_automation_ids=[],  # TODO: Add when automation domain exists
        )

        await self.event_bus.publish(
            "transport.user-account-events",
            event.model_dump()
        )

        log.info(f"User account deleted (soft): {command.user_id}")


# -----------------------------------------------------------------------------
# VerifyUserEmailHandler - Pure CQRS
# -----------------------------------------------------------------------------
@command_handler(VerifyUserEmailCommand)
class VerifyUserEmailHandler(ICommandHandler):
    """Handles the VerifyUserEmailCommand using only buses."""

    def __init__(self, deps: 'HandlerDependencies'):
        self.command_bus = deps.command_bus
        self.query_bus = deps.query_bus
        self.event_bus = deps.event_bus

    async def handle(self, command: VerifyUserEmailCommand) -> None:
        log.info(f"Verifying email for user: {command.user_id}")

        # Verify user exists
        user = await self.query_bus.query(
            GetUserProfileQuery(user_id=command.user_id)
        )
        if not user:
            raise ValueError("User not found.")

        if user.email_verified:
            log.info(f"Email already verified for user {command.user_id}")
            return  # Idempotent

        # TODO: Validate verification token

        # Publish email verified event
        event = UserEmailVerified(
            user_id=command.user_id,
        )

        await self.event_bus.publish(
            "transport.user-account-events",
            event.model_dump()
        )

        log.info(f"Email verified for user: {command.user_id}")

# =============================================================================
# EOF
# =============================================================================
