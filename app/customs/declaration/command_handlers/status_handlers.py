# =============================================================================
# File: app/customs/declaration/command_handlers/status_handlers.py
# Description: Command handlers for declaration status changes
# Handlers: MarkDeclarationReleased, MarkDeclarationRejected
# =============================================================================

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from app.config.logging_config import get_logger
from app.customs.declaration.commands import (
    MarkDeclarationReleasedCommand,
    MarkDeclarationRejectedCommand,
)
from app.customs.declaration.aggregate import CustomsDeclarationAggregate
from app.customs.exceptions import (
    DeclarationNotFoundError,
    DeclarationNotSubmittedError,
)
from app.customs.enums import DocflowStatus
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.customs.declaration.status_handlers")

# Transport topic for customs events
CUSTOMS_TRANSPORT_TOPIC = "transport.customs-events"


# -----------------------------------------------------------------------------
# MarkDeclarationReleasedHandler
# -----------------------------------------------------------------------------
@command_handler(MarkDeclarationReleasedCommand)
class MarkDeclarationReleasedHandler(BaseCommandHandler):
    """
    Handles the MarkDeclarationReleasedCommand.

    Marks declaration as released by customs. This is typically triggered
    by the status sync worker when Kontur reports RELEASED status, or
    can be used for manual status override.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: MarkDeclarationReleasedCommand) -> uuid.UUID:
        log.info(
            f"Marking declaration {command.declaration_id} as RELEASED "
            f"(gtd={command.gtd_number})"
        )

        # Load aggregate from Event Store
        declaration = await self.load_aggregate(
            command.declaration_id,
            "CustomsDeclaration",
            CustomsDeclarationAggregate
        )

        # Verify declaration exists
        if declaration.version == 0:
            raise DeclarationNotFoundError(
                f"Declaration {command.declaration_id} not found"
            )

        # Verify declaration is submitted to Kontur
        if not declaration.state.kontur_docflow_id:
            raise DeclarationNotSubmittedError(
                f"Declaration {command.declaration_id} must be submitted to Kontur "
                "before marking as released"
            )

        # Verify kontur_docflow_id matches
        if declaration.state.kontur_docflow_id != command.kontur_docflow_id:
            log.warning(
                f"Docflow ID mismatch: expected {declaration.state.kontur_docflow_id}, "
                f"got {command.kontur_docflow_id}"
            )

        # Check if already in final status (idempotent)
        if declaration.state.status == DocflowStatus.RELEASED:
            log.info(f"Declaration {command.declaration_id} already RELEASED")
            return command.declaration_id

        # Update status using aggregate method
        declaration.update_status_from_kontur(
            kontur_docflow_id=command.kontur_docflow_id,
            new_status=DocflowStatus.RELEASED,
            gtd_number=command.gtd_number,
        )

        # Publish events
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(f"Declaration {command.declaration_id} marked as RELEASED")
        return command.declaration_id


# -----------------------------------------------------------------------------
# MarkDeclarationRejectedHandler
# -----------------------------------------------------------------------------
@command_handler(MarkDeclarationRejectedCommand)
class MarkDeclarationRejectedHandler(BaseCommandHandler):
    """
    Handles the MarkDeclarationRejectedCommand.

    Marks declaration as rejected by customs. This is typically triggered
    by the status sync worker when Kontur reports REJECTED status, or
    can be used for manual status override.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: MarkDeclarationRejectedCommand) -> uuid.UUID:
        log.info(
            f"Marking declaration {command.declaration_id} as REJECTED "
            f"(reason={command.rejection_reason})"
        )

        # Load aggregate from Event Store
        declaration = await self.load_aggregate(
            command.declaration_id,
            "CustomsDeclaration",
            CustomsDeclarationAggregate
        )

        # Verify declaration exists
        if declaration.version == 0:
            raise DeclarationNotFoundError(
                f"Declaration {command.declaration_id} not found"
            )

        # Verify declaration is submitted to Kontur
        if not declaration.state.kontur_docflow_id:
            raise DeclarationNotSubmittedError(
                f"Declaration {command.declaration_id} must be submitted to Kontur "
                "before marking as rejected"
            )

        # Verify kontur_docflow_id matches
        if declaration.state.kontur_docflow_id != command.kontur_docflow_id:
            log.warning(
                f"Docflow ID mismatch: expected {declaration.state.kontur_docflow_id}, "
                f"got {command.kontur_docflow_id}"
            )

        # Check if already in final status (idempotent)
        if declaration.state.status == DocflowStatus.REJECTED:
            log.info(f"Declaration {command.declaration_id} already REJECTED")
            return command.declaration_id

        # Update status using aggregate method
        declaration.update_status_from_kontur(
            kontur_docflow_id=command.kontur_docflow_id,
            new_status=DocflowStatus.REJECTED,
            gtd_number=None,  # No GTD on rejection
        )

        # Publish events
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(f"Declaration {command.declaration_id} marked as REJECTED")
        return command.declaration_id


# =============================================================================
# EOF
# =============================================================================
