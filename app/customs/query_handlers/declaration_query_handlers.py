# =============================================================================
# File: app/customs/query_handlers/declaration_query_handlers.py
# Description: Query handlers for Customs Declaration domain
# =============================================================================

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from app.config.logging_config import get_logger
from app.infra.cqrs.cqrs_decorators import query_handler, readonly_query, cached_query_handler
from app.common.base.base_query_handler import BaseQueryHandler
from app.customs.queries import (
    GetDeclarationQuery,
    GetDeclarationSummaryQuery,
    ListDeclarationsQuery,
    ListPendingDeclarationsQuery,
    GetDeclarationByKonturIdQuery,
    SearchDeclarationsQuery,
    DeclarationDetail,
    DeclarationSummary,
    DeclarationStatus,
)
from app.infra.read_repos.customs_read_repo import CustomsDeclarationReadRepo
from app.customs.exceptions import DeclarationNotFoundError, UnauthorizedAccessError

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.customs.query_handlers.declaration")


# =============================================================================
# Declaration Query Handlers
# =============================================================================

@cached_query_handler(GetDeclarationQuery, ttl=60)
class GetDeclarationQueryHandler(BaseQueryHandler[GetDeclarationQuery, DeclarationDetail]):
    """Handler for getting full declaration by ID"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetDeclarationQuery) -> DeclarationDetail:
        """Get full declaration details with authorization check"""
        declaration = await CustomsDeclarationReadRepo.get_declaration_by_id(
            query.declaration_id
        )

        if not declaration:
            raise DeclarationNotFoundError(
                f"Declaration not found: {query.declaration_id}"
            )

        # Authorization check
        if declaration.user_id != query.user_id:
            raise UnauthorizedAccessError(
                f"User {query.user_id} not authorized to access declaration {query.declaration_id}"
            )

        return DeclarationDetail(
            id=declaration.id,
            user_id=declaration.user_id,
            company_id=declaration.company_id,
            kontur_docflow_id=declaration.kontur_docflow_id,
            gtd_number=declaration.gtd_number,
            name=declaration.name,
            declaration_type=declaration.declaration_type,
            procedure=declaration.procedure,
            customs_code=declaration.customs_code,
            status=declaration.status,
            organization_id=declaration.organization_id,
            employee_id=declaration.employee_id,
            declarant_inn=declaration.declarant_inn,
            form_data=declaration.form_data or {},
            documents=declaration.documents or [],
            created_at=declaration.created_at,
            updated_at=declaration.updated_at,
            submitted_at=declaration.submitted_at,
            is_deleted=declaration.is_deleted,
        )


@cached_query_handler(GetDeclarationSummaryQuery, ttl=60)
class GetDeclarationSummaryQueryHandler(BaseQueryHandler[GetDeclarationSummaryQuery, DeclarationSummary]):
    """Handler for getting declaration summary by ID"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetDeclarationSummaryQuery) -> DeclarationSummary:
        """Get declaration summary"""
        declaration = await CustomsDeclarationReadRepo.get_declaration_summary_by_id(
            query.declaration_id
        )

        if not declaration:
            raise DeclarationNotFoundError(
                f"Declaration not found: {query.declaration_id}"
            )

        return DeclarationSummary(
            id=declaration.id,
            name=declaration.name,
            declaration_type=declaration.declaration_type,
            procedure=declaration.procedure,
            customs_code=declaration.customs_code,
            status=declaration.status,
            gtd_number=declaration.gtd_number,
            organization_id=declaration.organization_id,
            created_at=declaration.created_at,
            submitted_at=declaration.submitted_at,
            is_deleted=declaration.is_deleted,
        )


@readonly_query(ListDeclarationsQuery)
class ListDeclarationsQueryHandler(BaseQueryHandler[ListDeclarationsQuery, List[DeclarationSummary]]):
    """Handler for listing declarations with filters"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: ListDeclarationsQuery) -> List[DeclarationSummary]:
        """List declarations for user"""
        status_value = query.status.value if query.status else None

        declarations = await CustomsDeclarationReadRepo.list_declarations(
            user_id=query.user_id,
            company_id=query.company_id,
            status=status_value,
            limit=query.limit,
            offset=query.offset,
        )

        return [
            DeclarationSummary(
                id=d.id,
                name=d.name,
                declaration_type=d.declaration_type,
                procedure=d.procedure,
                customs_code=d.customs_code,
                status=d.status,
                gtd_number=d.gtd_number,
                organization_id=d.organization_id,
                created_at=d.created_at,
                submitted_at=d.submitted_at,
                is_deleted=d.is_deleted,
            )
            for d in declarations
        ]


@readonly_query(ListPendingDeclarationsQuery)
class ListPendingDeclarationsQueryHandler(BaseQueryHandler[ListPendingDeclarationsQuery, List[DeclarationStatus]]):
    """Handler for listing pending declarations for sync worker"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: ListPendingDeclarationsQuery) -> List[DeclarationStatus]:
        """List pending declarations for Kontur sync"""
        status_values = [s.value for s in query.status_list]

        declarations = await CustomsDeclarationReadRepo.list_pending_declarations(
            status_list=status_values,
            has_kontur_docflow_id=query.has_kontur_docflow_id,
            limit=query.limit,
        )

        return [
            DeclarationStatus(
                id=d.id,
                name=d.name,
                status=d.status,
                kontur_docflow_id=d.kontur_docflow_id,
                gtd_number=d.gtd_number,
                submitted_at=d.submitted_at,
                updated_at=d.updated_at,
            )
            for d in declarations
        ]


@query_handler(GetDeclarationByKonturIdQuery)
class GetDeclarationByKonturIdQueryHandler(BaseQueryHandler[GetDeclarationByKonturIdQuery, Optional[DeclarationDetail]]):
    """Handler for getting declaration by Kontur docflow ID"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetDeclarationByKonturIdQuery) -> Optional[DeclarationDetail]:
        """Get declaration by Kontur docflow ID"""
        declaration = await CustomsDeclarationReadRepo.get_declaration_by_kontur_docflow_id(
            query.kontur_docflow_id
        )

        if not declaration:
            return None

        return DeclarationDetail(
            id=declaration.id,
            user_id=declaration.user_id,
            company_id=declaration.company_id,
            kontur_docflow_id=declaration.kontur_docflow_id,
            gtd_number=declaration.gtd_number,
            name=declaration.name,
            declaration_type=declaration.declaration_type,
            procedure=declaration.procedure,
            customs_code=declaration.customs_code,
            status=declaration.status,
            organization_id=declaration.organization_id,
            employee_id=declaration.employee_id,
            declarant_inn=declaration.declarant_inn,
            form_data=declaration.form_data or {},
            documents=declaration.documents or [],
            created_at=declaration.created_at,
            updated_at=declaration.updated_at,
            submitted_at=declaration.submitted_at,
            is_deleted=declaration.is_deleted,
        )


# =============================================================================
# EOF
# =============================================================================
