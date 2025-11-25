# =============================================================================
# File: app/company/queries.py
# Description: Company domain queries
# =============================================================================

from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field
import uuid
from datetime import datetime
from decimal import Decimal

from app.infra.cqrs.query_bus import Query


# =============================================================================
# Company Queries
# =============================================================================

class GetCompanyByIdQuery(Query):
    """Get company details by ID"""
    company_id: uuid.UUID


class GetCompaniesQuery(Query):
    """Get all companies (admin view)"""
    include_archived: bool = False
    include_deleted: bool = False
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class GetCompaniesByUserQuery(Query):
    """Get all companies for a user"""
    user_id: uuid.UUID
    include_archived: bool = False
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchCompaniesQuery(Query):
    """Search companies by name or VAT"""
    search_term: str = Field(..., min_length=1, max_length=100)
    limit: int = Field(default=20, ge=1, le=50)


class GetCompanyByVatQuery(Query):
    """Get company by VAT (INN)"""
    vat: str


# =============================================================================
# User-Company Relationship Queries
# =============================================================================

class GetCompanyUsersQuery(Query):
    """Get users of a company"""
    company_id: uuid.UUID
    include_inactive: bool = False


class GetUserCompanyRelationshipQuery(Query):
    """Check user's relationship with company"""
    company_id: uuid.UUID
    user_id: uuid.UUID


# =============================================================================
# Telegram Queries
# =============================================================================

class GetCompanyTelegramSupergroupsQuery(Query):
    """Get Telegram supergroups for a company"""
    company_id: uuid.UUID


class GetCompanyByTelegramGroupQuery(Query):
    """Get company by Telegram group ID"""
    telegram_group_id: int


# =============================================================================
# Balance Queries
# =============================================================================

class GetCompanyBalanceQuery(Query):
    """Get company balance"""
    company_id: uuid.UUID


class GetCompanyBalanceHistoryQuery(Query):
    """Get company balance transaction history"""
    company_id: uuid.UUID
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# =============================================================================
# Result Types
# =============================================================================

class CompanyDetail(BaseModel):
    """Company details for API response"""
    id: uuid.UUID
    name: str
    company_type: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool = True

    # Legal info
    vat: Optional[str] = None
    ogrn: Optional[str] = None
    kpp: Optional[str] = None

    # Address
    postal_code: Optional[str] = None
    country_id: int = 190
    city: Optional[str] = None
    street: Optional[str] = None

    # Contacts
    director: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    # Telegram contacts
    tg_dir: Optional[str] = None
    tg_accountant: Optional[str] = None
    tg_manager_1: Optional[str] = None
    tg_manager_2: Optional[str] = None
    tg_manager_3: Optional[str] = None
    tg_support: Optional[str] = None

    # Balance
    balance: Decimal = Decimal("0.00")

    # Counts
    user_count: int = 0


class CompanySummary(BaseModel):
    """Company summary for list views"""
    id: uuid.UUID
    name: str
    company_type: str
    vat: Optional[str] = None
    city: Optional[str] = None
    user_count: int = 0
    balance: Decimal = Decimal("0.00")
    is_active: bool = True


class UserCompanyInfo(BaseModel):
    """User's company relationship info"""
    company_id: uuid.UUID
    user_id: uuid.UUID
    relationship_type: str
    joined_at: datetime
    is_active: bool = True
    # Company details
    company_name: Optional[str] = None
    company_type: Optional[str] = None


class CompanyUserInfo(BaseModel):
    """Company user information"""
    user_id: uuid.UUID
    relationship_type: str
    joined_at: datetime
    is_active: bool = True
    # User details (joined from user table)
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_phone: Optional[str] = None


class TelegramSupergroupInfo(BaseModel):
    """Telegram supergroup information"""
    telegram_group_id: int
    title: str
    username: Optional[str] = None
    description: Optional[str] = None
    invite_link: Optional[str] = None
    is_forum: bool = True
    created_at: datetime


class BalanceInfo(BaseModel):
    """Company balance information"""
    company_id: uuid.UUID
    balance: Decimal
    last_updated: Optional[datetime] = None


class BalanceTransaction(BaseModel):
    """Balance transaction record"""
    id: uuid.UUID
    company_id: uuid.UUID
    old_balance: Decimal
    new_balance: Decimal
    change_amount: Decimal
    reason: str
    reference_id: Optional[str] = None
    updated_by: uuid.UUID
    created_at: datetime


class UserCompanyRelationship(BaseModel):
    """User-company relationship status"""
    company_id: uuid.UUID
    user_id: uuid.UUID
    is_member: bool
    relationship_type: Optional[str] = None
    joined_at: Optional[datetime] = None
