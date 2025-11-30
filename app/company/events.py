# =============================================================================
# File: app/company/events.py
# Description: Company domain events
# =============================================================================

from __future__ import annotations

from typing import Literal, Optional, Dict, Any, List
from pydantic import Field
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.common.base.base_model import BaseEvent
from app.infra.event_bus.event_decorators import domain_event


# =============================================================================
# Company Lifecycle Events
# =============================================================================

@domain_event(category="domain")
class CompanyCreated(BaseEvent):
    """Event emitted when a new company is created"""
    event_type: Literal["CompanyCreated"] = "CompanyCreated"
    company_id: uuid.UUID
    name: str
    company_type: str = "company"  # company, project, individual
    created_by: uuid.UUID

    # Legal info (Russian business)
    vat: Optional[str] = None  # INN
    ogrn: Optional[str] = None
    kpp: Optional[str] = None

    # Address
    postal_code: Optional[str] = None
    country_id: int = 190  # Default Russia
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

    # Saga orchestration context (enriched data for CompanyCreationSaga)
    # If True, saga will create Telegram group automatically
    create_telegram_group: bool = False
    telegram_group_title: Optional[str] = None
    telegram_group_description: Optional[str] = None
    # If True, saga will create company chat (default: True for backward compat)
    create_chat: bool = True
    # If provided, saga will link this existing chat to the company
    link_chat_id: Optional[uuid.UUID] = None


@domain_event(category="domain")
class CompanyUpdated(BaseEvent):
    """Event emitted when company details are updated"""
    event_type: Literal["CompanyUpdated"] = "CompanyUpdated"
    company_id: uuid.UUID
    updated_by: uuid.UUID

    # Only include changed fields
    name: Optional[str] = None
    company_type: Optional[str] = None
    vat: Optional[str] = None
    ogrn: Optional[str] = None
    kpp: Optional[str] = None
    postal_code: Optional[str] = None
    country_id: Optional[int] = None
    city: Optional[str] = None
    street: Optional[str] = None
    director: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    tg_dir: Optional[str] = None
    tg_accountant: Optional[str] = None
    tg_manager_1: Optional[str] = None
    tg_manager_2: Optional[str] = None
    tg_manager_3: Optional[str] = None
    tg_support: Optional[str] = None


@domain_event(category="domain")
class CompanyArchived(BaseEvent):
    """Event emitted when a company is archived"""
    event_type: Literal["CompanyArchived"] = "CompanyArchived"
    company_id: uuid.UUID
    archived_by: uuid.UUID
    reason: Optional[str] = None


@domain_event(category="domain")
class CompanyRestored(BaseEvent):
    """Event emitted when an archived company is restored"""
    event_type: Literal["CompanyRestored"] = "CompanyRestored"
    company_id: uuid.UUID
    restored_by: uuid.UUID


@domain_event(category="domain")
class CompanyDeleted(BaseEvent):
    """Event emitted when a company is deleted"""
    event_type: Literal["CompanyDeleted"] = "CompanyDeleted"
    company_id: uuid.UUID
    deleted_by: uuid.UUID


@domain_event(category="domain")
class CompanyDeleteRequested(BaseEvent):
    """
    Event requesting company deletion - ENRICHED with cascade data.

    TRUE SAGA Pattern: Handler enriches this event with all data saga needs.
    Saga uses ONLY this event data, NO queries.

    preserve_company: If True, keep company record for re-linking to new Telegram group.
    """
    event_type: Literal["CompanyDeleteRequested"] = "CompanyDeleteRequested"
    company_id: uuid.UUID
    company_name: str
    deleted_by: uuid.UUID

    # ENRICHED DATA (queried by handler, NOT saga):
    telegram_group_id: Optional[int] = None
    chat_ids: List[uuid.UUID] = Field(default_factory=list)
    cascade: bool = True
    preserve_company: bool = False  # If True, keep company for future re-linking


# =============================================================================
# User-Company Relationship Events
# =============================================================================

@domain_event(category="domain")
class UserAddedToCompany(BaseEvent):
    """Event emitted when a user is added to a company"""
    event_type: Literal["UserAddedToCompany"] = "UserAddedToCompany"
    company_id: uuid.UUID
    user_id: uuid.UUID
    relationship_type: str = "participant"  # owner, participant, declarant, accountant, manager
    added_by: uuid.UUID


