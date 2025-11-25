# =============================================================================
# File: app/company/query_handlers/__init__.py
# Description: Company query handlers package
# =============================================================================

from app.company.query_handlers.company_query_handlers import (
    # Company queries
    GetCompanyByIdQueryHandler,
    GetCompaniesQueryHandler,
    GetCompaniesByUserQueryHandler,
    SearchCompaniesQueryHandler,
    GetCompanyByVatQueryHandler,
    # User-company queries
    GetCompanyUsersQueryHandler,
    GetUserCompanyRelationshipQueryHandler,
    # Telegram queries
    GetCompanyTelegramSupergroupsQueryHandler,
    GetCompanyByTelegramGroupQueryHandler,
    # Balance queries
    GetCompanyBalanceQueryHandler,
    GetCompanyBalanceHistoryQueryHandler,
)

__all__ = [
    # Company queries
    "GetCompanyByIdQueryHandler",
    "GetCompaniesQueryHandler",
    "GetCompaniesByUserQueryHandler",
    "SearchCompaniesQueryHandler",
    "GetCompanyByVatQueryHandler",
    # User-company queries
    "GetCompanyUsersQueryHandler",
    "GetUserCompanyRelationshipQueryHandler",
    # Telegram queries
    "GetCompanyTelegramSupergroupsQueryHandler",
    "GetCompanyByTelegramGroupQueryHandler",
    # Balance queries
    "GetCompanyBalanceQueryHandler",
    "GetCompanyBalanceHistoryQueryHandler",
]
