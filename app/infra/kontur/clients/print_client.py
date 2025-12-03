# =============================================================================
# File: app/infra/kontur/clients/print_client.py
# Description: Client for Kontur Print API (form printing and export)
# Endpoints: 2
# =============================================================================

from typing import Optional
from app.config.logging_config import get_logger
from app.infra.kontur.clients.base_client import BaseClient

log = get_logger("wellwon.infra.kontur.print")


class PrintClient(BaseClient):
    """
    Client for Print API (declaration printing and export).

    Core operations:
    - Generate HTML preview
    - Generate PDF for printing/submission
    """

    def __init__(self, http_client, config):
        super().__init__(http_client, config, category="print")

    async def print_html(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[str]:
        """
        Generate HTML preview of form.

        Useful for:
        - Web preview before submission
        - Validation review
        - Email notifications

        Args:
            docflow_id: Docflow UUID
            form_id: Form ID (e.g., "dt")

        Returns:
            HTML string, or None on error
        """
        if not docflow_id or not form_id:
            log.warning("docflow_id and form_id are required for print_html")
            return None

        log.debug(f"Generating HTML for form {form_id} in docflow {docflow_id}")

        # Use _request with reliability stack (returns text)
        result = await self._request(
            "GET",
            f"/docflows/{docflow_id}/form/{form_id}/printHtml",
            response_type="text"
        )

        return result

    async def print_pdf(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[bytes]:
        """
        Generate PDF of form for printing or submission.

        PDF is official format for:
        - Paper customs submission
        - Archive storage
        - Email attachments

        Args:
            docflow_id: Docflow UUID
            form_id: Form ID (e.g., "dt")

        Returns:
            PDF content as bytes, or None on error

        Note:
            PDF generation can be slow (5-10 seconds), so long timeout is used.
        """
        if not docflow_id or not form_id:
            log.warning("docflow_id and form_id are required for print_pdf")
            return None

        log.info(f"Generating PDF for form {form_id} in docflow {docflow_id}")

        # Use _request with reliability stack (PDF generation can be slow)
        result = await self._request(
            "GET",
            f"/docflows/{docflow_id}/form/{form_id}/printPDF",
            use_long_timeout=True,
            response_type="bytes"
        )

        if result:
            log.info(f"PDF generated successfully ({len(result)} bytes)")

        return result
