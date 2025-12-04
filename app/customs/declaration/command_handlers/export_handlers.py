# =============================================================================
# File: app/customs/declaration/command_handlers/export_handlers.py
# Description: Command handlers for PDF/XML export and import operations
# Handlers: ExportDeclarationPdf, ExportDeclarationXml, ImportDeclarationXml
# =============================================================================

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
import uuid

from app.config.logging_config import get_logger
from app.customs.declaration.commands import (
    ExportDeclarationPdfCommand,
    ExportDeclarationXmlCommand,
    ImportDeclarationXmlCommand,
)
from app.customs.declaration.aggregate import CustomsDeclarationAggregate
from app.customs.exceptions import (
    DeclarationNotFoundError,
    KonturSyncError,
    DeclarationNotSubmittedError,
    FormExportError,
    FormImportError,
)
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler
from app.infra.kontur.adapter import get_kontur_adapter

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.customs.declaration.export_handlers")

# Transport topic for customs events
CUSTOMS_TRANSPORT_TOPIC = "transport.customs-events"


# -----------------------------------------------------------------------------
# ExportDeclarationPdfHandler
# -----------------------------------------------------------------------------
@command_handler(ExportDeclarationPdfCommand)
class ExportDeclarationPdfHandler(BaseCommandHandler):
    """
    Handles the ExportDeclarationPdfCommand.

    Exports declaration form as PDF from Kontur. Requires declaration to be
    submitted to Kontur first.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: ExportDeclarationPdfCommand) -> bytes:
        log.info(
            f"Exporting PDF for declaration {command.declaration_id} "
            f"(form_id={command.form_id})"
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
                "before exporting PDF"
            )

        # Get Kontur adapter
        adapter = await get_kontur_adapter()

        # Export PDF from Kontur
        try:
            pdf_bytes = await adapter.print_pdf(
                docflow_id=declaration.state.kontur_docflow_id,
                form_id=command.form_id,
            )
            if not pdf_bytes:
                raise FormExportError("Kontur returned empty PDF")
        except FormExportError:
            raise
        except Exception as e:
            log.error(f"Failed to export PDF from Kontur: {e}")
            raise FormExportError(f"Failed to export PDF: {e}") from e

        log.info(
            f"PDF exported for declaration {command.declaration_id}, "
            f"size={len(pdf_bytes)} bytes"
        )
        return pdf_bytes


# -----------------------------------------------------------------------------
# ExportDeclarationXmlHandler
# -----------------------------------------------------------------------------
@command_handler(ExportDeclarationXmlCommand)
class ExportDeclarationXmlHandler(BaseCommandHandler):
    """
    Handles the ExportDeclarationXmlCommand.

    Exports declaration form as XML from Kontur. Requires declaration to be
    submitted to Kontur first.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: ExportDeclarationXmlCommand) -> bytes:
        log.info(
            f"Exporting XML for declaration {command.declaration_id} "
            f"(form_id={command.form_id})"
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
                "before exporting XML"
            )

        # Get Kontur adapter
        adapter = await get_kontur_adapter()

        # Export XML from Kontur
        try:
            xml_bytes = await adapter.get_form_xml(
                docflow_id=declaration.state.kontur_docflow_id,
                form_id=command.form_id,
            )
            if not xml_bytes:
                raise FormExportError("Kontur returned empty XML")
        except FormExportError:
            raise
        except Exception as e:
            log.error(f"Failed to export XML from Kontur: {e}")
            raise FormExportError(f"Failed to export XML: {e}") from e

        log.info(
            f"XML exported for declaration {command.declaration_id}, "
            f"size={len(xml_bytes)} bytes"
        )
        return xml_bytes


# -----------------------------------------------------------------------------
# ImportDeclarationXmlHandler
# -----------------------------------------------------------------------------
@command_handler(ImportDeclarationXmlCommand)
class ImportDeclarationXmlHandler(BaseCommandHandler):
    """
    Handles the ImportDeclarationXmlCommand.

    Imports XML data into declaration via Kontur. Requires declaration to be
    submitted to Kontur first. The imported data will update the form in Kontur.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: ImportDeclarationXmlCommand) -> uuid.UUID:
        log.info(
            f"Importing XML into declaration {command.declaration_id} "
            f"(document_mode_id={command.document_mode_id})"
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
                "before importing XML"
            )

        # Get Kontur adapter
        adapter = await get_kontur_adapter()

        # Import XML into Kontur
        try:
            success = await adapter.upload_form_file(
                docflow_id=declaration.state.kontur_docflow_id,
                form_id="dt",
                file_bytes=command.xml_content,
                filename="import.xml",
            )
            if not success:
                raise FormImportError("Kontur returned false for XML import")
        except FormImportError:
            raise
        except Exception as e:
            log.error(f"Failed to import XML to Kontur: {e}")
            # Record sync failure
            declaration.mark_sync_failed(
                error_message=f"XML import failed: {e}",
                kontur_docflow_id=declaration.state.kontur_docflow_id,
            )
            await self.publish_events(
                aggregate=declaration,
                aggregate_id=command.declaration_id,
                command=command,
                aggregate_type="CustomsDeclaration"
            )
            raise FormImportError(f"Failed to import XML: {e}") from e

        log.info(f"XML imported successfully for declaration {command.declaration_id}")

        # Note: We don't update aggregate form_data here because Kontur
        # parses the XML and updates the form. The form data would need
        # to be fetched back via get_form_json if needed for local sync.

        return command.declaration_id


# =============================================================================
# EOF
# =============================================================================
