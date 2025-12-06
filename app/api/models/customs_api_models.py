# =============================================================================
# File: app/api/models/customs_api_models.py
# Description: Customs domain API models (Pydantic v2)
# =============================================================================

from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime

from app.customs.enums import DeclarationType, DocflowStatus, DtsType, DistributeBy, IncludeIn


# =============================================================================
# Request Models - Declaration Lifecycle
# =============================================================================

class CreateDeclarationRequest(BaseModel):
    """Request to create a new customs declaration"""
    model_config = ConfigDict(use_enum_values=True)

    name: str = Field(..., min_length=1, max_length=255, description="Declaration name/reference")
    company_id: UUID = Field(..., description="Company this declaration belongs to")
    declaration_type: DeclarationType = Field(default=DeclarationType.IMPORT)
    procedure: str = Field(default="4000", description="Customs procedure code")
    customs_code: str = Field(..., description="Customs office code")
    organization_id: Optional[str] = Field(None, description="Kontur organization ID")
    employee_id: Optional[str] = Field(None, description="Kontur employee ID (declarant)")


class UpdateDeclarationRequest(BaseModel):
    """Request to update declaration details"""
    name: Optional[str] = Field(None, max_length=255)
    procedure: Optional[str] = None
    customs_code: Optional[str] = None
    organization_id: Optional[str] = None
    employee_id: Optional[str] = None


class CopyDeclarationRequest(BaseModel):
    """Request to copy an existing declaration"""
    new_name: str = Field(..., min_length=1, max_length=255)
    copy_documents: bool = Field(default=True)
    copy_form_data: bool = Field(default=True)


class DeleteDeclarationRequest(BaseModel):
    """Request to delete a declaration"""
    reason: Optional[str] = Field(None, max_length=500)


# =============================================================================
# Request Models - Form Data
# =============================================================================

class UpdateFormDataRequest(BaseModel):
    """Request to update declaration form data"""
    form_data: Dict[str, Any] = Field(..., description="Form data to merge/update")


class ImportGoodsRequest(BaseModel):
    """Request to import goods into declaration"""
    goods: List[Dict[str, Any]] = Field(..., description="List of goods to import")
    import_source: str = Field(default="manual", description="Source: manual, xml, excel")
    replace_existing: bool = Field(default=False, description="Replace existing goods or append")


# =============================================================================
# Request Models - Documents
# =============================================================================

class AttachDocumentRequest(BaseModel):
    """Request to attach a document to declaration"""
    name: str = Field(..., min_length=1, max_length=255)
    number: str = Field(..., min_length=1, max_length=100)
    date: str = Field(..., description="ISO format date")
    grafa44_code: str = Field(..., description="Customs document code (Grafa 44)")
    form_id: str = Field(default="dt")
    belongs_to_all_goods: bool = Field(default=True)
    file_id: Optional[str] = None


class CreateDtsRequest(BaseModel):
    """Request to create DTS (customs value declaration) document"""
    model_config = ConfigDict(use_enum_values=True)

    dts_type: DtsType
    distribution_items: List[DtsDistributionItem] = Field(
        ...,
        description="List of distribution items"
    )


class DtsDistributionItem(BaseModel):
    """DTS distribution item"""
    model_config = ConfigDict(use_enum_values=True)

    grafa: str = Field(..., description="Field number")
    distribute_by: DistributeBy
    include_in: IncludeIn
    currency: str = Field(default="RUB")
    total: str = Field(..., description="Total amount as decimal string")


# Fix forward reference
CreateDtsRequest.model_rebuild()


# =============================================================================
# Request Models - Organization
# =============================================================================

class SetOrganizationRequest(BaseModel):
    """Request to set organization on declaration form"""
    organization_id: str
    grafa: str = Field(default="8", description="Field number (8=consignee, 9=financial)")


class SetEmployeeRequest(BaseModel):
    """Request to set employee (declarant) on declaration"""
    employee_id: str


# =============================================================================
# Request Models - Export/Import
# =============================================================================

class ExportRequest(BaseModel):
    """Request to export declaration"""
    form_id: str = Field(default="dt")


class ImportXmlRequest(BaseModel):
    """Request to import declaration from XML"""
    document_mode_id: str = Field(default="1006", description="Document mode ID for DT form")
    # XML content will be sent as file upload


# =============================================================================
# Response Models - Generic
# =============================================================================

