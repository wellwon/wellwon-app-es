# =============================================================================
# File: app/declarant/routes.py
# Description: API endpoints for Declarant module - References
# =============================================================================

from __future__ import annotations

import logging
from typing import List, Optional
from datetime import datetime

import os
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
from app.declarant.dadata_client import DaDataClientError, get_dadata_client, CompanyInfo
from app.declarant.docflow_repository import DocflowRepository, DocflowReadModel

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
    okato: Optional[str] = None
    okpo: Optional[str] = None
    oktmo: Optional[str] = None
    is_foreign: bool = False
    legal_address: Optional[dict] = None
    actual_address: Optional[dict] = None
    person: Optional[dict] = None
    identity_card: Optional[dict] = None
    bank_requisites: Optional[list] = None
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
                    okato=item.okato,
                    okpo=item.okpo,
                    oktmo=item.oktmo,
                    is_foreign=item.is_foreign,
                    legal_address=item.legal_address,
                    actual_address=item.actual_address,
                    person=item.person,
                    identity_card=item.identity_card,
                    bank_requisites=item.bank_requisites,
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
                    okato=item.okato,
                    okpo=item.okpo,
                    oktmo=item.oktmo,
                    is_foreign=item.is_foreign,
                    legal_address=item.legal_address,
                    actual_address=item.actual_address,
                    person=item.person,
                    identity_card=item.identity_card,
                    bank_requisites=item.bank_requisites,
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


class DeleteContractorRequest(BaseModel):
    """Request for deleting a contractor with password confirmation"""
    password: str


