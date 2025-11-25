# =============================================================================
# File: app/company/query_handlers/company_query_handlers.py
# Description: Query handlers for Company domain - CQRS COMPLIANT
# =============================================================================

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List
from decimal import Decimal

from app.config.logging_config import get_logger
from app.infra.cqrs.decorators import query_handler, readonly_query, cached_query_handler
from app.common.base.base_query_handler import BaseQueryHandler
from app.company.queries import (
    # Company queries
    GetCompanyByIdQuery,
    GetCompaniesQuery,
    GetCompaniesByUserQuery,
    SearchCompaniesQuery,
    GetCompanyByVatQuery,
    # User-company queries
    GetCompanyUsersQuery,
    GetUserCompanyRelationshipQuery,
    # Telegram queries
    GetCompanyTelegramSupergroupsQuery,
    GetCompanyByTelegramGroupQuery,
    # Balance queries
    GetCompanyBalanceQuery,
    GetCompanyBalanceHistoryQuery,
    # Result types
    CompanyDetail,
    CompanySummary,
    UserCompanyInfo,
    CompanyUserInfo,
    TelegramSupergroupInfo,
    BalanceInfo,
    BalanceTransaction,
    UserCompanyRelationship,
)
from app.infra.read_repos.company_read_repo import CompanyReadRepo
from app.common.exceptions.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.company.query_handlers")


# =============================================================================
# Company Query Handlers
# =============================================================================

@cached_query_handler(GetCompanyByIdQuery, ttl=120)
class GetCompanyByIdQueryHandler(BaseQueryHandler[GetCompanyByIdQuery, CompanyDetail]):
    """Handler for getting company details by ID"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetCompanyByIdQuery) -> CompanyDetail:
        """Get company details"""
        company = await CompanyReadRepo.get_company_by_id(query.company_id)

        if not company:
            raise ResourceNotFoundError(f"Company not found: {query.company_id}")

        return CompanyDetail(
            id=company.id,
            name=company.name,
            company_type=company.company_type,
            created_by=company.created_by,
            created_at=company.created_at,
            updated_at=company.updated_at,
            is_active=company.is_active,
            vat=company.vat,
            ogrn=company.ogrn,
            kpp=company.kpp,
            postal_code=company.postal_code,
            country_id=company.country_id,
            city=company.city,
            street=company.street,
            director=company.director,
            email=company.email,
            phone=company.phone,
            tg_dir=company.tg_dir,
            tg_accountant=company.tg_accountant,
            tg_manager_1=company.tg_manager_1,
            tg_manager_2=company.tg_manager_2,
            tg_manager_3=company.tg_manager_3,
            tg_support=company.tg_support,
            balance=company.balance,
            user_count=company.user_count,
        )


@readonly_query(GetCompaniesQuery)
class GetCompaniesQueryHandler(BaseQueryHandler[GetCompaniesQuery, List[CompanySummary]]):
    """Handler for getting all companies (admin view)"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetCompaniesQuery) -> List[CompanySummary]:
        """Get all companies"""
        companies = await CompanyReadRepo.get_companies(
            include_archived=query.include_archived,
            include_deleted=query.include_deleted,
            limit=query.limit,
            offset=query.offset,
        )

        return [
            CompanySummary(
                id=c.id,
                name=c.name,
                company_type=c.company_type,
                vat=c.vat,
                city=c.city,
                user_count=c.user_count,
                balance=c.balance,
                is_active=c.is_active,
            )
            for c in companies
        ]


@readonly_query(GetCompaniesByUserQuery)
class GetCompaniesByUserQueryHandler(BaseQueryHandler[GetCompaniesByUserQuery, List[UserCompanyInfo]]):
    """Handler for getting all companies for a user"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetCompaniesByUserQuery) -> List[UserCompanyInfo]:
        """Get user's companies"""
        user_companies = await CompanyReadRepo.get_companies_by_user(
            user_id=query.user_id,
            include_archived=query.include_archived,
            limit=query.limit,
            offset=query.offset,
        )

        return [
            UserCompanyInfo(
                company_id=uc.company_id,
                user_id=query.user_id,
                relationship_type=uc.relationship_type,
                joined_at=uc.joined_at,
                is_active=uc.is_active,
                company_name=uc.company_name,
                company_type=uc.company_type,
            )
            for uc in user_companies
        ]


