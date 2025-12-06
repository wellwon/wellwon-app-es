# =============================================================================
# File: app/customs/declaration/command_handlers/form_handlers.py
# Description: Command handlers for form data, documents, and goods operations
# Handlers: UpdateFormData, ImportGoods, SetOrganization, SetEmployee,
#           AttachDocument, RemoveDocument, CreateDts
# =============================================================================

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from app.config.logging_config import get_logger
from app.customs.declaration.commands import (
    UpdateFormDataCommand,
    ImportGoodsCommand,
    SetOrganizationCommand,
    SetEmployeeCommand,
    AttachDocumentCommand,
    RemoveDocumentCommand,
    CreateDtsCommand,
)
from app.customs.declaration.aggregate import CustomsDeclarationAggregate
from app.customs.exceptions import (
    DeclarationNotFoundError,
    KonturSyncError,
    InvalidDeclarationStatusError,
    DeclarationNotSubmittedError,
)
from app.customs.enums import DocflowStatus
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler
from app.infra.kontur.models import CreateDocumentRequest, DistributionItem

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies
    from app.customs.ports.kontur_declarant_port import KonturDeclarantPort

log = get_logger("wellwon.customs.declaration.form_handlers")

# Transport topic for customs events
CUSTOMS_TRANSPORT_TOPIC = "transport.customs-events"


