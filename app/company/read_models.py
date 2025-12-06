# =============================================================================
# File: app/company/read_models.py
# Description: Company domain read models for database projections
# =============================================================================

from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
import uuid
from datetime import datetime
from decimal import Decimal


class CompanyReadModel(BaseModel):
    """Read model for company details (PostgreSQL table: companies)"""
    id: uuid.UUID
    name: str
    client_type: str  # company, project
    created_by: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool = True
    is_deleted: bool = False

    # Legal info (Russian business)
    vat: Optional[str] = None  # INN
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

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: int = 0

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v),
            Decimal: lambda v: str(v)
        }
    )


class UserCompanyReadModel(BaseModel):
    """Read model for user-company relationships (PostgreSQL table: user_companies)"""
    id: uuid.UUID
    company_id: uuid.UUID
    user_id: uuid.UUID
    relationship_type: str = "participant"  # owner, participant, declarant, accountant, manager
    joined_at: datetime  # Maps from assigned_at column via alias
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v)
        }
    )


class TelegramSupergroupReadModel(BaseModel):
    """
    Read model for Telegram supergroups (PostgreSQL table: telegram_supergroups).

    Note: The table uses BIGINT for id which IS the Telegram group ID.
    company_id is UUID (FK to companies.id which is UUID).
    """
    id: int  # Telegram group ID (BIGINT primary key)
    company_id: Optional[uuid.UUID] = None  # FK to companies.id (UUID)
    title: str
    username: Optional[str] = None
    description: Optional[str] = None
    invite_link: Optional[str] = None
    member_count: int = 0
    is_forum: bool = False
    is_active: bool = True
    bot_is_admin: bool = False
    status_emoji: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        }
    )

    @property
    def telegram_group_id(self) -> int:
        """Alias for id - the Telegram group ID."""
        return self.id


class BalanceTransactionReadModel(BaseModel):
    """Read model for balance transactions (PostgreSQL table: company_balance_transactions)"""
    id: uuid.UUID
    company_id: uuid.UUID
    old_balance: Decimal
    new_balance: Decimal
    change_amount: Decimal
    reason: str
    reference_id: Optional[str] = None
    updated_by: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v),
            Decimal: lambda v: str(v)
        }
    )


# =============================================================================
# Composite Read Models (with joins)
# =============================================================================

class CompanyWithUsersReadModel(BaseModel):
    """Company with full user list"""
    company: CompanyReadModel
    users: List[UserCompanyReadModel] = Field(default_factory=list)


class CompanyWithTelegramReadModel(BaseModel):
    """Company with Telegram supergroups"""
    company: CompanyReadModel
    telegram_supergroups: List[TelegramSupergroupReadModel] = Field(default_factory=list)


class UserCompanyWithDetailsReadModel(BaseModel):
    """User-company relationship with user details"""
    user_company: UserCompanyReadModel
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_avatar_url: Optional[str] = None


class CompanyListItemReadModel(BaseModel):
    """Company item for list views with aggregated data"""
    id: uuid.UUID
    name: str
    client_type: str  # company, project
    vat: Optional[str] = None
    city: Optional[str] = None
    user_count: int = 0
    balance: Decimal = Decimal("0.00")
    is_active: bool = True
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v),
            Decimal: lambda v: str(v)
        }
    )


class UserCompanyListItemReadModel(BaseModel):
    """Company item for user's company list"""
    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str
    client_type: str  # company, project
    relationship_type: str
    joined_at: datetime
    is_active: bool = True

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v)
        }
    )
