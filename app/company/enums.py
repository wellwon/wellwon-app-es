# =============================================================================
# File: app/company/enums.py
# Description: Company domain enumerations
# =============================================================================

from enum import Enum


class CompanyType(str, Enum):
    """Client types - both companies and projects are clients"""
    COMPANY = "company"      # Legal entity with VAT/OGRN/KPP
    PROJECT = "project"      # Individual/no legal requirements


class UserCompanyRelationship(str, Enum):
    """User relationship types with company"""
    OWNER = "owner"
    PARTICIPANT = "participant"
    DECLARANT = "declarant"
    ACCOUNTANT = "accountant"
    MANAGER = "manager"


class CompanyStatus(str, Enum):
    """Company status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
