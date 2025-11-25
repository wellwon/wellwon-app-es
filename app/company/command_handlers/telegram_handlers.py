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
)
from app.company.aggregate import CompanyAggregate
from app.infra.cqrs.decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.company.command_handlers.telegram")


# -----------------------------------------------------------------------------
# CreateTelegramSupergroupHandler
# -----------------------------------------------------------------------------
@command_handler(CreateTelegramSupergroupCommand)
class CreateTelegramSupergroupHandler(BaseCommandHandler):
    """Handles the CreateTelegramSupergroupCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: CreateTelegramSupergroupCommand) -> uuid.UUID:
        log.info(f"Creating Telegram supergroup for company {command.company_id}")

        # Load aggregate from event store
        company_aggregate = await self.load_aggregate(
            aggregate_type="Company",
            aggregate_id=command.company_id,
            aggregate_class=CompanyAggregate,
        )

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

        # Publish events
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=company_aggregate.version - 1,
        )

        log.info(f"Telegram supergroup {command.telegram_group_id} created for company {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# LinkTelegramSupergroupHandler
# -----------------------------------------------------------------------------
@command_handler(LinkTelegramSupergroupCommand)
class LinkTelegramSupergroupHandler(BaseCommandHandler):
    """Handles the LinkTelegramSupergroupCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: LinkTelegramSupergroupCommand) -> uuid.UUID:
        log.info(f"Linking Telegram supergroup {command.telegram_group_id} to company {command.company_id}")

        # Load aggregate from event store
        company_aggregate = await self.load_aggregate(
            aggregate_type="Company",
            aggregate_id=command.company_id,
            aggregate_class=CompanyAggregate,
        )

        # Call aggregate command method
        company_aggregate.link_telegram_supergroup(
            telegram_group_id=command.telegram_group_id,
            linked_by=command.linked_by,
        )

        # Publish events
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=company_aggregate.version - 1,
        )

        log.info(f"Telegram supergroup {command.telegram_group_id} linked to company {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# UnlinkTelegramSupergroupHandler
# -----------------------------------------------------------------------------
@command_handler(UnlinkTelegramSupergroupCommand)
class UnlinkTelegramSupergroupHandler(BaseCommandHandler):
    """Handles the UnlinkTelegramSupergroupCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UnlinkTelegramSupergroupCommand) -> uuid.UUID:
        log.info(f"Unlinking Telegram supergroup {command.telegram_group_id} from company {command.company_id}")

        # Load aggregate from event store
        company_aggregate = await self.load_aggregate(
            aggregate_type="Company",
            aggregate_id=command.company_id,
            aggregate_class=CompanyAggregate,
        )

        # Call aggregate command method
        company_aggregate.unlink_telegram_supergroup(
            telegram_group_id=command.telegram_group_id,
            unlinked_by=command.unlinked_by,
        )

        # Publish events
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=company_aggregate.version - 1,
        )

        log.info(f"Telegram supergroup {command.telegram_group_id} unlinked from company {command.company_id}")
        return command.company_id


# -----------------------------------------------------------------------------
# UpdateTelegramSupergroupHandler
# -----------------------------------------------------------------------------
@command_handler(UpdateTelegramSupergroupCommand)
class UpdateTelegramSupergroupHandler(BaseCommandHandler):
    """Handles the UpdateTelegramSupergroupCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UpdateTelegramSupergroupCommand) -> uuid.UUID:
        log.info(f"Updating Telegram supergroup {command.telegram_group_id} for company {command.company_id}")

        # Load aggregate from event store
        company_aggregate = await self.load_aggregate(
            aggregate_type="Company",
            aggregate_id=command.company_id,
            aggregate_class=CompanyAggregate,
        )

        # Call aggregate command method
        company_aggregate.update_telegram_supergroup(
            telegram_group_id=command.telegram_group_id,
            title=command.title,
            description=command.description,
            invite_link=command.invite_link,
        )

        # Publish events
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=company_aggregate.version - 1,
        )

        log.info(f"Telegram supergroup {command.telegram_group_id} updated for company {command.company_id}")
        return command.company_id
