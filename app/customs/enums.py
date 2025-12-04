# =============================================================================
# File: app/customs/enums.py
# Description: Shared enumerations for Customs domain
# =============================================================================

from enum import Enum


class DeclarationType(str, Enum):
    """Type of customs declaration."""
    IMPORT = "IM"
    EXPORT = "EX"
    TRANSIT = "TR"


class DocflowStatus(int, Enum):
    """
    Status of customs declaration in Kontur system.

    Maps to Kontur API docflow status values.
    """
    DRAFT = 0           # Not submitted yet
    SENT = 1            # Submitted to customs
    REGISTERED = 2      # Registered by customs (GTD number assigned)
    RELEASED = 3        # Goods released
    REJECTED = 4        # Declaration rejected
    CANCELLED = 5       # Declaration cancelled
    CORRECTION = 6      # Correction requested


class OrganizationType(int, Enum):
    """
    Type of organization in customs operations.

    Maps to Kontur API organization type values.
    """
    LEGAL_ENTITY = 0    # Russian legal entity (LLC, JSC, etc.)
    INDIVIDUAL = 1      # Individual entrepreneur (IP)
    NATURAL_PERSON = 2  # Natural person
    FOREIGN_ENTITY = 3  # Foreign organization


class DocumentType(str, Enum):
    """Types of customs documents."""
    DT = "dt"           # Declaration for goods (main form)
    DTS = "dts"         # Customs value declaration
    INVOICE = "invoice"
    CONTRACT = "contract"
    TRANSPORT = "transport"
    CERTIFICATE = "certificate"
    LICENSE = "license"
    OTHER = "other"


class DtsType(int, Enum):
    """Types of DTS (customs value declaration) calculations."""
    TRANSPORT = 1       # Transport costs
    INSURANCE = 2       # Insurance costs
    LOADING = 3         # Loading/unloading costs


class DistributeBy(int, Enum):
    """Distribution method for DTS calculations."""
    WEIGHT = 1          # Distribute by weight
    PRICE = 2           # Distribute by invoice price
    MANUAL = 3          # Manual distribution


class IncludeIn(int, Enum):
    """Where to include DTS costs."""
    PRICE = 1           # Include in price
    CUSTOMS_VALUE = 2   # Include in customs value
    STATISTICAL = 3     # Include in statistical value
