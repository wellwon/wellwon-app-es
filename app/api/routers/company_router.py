# =============================================================================
# File: app/api/routers/company_router.py
# Description: Company domain API endpoints
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, UploadFile, File

from app.security.jwt_auth import get_current_user

# API Models
from app.api.models.company_api_models import (
    CreateCompanyRequest,
    UpdateCompanyRequest,
    ArchiveCompanyRequest,
    AddUserToCompanyRequest,
    ChangeUserRoleRequest,
    RemoveUserRequest,
    CreateTelegramSupergroupRequest,
    LinkTelegramSupergroupRequest,
    UpdateTelegramSupergroupRequest,
    UpdateBalanceRequest,
    CompanyResponse,
    CompanyDetailResponse,
    CompanySummaryResponse,
    UserCompanyResponse,
    CompanyUserResponse,
    TelegramSupergroupResponse,
    CreateSupergroupResponse,
    BalanceResponse,
    BalanceTransactionResponse,
    BalanceHistoryResponse,
)

# Commands
from app.company.commands import (
    CreateCompanyCommand,
    UpdateCompanyCommand,
    ArchiveCompanyCommand,
    RestoreCompanyCommand,
    DeleteCompanyCommand,
    RequestCompanyDeletionCommand,
    AddUserToCompanyCommand,
    RemoveUserFromCompanyCommand,
    ChangeUserCompanyRoleCommand,
    CreateTelegramSupergroupCommand,
    LinkTelegramSupergroupCommand,
    UnlinkTelegramSupergroupCommand,
    UpdateTelegramSupergroupCommand,
    UpdateCompanyBalanceCommand,
)

# Queries
from app.company.queries import (
    GetCompanyByIdQuery,
    GetCompaniesQuery,
    GetCompaniesByUserQuery,
    SearchCompaniesQuery,
    GetCompanyByVatQuery,
    GetCompanyUsersQuery,
    GetUserCompanyRelationshipQuery,
    GetCompanyTelegramSupergroupsQuery,
    GetCompanyByTelegramGroupQuery,
    GetCompanyBalanceQuery,
    GetCompanyBalanceHistoryQuery,
    CompanyDetail,
    CompanySummary,
    CompanyUserInfo,
    TelegramSupergroupInfo,
    BalanceInfo,
    BalanceTransaction,
)

log = logging.getLogger("wellwon.api.company")

router = APIRouter(prefix="/companies", tags=["companies"])


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
# Company Lifecycle Endpoints
# =============================================================================

@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    request: CreateCompanyRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """
    Create a new company.

    If create_telegram_group=True, a CompanyCreationSaga will be triggered to:
    1. Create Telegram supergroup
    2. Link it to the company
    3. Create company chat (or link existing chat if link_chat_id is provided)
    """
    try:
        company_id = uuid.uuid4()
        command = CreateCompanyCommand(
            company_id=company_id,
            name=request.name,
            company_type=request.company_type,
            created_by=current_user["user_id"],
            vat=request.vat,
            ogrn=request.ogrn,
            kpp=request.kpp,
            postal_code=request.postal_code,
            country_id=request.country_id,
            city=request.city,
            street=request.street,
            director=request.director,
            email=request.email,
            phone=request.phone,
            tg_dir=request.tg_dir,
            tg_accountant=request.tg_accountant,
            tg_manager_1=request.tg_manager_1,
            tg_manager_2=request.tg_manager_2,
            tg_manager_3=request.tg_manager_3,
            tg_support=request.tg_support,
            # Saga orchestration options
            create_telegram_group=request.create_telegram_group,
            telegram_group_title=request.telegram_group_title,
            telegram_group_description=request.telegram_group_description,
            link_chat_id=request.link_chat_id,
        )

        result_id = await command_bus.send(command)
        log.info(f"Company created: {result_id} by user {current_user['user_id']}")
        return CompanyResponse(id=result_id, message="Company created")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        log.error(f"Failed to create company: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create company")


