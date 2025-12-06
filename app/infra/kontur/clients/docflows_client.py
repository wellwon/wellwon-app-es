# =============================================================================
# File: app/infra/kontur/clients/docflows_client.py
# Description: Client for Kontur Docflows API (customs declarations workflow)
# Endpoints: 7
# =============================================================================

from typing import List, Optional
from app.config.logging_config import get_logger
from app.infra.kontur.clients.base_client import BaseClient
from app.infra.kontur.models import (
    DocflowDto,
    CreateDocflowRequest,
    CopyDocflowRequest,
    SearchDocflowRequest,
    DeclarationMark,
    DocflowMessage
)

log = get_logger("wellwon.infra.kontur.docflows")


class DocflowsClient(BaseClient):
    """
    Client for Docflows API (customs declaration workflow management).

    Docflow = complete customs declaration procedure with all documents.

    Core operations:
    - Create new declaration
    - Copy from template
    - Search and list declarations
    - Get messages (exchange log with FTS)
    - Get customs marks/stamps
    - Mark as viewed
    """

    def __init__(self, http_client, config, session_refresh_callback=None):
        super().__init__(http_client, config, category="docflows", session_refresh_callback=session_refresh_callback)

    async def list(
        self,
        take: int = 1000,
        changed_from: Optional[int] = None,
        changed_to: Optional[int] = None,
        status: Optional[int] = None,
        skip: int = 0
    ) -> List[DocflowDto]:
        """
        List docflows with filtering.

        Args:
            take: Max results (default 1000)
            changed_from: Filter by change timestamp (from)
            changed_to: Filter by change timestamp (to)
            status: Filter by declaration status
            skip: Skip first N results (pagination)

        Returns:
            List of docflows matching criteria
        """
        log.debug(f"Listing docflows (take={take}, skip={skip})")

        params = {"take": take, "skip": skip}
        if changed_from:
            params["changedFrom"] = changed_from
        if changed_to:
            params["changedTo"] = changed_to
        if status is not None:
            params["status"] = status

        result = await self._request(
            "GET",
            "/docflows",
            params=params,
            use_long_timeout=True  # List can be slow with large datasets
        )

        if result and isinstance(result, list):
            return [DocflowDto.model_validate(item) for item in result]
        return []

    async def create(self, request: CreateDocflowRequest) -> Optional[DocflowDto]:
        """
        Create new docflow (customs declaration).

        Args:
            request: CreateDocflowRequest with declaration parameters

        Returns:
            Created docflow with ID, or None on error
        """
        log.info(f"Creating docflow: {request.name}")

        result = await self._request(
            "POST",
            "/docflows",
            json=request.model_dump(by_alias=True, exclude_none=True)
        )

        if result:
            return DocflowDto.model_validate(result)
        return None

    async def copy(self, request: CopyDocflowRequest) -> Optional[DocflowDto]:
        """
        Copy existing docflow (use as template).

        Recommended for creating declarations:
        1. Create one well-configured docflow manually
        2. Use it as template for subsequent declarations
        3. Only change specific fields (consignee, values, etc.)

        Args:
            request: CopyDocflowRequest with source ID and override fields

        Returns:
            New docflow (copy), or None on error
        """
        log.info(f"Copying docflow from: {request.copy_from_id}")

        result = await self._request(
            "POST",
            "/docflows/copy",
            json=request.model_dump(by_alias=True, exclude_none=True)
        )

        if result:
            return DocflowDto.model_validate(result)
        return None

    async def search(
        self,
        request: SearchDocflowRequest,
        take: int = 50,
        skip: int = 0
    ) -> List[DocflowDto]:
        """
        Advanced search for docflows.

        Supports full-text search and filtering by:
        - Name/query
        - Procedure (customs procedure code)
        - Type (declaration type)
        - Date range
        - Document number
        - Consignee/Consignor

        Args:
            request: SearchDocflowRequest with search criteria
            take: Max results (default 50)
            skip: Skip first N results

        Returns:
            List of matching docflows
        """
        log.debug(f"Searching docflows (query={request.query})")

        result = await self._request(
            "POST",
            "/docflows/search",
            params={"take": take, "skip": skip},
            json=request.model_dump(by_alias=True, exclude_none=True)
        )

        if result and isinstance(result, list):
            return [DocflowDto.model_validate(item) for item in result]
        return []

    async def get_marks(self, docflow_id: str) -> List[DeclarationMark]:
        """
        Get customs marks/stamps on declaration.

        Marks are official stamps/notes from Federal Customs Service (FTS).

        Args:
            docflow_id: Docflow UUID

        Returns:
            List of customs marks, empty list if none
        """
        if not docflow_id:
            log.warning("docflow_id is required for get_marks")
            return []

        # Validate UUID format (security: prevent path traversal)
        self._validate_uuid(docflow_id, "docflow_id")

        log.debug(f"Getting marks for docflow: {docflow_id}")

        result = await self._request(
            "GET",
            f"/docflows/{docflow_id}/declarationMarks",
            cache_key=f"kontur:docflow:{docflow_id}:marks",
            cache_ttl=300  # Cache for 5 minutes (marks don't change often)
        )

        if result and isinstance(result, list):
            return [DeclarationMark.model_validate(item) for item in result]
        return []

    async def get_messages(self, docflow_id: str) -> List[DocflowMessage]:
        """
        Get message journal (exchange log with FTS).

        Messages show communication history:
        - Outgoing: Submitted to customs
        - Incoming: Responses from FTS (registered, released, rejected, etc.)

        Args:
            docflow_id: Docflow UUID

        Returns:
            List of messages, empty list if none
        """
        if not docflow_id:
            log.warning("docflow_id is required for get_messages")
            return []

        self._validate_uuid(docflow_id, "docflow_id")

        log.debug(f"Getting messages for docflow: {docflow_id}")

        result = await self._request(
            "GET",
            f"/docflows/{docflow_id}/messages"
        )

        if result and isinstance(result, list):
            return [DocflowMessage.model_validate(item) for item in result]
        return []

    async def set_opened(self, docflow_id: str) -> bool:
        """
        Mark docflow as opened/viewed.

        Used to track which declarations user has reviewed.

        Args:
            docflow_id: Docflow UUID

        Returns:
            True if successful, False otherwise
        """
        if not docflow_id:
            log.warning("docflow_id is required for set_opened")
            return False

        log.debug(f"Marking docflow as opened: {docflow_id}")

        await self._request(
            "POST",
            f"/docflows/{docflow_id}/setOpenedTrue"
        )

        return True
