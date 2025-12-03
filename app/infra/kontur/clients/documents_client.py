# =============================================================================
# File: app/infra/kontur/clients/documents_client.py
# Description: Client for Kontur Documents API (declaration documents management)
# Endpoints: 5
# =============================================================================

from typing import List, Optional
from app.config.logging_config import get_logger
from app.infra.kontur.clients.base_client import BaseClient
from app.infra.kontur.models import (
    DocumentRowDto,
    CreateDocumentRequest,
    DistributionItem
)

log = get_logger("wellwon.infra.kontur.documents")


class DocumentsClient(BaseClient):
    """
    Client for Documents API (declaration document management).

    Documents = supporting documents for customs declarations (invoices, contracts, etc.)

    Core operations:
    - List documents in declaration
    - Create/attach documents
    - Link documents to goods
    - Calculate DTS (customs value distribution)
    - Copy document data from DT
    """

    def __init__(self, http_client, config):
        super().__init__(http_client, config, category="documents")

    async def list_documents(self, docflow_id: str) -> List[DocumentRowDto]:
        """
        List all documents in a docflow.

        Args:
            docflow_id: Docflow UUID

        Returns:
            List of documents attached to the declaration
        """
        if not docflow_id:
            log.warning("docflow_id is required for list_documents")
            return []

        log.debug(f"Listing documents for docflow: {docflow_id}")

        result = await self._request(
            "GET",
            f"/docflows/{docflow_id}/documents"
        )

        if result and isinstance(result, list):
            return [DocumentRowDto.model_validate(item) for item in result]
        return []

    async def create_documents(
        self,
        docflow_id: str,
        documents: List[CreateDocumentRequest]
    ) -> List[DocumentRowDto]:
        """
        Create multiple documents in a docflow.

        Args:
            docflow_id: Docflow UUID
            documents: List of documents to create

        Returns:
            List of created documents with IDs
        """
        if not docflow_id:
            log.warning("docflow_id is required for create_documents")
            return []

        if not documents:
            log.warning("documents list is empty")
            return []

        log.info(f"Creating {len(documents)} documents in docflow: {docflow_id}")

        result = await self._request(
            "POST",
            f"/docflows/{docflow_id}/documents",
            json=[doc.model_dump(by_alias=True, exclude_none=True) for doc in documents]
        )

        if result and isinstance(result, list):
            return [DocumentRowDto.model_validate(item) for item in result]
        return []

    async def attach_to_goods(
        self,
        docflow_id: str,
        document_id: str,
        good_numbers: str
    ) -> bool:
        """
        Attach document to specific goods in declaration.

        Args:
            docflow_id: Docflow UUID
            document_id: Document UUID
            good_numbers: Comma-separated good numbers (e.g., "1,2,3")

        Returns:
            True if successful, False otherwise
        """
        if not docflow_id or not document_id:
            log.warning("docflow_id and document_id are required for attach_to_goods")
            return False

        if not good_numbers:
            log.warning("good_numbers is required for attach_to_goods")
            return False

        log.info(f"Attaching document {document_id} to goods {good_numbers} in docflow {docflow_id}")

        await self._request(
            "POST",
            f"/docflows/{docflow_id}/documents/{document_id}/good/{good_numbers}"
        )

        return True

    async def create_dts_with_calculator(
        self,
        docflow_id: str,
        dts_type: int,
        items: List[DistributionItem]
    ) -> Optional[DocumentRowDto]:
        """
        Create DTS (customs value distribution) using calculator.

        DTS = Добавочный таможенный сбор (Additional Customs Fee)
        Calculator distributes costs across goods by weight, price, or manually.

        Args:
            docflow_id: Docflow UUID
            dts_type: DTS type (1=transport, 2=insurance, 3=loading, etc.)
            items: Distribution items with costs and allocation rules

        Returns:
            Created DTS document, or None on error
        """
        if not docflow_id:
            log.warning("docflow_id is required for create_dts_with_calculator")
            return None

        if not items:
            log.warning("items list is required for create_dts_with_calculator")
            return None

        log.info(f"Creating DTS type {dts_type} with {len(items)} items in docflow {docflow_id}")

        result = await self._request(
            "POST",
            f"/docflows/{docflow_id}/documents/createDtsWithCalculator",
            json={
                "dtsType": dts_type,
                "items": [item.model_dump(by_alias=True, exclude_none=True) for item in items]
            }
        )

        if result:
            return DocumentRowDto.model_validate(result)
        return None

    async def copy_from_dt(self, docflow_id: str, document_id: str) -> bool:
        """
        Copy document data from DT (customs declaration).

        Fills document fields automatically from declaration data.

        Args:
            docflow_id: Docflow UUID
            document_id: Document UUID

        Returns:
            True if successful, False otherwise
        """
        if not docflow_id or not document_id:
            log.warning("docflow_id and document_id are required for copy_from_dt")
            return False

        log.info(f"Copying DT data to document {document_id} in docflow {docflow_id}")

        await self._request(
            "POST",
            f"/docflows/{docflow_id}/documents/{document_id}/copyFromDt"
        )

        return True
