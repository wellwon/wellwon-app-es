# =============================================================================
# File: app/declarant/form_routes.py
# Description: API endpoints for Universal Form Generator
# =============================================================================

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.declarant.form_definitions_service import FormDefinitionsService, SyncResult
from app.declarant.kontur_client import KonturClientError

log = logging.getLogger("wellwon.declarant.form_routes")

router = APIRouter(prefix="/declarant/form-definitions", tags=["Form Definitions"])


# =============================================================================
# Response Models
# =============================================================================

class FieldOptionResponse(BaseModel):
    """Option for select fields"""
    value: str
    label: str


class FieldDefinitionResponse(BaseModel):
    """Field definition for form rendering"""
    path: str
    name: str
    field_type: str
    required: bool
    label_ru: str
    hint_ru: str = ""
    placeholder_ru: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    max_length: Optional[int] = None
    options: List[FieldOptionResponse] = []
    pattern: Optional[str] = None
    children: List['FieldDefinitionResponse'] = []

    class Config:
        from_attributes = True


class FormSectionResponse(BaseModel):
    """Section for UI grouping"""
    section_key: str
    title_ru: str
    description_ru: str = ""
    icon: str = "FileText"
    sort_order: int = 0
    field_paths: List[str] = []
    fields_config: List[Dict[str, Any]] = []  # Full field configurations from Form Builder
    columns: int = 2
    collapsible: bool = False
    default_expanded: bool = True


class FormDefinitionResponse(BaseModel):
    """Complete form definition for rendering"""
    id: str
    document_mode_id: str
    gf_code: str
    type_name: str
    fields: List[Dict[str, Any]]  # Nested structure as dict
    sections: List[FormSectionResponse]
    default_values: Dict[str, Any]
    version: int
    form_width: int = 100  # Ширина формы в % (70-130)


class FormDefinitionListItem(BaseModel):
    """Form definition item for list view"""
    id: str
    document_mode_id: str
    gf_code: str
    type_name: str
    fields_count: int
    version: int


class FormDefinitionsListResponse(BaseModel):
    """List of form definitions"""
    items: List[FormDefinitionListItem]
    total: int


class SyncResultResponse(BaseModel):
    """Sync operation result"""
    success: bool
    total_processed: int
    forms_created: int
    forms_updated: int
    schemas_changed: int
    errors: int
    error_details: List[Dict[str, str]] = []
    sync_duration_ms: int
    message: str


class SelectOptionRequest(BaseModel):
    """Select option for dropdown fields"""
    label: str
    value: str


class FormFieldConfigRequest(BaseModel):
    """Field configuration from Form Builder"""
    id: str
    schemaPath: str
    elementType: Optional[str] = None  # Тип элемента формы: subheading, section-divider
    fieldType: Optional[str] = None    # Тип поля: text, number, date, datetime, select, checkbox, textarea
    customLabel: Optional[str] = None
    customPlaceholder: Optional[str] = None
    customHint: Optional[str] = None
    prompt: Optional[str] = None
    width: str = "half"
    order: int = 0
    readonly: Optional[bool] = None
    defaultValue: Optional[Any] = None
    required: Optional[bool] = None
    isSelect: Optional[bool] = None  # Флаг: рендерить как select (deprecated, use fieldType)
    selectOptions: Optional[List[SelectOptionRequest]] = None  # Опции для select


class FormSectionConfigRequest(BaseModel):
    """Section configuration from Form Builder"""
    id: str
    key: str
    titleRu: str
    descriptionRu: Optional[str] = None
    icon: str = "FileText"
    order: int = 0
    columns: int = 2
    collapsible: bool = False
    defaultExpanded: bool = True
    fields: List[FormFieldConfigRequest] = []


class UpdateSectionsRequest(BaseModel):
    """Request to update form sections"""
    sections: List[FormSectionConfigRequest]


class UpdateSectionsResponse(BaseModel):
    """Response after updating sections"""
    success: bool
    message: str
    sections_count: int


# =============================================================================
# Helper Functions
# =============================================================================

