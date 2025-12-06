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
    RequestCompanyDeletionCommand,
)
from app.company.aggregate import CompanyAggregate
from app.company.events import CompanyDeleteRequested
# Queries only for Saga enrichment (RequestCompanyDeletionHandler)
from app.company.queries import GetCompanyByIdQuery, GetCompanyTelegramSupergroupsQuery
from app.chat.queries import GetChatsByCompanyQuery, GetChatsByTelegramSupergroupQuery
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.company.command_handlers")


# -----------------------------------------------------------------------------
# CreateCompanyHandler
# -----------------------------------------------------------------------------
@command_handler(CreateCompanyCommand)
class CreateCompanyHandler(BaseCommandHandler):
    """
    Handles the CreateCompanyCommand using pure Event Sourcing.

    Creates a new company aggregate and emits CompanyCreated event.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: CreateCompanyCommand) -> uuid.UUID:
        log.info(f"Creating company: {command.name}")

        # Create aggregate
        company_aggregate = CompanyAggregate(company_id=command.company_id)

        # Call aggregate command method (emits CompanyCreated event)
        # The event will be enriched with saga orchestration context
        company_aggregate.create_company(
            name=command.name,
            client_type=command.client_type,
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
            # Saga orchestration options
            create_telegram_group=command.create_telegram_group,
            telegram_group_title=command.telegram_group_title,
            telegram_group_description=command.telegram_group_description,
            create_chat=command.create_chat,
            link_chat_id=command.link_chat_id,
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
    """
    Handles the UpdateCompanyCommand using pure Event Sourcing.

    Loads company aggregate from Event Store and updates it.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UpdateCompanyCommand) -> uuid.UUID:
        log.info(f"Updating company: {command.company_id}")

        # Load aggregate from Event Store (proper Event Sourcing)
        company_aggregate = await self.load_aggregate(command.company_id, "Company", CompanyAggregate)

        # Verify company exists (version > 0 means events exist)
        if company_aggregate.version == 0:
            raise ValueError(f"Company {command.company_id} not found")

        # Call aggregate command method
        company_aggregate.update_company(
            updated_by=command.updated_by,
            name=command.name,
            client_type=command.client_type,
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

        # Publish events with version tracking
        await self.publish_events(
            aggregate=company_aggregate,
            aggregate_id=command.company_id,
            command=command
        )

        log.info(f"Company updated: {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# ArchiveCompanyHandler
# -----------------------------------------------------------------------------
@command_handler(ArchiveCompanyCommand)
class ArchiveCompanyHandler(BaseCommandHandler):
    """
    Handles the ArchiveCompanyCommand using pure Event Sourcing.

    Loads company from Event Store and archives it.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: ArchiveCompanyCommand) -> uuid.UUID:
        log.info(f"Archiving company: {command.company_id}")

        # Load aggregate from Event Store
        company_aggregate = await self.load_aggregate(command.company_id, "Company", CompanyAggregate)

        # Verify company exists
        if company_aggregate.version == 0:
            raise ValueError(f"Company {command.company_id} not found")

        # Call aggregate command method
        company_aggregate.archive_company(
            archived_by=command.archived_by,
            reason=command.reason,
        )

        # Publish events with version tracking
        await self.publish_events(
            aggregate=company_aggregate,
            aggregate_id=command.company_id,
            command=command
        )

        log.info(f"Company archived: {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# RestoreCompanyHandler
# -----------------------------------------------------------------------------
@command_handler(RestoreCompanyCommand)
class RestoreCompanyHandler(BaseCommandHandler):
    """
    Handles the RestoreCompanyCommand using pure Event Sourcing.

    Loads company from Event Store and restores it.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: RestoreCompanyCommand) -> uuid.UUID:
        log.info(f"Restoring company: {command.company_id}")

        # Load aggregate from Event Store
        company_aggregate = await self.load_aggregate(command.company_id, "Company", CompanyAggregate)

        # Verify company exists
        if company_aggregate.version == 0:
            raise ValueError(f"Company {command.company_id} not found")

        # Call aggregate command method
        company_aggregate.restore_company(restored_by=command.restored_by)

        # Publish events with version tracking
        await self.publish_events(
            aggregate=company_aggregate,
            aggregate_id=command.company_id,
            command=command
        )

        log.info(f"Company restored: {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# DeleteCompanyHandler
# -----------------------------------------------------------------------------
@command_handler(DeleteCompanyCommand)
class DeleteCompanyHandler(BaseCommandHandler):
    """
    Handles the DeleteCompanyCommand using pure Event Sourcing.

    Loads company from Event Store and deletes it.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: DeleteCompanyCommand) -> uuid.UUID:
        log.info(f"Deleting company: {command.company_id}")

        # Load aggregate from Event Store
        company_aggregate = await self.load_aggregate(command.company_id, "Company", CompanyAggregate)

        # Verify company exists
        if company_aggregate.version == 0:
            raise ValueError(f"Company {command.company_id} not found")

        # Call aggregate command method
        # force=True bypasses permission checks for saga-initiated deletions
        company_aggregate.delete_company(deleted_by=command.deleted_by, force=command.force)

        # Check if delete event was generated (idempotency - already deleted?)
        if not company_aggregate.get_uncommitted_events():
            log.info(f"Company {command.company_id} already deleted in EventStore")
            return command.company_id

        # Publish events with proper expected_version from replay
        await self.publish_events(
            aggregate=company_aggregate,
            aggregate_id=command.company_id,
            command=command
        )

        log.info(f"Company deleted: {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# RequestCompanyDeletionHandler - TRUE SAGA Pattern
# EXCEPTION: This handler uses QueryBus for Saga event enrichment.
# -----------------------------------------------------------------------------
@command_handler(RequestCompanyDeletionCommand)
class RequestCompanyDeletionHandler(BaseCommandHandler):
    """
    Handles RequestCompanyDeletionCommand - TRUE SAGA Pattern.

    EXCEPTION TO PURE CQRS: This handler uses QueryBus to enrich the event
    with all data the Saga needs. This is intentional - the Saga should
    receive all data in the event, not query for it.

    Flow:
    1. Query company info (name, telegram_group_id)
    2. Query all chats for company (chat_ids)
    3. Publish ENRICHED CompanyDeleteRequested event
    4. SagaService triggers GroupDeletionSaga with enriched context
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: RequestCompanyDeletionCommand) -> uuid.UUID:
        log.info(f"Processing company deletion request: {command.company_id}")

        # -----------------------------------------------------------------
        # QUERY ALL DATA HERE (NOT in saga!)
        # -----------------------------------------------------------------

        # 1. Get company info
        company = await self.query_bus.query(
            GetCompanyByIdQuery(company_id=command.company_id)
        )
        if not company:
            raise ValueError(f"Company {command.company_id} not found")

        # 2. Get telegram supergroups for this company
        telegram_supergroups = await self.query_bus.query(
            GetCompanyTelegramSupergroupsQuery(company_id=command.company_id)
        )
        # Get first supergroup ID (company typically has one main supergroup)
        telegram_group_id = None
        if telegram_supergroups:
            telegram_group_id = telegram_supergroups[0].telegram_group_id

        # 3. Get all chats for this company
        # FIX: Use both queries to find ALL chats:
        #   - GetChatsByCompanyQuery: finds chats by company_id or via telegram_supergroups.company_id
        #   - GetChatsByTelegramSupergroupQuery: finds chats by telegram_supergroup_id directly
        # This ensures we catch chats created without company_id (e.g., manual topic creation)
        chat_ids_set = set()
        telegram_chats = []  # Initialize for logging

        # 3a. Get chats by company_id
        company_chats = await self.query_bus.query(
            GetChatsByCompanyQuery(
                company_id=command.company_id,
                include_archived=True  # Include archived chats for deletion
            )
        )
        if company_chats:
            chat_ids_set.update(chat.id for chat in company_chats)

        # 3b. Get chats by telegram_supergroup_id (catches chats with NULL company_id)
        if telegram_group_id:
            telegram_chats = await self.query_bus.query(
                GetChatsByTelegramSupergroupQuery(
                    telegram_supergroup_id=telegram_group_id,
                    include_archived=True
                )
            )
            if telegram_chats:
                chat_ids_set.update(chat.id for chat in telegram_chats)

        chat_ids = list(chat_ids_set)

        log.info(
            f"Company deletion request enriched: company={company.name}, "
            f"telegram_group_id={telegram_group_id}, chat_count={len(chat_ids)} "
            f"(company_chats={len(company_chats) if company_chats else 0}, "
            f"telegram_chats={len(telegram_chats) if telegram_chats else 0})"
        )

        # -----------------------------------------------------------------
        # PUBLISH ENRICHED EVENT
        # -----------------------------------------------------------------
        event = CompanyDeleteRequested(
            company_id=command.company_id,
            company_name=company.name,
            deleted_by=command.deleted_by,
            telegram_group_id=telegram_group_id,
            chat_ids=chat_ids,  # ENRICHED!
            cascade=command.cascade,
            preserve_company=command.preserve_company,  # Keep company for re-linking
        )

        # Publish to transport topic for SagaService
        await self.event_bus.publish(
            "transport.company-events",
            event.model_dump(mode='json')
        )

        log.info(
            f"CompanyDeleteRequested event published for: {command.company_id}, "
            f"preserve_company={command.preserve_company}"
        )
        return command.company_id


# =============================================================================
# EOF
# =============================================================================
