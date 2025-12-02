# =============================================================================
# File: app/declarant/routes.py
# Description: API endpoints for Declarant module - References
# =============================================================================

from __future__ import annotations

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.declarant.json_templates_service import JsonTemplatesService
from app.declarant.json_templates_service import SyncResult as JsonSyncResult
from app.declarant.references_service import (
    CustomsService,
    DeclarationTypesService,
    ProceduresService,
    PackagingGroupsService,
    CurrenciesService,
    EnterpriseCategoriesService,
    MeasurementUnitsService,
    DeclarationFeaturesService,
    DocumentTypesService,
    CommonOrgsService,
    OrganizationsService,
    EmployeesService,
    SyncResult,
)
from app.declarant.kontur_client import KonturClientError, get_kontur_client

log = logging.getLogger("wellwon.declarant.routes")

router = APIRouter(prefix="/declarant/references", tags=["Declarant References"])


# =============================================================================
# Response Models
# =============================================================================

class JsonTemplateResponse(BaseModel):
    """JSON template response model"""
    id: str
    gf_code: str
    document_mode_id: str
    type_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    sections_count: int = 0  # Количество настроенных секций в форме
    document_type_code: Optional[str] = None  # Код вида документа (связь с dc_document_types)

    class Config:
        from_attributes = True


class JsonTemplatesListResponse(BaseModel):
    """List of JSON templates with metadata"""
    items: List[JsonTemplateResponse]
    total: int
    unique_forms: int
    last_updated: Optional[datetime] = None


class SyncResultResponse(BaseModel):
    """Sync operation result"""
    success: bool
    total_fetched: int
    inserted: int
    updated: int
    skipped: int
    errors: int
    sync_time: datetime
    message: str


class ReferenceInfo(BaseModel):
    """Reference metadata for listing"""
    id: str
    name: str
    description: str
    endpoint: str
    count: int
    unique_count: Optional[int] = None
    last_updated: Optional[datetime] = None
    # API source info
    api_source: Optional[str] = None
    api_endpoint: Optional[str] = None
    # Database table name
    table_name: Optional[str] = None


class ReferencesListResponse(BaseModel):
    """List of all available references"""
    references: List[ReferenceInfo]


# -----------------------------------------------------------------------------
# Customs Response Models
# -----------------------------------------------------------------------------

class CustomsResponse(BaseModel):
    """Customs office response model"""
    id: str
    kontur_id: str
    code: Optional[str]
    short_name: Optional[str]
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomsListResponse(BaseModel):
    """List of customs offices with metadata"""
    items: List[CustomsResponse]
    total: int
    last_updated: Optional[datetime] = None


# -----------------------------------------------------------------------------
# Declaration Types Response Models
# -----------------------------------------------------------------------------

class DeclarationTypeResponse(BaseModel):
    """Declaration type response model"""
    id: str
    kontur_id: int
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeclarationTypesListResponse(BaseModel):
    """List of declaration types with metadata"""
    items: List[DeclarationTypeResponse]
    total: int
    last_updated: Optional[datetime] = None


# -----------------------------------------------------------------------------
# Procedures Response Models
# -----------------------------------------------------------------------------

class ProcedureResponse(BaseModel):
    """Procedure response model"""
    id: str
    kontur_id: int
    declaration_type_id: int
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProceduresListResponse(BaseModel):
    """List of procedures with metadata"""
    items: List[ProcedureResponse]
    total: int
    unique_codes: Optional[int] = None
    last_updated: Optional[datetime] = None


# -----------------------------------------------------------------------------
# Static Reference Response Models
# -----------------------------------------------------------------------------

class PackagingGroupResponse(BaseModel):
    """Packaging group response model"""
    id: str
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PackagingGroupsListResponse(BaseModel):
    """List of packaging groups with metadata"""
    items: List[PackagingGroupResponse]
    total: int
    last_updated: Optional[datetime] = None


class CurrencyResponse(BaseModel):
    """Currency response model"""
    id: str
    code: str
    alpha_code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CurrenciesListResponse(BaseModel):
    """List of currencies with metadata"""
    items: List[CurrencyResponse]
    total: int
    last_updated: Optional[datetime] = None


class EnterpriseCategoryResponse(BaseModel):
    """Enterprise category response model"""
    id: str
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EnterpriseCategoriesListResponse(BaseModel):
    """List of enterprise categories with metadata"""
    items: List[EnterpriseCategoryResponse]
    total: int
    last_updated: Optional[datetime] = None


class MeasurementUnitResponse(BaseModel):
    """Measurement unit response model"""
    id: str
    code: str
    short_name: str
    full_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MeasurementUnitsListResponse(BaseModel):
    """List of measurement units with metadata"""
    items: List[MeasurementUnitResponse]
    total: int
    last_updated: Optional[datetime] = None


class DeclarationFeatureResponse(BaseModel):
    """Declaration feature response model"""
    id: str
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeclarationFeaturesListResponse(BaseModel):
    """List of declaration features with metadata"""
    items: List[DeclarationFeatureResponse]
    total: int
    last_updated: Optional[datetime] = None


class DocumentTypeResponse(BaseModel):
    """Document type response model"""
    id: str
    code: str
    name: str
    ed_documents: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentTypesListResponse(BaseModel):
    """List of document types with metadata"""
    items: List[DocumentTypeResponse]
    total: int
    last_updated: Optional[datetime] = None


# -----------------------------------------------------------------------------
# CommonOrgs Response Models (Контрагенты)
# -----------------------------------------------------------------------------

