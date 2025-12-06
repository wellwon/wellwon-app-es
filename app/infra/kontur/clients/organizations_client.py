# =============================================================================
# File: app/infra/kontur/clients/organizations_client.py
# Description: Client for Kontur CommonOrgs API (contractor management)
# Endpoints: 2
# =============================================================================

from typing import Optional
from app.config.logging_config import get_logger
from app.infra.kontur.clients.base_client import BaseClient
from app.infra.kontur.models import CommonOrg

log = get_logger("wellwon.infra.kontur.organizations")


class OrganizationsClient(BaseClient):
    """
    Client for CommonOrgs API (contractor management).

    Endpoints:
    - POST /commonOrganizations - Create or update contractor
    - POST /getOrCreateCommonOrgByInn - Get or create by INN (Russian tax ID)
    """

    def __init__(self, http_client, config, session_refresh_callback=None):
        super().__init__(http_client, config, category="organizations", session_refresh_callback=session_refresh_callback)

    async def create_or_update(self, org: CommonOrg) -> Optional[CommonOrg]:
        """
        Create or update organization.

        If organization with same orgName exists, it updates; otherwise creates new.

        Args:
            org: CommonOrg model with organization data

        Returns:
            Created/updated CommonOrg with ID, or None on error
        """
        if not org.org_name:
            log.warning("Cannot create organization without org_name")
            return None

        log.info(f"Creating/updating organization: {org.org_name}")

        result = await self._request(
            "POST",
            "/commonOrganizations",
            json=org.model_dump(by_alias=True, exclude_none=True)
        )

        if result:
            return CommonOrg.model_validate(result)
        return None

    async def get_or_create_by_inn(self, inn: str) -> Optional[CommonOrg]:
        """
        Get or create organization by Russian INN (tax ID).

        Uses Kontur.Focus integration to automatically fetch company data
        from Russian business registries.

        Args:
            inn: Russian INN (10 or 12 digits)

        Returns:
            CommonOrg with company data, or None on error

        Note:
            - Cached for 1 hour to avoid repeated lookups
            - Only works for Russian companies
            - Automatically fills: name, address, registration data
        """
        if not inn or len(inn) < 10:
            log.warning(f"Invalid INN: {inn}")
            return None

        log.info(f"Looking up organization by INN: {inn}")

        result = await self._request(
            "POST",
            "/getOrCreateCommonOrgByInn",
            params={"inn": inn},
            cache_key=f"kontur:org:inn:{inn}",
            cache_ttl=3600  # Cache for 1 hour
        )

        if result:
            return CommonOrg.model_validate(result)
        return None
