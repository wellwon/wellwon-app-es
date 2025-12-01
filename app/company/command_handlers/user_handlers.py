# =============================================================================
# File: app/company/command_handlers/user_handlers.py
# Description: Company user relationship command handlers
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
from app.company.queries import GetCompanyByIdQuery
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
    """Handles the AddUserToCompanyCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: AddUserToCompanyCommand) -> uuid.UUID:
        log.info(f"Adding user {command.user_id} to company {command.company_id}")

        # Verify company exists
        company = await self.query_bus.query(
            GetCompanyByIdQuery(company_id=command.company_id)
        )
        if not company:
            raise ValueError(f"Company {command.company_id} not found")

        # Create aggregate
        company_aggregate = CompanyAggregate(company_id=command.company_id)

        # Call aggregate command method
        company_aggregate.add_user(
            user_id=command.user_id,
            relationship_type=command.relationship_type,
            added_by=command.added_by,
        )

        # Publish events
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=None,
        )

        log.info(f"User {command.user_id} added to company {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# RemoveUserFromCompanyHandler
# -----------------------------------------------------------------------------
@command_handler(RemoveUserFromCompanyCommand)
class RemoveUserFromCompanyHandler(BaseCommandHandler):
    """Handles the RemoveUserFromCompanyCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: RemoveUserFromCompanyCommand) -> uuid.UUID:
        log.info(f"Removing user {command.user_id} from company {command.company_id}")

        # Verify company exists
        company = await self.query_bus.query(
            GetCompanyByIdQuery(company_id=command.company_id)
        )
        if not company:
            raise ValueError(f"Company {command.company_id} not found")

        # Create aggregate
        company_aggregate = CompanyAggregate(company_id=command.company_id)

        # Call aggregate command method
        company_aggregate.remove_user(
            user_id=command.user_id,
            removed_by=command.removed_by,
            reason=command.reason,
        )

        # Publish events
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=None,
        )

        log.info(f"User {command.user_id} removed from company {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# ChangeUserCompanyRoleHandler
# -----------------------------------------------------------------------------
@command_handler(ChangeUserCompanyRoleCommand)
class ChangeUserCompanyRoleHandler(BaseCommandHandler):
    """Handles the ChangeUserCompanyRoleCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: ChangeUserCompanyRoleCommand) -> uuid.UUID:
        log.info(f"Changing role for user {command.user_id} in company {command.company_id}")

        # Verify company exists
        company = await self.query_bus.query(
            GetCompanyByIdQuery(company_id=command.company_id)
        )
        if not company:
            raise ValueError(f"Company {command.company_id} not found")

        # Create aggregate
        company_aggregate = CompanyAggregate(company_id=command.company_id)

        # Call aggregate command method
        company_aggregate.change_user_role(
            user_id=command.user_id,
            new_relationship_type=command.new_relationship_type,
            changed_by=command.changed_by,
        )

        # Publish events
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=None,
        )

        log.info(f"User {command.user_id} role changed in company {command.company_id}")
        return command.company_id
