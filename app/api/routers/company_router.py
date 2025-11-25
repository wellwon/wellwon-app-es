# =============================================================================
# File: app/api/routers/company_router.py
# Description: Company domain API endpoints
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.security.jwt_auth import get_current_user
from app.api.dependencies.cqrs_deps import get_handler_dependencies

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

router = APIRouter(prefix="/api/companies", tags=["companies"])


# =============================================================================
# Company Lifecycle Endpoints
# =============================================================================

@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    request: CreateCompanyRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Create a new company"""
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
        )

        result_id = await deps["command_bus"].dispatch(command)
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
    deps: Annotated[dict, Depends(get_handler_dependencies)],
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

    results = await deps["query_bus"].query(query)
    return [CompanySummaryResponse(**r.model_dump()) for r in results]


@router.get("/search", response_model=List[CompanySummaryResponse])
async def search_companies(
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=50),
):
    """Search companies by name or VAT"""
    query = SearchCompaniesQuery(
        search_term=q,
        limit=limit,
    )

    results = await deps["query_bus"].query(query)
    return [CompanySummaryResponse(**r.model_dump()) for r in results]


@router.get("/by-vat/{vat}", response_model=CompanyDetailResponse)
async def get_company_by_vat(
    vat: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Get company by VAT (INN)"""
    query = GetCompanyByVatQuery(vat=vat)
    result = await deps["query_bus"].query(query)

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return CompanyDetailResponse(**result.model_dump())


