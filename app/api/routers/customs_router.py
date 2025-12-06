# =============================================================================
# File: app/api/routers/customs_router.py
# Description: Customs domain API endpoints
# =============================================================================

from __future__ import annotations

import base64
from uuid import UUID
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, UploadFile, File
from fastapi.responses import Response

from app.config.logging_config import get_logger
from app.security.jwt_auth import get_current_user
from app.utils.uuid_utils import generate_uuid

# API Models
from app.api.models.customs_api_models import (
    # Requests
    CreateDeclarationRequest,
    UpdateDeclarationRequest,
    CopyDeclarationRequest,
    DeleteDeclarationRequest,
    UpdateFormDataRequest,
    ImportGoodsRequest,
    AttachDocumentRequest,
    CreateDtsRequest,
    SetOrganizationRequest,
    SetEmployeeRequest,
    ExportRequest,
    # Responses
    DeclarationResponse,
    OperationResponse,
    DeclarationDetailResponse,
    DeclarationSummaryResponse,
    DeclarationListResponse,
    DocumentResponse,
    OrganizationResponse,
    OrganizationSummaryResponse,
    KonturOrganizationOption,
    KonturEmployeeOption,
    KonturCustomsOption,
    KonturProcedureOption,
    KonturDeclarationTypeOption,
    ExportPdfResponse,
    ExportXmlResponse,
    DeclarationStatusResponse,
    SubmitResponse,
    RefreshStatusResponse,
)

# Commands
from app.customs.declaration.commands import (
    CreateCustomsDeclarationCommand,
    DeleteCustomsDeclarationCommand,
    CopyCustomsDeclarationCommand,
    UpdateFormDataCommand,
    ImportGoodsCommand,
    AttachDocumentCommand,
    RemoveDocumentCommand,
    CreateDtsCommand,
    SubmitToKonturCommand,
    RefreshStatusFromKonturCommand,
    SetOrganizationCommand,
    SetEmployeeCommand,
    ExportDeclarationPdfCommand,
    ExportDeclarationXmlCommand,
    ImportDeclarationXmlCommand,
)

# Queries
from app.customs.queries import (
    GetDeclarationQuery,
    GetDeclarationSummaryQuery,
    ListDeclarationsQuery,
    SearchDeclarationsQuery,
    GetOrganizationQuery,
    ListOrganizationsQuery,
    SearchOrganizationsQuery,
    GetKonturOrganizationsQuery,
    GetKonturEmployeesQuery,
    GetKonturDeclarationTypesQuery,
    GetCustomsProceduresQuery,
    GetCustomsOfficesQuery,
    DeclarationDetail,
    DeclarationSummary,
)

from app.customs.enums import DeclarationType, DocflowStatus
from app.customs.exceptions import KonturServiceUnavailableError

log = get_logger("wellwon.api.customs")

router = APIRouter(prefix="/customs", tags=["customs"])


# =============================================================================
# Dependency Injection
# =============================================================================

async def get_command_bus(request: Request):
    """Get command bus from application state"""
    if not hasattr(request.app.state, 'command_bus'):
        raise RuntimeError("Command bus not configured")
    return request.app.state.command_bus


async def get_query_bus(request: Request):
    """Get query bus from application state"""
    if not hasattr(request.app.state, 'query_bus'):
        raise RuntimeError("Query bus not configured")
    return request.app.state.query_bus


# =============================================================================
# Declaration Lifecycle Endpoints
# =============================================================================

@router.post("/declarations", response_model=DeclarationResponse, status_code=status.HTTP_201_CREATED)
async def create_declaration(
    request: CreateDeclarationRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
):
    """Create a new customs declaration."""
    try:
        declaration_id = generate_uuid()
        command = CreateCustomsDeclarationCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
            company_id=request.company_id,
            name=request.name,
            declaration_type=request.declaration_type,
            procedure=request.procedure,
            customs_code=request.customs_code,
            organization_id=request.organization_id,
            employee_id=request.employee_id,
        )

        result_id = await command_bus.send(command)
        log.info(f"Declaration created: {result_id} by user {current_user['user_id']}")
        return DeclarationResponse(id=result_id, message="Declaration created")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        log.error(f"Failed to create declaration: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create declaration")


