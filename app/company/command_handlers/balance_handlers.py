# =============================================================================
# File: app/company/command_handlers/balance_handlers.py
# Description: Company balance command handlers
# Handlers: UpdateBalance
# =============================================================================

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.config.logging_config import get_logger
from app.company.commands import UpdateCompanyBalanceCommand
from app.company.aggregate import CompanyAggregate
from app.infra.cqrs.decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.company.command_handlers.balance")


# -----------------------------------------------------------------------------
# UpdateCompanyBalanceHandler
# -----------------------------------------------------------------------------
@command_handler(UpdateCompanyBalanceCommand)
class UpdateCompanyBalanceHandler(BaseCommandHandler):
    """Handles the UpdateCompanyBalanceCommand using Event Sourcing pattern."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.company-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UpdateCompanyBalanceCommand) -> uuid.UUID:
        log.info(
            f"Updating balance for company {command.company_id}: "
            f"{command.change_amount} ({command.reason})"
        )

        # Load aggregate from event store
        company_aggregate = await self.load_aggregate(
            aggregate_type="Company",
            aggregate_id=command.company_id,
            aggregate_class=CompanyAggregate,
        )

        # Call aggregate command method
        company_aggregate.update_balance(
            change_amount=command.change_amount,
            reason=command.reason,
            reference_id=command.reference_id,
            updated_by=command.updated_by,
        )

        # Publish events
        await self.publish_and_commit_events(
            aggregate=company_aggregate,
            aggregate_type="Company",
            expected_version=company_aggregate.version - 1,
        )

        log.info(f"Balance updated for company {command.company_id}")
        return command.company_id
