# =============================================================================
# File: app/customs/declaration/command_handlers/lifecycle_handlers.py
# Description: Command handlers for declaration lifecycle (Create, Delete, Copy)
# Handlers: CreateCustomsDeclaration, DeleteCustomsDeclaration, CopyCustomsDeclaration
# =============================================================================

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from app.config.logging_config import get_logger
from app.customs.declaration.commands import (
    CreateCustomsDeclarationCommand,
    DeleteCustomsDeclarationCommand,
    CopyCustomsDeclarationCommand,
)
from app.customs.declaration.aggregate import CustomsDeclarationAggregate
from app.customs.exceptions import DeclarationNotFoundError
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.customs.declaration.lifecycle_handlers")

# Transport topic for customs events
CUSTOMS_TRANSPORT_TOPIC = "transport.customs-events"


# -----------------------------------------------------------------------------
# CreateCustomsDeclarationHandler
# -----------------------------------------------------------------------------
@command_handler(CreateCustomsDeclarationCommand)
class CreateCustomsDeclarationHandler(BaseCommandHandler):
    """
    Handles the CreateCustomsDeclarationCommand.

    Creates a new customs declaration aggregate and emits CustomsDeclarationCreated event.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: CreateCustomsDeclarationCommand) -> uuid.UUID:
        log.info(
            f"Creating customs declaration: {command.name} "
            f"(type={command.declaration_type.value}, procedure={command.procedure})"
        )

        # Create new aggregate
        declaration = CustomsDeclarationAggregate(declaration_id=command.declaration_id)

        # Call aggregate command method
        declaration.create_declaration(
            user_id=command.user_id,
            company_id=command.company_id,
            name=command.name,
            declaration_type=command.declaration_type,
            procedure=command.procedure,
            customs_code=command.customs_code,
            organization_id=command.organization_id,
            employee_id=command.employee_id,
        )

        # Publish events
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(f"Customs declaration created: {command.declaration_id}")
        return command.declaration_id


# -----------------------------------------------------------------------------
# DeleteCustomsDeclarationHandler
# -----------------------------------------------------------------------------
@command_handler(DeleteCustomsDeclarationCommand)
class DeleteCustomsDeclarationHandler(BaseCommandHandler):
    """
    Handles the DeleteCustomsDeclarationCommand.

    Soft-deletes a customs declaration (only if in DRAFT status).
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: DeleteCustomsDeclarationCommand) -> uuid.UUID:
        log.info(f"Deleting customs declaration: {command.declaration_id}")

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

        # Call aggregate command method
        declaration.delete_declaration(
            user_id=command.user_id,
            reason=command.reason,
        )

        # Publish events
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(f"Customs declaration deleted: {command.declaration_id}")
        return command.declaration_id


# -----------------------------------------------------------------------------
# CopyCustomsDeclarationHandler
# -----------------------------------------------------------------------------
@command_handler(CopyCustomsDeclarationCommand)
class CopyCustomsDeclarationHandler(BaseCommandHandler):
    """
    Handles the CopyCustomsDeclarationCommand.

    Creates a new declaration as a copy from an existing one (template pattern).
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: CopyCustomsDeclarationCommand) -> uuid.UUID:
        log.info(
            f"Copying customs declaration from {command.source_declaration_id} "
            f"to {command.new_declaration_id}"
        )

        # Load source aggregate to get data to copy
        source = await self.load_aggregate(
            command.source_declaration_id,
            "CustomsDeclaration",
            CustomsDeclarationAggregate
        )

        # Verify source exists
        if source.version == 0:
            raise DeclarationNotFoundError(
                f"Source declaration {command.source_declaration_id} not found"
            )

        # Create new aggregate as copy
        new_declaration = CustomsDeclarationAggregate(
            declaration_id=command.new_declaration_id
        )

        # Prepare data to copy based on options
        form_data = source.state.form_data if command.copy_form_data else {}
        documents = source.state.documents if command.copy_documents else []

        # Call aggregate command method
        new_declaration.create_as_copy(
            source_declaration_id=command.source_declaration_id,
            user_id=command.user_id,
            company_id=source.state.company_id,
            name=command.new_name,
            declaration_type=source.state.declaration_type,
            procedure=source.state.procedure,
            customs_code=source.state.customs_code,
            organization_id=source.state.organization_id,
            employee_id=source.state.employee_id,
            form_data=form_data,
            documents=documents,
        )

        # Publish events
        await self.publish_events(
            aggregate=new_declaration,
            aggregate_id=command.new_declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(f"Customs declaration copied: {command.new_declaration_id}")
        return command.new_declaration_id


# =============================================================================
# EOF
# =============================================================================
