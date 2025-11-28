# =============================================================================
# File: app/api/models/company_api_models.py
# Description: Company domain API models (Pydantic v2)
# =============================================================================

from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
import uuid
from datetime import datetime
from decimal import Decimal


# =============================================================================
# Request Models
# =============================================================================

class CreateCompanyRequest(BaseModel):
    """Request to create a new company"""
    name: str = Field(..., min_length=1, max_length=255)
    company_type: str = Field(default="company", description="company, project, or individual")

    # Legal info (Russian business)
    vat: Optional[str] = Field(None, max_length=20, description="INN")
    ogrn: Optional[str] = Field(None, max_length=20)
    kpp: Optional[str] = Field(None, max_length=20)

    # Address
    postal_code: Optional[str] = Field(None, max_length=20)
    country_id: int = Field(default=190, description="Default Russia")
    city: Optional[str] = Field(None, max_length=100)
    street: Optional[str] = Field(None, max_length=255)

    # Contacts
    director: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)

    # Telegram contacts
    tg_dir: Optional[str] = Field(None, max_length=100)
    tg_accountant: Optional[str] = Field(None, max_length=100)
    tg_manager_1: Optional[str] = Field(None, max_length=100)
    tg_manager_2: Optional[str] = Field(None, max_length=100)
    tg_manager_3: Optional[str] = Field(None, max_length=100)
    tg_support: Optional[str] = Field(None, max_length=100)

    # Saga orchestration options
    # If True, CompanyCreationSaga will create Telegram group and chat automatically
    create_telegram_group: bool = Field(default=False, description="Create Telegram supergroup via saga")
    telegram_group_title: Optional[str] = Field(None, max_length=255, description="Telegram group title (defaults to company name)")
    telegram_group_description: Optional[str] = Field(None, max_length=1000, description="Telegram group description")
    # If provided, saga will link this existing chat to the company instead of creating a new one
    link_chat_id: Optional[uuid.UUID] = Field(None, description="Existing chat ID to link to company")


class UpdateCompanyRequest(BaseModel):
    """Request to update company details"""
    name: Optional[str] = Field(None, max_length=255)
    company_type: Optional[str] = None
    vat: Optional[str] = Field(None, max_length=20)
    ogrn: Optional[str] = Field(None, max_length=20)
    kpp: Optional[str] = Field(None, max_length=20)
    postal_code: Optional[str] = Field(None, max_length=20)
    country_id: Optional[int] = None
    city: Optional[str] = Field(None, max_length=100)
    street: Optional[str] = Field(None, max_length=255)
    director: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    tg_dir: Optional[str] = Field(None, max_length=100)
    tg_accountant: Optional[str] = Field(None, max_length=100)
    tg_manager_1: Optional[str] = Field(None, max_length=100)
    tg_manager_2: Optional[str] = Field(None, max_length=100)
    tg_manager_3: Optional[str] = Field(None, max_length=100)
    tg_support: Optional[str] = Field(None, max_length=100)


class ArchiveCompanyRequest(BaseModel):
    """Request to archive a company"""
    reason: Optional[str] = Field(None, max_length=500)


class AddUserToCompanyRequest(BaseModel):
    """Request to add user to company"""
    user_id: uuid.UUID
    relationship_type: str = Field(default="participant", description="owner, participant, declarant, accountant, manager")


class ChangeUserRoleRequest(BaseModel):
    """Request to change user's role in company"""
    new_relationship_type: str = Field(..., description="owner, participant, declarant, accountant, manager")


class RemoveUserRequest(BaseModel):
    """Request to remove user from company"""
    reason: Optional[str] = Field(None, max_length=500)


class CreateTelegramSupergroupRequest(BaseModel):
    """Request to create Telegram supergroup for company"""
    title: str = Field(..., max_length=255)
    username: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    is_forum: bool = True


class LinkTelegramSupergroupRequest(BaseModel):
    """Request to link existing Telegram supergroup"""
    telegram_group_id: int


class UpdateTelegramSupergroupRequest(BaseModel):
    """Request to update Telegram supergroup info"""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class UpdateBalanceRequest(BaseModel):
    """Request to update company balance"""
    change_amount: Decimal = Field(..., description="Positive to add, negative to subtract")
    reason: str = Field(..., min_length=1, max_length=500)
    reference_id: Optional[str] = Field(None, max_length=100, description="Order ID, transaction ID, etc.")


# =============================================================================
# Response Models
# =============================================================================

class CompanyResponse(BaseModel):
    """Generic company response"""
    id: uuid.UUID
    message: str = "Success"


class CompanyDetailResponse(BaseModel):
    """Full company details response"""
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

    # Counts
    balance: Decimal = Decimal("0.00")
    user_count: int = 0

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v),
            Decimal: lambda v: str(v)
        }
    )


class CompanySummaryResponse(BaseModel):
    """Company summary for list views"""
    id: uuid.UUID
    name: str
    company_type: str
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


class UserCompanyResponse(BaseModel):
    """User's company relationship"""
    company_id: uuid.UUID
    company_name: str
    company_type: str
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


class CompanyUserResponse(BaseModel):
    """Company user information"""
    user_id: uuid.UUID
    relationship_type: str
    joined_at: datetime
    is_active: bool = True
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_phone: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v)
        }
    )


class TelegramSupergroupResponse(BaseModel):
    """Telegram supergroup information"""
    telegram_group_id: int
    title: str
    username: Optional[str] = None
    description: Optional[str] = None
    invite_link: Optional[str] = None
    is_forum: bool = True
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )


class CreateSupergroupResponse(BaseModel):
    """Response after creating Telegram supergroup"""
    success: bool
    telegram_group_id: Optional[int] = None
    title: Optional[str] = None
    invite_link: Optional[str] = None
    error: Optional[str] = None


class BalanceResponse(BaseModel):
    """Company balance response"""
    company_id: uuid.UUID
    balance: Decimal
    last_updated: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v),
            Decimal: lambda v: str(v)
        }
    )


class BalanceTransactionResponse(BaseModel):
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

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v),
            Decimal: lambda v: str(v)
        }
    )


class BalanceHistoryResponse(BaseModel):
    """Balance history with transactions"""
    company_id: uuid.UUID
    current_balance: Decimal
    transactions: List[BalanceTransactionResponse] = Field(default_factory=list)
    total_count: int = 0

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            uuid.UUID: lambda v: str(v),
            Decimal: lambda v: str(v)
        }
    )