@readonly_query(SearchCompaniesQuery)
class SearchCompaniesQueryHandler(BaseQueryHandler[SearchCompaniesQuery, List[CompanySummary]]):
    """Handler for searching companies"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: SearchCompaniesQuery) -> List[CompanySummary]:
        """Search companies by name or VAT"""
        companies = await CompanyReadRepo.search_companies(
            search_term=query.search_term,
            limit=query.limit,
        )

        return [
            CompanySummary(
                id=c.id,
                name=c.name,
                company_type=c.company_type,
                vat=c.vat,
                city=c.city,
                user_count=c.user_count,
                balance=c.balance,
                is_active=c.is_active,
            )
            for c in companies
        ]


@readonly_query(GetCompanyByVatQuery)
class GetCompanyByVatQueryHandler(BaseQueryHandler[GetCompanyByVatQuery, Optional[CompanyDetail]]):
    """Handler for getting company by VAT (INN)"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetCompanyByVatQuery) -> Optional[CompanyDetail]:
        """Get company by VAT"""
        company = await CompanyReadRepo.get_company_by_vat(query.vat)

        if not company:
            return None

        return CompanyDetail(
            id=company.id,
            name=company.name,
            company_type=company.company_type,
            created_by=company.created_by,
            created_at=company.created_at,
            updated_at=company.updated_at,
            is_active=company.is_active,
            vat=company.vat,
            ogrn=company.ogrn,
            kpp=company.kpp,
            postal_code=company.postal_code,
            country_id=company.country_id,
            city=company.city,
            street=company.street,
            director=company.director,
            email=company.email,
            phone=company.phone,
            tg_dir=company.tg_dir,
            tg_accountant=company.tg_accountant,
            tg_manager_1=company.tg_manager_1,
            tg_manager_2=company.tg_manager_2,
            tg_manager_3=company.tg_manager_3,
            tg_support=company.tg_support,
            balance=company.balance,
            user_count=company.user_count,
        )


# =============================================================================
# User-Company Query Handlers
# =============================================================================

@readonly_query(GetCompanyUsersQuery)
class GetCompanyUsersQueryHandler(BaseQueryHandler[GetCompanyUsersQuery, List[CompanyUserInfo]]):
    """Handler for getting users of a company"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetCompanyUsersQuery) -> List[CompanyUserInfo]:
        """Get company users"""
        users = await CompanyReadRepo.get_company_users(
            company_id=query.company_id,
            include_inactive=query.include_inactive,
        )

        return [
            CompanyUserInfo(
                user_id=u.user_id,
                relationship_type=u.relationship_type,
                joined_at=u.joined_at,
                is_active=u.is_active,
            )
            for u in users
        ]


@readonly_query(GetUserCompanyRelationshipQuery)
class GetUserCompanyRelationshipQueryHandler(BaseQueryHandler[GetUserCompanyRelationshipQuery, UserCompanyRelationship]):
    """Handler for checking user's relationship with company"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetUserCompanyRelationshipQuery) -> UserCompanyRelationship:
        """Check user-company relationship"""
        relationship = await CompanyReadRepo.get_user_company_relationship(
            company_id=query.company_id,
            user_id=query.user_id,
        )

        if not relationship:
            return UserCompanyRelationship(
                company_id=query.company_id,
                user_id=query.user_id,
                is_member=False,
            )

        return UserCompanyRelationship(
            company_id=query.company_id,
            user_id=query.user_id,
            is_member=relationship.is_active,
            relationship_type=relationship.relationship_type,
            joined_at=relationship.joined_at,
        )