@domain_event(category="domain")
class UserRemovedFromCompany(BaseEvent):
    """Event emitted when a user is removed from a company"""
    event_type: Literal["UserRemovedFromCompany"] = "UserRemovedFromCompany"
    company_id: uuid.UUID
    user_id: uuid.UUID
    removed_by: uuid.UUID
    reason: Optional[str] = None


@domain_event(category="domain")
class UserCompanyRoleChanged(BaseEvent):
    """Event emitted when a user's role in company is changed"""
    event_type: Literal["UserCompanyRoleChanged"] = "UserCompanyRoleChanged"
    company_id: uuid.UUID
    user_id: uuid.UUID
    old_relationship_type: str
    new_relationship_type: str
    changed_by: uuid.UUID


# =============================================================================
# Telegram Integration Events
# =============================================================================

@domain_event(category="domain")
class TelegramSupergroupCreated(BaseEvent):
    """Event emitted when a Telegram supergroup is created for company"""
    event_type: Literal["TelegramSupergroupCreated"] = "TelegramSupergroupCreated"
    company_id: uuid.UUID
    telegram_group_id: int
    title: str
    username: Optional[str] = None
    description: Optional[str] = None
    invite_link: Optional[str] = None
    is_forum: bool = True
    created_by: uuid.UUID


@domain_event(category="domain")
class TelegramSupergroupLinked(BaseEvent):
    """Event emitted when an existing Telegram supergroup is linked to company"""
    event_type: Literal["TelegramSupergroupLinked"] = "TelegramSupergroupLinked"
    company_id: uuid.UUID
    telegram_group_id: int
    linked_by: uuid.UUID


@domain_event(category="domain")
class TelegramSupergroupUnlinked(BaseEvent):
    """Event emitted when a Telegram supergroup is unlinked from company"""
    event_type: Literal["TelegramSupergroupUnlinked"] = "TelegramSupergroupUnlinked"
    company_id: uuid.UUID
    telegram_group_id: int
    unlinked_by: uuid.UUID


@domain_event(category="domain")
class TelegramSupergroupUpdated(BaseEvent):
    """Event emitted when Telegram supergroup info is updated"""
    event_type: Literal["TelegramSupergroupUpdated"] = "TelegramSupergroupUpdated"
    company_id: uuid.UUID
    telegram_group_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    invite_link: Optional[str] = None


@domain_event(category="domain")
class TelegramSupergroupDeleted(BaseEvent):
    """Event emitted when a Telegram supergroup is permanently deleted"""
    event_type: Literal["TelegramSupergroupDeleted"] = "TelegramSupergroupDeleted"
    telegram_group_id: int
    company_id: Optional[uuid.UUID] = None  # May be None if supergroup wasn't linked
    deleted_by: uuid.UUID
    reason: Optional[str] = None


# =============================================================================
# Balance Events
# =============================================================================

@domain_event(category="domain")
class CompanyBalanceUpdated(BaseEvent):
    """Event emitted when company balance changes"""
    event_type: Literal["CompanyBalanceUpdated"] = "CompanyBalanceUpdated"
    company_id: uuid.UUID
    old_balance: Decimal
    new_balance: Decimal
    change_amount: Decimal
    reason: str
    reference_id: Optional[str] = None  # Order ID, transaction ID, etc.
    updated_by: uuid.UUID


# =============================================================================
# Event Type Registry
# =============================================================================

COMPANY_EVENT_TYPES = {
    "CompanyCreated": CompanyCreated,
    "CompanyUpdated": CompanyUpdated,
    "CompanyArchived": CompanyArchived,
    "CompanyRestored": CompanyRestored,
    "CompanyDeleted": CompanyDeleted,
    "CompanyDeleteRequested": CompanyDeleteRequested,
    "UserAddedToCompany": UserAddedToCompany,
    "UserRemovedFromCompany": UserRemovedFromCompany,
    "UserCompanyRoleChanged": UserCompanyRoleChanged,
    "TelegramSupergroupCreated": TelegramSupergroupCreated,
    "TelegramSupergroupLinked": TelegramSupergroupLinked,
    "TelegramSupergroupUnlinked": TelegramSupergroupUnlinked,
    "TelegramSupergroupUpdated": TelegramSupergroupUpdated,
    "TelegramSupergroupDeleted": TelegramSupergroupDeleted,
    "CompanyBalanceUpdated": CompanyBalanceUpdated,
}