def _count_fields(fields: List) -> int:
    """Count total fields including nested"""
    count = 0
    for f in fields:
        count += 1
        if hasattr(f, 'children') and f.children:
            count += _count_fields(f.children)
        elif isinstance(f, dict) and 'children' in f:
            count += _count_fields(f['children'])
    return count


def _field_to_dict(field) -> Dict[str, Any]:
    """Convert FieldDefinition to dict"""
    result = {
        "path": field.path,
        "name": field.name,
        "field_type": field.field_type.value if hasattr(field.field_type, 'value') else field.field_type,
        "required": field.required,
        "label_ru": field.label_ru,
        "hint_ru": field.hint_ru,
        "placeholder_ru": field.placeholder_ru,
    }

    if field.min_value is not None:
        result["min_value"] = field.min_value
    if field.max_value is not None:
        result["max_value"] = field.max_value
    if field.max_length is not None:
        result["max_length"] = field.max_length
    if field.pattern:
        result["pattern"] = field.pattern
    if field.options:
        result["options"] = [{"value": o.value, "label": o.label} for o in field.options]
    if field.children:
        result["children"] = [_field_to_dict(c) for c in field.children]

    return result


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/", response_model=FormDefinitionsListResponse)
async def list_form_definitions():
    """
    Get list of all form definitions

    Returns overview list for navigation/selection.
    """
    try:
        definitions = await FormDefinitionsService.get_all()

        items = [
            FormDefinitionListItem(
                id=d.id or "",
                document_mode_id=d.document_mode_id,
                gf_code=d.gf_code,
                type_name=d.type_name,
                fields_count=_count_fields(d.fields),
                version=d.version
            )
            for d in definitions
        ]

        return FormDefinitionsListResponse(
            items=items,
            total=len(items)
        )

    except Exception as e:
        log.error(f"Error listing form definitions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing form definitions: {str(e)}"
        )


