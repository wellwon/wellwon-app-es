# =============================================================================
# File: app/company/aggregate.py
# Description: Company domain aggregate with Event Sourcing
# =============================================================================

from __future__ import annotations

from typing import List, Optional, Dict, Any, Set
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid
import logging
from decimal import Decimal

from app.common.base.base_model import BaseEvent
from app.company.events import (
    CompanyCreated,
    CompanyUpdated,
    CompanyArchived,
    CompanyRestored,
    CompanyDeleted,
    UserAddedToCompany,
    UserRemovedFromCompany,
    UserCompanyRoleChanged,
    TelegramSupergroupCreated,
    TelegramSupergroupLinked,
    TelegramSupergroupUnlinked,
    TelegramSupergroupUpdated,
    TelegramSupergroupDeleted,
    CompanyBalanceUpdated,
)
from app.company.exceptions import (
    CompanyAlreadyExistsError,
    CompanyInactiveError,
    UserNotInCompanyError,
    UserAlreadyInCompanyError,
    InsufficientCompanyPermissionsError,
    TelegramSupergroupAlreadyLinkedError,
    TelegramSupergroupNotFoundError,
    InsufficientBalanceError,
    CannotRemoveOwnerError,
)
from app.company.enums import UserCompanyRelationship

log = logging.getLogger("wellwon.company.aggregate")


# =============================================================================
# User-Company Relationship State (embedded in aggregate state)
# =============================================================================

class UserCompanyState(BaseModel):
    """State of a user's relationship with company"""
    user_id: uuid.UUID
    relationship_type: str = "participant"
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True


# =============================================================================
# Telegram Supergroup State
# =============================================================================

class TelegramSupergroupState(BaseModel):
    """State of a Telegram supergroup linked to company"""
    telegram_group_id: int
    title: str
    username: Optional[str] = None
    description: Optional[str] = None
    invite_link: Optional[str] = None
    is_forum: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Company Aggregate State
# =============================================================================

class CompanyAggregateState(BaseModel):
    """In-memory state for Company aggregate"""
    company_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    company_type: str = "company"  # company, project, individual
    created_by: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_active: bool = True
    is_deleted: bool = False

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

    # Balance
    balance: Decimal = Decimal("0.00")

    # Users (user_id -> UserCompanyState)
    users: Dict[str, UserCompanyState] = Field(default_factory=dict)

    # Telegram supergroups (telegram_group_id -> TelegramSupergroupState)
    telegram_supergroups: Dict[str, TelegramSupergroupState] = Field(default_factory=dict)

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Company Aggregate
# =============================================================================

