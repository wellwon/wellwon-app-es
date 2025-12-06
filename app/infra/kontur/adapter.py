# =============================================================================
# File: app/infra/kontur/adapter.py
# Description: Main Kontur Declarant API adapter facade
# Endpoints: 32 (delegated to 8 specialized clients)
# =============================================================================

from typing import Optional, List, Dict, Any, TYPE_CHECKING
from functools import lru_cache
import httpx

from app.config.kontur_config import get_kontur_config, KonturConfig
from app.config.logging_config import get_logger

if TYPE_CHECKING:
    from app.infra.persistence.cache_manager import CacheManager
from app.infra.kontur.models import (
    CommonOrg,
    DocflowDto,
    CreateDocflowRequest,
    CopyDocflowRequest,
    SearchDocflowRequest,
    DeclarationMark,
    DocflowMessage,
    DocumentRowDto,
    CreateDocumentRequest,
    DistributionItem,
    OrganizationOption,
    EmployeeOption,
    DeclarationTypeOption,
    CustomsOption,
    JsonTemplate,
    VehiclePaymentRequest,
    VehiclePaymentResult
)
from app.infra.kontur.clients.organizations_client import OrganizationsClient
from app.infra.kontur.clients.docflows_client import DocflowsClient
from app.infra.kontur.clients.documents_client import DocumentsClient
from app.infra.kontur.clients.forms_client import FormsClient
from app.infra.kontur.clients.templates_client import TemplatesClient
from app.infra.kontur.clients.options_client import OptionsClient
from app.infra.kontur.clients.print_client import PrintClient
from app.infra.kontur.clients.payments_client import PaymentsClient

log = get_logger("wellwon.infra.kontur.adapter")


