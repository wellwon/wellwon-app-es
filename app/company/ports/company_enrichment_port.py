# =============================================================================
# File: app/company/ports/company_enrichment_port.py
# Description: Port interface for company data enrichment operations
# Pattern: Hexagonal Architecture / Ports & Adapters
# =============================================================================

from __future__ import annotations

from typing import Protocol, Optional, List, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.infra.dadata.models import CompanyInfo


@runtime_checkable
class CompanyEnrichmentPort(Protocol):
    """
    Port: Company Data Enrichment

    Defined by: Company Domain
    Implemented by: DaDataAdapter (app/infra/dadata/adapter.py)

    This port defines the contract for company data enrichment operations.
    Used to lookup and autocomplete company information from Russian
    business registries (EGRUL/EGRIP) via DaData API.

    Categories:
    - Lookup by identifiers (2 methods)
    - Search/autocomplete (1 method)

    Total: 3 methods
    """

    # =========================================================================
    # Lookup by Identifiers (2 methods)
    # =========================================================================

    async def lookup_company_by_inn(
        self,
        inn: str
    ) -> Optional['CompanyInfo']:
        """
        Lookup company by Russian INN (tax identification number).

        Uses DaData findById/party endpoint to find exact match.

        Args:
            inn: Company INN (10 digits for legal entities, 12 for individuals)

        Returns:
            CompanyInfo with full company details if found, None otherwise.
            CompanyInfo includes:
            - name_full, name_short, name_short_with_opf
            - inn, kpp, ogrn
            - address details
            - status (ACTIVE, LIQUIDATING, etc.)
            - management info
            - and more
        """
        ...

    async def lookup_company_by_ogrn(
        self,
        ogrn: str
    ) -> Optional['CompanyInfo']:
        """
        Lookup company by Russian OGRN (registration number).

        Uses DaData findById/party endpoint to find exact match.

        Args:
            ogrn: Company OGRN (13 digits for legal entities, 15 for individuals)

        Returns:
            CompanyInfo with full company details if found, None otherwise.
        """
        ...

    # =========================================================================
    # Search/Autocomplete (1 method)
    # =========================================================================

    async def suggest_companies(
        self,
        query: str,
        count: int = 10
    ) -> List['CompanyInfo']:
        """
        Search companies by name, INN, or OGRN (autocomplete).

        Uses DaData suggest/party endpoint for fuzzy search.
        Supports partial matches and typo tolerance.

        Args:
            query: Search query (company name, INN, or OGRN)
                   Minimum 3 characters required
            count: Maximum number of results to return

        Returns:
            List of CompanyInfo matching the query.
            Empty list if no matches or query too short.
        """
        ...


# =============================================================================
# EOF
# =============================================================================