@router.get("/declarations", response_model=DeclarationListResponse)
async def list_declarations(
    current_user: Annotated[dict, Depends(get_current_user)],
    query_bus=Depends(get_query_bus),
    company_id: Optional[UUID] = Query(None),
    status_filter: Optional[int] = Query(None, alias="status"),
    declaration_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List declarations for current user with optional filters."""
    query = ListDeclarationsQuery(
        user_id=current_user["user_id"],
        company_id=company_id,
        status=DocflowStatus(status_filter) if status_filter is not None else None,
        declaration_type=DeclarationType(declaration_type) if declaration_type else None,
        limit=limit,
        offset=offset,
    )

    results = await query_bus.query(query)

    declarations = []
    for r in results:
        declarations.append(DeclarationSummaryResponse(
            id=r.id,
            name=r.name,
            declaration_type=r.declaration_type,
            procedure=r.procedure,
            customs_code=r.customs_code,
            status=r.status,
            status_name=DocflowStatus(r.status).name if isinstance(r.status, int) else r.status.name,
            gtd_number=r.gtd_number,
            organization_id=r.organization_id,
            goods_count=getattr(r, 'goods_count', 0),
            created_at=r.created_at,
            submitted_at=r.submitted_at,
            is_deleted=r.is_deleted,
        ))

    return DeclarationListResponse(
        declarations=declarations,
        total=len(declarations),  # TODO: Add total count query
        limit=limit,
        offset=offset,
    )


@router.get("/declarations/search", response_model=List[DeclarationSummaryResponse])
async def search_declarations(
    current_user: Annotated[dict, Depends(get_current_user)],
    query_bus=Depends(get_query_bus),
    q: str = Query(..., min_length=1, max_length=100),
    company_id: Optional[UUID] = Query(None),
    limit: int = Query(20, ge=1, le=50),
):
    """Search declarations by name or GTD number."""
    query = SearchDeclarationsQuery(
        user_id=current_user["user_id"],
        search_term=q,
        company_id=company_id,
        limit=limit,
    )

    results = await query_bus.query(query)

    return [
        DeclarationSummaryResponse(
            id=r.id,
            name=r.name,
            declaration_type=r.declaration_type,
            procedure=r.procedure,
            customs_code=r.customs_code,
            status=r.status,
            status_name=DocflowStatus(r.status).name if isinstance(r.status, int) else r.status.name,
            gtd_number=r.gtd_number,
            organization_id=r.organization_id,
            created_at=r.created_at,
            submitted_at=r.submitted_at,
            is_deleted=r.is_deleted,
        )
        for r in results
    ]


@router.get("/declarations/{declaration_id}", response_model=DeclarationDetailResponse)
async def get_declaration(
    declaration_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    query_bus=Depends(get_query_bus),
):
    """Get declaration details."""
    query = GetDeclarationQuery(
        declaration_id=declaration_id,
        user_id=current_user["user_id"],
    )

    result = await query_bus.query(query)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Declaration not found")

    return DeclarationDetailResponse(
        id=result.id,
        user_id=result.user_id,
        company_id=result.company_id,
        kontur_docflow_id=result.kontur_docflow_id,
        gtd_number=result.gtd_number,
        name=result.name,
        declaration_type=result.declaration_type,
        procedure=result.procedure,
        customs_code=result.customs_code,
        status=result.status,
        status_name=DocflowStatus(result.status).name if isinstance(result.status, int) else result.status.name,
        organization_id=result.organization_id,
        employee_id=result.employee_id,
        declarant_inn=result.declarant_inn,
        form_data=result.form_data,
        documents=[DocumentResponse(**d) for d in result.documents],
        goods_count=len(result.goods) if hasattr(result, 'goods') else 0,
        created_at=result.created_at,
        updated_at=result.updated_at,
        submitted_at=result.submitted_at,
        is_deleted=result.is_deleted,
    )


@router.post("/declarations/{declaration_id}/copy", response_model=DeclarationResponse)
async def copy_declaration(
    declaration_id: UUID,
    request: CopyDeclarationRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
):
    """Copy an existing declaration as a template."""
    try:
        new_id = generate_uuid()
        command = CopyCustomsDeclarationCommand(
            source_declaration_id=declaration_id,
            new_declaration_id=new_id,
            user_id=current_user["user_id"],
            new_name=request.new_name,
            copy_documents=request.copy_documents,
            copy_form_data=request.copy_form_data,
        )

        result_id = await command_bus.send(command)
        return DeclarationResponse(id=result_id, message="Declaration copied")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/declarations/{declaration_id}", response_model=DeclarationResponse)
async def delete_declaration(
    declaration_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    reason: Optional[str] = Query(None, max_length=500),
):
    """Delete a customs declaration."""
    try:
        command = DeleteCustomsDeclarationCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
            reason=reason,
        )

        await command_bus.send(command)
        return DeclarationResponse(id=declaration_id, message="Declaration deleted")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# Form Data Endpoints
# =============================================================================

@router.patch("/declarations/{declaration_id}/form", response_model=OperationResponse)
async def update_form_data(
    declaration_id: UUID,
    request: UpdateFormDataRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
):
    """Update declaration form data."""
    try:
        command = UpdateFormDataCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
            form_data=request.form_data,
        )

        await command_bus.send(command)
        return OperationResponse(success=True, message="Form data updated")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/declarations/{declaration_id}/goods", response_model=OperationResponse)
async def import_goods(
    declaration_id: UUID,
    request: ImportGoodsRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
):
    """Import goods into declaration."""
    try:
        command = ImportGoodsCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
            goods=request.goods,
            import_source=request.import_source,
            replace_existing=request.replace_existing,
        )

        await command_bus.send(command)
        return OperationResponse(success=True, message=f"Imported {len(request.goods)} goods")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# Document Endpoints
# =============================================================================

@router.post("/declarations/{declaration_id}/documents", response_model=OperationResponse)
async def attach_document(
    declaration_id: UUID,
    request: AttachDocumentRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
):
    """Attach a document to declaration."""
    try:
        command = AttachDocumentCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
            name=request.name,
            number=request.number,
            date=request.date,
            grafa44_code=request.grafa44_code,
            form_id=request.form_id,
            belongs_to_all_goods=request.belongs_to_all_goods,
            file_id=request.file_id,
        )

        await command_bus.send(command)
        return OperationResponse(success=True, message="Document attached")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/declarations/{declaration_id}/documents/{document_id}", response_model=OperationResponse)
async def remove_document(
    declaration_id: UUID,
    document_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
):
    """Remove a document from declaration."""
    try:
        command = RemoveDocumentCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
            document_id=document_id,
        )

        await command_bus.send(command)
        return OperationResponse(success=True, message="Document removed")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/declarations/{declaration_id}/dts", response_model=OperationResponse)
async def create_dts(
    declaration_id: UUID,
    request: CreateDtsRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
):
    """Create DTS (customs value declaration) document."""
    try:
        command = CreateDtsCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
            dts_type=request.dts_type,
            distribution_items=[item.model_dump() for item in request.distribution_items],
        )

        await command_bus.send(command)
        return OperationResponse(success=True, message="DTS created")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# Organization Endpoints
# =============================================================================

@router.post("/declarations/{declaration_id}/organization", response_model=OperationResponse)
async def set_organization(
    declaration_id: UUID,
    request: SetOrganizationRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
):
    """Set organization on declaration form."""
    try:
        command = SetOrganizationCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
            organization_id=request.organization_id,
            grafa=request.grafa,
        )

        await command_bus.send(command)
        return OperationResponse(success=True, message="Organization set")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/declarations/{declaration_id}/employee", response_model=OperationResponse)
async def set_employee(
    declaration_id: UUID,
    request: SetEmployeeRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
):
    """Set employee (declarant) on declaration."""
    try:
        command = SetEmployeeCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
            employee_id=request.employee_id,
        )

        await command_bus.send(command)
        return OperationResponse(success=True, message="Employee set")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# Kontur Submission Endpoints
# =============================================================================

@router.post("/declarations/{declaration_id}/submit", response_model=SubmitResponse)
async def submit_to_kontur(
    declaration_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
):
    """Submit declaration to Kontur."""
    try:
        command = SubmitToKonturCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
        )

        result_id = await command_bus.send(command)
        log.info(f"Declaration {declaration_id} submitted to Kontur")

        return SubmitResponse(
            success=True,
            declaration_id=declaration_id,
            message="Declaration submitted to Kontur"
        )

    except ValueError as e:
        return SubmitResponse(success=False, declaration_id=declaration_id, error=str(e))
    except Exception as e:
        log.error(f"Failed to submit to Kontur: {e}", exc_info=True)
        return SubmitResponse(success=False, declaration_id=declaration_id, error="Submission failed")


@router.post("/declarations/{declaration_id}/refresh-status", response_model=RefreshStatusResponse)
async def refresh_status(
    declaration_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Refresh declaration status from Kontur."""
    try:
        # Get current status
        query = GetDeclarationQuery(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
        )
        current = await query_bus.query(query)
        if not current:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Declaration not found")

        old_status = current.status

        # Refresh from Kontur
        command = RefreshStatusFromKonturCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
        )
        await command_bus.send(command)

        # Get new status
        result = await query_bus.query(query)

        return RefreshStatusResponse(
            success=True,
            declaration_id=declaration_id,
            old_status=old_status,
            new_status=result.status,
            status_name=DocflowStatus(result.status).name if isinstance(result.status, int) else result.status.name,
            gtd_number=result.gtd_number,
            message="Status refreshed"
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/declarations/{declaration_id}/status", response_model=DeclarationStatusResponse)
async def get_declaration_status(
    declaration_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    query_bus=Depends(get_query_bus),
):
    """Get current declaration status."""
    query = GetDeclarationSummaryQuery(
        declaration_id=declaration_id,
        user_id=current_user["user_id"],
    )

    result = await query_bus.query(query)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Declaration not found")

    return DeclarationStatusResponse(
        id=result.id,
        name=result.name,
        status=result.status,
        status_name=DocflowStatus(result.status).name if isinstance(result.status, int) else result.status.name,
        kontur_docflow_id=getattr(result, 'kontur_docflow_id', None),
        gtd_number=result.gtd_number,
        submitted_at=result.submitted_at,
        updated_at=getattr(result, 'updated_at', None),
    )


# =============================================================================
# Export Endpoints
# =============================================================================

@router.get("/declarations/{declaration_id}/export/pdf")
async def export_pdf(
    declaration_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    form_id: str = Query(default="dt"),
):
    """Export declaration as PDF."""
    try:
        command = ExportDeclarationPdfCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
            form_id=form_id,
        )

        pdf_bytes = await command_bus.send(command)

        if pdf_bytes:
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=declaration_{declaration_id}.pdf"
                }
            )
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="PDF generation failed")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/declarations/{declaration_id}/export/xml")
async def export_xml(
    declaration_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    form_id: str = Query(default="dt"),
):
    """Export declaration as XML."""
    try:
        command = ExportDeclarationXmlCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
            form_id=form_id,
        )

        xml_bytes = await command_bus.send(command)

        if xml_bytes:
            return Response(
                content=xml_bytes,
                media_type="application/xml",
                headers={
                    "Content-Disposition": f"attachment; filename=declaration_{declaration_id}.xml"
                }
            )
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="XML generation failed")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/declarations/{declaration_id}/import/xml", response_model=OperationResponse)
async def import_xml(
    declaration_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    file: UploadFile = File(...),
    document_mode_id: str = Query(default="1006"),
):
    """Import declaration data from XML file."""
    try:
        xml_content = await file.read()

        command = ImportDeclarationXmlCommand(
            declaration_id=declaration_id,
            user_id=current_user["user_id"],
            xml_content=xml_content,
            document_mode_id=document_mode_id,
        )

        await command_bus.send(command)
        return OperationResponse(success=True, message="XML imported successfully")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# Kontur Reference Data Endpoints (Options)
