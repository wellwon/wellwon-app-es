# =============================================================================
# File: tests/fakes/fake_dadata_adapter.py
# Description: Fake implementation of CompanyEnrichmentPort for unit testing
# Pattern: Ports & Adapters - Fake/Stub adapter
# =============================================================================

from __future__ import annotations

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class FakeCompanyInfo:
    """Fake company info for testing."""
    inn: str
    name_full: str
    name_short: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    address: Optional[str] = None
    status: str = "ACTIVE"


@dataclass
class CallRecord:
    """Record of a method call for verification."""
    method: str
    args: tuple
    kwargs: Dict[str, Any]
    result: Any = None


class FakeDaDataAdapter:
    """
    Fake implementation of CompanyEnrichmentPort for unit testing.

    This adapter stores data in memory and tracks all method calls
    for verification in tests.

    Usage:
        fake = FakeDaDataAdapter()
        fake.set_company("1234567890", FakeCompanyInfo(
            inn="1234567890",
            name_full="Test Company LLC",
            ogrn="1234567890123",
        ))

        # Use in handler/service
        result = await fake.lookup_company_by_inn("1234567890")
        assert result.name_full == "Test Company LLC"

        # Verify calls
        assert fake.was_called("lookup_company_by_inn")
    """

    def __init__(self):
        # In-memory storage - indexed by INN and OGRN
        self.companies_by_inn: Dict[str, FakeCompanyInfo] = {}
        self.companies_by_ogrn: Dict[str, FakeCompanyInfo] = {}

        # Call tracking
        self._calls: List[CallRecord] = []

        # Configurable responses
        self._should_fail: Dict[str, str] = {}  # method -> error message
        self._custom_responses: Dict[str, Any] = {}  # method -> response

    # =========================================================================
    # Test Setup Methods
    # =========================================================================

    def set_company(self, inn: str, company: FakeCompanyInfo) -> None:
        """Setup a company for testing (indexed by INN)."""
        self.companies_by_inn[inn] = company
        if company.ogrn:
            self.companies_by_ogrn[company.ogrn] = company

    def set_company_by_ogrn(self, ogrn: str, company: FakeCompanyInfo) -> None:
        """Setup a company for testing (indexed by OGRN)."""
        self.companies_by_ogrn[ogrn] = company
        if company.inn:
            self.companies_by_inn[company.inn] = company

    def configure_failure(self, method: str, error_message: str) -> None:
        """Configure a method to fail with an error."""
        self._should_fail[method] = error_message

    def configure_response(self, method: str, response: Any) -> None:
        """Configure a custom response for a method."""
        self._custom_responses[method] = response

    def clear(self) -> None:
        """Reset all state between tests."""
        self.companies_by_inn.clear()
        self.companies_by_ogrn.clear()
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
    # CompanyEnrichmentPort Implementation
    # =========================================================================

    async def lookup_company_by_inn(self, inn: str) -> Optional[FakeCompanyInfo]:
        """
        Lookup company by INN.

        Args:
            inn: Russian INN (10 or 12 digits)

        Returns:
            FakeCompanyInfo if found, None otherwise
        """
        self._record_call("lookup_company_by_inn", inn)
        self._check_failure("lookup_company_by_inn")

        if custom := self._get_custom_response("lookup_company_by_inn"):
            return custom

        return self.companies_by_inn.get(inn)

    async def lookup_company_by_ogrn(self, ogrn: str) -> Optional[FakeCompanyInfo]:
        """
        Lookup company by OGRN.

        Args:
            ogrn: Russian OGRN (13 or 15 digits)

        Returns:
            FakeCompanyInfo if found, None otherwise
        """
        self._record_call("lookup_company_by_ogrn", ogrn)
        self._check_failure("lookup_company_by_ogrn")

        if custom := self._get_custom_response("lookup_company_by_ogrn"):
            return custom

        return self.companies_by_ogrn.get(ogrn)

    async def suggest_companies(
        self,
        query: str,
        count: int = 10
    ) -> List[FakeCompanyInfo]:
        """
        Search companies by name, INN, or OGRN (autocomplete).

        Args:
            query: Search query
            count: Maximum number of results

        Returns:
            List of matching companies
        """
        self._record_call("suggest_companies", query, count=count)
        self._check_failure("suggest_companies")

        if custom := self._get_custom_response("suggest_companies"):
            return custom

        # Simple search in stored companies
        if len(query) < 3:
            return []

        results = []
        query_lower = query.lower()

        for company in self.companies_by_inn.values():
            if (
                query in company.inn or
                (company.ogrn and query in company.ogrn) or
                query_lower in company.name_full.lower() or
                (company.name_short and query_lower in company.name_short.lower())
            ):
                results.append(company)
                if len(results) >= count:
                    break

        return results


# =============================================================================
# EOF
# =============================================================================
