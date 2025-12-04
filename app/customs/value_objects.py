# =============================================================================
# File: app/customs/value_objects.py
# Description: Value objects for Customs domain (immutable, no identity)
# =============================================================================

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List
from datetime import date


@dataclass(frozen=True)
class AddressInfo:
    """
    Address value object for organizations and customs operations.

    Immutable representation of a physical address.
    """
    country_code: str           # ISO 3166-1 alpha-2 (e.g., "RU", "CN")
    city: str
    street_house: str
    postal_code: Optional[str] = None
    region: Optional[str] = None
    district: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "country_code": self.country_code,
            "city": self.city,
            "street_house": self.street_house,
            "postal_code": self.postal_code,
            "region": self.region,
            "district": self.district,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AddressInfo":
        """Create from dictionary."""
        return cls(
            country_code=data.get("country_code", ""),
            city=data.get("city", ""),
            street_house=data.get("street_house", ""),
            postal_code=data.get("postal_code"),
            region=data.get("region"),
            district=data.get("district"),
        )


@dataclass(frozen=True)
class Document:
    """
    Document value object for customs declarations.

    Represents a document attached to a declaration (invoice, contract, etc.).
    """
    document_id: str            # Unique ID within declaration
    form_id: str                # Form type (e.g., "dt", "dts")
    name: str                   # Document name/title
    number: str                 # Document number
    date: str                   # Document date (ISO format)
    grafa44_code: str           # Customs document code (Grafa 44)
    belongs_to_all_goods: bool = True  # Applies to all goods in declaration
    file_id: Optional[str] = None      # Attached file ID (if uploaded)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "document_id": self.document_id,
            "form_id": self.form_id,
            "name": self.name,
            "number": self.number,
            "date": self.date,
            "grafa44_code": self.grafa44_code,
            "belongs_to_all_goods": self.belongs_to_all_goods,
            "file_id": self.file_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        """Create from dictionary."""
        return cls(
            document_id=data.get("document_id", ""),
            form_id=data.get("form_id", "dt"),
            name=data.get("name", ""),
            number=data.get("number", ""),
            date=data.get("date", ""),
            grafa44_code=data.get("grafa44_code", ""),
            belongs_to_all_goods=data.get("belongs_to_all_goods", True),
            file_id=data.get("file_id"),
        )


@dataclass(frozen=True)
class GoodItem:
    """
    Good item value object for customs declarations.

    Represents a single item/product in the declaration.
    """
    item_number: int            # Sequential number in declaration
    description: str            # Product description
    quantity: Decimal           # Quantity
    unit: str                   # Unit of measurement code
    customs_value: Decimal      # Customs value
    currency_code: str          # Currency code (e.g., "USD", "EUR", "RUB")
    hs_code: Optional[str] = None       # HS/TN VED code (10 digits)
    country_of_origin: Optional[str] = None  # ISO country code
    gross_weight: Optional[Decimal] = None   # Gross weight in kg
    net_weight: Optional[Decimal] = None     # Net weight in kg
    invoice_price: Optional[Decimal] = None  # Invoice price

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "item_number": self.item_number,
            "description": self.description,
            "quantity": str(self.quantity),
            "unit": self.unit,
            "customs_value": str(self.customs_value),
            "currency_code": self.currency_code,
            "hs_code": self.hs_code,
            "country_of_origin": self.country_of_origin,
            "gross_weight": str(self.gross_weight) if self.gross_weight else None,
            "net_weight": str(self.net_weight) if self.net_weight else None,
            "invoice_price": str(self.invoice_price) if self.invoice_price else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GoodItem":
        """Create from dictionary."""
        return cls(
            item_number=data.get("item_number", 0),
            description=data.get("description", ""),
            quantity=Decimal(data.get("quantity", "0")),
            unit=data.get("unit", ""),
            customs_value=Decimal(data.get("customs_value", "0")),
            currency_code=data.get("currency_code", "RUB"),
            hs_code=data.get("hs_code"),
            country_of_origin=data.get("country_of_origin"),
            gross_weight=Decimal(data["gross_weight"]) if data.get("gross_weight") else None,
            net_weight=Decimal(data["net_weight"]) if data.get("net_weight") else None,
            invoice_price=Decimal(data["invoice_price"]) if data.get("invoice_price") else None,
        )


@dataclass(frozen=True)
class DtsDistributionItem:
    """
    DTS distribution item for customs value calculations.

    Represents how costs are distributed across goods.
    """
    grafa: str                  # Field number in declaration
    distribute_by: int          # 1=weight, 2=price, 3=manual
    include_in: int             # 1=price, 2=customs_value, 3=statistical
    currency_code: str          # Currency code
    total: Decimal              # Total amount to distribute
    border_place: Optional[str] = None  # Border crossing point

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "grafa": self.grafa,
            "distribute_by": self.distribute_by,
            "include_in": self.include_in,
            "currency_code": self.currency_code,
            "total": str(self.total),
            "border_place": self.border_place,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DtsDistributionItem":
        """Create from dictionary."""
        return cls(
            grafa=data.get("grafa", ""),
            distribute_by=data.get("distribute_by", 1),
            include_in=data.get("include_in", 2),
            currency_code=data.get("currency_code", "USD"),
            total=Decimal(data.get("total", "0")),
            border_place=data.get("border_place"),
        )


@dataclass(frozen=True)
class CustomsMark:
    """
    Customs mark/stamp value object.

    Represents an official mark from Federal Customs Service (FTS).
    """
    mark_id: str
    mark_type: str              # Type of mark
    mark_text: str              # Mark content
    mark_date: str              # Date of mark (ISO format)
    official_name: Optional[str] = None  # Name of customs official

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "mark_id": self.mark_id,
            "mark_type": self.mark_type,
            "mark_text": self.mark_text,
            "mark_date": self.mark_date,
            "official_name": self.official_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CustomsMark":
        """Create from dictionary."""
        return cls(
            mark_id=data.get("mark_id", ""),
            mark_type=data.get("mark_type", ""),
            mark_text=data.get("mark_text", ""),
            mark_date=data.get("mark_date", ""),
            official_name=data.get("official_name"),
        )