# Uses QueryBus for proper CQRS architecture - handlers inject adapter
# =============================================================================

@router.get("/options/organizations", response_model=List[KonturOrganizationOption])
async def list_kontur_organizations(
    current_user: Annotated[dict, Depends(get_current_user)],
    query_bus=Depends(get_query_bus),
):
    """Get list of organizations from Kontur."""
    try:
        query = GetKonturOrganizationsQuery()
        results = await query_bus.query(query)
        return [
            KonturOrganizationOption(
                id=org.id,
                name=org.name,
                inn=org.inn,
            )
            for org in results
        ]
    except KonturServiceUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        log.error(f"Failed to fetch organizations from Kontur: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Kontur service unavailable")


@router.get("/options/employees/{org_id}", response_model=List[KonturEmployeeOption])
async def list_kontur_employees(
    org_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    query_bus=Depends(get_query_bus),
):
    """Get list of employees for organization from Kontur."""
    try:
        query = GetKonturEmployeesQuery(organization_id=org_id)
        results = await query_bus.query(query)
        return [
            KonturEmployeeOption(
                id=emp.id,
                name=emp.name,
                position=emp.position,
            )
            for emp in results
        ]
    except KonturServiceUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        log.error(f"Failed to fetch employees from Kontur: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Kontur service unavailable")