@router.get("/{document_mode_id}", response_model=FormDefinitionResponse)
async def get_form_definition(document_mode_id: str):
    """
    Get form definition for rendering

    Returns complete form definition with:
    - Field definitions (types, labels, validation)
    - Sections for UI grouping
    - Default values
    """
    try:
        form_def = await FormDefinitionsService.get_by_document_mode_id(document_mode_id)

        if not form_def:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Form definition not found for {document_mode_id}. Run sync first."
            )

        # Convert sections
        sections = [
            FormSectionResponse(
                section_key=s.section_key,
                title_ru=s.title_ru,
                description_ru=s.description_ru,
                icon=s.icon,
                sort_order=s.sort_order,
                field_paths=s.field_paths,
                fields_config=s.fields_config,
                columns=s.columns,
                collapsible=s.collapsible,
                default_expanded=s.default_expanded
            )
            for s in form_def.sections
        ]

        # Convert fields to dicts
        fields_dict = [_field_to_dict(f) for f in form_def.fields]

        return FormDefinitionResponse(
            id=form_def.id or "",
            document_mode_id=form_def.document_mode_id,
            gf_code=form_def.gf_code,
            type_name=form_def.type_name,
            fields=fields_dict,
            sections=sections,
            default_values=form_def.default_values,
            version=form_def.version,
            form_width=form_def.form_width
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting form definition for {document_mode_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting form definition: {str(e)}"
        )


@router.post("/sync", response_model=SyncResultResponse)
async def sync_all_form_definitions():
    """
    Sync all form definitions from Kontur API

    Fetches all JSON templates and transforms them into form definitions.
    Smart merge: preserves customizations when schema changes.
    """
    try:
        log.info("Starting full form definitions sync from Kontur API")

        result: SyncResult = await FormDefinitionsService.sync_from_api()

        message = f"Синхронизировано {result.total_processed} форм"
        if result.forms_created > 0:
            message += f" (создано: {result.forms_created})"
        if result.forms_updated > 0:
            message += f" (обновлено: {result.forms_updated})"
        if result.schemas_changed > 0:
            message += f" (схем изменено: {result.schemas_changed})"
        if result.errors > 0:
            message += f" (ошибок: {result.errors})"

        return SyncResultResponse(
            success=result.errors == 0,
            total_processed=result.total_processed,
            forms_created=result.forms_created,
            forms_updated=result.forms_updated,
            schemas_changed=result.schemas_changed,
            errors=result.errors,
            error_details=result.error_details,
            sync_duration_ms=result.sync_duration_ms,
            message=message
        )

    except KonturClientError as e:
        log.error(f"Kontur API error during sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Kontur API: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error syncing form definitions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка синхронизации: {str(e)}"
        )


@router.post("/{document_mode_id}/sync", response_model=SyncResultResponse)
async def sync_single_form_definition(document_mode_id: str):
    """
    Sync a single form definition from Kontur API

    Fetches schema for specific document_mode_id and updates form definition.
    """
    try:
        log.info(f"Starting sync for form definition {document_mode_id}")

        result: SyncResult = await FormDefinitionsService.sync_from_api(document_mode_id)

        message = f"Синхронизирована форма {document_mode_id}"
        if result.forms_created > 0:
            message = f"Создана форма {document_mode_id}"
        elif result.schemas_changed > 0:
            message = f"Обновлена форма {document_mode_id} (схема изменилась)"
        elif result.errors > 0:
            message = f"Ошибка синхронизации {document_mode_id}"

        return SyncResultResponse(
            success=result.errors == 0,
            total_processed=result.total_processed,
            forms_created=result.forms_created,
            forms_updated=result.forms_updated,
            schemas_changed=result.schemas_changed,
            errors=result.errors,
            error_details=result.error_details,
            sync_duration_ms=result.sync_duration_ms,
            message=message
        )

    except KonturClientError as e:
        log.error(f"Kontur API error syncing {document_mode_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Kontur API: {str(e)}"
        )
    except Exception as e:
        log.error(f"Error syncing form definition {document_mode_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка синхронизации: {str(e)}"
        )


@router.get("/{document_mode_id}/schema")
async def get_raw_schema(document_mode_id: str):
    """
    Get raw Kontur schema for a form definition

    Returns the original JSON schema from Kontur API (stored in database).
    Useful for debugging and schema inspection.
    """
    try:
        form_def = await FormDefinitionsService.get_by_document_mode_id(document_mode_id)

        if not form_def:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Form definition not found for {document_mode_id}. Run sync first."
            )

        return {
            "document_mode_id": document_mode_id,
            "schema_hash": form_def.kontur_schema_hash,
            "schema": form_def.kontur_schema_json
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting raw schema for {document_mode_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting schema: {str(e)}"
        )


@router.put("/{document_mode_id}/sections", response_model=UpdateSectionsResponse)
async def update_form_sections(
    document_mode_id: str,
    request: UpdateSectionsRequest
):
    """
    Update sections for a form definition

    Called from Form Builder to save section configuration.
    Converts FormSectionConfigRequest to database format and saves.
    """
    try:
        log.info(f"Updating sections for {document_mode_id}: {len(request.sections)} sections")

        # Check if form definition exists
        form_def = await FormDefinitionsService.get_by_document_mode_id(document_mode_id)
        if not form_def:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Form definition not found for {document_mode_id}"
            )

        # Update sections in database
        await FormDefinitionsService.update_sections(document_mode_id, request.sections)

        return UpdateSectionsResponse(
            success=True,
            message=f"Сохранено {len(request.sections)} секций",
            sections_count=len(request.sections)
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error updating sections for {document_mode_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сохранения секций: {str(e)}"
        )


class UpdateFormWidthRequest(BaseModel):
    """Request to update form width"""
    form_width: int


class UpdateFormWidthResponse(BaseModel):
    """Response after updating form width"""
    success: bool
    message: str
    form_width: int


@router.put("/{document_mode_id}/width", response_model=UpdateFormWidthResponse)
async def update_form_width(
    document_mode_id: str,
    request: UpdateFormWidthRequest
):
    """
    Update form width for a form definition

    Called from Form Builder to save form width setting.
    """
    try:
        log.info(f"Updating form width for {document_mode_id}: {request.form_width}%")

        # Check if form definition exists
        form_def = await FormDefinitionsService.get_by_document_mode_id(document_mode_id)
        if not form_def:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Form definition not found for {document_mode_id}"
            )

        # Update form width in database
        await FormDefinitionsService.update_form_width(document_mode_id, request.form_width)

        # Clamp to valid range for response
        clamped_width = max(70, min(130, request.form_width))

        return UpdateFormWidthResponse(
            success=True,
            message=f"Ширина формы обновлена до {clamped_width}%",
            form_width=clamped_width
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error updating form width for {document_mode_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления ширины формы: {str(e)}"
        )


# =============================================================================
# Version Management Endpoints
# =============================================================================

class CreateVersionRequest(BaseModel):
    """Request to create a new version"""
    version_label: Optional[str] = None
    change_description: Optional[str] = None


class VersionResponse(BaseModel):
    """Version data response"""
    id: str
    version_number: int
    version_label: Optional[str] = None
    change_description: Optional[str] = None
    fields_count: int
    sections_count: int
    created_at: Optional[str] = None
    is_current: bool


class VersionListResponse(BaseModel):
    """List of versions"""
    items: List[VersionResponse]
    total: int


class RestoreVersionResponse(BaseModel):
    """Response after restoring version"""
    success: bool
    message: str
    version_number: int


@router.get("/{document_mode_id}/versions", response_model=VersionListResponse)
async def get_form_versions(document_mode_id: str):
    """
    Get all versions for a form definition

    Returns list of saved versions with metadata.
    """
    try:
        versions = await FormDefinitionsService.get_versions(document_mode_id)

        return VersionListResponse(
            items=[VersionResponse(**v) for v in versions],
            total=len(versions)
        )

    except Exception as e:
        log.error(f"Error getting versions for {document_mode_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения версий: {str(e)}"
        )


@router.post("/{document_mode_id}/versions", response_model=VersionResponse)
async def create_form_version(
    document_mode_id: str,
    request: CreateVersionRequest
):
    """
    Create a new version snapshot

    Saves current sections configuration as a new version.
    """
    try:
        log.info(f"Creating version for {document_mode_id}")

        # Check if form definition exists
        form_def = await FormDefinitionsService.get_by_document_mode_id(document_mode_id)
        if not form_def:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Form definition not found for {document_mode_id}"
            )

        version = await FormDefinitionsService.create_version(
            document_mode_id,
            version_label=request.version_label,
            change_description=request.change_description
        )

        return VersionResponse(**version)

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error creating version for {document_mode_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания версии: {str(e)}"
        )


