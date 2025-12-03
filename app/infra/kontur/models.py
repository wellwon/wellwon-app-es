# =============================================================================
# File: app/infra/kontur/models.py
# Description: Data models for Kontur Declarant API
# All models use Pydantic BaseModel v2 for system consistency and validation
# =============================================================================

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Enumerations
# =============================================================================

class OrganizationType(Enum):
    """Organization type codes"""
    LEGAL_ENTITY = 0    # Юридическое лицо
    INDIVIDUAL = 1      # ИП
    NATURAL_PERSON = 2  # Физическое лицо


class DocflowStatus(Enum):
    """Docflow status codes (subset - Kontur has 200+ statuses)"""
    DRAFT = 0
    SENT = 1
    REGISTERED = 2
    RELEASED = 3
    REJECTED = 4


class DeclarationType(Enum):
    """Declaration types (направления перемещения)"""
    IMPORT = "IM"
    EXPORT = "EX"
    TRANSIT = "TR"


# =============================================================================
# Shared/Common Models
# =============================================================================

class AddressInfo(BaseModel):
    """Address information (used across multiple resources)"""
    model_config = ConfigDict(populate_by_name=True)

    city: str = ""
    settlement: str = ""
    country_name: str = Field(default="", alias="countryName")
    country_code: str = Field(default="", alias="countryCode")
    postal_code: Optional[str] = Field(default=None, alias="postalCode")
    region: str = ""
    street_house: str = Field(default="", alias="streetHouse")
    house: str = ""
    room: Optional[str] = None
    territory_code: Optional[str] = Field(default=None, alias="territoryCode")
    address_text: Optional[str] = Field(default=None, alias="addressText")


class PersonInfo(BaseModel):
    """Person information for natural persons"""
    model_config = ConfigDict(populate_by_name=True)

    surname: str = ""
    name: str = ""
    patronymic: Optional[str] = None
    position: Optional[str] = Field(default=None, alias="post")


class IdentityCard(BaseModel):
    """Identity card/passport information"""
    model_config = ConfigDict(populate_by_name=True)

    document_type: str = Field(default="", alias="documentType")
    series: Optional[str] = None
    number: str = ""
    issue_date: Optional[str] = Field(default=None, alias="issueDate")
    issued_by: Optional[str] = Field(default=None, alias="issuedBy")


# =============================================================================
# CommonOrgs Models (Organizations/Contractors)
# =============================================================================

class CommonOrg(BaseModel):
    """Common organization model (contractors)"""
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    org_name: str = Field(default="", alias="orgName")
    short_name: str = Field(default="", alias="shortName")
    type: int = 0  # OrganizationType
    is_foreign: bool = Field(default=False, alias="isForeign")

    # Russian org fields
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    okpo: Optional[str] = None
    okato: Optional[str] = None
    oktmo: Optional[str] = None

    # Addresses
    legal_address: Optional[AddressInfo] = Field(default=None, alias="legalAddress")
    actual_address: Optional[AddressInfo] = Field(default=None, alias="actualAddress")

    # Person (for natural persons)
    person: Optional[PersonInfo] = None
    identity_card: Optional[IdentityCard] = Field(default=None, alias="identityCard")

    # Additional
    branch_description: Optional[str] = Field(default=None, alias="branchDescription")
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")


# =============================================================================
# Docflow Models
# =============================================================================

class DocflowDto(BaseModel):
    """Document flow (declaration workflow)"""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    declaration_type: str = Field(alias="declarationType")
    procedure: str
    status: int
    status_text: str = Field(alias="statusText")
    changed: int  # timestamp
    created: int  # timestamp
    process_id: Optional[str] = Field(default=None, alias="processId")
    gtd_number: Optional[str] = Field(default=None, alias="gtdNumber")
    singularity: Optional[str] = None
    customs: Optional[str] = None
    organization_id: Optional[str] = Field(default=None, alias="organizationId")
    employee_id: Optional[str] = Field(default=None, alias="employeeId")
    org_name: Optional[str] = Field(default=None, alias="orgName")
    inn: Optional[str] = None
    kpp: Optional[str] = None


class CreateDocflowRequest(BaseModel):
    """Request for creating docflow"""
    model_config = ConfigDict(populate_by_name=True)

    type: str
    procedure: str
    customs: str
    organization_id: str = Field(alias="organizationId")
    employee_id: str = Field(alias="employeeId")
    name: str
    singularity: Optional[str] = None


class CopyDocflowRequest(BaseModel):
    """Request for copying docflow"""
    model_config = ConfigDict(populate_by_name=True)

    copy_from_id: str = Field(alias="copyFromId")
    name: Optional[str] = None
    customs: Optional[str] = None
    organization_id: Optional[str] = Field(default=None, alias="organizationId")
    employee_id: Optional[str] = Field(default=None, alias="employeeId")