class CommonOrgResponse(BaseModel):
    """Counterparty response model"""
    id: str
    kontur_id: str
    org_name: Optional[str] = None
    short_name: Optional[str] = None
    org_type: int = 0
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    is_foreign: bool = False
    legal_address: Optional[dict] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CommonOrgsListResponse(BaseModel):
    """List of counterparties with metadata"""
    items: List[CommonOrgResponse]
    total: int
    last_updated: Optional[datetime] = None


# -----------------------------------------------------------------------------
# Organizations Response Models (Организации)
# -----------------------------------------------------------------------------

class OrganizationResponse(BaseModel):
    """Organization response model"""
    id: str
    kontur_id: str
    name: Optional[str] = None
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    address: Optional[dict] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrganizationsListResponse(BaseModel):
    """List of organizations with metadata"""
    items: List[OrganizationResponse]
    total: int
    last_updated: Optional[datetime] = None


# -----------------------------------------------------------------------------
# Employees Response Models (Подписанты)
# -----------------------------------------------------------------------------

class EmployeeResponse(BaseModel):
    """Employee/Signer response model"""
    id: str
    kontur_id: str
    organization_id: Optional[str] = None
    surname: Optional[str] = None
    name: Optional[str] = None
    patronymic: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    auth_letter_date: Optional[str] = None
    auth_letter_number: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmployeesListResponse(BaseModel):
    """List of employees with metadata"""
    items: List[EmployeeResponse]
    total: int
    last_updated: Optional[datetime] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/", response_model=ReferencesListResponse)
async def list_references():
    """
    Get list of all available references with metadata

    Returns overview of all reference tables for the references page.
    """
    try:
        # JSON Templates stats
        json_templates_count = await JsonTemplatesService.get_count()
        json_templates_unique = await JsonTemplatesService.get_unique_forms_count()
        json_templates_updated = await JsonTemplatesService.get_last_update()

        # Customs stats
        customs_count = await CustomsService.get_count()
        customs_updated = await CustomsService.get_last_update()

        # Declaration Types stats
        declaration_types_count = await DeclarationTypesService.get_count()
        declaration_types_updated = await DeclarationTypesService.get_last_update()

        # Procedures stats
        procedures_count = await ProceduresService.get_count()
        procedures_unique = await ProceduresService.get_unique_codes_count()
        procedures_updated = await ProceduresService.get_last_update()

        # Static references stats
        packaging_groups_count = await PackagingGroupsService.get_count()
        packaging_groups_updated = await PackagingGroupsService.get_last_update()

        currencies_count = await CurrenciesService.get_count()
        currencies_updated = await CurrenciesService.get_last_update()

        enterprise_categories_count = await EnterpriseCategoriesService.get_count()
        enterprise_categories_updated = await EnterpriseCategoriesService.get_last_update()

        measurement_units_count = await MeasurementUnitsService.get_count()
        measurement_units_updated = await MeasurementUnitsService.get_last_update()

        declaration_features_count = await DeclarationFeaturesService.get_count()
        declaration_features_updated = await DeclarationFeaturesService.get_last_update()

        document_types_count = await DocumentTypesService.get_count()
        document_types_updated = await DocumentTypesService.get_last_update()

        # CommonOrgs stats
        common_orgs_count = await CommonOrgsService.get_count()
        common_orgs_updated = await CommonOrgsService.get_last_update()

        # Organizations stats
        organizations_count = await OrganizationsService.get_count()
        organizations_updated = await OrganizationsService.get_last_update()

        # Employees stats
        employees_count = await EmployeesService.get_count()
        employees_updated = await EmployeesService.get_last_update()

        references = [
            ReferenceInfo(
                id="json-templates",
                name=JsonTemplatesService.REFERENCE_NAME,
                description=JsonTemplatesService.REFERENCE_DESCRIPTION,
                endpoint="/declarant/references/json-templates",
                count=json_templates_count,
                unique_count=json_templates_unique,
                last_updated=json_templates_updated,
                api_source="Kontur.Declarant API",
                api_endpoint="GET /common/v1/jsonTemplates",
                table_name=JsonTemplatesService.TABLE_NAME,
            ),
            ReferenceInfo(
                id="customs",
                name=CustomsService.REFERENCE_NAME,
                description=CustomsService.REFERENCE_DESCRIPTION,
                endpoint="/declarant/references/customs",
                count=customs_count,
                last_updated=customs_updated,
                api_source="Kontur.Declarant API",
                api_endpoint="GET /common/v1/options/customs",
                table_name=CustomsService.TABLE_NAME,
            ),
            ReferenceInfo(
                id="declaration-types",
                name=DeclarationTypesService.REFERENCE_NAME,
                description=DeclarationTypesService.REFERENCE_DESCRIPTION,
                endpoint="/declarant/references/declaration-types",
                count=declaration_types_count,
                last_updated=declaration_types_updated,
                api_source="Kontur.Declarant API",
                api_endpoint="GET /common/v1/options/declarationTypes",
                table_name=DeclarationTypesService.TABLE_NAME,
            ),
            ReferenceInfo(
                id="procedures",
                name=ProceduresService.REFERENCE_NAME,
                description=ProceduresService.REFERENCE_DESCRIPTION,
                endpoint="/declarant/references/procedures",
                count=procedures_count,
                unique_count=procedures_unique,
                last_updated=procedures_updated,
                api_source="Kontur.Declarant API",
                api_endpoint="GET /common/v1/options/declarationProcedureTypes",
                table_name=ProceduresService.TABLE_NAME,
            ),
            # Static references
            ReferenceInfo(
                id="packaging-groups",
                name=PackagingGroupsService.REFERENCE_NAME,
                description=PackagingGroupsService.REFERENCE_DESCRIPTION,
                endpoint="/declarant/references/packaging-groups",
                count=packaging_groups_count,
                last_updated=packaging_groups_updated,
                table_name=PackagingGroupsService.TABLE_NAME,
            ),
            ReferenceInfo(
                id="currencies",
                name=CurrenciesService.REFERENCE_NAME,
                description=CurrenciesService.REFERENCE_DESCRIPTION,
                endpoint="/declarant/references/currencies",
                count=currencies_count,
                last_updated=currencies_updated,
                table_name=CurrenciesService.TABLE_NAME,
            ),
            ReferenceInfo(
                id="enterprise-categories",
                name=EnterpriseCategoriesService.REFERENCE_NAME,
                description=EnterpriseCategoriesService.REFERENCE_DESCRIPTION,
                endpoint="/declarant/references/enterprise-categories",
                count=enterprise_categories_count,
                last_updated=enterprise_categories_updated,
                table_name=EnterpriseCategoriesService.TABLE_NAME,
            ),
            ReferenceInfo(
                id="measurement-units",
                name=MeasurementUnitsService.REFERENCE_NAME,
                description=MeasurementUnitsService.REFERENCE_DESCRIPTION,
                endpoint="/declarant/references/measurement-units",
                count=measurement_units_count,
                last_updated=measurement_units_updated,
                table_name=MeasurementUnitsService.TABLE_NAME,
            ),
            # API references - Контрагенты и Подписанты
            ReferenceInfo(
                id="common-orgs",
                name=CommonOrgsService.REFERENCE_NAME,
                description=CommonOrgsService.REFERENCE_DESCRIPTION,
                endpoint="/declarant/references/common-orgs",
                count=common_orgs_count,
                last_updated=common_orgs_updated,
                api_source="Kontur.Declarant API",
                api_endpoint="GET /common/v1/options/commonOrgs",
                table_name=CommonOrgsService.TABLE_NAME,
            ),
            ReferenceInfo(
                id="organizations",
                name=OrganizationsService.REFERENCE_NAME,
                description=OrganizationsService.REFERENCE_DESCRIPTION,
                endpoint="/declarant/references/organizations",
                count=organizations_count,
                last_updated=organizations_updated,
                api_source="Kontur.Declarant API",
                api_endpoint="GET /common/v1/options/organizations",
                table_name=OrganizationsService.TABLE_NAME,
            ),
            ReferenceInfo(
                id="employees",
                name=EmployeesService.REFERENCE_NAME,
                description=EmployeesService.REFERENCE_DESCRIPTION,
                endpoint="/declarant/references/employees",
                count=employees_count,
                last_updated=employees_updated,
                api_source="Kontur.Declarant API",
                api_endpoint="GET /common/v1/options/employees",
                table_name=EmployeesService.TABLE_NAME,
            ),
            # API reference - Особенности
            ReferenceInfo(
                id="declaration-features",
                name=DeclarationFeaturesService.REFERENCE_NAME,
                description=DeclarationFeaturesService.REFERENCE_DESCRIPTION,
                endpoint="/declarant/references/declaration-features",
                count=declaration_features_count,
                last_updated=declaration_features_updated,
                api_source="Kontur.Declarant API",
                api_endpoint="GET /common/v1/options/declarationSingularities",
                table_name=DeclarationFeaturesService.TABLE_NAME,
            ),
            # Static reference - Виды документов
            ReferenceInfo(
                id="document-types",
                name=DocumentTypesService.REFERENCE_NAME,
                description=DocumentTypesService.REFERENCE_DESCRIPTION,
                endpoint="/declarant/references/document-types",
                count=document_types_count,
                last_updated=document_types_updated,
                table_name=DocumentTypesService.TABLE_NAME,
            ),
        ]

        return ReferencesListResponse(references=references)

    except Exception as e:
        log.error(f"Error listing references: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing references: {str(e)}"
        )


