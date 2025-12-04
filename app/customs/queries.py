# =============================================================================
# File: app/customs/queries.py
# Description: Query definitions for Customs domain
# =============================================================================

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from app.infra.cqrs.query_bus import Query
from app.customs.enums import DocflowStatus, DeclarationType, OrganizationType


# =============================================================================
# Declaration Queries
# =============================================================================

class GetDeclarationQuery(Query):
    """Get full customs declaration by ID"""
    declaration_id: uuid.UUID
    user_id: uuid.UUID  # For authorization check


class GetDeclarationSummaryQuery(Query):
    """Get declaration summary by ID"""
    declaration_id: uuid.UUID
    user_id: uuid.UUID


class ListDeclarationsQuery(Query):
    """List declarations for user with optional filters"""
    user_id: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    status: Optional[DocflowStatus] = None
    declaration_type: Optional[DeclarationType] = None
    limit: int = 50
    offset: int = 0


class ListPendingDeclarationsQuery(Query):
    """List declarations pending Kontur sync (for background worker)"""
    status_list: List[DocflowStatus] = Field(
        default_factory=lambda: [DocflowStatus.SENT, DocflowStatus.REGISTERED]
    )
    has_kontur_docflow_id: bool = True
    limit: int = 100


class GetDeclarationByKonturIdQuery(Query):
    """Get declaration by Kontur docflow ID"""
    kontur_docflow_id: str


class SearchDeclarationsQuery(Query):
    """Search declarations by various criteria"""
    user_id: uuid.UUID
    search_term: str
    company_id: Optional[uuid.UUID] = None
    limit: int = 20


# =============================================================================
# Organization Queries
# =============================================================================

class GetOrganizationQuery(Query):
    """Get organization by ID"""
    org_id: uuid.UUID


class GetOrganizationByInnQuery(Query):
    """Get organization by INN"""
    inn: str


class GetOrganizationByKonturIdQuery(Query):
    """Get organization by Kontur org ID"""
    kontur_org_id: str


class ListOrganizationsQuery(Query):
    """List all organizations"""
    limit: int = 50
    offset: int = 0
    include_deleted: bool = False


class SearchOrganizationsQuery(Query):
    """Search organizations by name or INN"""
    search_term: str
    limit: int = 20


# =============================================================================
# Reference Data Queries
# =============================================================================

class GetReferenceDataQuery(Query):
    """Get reference data (procedures, customs offices, declaration types)"""
    data_type: str  # "procedures", "customs_offices", "declaration_types"
    declaration_type: Optional[str] = None  # Filter by declaration type


class GetCustomsProceduresQuery(Query):
    """Get customs procedures for declaration type"""
    declaration_type: Optional[DeclarationType] = None


class GetCustomsOfficesQuery(Query):
    """Get customs offices"""
    country_code: str = "RU"


# =============================================================================
# Query Result Types
# =============================================================================

class DeclarationDetail(BaseModel):
    """Full declaration details"""
    id: uuid.UUID
    user_id: uuid.UUID
    company_id: uuid.UUID
    kontur_docflow_id: Optional[str] = None
    gtd_number: Optional[str] = None
    name: str
    declaration_type: str
    procedure: str
    customs_code: str
    status: int
    organization_id: Optional[str] = None
    employee_id: Optional[str] = None
    declarant_inn: Optional[str] = None
    form_data: Dict[str, Any] = Field(default_factory=dict)
    documents: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    is_deleted: bool = False

    @property
    def status_name(self) -> str:
        """Get human-readable status name"""
        try:
            return DocflowStatus(self.status).name
        except ValueError:
            return f"UNKNOWN_{self.status}"


class DeclarationSummary(BaseModel):
    """Declaration summary for list views"""
    id: uuid.UUID
    name: str
    declaration_type: str
    procedure: str
    customs_code: str
    status: int
    gtd_number: Optional[str] = None
    organization_id: Optional[str] = None
    created_at: datetime
    submitted_at: Optional[datetime] = None
    is_deleted: bool = False


class DeclarationStatus(BaseModel):
    """Declaration status for sync worker"""
    id: uuid.UUID
    name: str
    status: int
    kontur_docflow_id: Optional[str] = None
    gtd_number: Optional[str] = None
    submitted_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OrganizationDetail(BaseModel):
    """Full organization details"""
    id: uuid.UUID
    kontur_org_id: Optional[str] = None
    org_name: str
    short_name: Optional[str] = None
    org_type: int
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    is_foreign: bool = False
    legal_address: Optional[Dict[str, Any]] = None
    actual_address: Optional[Dict[str, Any]] = None
    created_at: datetime
    synced_at: Optional[datetime] = None
    is_deleted: bool = False

    @property
    def org_type_name(self) -> str:
        """Get human-readable org type name"""
        try:
            return OrganizationType(self.org_type).name
        except ValueError:
            return f"UNKNOWN_{self.org_type}"


class OrganizationSummary(BaseModel):
    """Organization summary for list views"""
    id: uuid.UUID
    kontur_org_id: Optional[str] = None
    org_name: str
    short_name: Optional[str] = None
    inn: Optional[str] = None
    is_foreign: bool = False


class CustomsProcedure(BaseModel):
    """Customs procedure reference data"""
    code: str
    name: str
    description: Optional[str] = None
    declaration_type: Optional[str] = None


class CustomsOffice(BaseModel):
    """Customs office reference data"""
    code: str
    name: str
    address: Optional[str] = None
    is_active: bool = True


# =============================================================================
# EOF
# =============================================================================