class KonturAdapter:
    """
    Main Kontur Declarant API adapter facade.

    Provides unified interface to all Kontur API operations:
    - Organizations (2 endpoints)
    - Docflows (7 endpoints)
    - Documents (5 endpoints)
    - Forms (6 endpoints)
    - Templates (2 endpoints)
    - Options (7 endpoints)
    - Print (2 endpoints)
    - Payments (1 endpoint)

    Total: 32 endpoints across 8 categories.

    Features:
    - Lazy initialization of HTTP client and sub-clients
    - Singleton pattern via get_kontur_adapter()
    - Full reliability stack (circuit breaker, retry, rate limiting, etc.)
    - Comprehensive error handling
    - Request/response logging
    """

    # Cache key for Kontur session ID
    CACHE_KEY_SESSION = "wellwon:kontur:session_id"
    SESSION_TTL_SECONDS = 86400  # 24 hours - long-lived, we refresh on 401 error

    def __init__(
        self,
        config: Optional[KonturConfig] = None,
        cache_manager: Optional['CacheManager'] = None
    ):
        """
        Initialize Kontur adapter.

        Args:
            config: Optional KonturConfig (uses get_kontur_config() if not provided)
            cache_manager: Optional CacheManager for session caching (recommended)
        """
        self.config = config or get_kontur_config()
        self._cache_manager = cache_manager
        self._http_client: Optional[httpx.AsyncClient] = None
        self._session_id: Optional[str] = None  # In-memory fallback

        # Lazy-initialized sub-clients
        self._organizations_client: Optional[OrganizationsClient] = None
        self._docflows_client: Optional[DocflowsClient] = None
        self._documents_client: Optional[DocumentsClient] = None
        self._forms_client: Optional[FormsClient] = None
        self._templates_client: Optional[TemplatesClient] = None
        self._options_client: Optional[OptionsClient] = None
        self._print_client: Optional[PrintClient] = None
        self._payments_client: Optional[PaymentsClient] = None

        # Initialization logged by startup/adapters.py

    async def _refresh_session(self) -> None:
        """Refresh session - called by sub-clients on 401 error."""
        log.info("Refreshing Kontur session due to 401 error")
        await self.invalidate_session()
        await self.authenticate(force=True)

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client (lazy initialization)."""
        if self._http_client is None:
            headers = {
                "X-Kontur-ApiKey": self.config.get_api_key(),
                "Content-Type": "application/json"
            }
            # Add session ID if available
            if self._session_id:
                headers["Authorization"] = self._session_id

            self._http_client = httpx.AsyncClient(
                headers=headers,
                timeout=self.config.timeout_seconds
            )
            log.debug("HTTP client initialized")
        return self._http_client

    async def _get_cached_session(self) -> Optional[str]:
        """Get session ID from cache."""
        if self._cache_manager:
            try:
                return await self._cache_manager.get(self.CACHE_KEY_SESSION)
            except Exception as e:
                log.warning(f"Failed to get session from cache: {e}")
        return None

    async def _set_cached_session(self, session_id: str) -> None:
        """Store session ID in cache."""
        if self._cache_manager:
            try:
                await self._cache_manager.set(
                    self.CACHE_KEY_SESSION,
                    session_id,
                    ttl=self.SESSION_TTL_SECONDS
                )
            except Exception as e:
                log.warning(f"Failed to cache session: {e}")

    async def _clear_cached_session(self) -> None:
        """Clear session ID from cache."""
        if self._cache_manager:
            try:
                await self._cache_manager.delete(self.CACHE_KEY_SESSION)
            except Exception as e:
                log.warning(f"Failed to clear cached session: {e}")

    async def authenticate(self, force: bool = False) -> str:
        """
        Authenticate with Kontur API and obtain session ID.

        Calls POST /auth/v1/authenticate with login, password, and API key.
        The returned session ID is stored in cache and used for subsequent requests.

        Args:
            force: If True, skip cache and always get new session

        Returns:
            Session ID string

        Raises:
            ValueError: If credentials not configured
            PermissionError: If authentication fails (403)
            RuntimeError: If authentication fails for other reasons
        """
        # Try cache first (unless forced)
        if not force:
            cached_session = await self._get_cached_session()
            if cached_session:
                self._session_id = cached_session
                log.debug("Using cached Kontur session")
                return cached_session

        if not self.config.has_credentials():
            raise ValueError(
                "Kontur credentials not configured. "
                "Set KONTUR_API_KEY, KONTUR_LOGIN, and KONTUR_PASSWORD in .env"
            )

        auth_url = f"{self.config.base_url}/auth/v1/authenticate"

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(
                auth_url,
                params={
                    "login": self.config.login,
                    "pass": self.config.get_password(),
                },
                headers={
                    "X-Kontur-ApiKey": self.config.get_api_key(),
                    "Content-Type": "application/json"
                },
                content="{}"  # Empty JSON body required
            )

            if response.status_code == 200:
                self._session_id = response.text.strip().strip('"')
                # Cache the session
                await self._set_cached_session(self._session_id)
                # Reset HTTP client to pick up new session ID
                if self._http_client:
                    await self._http_client.aclose()
                    self._http_client = None
                log.info("Kontur authentication successful")
                return self._session_id
            elif response.status_code == 403:
                log.error("Kontur authentication failed: invalid credentials or API key")
                raise PermissionError("Kontur authentication failed: invalid login, password, or API key")
            else:
                log.error(f"Kontur authentication failed: HTTP {response.status_code}")
                raise RuntimeError(f"Kontur authentication failed: HTTP {response.status_code}")

    @property
    def is_authenticated(self) -> bool:
        """Check if we have a valid session ID in memory."""
        return self._session_id is not None

    async def ensure_authenticated(self) -> None:
        """Ensure we have a valid session ID, authenticating if needed."""
        if not self._session_id:
            await self.authenticate()

    async def invalidate_session(self) -> None:
        """Invalidate current session and clear cache."""
        self._session_id = None
        await self._clear_cached_session()
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        log.info("Kontur session invalidated")

    async def close(self):
        """Close HTTP client and cleanup resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            log.info("Kontur adapter closed")

    # =========================================================================
    # Organizations API (2 endpoints)
    # =========================================================================

    @property
    def _organizations(self) -> OrganizationsClient:
        """Get OrganizationsClient (lazy initialization)."""
        if self._organizations_client is None:
            self._organizations_client = OrganizationsClient(
                self._get_http_client(),
                self.config,
                session_refresh_callback=self._refresh_session
            )
        return self._organizations_client

    async def create_or_update_org(self, org: CommonOrg) -> Optional[CommonOrg]:
        """
        Create or update organization.

        Args:
            org: CommonOrg model with organization data

        Returns:
            Created/updated CommonOrg with ID, or None on error
        """
        return await self._organizations.create_or_update(org)

    async def get_or_create_org_by_inn(self, inn: str) -> Optional[CommonOrg]:
        """
        Get or create organization by Russian INN (tax ID).

        Auto-fetches company data from Russian business registries.

        Args:
            inn: Russian INN (10 or 12 digits)

        Returns:
            CommonOrg with company data, or None on error
        """
        return await self._organizations.get_or_create_by_inn(inn)

    # =========================================================================
    # Docflows API (7 endpoints)
    # =========================================================================

    @property
    def _docflows(self) -> DocflowsClient:
        """Get DocflowsClient (lazy initialization)."""
        if self._docflows_client is None:
            self._docflows_client = DocflowsClient(
                self._get_http_client(),
                self.config,
                session_refresh_callback=self._refresh_session
            )
        return self._docflows_client

    async def list_docflows(
        self,
        take: int = 1000,
        changed_from: Optional[int] = None,
        changed_to: Optional[int] = None,
        status: Optional[int] = None,
        skip: int = 0
    ) -> List[DocflowDto]:
        """List docflows with filtering."""
        return await self._docflows.list(
            take=take,
            changed_from=changed_from,
            changed_to=changed_to,
            status=status,
            skip=skip
        )

    async def create_docflow(self, request: CreateDocflowRequest) -> Optional[DocflowDto]:
        """Create new docflow (customs declaration)."""
        return await self._docflows.create(request)

    async def copy_docflow(self, request: CopyDocflowRequest) -> Optional[DocflowDto]:
        """Copy existing docflow (use as template)."""
        return await self._docflows.copy(request)

    async def search_docflows(
        self,
        request: SearchDocflowRequest,
        take: int = 50,
        skip: int = 0
    ) -> List[DocflowDto]:
        """Advanced search for docflows."""
        return await self._docflows.search(request, take=take, skip=skip)

    async def get_declaration_marks(self, docflow_id: str) -> List[DeclarationMark]:
        """Get customs marks/stamps on declaration."""
        return await self._docflows.get_marks(docflow_id)

    async def get_messages(self, docflow_id: str) -> List[DocflowMessage]:
        """Get message journal (exchange log with FTS)."""
        return await self._docflows.get_messages(docflow_id)

    async def set_opened_true(self, docflow_id: str) -> bool:
        """Mark docflow as opened/viewed."""
        return await self._docflows.set_opened(docflow_id)

    async def get_docflow(self, docflow_id: str) -> Optional[DocflowDto]:
        """
        Get single docflow by ID.

        Uses list_docflows to find specific docflow since Kontur API
        doesn't have a direct get-by-id endpoint.

        Args:
            docflow_id: Docflow UUID

        Returns:
            DocflowDto if found, None otherwise
        """
        # List all docflows and find by ID
        # Note: For better performance with large datasets, consider using
        # search_docflows with appropriate filters
        docflows = await self.list_docflows(take=1000)
        for df in docflows:
            if df.id == docflow_id:
                return df
        return None

    # =========================================================================
    # Documents API (5 endpoints)
    # =========================================================================

    @property
    def _documents(self) -> DocumentsClient:
        """Get DocumentsClient (lazy initialization)."""
        if self._documents_client is None:
            self._documents_client = DocumentsClient(
                self._get_http_client(),
                self.config,
                session_refresh_callback=self._refresh_session
            )
        return self._documents_client

    async def list_documents(self, docflow_id: str) -> List[DocumentRowDto]:
        """List all documents in a docflow."""
        return await self._documents.list_documents(docflow_id)

    async def create_documents(
        self,
        docflow_id: str,
        documents: List[CreateDocumentRequest]
    ) -> List[DocumentRowDto]:
        """Create multiple documents in a docflow."""
        return await self._documents.create_documents(docflow_id, documents)

    async def attach_document_to_goods(
        self,
        docflow_id: str,
        document_id: str,
        good_numbers: str
    ) -> bool:
        """Attach document to specific goods in declaration."""
        return await self._documents.attach_to_goods(docflow_id, document_id, good_numbers)

    async def create_dts_with_calculator(
        self,
        docflow_id: str,
        dts_type: int,
        items: List[DistributionItem]
    ) -> Optional[DocumentRowDto]:
        """Create DTS (customs value distribution) using calculator."""
        return await self._documents.create_dts_with_calculator(docflow_id, dts_type, items)

    async def copy_document_from_dt(self, docflow_id: str, document_id: str) -> bool:
        """Copy document data from DT (customs declaration)."""
        return await self._documents.copy_from_dt(docflow_id, document_id)

    # =========================================================================
    # Forms API (6 endpoints)
    # =========================================================================

    @property
    def _forms(self) -> FormsClient:
        """Get FormsClient (lazy initialization)."""
        if self._forms_client is None:
            self._forms_client = FormsClient(
                self._get_http_client(),
                self.config,
                session_refresh_callback=self._refresh_session
            )
        return self._forms_client

    async def get_form_json(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get form data as JSON."""
        return await self._forms.get_form_json(docflow_id, form_id)

    async def import_form_json(
        self,
        docflow_id: str,
        form_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """Import form data from JSON."""
        return await self._forms.import_json(docflow_id, form_id, data)

    async def import_goods_data(
        self,
        docflow_id: str,
        form_id: str,
        goods: List[Dict[str, Any]],
        clear_before: bool = False,
        preserve_attached: bool = False
    ) -> bool:
        """Import goods data in bulk."""
        return await self._forms.import_goods(
            docflow_id,
            form_id,
            goods,
            clear_before=clear_before,
            preserve_attached=preserve_attached
        )

    async def upload_form_file(
        self,
        docflow_id: str,
        form_id: str,
        file_bytes: bytes,
        filename: str
    ) -> bool:
        """Upload form file (Excel, XML, etc.)."""
        return await self._forms.upload_file(docflow_id, form_id, file_bytes, filename)

    async def get_form_xml(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[bytes]:
        """Export form as XML."""
        return await self._forms.get_xml(docflow_id, form_id)

    async def set_form_contractor(
        self,
        docflow_id: str,
        form_id: str,
        org_id: str,
        graph_number: str
    ) -> bool:
        """Set organization from CommonOrgs to a specific field."""
        return await self._forms.set_common_org(docflow_id, form_id, org_id, graph_number)

    # =========================================================================
    # Templates API (2 endpoints)
    # =========================================================================

    @property
    def _templates(self) -> TemplatesClient:
        """Get TemplatesClient (lazy initialization)."""
        if self._templates_client is None:
            self._templates_client = TemplatesClient(
                self._get_http_client(),
                self.config,
                session_refresh_callback=self._refresh_session
            )
        return self._templates_client

    async def list_templates(self) -> List[JsonTemplate]:
        """List all available JSON templates."""
        return await self._templates.list_templates()

    async def get_template(self, document_mode_id: str) -> Optional[Dict[str, Any]]:
        """Get specific template structure."""
        return await self._templates.get_template(document_mode_id)

    # =========================================================================
    # Options API (7 endpoints)
    # =========================================================================

    @property
    def _options(self) -> OptionsClient:
        """Get OptionsClient (lazy initialization)."""
        if self._options_client is None:
            self._options_client = OptionsClient(
                self._get_http_client(),
                self.config,
                session_refresh_callback=self._refresh_session
            )
        return self._options_client

    async def list_organizations(self) -> List[OrganizationOption]:
        """List organizations available to current user."""
        return await self._options.list_organizations()

    async def list_employees(self, org_id: str) -> List[EmployeeOption]:
        """List employees for specific organization."""
        return await self._options.list_employees(org_id)

    async def list_declaration_types(self) -> List[DeclarationTypeOption]:
        """List movement directions (declaration types)."""
        return await self._options.list_declaration_types()

    async def list_procedures(self, declaration_type: str) -> List[Dict[str, Any]]:
        """List customs procedures for specific declaration type."""
        return await self._options.list_procedures(declaration_type)

    async def list_singularities(self, procedure: str) -> List[Dict[str, Any]]:
        """List declaration singularities (special features) for procedure."""
        return await self._options.list_singularities(procedure)

    async def list_customs(self) -> List[CustomsOption]:
        """List customs posts/offices."""
        return await self._options.list_customs()

    async def list_common_orgs(self) -> List[Dict[str, Any]]:
        """List common organizations (contractors)."""
        return await self._options.list_common_orgs()

    # =========================================================================
    # Print API (2 endpoints)
    # =========================================================================

    @property
    def _print(self) -> PrintClient:
        """Get PrintClient (lazy initialization)."""
        if self._print_client is None:
            self._print_client = PrintClient(
                self._get_http_client(),
                self.config,
                session_refresh_callback=self._refresh_session
            )
        return self._print_client

    async def print_html(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[str]:
        """Generate HTML preview of form."""
        return await self._print.print_html(docflow_id, form_id)

    async def print_pdf(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[bytes]:
        """Generate PDF of form for printing or submission."""
        return await self._print.print_pdf(docflow_id, form_id)

    # =========================================================================
    # Payments API (1 endpoint)
    # =========================================================================

    @property
    def _payments(self) -> PaymentsClient:
        """Get PaymentsClient (lazy initialization)."""
        if self._payments_client is None:
            self._payments_client = PaymentsClient(
                self._get_http_client(),
                self.config,
                session_refresh_callback=self._refresh_session
            )
        return self._payments_client

    async def calculate_vehicle_payments(
        self,
        request: VehiclePaymentRequest
    ) -> Optional[VehiclePaymentResult]:
        """Calculate customs payments for vehicle import."""
        return await self._payments.calculate_vehicle_payments(request)


# =============================================================================
# Singleton Factory
# =============================================================================

_kontur_adapter_instance: Optional[KonturAdapter] = None


def get_kontur_adapter(cache_manager: Optional['CacheManager'] = None) -> KonturAdapter:
    """
    Get Kontur adapter singleton.

    Args:
        cache_manager: Optional CacheManager for session caching.
                      Only used on first call to create the singleton.

    Returns:
        Global KonturAdapter instance
    """
    global _kontur_adapter_instance
    if _kontur_adapter_instance is None:
        _kontur_adapter_instance = KonturAdapter(cache_manager=cache_manager)
        # Instance creation logged by startup/adapters.py
    return _kontur_adapter_instance


async def get_kontur_adapter_async(cache_manager: Optional['CacheManager'] = None) -> KonturAdapter:
    """
    Get Kontur adapter singleton with pre-authentication.

    Use this at startup to ensure the adapter is authenticated.

    Args:
        cache_manager: Optional CacheManager for session caching.

    Returns:
        Authenticated KonturAdapter instance
    """
    adapter = get_kontur_adapter(cache_manager)
    if adapter.config.has_credentials():
        await adapter.authenticate()
    return adapter


def reset_kontur_adapter() -> None:
    """Reset adapter singleton (for testing)."""
    global _kontur_adapter_instance
    _kontur_adapter_instance = None
