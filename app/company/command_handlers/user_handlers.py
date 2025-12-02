# =============================================================================
# File: app/company/command_handlers/user_handlers.py
# Description: Company user relationship command handlers (pure Event Sourcing)
# Handlers: AddUser, RemoveUser, ChangeRole
# =============================================================================

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.config.logging_config import get_logger
from app.company.commands import (
    AddUserToCompanyCommand,
    RemoveUserFromCompanyCommand,
    ChangeUserCompanyRoleCommand,
)
from app.company.aggregate import CompanyAggregate
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.company.command_handlers.user")


# -----------------------------------------------------------------------------
# AddUserToCompanyHandler
# -----------------------------------------------------------------------------
@command_handler(AddUserToCompanyCommand)
class AddUserToCompanyHandler(BaseCommandHandler):
    """
    Handles the AddUserToCompanyCommand using pure Event Sourcing.

    Loads company from Event Store and adds user relationship.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: AddUserToCompanyCommand) -> uuid.UUID:
        log.info(f"Adding user {command.user_id} to company {command.company_id}")

        # Load aggregate from Event Store
        company_aggregate = await self.load_aggregate(command.company_id, "Company", CompanyAggregate)

        # Verify company exists
        if company_aggregate.version == 0:
            raise ValueError(f"Company {command.company_id} not found")

        # Call aggregate command method
        company_aggregate.add_user(
            user_id=command.user_id,
            relationship_type=command.relationship_type,
            added_by=command.added_by,
        )

        # Publish events with version tracking
        await self.publish_events(
            aggregate=company_aggregate,
            aggregate_id=command.company_id,
            command=command
        )

        log.info(f"User {command.user_id} added to company {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# RemoveUserFromCompanyHandler
# -----------------------------------------------------------------------------
@command_handler(RemoveUserFromCompanyCommand)
class RemoveUserFromCompanyHandler(BaseCommandHandler):
    """
    Handles the RemoveUserFromCompanyCommand using pure Event Sourcing.

    Loads company from Event Store and removes user relationship.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: RemoveUserFromCompanyCommand) -> uuid.UUID:
        log.info(f"Removing user {command.user_id} from company {command.company_id}")

        # Load aggregate from Event Store
        company_aggregate = await self.load_aggregate(command.company_id, "Company", CompanyAggregate)

        # Verify company exists
        if company_aggregate.version == 0:
            raise ValueError(f"Company {command.company_id} not found")

        # Call aggregate command method
        company_aggregate.remove_user(
            user_id=command.user_id,
            removed_by=command.removed_by,
            reason=command.reason,
        )

        # Publish events with version tracking
        await self.publish_events(
            aggregate=company_aggregate,
            aggregate_id=command.company_id,
            command=command
        )

        log.info(f"User {command.user_id} removed from company {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# ChangeUserCompanyRoleHandler
# -----------------------------------------------------------------------------
@command_handler(ChangeUserCompanyRoleCommand)
class ChangeUserCompanyRoleHandler(BaseCommandHandler):
    """
    Handles the ChangeUserCompanyRoleCommand using pure Event Sourcing.

    Loads company from Event Store and changes user role.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: ChangeUserCompanyRoleCommand) -> uuid.UUID:
        log.info(f"Changing role for user {command.user_id} in company {command.company_id}")

        # Load aggregate from Event Store
        company_aggregate = await self.load_aggregate(command.company_id, "Company", CompanyAggregate)

        # Verify company exists
        if company_aggregate.version == 0:
            raise ValueError(f"Company {command.company_id} not found")

        # Call aggregate command method
        company_aggregate.change_user_role(
            user_id=command.user_id,
            new_relationship_type=command.new_relationship_type,
            changed_by=command.changed_by,
        )

        # Publish events with version tracking
        await self.publish_events(
            aggregate=company_aggregate,
            aggregate_id=command.company_id,
            command=command
        )

        log.info(f"User {command.user_id} role changed in company {command.company_id}")
        return command.company_id