class CompanyAggregate:
    """
    Company Aggregate Root for Event Sourcing.

    Responsibilities:
    - Validate business rules for company operations
    - Emit domain events
    - Maintain aggregate state from events
    """

    def __init__(self, company_id: uuid.UUID):
        self.id: uuid.UUID = company_id
        self.version: int = 0
        self.state: CompanyAggregateState = CompanyAggregateState(company_id=company_id)
        self._uncommitted_events: List[BaseEvent] = []

    # =========================================================================
    # Event Management
    # =========================================================================

    def get_uncommitted_events(self) -> List[BaseEvent]:
        """Get events that haven't been committed to event store"""
        return self._uncommitted_events

    def mark_events_committed(self) -> None:
        """Mark all events as committed"""
        self._uncommitted_events.clear()

    def _apply_and_record(self, event: BaseEvent) -> None:
        """Apply event to state and record for commit"""
        self._apply(event)
        self._uncommitted_events.append(event)
        self.version += 1

    # =========================================================================
    # Company Lifecycle Methods
    # =========================================================================

    def create_company(
        self,
        name: str,
        company_type: str,
        created_by: uuid.UUID,
        vat: Optional[str] = None,
        ogrn: Optional[str] = None,
        kpp: Optional[str] = None,
        postal_code: Optional[str] = None,
        country_id: int = 190,
        city: Optional[str] = None,
        street: Optional[str] = None,
        director: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        tg_dir: Optional[str] = None,
        tg_accountant: Optional[str] = None,
        tg_manager_1: Optional[str] = None,
        tg_manager_2: Optional[str] = None,
        tg_manager_3: Optional[str] = None,
        tg_support: Optional[str] = None,
        # Saga orchestration options (enriches event for CompanyCreationSaga)
        create_telegram_group: bool = False,
        telegram_group_title: Optional[str] = None,
        telegram_group_description: Optional[str] = None,
        create_chat: bool = True,
        link_chat_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Create a new company"""
        if self.version > 0:
            raise CompanyAlreadyExistsError(str(self.id))

        event = CompanyCreated(
            company_id=self.id,
            name=name,
            company_type=company_type,
            created_by=created_by,
            vat=vat,
            ogrn=ogrn,
            kpp=kpp,
            postal_code=postal_code,
            country_id=country_id,
            city=city,
            street=street,
            director=director,
            email=email,
            phone=phone,
            tg_dir=tg_dir,
            tg_accountant=tg_accountant,
            tg_manager_1=tg_manager_1,
            tg_manager_2=tg_manager_2,
            tg_manager_3=tg_manager_3,
            tg_support=tg_support,
            # Saga orchestration context
            create_telegram_group=create_telegram_group,
            telegram_group_title=telegram_group_title or name,  # Default to company name
            telegram_group_description=telegram_group_description or f"Рабочая группа компании {name}",
            create_chat=create_chat,
            link_chat_id=link_chat_id,
        )
        self._apply_and_record(event)

    def update_company(
        self,
        updated_by: uuid.UUID,
        name: Optional[str] = None,
        company_type: Optional[str] = None,
        vat: Optional[str] = None,
        ogrn: Optional[str] = None,
        kpp: Optional[str] = None,
        postal_code: Optional[str] = None,
        country_id: Optional[int] = None,
        city: Optional[str] = None,
        street: Optional[str] = None,
        director: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        tg_dir: Optional[str] = None,
        tg_accountant: Optional[str] = None,
        tg_manager_1: Optional[str] = None,
        tg_manager_2: Optional[str] = None,
        tg_manager_3: Optional[str] = None,
        tg_support: Optional[str] = None,
    ) -> None:
        """Update company details"""
        self._ensure_active()
        self._ensure_user_in_company(updated_by)

        event = CompanyUpdated(
            company_id=self.id,
            updated_by=updated_by,
            name=name,
            company_type=company_type,
            vat=vat,
            ogrn=ogrn,
            kpp=kpp,
            postal_code=postal_code,
            country_id=country_id,
            city=city,
            street=street,
            director=director,
            email=email,
            phone=phone,
            tg_dir=tg_dir,
            tg_accountant=tg_accountant,
            tg_manager_1=tg_manager_1,
            tg_manager_2=tg_manager_2,
            tg_manager_3=tg_manager_3,
            tg_support=tg_support,
        )
        self._apply_and_record(event)

    def archive_company(self, archived_by: uuid.UUID, reason: Optional[str] = None) -> None:
        """Archive the company"""
        self._ensure_active()
        self._ensure_owner(archived_by)

        event = CompanyArchived(
            company_id=self.id,
            archived_by=archived_by,
            reason=reason,
        )
        self._apply_and_record(event)

    def restore_company(self, restored_by: uuid.UUID) -> None:
        """Restore an archived company"""
        if self.state.is_active:
            raise CompanyInactiveError(str(self.id))  # Already active

        event = CompanyRestored(
            company_id=self.id,
            restored_by=restored_by,
        )
        self._apply_and_record(event)

    def delete_company(self, deleted_by: uuid.UUID, force: bool = False) -> None:
        """Permanently delete a company

        Args:
            deleted_by: User ID performing deletion
            force: If True, bypass permission checks (for saga-initiated deletions)
        """
        if not force:
            self._ensure_owner(deleted_by)

        event = CompanyDeleted(
            company_id=self.id,
            deleted_by=deleted_by,
        )
        self._apply_and_record(event)

    # =========================================================================
    # User-Company Relationship Methods
    # =========================================================================

    def add_user(
        self,
        user_id: uuid.UUID,
        relationship_type: str = "participant",
        added_by: uuid.UUID = None,
    ) -> None:
        """Add a user to the company"""
        self._ensure_active()

        user_key = str(user_id)
        if user_key in self.state.users and self.state.users[user_key].is_active:
            raise UserAlreadyInCompanyError(str(self.id), str(user_id))

        event = UserAddedToCompany(
            company_id=self.id,
            user_id=user_id,
            relationship_type=relationship_type,
            added_by=added_by,
        )
        self._apply_and_record(event)

    def remove_user(
        self,
        user_id: uuid.UUID,
        removed_by: uuid.UUID,
        reason: Optional[str] = None,
    ) -> None:
        """Remove a user from the company"""
        self._ensure_active()
        self._ensure_user_in_company(user_id)

        # Cannot remove owner
        user_key = str(user_id)
        if self.state.users[user_key].relationship_type == UserCompanyRelationship.OWNER.value:
            raise CannotRemoveOwnerError(str(self.id), str(user_id))

        event = UserRemovedFromCompany(
            company_id=self.id,
            user_id=user_id,
            removed_by=removed_by,
            reason=reason,
        )
        self._apply_and_record(event)

    def change_user_role(
        self,
        user_id: uuid.UUID,
        new_relationship_type: str,
        changed_by: uuid.UUID,
    ) -> None:
        """Change a user's role in the company"""
        self._ensure_active()
        self._ensure_user_in_company(user_id)
        self._ensure_owner(changed_by)

        user_key = str(user_id)
        old_relationship_type = self.state.users[user_key].relationship_type

        if old_relationship_type == new_relationship_type:
            return  # No change needed

        event = UserCompanyRoleChanged(
            company_id=self.id,
            user_id=user_id,
            old_relationship_type=old_relationship_type,
            new_relationship_type=new_relationship_type,
            changed_by=changed_by,
        )
        self._apply_and_record(event)

    # =========================================================================
    # Telegram Supergroup Methods
    # =========================================================================

    def create_telegram_supergroup(
        self,
        telegram_group_id: int,
        title: str,
        created_by: uuid.UUID,
        username: Optional[str] = None,
        description: Optional[str] = None,
        invite_link: Optional[str] = None,
        is_forum: bool = True,
    ) -> None:
        """Create and link a Telegram supergroup"""
        self._ensure_active()

        group_key = str(telegram_group_id)
        if group_key in self.state.telegram_supergroups:
            raise TelegramSupergroupAlreadyLinkedError(str(self.id), telegram_group_id)

        event = TelegramSupergroupCreated(
            company_id=self.id,
            telegram_group_id=telegram_group_id,
            title=title,
            username=username,
            description=description,
            invite_link=invite_link,
            is_forum=is_forum,
            created_by=created_by,
        )
        self._apply_and_record(event)

    def link_telegram_supergroup(
        self,
        telegram_group_id: int,
        linked_by: uuid.UUID,
    ) -> None:
        """Link an existing Telegram supergroup"""
        self._ensure_active()

        group_key = str(telegram_group_id)
        if group_key in self.state.telegram_supergroups:
            raise TelegramSupergroupAlreadyLinkedError(str(self.id), telegram_group_id)

        event = TelegramSupergroupLinked(
            company_id=self.id,
            telegram_group_id=telegram_group_id,
            linked_by=linked_by,
        )
        self._apply_and_record(event)

    def unlink_telegram_supergroup(
        self,
        telegram_group_id: int,
        unlinked_by: uuid.UUID,
    ) -> None:
        """Unlink a Telegram supergroup"""
        self._ensure_active()

        group_key = str(telegram_group_id)
        if group_key not in self.state.telegram_supergroups:
            raise TelegramSupergroupNotFoundError(str(self.id), telegram_group_id)

        event = TelegramSupergroupUnlinked(
            company_id=self.id,
            telegram_group_id=telegram_group_id,
            unlinked_by=unlinked_by,
        )
        self._apply_and_record(event)

    def update_telegram_supergroup(
        self,
        telegram_group_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        invite_link: Optional[str] = None,
    ) -> None:
        """Update Telegram supergroup info"""
        self._ensure_active()

        group_key = str(telegram_group_id)
        if group_key not in self.state.telegram_supergroups:
            raise TelegramSupergroupNotFoundError(str(self.id), telegram_group_id)

        event = TelegramSupergroupUpdated(
            company_id=self.id,
            telegram_group_id=telegram_group_id,
            title=title,
            description=description,
            invite_link=invite_link,
        )
        self._apply_and_record(event)

    def delete_telegram_supergroup(
        self,
        telegram_group_id: int,
        deleted_by: uuid.UUID,
        company_id: Optional[uuid.UUID] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Permanently delete a Telegram supergroup"""
        # No validation needed - supergroup might not be in aggregate state
        # if it was created without being linked to a company

        event = TelegramSupergroupDeleted(
            telegram_group_id=telegram_group_id,
            company_id=company_id,
            deleted_by=deleted_by,
            reason=reason,
        )
        self._apply_and_record(event)

    # =========================================================================
    # Balance Methods
    # =========================================================================

    def update_balance(
        self,
        change_amount: Decimal,
        reason: str,
        updated_by: uuid.UUID,
        reference_id: Optional[str] = None,
    ) -> None:
        """Update company balance"""
        self._ensure_active()

        old_balance = self.state.balance
        new_balance = old_balance + change_amount

        # Don't allow negative balance
        if new_balance < Decimal("0"):
            raise InsufficientBalanceError(
                str(self.id),
                str(abs(change_amount)),
                str(old_balance)
            )

        event = CompanyBalanceUpdated(
            company_id=self.id,
            old_balance=old_balance,
            new_balance=new_balance,
            change_amount=change_amount,
            reason=reason,
            reference_id=reference_id,
            updated_by=updated_by,
        )
        self._apply_and_record(event)

    # =========================================================================
    # Validation Helpers
    # =========================================================================

    def _ensure_active(self) -> None:
        """Ensure company is active"""
        if not self.state.is_active or self.state.is_deleted:
            raise CompanyInactiveError(str(self.id))

    def _ensure_user_in_company(self, user_id: uuid.UUID) -> None:
        """Ensure user is associated with the company"""
        user_key = str(user_id)
        if user_key not in self.state.users:
            raise UserNotInCompanyError(str(self.id), str(user_id))
        if not self.state.users[user_key].is_active:
            raise UserNotInCompanyError(str(self.id), str(user_id))

    def _ensure_owner(self, user_id: uuid.UUID) -> None:
        """Ensure user is an owner"""
        user_key = str(user_id)
        self._ensure_user_in_company(user_id)
        if self.state.users[user_key].relationship_type != UserCompanyRelationship.OWNER.value:
            raise InsufficientCompanyPermissionsError(str(user_id), "perform owner action")

    def is_user_in_company(self, user_id: uuid.UUID) -> bool:
        """Check if user is associated with company"""
        user_key = str(user_id)
        if user_key not in self.state.users:
            return False
        return self.state.users[user_key].is_active

    def get_user_count(self) -> int:
        """Get count of active users"""
        return sum(1 for u in self.state.users.values() if u.is_active)

    # =========================================================================
    # Event Application (State Updates)
    # =========================================================================

    def _apply(self, event: BaseEvent) -> None:
        """Route event to appropriate handler"""
        handlers = {
            CompanyCreated: self._on_company_created,
            CompanyUpdated: self._on_company_updated,
            CompanyArchived: self._on_company_archived,
            CompanyRestored: self._on_company_restored,
            CompanyDeleted: self._on_company_deleted,
            UserAddedToCompany: self._on_user_added,
            UserRemovedFromCompany: self._on_user_removed,
            UserCompanyRoleChanged: self._on_user_role_changed,
            TelegramSupergroupCreated: self._on_telegram_supergroup_created,
            TelegramSupergroupLinked: self._on_telegram_supergroup_linked,
            TelegramSupergroupUnlinked: self._on_telegram_supergroup_unlinked,
            TelegramSupergroupUpdated: self._on_telegram_supergroup_updated,
            TelegramSupergroupDeleted: self._on_telegram_supergroup_deleted,
            CompanyBalanceUpdated: self._on_balance_updated,
        }

        handler = handlers.get(type(event))
        if handler:
            handler(event)

    def _on_company_created(self, event: CompanyCreated) -> None:
        self.state.company_id = event.company_id
        self.state.name = event.name
        self.state.company_type = event.company_type
        self.state.created_by = event.created_by
        self.state.created_at = event.timestamp
        self.state.is_active = True

        # Legal info
        self.state.vat = event.vat
        self.state.ogrn = event.ogrn
        self.state.kpp = event.kpp

        # Address
        self.state.postal_code = event.postal_code
        self.state.country_id = event.country_id
        self.state.city = event.city
        self.state.street = event.street

        # Contacts
        self.state.director = event.director
        self.state.email = event.email
        self.state.phone = event.phone

        # Telegram contacts
        self.state.tg_dir = event.tg_dir
        self.state.tg_accountant = event.tg_accountant
        self.state.tg_manager_1 = event.tg_manager_1
        self.state.tg_manager_2 = event.tg_manager_2
        self.state.tg_manager_3 = event.tg_manager_3
        self.state.tg_support = event.tg_support

    def _on_company_updated(self, event: CompanyUpdated) -> None:
        if event.name is not None:
            self.state.name = event.name
        if event.company_type is not None:
            self.state.company_type = event.company_type
        if event.vat is not None:
            self.state.vat = event.vat
        if event.ogrn is not None:
            self.state.ogrn = event.ogrn
        if event.kpp is not None:
            self.state.kpp = event.kpp
        if event.postal_code is not None:
            self.state.postal_code = event.postal_code
        if event.country_id is not None:
            self.state.country_id = event.country_id
        if event.city is not None:
            self.state.city = event.city
        if event.street is not None:
            self.state.street = event.street
        if event.director is not None:
            self.state.director = event.director
        if event.email is not None:
            self.state.email = event.email
        if event.phone is not None:
            self.state.phone = event.phone
        if event.tg_dir is not None:
            self.state.tg_dir = event.tg_dir
        if event.tg_accountant is not None:
            self.state.tg_accountant = event.tg_accountant
        if event.tg_manager_1 is not None:
            self.state.tg_manager_1 = event.tg_manager_1
        if event.tg_manager_2 is not None:
            self.state.tg_manager_2 = event.tg_manager_2
        if event.tg_manager_3 is not None:
            self.state.tg_manager_3 = event.tg_manager_3
        if event.tg_support is not None:
            self.state.tg_support = event.tg_support
        self.state.updated_at = event.timestamp

    def _on_company_archived(self, event: CompanyArchived) -> None:
        self.state.is_active = False
        self.state.updated_at = event.timestamp

    def _on_company_restored(self, event: CompanyRestored) -> None:
        self.state.is_active = True
        self.state.updated_at = event.timestamp

    def _on_company_deleted(self, event: CompanyDeleted) -> None:
        self.state.is_deleted = True
        self.state.is_active = False
        self.state.updated_at = event.timestamp

    def _on_user_added(self, event: UserAddedToCompany) -> None:
        user_key = str(event.user_id)
        self.state.users[user_key] = UserCompanyState(
            user_id=event.user_id,
            relationship_type=event.relationship_type,
            joined_at=event.timestamp,
            is_active=True,
        )

    def _on_user_removed(self, event: UserRemovedFromCompany) -> None:
        user_key = str(event.user_id)
        if user_key in self.state.users:
            self.state.users[user_key].is_active = False

    def _on_user_role_changed(self, event: UserCompanyRoleChanged) -> None:
        user_key = str(event.user_id)
        if user_key in self.state.users:
            self.state.users[user_key].relationship_type = event.new_relationship_type

    def _on_telegram_supergroup_created(self, event: TelegramSupergroupCreated) -> None:
        group_key = str(event.telegram_group_id)
        self.state.telegram_supergroups[group_key] = TelegramSupergroupState(
            telegram_group_id=event.telegram_group_id,
            title=event.title,
            username=event.username,
            description=event.description,
            invite_link=event.invite_link,
            is_forum=event.is_forum,
            created_at=event.timestamp,
        )

    def _on_telegram_supergroup_linked(self, event: TelegramSupergroupLinked) -> None:
        group_key = str(event.telegram_group_id)
        self.state.telegram_supergroups[group_key] = TelegramSupergroupState(
            telegram_group_id=event.telegram_group_id,
            title="",  # Will be updated later
            created_at=event.timestamp,
        )

    def _on_telegram_supergroup_unlinked(self, event: TelegramSupergroupUnlinked) -> None:
        group_key = str(event.telegram_group_id)
        if group_key in self.state.telegram_supergroups:
            del self.state.telegram_supergroups[group_key]

    def _on_telegram_supergroup_updated(self, event: TelegramSupergroupUpdated) -> None:
        group_key = str(event.telegram_group_id)
        if group_key in self.state.telegram_supergroups:
            if event.title is not None:
                self.state.telegram_supergroups[group_key].title = event.title
            if event.description is not None:
                self.state.telegram_supergroups[group_key].description = event.description
            if event.invite_link is not None:
                self.state.telegram_supergroups[group_key].invite_link = event.invite_link

    def _on_telegram_supergroup_deleted(self, event: TelegramSupergroupDeleted) -> None:
        group_key = str(event.telegram_group_id)
        if group_key in self.state.telegram_supergroups:
            del self.state.telegram_supergroups[group_key]

    def _on_balance_updated(self, event: CompanyBalanceUpdated) -> None:
        self.state.balance = event.new_balance

    # =========================================================================
    # Snapshot Support
    # =========================================================================

    def create_snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of current state for persistence"""
        return {
            "company_id": str(self.state.company_id) if self.state.company_id else None,
            "name": self.state.name,
            "company_type": self.state.company_type,
            "created_by": str(self.state.created_by) if self.state.created_by else None,
            "created_at": self.state.created_at.isoformat() if self.state.created_at else None,
            "updated_at": self.state.updated_at.isoformat() if self.state.updated_at else None,
            "is_active": self.state.is_active,
            "is_deleted": self.state.is_deleted,
            "vat": self.state.vat,
            "ogrn": self.state.ogrn,
            "kpp": self.state.kpp,
            "postal_code": self.state.postal_code,
            "country_id": self.state.country_id,
            "city": self.state.city,
            "street": self.state.street,
            "director": self.state.director,
            "email": self.state.email,
            "phone": self.state.phone,
            "tg_dir": self.state.tg_dir,
            "tg_accountant": self.state.tg_accountant,
            "tg_manager_1": self.state.tg_manager_1,
            "tg_manager_2": self.state.tg_manager_2,
            "tg_manager_3": self.state.tg_manager_3,
            "tg_support": self.state.tg_support,
            "balance": str(self.state.balance),
            "users": {
                k: {
                    "user_id": str(v.user_id),
                    "relationship_type": v.relationship_type,
                    "joined_at": v.joined_at.isoformat(),
                    "is_active": v.is_active,
                }
                for k, v in self.state.users.items()
            },
            "telegram_supergroups": {
                k: {
                    "telegram_group_id": v.telegram_group_id,
                    "title": v.title,
                    "username": v.username,
                    "description": v.description,
                    "invite_link": v.invite_link,
                    "is_forum": v.is_forum,
                    "created_at": v.created_at.isoformat(),
                }
                for k, v in self.state.telegram_supergroups.items()
            },
            "metadata": self.state.metadata,
            "version": self.version,
        }

    def restore_from_snapshot(self, snapshot_data: Dict[str, Any]) -> None:
        """Restore state from a snapshot"""
        self.state.company_id = uuid.UUID(snapshot_data["company_id"]) if snapshot_data.get("company_id") else None
        self.state.name = snapshot_data.get("name")
        self.state.company_type = snapshot_data.get("company_type", "company")
        self.state.created_by = uuid.UUID(snapshot_data["created_by"]) if snapshot_data.get("created_by") else None
        self.state.is_active = snapshot_data.get("is_active", True)
        self.state.is_deleted = snapshot_data.get("is_deleted", False)

        # Legal info
        self.state.vat = snapshot_data.get("vat")
        self.state.ogrn = snapshot_data.get("ogrn")
        self.state.kpp = snapshot_data.get("kpp")

        # Address
        self.state.postal_code = snapshot_data.get("postal_code")
        self.state.country_id = snapshot_data.get("country_id", 190)
        self.state.city = snapshot_data.get("city")
        self.state.street = snapshot_data.get("street")

        # Contacts
        self.state.director = snapshot_data.get("director")
        self.state.email = snapshot_data.get("email")
        self.state.phone = snapshot_data.get("phone")

        # Telegram contacts
        self.state.tg_dir = snapshot_data.get("tg_dir")
        self.state.tg_accountant = snapshot_data.get("tg_accountant")
        self.state.tg_manager_1 = snapshot_data.get("tg_manager_1")
        self.state.tg_manager_2 = snapshot_data.get("tg_manager_2")
        self.state.tg_manager_3 = snapshot_data.get("tg_manager_3")
        self.state.tg_support = snapshot_data.get("tg_support")

        # Balance
        self.state.balance = Decimal(snapshot_data.get("balance", "0.00"))

        if snapshot_data.get("created_at"):
            self.state.created_at = datetime.fromisoformat(snapshot_data["created_at"])
        if snapshot_data.get("updated_at"):
            self.state.updated_at = datetime.fromisoformat(snapshot_data["updated_at"])

        # Restore users
        self.state.users = {}
        for k, v in snapshot_data.get("users", {}).items():
            self.state.users[k] = UserCompanyState(
                user_id=uuid.UUID(v["user_id"]),
                relationship_type=v["relationship_type"],
                joined_at=datetime.fromisoformat(v["joined_at"]),
                is_active=v["is_active"],
            )

        # Restore telegram supergroups
        self.state.telegram_supergroups = {}
        for k, v in snapshot_data.get("telegram_supergroups", {}).items():
            self.state.telegram_supergroups[k] = TelegramSupergroupState(
                telegram_group_id=v["telegram_group_id"],
                title=v["title"],
                username=v.get("username"),
                description=v.get("description"),
                invite_link=v.get("invite_link"),
                is_forum=v.get("is_forum", True),
                created_at=datetime.fromisoformat(v["created_at"]),
            )

        self.state.metadata = snapshot_data.get("metadata", {})
        self.version = snapshot_data.get("version", 0)

    @classmethod
    def replay_from_events(
        cls,
        company_id: uuid.UUID,
        events: List[BaseEvent],
        snapshot: Optional[Any] = None
    ) -> 'CompanyAggregate':
        """
        Reconstruct aggregate from event history.

        Handles both BaseEvent objects and EventEnvelope objects (from KurrentDB).
        EventEnvelopes are converted to domain events using the event registry.

        Args:
            company_id: The aggregate ID
            events: Events to replay (should be events AFTER snapshot if snapshot provided)
            snapshot: Optional AggregateSnapshot to restore from first
        """
        from app.infra.event_store.event_envelope import EventEnvelope
        from app.company.events import COMPANY_EVENT_TYPES

        agg = cls(company_id)

        # Restore from snapshot first if provided
        if snapshot is not None:
            agg.restore_from_snapshot(snapshot.state)
            agg.version = snapshot.version
            log.debug(f"Restored company {company_id} from snapshot at version {snapshot.version}")

        for evt in events:
            # Handle EventEnvelope from KurrentDB
            if isinstance(evt, EventEnvelope):
                # Try to convert envelope to domain event object
                event_obj = evt.to_event_object()
                if event_obj is None:
                    # Fallback: use COMPANY_EVENT_TYPES registry
                    event_class = COMPANY_EVENT_TYPES.get(evt.event_type)
                    if event_class:
                        try:
                            event_obj = event_class(**evt.event_data)
                        except Exception as e:
                            log.warning(f"Failed to deserialize {evt.event_type}: {e}")
                            continue
                    else:
                        log.warning(f"Unknown event type in replay: {evt.event_type}")
                        continue
                agg._apply(event_obj)
                # Use version from envelope (handles snapshot case correctly)
                if evt.aggregate_version:
                    agg.version = evt.aggregate_version
                else:
                    agg.version += 1
            else:
                # Direct BaseEvent object
                agg._apply(evt)
                agg.version += 1
        agg.mark_events_committed()
        return agg