@router.get("", response_model=List[CompanySummaryResponse])
async def get_my_companies(
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get all companies for current user"""
    query = GetCompaniesByUserQuery(
        user_id=current_user["user_id"],
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )

    results = await query_bus.query(query)
    return [CompanySummaryResponse(**r.model_dump()) for r in results]


@router.get("/search", response_model=List[CompanySummaryResponse])
async def search_companies(
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=50),
):
    """Search companies by name or VAT"""
    query = SearchCompaniesQuery(
        search_term=q,
        limit=limit,
    )

    results = await query_bus.query(query)
    return [CompanySummaryResponse(**r.model_dump()) for r in results]


# =============================================================================
# DaData Integration Endpoints
# =============================================================================

from pydantic import BaseModel, Field


class LookupVatRequest(BaseModel):
    """Request for company lookup by VAT (INN)"""
    vat: str = Field(..., min_length=10, max_length=12, description="Company INN (10 or 12 digits)")


class LookupVatResponse(BaseModel):
    """Response from company lookup"""
    found: bool
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    okved: Optional[str] = None
    name_short: Optional[str] = None
    name_full: Optional[str] = None
    name_short_with_opf: Optional[str] = None
    name_full_with_opf: Optional[str] = None
    opf_short: Optional[str] = None
    opf_full: Optional[str] = None
    status: Optional[str] = None
    type: Optional[str] = None
    address: Optional[str] = None
    director_name: Optional[str] = None
    director_post: Optional[str] = None
    registration_date: Optional[str] = None
    liquidation_date: Optional[str] = None
    capital_value: Optional[float] = None
    emails: List[str] = []
    phones: List[str] = []


@router.post("/lookup-vat", response_model=LookupVatResponse)
async def lookup_company_by_vat_dadata(
    body: LookupVatRequest,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Lookup company information by VAT (INN) using DaData API.

    This endpoint fetches company details from the Russian DaData service
    by INN (Taxpayer Identification Number).
    """
    # Get DaData adapter from app state (initialized in adapters.py)
    adapter = request.app.state.dadata_adapter
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DaData service is not configured"
        )

    try:
        company = await adapter.lookup_company_by_inn(body.vat)

        if not company:
            return LookupVatResponse(found=False)

        return LookupVatResponse(
            found=True,
            inn=company.inn,
            kpp=company.kpp,
            ogrn=company.ogrn,
            okved=company.okved,
            name_short=company.name_short,
            name_full=company.name_full,
            name_short_with_opf=company.name_short_with_opf,
            name_full_with_opf=company.name_full_with_opf,
            opf_short=company.opf_short,
            opf_full=company.opf_full,
            status=company.status,
            type=company.type,
            address=company.address_value,
            director_name=company.director_name,
            director_post=company.director_post,
            registration_date=company.registration_date,
            liquidation_date=company.liquidation_date,
            capital_value=company.capital_value,
            emails=company.emails,
            phones=company.phones,
        )

    except Exception as e:
        log.error(f"DaData lookup failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to lookup company"
        )


