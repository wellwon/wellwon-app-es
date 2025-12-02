# =============================================================================
# File: app/declarant/kontur_client.py
# Description: HTTP client for Kontur.Declarant API
# =============================================================================

from __future__ import annotations

import os
import logging
from typing import Optional
from urllib.parse import quote

import httpx

log = logging.getLogger("wellwon.declarant.kontur_client")


class KonturClientError(Exception):
    """Base exception for Kontur API errors"""
    pass


class KonturAuthError(KonturClientError):
    """Authentication error"""
    pass


class KonturClient:
    """
    HTTP client for Kontur.Declarant API

    Environment variables:
        KONTUR_API_BASE_URL: Base URL (default: https://api-d.kontur.ru)
        KONTUR_API_LOGIN: Login email
        KONTUR_API_PASSWORD: Password
        KONTUR_API_KEY: API key (X-Kontur-ApiKey header)
        KONTUR_API_SID: Session ID (can be refreshed via authenticate)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        login: Optional[str] = None,
        password: Optional[str] = None,
        sid: Optional[str] = None,
    ):
        self.base_url = base_url or os.getenv("KONTUR_API_BASE_URL", "https://api-d.kontur.ru")
        self.api_key = api_key or os.getenv("KONTUR_API_KEY")
        self.login = login or os.getenv("KONTUR_API_LOGIN")
        self.password = password or os.getenv("KONTUR_API_PASSWORD")
        self._sid = sid or os.getenv("KONTUR_API_SID")

        if not self.api_key:
            raise KonturClientError("KONTUR_API_KEY is required")

    @property
    def sid(self) -> Optional[str]:
        """Get current session ID"""
        return self._sid

    def _get_headers(self, include_auth: bool = True) -> dict:
        """Build request headers"""
        headers = {
            "X-Kontur-ApiKey": self.api_key,
        }
        if include_auth and self._sid:
            headers["Authorization"] = self._sid
        return headers

    async def authenticate(self) -> str:
        """
        Authenticate and get new SessionID (sid)

        Returns:
            str: SessionID for use in subsequent requests

        Raises:
            KonturAuthError: If authentication fails
        """
        if not self.login or not self.password:
            raise KonturAuthError("KONTUR_API_LOGIN and KONTUR_API_PASSWORD are required for authentication")

        # URL-encode the login (email)
        encoded_login = quote(self.login, safe='')
        url = f"{self.base_url}/auth/v1/authenticate?login={encoded_login}&pass={self.password}"

        log.info(f"Authenticating with Kontur API as {self.login}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers={"X-Kontur-ApiKey": self.api_key}
            )

            if response.status_code == 403:
                raise KonturAuthError("Authentication failed: Invalid credentials or API key")

            response.raise_for_status()

            # Response is plain text SID
            self._sid = response.text.strip()
            log.info("Successfully authenticated with Kontur API")

            return self._sid

    async def ensure_authenticated(self) -> None:
        """Ensure we have a valid SID, authenticate if needed"""
        if not self._sid:
            await self.authenticate()

    async def get_document_types(self) -> list[dict]:
        """
        Get list of document types (JSON templates)

        Endpoint: GET /common/v1/jsonTemplates

        Returns:
            list[dict]: List of document types with id, documentModeId, typeName

        Example response:
            [
                {"id": "10BS110E", "documentModeId": "10BS110E", "typeName": "FreeDoc"},
                ...
            ]
        """
        await self.ensure_authenticated()

        url = f"{self.base_url}/common/v1/jsonTemplates"

        log.info("Fetching document types from Kontur API")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                headers=self._get_headers()
            )

            if response.status_code == 401:
                # Try to re-authenticate
                log.warning("Session expired, re-authenticating...")
                await self.authenticate()
                response = await client.get(
                    url,
                    headers=self._get_headers()
                )

            response.raise_for_status()

            data = response.json()
            log.info(f"Fetched {len(data)} document types from Kontur API")

            return data

    async def get_document_template(self, document_mode_id: str) -> str:
        """
        Get JSON template for a specific document type

        Endpoint: GET /common/v1/jsonTemplates/{documentModeId}

        Args:
            document_mode_id: The document mode ID (e.g., "10BS110E")

        Returns:
            str: JSON template as string
        """
        await self.ensure_authenticated()

        url = f"{self.base_url}/common/v1/jsonTemplates/{document_mode_id}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                headers=self._get_headers()
            )

            if response.status_code == 401:
                await self.authenticate()
                response = await client.get(
                    url,
                    headers=self._get_headers()
                )

            response.raise_for_status()

            return response.text

    # =========================================================================
    # References API (Options)
    # =========================================================================

    async def get_customs(self) -> list[dict]:
        """
        Get list of customs offices (таможенные органы)

        Endpoint: GET /common/v1/options/customs

        Returns:
            list[dict]: List of customs offices with id, shortName, name

        Example response:
            [
                {"id": "uuid", "shortName": "ЦЭД", "name": "Центральная электронная таможня"},
                ...
            ]
        """
        await self.ensure_authenticated()

        url = f"{self.base_url}/common/v1/options/customs"

        log.info("Fetching customs offices from Kontur API")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                headers=self._get_headers()
            )

            if response.status_code == 401:
                log.warning("Session expired, re-authenticating...")
                await self.authenticate()
                response = await client.get(
                    url,
                    headers=self._get_headers()
                )

            response.raise_for_status()

            data = response.json()
            log.info(f"Fetched {len(data)} customs offices from Kontur API")

            return data

    async def get_declaration_types(self) -> list[dict]:
        """
        Get list of declaration types (направления перемещения)

        Endpoint: GET /common/v1/options/declarationTypes

        Returns:
            list[dict]: List of declaration types with id, description

        Example response:
            [
                {"id": 0, "description": "ИМ"},
                {"id": 1, "description": "ЭК"},
                ...
            ]
        """
        await self.ensure_authenticated()

        url = f"{self.base_url}/common/v1/options/declarationTypes"

        log.info("Fetching declaration types from Kontur API")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                headers=self._get_headers()
            )

            if response.status_code == 401:
                log.warning("Session expired, re-authenticating...")
                await self.authenticate()
                response = await client.get(
                    url,
                    headers=self._get_headers()
                )

            response.raise_for_status()

            data = response.json()
            log.info(f"Fetched {len(data)} declaration types from Kontur API")

            return data

    async def get_declaration_procedures(self, declaration_type: int) -> list[dict]:
        """
        Get list of customs procedures for a specific declaration type

        Endpoint: GET /common/v1/options/declarationProcedureTypes?declarationType={type}

        Args:
            declaration_type: Declaration type ID (0=ИМ, 1=ЭК, etc.)

        Returns:
            list[dict]: List of procedures with id, code, name

        Example response:
            [
                {"id": 0, "code": "40", "name": "Выпуск для внутреннего потребления"},
                {"id": 1, "code": "10", "name": "Экспорт"},
                ...
            ]
        """
        await self.ensure_authenticated()

        url = f"{self.base_url}/common/v1/options/declarationProcedureTypes?declarationType={declaration_type}"

        log.info(f"Fetching procedures for declaration type {declaration_type} from Kontur API")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                headers=self._get_headers()
            )

            if response.status_code == 401:
                log.warning("Session expired, re-authenticating...")
                await self.authenticate()
                response = await client.get(
                    url,
                    headers=self._get_headers()
                )

            response.raise_for_status()

            data = response.json()
            log.info(f"Fetched {len(data)} procedures for type {declaration_type} from Kontur API")

            return data

    async def get_declaration_singularities(self, declaration_type: Optional[int] = None) -> list[dict]:
        """
        Get list of declaration singularities (особенности декларирования)

        Endpoint: GET /common/v1/options/declarationSingularities

        Args:
            declaration_type: Optional declaration type filter (0=ИМ, 1=ЭК, etc.)

        Returns:
            list[dict]: List of singularities with id, shortName, name

        Example response:
            [
                {"id": 0, "shortName": "ПТД", "name": "Предварительное декларирование"},
                {"id": 1, "shortName": "ПКТ", "name": "Предварительное декларирование (компонент)"},
                ...
            ]
        """
        await self.ensure_authenticated()

        url = f"{self.base_url}/common/v1/options/declarationSingularities"
        if declaration_type is not None:
            url += f"?declarationType={declaration_type}"

        log.info("Fetching declaration singularities from Kontur API")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                headers=self._get_headers()
            )

            if response.status_code == 401:
                log.warning("Session expired, re-authenticating...")
                await self.authenticate()
                response = await client.get(
                    url,
                    headers=self._get_headers()
                )

            response.raise_for_status()

            data = response.json()
            log.info(f"Fetched {len(data)} declaration singularities from Kontur API")

            return data

    async def get_common_orgs(self) -> list[dict]:
        """
        Get list of counterparties (контрагенты)

        Endpoint: GET /common/v1/options/commonOrgs

        Returns:
            list[dict]: List of counterparties (CommonOrg structure)

        Example response:
            [
                {
                    "id": "uuid",
                    "orgName": "ООО РОМАШКА",
                    "shortName": "РОМАШКА",
                    "type": 0,
                    "inn": "7719483568",
                    "kpp": "111111111",
                    "ogrn": "1187746252821",
                    "isForeign": false,
                    "legalAddress": {...},
                    ...
                }
            ]
        """
        await self.ensure_authenticated()

        url = f"{self.base_url}/common/v1/options/commonOrgs"

        log.info("Fetching counterparties from Kontur API")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                headers=self._get_headers()
            )

            if response.status_code == 401:
                log.warning("Session expired, re-authenticating...")
                await self.authenticate()
                response = await client.get(
                    url,
                    headers=self._get_headers()
                )

            response.raise_for_status()

            data = response.json()
            log.info(f"Fetched {len(data)} counterparties from Kontur API")

            return data

    async def get_organizations(self) -> list[dict]:
        """
        Get list of organizations (свои организации)

        Endpoint: GET /common/v1/options/organizations

        Returns:
            list[dict]: List of own organizations

        Example response:
            [
                {
                    "id": "uuid",
                    "participationIds": "string",
                    "name": "ООО КОМПАНИЯ",
                    "inn": "1234567890",
                    "kpp": "123456789",
                    "ogrn": "1234567890123",
                    "okpo": "12345678",
                    "okato": "12345678901",
                    "oktmo": "12345678",
                    "address": {...}
                }
            ]
        """
        await self.ensure_authenticated()

        url = f"{self.base_url}/common/v1/options/organizations"

        log.info("Fetching organizations from Kontur API")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                headers=self._get_headers()
            )

            if response.status_code == 401:
                log.warning("Session expired, re-authenticating...")
                await self.authenticate()
                response = await client.get(
                    url,
                    headers=self._get_headers()
                )

            response.raise_for_status()

            data = response.json()
            log.info(f"Fetched {len(data)} organizations from Kontur API")

            return data

    async def get_employees(self, org_id: str) -> list[dict]:
        """
        Get list of employees (signers) for an organization

        Endpoint: GET /common/v1/options/employees?orgId={orgId}

        Args:
            org_id: Organization UUID

        Returns:
            list[dict]: List of employees/signers

        Example response:
            [
                {
                    "id": "uuid",
                    "surname": "Иванов",
                    "name": "Иван",
                    "patronymic": "Иванович",
                    "phone": "+7...",
                    "email": "email@example.com",
                    "passportOrganization": "...",
                    "passportDate": "2020-01-01",
                    "passportNumber": "...",
                    "identity": 0,
                    "authLetterDate": "2024-01-01",
                    "authLetterNumber": "123"
                }
            ]
        """
        await self.ensure_authenticated()

        url = f"{self.base_url}/common/v1/options/employees?orgId={org_id}"

        log.info(f"Fetching employees for organization {org_id} from Kontur API")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                headers=self._get_headers()
            )

            if response.status_code == 401:
                log.warning("Session expired, re-authenticating...")
                await self.authenticate()
                response = await client.get(
                    url,
                    headers=self._get_headers()
                )

            if response.status_code == 400:
                log.warning("Bad request: Organization ID may be invalid")
                return []

            response.raise_for_status()

            data = response.json()
            log.info(f"Fetched {len(data)} employees for organization {org_id} from Kontur API")

            return data

    # =========================================================================
    # Docflow API (документооборот)
    # =========================================================================

    async def create_docflow(
        self,
        declaration_type: int,
        procedure: int,
        customs: int,
        organization_id: str,
        employee_id: str,
        singularity: Optional[int] = None,
        name: Optional[str] = None
    ) -> dict:
        """
        Create new docflow (документооборот / пакет декларации)

        Endpoint: POST /common/v1/docflows

        Args:
            declaration_type: Declaration type (0=ИМ, 1=ЭК, etc.)
            procedure: Customs procedure ID
            customs: Customs office code (e.g., 10130010)
            organization_id: Organization UUID
            employee_id: Employee (signer) UUID
            singularity: Optional singularity ID
            name: Optional docflow name

        Returns:
            dict: Created docflow data (DocflowDto)

        Example response:
            {
                "id": "uuid",
                "version": 1,
                "state": 0,
                "type": 0,
                "procedure": 0,
                "singularity": 0,
                "customs": 10130010,
                "name": "Docflow name",
                "organizationId": "uuid",
                "employeeId": "uuid",
                "createDate": "2024-01-01T00:00:00Z",
                "updateDate": "2024-01-01T00:00:00Z"
            }
        """
        await self.ensure_authenticated()

        url = f"{self.base_url}/common/v1/docflows"

        # Build request body
        body = {
            "type": declaration_type,
            "procedure": procedure,
            "customs": customs,
            "organizationId": organization_id,
            "employeeId": employee_id,
        }

        if singularity is not None:
            body["singularity"] = singularity

        if name:
            body["name"] = name

        log.info(f"Creating docflow: type={declaration_type}, procedure={procedure}, customs={customs}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers=self._get_headers(),
                json=body
            )

            # Handle expired session (401 or 403)
            if response.status_code in (401, 403):
                log.warning(f"Session expired ({response.status_code}), re-authenticating...")
                await self.authenticate()
                response = await client.post(
                    url,
                    headers=self._get_headers(),
                    json=body
                )

            response.raise_for_status()

            data = response.json()
            log.info(f"Successfully created docflow with ID: {data.get('id')}")

            return data

    async def get_form_json(self, docflow_id: str, form_id: str) -> dict:
        """
        Get JSON content of a document form

        Endpoint: GET /common/v1/docflows/{docflowId}/form/{formId}/json

        Args:
            docflow_id: UUID of the docflow
            form_id: UUID of the form

        Returns:
            dict: JSON content of the document
        """
        await self.ensure_authenticated()

        url = f"{self.base_url}/common/v1/docflows/{docflow_id}/form/{form_id}/json"

        log.info(f"Fetching form JSON: docflow={docflow_id}, form={form_id}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, headers=self._get_headers())

            if response.status_code == 401:
                log.warning("Session expired, re-authenticating...")
                await self.authenticate()
                response = await client.get(url, headers=self._get_headers())

            response.raise_for_status()

            data = response.json()
            log.info(f"Successfully fetched form JSON")

            return data


# Singleton instance for convenience
_client: Optional[KonturClient] = None


def get_kontur_client() -> KonturClient:
    """Get or create singleton KonturClient instance"""
    global _client
    if _client is None:
        _client = KonturClient()
    return _client