@router.get("/{document_mode_id}/versions/{version_number}")
async def get_form_version(document_mode_id: str, version_number: int):
    """
    Get a specific version with full sections data

    Returns version with sections_snapshot for preview or restore.
    """
    try:
        version = await FormDefinitionsService.get_version(document_mode_id, version_number)

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_number} not found"
            )

        return version

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting version {version_number} for {document_mode_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения версии: {str(e)}"
        )


@router.post("/{document_mode_id}/versions/{version_number}/restore", response_model=RestoreVersionResponse)
async def restore_form_version(document_mode_id: str, version_number: int):
    """
    Restore sections from a specific version

    Replaces current sections with the saved snapshot.
    """
    try:
        log.info(f"Restoring version {version_number} for {document_mode_id}")

        success = await FormDefinitionsService.restore_version(document_mode_id, version_number)

        return RestoreVersionResponse(
            success=success,
            message=f"Восстановлена версия {version_number}",
            version_number=version_number
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Error restoring version {version_number} for {document_mode_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка восстановления версии: {str(e)}"
        )


@router.delete("/{document_mode_id}/versions/{version_number}")
async def delete_form_version(document_mode_id: str, version_number: int):
    """
    Delete a specific version

    Cannot delete the current (active) version.
    """
    try:
        success = await FormDefinitionsService.delete_version(document_mode_id, version_number)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_number} not found"
            )

        return {"success": True, "message": f"Версия {version_number} удалена"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error deleting version {version_number} for {document_mode_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления версии: {str(e)}"
        )