@router.get("/json-templates", response_model=JsonTemplatesListResponse)
async def get_json_templates(include_inactive: bool = False):
    """
    Get all JSON templates

    Args:
        include_inactive: Include inactive templates (default: False)

    Returns:
        List of JSON templates with metadata
    """
    try:
        items = await JsonTemplatesService.get_all(include_inactive=include_inactive)
        unique_forms = await JsonTemplatesService.get_unique_forms_count()
        last_updated = await JsonTemplatesService.get_last_update()

        return JsonTemplatesListResponse(
            items=[
                JsonTemplateResponse(
                    id=item.id,
                    gf_code=item.gf_code,
                    document_mode_id=item.document_mode_id,
                    type_name=item.type_name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    sections_count=item.sections_count
                )
                for item in items
            ],
            total=len(items),
            unique_forms=unique_forms,
            last_updated=last_updated
        )
    except Exception as e:
        log.error(f"Error getting JSON templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting JSON templates: {str(e)}"
        )


@router.post("/json-templates/sync", response_model=SyncResultResponse)
async def sync_json_templates():
    """
    Sync JSON templates from Kontur API

    Fetches templates from Kontur API (GET /common/v1/jsonTemplates)
    and updates the local database.

    Returns:
        Sync operation result with statistics
    """
    try:
        log.info("Starting JSON templates sync from Kontur API")

        result: JsonSyncResult = await JsonTemplatesService.sync_from_api()

        message = f"Синхронизировано {result.total_fetched} шаблонов"
        if result.inserted > 0:
            message += f" (новых: {result.inserted})"
        if result.updated > 0:
            message += f" (обновлено: {result.updated})"
        if result.skipped > 0:
            message += f" (пропущено: {result.skipped})"
        if result.errors > 0:
            message += f" (ошибок: {result.errors})"

        return SyncResultResponse(
            success=True,
            total_fetched=result.total_fetched,
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors,
            sync_time=result.sync_time,
            message=message
        )

    except KonturClientError as e:
        log.error(f"Kontur API error during sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Kontur API: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error syncing JSON templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка синхронизации: {str(e)}"
        )