@router.delete("/common-orgs/{contractor_id}")
async def delete_common_org(contractor_id: str, request: DeleteContractorRequest):
    """
    Delete a counterparty (контрагент) with password confirmation

    Args:
        contractor_id: UUID of the contractor to delete
        password: Admin password for confirmation

    Returns:
        Success message
    """
    from app.infra.persistence import pg_client

    # Get password from environment
    admin_password = os.getenv("ADMIN_DELETE_PASSWORD", "")

    if not admin_password:
        log.error("ADMIN_DELETE_PASSWORD not configured in environment")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Удаление не настроено"
        )

    if request.password != admin_password:
        log.warning(f"Invalid delete password attempt for contractor {contractor_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Неверный пароль"
        )

    try:
        # Check if contractor exists
        existing = await pg_client.fetchrow(
            "SELECT id, short_name, org_name FROM dc_common_orgs WHERE id = $1",
            contractor_id
        )

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Контрагент не найден"
            )

        # Delete contractor (CASCADE will delete bank accounts)
        await pg_client.execute(
            "DELETE FROM dc_common_orgs WHERE id = $1",
            contractor_id
        )

        name = existing["short_name"] or existing["org_name"] or "Контрагент"
        log.info(f"Deleted contractor {contractor_id}: {name}")

        return {
            "success": True,
            "message": f"Контрагент '{name}' удален"
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error deleting contractor {contractor_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления: {str(e)}"
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


@router.delete("/organizations/{organization_id}")
async def delete_organization(organization_id: str, request: DeleteContractorRequest):
    """
    Delete an organization by ID (with password confirmation)

    Requires admin password for confirmation.
    """
    admin_password = os.getenv("ADMIN_DELETE_PASSWORD", "")

    if not admin_password:
        log.error("ADMIN_DELETE_PASSWORD not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Удаление не настроено"
        )

    if request.password != admin_password:
        log.warning(f"Invalid delete password attempt for organization {organization_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Неверный пароль"
        )

    try:
        # Check if organization exists
        existing = await pg_client.fetchrow(
            "SELECT id, name FROM dc_organizations WHERE id = $1",
            organization_id
        )

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Организация не найдена"
            )

        # Delete organization
        await pg_client.execute(
            "DELETE FROM dc_organizations WHERE id = $1",
            organization_id
        )

        name = existing["name"] or "Организация"
        log.info(f"Deleted organization {organization_id}: {name}")

        return {
            "success": True,
            "message": f"Организация '{name}' удалена"
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error deleting organization {organization_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления: {str(e)}"
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


class DocflowDocumentItem(BaseModel):
    """Document item in docflow"""
    document_id: str
    form_id: str
    name: str
    is_core: bool = False
    gfv: Optional[str] = None
    doc_number: Optional[str] = None


class DocflowResponse(BaseModel):
    """Response model for docflow"""
    id: str  # Kontur docflow ID
    ww_number: str  # Our WW-XXXXXX number
    name: Optional[str] = None
    declaration_type: int
    procedure: int
    status: int
    org_name: Optional[str] = None
    inn: Optional[str] = None
    kpp: Optional[str] = None
    gtd_number: Optional[str] = None
    process_id: Optional[str] = None
    created: Optional[str] = None
    changed: Optional[str] = None
    # Documents
    documents: List[DocflowDocumentItem] = []


@docflows_router.post("", response_model=DocflowResponse)
async def create_docflow(request: CreateDocflowRequest):
    """
    Create a new docflow (пакет декларации) in Kontur API and save to database

    Args:
        request: Docflow creation data

    Returns:
        Created docflow data with documents
    """
    try:
        log.info(f"Creating docflow: type={request.type}, procedure={request.procedure}")

        # 1. Create docflow in Kontur
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

        kontur_id = result.get("id", "")
        log.info(f"Docflow created in Kontur: {kontur_id}")

        # 2. Get documents from Kontur
        documents_data = []
        try:
            documents_raw = await client.get_docflow_documents(kontur_id)
            for doc in documents_raw:
                doc_item = {
                    "document_id": doc.get("documentId", ""),
                    "form_id": doc.get("formId", ""),
                    "name": doc.get("name", ""),
                    "is_core": doc.get("isCore", False),
                    "gfv": doc.get("gfv"),
                    "doc_number": doc.get("docNumber"),
                    "grafa44_code": doc.get("grafa44Code"),
                    "document_mode_id": doc.get("documentModeId"),
                }
                documents_data.append(doc_item)
        except Exception as e:
            log.warning(f"Failed to get documents for docflow {kontur_id}: {e}")

        # 3. Generate WW number (with type prefix) and save to database
        declaration_type_value = result.get("declarationType", request.type)
        ww_number = DocflowRepository.generate_ww_number(declaration_type_value)

        try:
            # Ensure table exists
            await DocflowRepository.ensure_table()

            # Parse timestamps
            kontur_created = None
            kontur_changed = None
            if result.get("created"):
                try:
                    from dateutil.parser import parse
                    kontur_created = parse(result.get("created"))
                except Exception:
                    pass
            if result.get("changed"):
                try:
                    from dateutil.parser import parse
                    kontur_changed = parse(result.get("changed"))
                except Exception:
                    pass

            await DocflowRepository.insert(
                kontur_id=kontur_id,
                ww_number=ww_number,
                declaration_type=result.get("declarationType", request.type),
                procedure=result.get("procedure", request.procedure),
                status=result.get("status", 0),
                name=result.get("name"),
                status_text=result.get("statusText"),
                customs_code=request.customs,
                organization_id=request.organization_id,
                organization_name=result.get("orgName"),
                inn=result.get("inn"),
                kpp=result.get("kpp"),
                employee_id=request.employee_id,
                gtd_number=result.get("gtdNumber"),
                process_id=result.get("processId"),
                documents=documents_data,
                kontur_created=kontur_created,
                kontur_changed=kontur_changed,
            )
            log.info(f"Docflow saved to database: {ww_number}")
        except Exception as e:
            log.error(f"Failed to save docflow to database: {e}")
            # Continue - we still return the Kontur data

        return DocflowResponse(
            id=kontur_id,
            ww_number=ww_number,
            name=result.get("name"),
            declaration_type=result.get("declarationType", request.type),
            procedure=result.get("procedure", request.procedure),
            status=result.get("status", 0),
            org_name=result.get("orgName"),
            inn=result.get("inn"),
            kpp=result.get("kpp"),
            gtd_number=result.get("gtdNumber"),
            process_id=result.get("processId"),
            created=result.get("created"),
            changed=result.get("changed"),
            documents=[
                DocflowDocumentItem(
                    document_id=d["document_id"],
                    form_id=d["form_id"],
                    name=d["name"],
                    is_core=d["is_core"],
                    gfv=d.get("gfv"),
                    doc_number=d.get("doc_number"),
                )
                for d in documents_data
            ],
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


class DocflowDocumentResponse(BaseModel):
    """Response model for a document in docflow"""
    document_id: str
    form_id: str
    name: str
    state: int
    is_core: bool
    gfv: Optional[str] = None


class DocflowDocumentsResponse(BaseModel):
    """Response model for list of documents in docflow"""
    documents: List[DocflowDocumentResponse]


@docflows_router.get("/{docflow_id}/documents", response_model=DocflowDocumentsResponse)
async def get_docflow_documents(docflow_id: str):
    """
    Get list of documents in a docflow

    Returns list of documents including the core declaration document
    with all IDs needed to construct Kontur UI links on frontend.

    Args:
        docflow_id: UUID of the docflow

    Returns:
        List of documents with documentId, formId, gfv for frontend link construction
    """
    try:
        log.info(f"Fetching documents for docflow: {docflow_id}")

        client = get_kontur_client()
        documents = await client.get_docflow_documents(docflow_id)

        return DocflowDocumentsResponse(
            documents=[
                DocflowDocumentResponse(
                    document_id=doc.get("documentId", ""),
                    form_id=doc.get("formId", ""),
                    name=doc.get("name", ""),
                    state=doc.get("state", 0),
                    is_core=doc.get("isCore", False),
                    gfv=doc.get("gfv")
                )
                for doc in documents
            ]
        )

    except KonturClientError as e:
        log.error(f"Kontur API error fetching docflow documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Kontur API: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error fetching docflow documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения документов: {str(e)}"
        )


@docflows_router.get("/{docflow_id}/form/{form_id}/json")
async def get_form_json(docflow_id: str, form_id: str):
    """
    Get JSON content of a document form from Kontur API

    Debug endpoint for fetching document JSON data.

    Args:
        docflow_id: UUID of the docflow
        form_id: UUID of the form

    Returns:
        JSON content of the document
    """
    try:
        log.info(f"Fetching form JSON: docflow_id={docflow_id}, form_id={form_id}")

        client = get_kontur_client()
        json_content = await client.get_form_json(docflow_id, form_id)

        return {"json": json_content}

    except KonturClientError as e:
        log.error(f"Kontur API error fetching form JSON: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Kontur API: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error fetching form JSON: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения JSON: {str(e)}"
        )


# =============================================================================
# Docflows List/Search Endpoints
# =============================================================================

class DocflowListItem(BaseModel):
    """Docflow item in list response"""
    id: str  # Our internal UUID
    kontur_id: str  # Kontur's UUID
    ww_number: str  # Our WW-XXXXXX number
    name: Optional[str] = None
    declaration_type: int
    declaration_type_code: str  # ИМ/ЭК/ТТ
    procedure: int
    status: int
    status_text: Optional[str] = None
    org_name: Optional[str] = None
    inn: Optional[str] = None
    gtd_number: Optional[str] = None
    documents_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocflowListResponse(BaseModel):
    """Response model for docflows list"""
    items: List[DocflowListItem]
    total: int
    skip: int
    take: int


class DocflowDetailResponse(BaseModel):
    """Detailed docflow response"""
    id: str  # Our internal UUID
    kontur_id: str
    ww_number: str
    name: Optional[str] = None
    declaration_type: int
    declaration_type_code: str
    procedure: int
    status: int
    status_text: Optional[str] = None
    customs_code: Optional[int] = None
    org_name: Optional[str] = None
    inn: Optional[str] = None
    kpp: Optional[str] = None
    employee_id: Optional[str] = None
    gtd_number: Optional[str] = None
    process_id: Optional[str] = None
    documents: List[DocflowDocumentItem] = []
    kontur_created: Optional[datetime] = None
    kontur_changed: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def _model_to_list_item(model: DocflowReadModel) -> DocflowListItem:
    """Convert DocflowReadModel to list item"""
    return DocflowListItem(
        id=str(model.id),
        kontur_id=model.kontur_id,
        ww_number=model.ww_number,
        name=model.name,
        declaration_type=model.declaration_type,
        declaration_type_code=model.declaration_type_code,
        procedure=model.procedure,
        status=model.status,
        status_text=model.status_text,
        org_name=model.organization_name,
        inn=model.inn,
        gtd_number=model.gtd_number,
        documents_count=len(model.documents),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _model_to_detail(model: DocflowReadModel) -> DocflowDetailResponse:
    """Convert DocflowReadModel to detail response"""
    return DocflowDetailResponse(
        id=str(model.id),
        kontur_id=model.kontur_id,
        ww_number=model.ww_number,
        name=model.name,
        declaration_type=model.declaration_type,
        declaration_type_code=model.declaration_type_code,
        procedure=model.procedure,
        status=model.status,
        status_text=model.status_text,
        customs_code=model.customs_code,
        org_name=model.organization_name,
        inn=model.inn,
        kpp=model.kpp,
        employee_id=model.employee_id,
        gtd_number=model.gtd_number,
        process_id=model.process_id,
        documents=[
            DocflowDocumentItem(
                document_id=doc.document_id,
                form_id=doc.form_id,
                name=doc.name,
                is_core=doc.is_core,
                gfv=doc.gfv,
                doc_number=doc.doc_number,
            )
            for doc in model.documents
        ],
        kontur_created=model.kontur_created,
        kontur_changed=model.kontur_changed,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@docflows_router.get("", response_model=DocflowListResponse)
async def list_docflows(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    take: int = Query(50, ge=1, le=100, description="Number of records to return"),
    declaration_type: Optional[int] = Query(None, description="Filter by declaration type (0=ИМ, 1=ЭК, etc.)"),
    status: Optional[int] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by WW number, name, or GTD number"),
):
    """
    List docflows from database with filtering and pagination

    Args:
        skip: Number of records to skip (default: 0)
        take: Number of records to return (default: 50, max: 100)
        declaration_type: Filter by declaration type
        status: Filter by status
        search: Search by WW number, name, or GTD number

    Returns:
        Paginated list of docflows
    """
    try:
        # Ensure table exists
        await DocflowRepository.ensure_table()

        items = await DocflowRepository.list_docflows(
            skip=skip,
            take=take,
            declaration_type=declaration_type,
            status=status,
            search=search,
        )

        total = await DocflowRepository.count_docflows(
            declaration_type=declaration_type,
            status=status,
        )

        return DocflowListResponse(
            items=[_model_to_list_item(item) for item in items],
            total=total,
            skip=skip,
            take=take,
        )

    except Exception as e:
        log.error(f"Error listing docflows: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка пакетов: {str(e)}"
        )


@docflows_router.get("/by-ww/{ww_number}", response_model=DocflowDetailResponse)
async def get_docflow_by_ww_number(ww_number: str):
    """
    Get docflow by WW number (e.g., WW-123456)

    Args:
        ww_number: Our internal WW number

    Returns:
        Detailed docflow data
    """
    try:
        await DocflowRepository.ensure_table()

        model = await DocflowRepository.get_by_ww_number(ww_number)
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пакет {ww_number} не найден"
            )

        return _model_to_detail(model)

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting docflow by WW number: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения пакета: {str(e)}"
        )


@docflows_router.get("/by-kontur/{kontur_id}", response_model=DocflowDetailResponse)
async def get_docflow_by_kontur_id(kontur_id: str):
    """
    Get docflow by Kontur ID

    Args:
        kontur_id: Kontur's UUID

    Returns:
        Detailed docflow data
    """
    try:
        await DocflowRepository.ensure_table()

        model = await DocflowRepository.get_by_kontur_id(kontur_id)
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пакет с Kontur ID {kontur_id} не найден"
            )

        return _model_to_detail(model)

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting docflow by Kontur ID: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения пакета: {str(e)}"
        )


@docflows_router.delete("/{kontur_id}")
async def delete_docflow(kontur_id: str):
    """
    Delete docflow from database by Kontur ID

    Note: This only deletes from our database, not from Kontur.

    Args:
        kontur_id: Kontur's UUID

    Returns:
        Success message
    """
    try:
        await DocflowRepository.ensure_table()

        deleted = await DocflowRepository.delete(kontur_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пакет с Kontur ID {kontur_id} не найден"
            )

        return {"success": True, "message": f"Пакет {kontur_id} удален из базы данных"}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error deleting docflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления пакета: {str(e)}"
        )


# =============================================================================
# DaData API - Company Search by INN
# =============================================================================

class DaDataCompanyResponse(BaseModel):
    """Company information from DaData"""
    inn: str
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    okpo: Optional[str] = None
    oktmo: Optional[str] = None
    okato: Optional[str] = None
    name_full: Optional[str] = None
    name_short: Optional[str] = None
    opf_short: Optional[str] = None
    opf_full: Optional[str] = None
    type: str = "LEGAL"
    address: Optional[str] = None
    address_data: Optional[dict] = None
    management_name: Optional[str] = None
    management_post: Optional[str] = None
    state_status: Optional[str] = None
    state_registration_date: Optional[str | int] = None  # Can be timestamp or string


class DaDataSearchResponse(BaseModel):
    """DaData search response"""
    success: bool
    data: Optional[DaDataCompanyResponse] = None
    message: Optional[str] = None


class DaDataSuggestResponse(BaseModel):
    """DaData suggestions response"""
    success: bool
    suggestions: List[DaDataCompanyResponse] = []
    message: Optional[str] = None


@router.get("/dadata/find-by-inn/{inn}", response_model=DaDataSearchResponse)
async def find_company_by_inn(inn: str):
    """
    Find company by INN using DaData API

    Args:
        inn: Company INN (10 digits for legal entities, 12 for individuals)

    Returns:
        Company information if found
    """
    try:
        client = get_dadata_client()
        result = await client.find_by_inn(inn)

        if not result:
            return DaDataSearchResponse(
                success=False,
                data=None,
                message=f"Компания с ИНН {inn} не найдена"
            )

        return DaDataSearchResponse(
            success=True,
            data=DaDataCompanyResponse(
                inn=result.inn,
                kpp=result.kpp,
                ogrn=result.ogrn,
                okpo=result.okpo,
                oktmo=result.oktmo,
                okato=result.okato,
                name_full=result.name_full,
                name_short=result.name_short,
                opf_short=result.opf_short,
                opf_full=result.opf_full,
                type=result.type,
                address=result.address,
                address_data=result.address_data,
                management_name=result.management_name,
                management_post=result.management_post,
                state_status=result.state_status,
                state_registration_date=result.state_registration_date,
            ),
            message=None
        )

    except DaDataClientError as e:
        log.error(f"DaData API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Error searching company by INN: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка поиска компании: {str(e)}"
        )


@router.get("/dadata/suggest", response_model=DaDataSuggestResponse)
async def suggest_companies(
    query: str = Query(..., min_length=2, description="Search query (company name or INN)"),
    count: int = Query(10, ge=1, le=20, description="Maximum number of suggestions")
):
    """
    Suggest companies by name or INN using DaData API (autocomplete)

    Args:
        query: Search query (company name or partial INN)
        count: Maximum number of suggestions (default 10)

    Returns:
        List of company suggestions
    """
    try:
        client = get_dadata_client()
        results = await client.suggest_company(query, count)

        return DaDataSuggestResponse(
            success=True,
            suggestions=[
                DaDataCompanyResponse(
                    inn=r.inn,
                    kpp=r.kpp,
                    ogrn=r.ogrn,
                    okpo=r.okpo,
                    oktmo=r.oktmo,
                    okato=r.okato,
                    name_full=r.name_full,
                    name_short=r.name_short,
                    opf_short=r.opf_short,
                    opf_full=r.opf_full,
                    type=r.type,
                    address=r.address,
                    address_data=r.address_data,
                    management_name=r.management_name,
                    management_post=r.management_post,
                    state_status=r.state_status,
                    state_registration_date=r.state_registration_date,
                )
                for r in results
            ],
            message=None
        )

    except DaDataClientError as e:
        log.error(f"DaData API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Error suggesting companies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка поиска компаний: {str(e)}"
        )