@router.get("/options/customs", response_model=List[KonturCustomsOption])
async def list_kontur_customs(
    current_user: Annotated[dict, Depends(get_current_user)],
    query_bus=Depends(get_query_bus),
):
    """Get list of customs offices from Kontur."""
    try:
        query = GetCustomsOfficesQuery()
        results = await query_bus.query(query)
        return [
            KonturCustomsOption(
                code=c.code,
                name=c.name,
            )
            for c in results
        ]
    except KonturServiceUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        log.error(f"Failed to fetch customs from Kontur: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Kontur service unavailable")


@router.get("/options/declaration-types", response_model=List[KonturDeclarationTypeOption])
async def list_kontur_declaration_types(
    current_user: Annotated[dict, Depends(get_current_user)],
    query_bus=Depends(get_query_bus),
):
    """Get list of declaration types from Kontur."""
    try:
        query = GetKonturDeclarationTypesQuery()
        results = await query_bus.query(query)
        return [
            KonturDeclarationTypeOption(
                code=t.code,
                name=t.name,
            )
            for t in results
        ]
    except KonturServiceUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        log.error(f"Failed to fetch declaration types from Kontur: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Kontur service unavailable")


@router.get("/options/procedures/{declaration_type}", response_model=List[KonturProcedureOption])
async def list_kontur_procedures(
    declaration_type: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    query_bus=Depends(get_query_bus),
):
    """Get list of procedures for declaration type from Kontur."""
    try:
        query = GetCustomsProceduresQuery(
            declaration_type=DeclarationType(declaration_type) if declaration_type else None
        )
        results = await query_bus.query(query)
        return [
            KonturProcedureOption(
                code=p.code,
                name=p.name,
                description=p.description,
            )
            for p in results
        ]
    except KonturServiceUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        log.error(f"Failed to fetch procedures from Kontur: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Kontur service unavailable")


# =============================================================================
# EOF
# =============================================================================