@router.get("/json-templates/{document_mode_id}/schema")
async def get_json_template_schema(document_mode_id: str):
    """
    Get full JSON schema for a specific document template

    Args:
        document_mode_id: The document mode ID (e.g., "1002007E")

    Returns:
        Full JSON schema from Kontur API
    """
    try:
        from app.declarant.kontur_client import get_kontur_client
        import json

        client = get_kontur_client()
        schema_str = await client.get_document_template(document_mode_id)

        # Parse JSON string to object
        try:
            schema = json.loads(schema_str)
        except json.JSONDecodeError:
            schema = {"raw": schema_str}

        return {
            "document_mode_id": document_mode_id,
            "schema": schema
        }

    except KonturClientError as e:
        log.error(f"Kontur API error fetching schema for {document_mode_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Kontur API: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error fetching schema for {document_mode_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения схемы: {str(e)}"
        )


@router.get("/json-templates/search")
async def search_json_templates(q: str, limit: int = 50):
    """
    Search JSON templates by name, documentModeId or gf_code

    Args:
        q: Search query
        limit: Max results (default: 50)

    Returns:
        List of matching templates
    """
    try:
        items = await JsonTemplatesService.search(q, limit)

        return {
            "items": [
                JsonTemplateResponse(
                    id=item.id,
                    gf_code=item.gf_code,
                    document_mode_id=item.document_mode_id,
                    type_name=item.type_name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    sections_count=item.sections_count
                )
                for item in items
            ],
            "total": len(items),
            "query": q
        }
    except Exception as e:
        log.error(f"Error searching JSON templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching: {str(e)}"
        )


# =============================================================================
# Customs Endpoints (Таможенные органы)
# =============================================================================