@router.get("/by-vat/{vat}", response_model=CompanyDetailResponse)
async def get_company_by_vat(
    vat: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Get company by VAT (INN)"""
    query = GetCompanyByVatQuery(vat=vat)
    result = await query_bus.query(query)

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return CompanyDetailResponse(**result.model_dump())


@router.get("/{company_id}", response_model=CompanyDetailResponse)
async def get_company(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Get company details"""
    query = GetCompanyByIdQuery(company_id=company_id)
    result = await query_bus.query(query)

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return CompanyDetailResponse(**result.model_dump())


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: uuid.UUID,
    request: UpdateCompanyRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Update company details"""
    try:
        command = UpdateCompanyCommand(
            company_id=company_id,
            updated_by=current_user["user_id"],
            name=request.name,
            company_type=request.company_type,
            vat=request.vat,
            ogrn=request.ogrn,
            kpp=request.kpp,
            postal_code=request.postal_code,
            country_id=request.country_id,
            city=request.city,
            street=request.street,
            director=request.director,
            email=request.email,
            phone=request.phone,
            tg_dir=request.tg_dir,
            tg_accountant=request.tg_accountant,
            tg_manager_1=request.tg_manager_1,
            tg_manager_2=request.tg_manager_2,
            tg_manager_3=request.tg_manager_3,
            tg_support=request.tg_support,
        )

        await command_bus.send(command)
        return CompanyResponse(id=company_id, message="Company updated")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{company_id}/archive", response_model=CompanyResponse)
async def archive_company(
    company_id: uuid.UUID,
    request: ArchiveCompanyRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Archive (soft delete) a company"""
    try:
        command = ArchiveCompanyCommand(
            company_id=company_id,
            archived_by=current_user["user_id"],
            reason=request.reason,
        )

        await command_bus.send(command)
        return CompanyResponse(id=company_id, message="Company archived")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{company_id}/restore", response_model=CompanyResponse)
async def restore_company(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Restore an archived company"""
    try:
        command = RestoreCompanyCommand(
            company_id=company_id,
            restored_by=current_user["user_id"],
        )

        await command_bus.send(command)
        return CompanyResponse(id=company_id, message="Company restored")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{company_id}", response_model=CompanyResponse)
async def delete_company(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
    cascade: bool = Query(True, description="If True, use saga to cascade delete messages/chats/telegram"),
    preserve_company: bool = Query(False, description="If True, preserve company record for future re-linking"),
):
    """
    Permanently delete a company (hard delete).

    If cascade=True (default), sends RequestCompanyDeletionCommand which:
    1. Handler enriches event with all chat_ids and telegram_group_id
    2. Publishes CompanyDeleteRequested event
    3. Triggers GroupDeletionSaga (TRUE SAGA pattern)
    4. Saga cascades: Delete chats (with messages) -> Delete Telegram -> Delete Company

    If preserve_company=True, the company record is kept for future re-linking
    to a new Telegram group. Useful when company has other linked entities.

    If cascade=False, only deletes the company record (chats/messages remain orphaned).

    TRUE SAGA Pattern: Handler queries all data and enriches event. Saga uses ONLY
    enriched event data (no queries, no direct SQL).
    """
    try:
        if cascade:
            # TRUE SAGA Pattern: Send command, handler enriches event with all data
            # Saga uses ONLY enriched event data (no queries in saga)
            command = RequestCompanyDeletionCommand(
                company_id=company_id,
                deleted_by=current_user["user_id"],
                cascade=True,
                preserve_company=preserve_company,
            )

            await command_bus.send(command)

            log.info(f"RequestCompanyDeletionCommand sent for company {company_id}, preserve_company={preserve_company}")
            message = "Company deletion requested (saga will cascade delete)"
            if preserve_company:
                message = "Telegram group deletion requested (company preserved for re-linking)"
            return CompanyResponse(
                id=company_id,
                message=message
            )

        else:
            # Direct delete (no cascade)
            command = DeleteCompanyCommand(
                company_id=company_id,
                deleted_by=current_user["user_id"],
            )

            await command_bus.send(command)
            return CompanyResponse(id=company_id, message="Company deleted")

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        log.error(f"Failed to delete company: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete company")


# =============================================================================
# User-Company Relationship Endpoints
# =============================================================================

@router.get("/{company_id}/users", response_model=List[CompanyUserResponse])
async def get_company_users(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
    include_inactive: bool = Query(False),
):
    """Get users of a company"""
    query = GetCompanyUsersQuery(
        company_id=company_id,
        include_inactive=include_inactive,
    )

    results = await query_bus.query(query)
    return [CompanyUserResponse(**r.model_dump()) for r in results]


@router.post("/{company_id}/users", response_model=CompanyResponse)
async def add_user_to_company(
    company_id: uuid.UUID,
    request: AddUserToCompanyRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Add a user to company"""
    try:
        command = AddUserToCompanyCommand(
            company_id=company_id,
            user_id=request.user_id,
            relationship_type=request.relationship_type,
            added_by=current_user["user_id"],
        )

        await command_bus.send(command)
        return CompanyResponse(id=company_id, message="User added to company")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{company_id}/users/{user_id}", response_model=CompanyResponse)
async def remove_user_from_company(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
    reason: Optional[str] = Query(None, max_length=500),
):
    """Remove a user from company"""
    try:
        command = RemoveUserFromCompanyCommand(
            company_id=company_id,
            user_id=user_id,
            removed_by=current_user["user_id"],
            reason=reason,
        )

        await command_bus.send(command)
        return CompanyResponse(id=company_id, message="User removed from company")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{company_id}/users/{user_id}/role", response_model=CompanyResponse)
async def change_user_company_role(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    request: ChangeUserRoleRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Change a user's role in company"""
    try:
        command = ChangeUserCompanyRoleCommand(
            company_id=company_id,
            user_id=user_id,
            new_relationship_type=request.new_relationship_type,
            changed_by=current_user["user_id"],
        )

        await command_bus.send(command)
        return CompanyResponse(id=company_id, message="User role changed")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{company_id}/users/{user_id}/relationship", response_model=UserCompanyResponse)
async def get_user_company_relationship(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Get user's relationship with company"""
    query = GetUserCompanyRelationshipQuery(
        company_id=company_id,
        user_id=user_id,
    )

    result = await query_bus.query(query)
    if not result or not result.is_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not in company")

    return UserCompanyResponse(
        company_id=company_id,
        company_name=result.company_name or "",
        company_type=result.company_type or "company",
        relationship_type=result.relationship_type,
        joined_at=result.joined_at,
        is_active=result.is_member,
    )


# =============================================================================
# Telegram Integration Endpoints
# =============================================================================

@router.get("/{company_id}/telegram", response_model=List[TelegramSupergroupResponse])
async def get_company_telegram_supergroups(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Get Telegram supergroups for company"""
    query = GetCompanyTelegramSupergroupsQuery(company_id=company_id)
    results = await query_bus.query(query)
    return [TelegramSupergroupResponse(**r.model_dump()) for r in results]


@router.post("/{company_id}/telegram", response_model=CreateSupergroupResponse)
async def create_telegram_supergroup(
    company_id: uuid.UUID,
    request: CreateTelegramSupergroupRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Create a Telegram supergroup for company"""
    try:
        # Use Telegram adapter to create the group
        from app.infra.telegram.adapter import get_telegram_adapter

        adapter = await get_telegram_adapter()
        result = await adapter.create_company_group(
            company_name=request.title,
            description=request.description or "",
            setup_bots=True,
        )

        if not result.success:
            return CreateSupergroupResponse(
                success=False,
                error=result.error or "Failed to create Telegram supergroup"
            )

        # Create command to link the supergroup
        command = CreateTelegramSupergroupCommand(
            company_id=company_id,
            telegram_group_id=result.group_id,
            title=result.group_title or request.title,
            username=request.username,
            description=request.description,
            invite_link=result.invite_link,
            is_forum=request.is_forum,
            created_by=current_user["user_id"],
        )

        await command_bus.send(command)

        return CreateSupergroupResponse(
            success=True,
            telegram_group_id=result.group_id,
            title=result.group_title,
            invite_link=result.invite_link,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        log.error(f"Failed to create Telegram supergroup: {e}", exc_info=True)
        return CreateSupergroupResponse(success=False, error=str(e))


@router.post("/{company_id}/telegram/link", response_model=CompanyResponse)
async def link_telegram_supergroup(
    company_id: uuid.UUID,
    request: LinkTelegramSupergroupRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Link an existing Telegram supergroup to company"""
    try:
        command = LinkTelegramSupergroupCommand(
            company_id=company_id,
            telegram_group_id=request.telegram_group_id,
            linked_by=current_user["user_id"],
        )

        await command_bus.send(command)
        return CompanyResponse(id=company_id, message="Telegram supergroup linked")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{company_id}/telegram/{telegram_group_id}", response_model=CompanyResponse)
async def unlink_telegram_supergroup(
    company_id: uuid.UUID,
    telegram_group_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Unlink a Telegram supergroup from company"""
    try:
        command = UnlinkTelegramSupergroupCommand(
            company_id=company_id,
            telegram_group_id=telegram_group_id,
            unlinked_by=current_user["user_id"],
        )

        await command_bus.send(command)
        return CompanyResponse(id=company_id, message="Telegram supergroup unlinked")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{company_id}/telegram/{telegram_group_id}", response_model=CompanyResponse)
async def update_telegram_supergroup(
    company_id: uuid.UUID,
    telegram_group_id: int,
    request: UpdateTelegramSupergroupRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Update Telegram supergroup info"""
    try:
        command = UpdateTelegramSupergroupCommand(
            company_id=company_id,
            telegram_group_id=telegram_group_id,
            title=request.title,
            description=request.description,
        )

        await command_bus.send(command)
        return CompanyResponse(id=company_id, message="Telegram supergroup updated")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# Balance Endpoints
# =============================================================================

@router.get("/{company_id}/balance", response_model=BalanceResponse)
async def get_company_balance(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Get company balance"""
    query = GetCompanyBalanceQuery(company_id=company_id)
    result = await query_bus.query(query)

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return BalanceResponse(**result.model_dump())


@router.post("/{company_id}/balance", response_model=BalanceResponse)
async def update_company_balance(
    company_id: uuid.UUID,
    request: UpdateBalanceRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Update company balance"""
    try:
        command = UpdateCompanyBalanceCommand(
            company_id=company_id,
            change_amount=request.change_amount,
            reason=request.reason,
            reference_id=request.reference_id,
            updated_by=current_user["user_id"],
        )

        await command_bus.send(command)

        # Return updated balance
        query = GetCompanyBalanceQuery(company_id=company_id)
        result = await query_bus.query(query)
        return BalanceResponse(**result.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{company_id}/balance/history", response_model=BalanceHistoryResponse)
async def get_company_balance_history(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get company balance transaction history"""
    # Get current balance
    balance_query = GetCompanyBalanceQuery(company_id=company_id)
    balance_result = await query_bus.query(balance_query)

    if not balance_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    # Get transaction history
    history_query = GetCompanyBalanceHistoryQuery(
        company_id=company_id,
        limit=limit,
        offset=offset,
    )
    transactions = await query_bus.query(history_query)

    return BalanceHistoryResponse(
        company_id=company_id,
        current_balance=balance_result.balance,
        transactions=[BalanceTransactionResponse(**t.model_dump()) for t in transactions],
        total_count=len(transactions),
    )


# =============================================================================
# Logo Endpoints
# =============================================================================

from app.infra.storage.minio_provider import get_storage_provider


class LogoUploadResponse(BaseModel):
    """Response for logo upload"""
    success: bool
    logo_url: Optional[str] = None
    error: Optional[str] = None


class LogoDeleteResponse(BaseModel):
    """Response for logo delete"""
    success: bool
    error: Optional[str] = None


# Allowed image types for logo
ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_LOGO_SIZE = 4 * 1024 * 1024  # 4MB


@router.post("/{company_id}/logo", response_model=LogoUploadResponse)
async def upload_company_logo(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    file: UploadFile = File(...),
):
    """
    Upload company logo.

    Accepts image files (PNG, JPEG, WebP, GIF) up to 4MB.
    """
    try:
        # Validate content type
        if file.content_type not in ALLOWED_LOGO_TYPES:
            return LogoUploadResponse(
                success=False,
                error=f"Invalid file type. Allowed: {', '.join(ALLOWED_LOGO_TYPES)}"
            )

        # Read file content
        content = await file.read()

        # Validate size
        if len(content) > MAX_LOGO_SIZE:
            return LogoUploadResponse(
                success=False,
                error=f"File too large. Maximum size: {MAX_LOGO_SIZE // 1024 // 1024}MB"
            )

        # Upload to storage
        storage = get_storage_provider()
        result = await storage.upload_file(
            bucket="company-logos",
            file_content=content,
            content_type=file.content_type,
            original_filename=file.filename,
        )

        if not result.success:
            return LogoUploadResponse(success=False, error=result.error)

        log.info(f"Logo uploaded for company {company_id}: {result.public_url}")

        return LogoUploadResponse(
            success=True,
            logo_url=result.public_url,
        )

    except Exception as e:
        log.error(f"Failed to upload logo: {e}", exc_info=True)
        return LogoUploadResponse(success=False, error="Failed to upload logo")


@router.delete("/{company_id}/logo", response_model=LogoDeleteResponse)
async def delete_company_logo(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    logo_url: str = Query(..., description="URL of the logo to delete"),
):
    """Delete company logo by URL"""
    try:
        storage = get_storage_provider()
        deleted = await storage.delete_by_url(logo_url)

        if deleted:
            log.info(f"Logo deleted for company {company_id}: {logo_url}")
            return LogoDeleteResponse(success=True)
        else:
            return LogoDeleteResponse(success=False, error="Logo not found")

    except Exception as e:
        log.error(f"Failed to delete logo: {e}", exc_info=True)
        return LogoDeleteResponse(success=False, error="Failed to delete logo")
