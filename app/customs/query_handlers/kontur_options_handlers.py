# =============================================================================
# File: app/customs/query_handlers/kontur_options_handlers.py
# Description: Query handlers for Kontur API reference data (organizations,
#              employees, customs offices, procedures, declaration types)
# =============================================================================

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from app.config.logging_config import get_logger
from app.infra.cqrs.cqrs_decorators import query_handler, cached_query_handler
from app.common.base.base_query_handler import BaseQueryHandler
from app.customs.queries import (
    GetKonturOrganizationsQuery,
    GetKonturEmployeesQuery,
    GetKonturDeclarationTypesQuery,
    GetCustomsProceduresQuery,
    GetCustomsOfficesQuery,
)
from app.customs.exceptions import KonturServiceUnavailableError

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies
    from app.customs.ports.kontur_declarant_port import KonturDeclarantPort

log = get_logger("wellwon.customs.query_handlers.kontur_options")


# =============================================================================
# Result Types (lightweight for API responses)
# =============================================================================

from pydantic import BaseModel


class KonturOrganization(BaseModel):
    """Kontur organization option"""
    id: str
    name: str
    inn: Optional[str] = None


class KonturEmployee(BaseModel):
    """Kontur employee option"""
    id: str
    name: str
    position: Optional[str] = None


class KonturDeclarationType(BaseModel):
    """Kontur declaration type option"""
    code: str
    name: str


class KonturProcedure(BaseModel):
    """Kontur procedure option"""
    code: str
    name: str
    description: Optional[str] = None


class KonturCustomsOffice(BaseModel):
    """Kontur customs office option"""
    code: str
    name: str


# =============================================================================
# Query Handlers
# =============================================================================

@cached_query_handler(GetKonturOrganizationsQuery, ttl=300)
class GetKonturOrganizationsQueryHandler(BaseQueryHandler[GetKonturOrganizationsQuery, List[KonturOrganization]]):
    """
    Handler for fetching organizations from Kontur API.

    Cached for 5 minutes as organization list rarely changes.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        # Port injection: kontur_adapter implements KonturDeclarantPort
        self._kontur: 'KonturDeclarantPort' = deps.kontur_adapter

    async def handle(self, query: GetKonturOrganizationsQuery) -> List[KonturOrganization]:
        """Fetch organizations from Kontur via port"""
        if not self._kontur:
            raise KonturServiceUnavailableError("Kontur adapter not configured")

        try:
            orgs = await self._kontur.list_organizations()

            if not orgs:
                return []

            return [
                KonturOrganization(
                    id=org.id,
                    name=org.name,
                    inn=getattr(org, 'inn', None),
                )
                for org in orgs
            ]
        except Exception as e:
            log.error(f"Failed to fetch organizations from Kontur: {e}")
            raise KonturServiceUnavailableError(f"Failed to fetch organizations: {e}") from e


@cached_query_handler(GetKonturEmployeesQuery, ttl=300)
class GetKonturEmployeesQueryHandler(BaseQueryHandler[GetKonturEmployeesQuery, List[KonturEmployee]]):
    """
    Handler for fetching employees for organization from Kontur API.

    Cached for 5 minutes per organization.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        # Port injection: kontur_adapter implements KonturDeclarantPort
        self._kontur: 'KonturDeclarantPort' = deps.kontur_adapter

    async def handle(self, query: GetKonturEmployeesQuery) -> List[KonturEmployee]:
        """Fetch employees for organization from Kontur via port"""
        if not self._kontur:
            raise KonturServiceUnavailableError("Kontur adapter not configured")

        try:
            employees = await self._kontur.list_employees(
                query.organization_id
            )

            if not employees:
                return []

            return [
                KonturEmployee(
                    id=emp.id,
                    name=emp.name,
                    position=getattr(emp, 'position', None),
                )
                for emp in employees
            ]
        except Exception as e:
            log.error(f"Failed to fetch employees from Kontur: {e}")
            raise KonturServiceUnavailableError(f"Failed to fetch employees: {e}") from e


@cached_query_handler(GetKonturDeclarationTypesQuery, ttl=3600)
class GetKonturDeclarationTypesQueryHandler(BaseQueryHandler[GetKonturDeclarationTypesQuery, List[KonturDeclarationType]]):
    """
    Handler for fetching declaration types from Kontur API.

    Cached for 1 hour as declaration types are static reference data.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        # Port injection: kontur_adapter implements KonturDeclarantPort
        self._kontur: 'KonturDeclarantPort' = deps.kontur_adapter

    async def handle(self, query: GetKonturDeclarationTypesQuery) -> List[KonturDeclarationType]:
        """Fetch declaration types from Kontur via port"""
        if not self._kontur:
            raise KonturServiceUnavailableError("Kontur adapter not configured")

        try:
            types = await self._kontur.list_declaration_types()

            if not types:
                return []

            return [
                KonturDeclarationType(
                    code=t.code,
                    name=t.name,
                )
                for t in types
            ]
        except Exception as e:
            log.error(f"Failed to fetch declaration types from Kontur: {e}")
            raise KonturServiceUnavailableError(f"Failed to fetch declaration types: {e}") from e


@cached_query_handler(GetCustomsProceduresQuery, ttl=3600)
class GetCustomsProceduresQueryHandler(BaseQueryHandler[GetCustomsProceduresQuery, List[KonturProcedure]]):
    """
    Handler for fetching customs procedures from Kontur API.

    Cached for 1 hour as procedures are static reference data.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        # Port injection: kontur_adapter implements KonturDeclarantPort
        self._kontur: 'KonturDeclarantPort' = deps.kontur_adapter

    async def handle(self, query: GetCustomsProceduresQuery) -> List[KonturProcedure]:
        """Fetch procedures from Kontur via port"""
        if not self._kontur:
            raise KonturServiceUnavailableError("Kontur adapter not configured")

        try:
            declaration_type = query.declaration_type.value if query.declaration_type else None
            procedures = await self._kontur.list_procedures(
                declaration_type=declaration_type
            )

            if not procedures:
                return []

            return [
                KonturProcedure(
                    code=p.code,
                    name=p.name,
                    description=getattr(p, 'description', None),
                )
                for p in procedures
            ]
        except Exception as e:
            log.error(f"Failed to fetch procedures from Kontur: {e}")
            raise KonturServiceUnavailableError(f"Failed to fetch procedures: {e}") from e


@cached_query_handler(GetCustomsOfficesQuery, ttl=3600)
class GetCustomsOfficesQueryHandler(BaseQueryHandler[GetCustomsOfficesQuery, List[KonturCustomsOffice]]):
    """
    Handler for fetching customs offices from Kontur API.

    Cached for 1 hour as customs offices are static reference data.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        # Port injection: kontur_adapter implements KonturDeclarantPort
        self._kontur: 'KonturDeclarantPort' = deps.kontur_adapter

    async def handle(self, query: GetCustomsOfficesQuery) -> List[KonturCustomsOffice]:
        """Fetch customs offices from Kontur via port"""
        if not self._kontur:
            raise KonturServiceUnavailableError("Kontur adapter not configured")

        try:
            customs = await self._kontur.list_customs(
                country_code=query.country_code
            )

            if not customs:
                return []

            return [
                KonturCustomsOffice(
                    code=c.code,
                    name=c.name,
                )
                for c in customs
            ]
        except Exception as e:
            log.error(f"Failed to fetch customs offices from Kontur: {e}")
            raise KonturServiceUnavailableError(f"Failed to fetch customs offices: {e}") from e


# =============================================================================
# EOF
# =============================================================================