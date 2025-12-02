# =============================================================================
# File: app/declarant/form_templates_routes.py
# Description: API endpoints for Form Templates (Form Builder backend)
# =============================================================================

from __future__ import annotations

import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.infra.persistence.pg_client import get_pool
from app.security.jwt_auth import get_current_user
from app.declarant.form_templates_service import FormTemplatesService

log = logging.getLogger("wellwon.declarant.form_templates_routes")

router = APIRouter(prefix="/declarant/form-templates", tags=["Declarant Form Templates"])


# =============================================================================
# Request/Response Models
# =============================================================================

class FormSectionConfigModel(BaseModel):
    """Section configuration model"""
    id: str
    key: str
    titleRu: str
    descriptionRu: Optional[str] = None
    icon: str = "FileText"
    order: int
    columns: int = Field(ge=1, le=4, default=2)
    collapsible: bool = False
    defaultExpanded: bool = True
    fields: List[Dict[str, Any]] = []
    conditionalLogic: Optional[Dict[str, Any]] = None


class CreateTemplateRequest(BaseModel):
    """Create template request"""
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    document_mode_id: str = Field(min_length=1)
    gf_code: str = Field(min_length=1)
    type_name: str = Field(min_length=1)
    sections: List[Dict[str, Any]] = []
    default_values: Optional[Dict[str, Any]] = None