@router.get("/customs", response_model=CustomsListResponse)
async def get_customs(include_inactive: bool = False):
    """
    Get all customs offices (таможенные органы)

    Args:
        include_inactive: Include inactive entries (default: False)

    Returns:
        List of customs offices with metadata
    """
    try:
        items = await CustomsService.get_all(include_inactive=include_inactive)
        last_updated = await CustomsService.get_last_update()

        return CustomsListResponse(
            items=[
                CustomsResponse(
                    id=item.id,
                    kontur_id=item.kontur_id,
                    code=item.code,
                    short_name=item.short_name,
                    full_name=item.full_name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            total=len(items),
            last_updated=last_updated
        )
    except Exception as e:
        log.error(f"Error getting customs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting customs: {str(e)}"
        )


@router.post("/customs/sync", response_model=SyncResultResponse)
async def sync_customs():
    """
    Sync customs offices from Kontur API

    Fetches from GET /common/v1/options/customs
    and updates the local database.

    Returns:
        Sync operation result with statistics
    """
    try:
        log.info("Starting customs sync from Kontur API")

        result: SyncResult = await CustomsService.sync_from_api()

        message = f"Синхронизировано {result.total_fetched} таможенных органов"
        if result.inserted > 0:
            message += f" (новых: {result.inserted})"
        if result.updated > 0:
            message += f" (обновлено: {result.updated})"
        if result.skipped > 0:
            message += f" (пропущено: {result.skipped})"
        if result.errors > 0:
            message += f" (ошибок: {result.errors})"

        return SyncResultResponse(
            success=True,
            total_fetched=result.total_fetched,
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors,
            sync_time=result.sync_time,
            message=message
        )

    except KonturClientError as e:
        log.error(f"Kontur API error during customs sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Kontur API: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error syncing customs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка синхронизации: {str(e)}"
        )


@router.get("/customs/search")
async def search_customs(q: str, limit: int = 50):
    """
    Search customs offices by name or code

    Args:
        q: Search query
        limit: Max results (default: 50)

    Returns:
        List of matching customs offices
    """
    try:
        items = await CustomsService.search(q, limit)

        return {
            "items": [
                CustomsResponse(
                    id=item.id,
                    kontur_id=item.kontur_id,
                    code=item.code,
                    short_name=item.short_name,
                    full_name=item.full_name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            "total": len(items),
            "query": q
        }
    except Exception as e:
        log.error(f"Error searching customs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching: {str(e)}"
        )


# =============================================================================
# Declaration Types Endpoints (Типы деклараций)
# =============================================================================

@router.get("/declaration-types", response_model=DeclarationTypesListResponse)
async def get_declaration_types(include_inactive: bool = False):
    """
    Get all declaration types (типы деклараций / направления перемещения)

    Args:
        include_inactive: Include inactive entries (default: False)

    Returns:
        List of declaration types with metadata
    """
    try:
        items = await DeclarationTypesService.get_all(include_inactive=include_inactive)
        last_updated = await DeclarationTypesService.get_last_update()

        return DeclarationTypesListResponse(
            items=[
                DeclarationTypeResponse(
                    id=item.id,
                    kontur_id=item.kontur_id,
                    description=item.description,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            total=len(items),
            last_updated=last_updated
        )
    except Exception as e:
        log.error(f"Error getting declaration types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting declaration types: {str(e)}"
        )


@router.post("/declaration-types/sync", response_model=SyncResultResponse)
async def sync_declaration_types():
    """
    Sync declaration types from Kontur API

    Fetches from GET /common/v1/options/declarationTypes
    and updates the local database.

    Returns:
        Sync operation result with statistics
    """
    try:
        log.info("Starting declaration types sync from Kontur API")

        result: SyncResult = await DeclarationTypesService.sync_from_api()

        message = f"Синхронизировано {result.total_fetched} типов деклараций"
        if result.inserted > 0:
            message += f" (новых: {result.inserted})"
        if result.updated > 0:
            message += f" (обновлено: {result.updated})"
        if result.skipped > 0:
            message += f" (пропущено: {result.skipped})"
        if result.errors > 0:
            message += f" (ошибок: {result.errors})"

        return SyncResultResponse(
            success=True,
            total_fetched=result.total_fetched,
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors,
            sync_time=result.sync_time,
            message=message
        )

    except KonturClientError as e:
        log.error(f"Kontur API error during declaration types sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Kontur API: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error syncing declaration types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка синхронизации: {str(e)}"
        )


# =============================================================================
# Procedures Endpoints (Таможенные процедуры)
# =============================================================================

@router.get("/procedures", response_model=ProceduresListResponse)
async def get_procedures(
    include_inactive: bool = False,
    declaration_type_id: Optional[int] = Query(None, description="Filter by declaration type ID")
):
    """
    Get all customs procedures (таможенные процедуры)

    Args:
        include_inactive: Include inactive entries (default: False)
        declaration_type_id: Optional filter by declaration type (0=ИМ, 1=ЭК, etc.)

    Returns:
        List of procedures with metadata
    """
    try:
        items = await ProceduresService.get_all(
            include_inactive=include_inactive,
            declaration_type_id=declaration_type_id
        )
        unique_codes = await ProceduresService.get_unique_codes_count()
        last_updated = await ProceduresService.get_last_update()

        return ProceduresListResponse(
            items=[
                ProcedureResponse(
                    id=item.id,
                    kontur_id=item.kontur_id,
                    declaration_type_id=item.declaration_type_id,
                    code=item.code,
                    name=item.name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            total=len(items),
            unique_codes=unique_codes,
            last_updated=last_updated
        )
    except Exception as e:
        log.error(f"Error getting procedures: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting procedures: {str(e)}"
        )


@router.post("/procedures/sync", response_model=SyncResultResponse)
async def sync_procedures():
    """
    Sync customs procedures from Kontur API

    Fetches procedures for all declaration types from
    GET /common/v1/options/declarationProcedureTypes
    and updates the local database.

    Returns:
        Sync operation result with statistics
    """
    try:
        log.info("Starting procedures sync from Kontur API")

        result: SyncResult = await ProceduresService.sync_from_api()

        message = f"Синхронизировано {result.total_fetched} процедур"
        if result.inserted > 0:
            message += f" (новых: {result.inserted})"
        if result.updated > 0:
            message += f" (обновлено: {result.updated})"
        if result.skipped > 0:
            message += f" (пропущено: {result.skipped})"
        if result.errors > 0:
            message += f" (ошибок: {result.errors})"

        return SyncResultResponse(
            success=True,
            total_fetched=result.total_fetched,
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors,
            sync_time=result.sync_time,
            message=message
        )

    except KonturClientError as e:
        log.error(f"Kontur API error during procedures sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Kontur API: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error syncing procedures: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка синхронизации: {str(e)}"
        )


@router.get("/procedures/search")
async def search_procedures(q: str, limit: int = 50):
    """
    Search procedures by name or code

    Args:
        q: Search query
        limit: Max results (default: 50)

    Returns:
        List of matching procedures
    """
    try:
        items = await ProceduresService.search(q, limit)

        return {
            "items": [
                ProcedureResponse(
                    id=item.id,
                    kontur_id=item.kontur_id,
                    declaration_type_id=item.declaration_type_id,
                    code=item.code,
                    name=item.name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            "total": len(items),
            "query": q
        }
    except Exception as e:
        log.error(f"Error searching procedures: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching: {str(e)}"
        )


# =============================================================================
# Packaging Groups Endpoints (Группы упаковки) - Static
# =============================================================================

@router.get("/packaging-groups", response_model=PackagingGroupsListResponse)
async def get_packaging_groups(include_inactive: bool = False):
    """
    Get all packaging groups (группы упаковки)

    Args:
        include_inactive: Include inactive entries (default: False)

    Returns:
        List of packaging groups with metadata
    """
    try:
        items = await PackagingGroupsService.get_all(include_inactive=include_inactive)
        last_updated = await PackagingGroupsService.get_last_update()

        return PackagingGroupsListResponse(
            items=[
                PackagingGroupResponse(
                    id=item.id,
                    code=item.code,
                    name=item.name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            total=len(items),
            last_updated=last_updated
        )
    except Exception as e:
        log.error(f"Error getting packaging groups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting packaging groups: {str(e)}"
        )


# =============================================================================
# Currencies Endpoints (Валюты) - Static
# =============================================================================

@router.get("/currencies", response_model=CurrenciesListResponse)
async def get_currencies(include_inactive: bool = False):
    """
    Get all currencies (валюты)

    Args:
        include_inactive: Include inactive entries (default: False)

    Returns:
        List of currencies with metadata
    """
    try:
        items = await CurrenciesService.get_all(include_inactive=include_inactive)
        last_updated = await CurrenciesService.get_last_update()

        return CurrenciesListResponse(
            items=[
                CurrencyResponse(
                    id=item.id,
                    code=item.code,
                    alpha_code=item.alpha_code,
                    name=item.name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            total=len(items),
            last_updated=last_updated
        )
    except Exception as e:
        log.error(f"Error getting currencies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting currencies: {str(e)}"
        )


@router.get("/currencies/search")
async def search_currencies(q: str, limit: int = 50):
    """
    Search currencies by code or name

    Args:
        q: Search query
        limit: Max results (default: 50)

    Returns:
        List of matching currencies
    """
    try:
        items = await CurrenciesService.search(q, limit)

        return {
            "items": [
                CurrencyResponse(
                    id=item.id,
                    code=item.code,
                    alpha_code=item.alpha_code,
                    name=item.name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            "total": len(items),
            "query": q
        }
    except Exception as e:
        log.error(f"Error searching currencies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching: {str(e)}"
        )


# =============================================================================
# Enterprise Categories Endpoints (Категории предприятий) - Static
# =============================================================================

@router.get("/enterprise-categories", response_model=EnterpriseCategoriesListResponse)
async def get_enterprise_categories(include_inactive: bool = False):
    """
    Get all enterprise categories (категории предприятий)

    Args:
        include_inactive: Include inactive entries (default: False)

    Returns:
        List of enterprise categories with metadata
    """
    try:
        items = await EnterpriseCategoriesService.get_all(include_inactive=include_inactive)
        last_updated = await EnterpriseCategoriesService.get_last_update()

        return EnterpriseCategoriesListResponse(
            items=[
                EnterpriseCategoryResponse(
                    id=item.id,
                    code=item.code,
                    name=item.name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            total=len(items),
            last_updated=last_updated
        )
    except Exception as e:
        log.error(f"Error getting enterprise categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting enterprise categories: {str(e)}"
        )


@router.get("/enterprise-categories/search")
async def search_enterprise_categories(q: str, limit: int = 50):
    """
    Search enterprise categories by code or name

    Args:
        q: Search query
        limit: Max results (default: 50)

    Returns:
        List of matching enterprise categories
    """
    try:
        items = await EnterpriseCategoriesService.search(q, limit)

        return {
            "items": [
                EnterpriseCategoryResponse(
                    id=item.id,
                    code=item.code,
                    name=item.name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            "total": len(items),
            "query": q
        }
    except Exception as e:
        log.error(f"Error searching enterprise categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching: {str(e)}"
        )


# =============================================================================
# Measurement Units Endpoints (Единицы измерения) - Static
# =============================================================================

@router.get("/measurement-units", response_model=MeasurementUnitsListResponse)
async def get_measurement_units(include_inactive: bool = False):
    """
    Get all measurement units (единицы измерения)

    Args:
        include_inactive: Include inactive entries (default: False)

    Returns:
        List of measurement units with metadata
    """
    try:
        items = await MeasurementUnitsService.get_all(include_inactive=include_inactive)
        last_updated = await MeasurementUnitsService.get_last_update()

        return MeasurementUnitsListResponse(
            items=[
                MeasurementUnitResponse(
                    id=item.id,
                    code=item.code,
                    short_name=item.short_name,
                    full_name=item.full_name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            total=len(items),
            last_updated=last_updated
        )
    except Exception as e:
        log.error(f"Error getting measurement units: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting measurement units: {str(e)}"
        )


@router.get("/measurement-units/search")
async def search_measurement_units(q: str, limit: int = 50):
    """
    Search measurement units by code or name

    Args:
        q: Search query
        limit: Max results (default: 50)

    Returns:
        List of matching measurement units
    """
    try:
        items = await MeasurementUnitsService.search(q, limit)

        return {
            "items": [
                MeasurementUnitResponse(
                    id=item.id,
                    code=item.code,
                    short_name=item.short_name,
                    full_name=item.full_name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            "total": len(items),
            "query": q
        }
    except Exception as e:
        log.error(f"Error searching measurement units: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching: {str(e)}"
        )


# =============================================================================
# Declaration Features Endpoints (Особенности) - Static
# =============================================================================

@router.get("/declaration-features", response_model=DeclarationFeaturesListResponse)
async def get_declaration_features(include_inactive: bool = False):
    """
    Get all declaration features (особенности декларирования)

    Args:
        include_inactive: Include inactive entries (default: False)

    Returns:
        List of declaration features with metadata
    """
    try:
        items = await DeclarationFeaturesService.get_all(include_inactive=include_inactive)
        last_updated = await DeclarationFeaturesService.get_last_update()

        return DeclarationFeaturesListResponse(
            items=[
                DeclarationFeatureResponse(
                    id=item.id,
                    code=item.code,
                    name=item.name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            total=len(items),
            last_updated=last_updated
        )
    except Exception as e:
        log.error(f"Error getting declaration features: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting declaration features: {str(e)}"
        )


@router.post("/declaration-features/sync", response_model=SyncResultResponse)
async def sync_declaration_features():
    """
    Sync declaration features from Kontur API

    Fetches declaration singularities from Kontur API and updates local database.
    """
    try:
        result = await DeclarationFeaturesService.sync_from_api()

        return SyncResultResponse(
            success=True,
            total_fetched=result.total_fetched,
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors,
            sync_time=result.sync_time,
            message=f"Синхронизировано {result.total_fetched} особенностей декларирования"
        )
    except KonturClientError as e:
        log.error(f"Kontur API error syncing declaration features: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Kontur API error: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error syncing declaration features: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error syncing: {str(e)}"
        )


# =============================================================================
# Document Types Endpoints (Виды документов) - Static
# =============================================================================

@router.get("/document-types", response_model=DocumentTypesListResponse)
async def get_document_types(include_inactive: bool = False):
    """
    Get all document types (виды документов)

    Args:
        include_inactive: Include inactive entries (default: False)

    Returns:
        List of document types with metadata
    """
    try:
        items = await DocumentTypesService.get_all(include_inactive=include_inactive)
        last_updated = await DocumentTypesService.get_last_update()

        return DocumentTypesListResponse(
            items=[
                DocumentTypeResponse(
                    id=item.id,
                    code=item.code,
                    name=item.name,
                    ed_documents=item.ed_documents,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            total=len(items),
            last_updated=last_updated
        )
    except Exception as e:
        log.error(f"Error getting document types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting document types: {str(e)}"
        )


@router.get("/document-types/search")
async def search_document_types(q: str, limit: int = 50):
    """
    Search document types by code, name, or ED documents

    Args:
        q: Search query
        limit: Max results (default: 50)

    Returns:
        List of matching document types
    """
    try:
        items = await DocumentTypesService.search(q, limit)

        return {
            "items": [
                DocumentTypeResponse(
                    id=item.id,
                    code=item.code,
                    name=item.name,
                    ed_documents=item.ed_documents,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            "total": len(items),
            "query": q
        }
    except Exception as e:
        log.error(f"Error searching document types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching: {str(e)}"
        )


# =============================================================================
# CommonOrgs Endpoints (Контрагенты)
# =============================================================================

@router.get("/common-orgs", response_model=CommonOrgsListResponse)
async def get_common_orgs(include_inactive: bool = False):
    """
    Get all counterparties (контрагенты)

    Args:
        include_inactive: Include inactive entries (default: False)

    Returns:
        List of counterparties with metadata
    """
    try:
        items = await CommonOrgsService.get_all(include_inactive=include_inactive)
        last_updated = await CommonOrgsService.get_last_update()

        return CommonOrgsListResponse(
            items=[
                CommonOrgResponse(
                    id=item.id,
                    kontur_id=item.kontur_id,
                    org_name=item.org_name,
                    short_name=item.short_name,
                    org_type=item.org_type,
                    inn=item.inn,
                    kpp=item.kpp,
                    ogrn=item.ogrn,
                    is_foreign=item.is_foreign,
                    legal_address=item.legal_address,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            total=len(items),
            last_updated=last_updated
        )
    except Exception as e:
        log.error(f"Error getting common orgs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting counterparties: {str(e)}"
        )


@router.post("/common-orgs/sync", response_model=SyncResultResponse)
async def sync_common_orgs():
    """
    Sync counterparties from Kontur API

    Fetches from GET /common/v1/options/commonOrgs
    and updates the local database.

    Returns:
        Sync operation result with statistics
    """
    try:
        log.info("Starting common orgs sync from Kontur API")

        result: SyncResult = await CommonOrgsService.sync_from_api()

        message = f"Синхронизировано {result.total_fetched} контрагентов"
        if result.inserted > 0:
            message += f" (новых: {result.inserted})"
        if result.updated > 0:
            message += f" (обновлено: {result.updated})"

        return SyncResultResponse(
            success=True,
            total_fetched=result.total_fetched,
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors,
            sync_time=result.sync_time,
            message=message
        )

    except KonturClientError as e:
        log.error(f"Kontur API error during common orgs sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Kontur API: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error syncing common orgs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка синхронизации: {str(e)}"
        )


@router.get("/common-orgs/search")
async def search_common_orgs(q: str, limit: int = 50):
    """
    Search counterparties by name or INN

    Args:
        q: Search query
        limit: Max results (default: 50)

    Returns:
        List of matching counterparties
    """
    try:
        items = await CommonOrgsService.search(q, limit)

        return {
            "items": [
                CommonOrgResponse(
                    id=item.id,
                    kontur_id=item.kontur_id,
                    org_name=item.org_name,
                    short_name=item.short_name,
                    org_type=item.org_type,
                    inn=item.inn,
                    kpp=item.kpp,
                    ogrn=item.ogrn,
                    is_foreign=item.is_foreign,
                    legal_address=item.legal_address,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            "total": len(items),
            "query": q
        }
    except Exception as e:
        log.error(f"Error searching common orgs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching: {str(e)}"
        )


# =============================================================================
# Organizations Endpoints (Организации)
# =============================================================================

@router.get("/organizations", response_model=OrganizationsListResponse)
async def get_organizations(include_inactive: bool = False):
    """
    Get all organizations (свои организации)

    Args:
        include_inactive: Include inactive entries (default: False)

    Returns:
        List of organizations with metadata
    """
    try:
        items = await OrganizationsService.get_all(include_inactive=include_inactive)
        last_updated = await OrganizationsService.get_last_update()

        return OrganizationsListResponse(
            items=[
                OrganizationResponse(
                    id=item.id,
                    kontur_id=item.kontur_id,
                    name=item.name,
                    inn=item.inn,
                    kpp=item.kpp,
                    ogrn=item.ogrn,
                    address=item.address,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            total=len(items),
            last_updated=last_updated
        )
    except Exception as e:
        log.error(f"Error getting organizations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting organizations: {str(e)}"
        )


@router.post("/organizations/sync", response_model=SyncResultResponse)
async def sync_organizations():
    """
    Sync organizations from Kontur API

    Fetches from GET /common/v1/options/organizations
    and updates the local database.

    Returns:
        Sync operation result with statistics
    """
    try:
        log.info("Starting organizations sync from Kontur API")

        result: SyncResult = await OrganizationsService.sync_from_api()

        message = f"Синхронизировано {result.total_fetched} организаций"
        if result.inserted > 0:
            message += f" (новых: {result.inserted})"
        if result.updated > 0:
            message += f" (обновлено: {result.updated})"

        return SyncResultResponse(
            success=True,
            total_fetched=result.total_fetched,
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors,
            sync_time=result.sync_time,
            message=message
        )

    except KonturClientError as e:
        log.error(f"Kontur API error during organizations sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Kontur API: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error syncing organizations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка синхронизации: {str(e)}"
        )


# =============================================================================
# Employees Endpoints (Подписанты)
# =============================================================================

@router.get("/employees", response_model=EmployeesListResponse)
async def get_employees(
    include_inactive: bool = False,
    organization_id: Optional[str] = Query(None, description="Filter by organization ID")
):
    """
    Get all employees/signers (подписанты)

    Args:
        include_inactive: Include inactive entries (default: False)
        organization_id: Optional filter by organization UUID

    Returns:
        List of employees with metadata
    """
    try:
        items = await EmployeesService.get_all(
            include_inactive=include_inactive,
            organization_id=organization_id
        )
        last_updated = await EmployeesService.get_last_update()

        return EmployeesListResponse(
            items=[
                EmployeeResponse(
                    id=item.id,
                    kontur_id=item.kontur_id,
                    organization_id=item.organization_id,
                    surname=item.surname,
                    name=item.name,
                    patronymic=item.patronymic,
                    phone=item.phone,
                    email=item.email,
                    auth_letter_date=item.auth_letter_date,
                    auth_letter_number=item.auth_letter_number,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            total=len(items),
            last_updated=last_updated
        )
    except Exception as e:
        log.error(f"Error getting employees: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting employees: {str(e)}"
        )


@router.post("/employees/sync", response_model=SyncResultResponse)
async def sync_employees():
    """
    Sync employees from Kontur API for all organizations

    First syncs organizations, then fetches employees for each.
    Endpoint: GET /common/v1/options/employees?orgId={orgId}

    Returns:
        Sync operation result with statistics
    """
    try:
        log.info("Starting employees sync from Kontur API")

        result: SyncResult = await EmployeesService.sync_from_api()

        message = f"Синхронизировано {result.total_fetched} подписантов"
        if result.inserted > 0:
            message += f" (новых: {result.inserted})"
        if result.updated > 0:
            message += f" (обновлено: {result.updated})"

        return SyncResultResponse(
            success=True,
            total_fetched=result.total_fetched,
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors,
            sync_time=result.sync_time,
            message=message
        )

    except KonturClientError as e:
        log.error(f"Kontur API error during employees sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Kontur API: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error syncing employees: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка синхронизации: {str(e)}"
        )


@router.get("/employees/search")
async def search_employees(q: str, limit: int = 50):
    """
    Search employees by name or email

    Args:
        q: Search query
        limit: Max results (default: 50)

    Returns:
        List of matching employees
    """
    try:
        items = await EmployeesService.search(q, limit)

        return {
            "items": [
                EmployeeResponse(
                    id=item.id,
                    kontur_id=item.kontur_id,
                    organization_id=item.organization_id,
                    surname=item.surname,
                    name=item.name,
                    patronymic=item.patronymic,
                    phone=item.phone,
                    email=item.email,
                    auth_letter_date=item.auth_letter_date,
                    auth_letter_number=item.auth_letter_number,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in items
            ],
            "total": len(items),
            "query": q
        }
    except Exception as e:
        log.error(f"Error searching employees: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching: {str(e)}"
        )


# =============================================================================
# Docflows API (документооборот / пакеты деклараций)
# =============================================================================

docflows_router = APIRouter(prefix="/declarant/docflows", tags=["Declarant Docflows"])


class CreateDocflowRequest(BaseModel):
    """Request model for creating a docflow"""
    type: int  # Declaration type: 0=ИМ, 1=ЭК, etc.
    procedure: int  # Customs procedure ID
    customs: int  # Customs office code (e.g., 10130010)
    organization_id: str  # Organization UUID
    employee_id: str  # Employee (signer) UUID
    singularity: Optional[int] = None  # Optional singularity ID
    name: Optional[str] = None  # Optional docflow name


class DocflowResponse(BaseModel):
    """Response model for docflow"""
    id: str
    version: int
    state: int
    type: int
    procedure: int
    singularity: Optional[int] = None
    customs: int
    name: Optional[str] = None
    organization_id: str
    employee_id: str
    create_date: Optional[datetime] = None
    update_date: Optional[datetime] = None


@docflows_router.post("", response_model=DocflowResponse)
async def create_docflow(request: CreateDocflowRequest):
    """
    Create a new docflow (пакет декларации) in Kontur API

    Args:
        request: Docflow creation data

    Returns:
        Created docflow data
    """
    try:
        log.info(f"Creating docflow: type={request.type}, procedure={request.procedure}")

        client = get_kontur_client()
        result = await client.create_docflow(
            declaration_type=request.type,
            procedure=request.procedure,
            customs=request.customs,
            organization_id=request.organization_id,
            employee_id=request.employee_id,
            singularity=request.singularity,
            name=request.name
        )

        return DocflowResponse(
            id=result.get("id", ""),
            version=result.get("version", 1),
            state=result.get("state", 0),
            type=result.get("type", request.type),
            procedure=result.get("procedure", request.procedure),
            singularity=result.get("singularity"),
            customs=result.get("customs", request.customs),
            name=result.get("name"),
            organization_id=result.get("organizationId", request.organization_id),
            employee_id=result.get("employeeId", request.employee_id),
            create_date=result.get("createDate"),
            update_date=result.get("updateDate")
        )

    except KonturClientError as e:
        log.error(f"Kontur API error creating docflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Kontur API: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error creating docflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания пакета: {str(e)}"
        )
