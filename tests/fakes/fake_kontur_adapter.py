# =============================================================================
# File: tests/fakes/fake_kontur_adapter.py
# Description: Fake implementation of KonturDeclarantPort for unit testing
# Pattern: Ports & Adapters - Fake/Stub adapter
# =============================================================================

from __future__ import annotations

import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class FakeDocflow:
    """Fake docflow for testing."""
    id: str
    status: int = 0  # Draft
    declaration_type: str = "IM"
    procedure: str = "4000"
    organization_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FakeOrganization:
    """Fake organization for testing."""
    id: str
    name: str
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None


@dataclass
class CallRecord:
    """Record of a method call for verification."""
    method: str
    args: tuple
    kwargs: Dict[str, Any]
    result: Any = None


class FakeKonturAdapter:
    """
    Fake implementation of KonturDeclarantPort for unit testing.

    This adapter stores data in memory and tracks all method calls
    for verification in tests.

    Usage:
        fake = FakeKonturAdapter()
        fake.set_docflow("test-id", FakeDocflow(id="test-id", status=0))

        handler = SubmitToKonturHandler(HandlerDependencies(
            kontur_adapter=fake,
            ...
        ))

        await handler.handle(command)

        # Verify calls
        assert fake.was_called("create_docflow")
        assert fake.get_call_count("import_form_json") == 1
    """

    def __init__(self):
        # In-memory storage
        self.docflows: Dict[str, FakeDocflow] = {}
        self.organizations: Dict[str, FakeOrganization] = {}
        self.forms: Dict[str, Dict[str, Any]] = {}  # docflow_id -> form_id -> data
        self.documents: Dict[str, List[Dict[str, Any]]] = {}  # docflow_id -> docs

        # Call tracking
        self._calls: List[CallRecord] = []

        # Configurable responses
        self._should_fail: Dict[str, str] = {}  # method -> error message
        self._custom_responses: Dict[str, Any] = {}  # method -> response

    # =========================================================================
    # Test Setup Methods
    # =========================================================================

    def set_docflow(self, docflow_id: str, docflow: FakeDocflow) -> None:
        """Setup a docflow for testing."""
        self.docflows[docflow_id] = docflow

    def set_organization(self, org_id: str, org: FakeOrganization) -> None:
        """Setup an organization for testing."""
        self.organizations[org_id] = org

    def set_form_data(self, docflow_id: str, form_id: str, data: Dict[str, Any]) -> None:
        """Setup form data for testing."""
        if docflow_id not in self.forms:
            self.forms[docflow_id] = {}
        self.forms[docflow_id][form_id] = data

    def configure_failure(self, method: str, error_message: str) -> None:
        """Configure a method to fail with an error."""
        self._should_fail[method] = error_message

    def configure_response(self, method: str, response: Any) -> None:
        """Configure a custom response for a method."""
        self._custom_responses[method] = response

    def clear(self) -> None:
        """Reset all state between tests."""
        self.docflows.clear()
        self.organizations.clear()
        self.forms.clear()
        self.documents.clear()
        self._calls.clear()
        self._should_fail.clear()
        self._custom_responses.clear()

    # =========================================================================
    # Test Verification Methods
    # =========================================================================

    def was_called(self, method: str) -> bool:
        """Check if a method was called."""
        return any(c.method == method for c in self._calls)

    def get_call_count(self, method: str) -> int:
        """Get number of times a method was called."""
        return sum(1 for c in self._calls if c.method == method)

    def get_calls(self, method: str) -> List[CallRecord]:
        """Get all calls to a specific method."""
        return [c for c in self._calls if c.method == method]

    def get_last_call(self, method: str) -> Optional[CallRecord]:
        """Get the last call to a specific method."""
        calls = self.get_calls(method)
        return calls[-1] if calls else None

    def get_all_calls(self) -> List[CallRecord]:
        """Get all recorded calls."""
        return self._calls.copy()

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _record_call(self, method: str, *args, **kwargs) -> None:
        """Record a method call."""
        self._calls.append(CallRecord(method=method, args=args, kwargs=kwargs))

    def _check_failure(self, method: str) -> None:
        """Check if method should fail and raise exception."""
        if method in self._should_fail:
            raise Exception(self._should_fail[method])

    def _get_custom_response(self, method: str) -> Optional[Any]:
        """Get custom response if configured."""
        return self._custom_responses.get(method)

    # =========================================================================
    # KonturDeclarantPort Implementation - Organizations
    # =========================================================================

    async def create_or_update_org(self, org: Any) -> Optional[Any]:
        """Create or update organization."""
        self._record_call("create_or_update_org", org)
        self._check_failure("create_or_update_org")

        if custom := self._get_custom_response("create_or_update_org"):
            return custom

        fake_org = FakeOrganization(
            id=str(uuid.uuid4()),
            name=getattr(org, "name", "Test Org"),
            inn=getattr(org, "inn", None),
        )
        self.organizations[fake_org.id] = fake_org
        return org

    async def get_or_create_org_by_inn(self, inn: str) -> Optional[Any]:
        """Get or create organization by INN."""
        self._record_call("get_or_create_org_by_inn", inn)
        self._check_failure("get_or_create_org_by_inn")

        if custom := self._get_custom_response("get_or_create_org_by_inn"):
            return custom

        # Return existing org with matching INN or create new
        for org in self.organizations.values():
            if org.inn == inn:
                return org
        return None

    # =========================================================================
    # KonturDeclarantPort Implementation - Docflows
    # =========================================================================

    async def list_docflows(
        self,
        take: int = 1000,
        changed_from: Optional[int] = None,
        changed_to: Optional[int] = None,
        status: Optional[int] = None,
        skip: int = 0
    ) -> List[Any]:
        """List docflows."""
        self._record_call("list_docflows", take=take, status=status)
        self._check_failure("list_docflows")

        if custom := self._get_custom_response("list_docflows"):
            return custom

        result = list(self.docflows.values())
        if status is not None:
            result = [d for d in result if d.status == status]
        return result[skip:skip + take]

    async def create_docflow(self, request: Any) -> Optional[Any]:
        """Create new docflow."""
        self._record_call("create_docflow", request)
        self._check_failure("create_docflow")

        if custom := self._get_custom_response("create_docflow"):
            return custom

        docflow_id = str(uuid.uuid4())
        docflow = FakeDocflow(
            id=docflow_id,
            status=0,
            declaration_type=getattr(request, "declaration_type", "IM"),
            procedure=getattr(request, "procedure", "4000"),
            organization_id=getattr(request, "organization_id", None),
        )
        self.docflows[docflow_id] = docflow
        return docflow

    async def copy_docflow(self, request: Any) -> Optional[Any]:
        """Copy existing docflow."""
        self._record_call("copy_docflow", request)
        self._check_failure("copy_docflow")

        if custom := self._get_custom_response("copy_docflow"):
            return custom

        source_id = getattr(request, "source_docflow_id", None)
        if source_id and source_id in self.docflows:
            source = self.docflows[source_id]
            new_id = str(uuid.uuid4())
            copy = FakeDocflow(
                id=new_id,
                status=0,
                declaration_type=source.declaration_type,
                procedure=source.procedure,
                data=source.data.copy(),
            )
            self.docflows[new_id] = copy
            return copy
        return None

    async def search_docflows(
        self,
        request: Any,
        take: int = 50,
        skip: int = 0
    ) -> List[Any]:
        """Search docflows."""
        self._record_call("search_docflows", request, take=take, skip=skip)
        self._check_failure("search_docflows")

        if custom := self._get_custom_response("search_docflows"):
            return custom

        return list(self.docflows.values())[skip:skip + take]

    async def get_docflow(self, docflow_id: str) -> Optional[Any]:
        """Get docflow by ID."""
        self._record_call("get_docflow", docflow_id)
        self._check_failure("get_docflow")

        if custom := self._get_custom_response("get_docflow"):
            return custom

        return self.docflows.get(docflow_id)

    async def get_declaration_marks(self, docflow_id: str) -> List[Any]:
        """Get declaration marks."""
        self._record_call("get_declaration_marks", docflow_id)
        self._check_failure("get_declaration_marks")

        if custom := self._get_custom_response("get_declaration_marks"):
            return custom

        return []

    async def get_messages(self, docflow_id: str) -> List[Any]:
        """Get docflow messages."""
        self._record_call("get_messages", docflow_id)
        self._check_failure("get_messages")

        if custom := self._get_custom_response("get_messages"):
            return custom

        return []

    async def set_opened_true(self, docflow_id: str) -> bool:
        """Mark docflow as opened."""
        self._record_call("set_opened_true", docflow_id)
        self._check_failure("set_opened_true")
        return True

    # =========================================================================
    # KonturDeclarantPort Implementation - Documents
    # =========================================================================

    async def list_documents(self, docflow_id: str) -> List[Any]:
        """List documents in docflow."""
        self._record_call("list_documents", docflow_id)
        self._check_failure("list_documents")

        if custom := self._get_custom_response("list_documents"):
            return custom

        return self.documents.get(docflow_id, [])

    async def create_documents(
        self,
        docflow_id: str,
        documents: List[Any]
    ) -> List[Any]:
        """Create documents."""
        self._record_call("create_documents", docflow_id, documents)
        self._check_failure("create_documents")

        if custom := self._get_custom_response("create_documents"):
            return custom

        if docflow_id not in self.documents:
            self.documents[docflow_id] = []

        created = []
        for doc in documents:
            doc_dict = {"id": str(uuid.uuid4()), **doc} if isinstance(doc, dict) else {"id": str(uuid.uuid4())}
            self.documents[docflow_id].append(doc_dict)
            created.append(doc_dict)
        return created

    async def attach_document_to_goods(
        self,
        docflow_id: str,
        document_id: str,
        good_numbers: str
    ) -> bool:
        """Attach document to goods."""
        self._record_call("attach_document_to_goods", docflow_id, document_id, good_numbers)
        self._check_failure("attach_document_to_goods")
        return True

    async def create_dts_with_calculator(
        self,
        docflow_id: str,
        dts_type: int,
        items: List[Any]
    ) -> Optional[Any]:
        """Create DTS with calculator."""
        self._record_call("create_dts_with_calculator", docflow_id, dts_type, items)
        self._check_failure("create_dts_with_calculator")

        if custom := self._get_custom_response("create_dts_with_calculator"):
            return custom

        return {"id": str(uuid.uuid4()), "type": "dts"}

    async def copy_document_from_dt(
        self,
        docflow_id: str,
        document_id: str
    ) -> bool:
        """Copy document from DT."""
        self._record_call("copy_document_from_dt", docflow_id, document_id)
        self._check_failure("copy_document_from_dt")
        return True

    # =========================================================================
    # KonturDeclarantPort Implementation - Forms
    # =========================================================================

    async def get_form_json(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get form JSON."""
        self._record_call("get_form_json", docflow_id, form_id)
        self._check_failure("get_form_json")

        if custom := self._get_custom_response("get_form_json"):
            return custom

        return self.forms.get(docflow_id, {}).get(form_id)

    async def import_form_json(
        self,
        docflow_id: str,
        form_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """Import form JSON."""
        self._record_call("import_form_json", docflow_id, form_id, data)
        self._check_failure("import_form_json")

        if docflow_id not in self.forms:
            self.forms[docflow_id] = {}
        self.forms[docflow_id][form_id] = data
        return True

    async def import_goods_data(
        self,
        docflow_id: str,
        form_id: str,
        goods: List[Dict[str, Any]],
        clear_before: bool = False,
        preserve_attached: bool = False
    ) -> bool:
        """Import goods data."""
        self._record_call("import_goods_data", docflow_id, form_id, goods, clear_before=clear_before)
        self._check_failure("import_goods_data")

        if docflow_id not in self.forms:
            self.forms[docflow_id] = {}
        if form_id not in self.forms[docflow_id]:
            self.forms[docflow_id][form_id] = {}

        if clear_before:
            self.forms[docflow_id][form_id]["goods"] = goods
        else:
            existing = self.forms[docflow_id][form_id].get("goods", [])
            self.forms[docflow_id][form_id]["goods"] = existing + goods
        return True

    async def upload_form_file(
        self,
        docflow_id: str,
        form_id: str,
        file_bytes: bytes,
        filename: str
    ) -> bool:
        """Upload form file."""
        self._record_call("upload_form_file", docflow_id, form_id, file_bytes, filename)
        self._check_failure("upload_form_file")
        return True

    async def get_form_xml(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[bytes]:
        """Get form XML."""
        self._record_call("get_form_xml", docflow_id, form_id)
        self._check_failure("get_form_xml")

        if custom := self._get_custom_response("get_form_xml"):
            return custom

        return b"<fake-xml/>"

    async def set_form_contractor(
        self,
        docflow_id: str,
        form_id: str,
        org_id: str,
        graph_number: str
    ) -> bool:
        """Set form contractor."""
        self._record_call("set_form_contractor", docflow_id, form_id, org_id, graph_number)
        self._check_failure("set_form_contractor")
        return True

    # =========================================================================
    # KonturDeclarantPort Implementation - Templates
    # =========================================================================

    async def list_templates(self) -> List[Any]:
        """List templates."""
        self._record_call("list_templates")
        self._check_failure("list_templates")

        if custom := self._get_custom_response("list_templates"):
            return custom

        return []

    async def get_template(self, document_mode_id: str) -> Optional[Dict[str, Any]]:
        """Get template."""
        self._record_call("get_template", document_mode_id)
        self._check_failure("get_template")

        if custom := self._get_custom_response("get_template"):
            return custom

        return {}

    # =========================================================================
    # KonturDeclarantPort Implementation - Options
    # =========================================================================

    async def list_organizations(self) -> List[Any]:
        """List organizations."""
        self._record_call("list_organizations")
        self._check_failure("list_organizations")

        if custom := self._get_custom_response("list_organizations"):
            return custom

        return list(self.organizations.values())

    async def list_employees(self, org_id: str) -> List[Any]:
        """List employees."""
        self._record_call("list_employees", org_id)
        self._check_failure("list_employees")

        if custom := self._get_custom_response("list_employees"):
            return custom

        return []

    async def list_declaration_types(self) -> List[Any]:
        """List declaration types."""
        self._record_call("list_declaration_types")
        self._check_failure("list_declaration_types")

        if custom := self._get_custom_response("list_declaration_types"):
            return custom

        return [
            {"code": "IM", "name": "Import"},
            {"code": "EX", "name": "Export"},
        ]

    async def list_procedures(self, declaration_type: str) -> List[Dict[str, Any]]:
        """List procedures."""
        self._record_call("list_procedures", declaration_type)
        self._check_failure("list_procedures")

        if custom := self._get_custom_response("list_procedures"):
            return custom

        return [
            {"code": "4000", "name": "Release for domestic consumption"},
        ]

    async def list_singularities(self, procedure: str) -> List[Dict[str, Any]]:
        """List singularities."""
        self._record_call("list_singularities", procedure)
        self._check_failure("list_singularities")

        if custom := self._get_custom_response("list_singularities"):
            return custom

        return []

    async def list_customs(self) -> List[Any]:
        """List customs offices."""
        self._record_call("list_customs")
        self._check_failure("list_customs")

        if custom := self._get_custom_response("list_customs"):
            return custom

        return []

    async def list_common_orgs(self) -> List[Dict[str, Any]]:
        """List common organizations."""
        self._record_call("list_common_orgs")
        self._check_failure("list_common_orgs")

        if custom := self._get_custom_response("list_common_orgs"):
            return custom

        return [{"id": org.id, "name": org.name} for org in self.organizations.values()]

    # =========================================================================
    # KonturDeclarantPort Implementation - Print
    # =========================================================================

    async def print_html(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[str]:
        """Print HTML."""
        self._record_call("print_html", docflow_id, form_id)
        self._check_failure("print_html")

        if custom := self._get_custom_response("print_html"):
            return custom

        return "<html><body>Fake HTML</body></html>"

    async def print_pdf(
        self,
        docflow_id: str,
        form_id: str
    ) -> Optional[bytes]:
        """Print PDF."""
        self._record_call("print_pdf", docflow_id, form_id)
        self._check_failure("print_pdf")

        if custom := self._get_custom_response("print_pdf"):
            return custom

        return b"%PDF-1.4 fake"

    # =========================================================================
    # KonturDeclarantPort Implementation - Payments
    # =========================================================================

    async def calculate_vehicle_payments(self, request: Any) -> Optional[Any]:
        """Calculate vehicle payments."""
        self._record_call("calculate_vehicle_payments", request)
        self._check_failure("calculate_vehicle_payments")

        if custom := self._get_custom_response("calculate_vehicle_payments"):
            return custom

        return {"total": 0, "duty": 0, "vat": 0}


# =============================================================================
# EOF
# =============================================================================