# =============================================================================
# Telegram Query Handlers
# =============================================================================

@readonly_query(GetCompanyTelegramSupergroupsQuery)
class GetCompanyTelegramSupergroupsQueryHandler(BaseQueryHandler[GetCompanyTelegramSupergroupsQuery, List[TelegramSupergroupInfo]]):
    """Handler for getting Telegram supergroups for a company"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetCompanyTelegramSupergroupsQuery) -> List[TelegramSupergroupInfo]:
        """Get company Telegram supergroups"""
        supergroups = await CompanyReadRepo.get_company_telegram_supergroups(
            company_id=query.company_id,
        )

        return [
            TelegramSupergroupInfo(
                telegram_group_id=sg.telegram_group_id,
                title=sg.title,
                username=sg.username,
                description=sg.description,
                invite_link=sg.invite_link,
                is_forum=sg.is_forum,
                created_at=sg.created_at,
            )
            for sg in supergroups
        ]


@readonly_query(GetCompanyByTelegramGroupQuery)
class GetCompanyByTelegramGroupQueryHandler(BaseQueryHandler[GetCompanyByTelegramGroupQuery, Optional[CompanyDetail]]):
    """Handler for getting company by Telegram group ID"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetCompanyByTelegramGroupQuery) -> Optional[CompanyDetail]:
        """Get company by Telegram group"""
        company = await CompanyReadRepo.get_company_by_telegram_group(
            telegram_group_id=query.telegram_group_id,
        )

        if not company:
            return None

        return CompanyDetail(
            id=company.id,
            name=company.name,
            company_type=company.company_type,
            created_by=company.created_by,
            created_at=company.created_at,
            updated_at=company.updated_at,
            is_active=company.is_active,
            vat=company.vat,
            ogrn=company.ogrn,
            kpp=company.kpp,
            postal_code=company.postal_code,
            country_id=company.country_id,
            city=company.city,
            street=company.street,
            director=company.director,
            email=company.email,
            phone=company.phone,
            tg_dir=company.tg_dir,
            tg_accountant=company.tg_accountant,
            tg_manager_1=company.tg_manager_1,
            tg_manager_2=company.tg_manager_2,
            tg_manager_3=company.tg_manager_3,
            tg_support=company.tg_support,
            balance=company.balance,
            user_count=company.user_count,
        )


# =============================================================================
# Balance Query Handlers
# =============================================================================

@cached_query_handler(GetCompanyBalanceQuery, ttl=60)
class GetCompanyBalanceQueryHandler(BaseQueryHandler[GetCompanyBalanceQuery, BalanceInfo]):
    """Handler for getting company balance"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetCompanyBalanceQuery) -> BalanceInfo:
        """Get company balance"""
        balance = await CompanyReadRepo.get_company_balance(query.company_id)

        if balance is None:
            raise ResourceNotFoundError(f"Company not found: {query.company_id}")

        return BalanceInfo(
            company_id=query.company_id,
            balance=balance,
        )


@readonly_query(GetCompanyBalanceHistoryQuery)
class GetCompanyBalanceHistoryQueryHandler(BaseQueryHandler[GetCompanyBalanceHistoryQuery, List[BalanceTransaction]]):
    """Handler for getting company balance history"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetCompanyBalanceHistoryQuery) -> List[BalanceTransaction]:
        """Get balance transaction history"""
        transactions = await CompanyReadRepo.get_balance_history(
            company_id=query.company_id,
            limit=query.limit,
            offset=query.offset,
        )

        return [
            BalanceTransaction(
                id=t.id,
                company_id=t.company_id,
                old_balance=t.old_balance,
                new_balance=t.new_balance,
                change_amount=t.change_amount,
                reason=t.reason,
                reference_id=t.reference_id,
                updated_by=t.updated_by,
                created_at=t.created_at,
            )
            for t in transactions
        ]
