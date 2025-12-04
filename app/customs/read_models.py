# =============================================================================
# File: app/customs/read_models.py
# Description: Read models (DTOs) for Customs domain queries
# =============================================================================

from __future__ import annotations

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.customs.enums import DeclarationType, DocflowStatus


# =============================================================================
# Declaration Read Models
# =============================================================================

class CustomsDeclarationReadModel(BaseModel):
    """Full declaration read model for detail view."""
    id: UUID
    user_id: UUID
    company_id: UUID

    # Kontur integration
    kontur_docflow_id: Optional[str] = None
    gtd_number: Optional[str] = None

    # Declaration details
    name: str
    declaration_type: DeclarationType
    procedure: str
    customs_code: str
    status: DocflowStatus

    # Organization references
    organization_id: Optional[str] = None
    employee_id: Optional[str] = None
    declarant_inn: Optional[str] = None

    # Form data
    form_data: Dict[str, Any] = Field(default_factory=dict)

    # Documents
    documents: List[Dict[str, Any]] = Field(default_factory=list)

    # Goods
    goods: List[Dict[str, Any]] = Field(default_factory=list)

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None

    # Soft delete
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    # Event sourcing metadata
    aggregate_version: int = 1
    last_event_sequence: Optional[int] = None

    class Config:
        from_attributes = True


class DeclarationSummaryReadModel(BaseModel):
    """Lightweight declaration summary for list views."""
    id: UUID
    name: str
    declaration_type: DeclarationType
    procedure: str
    customs_code: str
    status: DocflowStatus
    gtd_number: Optional[str] = None
    organization_id: Optional[str] = None
    created_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    is_deleted: bool = False

    class Config:
        from_attributes = True


class DeclarationStatusReadModel(BaseModel):
    """Status-focused read model for status tracking."""
    id: UUID
    name: str
    status: DocflowStatus
    kontur_docflow_id: Optional[str] = None
    gtd_number: Optional[str] = None
    submitted_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================================================
# Organization Read Models
# =============================================================================

class CommonOrganizationReadModel(BaseModel):
    """Full organization read model."""
    id: UUID
    kontur_org_id: Optional[str] = None
    org_name: str
    short_name: Optional[str] = None
    org_type: int  # OrganizationType value
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    is_foreign: bool = False
    legal_address: Optional[Dict[str, Any]] = None
    actual_address: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    synced_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrganizationSummaryReadModel(BaseModel):
    """Lightweight organization summary for dropdowns/lists."""
    id: UUID
    kontur_org_id: Optional[str] = None
    org_name: str
    short_name: Optional[str] = None
    inn: Optional[str] = None
    is_foreign: bool = False

    class Config:
        from_attributes = True


# =============================================================================
# Reference Data Read Models
# =============================================================================

class CustomsProcedureReadModel(BaseModel):
    """Customs procedure reference data."""
    code: str
    name: str
    description: Optional[str] = None
    declaration_type: Optional[str] = None  # Applicable declaration types

    class Config:
        from_attributes = True


class CustomsOfficeReadModel(BaseModel):
    """Customs office reference data."""
    code: str
    name: str
    region: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class DeclarationTypeReadModel(BaseModel):
    """Declaration type reference data."""
    code: str
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


# =============================================================================
# Document Read Models
# =============================================================================

class DeclarationDocumentReadModel(BaseModel):
    """Document attached to declaration."""
    document_id: str
    form_id: str
    name: str
    number: Optional[str] = None
    date: Optional[str] = None
    grafa44_code: Optional[str] = None
    belongs_to_all_goods: bool = True
    file_id: Optional[str] = None
    dts_type: Optional[int] = None  # For DTS documents

    class Config:
        from_attributes = True


# =============================================================================
# Goods Read Models
# =============================================================================

class GoodItemReadModel(BaseModel):
    """Good item in declaration."""
    item_number: int
    description: str
    quantity: str  # Decimal as string
    unit: str
    customs_value: str  # Decimal as string
    currency_code: str
    hs_code: Optional[str] = None
    country_of_origin: Optional[str] = None
    gross_weight: Optional[str] = None
    net_weight: Optional[str] = None
    invoice_price: Optional[str] = None

    class Config:
        from_attributes = True


# =============================================================================
# Sync Failure Read Model
# =============================================================================

class SyncFailureReadModel(BaseModel):
    """Kontur sync failure record."""
    id: UUID
    declaration_id: UUID
    kontur_docflow_id: Optional[str] = None
    error_message: str
    failed_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# EOF
# =============================================================================
