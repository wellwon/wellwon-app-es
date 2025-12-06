# =============================================================================
# File: app/customs/ports/kontur_declarant_port.py
# Description: Port interface for Kontur Declarant API
# Pattern: Hexagonal Architecture / Ports & Adapters
# =============================================================================

from __future__ import annotations

from typing import Protocol, Optional, List, Dict, Any, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
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
        VehiclePaymentResult,
    )


@runtime_checkable
class KonturDeclarantPort(Protocol):
    """
    Port: Kontur Declarant API

    Defined by: Customs Domain
    Implemented by: KonturAdapter (app/infra/kontur/adapter.py)

    This port defines the contract for interacting with Russian Federal
    Customs Service (FTS) via Kontur Declarant API. The domain uses this
    interface without knowing about the concrete implementation.

    Categories:
    - Organizations (2 methods)
    - Docflows (8 methods)
    - Documents (5 methods)
    - Forms (6 methods)
    - Templates (2 methods)
    - Options (7 methods)
    - Print (2 methods)
    - Payments (1 method)

    Total: 33 methods
    """

    # =========================================================================
    # Organizations (2 methods)
    # =========================================================================

    async def create_or_update_org(
        self,
        org: 'CommonOrg'
    ) -> Optional['CommonOrg']:
        """
        Create or update organization.

        Args:
            org: CommonOrg model with organization data

        Returns:
            Created/updated CommonOrg with ID, or None on error
        """
        ...

    async def get_or_create_org_by_inn(
        self,
        inn: str
    ) -> Optional['CommonOrg']:
        """
        Get or create organization by Russian INN (tax ID).

        Auto-fetches company data from Russian business registries.

        Args:
            inn: Russian INN (10 or 12 digits)

        Returns:
            CommonOrg with company data, or None on error
        """
        ...

    # =========================================================================
    # Docflows (8 methods)
    # =========================================================================

    async def list_docflows(
        self,
        take: int = 1000,
        changed_from: Optional[int] = None,
        changed_to: Optional[int] = None,
        status: Optional[int] = None,
        skip: int = 0
    ) -> List['DocflowDto']:
        """
        List docflows with filtering.

        Args:
            take: Maximum number of docflows to return
            changed_from: Filter by change timestamp (ms since epoch)
            changed_to: Filter by change timestamp (ms since epoch)
            status: Filter by docflow status
            skip: Number of records to skip (pagination)

        Returns:
            List of DocflowDto objects
        """
        ...

    async def create_docflow(
        self,
        request: 'CreateDocflowRequest'
    ) -> Optional['DocflowDto']:
        """
        Create new docflow (customs declaration).

        Args:
            request: CreateDocflowRequest with declaration parameters

        Returns:
            Created DocflowDto, or None on error
        """
        ...

    async def copy_docflow(
        self,
        request: 'CopyDocflowRequest'
    ) -> Optional['DocflowDto']:
        """
        Copy existing docflow (use as template).

        Args:
            request: CopyDocflowRequest with source docflow ID

        Returns:
            New DocflowDto copy, or None on error
        """
        ...

    async def search_docflows(
        self,
        request: 'SearchDocflowRequest',
        take: int = 50,
        skip: int = 0
    ) -> List['DocflowDto']:
        """
        Advanced search for docflows.

        Args:
            request: SearchDocflowRequest with search criteria
            take: Maximum results to return
            skip: Pagination offset

        Returns:
            List of matching DocflowDto objects
        """
        ...

    async def get_docflow(
        self,
        docflow_id: str
    ) -> Optional['DocflowDto']:
        """
        Get single docflow by ID.

        Args:
            docflow_id: Docflow UUID

        Returns:
            DocflowDto if found, None otherwise
        """
        ...

    async def get_declaration_marks(
        self,
        docflow_id: str
    ) -> List['DeclarationMark']:
        """
        Get customs marks/stamps on declaration.

        Args:
            docflow_id: Docflow UUID

        Returns:
            List of DeclarationMark objects
        """
        ...

    async def get_messages(
        self,
        docflow_id: str
    ) -> List['DocflowMessage']:
        """
        Get message journal (exchange log with FTS).

        Args:
            docflow_id: Docflow UUID

        Returns:
            List of DocflowMessage objects
        """
        ...

    async def set_opened_true(
        self,
        docflow_id: str
    ) -> bool:
        """
        Mark docflow as opened/viewed.

        Args:
            docflow_id: Docflow UUID

        Returns:
            True on success, False on error
        """
        ...

    # =========================================================================
    # Documents (5 methods)
    # =========================================================================

    async def list_documents(
        self,
        docflow_id: str
    ) -> List['DocumentRowDto']:
        """
        List all documents in a docflow.

        Args:
            docflow_id: Docflow UUID

        Returns:
            List of DocumentRowDto objects
        """
        ...

    async def create_documents(
        self,
        docflow_id: str,
        documents: List['CreateDocumentRequest']
    ) -> List['DocumentRowDto']:
        """
        Create multiple documents in a docflow.

        Args:
            docflow_id: Docflow UUID
            documents: List of documents to create

        Returns:
            List of created DocumentRowDto objects
        """
        ...

    async def attach_document_to_goods(
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
            good_numbers: Comma-separated goods numbers (e.g., "1,2,3")

        Returns:
            True on success, False on error
        """
        ...

    async def create_dts_with_calculator(
        self,
        docflow_id: str,
        dts_type: int,
        items: List['DistributionItem']
    ) -> Optional['DocumentRowDto']:
        """
        Create DTS (customs value distribution) using calculator.

        Args:
            docflow_id: Docflow UUID
            dts_type: DTS type (1 or 2)
            items: Distribution items for calculation

        Returns:
            Created DocumentRowDto, or None on error
        """
        ...

    async def copy_document_from_dt(
        self,
        docflow_id: str,
        document_id: str
    ) -> bool:
        """
        Copy document data from DT (customs declaration).

        Args:
            docflow_id: Docflow UUID
            document_id: Document UUID

        Returns:
            True on success, False on error
        """
        ...

    # =========================================================================
    # Forms (6 methods)
    # =========================================================================

    async def get_form_json(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get form data as JSON.

        Args:
            docflow_id: Docflow UUID
            form_id: Form identifier (e.g., "dt", "dts1")

        Returns:
            Form data dictionary, or None on error
        """
        ...

    async def import_form_json(
        self,
        docflow_id: str,
        form_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Import form data from JSON.

        Args:
            docflow_id: Docflow UUID
            form_id: Form identifier
            data: Form data to import

        Returns:
            True on success, False on error
        """
        ...

    async def import_goods_data(
        self,
        docflow_id: str,
        form_id: str,
        goods: List[Dict[str, Any]],
        clear_before: bool = False,
        preserve_attached: bool = False
    ) -> bool:
        """
        Import goods data in bulk.

        Args:
            docflow_id: Docflow UUID
            form_id: Form identifier
            goods: List of goods data dictionaries
            clear_before: Clear existing goods before import
            preserve_attached: Preserve attached documents

        Returns:
            True on success, False on error
        """
        ...

    async def upload_form_file(
        self,
        docflow_id: str,
        form_id: str,
        file_bytes: bytes,
        filename: str
    ) -> bool:
        """
        Upload form file (Excel, XML, etc.).

        Args:
            docflow_id: Docflow UUID
            form_id: Form identifier
            file_bytes: File content
            filename: Original filename

        Returns:
            True on success, False on error
        """
        ...

    async def get_form_xml(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[bytes]:
        """
        Export form as XML.

        Args:
            docflow_id: Docflow UUID
            form_id: Form identifier

        Returns:
            XML bytes, or None on error
        """
        ...

    async def set_form_contractor(
        self,
        docflow_id: str,
        form_id: str,
        org_id: str,
        graph_number: str
    ) -> bool:
        """
        Set organization from CommonOrgs to a specific field.

        Args:
            docflow_id: Docflow UUID
            form_id: Form identifier
            org_id: Organization UUID from CommonOrgs
            graph_number: Field number (e.g., "8" for consignee, "9" for financial)

        Returns:
            True on success, False on error
        """
        ...

    # =========================================================================
    # Templates (2 methods)
    # =========================================================================

    async def list_templates(self) -> List['JsonTemplate']:
        """
        List all available JSON templates.

        Returns:
            List of JsonTemplate objects
        """
        ...

    async def get_template(
        self,
        document_mode_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get specific template structure.

        Args:
            document_mode_id: Template mode ID (e.g., "1006" for DT)

        Returns:
            Template structure dictionary, or None on error
        """
        ...

    # =========================================================================
    # Options (7 methods)
    # =========================================================================

    async def list_organizations(self) -> List['OrganizationOption']:
        """
        List organizations available to current user.

        Returns:
            List of OrganizationOption objects
        """
        ...

    async def list_employees(
        self,
        org_id: str
    ) -> List['EmployeeOption']:
        """
        List employees for specific organization.

        Args:
            org_id: Organization UUID

        Returns:
            List of EmployeeOption objects
        """
        ...

    async def list_declaration_types(self) -> List['DeclarationTypeOption']:
        """
        List movement directions (declaration types).

        Returns:
            List of DeclarationTypeOption objects
        """
        ...

    async def list_procedures(
        self,
        declaration_type: str
    ) -> List[Dict[str, Any]]:
        """
        List customs procedures for specific declaration type.

        Args:
            declaration_type: Declaration type code

        Returns:
            List of procedure dictionaries
        """
        ...

    async def list_singularities(
        self,
        procedure: str
    ) -> List[Dict[str, Any]]:
        """
        List declaration singularities (special features) for procedure.

        Args:
            procedure: Procedure code

        Returns:
            List of singularity dictionaries
        """
        ...

    async def list_customs(self) -> List['CustomsOption']:
        """
        List customs posts/offices.

        Returns:
            List of CustomsOption objects
        """
        ...

    async def list_common_orgs(self) -> List[Dict[str, Any]]:
        """
        List common organizations (contractors).

        Returns:
            List of organization dictionaries
        """
        ...

    # =========================================================================
    # Print (2 methods)
    # =========================================================================

    async def print_html(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[str]:
        """
        Generate HTML preview of form.

        Args:
            docflow_id: Docflow UUID
            form_id: Form identifier

        Returns:
            HTML string, or None on error
        """
        ...

    async def print_pdf(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[bytes]:
        """
        Generate PDF of form for printing or submission.

        Args:
            docflow_id: Docflow UUID
            form_id: Form identifier

        Returns:
            PDF bytes, or None on error
        """
        ...

    # =========================================================================
    # Payments (1 method)
    # =========================================================================

    async def calculate_vehicle_payments(
        self,
        request: 'VehiclePaymentRequest'
    ) -> Optional['VehiclePaymentResult']:
        """
        Calculate customs payments for vehicle import.

        Args:
            request: VehiclePaymentRequest with vehicle parameters

        Returns:
            VehiclePaymentResult with calculated payments, or None on error
        """
        ...


# =============================================================================
# Convenience property protocol for organizations sub-client access
# =============================================================================

@runtime_checkable
class KonturOrganizationsPort(Protocol):
    """
    Port: Kontur Organizations sub-client

    Used when handler needs direct access to organizations client
    with specific methods like list_organizations() and list_employees().

    Implemented by: OrganizationsClient via KonturAdapter.organizations property
    """

    async def list_organizations(self) -> List['OrganizationOption']:
        """List available organizations."""
        ...

    async def list_employees(
        self,
        org_id: str
    ) -> List['EmployeeOption']:
        """List employees for organization."""
        ...


@runtime_checkable
class KonturOptionsPort(Protocol):
    """
    Port: Kontur Options sub-client

    Used when handler needs direct access to reference data options.

    Implemented by: OptionsClient via KonturAdapter.options property
    """

    async def get_declaration_types(self) -> List['DeclarationTypeOption']:
        """Get declaration types (movement directions)."""
        ...

    async def get_procedures(
        self,
        declaration_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get customs procedures."""
        ...

    async def get_customs(
        self,
        country_code: str = "RU"
    ) -> List['CustomsOption']:
        """Get customs offices."""
        ...


# =============================================================================
# EOF
# =============================================================================
