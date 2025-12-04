# =============================================================================
# File: app/customs/query_handlers/organization_query_handlers.py
# Description: Query handlers for CommonOrganization domain
# =============================================================================

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from app.config.logging_config import get_logger
from app.infra.cqrs.cqrs_decorators import query_handler, readonly_query, cached_query_handler
from app.common.base.base_query_handler import BaseQueryHandler
from app.customs.queries import (
    GetOrganizationQuery,
    GetOrganizationByInnQuery,
    GetOrganizationByKonturIdQuery,
    ListOrganizationsQuery,
    SearchOrganizationsQuery,
    OrganizationDetail,
    OrganizationSummary,
)
from app.infra.read_repos.customs_read_repo import CommonOrganizationReadRepo
from app.customs.exceptions import OrganizationNotFoundError

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.customs.query_handlers.organization")


# =============================================================================
# Organization Query Handlers
# =============================================================================

@cached_query_handler(GetOrganizationQuery, ttl=120)
class GetOrganizationQueryHandler(BaseQueryHandler[GetOrganizationQuery, OrganizationDetail]):
    """Handler for getting organization by ID"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetOrganizationQuery) -> OrganizationDetail:
        """Get organization details"""
        org = await CommonOrganizationReadRepo.get_organization_by_id(query.org_id)

        if not org:
            raise OrganizationNotFoundError(
                f"Organization not found: {query.org_id}"
            )

        return OrganizationDetail(
            id=org.id,
            kontur_org_id=org.kontur_org_id,
            org_name=org.org_name,
            short_name=org.short_name,
            org_type=org.org_type,
            inn=org.inn,
            kpp=org.kpp,
            ogrn=org.ogrn,
            is_foreign=org.is_foreign,
            legal_address=org.legal_address,
            actual_address=org.actual_address,
            created_at=org.created_at,
            synced_at=org.synced_at,
            is_deleted=getattr(org, 'is_deleted', False),
        )


@cached_query_handler(GetOrganizationByInnQuery, ttl=120)
class GetOrganizationByInnQueryHandler(BaseQueryHandler[GetOrganizationByInnQuery, Optional[OrganizationDetail]]):
    """Handler for getting organization by INN"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetOrganizationByInnQuery) -> Optional[OrganizationDetail]:
        """Get organization by INN"""
        org = await CommonOrganizationReadRepo.get_organization_by_inn(query.inn)

        if not org:
            return None

        return OrganizationDetail(
            id=org.id,
            kontur_org_id=org.kontur_org_id,
            org_name=org.org_name,
            short_name=org.short_name,
            org_type=org.org_type,
            inn=org.inn,
            kpp=org.kpp,
            ogrn=org.ogrn,
            is_foreign=org.is_foreign,
            legal_address=org.legal_address,
            actual_address=org.actual_address,
            created_at=org.created_at,
            synced_at=org.synced_at,
            is_deleted=getattr(org, 'is_deleted', False),
        )


@query_handler(GetOrganizationByKonturIdQuery)
class GetOrganizationByKonturIdQueryHandler(BaseQueryHandler[GetOrganizationByKonturIdQuery, Optional[OrganizationDetail]]):
    """Handler for getting organization by Kontur org ID"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetOrganizationByKonturIdQuery) -> Optional[OrganizationDetail]:
        """Get organization by Kontur org ID"""
        org = await CommonOrganizationReadRepo.get_organization_by_kontur_id(
            query.kontur_org_id
        )

        if not org:
            return None

        return OrganizationDetail(
            id=org.id,
            kontur_org_id=org.kontur_org_id,
            org_name=org.org_name,
            short_name=org.short_name,
            org_type=org.org_type,
            inn=org.inn,
            kpp=org.kpp,
            ogrn=org.ogrn,
            is_foreign=org.is_foreign,
            legal_address=org.legal_address,
            actual_address=org.actual_address,
            created_at=org.created_at,
            synced_at=org.synced_at,
            is_deleted=getattr(org, 'is_deleted', False),
        )


@readonly_query(ListOrganizationsQuery)
class ListOrganizationsQueryHandler(BaseQueryHandler[ListOrganizationsQuery, List[OrganizationSummary]]):
    """Handler for listing organizations"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: ListOrganizationsQuery) -> List[OrganizationSummary]:
        """List organizations"""
        orgs = await CommonOrganizationReadRepo.list_organizations(
            limit=query.limit,
            offset=query.offset,
        )

        return [
            OrganizationSummary(
                id=o.id,
                kontur_org_id=o.kontur_org_id,
                org_name=o.org_name,
                short_name=o.short_name,
                inn=o.inn,
                is_foreign=o.is_foreign,
            )
            for o in orgs
        ]


@readonly_query(SearchOrganizationsQuery)
class SearchOrganizationsQueryHandler(BaseQueryHandler[SearchOrganizationsQuery, List[OrganizationSummary]]):
    """Handler for searching organizations"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: SearchOrganizationsQuery) -> List[OrganizationSummary]:
        """Search organizations by name or INN"""
        orgs = await CommonOrganizationReadRepo.search_organizations(
            search_term=query.search_term,
            limit=query.limit,
        )

        return [
            OrganizationSummary(
                id=o.id,
                kontur_org_id=o.kontur_org_id,
                org_name=o.org_name,
                short_name=o.short_name,
                inn=o.inn,
                is_foreign=o.is_foreign,
            )
            for o in orgs
        ]


# =============================================================================
# EOF
# =============================================================================
