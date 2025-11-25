# =============================================================================
# File: app/company/command_handlers/company_handlers.py
# Description: Company lifecycle command handlers
# Handlers: Create, Update, Archive, Restore, Delete
# =============================================================================

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.config.logging_config import get_logger
from app.company.commands import (
    CreateCompanyCommand,
    UpdateCompanyCommand,
    ArchiveCompanyCommand,
    RestoreCompanyCommand,
    DeleteCompanyCommand,
)
from app.company.aggregate import CompanyAggregate
from app.infra.cqrs.decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.company.command_handlers")


# -----------------------------------------------------------------------------
# CreateCompanyHandler
# -----------------------------------------------------------------------------
@command_handler(CreateCompanyCommand)
class CreateCompanyHandler(BaseCommandHandler):
    """Handles the CreateCompanyCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: CreateCompanyCommand) -> uuid.UUID:
        log.info(f"Creating company: {command.name}")

        # Create aggregate
        company_aggregate = CompanyAggregate(company_id=command.company_id)

        # Call aggregate command method (emits CompanyCreated event)
        company_aggregate.create_company(
            name=command.name,
            company_type=command.company_type,
            created_by=command.created_by,
            vat=command.vat,
            ogrn=command.ogrn,
            kpp=command.kpp,
            postal_code=command.postal_code,
            country_id=command.country_id,
            city=command.city,
            street=command.street,
            director=command.director,
            email=command.email,
            phone=command.phone,
            tg_dir=command.tg_dir,
            tg_accountant=command.tg_accountant,
            tg_manager_1=command.tg_manager_1,
            tg_manager_2=command.tg_manager_2,
            tg_manager_3=command.tg_manager_3,
            tg_support=command.tg_support,
        )

        # Auto-add creator as owner
        company_aggregate.add_user(
            user_id=command.created_by,
            relationship_type="owner",
            added_by=command.created_by,
        )

        # Publish events to EventStore + Transport
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=None,  # New aggregate
        )

        log.info(f"Company created with ID: {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# UpdateCompanyHandler
# -----------------------------------------------------------------------------
@command_handler(UpdateCompanyCommand)
class UpdateCompanyHandler(BaseCommandHandler):
    """Handles the UpdateCompanyCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UpdateCompanyCommand) -> uuid.UUID:
        log.info(f"Updating company: {command.company_id}")

        # Load aggregate from event store
        company_aggregate = await self.load_aggregate(
            aggregate_type="Company",
            aggregate_id=command.company_id,
            aggregate_class=CompanyAggregate,
        )

        # Call aggregate command method
        company_aggregate.update_company(
            updated_by=command.updated_by,
            name=command.name,
            company_type=command.company_type,
            vat=command.vat,
            ogrn=command.ogrn,
            kpp=command.kpp,
            postal_code=command.postal_code,
            country_id=command.country_id,
            city=command.city,
            street=command.street,
            director=command.director,
            email=command.email,
            phone=command.phone,
            tg_dir=command.tg_dir,
            tg_accountant=command.tg_accountant,
            tg_manager_1=command.tg_manager_1,
            tg_manager_2=command.tg_manager_2,
            tg_manager_3=command.tg_manager_3,
            tg_support=command.tg_support,
        )

        # Publish events
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=company_aggregate.version - 1,
        )

        log.info(f"Company updated: {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# ArchiveCompanyHandler
# -----------------------------------------------------------------------------
@command_handler(ArchiveCompanyCommand)
class ArchiveCompanyHandler(BaseCommandHandler):
    """Handles the ArchiveCompanyCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: ArchiveCompanyCommand) -> uuid.UUID:
        log.info(f"Archiving company: {command.company_id}")

        # Load aggregate from event store
        company_aggregate = await self.load_aggregate(
            aggregate_type="Company",
            aggregate_id=command.company_id,
            aggregate_class=CompanyAggregate,
        )

        # Call aggregate command method
        company_aggregate.archive_company(
            archived_by=command.archived_by,
            reason=command.reason,
        )

        # Publish events
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=company_aggregate.version - 1,
        )

        log.info(f"Company archived: {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# RestoreCompanyHandler
# -----------------------------------------------------------------------------
@command_handler(RestoreCompanyCommand)
class RestoreCompanyHandler(BaseCommandHandler):
    """Handles the RestoreCompanyCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: RestoreCompanyCommand) -> uuid.UUID:
        log.info(f"Restoring company: {command.company_id}")

        # Load aggregate from event store
        company_aggregate = await self.load_aggregate(
            aggregate_type="Company",
            aggregate_id=command.company_id,
            aggregate_class=CompanyAggregate,
        )

        # Call aggregate command method
        company_aggregate.restore_company(restored_by=command.restored_by)

        # Publish events
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=company_aggregate.version - 1,
        )

        log.info(f"Company restored: {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# DeleteCompanyHandler
# -----------------------------------------------------------------------------
@command_handler(DeleteCompanyCommand)
class DeleteCompanyHandler(BaseCommandHandler):
    """Handles the DeleteCompanyCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: DeleteCompanyCommand) -> uuid.UUID:
        log.info(f"Deleting company: {command.company_id}")

        # Load aggregate from event store
        company_aggregate = await self.load_aggregate(
            aggregate_type="Company",
            aggregate_id=command.company_id,
            aggregate_class=CompanyAggregate,
        )

        # Call aggregate command method
        company_aggregate.delete_company(deleted_by=command.deleted_by)

        # Publish events
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=company_aggregate.version - 1,
        )

        log.info(f"Company deleted: {command.company_id}")
        return command.company_id