class SearchDocflowRequest(BaseModel):
    """Search docflows request"""
    model_config = ConfigDict(populate_by_name=True)

    query: Optional[str] = None
    procedure: Optional[str] = None
    type: Optional[str] = None
    created_from: Optional[int] = Field(default=None, alias="createdFrom")
    created_to: Optional[int] = Field(default=None, alias="createdTo")
    document_number: Optional[str] = Field(default=None, alias="documentNumber")
    consignee: Optional[str] = None
    consignor: Optional[str] = None


class DeclarationMark(BaseModel):
    """Declaration mark/note"""
    id: str
    code: str
    text: str
    created: int


class DocflowMessage(BaseModel):
    """Message in docflow"""
    id: str
    type: str
    direction: str  # incoming/outgoing
    created: int
    status: str
    text: Optional[str] = None


# =============================================================================
# Document Models
# =============================================================================

class DocumentRowDto(BaseModel):
    """Document in a docflow"""
    model_config = ConfigDict(populate_by_name=True)

    form_id: str = Field(alias="formId")
    document_id: str = Field(alias="documentId")
    name: str
    number: str
    date: str
    document_mode_id: str = Field(alias="documentModeId")
    grafa44_code: str = Field(alias="grafa44Code")
    providing_index: Optional[str] = Field(default=None, alias="providingIndex")
    is_common: bool = Field(default=False, alias="isCommon")
    belongs_to_all_goods: bool = Field(default=False, alias="belongsToAllGoods")


class CreateDocumentRequest(BaseModel):
    """Request for creating document"""
    model_config = ConfigDict(populate_by_name=True)

    name: str
    number: str
    date: str
    document_mode_id: str = Field(alias="documentModeId")
    grafa44_code: str = Field(alias="grafa44Code")
    providing_index: Optional[str] = Field(default=None, alias="providingIndex")
    is_common: bool = Field(default=False, alias="isCommon")
    belongs_to_all_goods: bool = Field(default=False, alias="belongsToAllGoods")
    copy_data_from_dt: bool = Field(default=False, alias="copyDataFromDt")
    copy_if_exists: bool = Field(default=False, alias="copyIfExists")


class DistributionItem(BaseModel):
    """Distribution item for DTS calculator"""
    model_config = ConfigDict(populate_by_name=True)

    grafa: str
    distribute_by: int = Field(alias="distributeBy")  # 1=weight, 2=price, 3=manual
    include_in: int = Field(alias="includeIn")  # 1=price, 2=customs_value, 3=statistical_value
    currency_code: str = Field(alias="currencyCode")
    total: float
    border_place: Optional[str] = Field(default=None, alias="borderPlace")


# =============================================================================
# Form Models
# =============================================================================

class FormImportRequest(BaseModel):
    """Request for importing goods data"""
    goods: List[Dict[str, Any]] = Field(default_factory=list)


class FormJsonUpdateRequest(BaseModel):
    """Request for JSON form update"""
    data: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Options Models (Reference Data)
# =============================================================================

class OrganizationOption(BaseModel):
    """Organization from options"""
    id: str
    name: str


class EmployeeOption(BaseModel):
    """Employee from options"""
    id: str
    name: str
    position: str


class CustomsOption(BaseModel):
    """Customs post from options"""
    code: str
    name: str


class DeclarationTypeOption(BaseModel):
    """Declaration type option"""
    code: str
    name: str


# =============================================================================
# Template Models
# =============================================================================

class JsonTemplate(BaseModel):
    """JSON template metadata"""
    model_config = ConfigDict(populate_by_name=True)

    document_mode_id: str = Field(alias="documentModeId")
    name: str
    description: Optional[str] = None


# =============================================================================
# Vehicle Payment Models
# =============================================================================

class VehiclePaymentRequest(BaseModel):
    """Request for vehicle payment calculation"""
    model_config = ConfigDict(populate_by_name=True)

    vehicle_type: str = Field(alias="vehicleType")
    engine_volume: float = Field(alias="engineVolume")
    year: int
    customs_value: float = Field(alias="customsValue")
    currency_code: str = Field(alias="currencyCode")


class VehiclePaymentResult(BaseModel):
    """Result of vehicle payment calculation"""
    model_config = ConfigDict(populate_by_name=True)

    total_amount: float = Field(alias="totalAmount")
    customs_duty: float = Field(alias="customsDuty")
    excise: float
    vat: float
    currency_code: str = Field(alias="currencyCode")