@router.get("/{company_id}", response_model=CompanyDetailResponse)
async def get_company(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Get company details"""
    query = GetCompanyByIdQuery(company_id=company_id)
    result = await deps["query_bus"].query(query)

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return CompanyDetailResponse(**result.model_dump())


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: uuid.UUID,
    request: UpdateCompanyRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
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

        await deps["command_bus"].dispatch(command)
        return CompanyResponse(id=company_id, message="Company updated")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{company_id}/archive", response_model=CompanyResponse)
async def archive_company(
    company_id: uuid.UUID,
    request: ArchiveCompanyRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Archive (soft delete) a company"""
    try:
        command = ArchiveCompanyCommand(
            company_id=company_id,
            archived_by=current_user["user_id"],
            reason=request.reason,
        )

        await deps["command_bus"].dispatch(command)
        return CompanyResponse(id=company_id, message="Company archived")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{company_id}/restore", response_model=CompanyResponse)
async def restore_company(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Restore an archived company"""
    try:
        command = RestoreCompanyCommand(
            company_id=company_id,
            restored_by=current_user["user_id"],
        )

        await deps["command_bus"].dispatch(command)
        return CompanyResponse(id=company_id, message="Company restored")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{company_id}", response_model=CompanyResponse)
async def delete_company(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Permanently delete a company (hard delete)"""
    try:
        command = DeleteCompanyCommand(
            company_id=company_id,
            deleted_by=current_user["user_id"],
        )

        await deps["command_bus"].dispatch(command)
        return CompanyResponse(id=company_id, message="Company deleted")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# User-Company Relationship Endpoints
# =============================================================================

@router.get("/{company_id}/users", response_model=List[CompanyUserResponse])
async def get_company_users(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
    include_inactive: bool = Query(False),
):
    """Get users of a company"""
    query = GetCompanyUsersQuery(
        company_id=company_id,
        include_inactive=include_inactive,
    )

    results = await deps["query_bus"].query(query)
    return [CompanyUserResponse(**r.model_dump()) for r in results]


@router.post("/{company_id}/users", response_model=CompanyResponse)
async def add_user_to_company(
    company_id: uuid.UUID,
    request: AddUserToCompanyRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Add a user to company"""
    try:
        command = AddUserToCompanyCommand(
            company_id=company_id,
            user_id=request.user_id,
            relationship_type=request.relationship_type,
            added_by=current_user["user_id"],
        )

        await deps["command_bus"].dispatch(command)
        return CompanyResponse(id=company_id, message="User added to company")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{company_id}/users/{user_id}", response_model=CompanyResponse)
async def remove_user_from_company(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
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

        await deps["command_bus"].dispatch(command)
        return CompanyResponse(id=company_id, message="User removed from company")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{company_id}/users/{user_id}/role", response_model=CompanyResponse)
async def change_user_company_role(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    request: ChangeUserRoleRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Change a user's role in company"""
    try:
        command = ChangeUserCompanyRoleCommand(
            company_id=company_id,
            user_id=user_id,
            new_relationship_type=request.new_relationship_type,
            changed_by=current_user["user_id"],
        )

        await deps["command_bus"].dispatch(command)
        return CompanyResponse(id=company_id, message="User role changed")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{company_id}/users/{user_id}/relationship", response_model=UserCompanyResponse)
async def get_user_company_relationship(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Get user's relationship with company"""
    query = GetUserCompanyRelationshipQuery(
        company_id=company_id,
        user_id=user_id,
    )

    result = await deps["query_bus"].query(query)
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
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Get Telegram supergroups for company"""
    query = GetCompanyTelegramSupergroupsQuery(company_id=company_id)
    results = await deps["query_bus"].query(query)
    return [TelegramSupergroupResponse(**r.model_dump()) for r in results]


@router.post("/{company_id}/telegram", response_model=CreateSupergroupResponse)
async def create_telegram_supergroup(
    company_id: uuid.UUID,
    request: CreateTelegramSupergroupRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
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

        await deps["command_bus"].dispatch(command)

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
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Link an existing Telegram supergroup to company"""
    try:
        command = LinkTelegramSupergroupCommand(
            company_id=company_id,
            telegram_group_id=request.telegram_group_id,
            linked_by=current_user["user_id"],
        )

        await deps["command_bus"].dispatch(command)
        return CompanyResponse(id=company_id, message="Telegram supergroup linked")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{company_id}/telegram/{telegram_group_id}", response_model=CompanyResponse)
async def unlink_telegram_supergroup(
    company_id: uuid.UUID,
    telegram_group_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Unlink a Telegram supergroup from company"""
    try:
        command = UnlinkTelegramSupergroupCommand(
            company_id=company_id,
            telegram_group_id=telegram_group_id,
            unlinked_by=current_user["user_id"],
        )

        await deps["command_bus"].dispatch(command)
        return CompanyResponse(id=company_id, message="Telegram supergroup unlinked")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{company_id}/telegram/{telegram_group_id}", response_model=CompanyResponse)
async def update_telegram_supergroup(
    company_id: uuid.UUID,
    telegram_group_id: int,
    request: UpdateTelegramSupergroupRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Update Telegram supergroup info"""
    try:
        command = UpdateTelegramSupergroupCommand(
            company_id=company_id,
            telegram_group_id=telegram_group_id,
            title=request.title,
            description=request.description,
        )

        await deps["command_bus"].dispatch(command)
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
    deps: Annotated[dict, Depends(get_handler_dependencies)],
):
    """Get company balance"""
    query = GetCompanyBalanceQuery(company_id=company_id)
    result = await deps["query_bus"].query(query)

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return BalanceResponse(**result.model_dump())


@router.post("/{company_id}/balance", response_model=BalanceResponse)
async def update_company_balance(
    company_id: uuid.UUID,
    request: UpdateBalanceRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
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

        await deps["command_bus"].dispatch(command)

        # Return updated balance
        query = GetCompanyBalanceQuery(company_id=company_id)
        result = await deps["query_bus"].query(query)
        return BalanceResponse(**result.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{company_id}/balance/history", response_model=BalanceHistoryResponse)
async def get_company_balance_history(
    company_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    deps: Annotated[dict, Depends(get_handler_dependencies)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get company balance transaction history"""
    # Get current balance
    balance_query = GetCompanyBalanceQuery(company_id=company_id)
    balance_result = await deps["query_bus"].query(balance_query)

    if not balance_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    # Get transaction history
    history_query = GetCompanyBalanceHistoryQuery(
        company_id=company_id,
        limit=limit,
        offset=offset,
    )
    transactions = await deps["query_bus"].query(history_query)

    return BalanceHistoryResponse(
        company_id=company_id,
        current_balance=balance_result.balance,
        transactions=[BalanceTransactionResponse(**t.model_dump()) for t in transactions],
        total_count=len(transactions),
    )