class UpdateTemplateRequest(BaseModel):
    """Update template request"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    sections: Optional[List[Dict[str, Any]]] = None
    default_values: Optional[Dict[str, Any]] = None
    version_label: Optional[str] = None


class PublishTemplateRequest(BaseModel):
    """Publish template request"""
    version_label: Optional[str] = None
    change_description: Optional[str] = None


class DuplicateTemplateRequest(BaseModel):
    """Duplicate template request"""
    name: Optional[str] = None


class SaveDraftRequest(BaseModel):
    """Save draft request"""
    draft_data: Dict[str, Any]


class CreateNewDraftRequest(BaseModel):
    """Create new draft request"""
    document_mode_id: str
    draft_data: Dict[str, Any]


class TemplateResponse(BaseModel):
    """Template response"""
    id: str
    document_mode_id: str
    gf_code: str
    type_name: str
    name: str
    description: Optional[str] = None
    version: int
    version_label: Optional[str] = None
    is_draft: bool
    is_published: bool
    published_at: Optional[str] = None
    status: str
    sections: List[Dict[str, Any]]
    default_values: Dict[str, Any]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    usage_count: int
    last_used_at: Optional[str] = None


class TemplateListItemResponse(BaseModel):
    """Template list item response"""
    id: str
    name: str
    document_mode_id: str
    type_name: str
    version: int
    is_published: bool
    status: str
    updated_at: Optional[str] = None
    usage_count: int


class TemplateVersionResponse(BaseModel):
    """Template version response"""
    id: str
    template_id: str
    version: int
    version_label: Optional[str] = None
    sections_snapshot: List[Dict[str, Any]]
    default_values_snapshot: Dict[str, Any]
    change_description: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None


class PaginatedTemplatesResponse(BaseModel):
    """Paginated templates response"""
    items: List[TemplateListItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ApiResponse(BaseModel):
    """Generic API response"""
    data: Any
    message: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================

async def get_form_templates_service() -> FormTemplatesService:
    """Get FormTemplatesService instance"""
    pool = await get_pool()
    return FormTemplatesService(pool)


# =============================================================================
# Templates CRUD Endpoints
# =============================================================================

@router.get("", response_model=PaginatedTemplatesResponse)
async def get_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    document_mode_id: Optional[str] = None,
    search: Optional[str] = None,
    is_published: Optional[bool] = None,
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Get paginated list of form templates"""
    templates, total = await service.get_templates(
        page=page,
        page_size=page_size,
        document_mode_id=document_mode_id,
        search=search,
        is_published=is_published,
    )

    return PaginatedTemplatesResponse(
        items=[
            TemplateListItemResponse(
                id=t.id,
                name=t.name,
                document_mode_id=t.document_mode_id,
                type_name=t.type_name,
                version=t.version,
                is_published=t.is_published,
                status=t.status,
                updated_at=t.updated_at.isoformat() if t.updated_at else None,
                usage_count=t.usage_count,
            )
            for t in templates
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{template_id}", response_model=ApiResponse)
async def get_template(
    template_id: str,
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Get template by ID"""
    template = await service.get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return ApiResponse(data=template.to_dict())


@router.post("", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: CreateTemplateRequest,
    current_user: dict = Depends(get_current_user),
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Create new form template"""
    template = await service.create_template(
        document_mode_id=request.document_mode_id,
        gf_code=request.gf_code,
        type_name=request.type_name,
        name=request.name,
        description=request.description,
        sections=request.sections,
        default_values=request.default_values,
        user_id=current_user.get("user_id"),
    )

    return ApiResponse(data=template.to_dict(), message="Template created successfully")


@router.put("/{template_id}", response_model=ApiResponse)
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    current_user: dict = Depends(get_current_user),
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Update form template"""
    template = await service.update_template(
        template_id=template_id,
        name=request.name,
        description=request.description,
        sections=request.sections,
        default_values=request.default_values,
        user_id=current_user.get("user_id"),
    )

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return ApiResponse(data=template.to_dict(), message="Template updated successfully")


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Delete form template"""
    deleted = await service.delete_template(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")


@router.post("/{template_id}/duplicate", response_model=ApiResponse)
async def duplicate_template(
    template_id: str,
    request: DuplicateTemplateRequest,
    current_user: dict = Depends(get_current_user),
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Duplicate form template"""
    template = await service.duplicate_template(
        template_id=template_id,
        new_name=request.name,
        user_id=current_user.get("user_id"),
    )

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return ApiResponse(data=template.to_dict(), message="Template duplicated successfully")


# =============================================================================
# Publishing Endpoints
# =============================================================================

@router.post("/{template_id}/publish", response_model=ApiResponse)
async def publish_template(
    template_id: str,
    request: PublishTemplateRequest,
    current_user: dict = Depends(get_current_user),
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Publish form template (creates new version)"""
    template = await service.publish_template(
        template_id=template_id,
        version_label=request.version_label,
        change_description=request.change_description,
        user_id=current_user.get("user_id"),
    )

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return ApiResponse(data=template.to_dict(), message="Template published successfully")


@router.post("/{template_id}/unpublish", response_model=ApiResponse)
async def unpublish_template(
    template_id: str,
    current_user: dict = Depends(get_current_user),
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Unpublish form template"""
    template = await service.unpublish_template(
        template_id=template_id,
        user_id=current_user.get("user_id"),
    )

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return ApiResponse(data=template.to_dict(), message="Template unpublished successfully")


# =============================================================================
# Versions Endpoints
# =============================================================================

@router.get("/{template_id}/versions", response_model=ApiResponse)
async def get_template_versions(
    template_id: str,
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Get all versions of template"""
    versions = await service.get_template_versions(template_id)
    return ApiResponse(data=[v.to_dict() for v in versions])


@router.get("/{template_id}/versions/{version}", response_model=ApiResponse)
async def get_template_version(
    template_id: str,
    version: int,
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Get specific version of template"""
    version_data = await service.get_template_version(template_id, version)
    if not version_data:
        raise HTTPException(status_code=404, detail="Version not found")

    return ApiResponse(data=version_data.to_dict())


@router.post("/{template_id}/versions/{version}/restore", response_model=ApiResponse)
async def restore_template_version(
    template_id: str,
    version: int,
    current_user: dict = Depends(get_current_user),
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Restore template to specific version"""
    template = await service.restore_template_version(
        template_id=template_id,
        version=version,
        user_id=current_user.get("user_id"),
    )

    if not template:
        raise HTTPException(status_code=404, detail="Version not found")

    return ApiResponse(data=template.to_dict(), message=f"Restored to version {version}")


# =============================================================================
# Drafts Endpoints
# =============================================================================

@router.get("/{template_id}/draft", response_model=ApiResponse)
async def get_template_draft(
    template_id: str,
    current_user: dict = Depends(get_current_user),
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Get user's draft for template"""
    draft = await service.get_user_draft(template_id, current_user.get("user_id"))
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    return ApiResponse(data=draft)


@router.put("/{template_id}/draft", response_model=ApiResponse)
async def save_template_draft(
    template_id: str,
    request: SaveDraftRequest,
    current_user: dict = Depends(get_current_user),
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Save user's draft for template"""
    draft = await service.save_user_draft(
        template_id=template_id,
        user_id=current_user.get("user_id"),
        draft_data=request.draft_data,
    )

    return ApiResponse(data=draft, message="Draft saved")


@router.delete("/{template_id}/draft", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template_draft(
    template_id: str,
    current_user: dict = Depends(get_current_user),
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Delete user's draft for template"""
    await service.delete_user_draft(template_id, current_user.get("user_id"))


@router.get("/drafts", response_model=ApiResponse)
async def get_user_drafts(
    current_user: dict = Depends(get_current_user),
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Get all user's drafts"""
    drafts = await service.get_all_user_drafts(current_user.get("user_id"))
    return ApiResponse(data=drafts)


@router.post("/drafts", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
async def create_new_draft(
    request: CreateNewDraftRequest,
    current_user: dict = Depends(get_current_user),
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Create new draft (without existing template)"""
    # For new templates, we create a template first then save draft
    # This is a simplified version - in production might want separate logic
    raise HTTPException(
        status_code=501,
        detail="Create new draft without template not implemented yet"
    )


# =============================================================================
# Export/Import Endpoints
# =============================================================================

@router.get("/{template_id}/export")
async def export_template(
    template_id: str,
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Export template as JSON file"""
    template = await service.get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    export_data = {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "template": template.to_dict(),
    }

    json_content = json.dumps(export_data, ensure_ascii=False, indent=2)
    filename = f"{template.name.replace(' ', '_')}_template.json"

    return StreamingResponse(
        iter([json_content]),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.post("/import", response_model=ApiResponse)
async def import_template(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    service: FormTemplatesService = Depends(get_form_templates_service),
):
    """Import template from JSON file"""
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be JSON")

    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    # Validate structure
    if "template" not in data:
        raise HTTPException(status_code=400, detail="Invalid template format")

    template_data = data["template"]

    # Create new template from import
    template = await service.create_template(
        document_mode_id=template_data.get("document_mode_id", ""),
        gf_code=template_data.get("gf_code", ""),
        type_name=template_data.get("type_name", ""),
        name=f"{template_data.get('name', 'Imported')} (импорт)",
        description=template_data.get("description"),
        sections=template_data.get("sections", []),
        default_values=template_data.get("default_values", {}),
        user_id=current_user.get("user_id"),
    )

    return ApiResponse(data=template.to_dict(), message="Template imported successfully")


@router.post("/import/validate", response_model=ApiResponse)
async def validate_import(
    file: UploadFile = File(...),
):
    """Validate JSON file before import"""
    if not file.filename.endswith(".json"):
        return ApiResponse(
            data={"valid": False, "errors": ["File must be JSON"]}
        )

    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        return ApiResponse(
            data={"valid": False, "errors": [f"Invalid JSON: {str(e)}"]}
        )

    errors = []

    # Validate structure
    if "template" not in data:
        errors.append("Missing 'template' key in JSON")
    else:
        template_data = data["template"]

        required_fields = ["document_mode_id", "gf_code", "type_name", "name"]
        for field in required_fields:
            if not template_data.get(field):
                errors.append(f"Missing required field: {field}")

        if not isinstance(template_data.get("sections"), list):
            errors.append("'sections' must be an array")

    if errors:
        return ApiResponse(data={"valid": False, "errors": errors})

    return ApiResponse(
        data={
            "valid": True,
            "preview": {
                "name": data["template"].get("name"),
                "document_mode_id": data["template"].get("document_mode_id"),
                "sections_count": len(data["template"].get("sections", [])),
            },
        }
    )
