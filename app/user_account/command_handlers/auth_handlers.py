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
    GetUserByEmailQuery,
    GetUserProfileQuery,
    ValidateUserCredentialsQuery,
    HashPasswordQuery,
)

from app.infra.cqrs.command_bus import ICommandHandler
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler
from app.user_account.aggregate import UserAccountAggregate

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.users.auth_handlers")


# -----------------------------------------------------------------------------
# CreateUserHandler - Event Sourcing Pattern
# EXCEPTION: Uses QueryBus for uniqueness check and password hashing.
# These are legitimate exceptions: uniqueness validation and infrastructure services.
# -----------------------------------------------------------------------------
@command_handler(CreateUserAccountCommand)
class CreateUserAccountHandler(BaseCommandHandler):
    """
    Handles the CreateUserAccountCommand using Event Sourcing.

    EXCEPTION TO PURE CQRS: Uses QueryBus for:
    - Uniqueness check (username exists) - validation before create
    - Password hashing - infrastructure service (not a true query)
    """

    def __init__(self, deps: 'HandlerDependencies'):
        # Initialize base with event infrastructure
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.user-account-events",
            event_store=deps.event_store
        )
        # Query bus for uniqueness check and password hashing
        self.query_bus = deps.query_bus

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

        # Create aggregate
        user_aggregate = UserAccountAggregate(user_id=command.user_id)

        # Call aggregate command method (emits UserAccountCreated event)
        user_aggregate.create_new_user(
            username=command.username,
            email=command.email,
            role=command.role,
            hashed_password=hashed_password,
            hashed_secret=hashed_secret,
            first_name=command.first_name,
            last_name=command.last_name,
        )

        # Publish events to EventStore + Transport (via BaseCommandHandler)
        await self.publish_and_commit_events(
            aggregate=user_aggregate,
            aggregate_type="UserAccount",
            expected_version=None,  # New aggregate
        )

        log.info(f"User account created with ID: {command.user_id}")
        return command.user_id


# -----------------------------------------------------------------------------
# AuthenticateUserHandler - Query-like with Audit Events
# EXCEPTION: Authentication is inherently query-based (lookup by email/username).
# This is a legitimate exception for security-critical operations.
# -----------------------------------------------------------------------------
@command_handler(AuthenticateUserCommand)
class AuthenticateUserHandler(BaseCommandHandler):
    """
    Handles the AuthenticateUserCommand.

    EXCEPTION TO PURE CQRS: Authentication is inherently query-based:
    - Must lookup user by email/username to find aggregate ID
    - Must validate credentials against stored hash
    - Emits audit events (success/failure) for security tracking

    This is not a typical command - it's a security operation with audit trail.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.user-account-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: AuthenticateUserCommand) -> Tuple[uuid.UUID, str, str]:
        log.info(f"Authenticating user: {command.username}")

        # Check if username is actually an email (contains @)
        if '@' in command.username:
            # Get user by email
            user = await self.query_bus.query(
                GetUserByEmailQuery(email=command.username)
            )
            log.info(f"DEBUG AUTH: GetUserByEmailQuery returned: {user is not None}, is_active={user.is_active if user else 'N/A'}")
        else:
            # Get user by username
            user = await self.query_bus.query(
                GetUserByUsernameQuery(username=command.username)
            )
            log.info(f"DEBUG AUTH: GetUserByUsernameQuery returned: {user is not None}, is_active={user.is_active if user else 'N/A'}")

        if not user or not user.is_active:
            # Publish failed authentication event (audit only, no state change)
            event = UserAuthenticationFailed(
                username_attempted=command.username,
                reason="User not found or inactive"
            )
            await self.event_bus.publish(
                self.transport_topic,
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
            # Publish failed authentication event (audit only, no state change)
            event = UserAuthenticationFailed(
                username_attempted=command.username,
                reason="Invalid password"
            )
            await self.event_bus.publish(
                self.transport_topic,
                event.model_dump()
            )
            raise ValueError("Invalid username or password.")

        # Publish success event (audit only, projection may update last_login)
        event = UserAuthenticationSucceeded(
            user_id=user.id,
            username=user.username,
            role=user.role,
        )
        await self.event_bus.publish(
            self.transport_topic,
            event.model_dump()
        )

        log.info(f"User '{command.username}' authenticated successfully")
        return user.id, user.username, user.role


# -----------------------------------------------------------------------------
# DeleteUserHandler - Event Sourcing Pattern
# -----------------------------------------------------------------------------
@command_handler(DeleteUserAccountCommand)
class DeleteUserHandler(BaseCommandHandler):
    """
    Handles the DeleteUserAccountCommand using Event Sourcing pattern.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.user-account-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: DeleteUserAccountCommand) -> None:
        log.info(f"Deleting user account: {command.user_id}, reason: {command.reason}")

        # Load aggregate from read model to get current version
        user = await self.query_bus.query(
            GetUserProfileQuery(user_id=command.user_id)
        )
        if not user:
            raise ValueError("User not found.")

        # Create aggregate (in production, would load from event store)
        # For now, using simplified approach
        user_aggregate = UserAccountAggregate(user_id=command.user_id)
        # Note: In full Event Sourcing, would replay events here
        # user_aggregate.version = user.version (if available)

        # Call aggregate command method
        user_aggregate.delete(
            reason=command.reason,
            grace_period=command.grace_period
        )

        # Publish events
        await self.publish_and_commit_events(
            aggregate=user_aggregate,
            aggregate_type="UserAccount",
            expected_version=None,  # Simplified for now
        )

        log.info(f"User account deleted (soft): {command.user_id}")


# -----------------------------------------------------------------------------
# VerifyUserEmailHandler - Pure CQRS
# -----------------------------------------------------------------------------
@command_handler(VerifyUserEmailCommand)
class VerifyUserEmailHandler(BaseCommandHandler):
    """Handles the VerifyUserEmailCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.user-account-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

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

        # Create aggregate
        user_aggregate = UserAccountAggregate(user_id=command.user_id)

        # Call aggregate command method
        user_aggregate.verify_email()

        # Publish events
        await self.publish_and_commit_events(
            aggregate=user_aggregate,
            aggregate_type="UserAccount",
            expected_version=None,
        )

        log.info(f"Email verified for user: {command.user_id}")

# =============================================================================
# EOF
# =============================================================================