# -----------------------------------------------------------------------------
# UpdateFormDataHandler
# -----------------------------------------------------------------------------
@command_handler(UpdateFormDataCommand)
class UpdateFormDataHandler(BaseCommandHandler):
    """
    Handles the UpdateFormDataCommand.

    Updates local aggregate state with form data. If declaration is already
    submitted to Kontur, also syncs form data via import_form_json().
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )
        # Port injection: kontur_adapter implements KonturDeclarantPort
        self._kontur: 'KonturDeclarantPort' = deps.kontur_adapter

    async def handle(self, command: UpdateFormDataCommand) -> uuid.UUID:
        log.info(f"Updating form data for declaration {command.declaration_id}")

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

        # Update aggregate (validates status internally)
        declaration.update_form_data(
            user_id=command.user_id,
            form_data=command.form_data,
        )

        # If submitted to Kontur, sync form data via port
        if declaration.state.kontur_docflow_id:
            try:
                success = await self._kontur.import_form_json(
                    docflow_id=declaration.state.kontur_docflow_id,
                    form_id="dt",
                    data=command.form_data,
                )
                if not success:
                    log.warning(
                        f"Form data sync to Kontur returned false for "
                        f"docflow {declaration.state.kontur_docflow_id}"
                    )
            except Exception as e:
                log.error(f"Failed to sync form data to Kontur: {e}")
                # Don't fail the command, form data is saved locally
                declaration.mark_sync_failed(
                    error_message=f"Form data sync failed: {e}",
                    kontur_docflow_id=declaration.state.kontur_docflow_id,
                )

        # Publish events
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(f"Form data updated for declaration {command.declaration_id}")
        return command.declaration_id


# -----------------------------------------------------------------------------
# ImportGoodsHandler
# -----------------------------------------------------------------------------
@command_handler(ImportGoodsCommand)
class ImportGoodsHandler(BaseCommandHandler):
    """
    Handles the ImportGoodsCommand.

    Imports goods into declaration. If submitted to Kontur, syncs via
    import_goods_data().
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )
        # Port injection: kontur_adapter implements KonturDeclarantPort
        self._kontur: 'KonturDeclarantPort' = deps.kontur_adapter

    async def handle(self, command: ImportGoodsCommand) -> uuid.UUID:
        log.info(
            f"Importing {len(command.goods)} goods into declaration {command.declaration_id}"
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

        # Update aggregate
        declaration.import_goods(
            user_id=command.user_id,
            goods=command.goods,
            import_source=command.import_source,
            replace_existing=command.replace_existing,
        )

        # If submitted to Kontur, sync goods via port
        if declaration.state.kontur_docflow_id:
            try:
                success = await self._kontur.import_goods_data(
                    docflow_id=declaration.state.kontur_docflow_id,
                    form_id="dt",
                    goods=command.goods,
                    clear_before=command.replace_existing,
                    preserve_attached=True,
                )
                if not success:
                    log.warning(
                        f"Goods sync to Kontur returned false for "
                        f"docflow {declaration.state.kontur_docflow_id}"
                    )
            except Exception as e:
                log.error(f"Failed to sync goods to Kontur: {e}")
                declaration.mark_sync_failed(
                    error_message=f"Goods sync failed: {e}",
                    kontur_docflow_id=declaration.state.kontur_docflow_id,
                )

        # Publish events
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(f"Goods imported for declaration {command.declaration_id}")
        return command.declaration_id


# -----------------------------------------------------------------------------
# SetOrganizationHandler
# -----------------------------------------------------------------------------
@command_handler(SetOrganizationCommand)
class SetOrganizationHandler(BaseCommandHandler):
    """
    Handles the SetOrganizationCommand.

    Sets organization on declaration. If submitted to Kontur, syncs via
    set_form_contractor().
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )
        # Port injection: kontur_adapter implements KonturDeclarantPort
        self._kontur: 'KonturDeclarantPort' = deps.kontur_adapter

    async def handle(self, command: SetOrganizationCommand) -> uuid.UUID:
        log.info(
            f"Setting organization {command.organization_id} on declaration "
            f"{command.declaration_id} (grafa={command.grafa})"
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

        # Update aggregate
        declaration.set_organization(
            user_id=command.user_id,
            organization_id=command.organization_id,
            grafa=command.grafa,
        )

        # If submitted to Kontur, sync organization via port
        if declaration.state.kontur_docflow_id:
            try:
                success = await self._kontur.set_form_contractor(
                    docflow_id=declaration.state.kontur_docflow_id,
                    form_id="dt",
                    org_id=command.organization_id,
                    graph_number=command.grafa,
                )
                if not success:
                    log.warning(
                        f"Organization sync to Kontur returned false for "
                        f"docflow {declaration.state.kontur_docflow_id}"
                    )
            except Exception as e:
                log.error(f"Failed to sync organization to Kontur: {e}")
                declaration.mark_sync_failed(
                    error_message=f"Organization sync failed: {e}",
                    kontur_docflow_id=declaration.state.kontur_docflow_id,
                )

        # Publish events
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(f"Organization set for declaration {command.declaration_id}")
        return command.declaration_id


# -----------------------------------------------------------------------------
# SetEmployeeHandler
# -----------------------------------------------------------------------------
@command_handler(SetEmployeeCommand)
class SetEmployeeHandler(BaseCommandHandler):
    """
    Handles the SetEmployeeCommand.

    Sets employee (declarant) on declaration. This updates the local
    aggregate state. Kontur sync happens via form_json update.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: SetEmployeeCommand) -> uuid.UUID:
        log.info(
            f"Setting employee {command.employee_id} on declaration {command.declaration_id}"
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

        # Update aggregate
        declaration.set_employee(
            user_id=command.user_id,
            employee_id=command.employee_id,
        )

        # Publish events
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(f"Employee set for declaration {command.declaration_id}")
        return command.declaration_id


# -----------------------------------------------------------------------------
# AttachDocumentHandler
# -----------------------------------------------------------------------------
@command_handler(AttachDocumentCommand)
class AttachDocumentHandler(BaseCommandHandler):
    """
    Handles the AttachDocumentCommand.

    Attaches document to declaration. If submitted to Kontur, syncs via
    create_documents().
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )
        # Port injection: kontur_adapter implements KonturDeclarantPort
        self._kontur: 'KonturDeclarantPort' = deps.kontur_adapter

    async def handle(self, command: AttachDocumentCommand) -> uuid.UUID:
        log.info(
            f"Attaching document {command.document_id} to declaration {command.declaration_id}"
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

        # Update aggregate
        declaration.attach_document(
            user_id=command.user_id,
            document_id=command.document_id,
            form_id=command.form_id,
            name=command.name,
            number=command.number,
            date=command.date,
            grafa44_code=command.grafa44_code,
            belongs_to_all_goods=command.belongs_to_all_goods,
            file_id=command.file_id,
        )

        # If submitted to Kontur, sync document via port
        if declaration.state.kontur_docflow_id:
            try:
                doc_request = CreateDocumentRequest(
                    name=command.name,
                    number=command.number,
                    date=command.date,
                    document_mode_id="1006",  # DT form
                    grafa44_code=command.grafa44_code,
                    belongs_to_all_goods=command.belongs_to_all_goods,
                )
                result = await self._kontur.create_documents(
                    docflow_id=declaration.state.kontur_docflow_id,
                    documents=[doc_request],
                )
                if not result:
                    log.warning(
                        f"Document sync to Kontur returned empty for "
                        f"docflow {declaration.state.kontur_docflow_id}"
                    )
            except Exception as e:
                log.error(f"Failed to sync document to Kontur: {e}")
                declaration.mark_sync_failed(
                    error_message=f"Document sync failed: {e}",
                    kontur_docflow_id=declaration.state.kontur_docflow_id,
                )

        # Publish events
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(f"Document attached to declaration {command.declaration_id}")
        return command.declaration_id


# -----------------------------------------------------------------------------
# RemoveDocumentHandler
# -----------------------------------------------------------------------------
@command_handler(RemoveDocumentCommand)
class RemoveDocumentHandler(BaseCommandHandler):
    """
    Handles the RemoveDocumentCommand.

    Removes document from declaration. This is a local operation only -
    Kontur documents are managed separately in the Kontur UI.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: RemoveDocumentCommand) -> uuid.UUID:
        log.info(
            f"Removing document {command.document_id} from declaration {command.declaration_id}"
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

        # Update aggregate (validates status and document existence)
        declaration.remove_document(
            user_id=command.user_id,
            document_id=command.document_id,
        )

        # Publish events
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(f"Document removed from declaration {command.declaration_id}")
        return command.declaration_id


# -----------------------------------------------------------------------------
# CreateDtsHandler
# -----------------------------------------------------------------------------
@command_handler(CreateDtsCommand)
class CreateDtsHandler(BaseCommandHandler):
    """
    Handles the CreateDtsCommand.

    Creates DTS (customs value declaration) document via Kontur calculator.
    Requires declaration to be submitted to Kontur.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )
        # Port injection: kontur_adapter implements KonturDeclarantPort
        self._kontur: 'KonturDeclarantPort' = deps.kontur_adapter

    async def handle(self, command: CreateDtsCommand) -> str:
        log.info(
            f"Creating DTS type {command.dts_type.value} for declaration {command.declaration_id}"
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

        # Verify declaration is submitted
        if not declaration.state.kontur_docflow_id:
            raise DeclarationNotSubmittedError(
                f"Declaration {command.declaration_id} must be submitted to Kontur "
                "before creating DTS"
            )

        # Convert distribution items to Kontur model
        distribution_items = [
            DistributionItem(
                grafa=item.get("grafa", ""),
                distribute_by=item.get("distribute_by", 1),
                include_in=item.get("include_in", 1),
                currency_code=item.get("currency_code", "USD"),
                total=float(item.get("total", 0)),
                border_place=item.get("border_place"),
            )
            for item in command.distribution_items
        ]

        # Create DTS via Kontur calculator (via port)
        try:
            dts_doc = await self._kontur.create_dts_with_calculator(
                docflow_id=declaration.state.kontur_docflow_id,
                dts_type=command.dts_type.value,
                items=distribution_items,
            )
            if not dts_doc:
                raise KonturSyncError("Kontur returned empty DTS document")
        except Exception as e:
            log.error(f"Failed to create DTS in Kontur: {e}")
            declaration.mark_sync_failed(
                error_message=f"DTS creation failed: {e}",
                kontur_docflow_id=declaration.state.kontur_docflow_id,
            )
            await self.publish_events(
                aggregate=declaration,
                aggregate_id=command.declaration_id,
                command=command,
                aggregate_type="CustomsDeclaration"
            )
            raise KonturSyncError(f"Failed to create DTS: {e}") from e

        log.info(f"Created DTS document: {dts_doc.id}")

        # Update aggregate with DTS document
        declaration.attach_dts_document(
            user_id=command.user_id,
            document_id=dts_doc.id,
            dts_type=command.dts_type.value,
        )

        # Publish events
        await self.publish_events(
            aggregate=declaration,
            aggregate_id=command.declaration_id,
            command=command,
            aggregate_type="CustomsDeclaration"
        )

        log.info(f"DTS created for declaration {command.declaration_id}")
        return dts_doc.id


# =============================================================================
# EOF
# =============================================================================
