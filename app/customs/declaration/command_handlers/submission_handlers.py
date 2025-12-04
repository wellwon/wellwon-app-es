# =============================================================================
# File: app/customs/declaration/command_handlers/submission_handlers.py
# Description: Command handlers for Kontur submission and status sync
# Handlers: SubmitToKontur, SyncStatusFromKontur, RefreshStatusFromKontur
# =============================================================================

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from app.config.logging_config import get_logger
from app.customs.declaration.commands import (
    SubmitToKonturCommand,
    SyncStatusFromKonturCommand,
    RefreshStatusFromKonturCommand,
)
from app.customs.declaration.aggregate import CustomsDeclarationAggregate
from app.customs.exceptions import (
    DeclarationNotFoundError,
    DeclarationAlreadySubmittedError,
    KonturSyncError,
    InvalidDeclarationStatusError,
)
from app.customs.enums import DocflowStatus
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler
from app.infra.kontur.adapter import get_kontur_adapter
from app.infra.kontur.models import CreateDocflowRequest

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.customs.declaration.submission_handlers")

# Transport topic for customs events
CUSTOMS_TRANSPORT_TOPIC = "transport.customs-events"


# -----------------------------------------------------------------------------
# SubmitToKonturHandler
# -----------------------------------------------------------------------------
@command_handler(SubmitToKonturCommand)
class SubmitToKonturHandler(BaseCommandHandler):
    """
    Handles the SubmitToKonturCommand.

    Creates a new docflow in Kontur and updates the aggregate with the
    kontur_docflow_id. Emits CustomsDeclarationSubmitted event which
    triggers the submission saga for subsequent operations (form import,
    document upload, organization setting).

    TRUE SAGA Pattern: Event contains all enriched data needed by saga.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: SubmitToKonturCommand) -> uuid.UUID:
        log.info(f"Submitting declaration {command.declaration_id} to Kontur")

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

        # Verify not already submitted
        if declaration.state.kontur_docflow_id:
            raise DeclarationAlreadySubmittedError(
                f"Declaration {command.declaration_id} already submitted "
                f"with docflow ID: {declaration.state.kontur_docflow_id}"
            )

        # Verify declaration is in DRAFT status
        if declaration.state.status != DocflowStatus.DRAFT:
            raise InvalidDeclarationStatusError(
                f"Cannot submit declaration in status {declaration.state.status.name}. "
                f"Only DRAFT declarations can be submitted."
            )

        # Validate required fields for Kontur
        if not declaration.state.organization_id:
            raise InvalidDeclarationStatusError(
                "Organization ID is required to submit declaration to Kontur"
            )
        if not declaration.state.employee_id:
            raise InvalidDeclarationStatusError(
                "Employee ID is required to submit declaration to Kontur"
            )

        # Get Kontur adapter
        adapter = await get_kontur_adapter()

        # Create docflow request
        create_request = CreateDocflowRequest(
            type=declaration.state.declaration_type.value,
            procedure=declaration.state.procedure,
            customs=declaration.state.customs_code,
            organization_id=declaration.state.organization_id,
            employee_id=declaration.state.employee_id,
            name=declaration.state.name,
        )

        # Call Kontur API
        try:
            docflow = await adapter.create_docflow(create_request)
            if not docflow:
                raise KonturSyncError("Kontur returned empty docflow response")
        except Exception as e:
            log.error(f"Failed to create docflow in Kontur: {e}")
            # Record sync failure
            declaration.mark_sync_failed(
                error_message=str(e),
            )
            await self.publish_events(
                aggregate=declaration,
                aggregate_id=command.declaration_id,
                command=command,
                aggregate_type="CustomsDeclaration"
            )
            raise KonturSyncError(f"Failed to create docflow: {e}") from e

        log.info(f"Created Kontur docflow: {docflow.id} for declaration {command.declaration_id}")

        # Update aggregate with kontur_docflow_id (emits enriched event for saga)
        declaration.submit_to_kontur(
            user_id=command.user_id,
            kontur_docflow_id=docflow.id,
            form_data=declaration.state.form_data,
            documents=declaration.state.documents,
            organization_id=declaration.state.organization_id,
            organization_inn=declaration.state.declarant_inn,
        )

        # Publish events
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(f"Declaration {command.declaration_id} submitted to Kontur successfully")
        return command.declaration_id


# -----------------------------------------------------------------------------
# SyncStatusFromKonturHandler
# -----------------------------------------------------------------------------
@command_handler(SyncStatusFromKonturCommand)
class SyncStatusFromKonturHandler(BaseCommandHandler):
    """
    Handles the SyncStatusFromKonturCommand.

    Updates aggregate state when Kontur status changes (typically called by
    the background status sync worker). Also emits additional events for
    significant status changes (REGISTERED with GTD, RELEASED, REJECTED).
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: SyncStatusFromKonturCommand) -> uuid.UUID:
        log.info(
            f"Syncing status from Kontur for declaration {command.declaration_id}: "
            f"new_status={command.new_status.name}, gtd={command.gtd_number}"
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

        # Verify kontur_docflow_id matches
        if declaration.state.kontur_docflow_id != command.kontur_docflow_id:
            log.warning(
                f"Docflow ID mismatch: expected {declaration.state.kontur_docflow_id}, "
                f"got {command.kontur_docflow_id}"
            )

        # Update status (idempotent - aggregate checks for duplicate)
        declaration.update_status_from_kontur(
            kontur_docflow_id=command.kontur_docflow_id,
            new_status=command.new_status,
            gtd_number=command.gtd_number,
        )

        # Publish events (may include StatusUpdatedFromKontur + DeclarationRegistered/Released/Rejected)
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(
            f"Declaration {command.declaration_id} status synced: "
            f"{declaration.state.status.name}"
        )
        return command.declaration_id


# -----------------------------------------------------------------------------
# RefreshStatusFromKonturHandler
# -----------------------------------------------------------------------------
@command_handler(RefreshStatusFromKonturCommand)
class RefreshStatusFromKonturHandler(BaseCommandHandler):
    """
    Handles the RefreshStatusFromKonturCommand.

    User-initiated refresh that fetches current status from Kontur and
    updates the aggregate if status has changed. Uses search_docflows()
    or list_docflows() to get current status.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: RefreshStatusFromKonturCommand) -> uuid.UUID:
        log.info(f"Refreshing status from Kontur for declaration {command.declaration_id}")

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

        # Verify declaration has been submitted
        if not declaration.state.kontur_docflow_id:
            raise InvalidDeclarationStatusError(
                f"Declaration {command.declaration_id} has not been submitted to Kontur"
            )

        # Get Kontur adapter
        adapter = await get_kontur_adapter()

        # Fetch current docflow from Kontur
        try:
            docflow = await adapter.get_docflow(declaration.state.kontur_docflow_id)
            if not docflow:
                raise KonturSyncError(
                    f"Docflow {declaration.state.kontur_docflow_id} not found in Kontur"
                )
        except Exception as e:
            log.error(f"Failed to fetch docflow from Kontur: {e}")
            declaration.mark_sync_failed(
                error_message=str(e),
                kontur_docflow_id=declaration.state.kontur_docflow_id,
            )
            await self.publish_events(
                aggregate=declaration,
                aggregate_id=command.declaration_id,
                command=command,
                aggregate_type="CustomsDeclaration"
            )
            raise KonturSyncError(f"Failed to refresh status: {e}") from e

        # Map Kontur status to DocflowStatus
        new_status = DocflowStatus(docflow.status)

        # Get GTD number if available
        gtd_number = getattr(docflow, 'reg_number', None) or getattr(docflow, 'gtd_number', None)

        # Check if status changed
        if declaration.state.status == new_status:
            log.info(
                f"Declaration {command.declaration_id} status unchanged: {new_status.name}"
            )
            return command.declaration_id

        # Update status
        declaration.update_status_from_kontur(
            kontur_docflow_id=declaration.state.kontur_docflow_id,
            new_status=new_status,
            gtd_number=gtd_number,
        )

        # Publish events
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(
            f"Declaration {command.declaration_id} status refreshed: "
            f"{declaration.state.status.name}"
        )
        return command.declaration_id


# =============================================================================
# EOF
# =============================================================================
