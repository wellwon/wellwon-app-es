# =============================================================================
# File: app/customs/declaration/commands.py
# Description: Domain commands for CustomsDeclaration aggregate
# =============================================================================

from __future__ import annotations

from pydantic import Field
from uuid import UUID
from typing import Optional, Dict, Any, List

from app.infra.cqrs.command_bus import Command
from app.customs.enums import DeclarationType, DocflowStatus, DtsType, DistributeBy, IncludeIn
from app.utils.uuid_utils import generate_uuid, generate_uuid_str


# =============================================================================
# SECTION: Declaration Lifecycle Commands
# =============================================================================

class CreateCustomsDeclarationCommand(Command):
    """Command to create a new customs declaration."""
    declaration_id: UUID = Field(default_factory=generate_uuid, description="Generated declaration ID")
    user_id: UUID
    company_id: UUID
    name: str = Field(..., min_length=1, max_length=255, description="Declaration name/reference")
    declaration_type: DeclarationType = Field(default=DeclarationType.IMPORT)
    procedure: str = Field(default="4000", description="Customs procedure code")
    customs_code: str = Field(..., description="Customs office code")
    organization_id: Optional[str] = Field(None, description="Kontur organization ID")
    employee_id: Optional[str] = Field(None, description="Kontur employee ID (declarant)")


class DeleteCustomsDeclarationCommand(Command):
    """Command to delete a customs declaration."""
    declaration_id: UUID
    user_id: UUID
    reason: Optional[str] = None


class CopyCustomsDeclarationCommand(Command):
    """Command to copy an existing declaration as a template."""
    source_declaration_id: UUID
    new_declaration_id: UUID = Field(default_factory=generate_uuid)
    user_id: UUID
    new_name: str = Field(..., min_length=1, max_length=255)
    copy_documents: bool = True
    copy_form_data: bool = True


# =============================================================================
# SECTION: Form Data Commands
# =============================================================================

class UpdateFormDataCommand(Command):
    """Command to update declaration form data."""
    declaration_id: UUID
    user_id: UUID
    form_data: Dict[str, Any] = Field(..., description="Form data to merge/update")


class ImportGoodsCommand(Command):
    """Command to import goods into declaration."""
    declaration_id: UUID
    user_id: UUID
    goods: List[Dict[str, Any]] = Field(..., description="List of goods to import")
    import_source: str = Field(default="manual", description="Source: manual, xml, excel")
    replace_existing: bool = Field(default=False, description="Replace existing goods or append")


# =============================================================================
# SECTION: Document Commands
# =============================================================================

class AttachDocumentCommand(Command):
    """Command to attach a document to declaration."""
    declaration_id: UUID
    user_id: UUID
    document_id: str = Field(default_factory=generate_uuid_str)
    form_id: str = Field(default="dt")
    name: str
    number: str
    date: str  # ISO format
    grafa44_code: str = Field(..., description="Customs document code (Grafa 44)")
    belongs_to_all_goods: bool = True
    file_id: Optional[str] = None


class RemoveDocumentCommand(Command):
    """Command to remove a document from declaration."""
    declaration_id: UUID
    user_id: UUID
    document_id: str


class CreateDtsCommand(Command):
    """Command to create DTS (customs value declaration) document."""
    declaration_id: UUID
    user_id: UUID
    dts_type: DtsType
    distribution_items: List[Dict[str, Any]] = Field(
        ...,
        description="List of distribution items with grafa, distribute_by, include_in, currency, total"
    )


# =============================================================================
# SECTION: Kontur Integration Commands
# =============================================================================

class SubmitToKonturCommand(Command):
    """
    Command to submit declaration to Kontur.
    Triggers saga for multi-step submission process.
    """
    declaration_id: UUID
    user_id: UUID


class SyncStatusFromKonturCommand(Command):
    """Command to sync status from Kontur (background or manual)."""
    declaration_id: UUID
    kontur_docflow_id: str
    new_status: DocflowStatus
    gtd_number: Optional[str] = None


class RefreshStatusFromKonturCommand(Command):
    """Command for manual status refresh (user-initiated)."""
    declaration_id: UUID
    user_id: UUID


class MarkDeclarationReleasedCommand(Command):
    """Command to mark declaration as released."""
    declaration_id: UUID
    kontur_docflow_id: str
    gtd_number: str


class MarkDeclarationRejectedCommand(Command):
    """Command to mark declaration as rejected."""
    declaration_id: UUID
    kontur_docflow_id: str
    rejection_reason: Optional[str] = None


# =============================================================================
# SECTION: Organization Commands
# =============================================================================

class SetOrganizationCommand(Command):
    """Command to set organization on declaration form."""
    declaration_id: UUID
    user_id: UUID
    organization_id: str
    grafa: str = Field(default="8", description="Field number (8=consignee, 9=financial)")


class SetEmployeeCommand(Command):
    """Command to set employee (declarant) on declaration."""
    declaration_id: UUID
    user_id: UUID
    employee_id: str


# =============================================================================
# SECTION: Export/Import Commands
# =============================================================================

class ExportDeclarationPdfCommand(Command):
    """Command to export declaration as PDF."""
    declaration_id: UUID
    user_id: UUID
    form_id: str = Field(default="dt")


class ExportDeclarationXmlCommand(Command):
    """Command to export declaration as XML."""
    declaration_id: UUID
    user_id: UUID
    form_id: str = Field(default="dt")


class ImportDeclarationXmlCommand(Command):
    """Command to import declaration from XML."""
    declaration_id: UUID
    user_id: UUID
    xml_content: bytes
    document_mode_id: str = Field(default="1006", description="Document mode ID for DT form")


# =============================================================================
# EOF
# =============================================================================