class DeclarationResponse(BaseModel):
    """Generic response for declaration operations"""
    id: UUID
    message: str


class OperationResponse(BaseModel):
    """Generic operation response"""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Response Models - Declaration
# =============================================================================

class DeclarationDetailResponse(BaseModel):
    """Full declaration details response"""
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: UUID
    user_id: UUID
    company_id: UUID
    kontur_docflow_id: Optional[str] = None
    gtd_number: Optional[str] = None
    name: str
    declaration_type: str
    procedure: str
    customs_code: str
    status: int
    status_name: str
    organization_id: Optional[str] = None
    employee_id: Optional[str] = None
    declarant_inn: Optional[str] = None
    form_data: Dict[str, Any] = Field(default_factory=dict)
    documents: List[DocumentResponse] = Field(default_factory=list)
    goods_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    is_deleted: bool = False


class DeclarationSummaryResponse(BaseModel):
    """Lightweight declaration summary for list views"""
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: UUID
    name: str
    declaration_type: str
    procedure: str
    customs_code: str
    status: int
    status_name: str
    gtd_number: Optional[str] = None
    organization_id: Optional[str] = None
    goods_count: int = 0
    created_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    is_deleted: bool = False


class DeclarationListResponse(BaseModel):
    """Paginated list of declarations"""
    declarations: List[DeclarationSummaryResponse]
    total: int
    limit: int
    offset: int


# =============================================================================
# Response Models - Documents
# =============================================================================

class DocumentResponse(BaseModel):
    """Document attached to declaration"""
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    form_id: str
    name: str
    number: Optional[str] = None
    date: Optional[str] = None
    grafa44_code: Optional[str] = None
    belongs_to_all_goods: bool = True
    file_id: Optional[str] = None
    dts_type: Optional[int] = None


# =============================================================================
# Response Models - Organization
# =============================================================================

class OrganizationResponse(BaseModel):
    """Organization details response"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kontur_org_id: Optional[str] = None
    org_name: str
    short_name: Optional[str] = None
    org_type: int
    org_type_name: str
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    is_foreign: bool = False
    legal_address: Optional[Dict[str, Any]] = None
    actual_address: Optional[Dict[str, Any]] = None


class OrganizationSummaryResponse(BaseModel):
    """Lightweight organization summary"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kontur_org_id: Optional[str] = None
    org_name: str
    short_name: Optional[str] = None
    inn: Optional[str] = None
    is_foreign: bool = False


# =============================================================================
# Response Models - Kontur Options (Reference Data)
# =============================================================================

class KonturOrganizationOption(BaseModel):
    """Kontur organization option for dropdown"""
    id: str
    name: str
    inn: Optional[str] = None


class KonturEmployeeOption(BaseModel):
    """Kontur employee option for dropdown"""
    id: str
    name: str
    position: Optional[str] = None


class KonturCustomsOption(BaseModel):
    """Kontur customs office option for dropdown"""
    code: str
    name: str


class KonturProcedureOption(BaseModel):
    """Kontur procedure option for dropdown"""
    code: str
    name: str
    description: Optional[str] = None


class KonturDeclarationTypeOption(BaseModel):
    """Kontur declaration type option for dropdown"""
    code: str
    name: str


# =============================================================================
# Response Models - Export
# =============================================================================

class ExportPdfResponse(BaseModel):
    """PDF export response"""
    success: bool
    pdf_base64: Optional[str] = None
    filename: Optional[str] = None
    error: Optional[str] = None


class ExportXmlResponse(BaseModel):
    """XML export response"""
    success: bool
    xml_content: Optional[str] = None
    filename: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Response Models - Status
# =============================================================================

class DeclarationStatusResponse(BaseModel):
    """Declaration status response"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: int
    status_name: str
    kontur_docflow_id: Optional[str] = None
    gtd_number: Optional[str] = None
    submitted_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SubmitResponse(BaseModel):
    """Response for submit to Kontur operation"""
    success: bool
    declaration_id: UUID
    kontur_docflow_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


class RefreshStatusResponse(BaseModel):
    """Response for status refresh operation"""
    success: bool
    declaration_id: UUID
    old_status: int
    new_status: int
    status_name: str
    gtd_number: Optional[str] = None
    message: Optional[str] = None


# =============================================================================
# EOF
# =============================================================================
