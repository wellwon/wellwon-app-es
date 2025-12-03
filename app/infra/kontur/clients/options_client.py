# =============================================================================
# File: app/infra/kontur/clients/options_client.py
# Description: Client for Kontur Options API (reference data)
# Endpoints: 7
# =============================================================================

from typing import List, Dict, Any
from app.config.logging_config import get_logger
from app.infra.kontur.clients.base_client import BaseClient
from app.infra.kontur.models import (
    OrganizationOption,
    EmployeeOption,
    CustomsOption,
    DeclarationTypeOption
)

log = get_logger("wellwon.infra.kontur.options")


class OptionsClient(BaseClient):
    """
    Client for Options API (reference/dictionary data).

    Provides access to:
    - Organizations available to current user
    - Employees for specific organization
    - Declaration types (import, export, etc.)
    - Customs procedures
    - Declaration singularities (special features)
    - Customs posts/offices
    - Common organizations list

    All endpoints cached for 1 hour (static reference data).
    """

    def __init__(self, http_client, config):
        super().__init__(http_client, config, category="options")

    async def list_organizations(self) -> List[OrganizationOption]:
        """
        List organizations available to current user.

        Returns:
            List of organizations the API key has access to
        """
        log.debug("Fetching organizations list")

        result = await self._request(
            "GET",
            "/options/organizations",
            cache_key="kontur:options:organizations",
            cache_ttl=3600  # Cache for 1 hour
        )

        if result and isinstance(result, list):
            return [OrganizationOption.model_validate(item) for item in result]
        return []

    async def list_employees(self, org_id: str) -> List[EmployeeOption]:
        """
        List employees for specific organization.

        Args:
            org_id: Organization UUID

        Returns:
            List of employees for the organization
        """
        if not org_id:
            log.warning("org_id is required for list_employees")
            return []

        log.debug(f"Fetching employees for org: {org_id}")

        result = await self._request(
            "GET",
            "/options/employees",
            params={"orgId": org_id},
            cache_key=f"kontur:options:employees:{org_id}",
            cache_ttl=3600
        )

        if result and isinstance(result, list):
            return [EmployeeOption.model_validate(item) for item in result]
        return []

    async def list_declaration_types(self) -> List[DeclarationTypeOption]:
        """
        List movement directions (declaration types).

        Returns:
            List of declaration types (import, export, transit, etc.)
        """
        log.debug("Fetching declaration types")

        result = await self._request(
            "GET",
            "/options/declarationTypes",
            cache_key="kontur:options:declaration_types",
            cache_ttl=3600
        )

        if result and isinstance(result, list):
            return [DeclarationTypeOption.model_validate(item) for item in result]
        return []

    async def list_procedures(self, declaration_type: str) -> List[Dict[str, Any]]:
        """
        List customs procedures for specific declaration type.

        Args:
            declaration_type: Declaration type code (from list_declaration_types)

        Returns:
            List of available customs procedures (e.g., 40=import for release)
        """
        if not declaration_type:
            log.warning("declaration_type is required for list_procedures")
            return []

        log.debug(f"Fetching procedures for type: {declaration_type}")

        result = await self._request(
            "GET",
            "/options/declarationProcedureTypes",
            params={"declarationType": declaration_type},
            cache_key=f"kontur:options:procedures:{declaration_type}",
            cache_ttl=3600
        )

        return result if isinstance(result, list) else []

    async def list_singularities(self, procedure: str) -> List[Dict[str, Any]]:
        """
        List declaration singularities (special features) for procedure.

        Args:
            procedure: Procedure code (from list_procedures)

        Returns:
            List of available singularities/special features
        """
        if not procedure:
            log.warning("procedure is required for list_singularities")
            return []

        log.debug(f"Fetching singularities for procedure: {procedure}")

        result = await self._request(
            "GET",
            "/options/declarationSingularities",
            params={"procedure": procedure},
            cache_key=f"kontur:options:singularities:{procedure}",
            cache_ttl=3600
        )

        return result if isinstance(result, list) else []

    async def list_customs(self) -> List[CustomsOption]:
        """
        List customs posts/offices.

        Returns:
            List of customs posts with codes and names
        """
        log.debug("Fetching customs posts")

        result = await self._request(
            "GET",
            "/options/customs",
            cache_key="kontur:options:customs",
            cache_ttl=3600
        )

        if result and isinstance(result, list):
            return [CustomsOption.model_validate(item) for item in result]
        return []

    async def list_common_orgs(self) -> List[Dict[str, Any]]:
        """
        List common organizations (contractors).

        Returns:
            List of contractor summaries
        """
        log.debug("Fetching common organizations list")

        result = await self._request(
            "GET",
            "/options/commonOrgs",
            cache_key="kontur:options:common_orgs",
            cache_ttl=3600
        )

        return result if isinstance(result, list) else []
