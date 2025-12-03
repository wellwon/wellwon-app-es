# =============================================================================
# File: app/infra/kontur/adapter.py
# Description: Main Kontur Declarant API adapter facade
# Endpoints: 32 (delegated to 8 specialized clients)
# =============================================================================

from typing import Optional, List, Dict, Any
from functools import lru_cache
import httpx

from app.config.kontur_config import get_kontur_config, KonturConfig
from app.config.logging_config import get_logger
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

    def __init__(self, config: Optional[KonturConfig] = None):
        """
        Initialize Kontur adapter.

        Args:
            config: Optional KonturConfig (uses get_kontur_config() if not provided)
        """
        self.config = config or get_kontur_config()
        self._http_client: Optional[httpx.AsyncClient] = None

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

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client (lazy initialization)."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                headers={
                    "X-Kontur-ApiKey": self.config.api_key.get_secret_value(),
                    "Content-Type": "application/json"
                },
                timeout=self.config.timeout_seconds
            )
            log.debug("HTTP client initialized")
        return self._http_client

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
                self.config
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
                self.config
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

    # =========================================================================
    # Documents API (5 endpoints)
    # =========================================================================

    @property
    def _documents(self) -> DocumentsClient:
        """Get DocumentsClient (lazy initialization)."""
        if self._documents_client is None:
            self._documents_client = DocumentsClient(
                self._get_http_client(),
                self.config
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
                self.config
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
                self.config
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
                self.config
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
                self.config
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
                self.config
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


@lru_cache(maxsize=1)
def get_kontur_adapter() -> KonturAdapter:
    """
    Get Kontur adapter singleton.

    Returns:
        Global KonturAdapter instance
    """
    global _kontur_adapter_instance
    if _kontur_adapter_instance is None:
        _kontur_adapter_instance = KonturAdapter()
        # Instance creation logged by startup/adapters.py
    return _kontur_adapter_instance
