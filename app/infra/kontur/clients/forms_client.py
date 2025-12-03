# =============================================================================
# File: app/infra/kontur/clients/forms_client.py
# Description: Client for Kontur Forms API (declaration forms and data import)
# Endpoints: 6
# =============================================================================

from typing import Dict, List, Optional, Any
from app.config.logging_config import get_logger
from app.infra.kontur.clients.base_client import BaseClient

log = get_logger("wellwon.infra.kontur.forms")


class FormsClient(BaseClient):
    """
    Client for Forms API (declaration form filling and import).

    Forms = specific declaration types (DT, CMR, Invoice, etc.)

    Core operations:
    - Get/update form JSON data
    - Import goods data in bulk
    - Upload form files (Excel, XML, etc.)
    - Export form to XML
    - Set contractors from CommonOrgs
    """

    def __init__(self, http_client, config):
        super().__init__(http_client, config, category="forms")

    async def get_form_json(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get form data as JSON.

        Args:
            docflow_id: Docflow UUID
            form_id: Form ID (e.g., "dt", "cmr", "invoice")

        Returns:
            Form data as JSON dictionary, or None if not found
        """
        if not docflow_id or not form_id:
            log.warning("docflow_id and form_id are required for get_form_json")
            return None

        log.debug(f"Getting JSON for form {form_id} in docflow {docflow_id}")

        result = await self._request(
            "GET",
            f"/docflows/{docflow_id}/form/{form_id}/json"
        )

        return result if isinstance(result, dict) else None

    async def import_json(
        self,
        docflow_id: str,
        form_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Import form data from JSON.

        Updates form fields with provided data. Partial updates supported.

        Args:
            docflow_id: Docflow UUID
            form_id: Form ID
            data: JSON data to import (field name → value mapping)

        Returns:
            True if successful, False otherwise
        """
        if not docflow_id or not form_id:
            log.warning("docflow_id and form_id are required for import_json")
            return False

        if not data:
            log.warning("data is required for import_json")
            return False

        log.info(f"Importing JSON data to form {form_id} in docflow {docflow_id}")

        await self._request(
            "POST",
            f"/docflows/{docflow_id}/form/{form_id}/importJson",
            json=data
        )

        return True

    async def import_goods(
        self,
        docflow_id: str,
        form_id: str,
        goods: List[Dict[str, Any]],
        clear_before: bool = False,
        preserve_attached: bool = False
    ) -> bool:
        """
        Import goods data in bulk.

        Allows importing multiple goods with all their fields at once.
        Commonly used for:
        - Importing from Excel templates
        - Copying from previous declarations
        - Batch data entry

        Args:
            docflow_id: Docflow UUID
            form_id: Form ID (usually "dt" for customs declaration)
            goods: List of goods with field data
            clear_before: Clear existing goods before import
            preserve_attached: Keep documents attached to goods when clearing

        Returns:
            True if successful, False otherwise
        """
        if not docflow_id or not form_id:
            log.warning("docflow_id and form_id are required for import_goods")
            return False

        if not goods:
            log.warning("goods list is required for import_goods")
            return False

        log.info(f"Importing {len(goods)} goods to form {form_id} in docflow {docflow_id}")

        await self._request(
            "POST",
            f"/docflows/{docflow_id}/form/{form_id}/import",
            json={
                "goods": goods,
                "clearBefore": clear_before,
                "preserveAttached": preserve_attached
            }
        )

        return True

    async def upload_file(
        self,
        docflow_id: str,
        form_id: str,
        file_bytes: bytes,
        filename: str
    ) -> bool:
        """
        Upload form file (Excel, XML, etc.).

        Kontur can parse uploaded files and auto-fill declaration fields.
        Supported formats: Excel (.xlsx), XML, CSV.

        Args:
            docflow_id: Docflow UUID
            form_id: Form ID
            file_bytes: File content as bytes
            filename: Original filename (with extension)

        Returns:
            True if successful, False otherwise
        """
        if not docflow_id or not form_id:
            log.warning("docflow_id and form_id are required for upload_file")
            return False

        if not file_bytes or not filename:
            log.warning("file_bytes and filename are required for upload_file")
            return False

        # Security: Enforce 50MB file size limit to prevent DOS attacks
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
        file_size = len(file_bytes)
        if file_size > MAX_FILE_SIZE:
            log.error(f"File too large: {file_size} bytes (max {MAX_FILE_SIZE} bytes)")
            return False

        log.info(f"Uploading file {filename} ({file_size} bytes) to form {form_id} in docflow {docflow_id}")

        # Create multipart form data
        files_dict = {
            "file": (filename, file_bytes)
        }

        # Use _request with reliability stack (circuit breaker, retry, rate limiting)
        await self._request(
            "POST",
            f"/docflows/{docflow_id}/form/{form_id}/upload",
            files=files_dict,
            use_upload_timeout=True
        )

        log.info(f"File uploaded successfully: {filename}")
        return True

    async def get_xml(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[bytes]:
        """
        Export form as XML.

        Returns XML representation of the form (useful for validation or external processing).

        Args:
            docflow_id: Docflow UUID
            form_id: Form ID

        Returns:
            XML content as bytes, or None on error
        """
        if not docflow_id or not form_id:
            log.warning("docflow_id and form_id are required for get_xml")
            return None

        log.debug(f"Getting XML for form {form_id} in docflow {docflow_id}")

        # Use _request with reliability stack (returns bytes)
        result = await self._request(
            "GET",
            f"/docflows/{docflow_id}/form/{form_id}/xml",
            response_type="bytes"
        )

        return result

    async def set_common_org(
        self,
        docflow_id: str,
        form_id: str,
        org_id: str,
        graph_number: str
    ) -> bool:
        """
        Set organization from CommonOrgs to a specific field.

        Used to fill contractor fields (consignee, consignor, etc.) from saved organizations.

        Args:
            docflow_id: Docflow UUID
            form_id: Form ID
            org_id: CommonOrg UUID
            graph_number: Field number in declaration (e.g., "8" for consignee, "2" for consignor)

        Returns:
            True if successful, False otherwise
        """
        if not docflow_id or not form_id or not org_id or not graph_number:
            log.warning("All parameters are required for set_common_org")
            return False

        log.info(f"Setting CommonOrg {org_id} to graph {graph_number} in form {form_id}, docflow {docflow_id}")

        await self._request(
            "POST",
            f"/docflows/{docflow_id}/form/{form_id}/setCommonOrg",
            params={
                "orgId": org_id,
                "graphNumber": graph_number
            }
        )

        return True
