# =============================================================================
# File: app/infra/dadata/adapter.py — DaData API Adapter
# =============================================================================

import logging
from typing import Optional
import httpx

from app.config.dadata_config import get_dadata_config, is_dadata_configured
from app.infra.dadata.models import CompanyInfo, DaDataResponse

log = logging.getLogger("wellwon.infra.dadata")


class DaDataAdapter:
    """Adapter for DaData API"""

    def __init__(self):
        self._config = get_dadata_config()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._config.timeout_seconds,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Token {self._config.api_key}",
                    "X-Secret": self._config.secret_key,
                },
            )
        return self._client

    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def lookup_company_by_inn(self, inn: str) -> Optional[CompanyInfo]:
        """
        Lookup company by INN using DaData findById/party endpoint

        Args:
            inn: Company INN (10 or 12 digits)

        Returns:
            CompanyInfo if found, None otherwise
        """
        if not is_dadata_configured():
            log.error("DaData API not configured")
            return None

        if not inn or len(inn) < 10:
            log.warning(f"Invalid INN provided: {inn}")
            return None

        try:
            client = await self._get_client()

            log.debug(f"Looking up company by INN: {inn}")

            response = await client.post(
                self._config.find_by_id_url,
                json={"query": inn}
            )

            if response.status_code != 200:
                log.error(f"DaData API error: {response.status_code} {response.text}")
                return None

            data = response.json()
            dadata_response = DaDataResponse.from_api_response(data)

            if dadata_response.found:
                company = dadata_response.first
                log.info(f"Found company: {company.name_short_with_opf} (INN: {company.inn})")
                return company
            else:
                log.info(f"No company found for INN: {inn}")
                return None

        except httpx.TimeoutException:
            log.error(f"DaData API timeout for INN: {inn}")
            return None
        except Exception as e:
            log.error(f"DaData API error: {e}")
            return None

    async def lookup_company_by_ogrn(self, ogrn: str) -> Optional[CompanyInfo]:
        """
        Lookup company by OGRN using DaData findById/party endpoint

        Args:
            ogrn: Company OGRN (13 or 15 digits)

        Returns:
            CompanyInfo if found, None otherwise
        """
        if not is_dadata_configured():
            log.error("DaData API not configured")
            return None

        if not ogrn or len(ogrn) < 13:
            log.warning(f"Invalid OGRN provided: {ogrn}")
            return None

        try:
            client = await self._get_client()

            log.debug(f"Looking up company by OGRN: {ogrn}")

            response = await client.post(
                self._config.find_by_id_url,
                json={"query": ogrn}
            )

            if response.status_code != 200:
                log.error(f"DaData API error: {response.status_code} {response.text}")
                return None

            data = response.json()
            dadata_response = DaDataResponse.from_api_response(data)

            if dadata_response.found:
                company = dadata_response.first
                log.info(f"Found company: {company.name_short_with_opf} (OGRN: {company.ogrn})")
                return company
            else:
                log.info(f"No company found for OGRN: {ogrn}")
                return None

        except httpx.TimeoutException:
            log.error(f"DaData API timeout for OGRN: {ogrn}")
            return None
        except Exception as e:
            log.error(f"DaData API error: {e}")
            return None

    async def suggest_companies(self, query: str, count: int = 10) -> list[CompanyInfo]:
        """
        Search companies by name/INN/OGRN using DaData suggest endpoint

        Args:
            query: Search query (name, INN, or OGRN)
            count: Max number of results

        Returns:
            List of CompanyInfo
        """
        if not is_dadata_configured():
            log.error("DaData API not configured")
            return []

        if not query or len(query) < 3:
            return []

        try:
            client = await self._get_client()

            response = await client.post(
                self._config.suggest_party_url,
                json={"query": query, "count": count}
            )

            if response.status_code != 200:
                log.error(f"DaData API error: {response.status_code}")
                return []

            data = response.json()
            dadata_response = DaDataResponse.from_api_response(data)

            return dadata_response.suggestions

        except Exception as e:
            log.error(f"DaData suggest error: {e}")
            return []


# Singleton instance
_adapter: Optional[DaDataAdapter] = None


def get_dadata_adapter() -> DaDataAdapter:
    """Get DaData adapter (singleton)"""
    global _adapter
    if _adapter is None:
        _adapter = DaDataAdapter()
    return _adapter
