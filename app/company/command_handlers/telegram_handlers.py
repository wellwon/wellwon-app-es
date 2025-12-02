# =============================================================================
# File: app/company/command_handlers/telegram_handlers.py
# Description: Company Telegram supergroup command handlers
# Handlers: CreateSupergroup, LinkSupergroup, UnlinkSupergroup, UpdateSupergroup
# =============================================================================

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.config.logging_config import get_logger
from app.company.commands import (
    CreateTelegramSupergroupCommand,
    LinkTelegramSupergroupCommand,
    UnlinkTelegramSupergroupCommand,
    UpdateTelegramSupergroupCommand,
    DeleteTelegramSupergroupCommand,
)
from app.company.aggregate import CompanyAggregate
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.company.command_handlers.telegram")


# -----------------------------------------------------------------------------
# CreateTelegramSupergroupHandler
# -----------------------------------------------------------------------------
@command_handler(CreateTelegramSupergroupCommand)
class CreateTelegramSupergroupHandler(BaseCommandHandler):
    """
    Handles the CreateTelegramSupergroupCommand using Event Sourcing pattern.

    TRUE SAGA: No queries to read models - all data comes via command from enriched event.
    Simply appends events to company's event stream.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: CreateTelegramSupergroupCommand) -> uuid.UUID:
        log.info(f"Creating Telegram supergroup for company {command.company_id}")

        # Create aggregate - no query needed, data comes from saga via enriched event
        company_aggregate = CompanyAggregate(company_id=command.company_id)

        # Call aggregate command method
        company_aggregate.create_telegram_supergroup(
            telegram_group_id=command.telegram_group_id,
            title=command.title,
            username=command.username,
            description=command.description,
            invite_link=command.invite_link,
            is_forum=command.is_forum,
            created_by=command.created_by,
        )

        # Publish events - append to existing company stream
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=None,
        )

        log.info(f"Telegram supergroup {command.telegram_group_id} created for company {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# LinkTelegramSupergroupHandler
# -----------------------------------------------------------------------------
@command_handler(LinkTelegramSupergroupCommand)
class LinkTelegramSupergroupHandler(BaseCommandHandler):
    """
    Handles the LinkTelegramSupergroupCommand using Event Sourcing pattern.
    TRUE SAGA: No queries - all data via command.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: LinkTelegramSupergroupCommand) -> uuid.UUID:
        log.info(f"Linking Telegram supergroup {command.telegram_group_id} to company {command.company_id}")

        company_aggregate = CompanyAggregate(company_id=command.company_id)

        company_aggregate.link_telegram_supergroup(
            telegram_group_id=command.telegram_group_id,
            linked_by=command.linked_by,
        )

        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=None,
        )

        log.info(f"Telegram supergroup {command.telegram_group_id} linked to company {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# UnlinkTelegramSupergroupHandler
# -----------------------------------------------------------------------------
@command_handler(UnlinkTelegramSupergroupCommand)
class UnlinkTelegramSupergroupHandler(BaseCommandHandler):
    """
    Handles the UnlinkTelegramSupergroupCommand using Event Sourcing pattern.
    TRUE SAGA: No queries - all data via command.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UnlinkTelegramSupergroupCommand) -> uuid.UUID:
        log.info(f"Unlinking Telegram supergroup {command.telegram_group_id} from company {command.company_id}")

        company_aggregate = CompanyAggregate(company_id=command.company_id)

        company_aggregate.unlink_telegram_supergroup(
            telegram_group_id=command.telegram_group_id,
            unlinked_by=command.unlinked_by,
        )

        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=None,
        )

        log.info(f"Telegram supergroup {command.telegram_group_id} unlinked from company {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# UpdateTelegramSupergroupHandler
# -----------------------------------------------------------------------------
@command_handler(UpdateTelegramSupergroupCommand)
class UpdateTelegramSupergroupHandler(BaseCommandHandler):
    """
    Handles the UpdateTelegramSupergroupCommand using Event Sourcing pattern.
    TRUE SAGA: No queries - all data via command.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UpdateTelegramSupergroupCommand) -> uuid.UUID:
        log.info(f"Updating Telegram supergroup {command.telegram_group_id} for company {command.company_id}")

        company_aggregate = CompanyAggregate(company_id=command.company_id)

        company_aggregate.update_telegram_supergroup(
            telegram_group_id=command.telegram_group_id,
            title=command.title,
            description=command.description,
            invite_link=command.invite_link,
        )

        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=None,
        )

        log.info(f"Telegram supergroup {command.telegram_group_id} updated for company {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# DeleteTelegramSupergroupHandler
# -----------------------------------------------------------------------------
@command_handler(DeleteTelegramSupergroupCommand)
class DeleteTelegramSupergroupHandler(BaseCommandHandler):
    """
    Handles the DeleteTelegramSupergroupCommand using pure Event Sourcing.

    company_id comes from command (enriched by router).
    If no company_id, uses synthetic UUID for orphaned supergroup deletion.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: DeleteTelegramSupergroupCommand) -> int:
        log.info(f"Deleting Telegram supergroup {command.telegram_group_id}")

        # Get company_id from command (enriched by router) or use synthetic UUID
        company_id = command.company_id
        aggregate_company_id = company_id if company_id else uuid.uuid4()

        # Load or create aggregate
        if company_id:
            company_aggregate = await self.load_aggregate(company_id, "Company", CompanyAggregate)
        else:
            # Orphaned supergroup - create new aggregate for event publishing
            company_aggregate = CompanyAggregate(company_id=aggregate_company_id)

        company_aggregate.delete_telegram_supergroup(
            telegram_group_id=command.telegram_group_id,
            company_id=company_id,
            deleted_by=command.deleted_by,
            reason=command.reason,
        )

        # Publish events
        if company_id:
            await self.publish_events(
                aggregate=company_aggregate,
                aggregate_id=company_id,
                command=command
            )
        else:
            await self.publish_and_commit_events(
                aggregate=company_aggregate,
                aggregate_type="Company",
                expected_version=None,
            )

        log.info(f"Telegram supergroup {command.telegram_group_id} deleted")
        return command.telegram_group_id
