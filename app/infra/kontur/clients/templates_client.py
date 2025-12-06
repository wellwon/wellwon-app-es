# =============================================================================
# File: app/infra/kontur/clients/templates_client.py
# Description: Client for Kontur Templates API (JSON templates for forms)
# Endpoints: 2
# =============================================================================

from typing import List, Optional, Dict, Any
from app.config.logging_config import get_logger
from app.infra.kontur.clients.base_client import BaseClient
from app.infra.kontur.models import JsonTemplate

log = get_logger("wellwon.infra.kontur.templates")


class TemplatesClient(BaseClient):
    """
    Client for Templates API (JSON form templates).

    Templates = pre-filled form structures for different document types.

    Core operations:
    - List available templates
    - Get template structure

    Note: Templates rarely change, so aggressive caching (24h) is used.
    """

    def __init__(self, http_client, config, session_refresh_callback=None):
        super().__init__(http_client, config, category="templates", session_refresh_callback=session_refresh_callback)

    async def list_templates(self) -> List[JsonTemplate]:
        """
        List all available JSON templates.

        Templates define structure for different document modes
        (e.g., DT, CMR, Invoice, Contract, etc.)

        Returns:
            List of available templates with metadata
        """
        log.debug("Fetching JSON templates list")

        result = await self._request(
            "GET",
            "/jsonTemplates",
            cache_key="kontur:templates:list",
            cache_ttl=86400  # Cache for 24 hours (templates rarely change)
        )

        if result and isinstance(result, list):
            return [JsonTemplate.model_validate(item) for item in result]
        return []

    async def get_template(self, document_mode_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific template structure.

        Returns JSON schema defining:
        - Available fields
        - Field types and validations
        - Default values
        - Field relationships

        Args:
            document_mode_id: Document mode ID (e.g., "1006" for DT)

        Returns:
            Template JSON structure, or None if not found
        """
        if not document_mode_id:
            log.warning("document_mode_id is required for get_template")
            return None

        log.debug(f"Fetching template for document mode: {document_mode_id}")

        result = await self._request(
            "GET",
            f"/jsonTemplates/{document_mode_id}",
            cache_key=f"kontur:templates:{document_mode_id}",
            cache_ttl=86400  # Cache for 24 hours
        )

        return result if isinstance(result, dict) else None
