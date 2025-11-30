# =============================================================================
# File: app/company/commands.py
# Description: Company domain commands
# =============================================================================

from __future__ import annotations

from typing import Optional, List
from pydantic import Field, field_validator
import uuid
from decimal import Decimal

from app.infra.cqrs.command_bus import Command
from app.company.enums import CompanyType, UserCompanyRelationship


# =============================================================================
# Company Lifecycle Commands
# =============================================================================

class CreateCompanyCommand(Command):
    """Create a new company"""
    company_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(..., min_length=1, max_length=255)
    company_type: str = Field(default="company", description="company, project, or individual")
    created_by: uuid.UUID

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
    # If True, CompanyCreationSaga will create Telegram supergroup automatically
    create_telegram_group: bool = Field(default=False, description="Create Telegram supergroup via saga")
    telegram_group_title: Optional[str] = Field(None, max_length=255, description="Telegram group title (defaults to company name)")
    telegram_group_description: Optional[str] = Field(None, max_length=1000, description="Telegram group description")
    # If True, CompanyCreationSaga will create company chat (default: True)
    create_chat: bool = Field(default=True, description="Create company chat via saga")
    # If provided, saga will link this existing chat to the company
    link_chat_id: Optional[uuid.UUID] = Field(None, description="Existing chat ID to link to company")

    @field_validator('company_type')
    @classmethod
    def validate_company_type(cls, v: str) -> str:
        valid_types = [t.value for t in CompanyType]
        if v not in valid_types:
            raise ValueError(f"company_type must be one of {valid_types}")
        return v


class UpdateCompanyCommand(Command):
    """Update company details"""
    company_id: uuid.UUID
    updated_by: uuid.UUID

    # Only include changed fields
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

    @field_validator('company_type')
    @classmethod
    def validate_company_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid_types = [t.value for t in CompanyType]
        if v not in valid_types:
            raise ValueError(f"company_type must be one of {valid_types}")
        return v


class ArchiveCompanyCommand(Command):
    """Archive (soft delete) a company"""
    company_id: uuid.UUID
    archived_by: uuid.UUID
    reason: Optional[str] = Field(None, max_length=500)


class RestoreCompanyCommand(Command):
    """Restore an archived company"""
    company_id: uuid.UUID
    restored_by: uuid.UUID


class DeleteCompanyCommand(Command):
    """Permanently delete a company (hard delete)"""
    company_id: uuid.UUID
    deleted_by: uuid.UUID
    force: bool = Field(default=False, description="Bypass permission checks (for saga-initiated deletions)")


class RequestCompanyDeletionCommand(Command):
    """
    Request company deletion - triggers GroupDeletionSaga.

    TRUE SAGA Pattern: Handler queries all needed data and enriches
    CompanyDeleteRequested event. Saga uses ONLY enriched event data.

    preserve_company: If True, keep company record for future re-linking.
    """
    company_id: uuid.UUID
    deleted_by: uuid.UUID
    cascade: bool = Field(default=True, description="Cascade delete chats and messages")
    preserve_company: bool = Field(default=False, description="Keep company for re-linking to new Telegram group")


# =============================================================================
# User-Company Relationship Commands
# =============================================================================

class AddUserToCompanyCommand(Command):
    """Add a user to a company"""
    company_id: uuid.UUID
    user_id: uuid.UUID
    relationship_type: str = Field(default="participant", description="owner, participant, declarant, accountant, manager")
    added_by: uuid.UUID

    @field_validator('relationship_type')
    @classmethod
    def validate_relationship_type(cls, v: str) -> str:
        valid_types = [t.value for t in UserCompanyRelationship]
        if v not in valid_types:
            raise ValueError(f"relationship_type must be one of {valid_types}")
        return v


class RemoveUserFromCompanyCommand(Command):
    """Remove a user from a company"""
    company_id: uuid.UUID
    user_id: uuid.UUID
    removed_by: uuid.UUID
    reason: Optional[str] = Field(None, max_length=500)


class ChangeUserCompanyRoleCommand(Command):
    """Change a user's role in company"""
    company_id: uuid.UUID
    user_id: uuid.UUID
    new_relationship_type: str
    changed_by: uuid.UUID

    @field_validator('new_relationship_type')
    @classmethod
    def validate_relationship_type(cls, v: str) -> str:
        valid_types = [t.value for t in UserCompanyRelationship]
        if v not in valid_types:
            raise ValueError(f"new_relationship_type must be one of {valid_types}")
        return v


# =============================================================================
# Telegram Integration Commands
# =============================================================================

class CreateTelegramSupergroupCommand(Command):
    """Create a Telegram supergroup for company"""
    company_id: uuid.UUID
    telegram_group_id: int
    title: str = Field(..., max_length=255)
    username: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    invite_link: Optional[str] = Field(None, max_length=500)
    is_forum: bool = True
    created_by: uuid.UUID


class LinkTelegramSupergroupCommand(Command):
    """Link an existing Telegram supergroup to company"""
    company_id: uuid.UUID
    telegram_group_id: int
    linked_by: uuid.UUID


class UnlinkTelegramSupergroupCommand(Command):
    """Unlink a Telegram supergroup from company"""
    company_id: uuid.UUID
    telegram_group_id: int
    unlinked_by: uuid.UUID


class UpdateTelegramSupergroupCommand(Command):
    """Update Telegram supergroup info"""
    company_id: uuid.UUID
    telegram_group_id: int
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    invite_link: Optional[str] = Field(None, max_length=500)


class DeleteTelegramSupergroupCommand(Command):
    """Permanently delete a Telegram supergroup (hard delete from read model)"""
    telegram_group_id: int
    deleted_by: uuid.UUID
    reason: Optional[str] = Field(None, max_length=500)


# =============================================================================
# Balance Commands
# =============================================================================

class UpdateCompanyBalanceCommand(Command):
    """Update company balance"""
    company_id: uuid.UUID
    change_amount: Decimal
    reason: str = Field(..., min_length=1, max_length=500)
    reference_id: Optional[str] = Field(None, max_length=100, description="Order ID, transaction ID, etc.")
    updated_by: uuid.UUID
