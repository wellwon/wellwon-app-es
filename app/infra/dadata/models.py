# =============================================================================
# File: app/infra/dadata/models.py — DaData Response Models
# =============================================================================

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict


@dataclass
class AddressInfo:
    """Company address information"""
    value: str = ""
    unrestricted_value: str = ""
    postal_code: Optional[str] = None
    country: str = ""
    region: str = ""
    city: str = ""
    street: str = ""
    house: str = ""
    flat: Optional[str] = None


@dataclass
class ManagementInfo:
    """Company management information"""
    name: str = ""
    post: str = ""
    disqualified: Optional[bool] = None


@dataclass
class CompanyInfo:
    """Parsed company information from DaData"""
    # Basic info
    inn: str = ""
    kpp: str = ""
    ogrn: str = ""
    okpo: Optional[str] = None
    okato: Optional[str] = None
    oktmo: Optional[str] = None
    okogu: Optional[str] = None
    okfs: Optional[str] = None
    okved: Optional[str] = None
    okved_type: str = "2014"

    # Names
    name_short: str = ""
    name_full: str = ""
    name_short_with_opf: str = ""
    name_full_with_opf: str = ""

    # Organizational form
    opf_code: str = ""
    opf_short: str = ""
    opf_full: str = ""

    # Status
    status: str = ""
    type: str = ""  # LEGAL or INDIVIDUAL

    # Address
    address: Optional[AddressInfo] = None
    address_value: str = ""

    # Management
    management: Optional[ManagementInfo] = None
    director_name: str = ""
    director_post: str = ""

    # Dates
    registration_date: Optional[str] = None
    liquidation_date: Optional[str] = None

    # Capital
    capital_value: Optional[float] = None
    capital_type: Optional[str] = None

    # Contact
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)

    # Raw data for frontend compatibility
    raw_data: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dadata_suggestion(cls, data: Dict[str, Any]) -> "CompanyInfo":
        """Create CompanyInfo from DaData suggestion data"""
        company_data = data.get("data", {})

        # Parse address
        address_data = company_data.get("address", {})
        address = None
        address_value = ""
        if address_data:
            address = AddressInfo(
                value=address_data.get("value", ""),
                unrestricted_value=address_data.get("unrestricted_value", ""),
                postal_code=address_data.get("data", {}).get("postal_code"),
                country=address_data.get("data", {}).get("country", ""),
                region=address_data.get("data", {}).get("region", ""),
                city=address_data.get("data", {}).get("city", ""),
                street=address_data.get("data", {}).get("street", ""),
                house=address_data.get("data", {}).get("house", ""),
                flat=address_data.get("data", {}).get("flat"),
            )
            address_value = address_data.get("value", "")

        # Parse management
        management_data = company_data.get("management", {})
        management = None
        director_name = ""
        director_post = ""
        if management_data:
            management = ManagementInfo(
                name=management_data.get("name", ""),
                post=management_data.get("post", ""),
                disqualified=management_data.get("disqualified"),
            )
            director_name = management_data.get("name", "")
            director_post = management_data.get("post", "")

        # Parse names
        name_data = company_data.get("name", {})

        # Parse OPF (organizational form)
        opf_data = company_data.get("opf", {})

        # Parse state/status
        state_data = company_data.get("state", {})

        # Parse capital
        capital_data = company_data.get("capital", {})

        # Parse contacts
        emails = [e.get("value", "") for e in company_data.get("emails", []) if e.get("value")]
        phones = [p.get("value", "") for p in company_data.get("phones", []) if p.get("value")]

        return cls(
            inn=company_data.get("inn", ""),
            kpp=company_data.get("kpp", ""),
            ogrn=company_data.get("ogrn", ""),
            okpo=company_data.get("okpo"),
            okato=company_data.get("okato"),
            oktmo=company_data.get("oktmo"),
            okogu=company_data.get("okogu"),
            okfs=company_data.get("okfs"),
            okved=company_data.get("okved"),
            okved_type=company_data.get("okved_type", "2014"),
            name_short=name_data.get("short", ""),
            name_full=name_data.get("full", ""),
            name_short_with_opf=name_data.get("short_with_opf", ""),
            name_full_with_opf=name_data.get("full_with_opf", ""),
            opf_code=opf_data.get("code", ""),
            opf_short=opf_data.get("short", ""),
            opf_full=opf_data.get("full", ""),
            status=state_data.get("status", ""),
            type=company_data.get("type", ""),
            address=address,
            address_value=address_value,
            management=management,
            director_name=director_name,
            director_post=director_post,
            registration_date=state_data.get("registration_date"),
            liquidation_date=state_data.get("liquidation_date"),
            capital_value=capital_data.get("value") if capital_data else None,
            capital_type=capital_data.get("type") if capital_data else None,
            emails=emails,
            phones=phones,
            raw_data=data,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "inn": self.inn,
            "kpp": self.kpp,
            "ogrn": self.ogrn,
            "okpo": self.okpo,
            "okved": self.okved,
            "name_short": self.name_short,
            "name_full": self.name_full,
            "name_short_with_opf": self.name_short_with_opf,
            "name_full_with_opf": self.name_full_with_opf,
            "opf_short": self.opf_short,
            "opf_full": self.opf_full,
            "status": self.status,
            "type": self.type,
            "address": self.address_value,
            "director_name": self.director_name,
            "director_post": self.director_post,
            "registration_date": self.registration_date,
            "liquidation_date": self.liquidation_date,
            "capital_value": self.capital_value,
            "emails": self.emails,
            "phones": self.phones,
        }


@dataclass
class DaDataResponse:
    """Full DaData API response"""
    suggestions: List[CompanyInfo] = field(default_factory=list)
    raw_response: Optional[Dict[str, Any]] = None

    @classmethod
    def from_api_response(cls, response_data: Dict[str, Any]) -> "DaDataResponse":
        """Parse DaData API response"""
        suggestions = []
        for suggestion in response_data.get("suggestions", []):
            company_info = CompanyInfo.from_dadata_suggestion(suggestion)
            suggestions.append(company_info)

        return cls(suggestions=suggestions, raw_response=response_data)

    @property
    def first(self) -> Optional[CompanyInfo]:
        """Get first suggestion if exists"""
        return self.suggestions[0] if self.suggestions else None

    @property
    def found(self) -> bool:
        """Check if any suggestions found"""
        return len(self.suggestions) > 0
