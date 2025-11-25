# =============================================================================
# File: app/company/projectors.py
# Description: Company domain event projectors for read model updates
# =============================================================================

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone
from decimal import Decimal

from app.infra.event_store.event_envelope import EventEnvelope
from app.infra.event_store.sync_decorators import sync_projection, monitor_projection

if TYPE_CHECKING:
    from app.infra.read_repos.company_read_repo import CompanyReadRepo

log = logging.getLogger("wellwon.company.projectors")


class CompanyProjector:
    """
    Projects company domain events to PostgreSQL read models.

    Handles all company-related events and updates the corresponding
    read model tables (companies, user_companies, telegram_supergroups,
    company_balance_transactions).
    """

    def __init__(self, company_read_repo: 'CompanyReadRepo'):
        self.company_read_repo = company_read_repo

    # =========================================================================
    # Company Lifecycle Projections
    # =========================================================================

    @sync_projection("CompanyCreated")
    @monitor_projection
    async def on_company_created(self, envelope: EventEnvelope) -> None:
        """Project CompanyCreated event to read model"""
        event_data = envelope.event_data
        company_id = envelope.aggregate_id

        log.info(f"Projecting CompanyCreated: company_id={company_id}")

        await self.company_read_repo.insert_company(
            company_id=company_id,
            name=event_data['name'],
            company_type=event_data.get('company_type', 'company'),
            created_by=uuid.UUID(event_data['created_by']),
            vat=event_data.get('vat'),
            ogrn=event_data.get('ogrn'),
            kpp=event_data.get('kpp'),
            postal_code=event_data.get('postal_code'),
            country_id=event_data.get('country_id', 190),
            city=event_data.get('city'),
            street=event_data.get('street'),
            director=event_data.get('director'),
            email=event_data.get('email'),
            phone=event_data.get('phone'),
            tg_dir=event_data.get('tg_dir'),
            tg_accountant=event_data.get('tg_accountant'),
            tg_manager_1=event_data.get('tg_manager_1'),
            tg_manager_2=event_data.get('tg_manager_2'),
            tg_manager_3=event_data.get('tg_manager_3'),
            tg_support=event_data.get('tg_support'),
            created_at=envelope.timestamp,
        )

    @sync_projection("CompanyUpdated")
    async def on_company_updated(self, envelope: EventEnvelope) -> None:
        """Project CompanyUpdated event"""
        event_data = envelope.event_data
        company_id = envelope.aggregate_id

        log.info(f"Projecting CompanyUpdated: company_id={company_id}")

        await self.company_read_repo.update_company(
            company_id=company_id,
            name=event_data.get('name'),
            company_type=event_data.get('company_type'),
            vat=event_data.get('vat'),
            ogrn=event_data.get('ogrn'),
            kpp=event_data.get('kpp'),
            postal_code=event_data.get('postal_code'),
            country_id=event_data.get('country_id'),
            city=event_data.get('city'),
            street=event_data.get('street'),
            director=event_data.get('director'),
            email=event_data.get('email'),
            phone=event_data.get('phone'),
            tg_dir=event_data.get('tg_dir'),
            tg_accountant=event_data.get('tg_accountant'),
            tg_manager_1=event_data.get('tg_manager_1'),
            tg_manager_2=event_data.get('tg_manager_2'),
            tg_manager_3=event_data.get('tg_manager_3'),
            tg_support=event_data.get('tg_support'),
            updated_at=envelope.timestamp,
        )

    @sync_projection("CompanyArchived")
    async def on_company_archived(self, envelope: EventEnvelope) -> None:
        """Project CompanyArchived event"""
        company_id = envelope.aggregate_id

        log.info(f"Projecting CompanyArchived: company_id={company_id}")

        await self.company_read_repo.update_company_status(
            company_id=company_id,
            is_active=False,
            updated_at=envelope.timestamp,
        )

    @sync_projection("CompanyRestored")
    async def on_company_restored(self, envelope: EventEnvelope) -> None:
        """Project CompanyRestored event"""
        company_id = envelope.aggregate_id

        log.info(f"Projecting CompanyRestored: company_id={company_id}")

        await self.company_read_repo.update_company_status(
            company_id=company_id,
            is_active=True,
            updated_at=envelope.timestamp,
        )

    @sync_projection("CompanyDeleted")
    async def on_company_deleted(self, envelope: EventEnvelope) -> None:
        """Project CompanyDeleted event (soft delete)"""
        company_id = envelope.aggregate_id

        log.info(f"Projecting CompanyDeleted: company_id={company_id}")

        await self.company_read_repo.soft_delete_company(
            company_id=company_id,
            updated_at=envelope.timestamp,
        )

    # =========================================================================
    # User-Company Relationship Projections
    # =========================================================================

    @sync_projection("UserAddedToCompany")
    @monitor_projection
    async def on_user_added_to_company(self, envelope: EventEnvelope) -> None:
        """Project UserAddedToCompany event"""
        event_data = envelope.event_data
        company_id = envelope.aggregate_id
        user_id = uuid.UUID(event_data['user_id'])

        log.info(f"Projecting UserAddedToCompany: company={company_id}, user={user_id}")

        await self.company_read_repo.insert_user_company(
            company_id=company_id,
            user_id=user_id,
            relationship_type=event_data.get('relationship_type', 'participant'),
            joined_at=envelope.timestamp,
        )

        # Update user count on company
        await self.company_read_repo.increment_user_count(company_id)

    @sync_projection("UserRemovedFromCompany")
    async def on_user_removed_from_company(self, envelope: EventEnvelope) -> None:
        """Project UserRemovedFromCompany event"""
        event_data = envelope.event_data
        company_id = envelope.aggregate_id
        user_id = uuid.UUID(event_data['user_id'])

        log.info(f"Projecting UserRemovedFromCompany: company={company_id}, user={user_id}")

        await self.company_read_repo.deactivate_user_company(
            company_id=company_id,
            user_id=user_id,
        )

        # Update user count on company
        await self.company_read_repo.decrement_user_count(company_id)

    @sync_projection("UserCompanyRoleChanged")
    async def on_user_company_role_changed(self, envelope: EventEnvelope) -> None:
        """Project UserCompanyRoleChanged event"""
        event_data = envelope.event_data
        company_id = envelope.aggregate_id
        user_id = uuid.UUID(event_data['user_id'])

        log.info(f"Projecting UserCompanyRoleChanged: company={company_id}, user={user_id}")

        await self.company_read_repo.update_user_company_role(
            company_id=company_id,
            user_id=user_id,
            relationship_type=event_data['new_relationship_type'],
        )

    # =========================================================================
    # Telegram Supergroup Projections
    # =========================================================================

    @sync_projection("TelegramSupergroupCreated")
    @monitor_projection
    async def on_telegram_supergroup_created(self, envelope: EventEnvelope) -> None:
        """Project TelegramSupergroupCreated event"""
        event_data = envelope.event_data
        company_id = envelope.aggregate_id
        telegram_group_id = event_data['telegram_group_id']

        log.info(f"Projecting TelegramSupergroupCreated: company={company_id}, group={telegram_group_id}")

        await self.company_read_repo.insert_telegram_supergroup(
            company_id=company_id,
            telegram_group_id=telegram_group_id,
            title=event_data['title'],
            username=event_data.get('username'),
            description=event_data.get('description'),
            invite_link=event_data.get('invite_link'),
            is_forum=event_data.get('is_forum', True),
            created_at=envelope.timestamp,
        )

    @sync_projection("TelegramSupergroupLinked")
    async def on_telegram_supergroup_linked(self, envelope: EventEnvelope) -> None:
        """Project TelegramSupergroupLinked event"""
        event_data = envelope.event_data
        company_id = envelope.aggregate_id
        telegram_group_id = event_data['telegram_group_id']

        log.info(f"Projecting TelegramSupergroupLinked: company={company_id}, group={telegram_group_id}")

        await self.company_read_repo.insert_telegram_supergroup(
            company_id=company_id,
            telegram_group_id=telegram_group_id,
            title="",  # Will be updated when we get group info
            created_at=envelope.timestamp,
        )

    @sync_projection("TelegramSupergroupUnlinked")
    async def on_telegram_supergroup_unlinked(self, envelope: EventEnvelope) -> None:
        """Project TelegramSupergroupUnlinked event"""
        event_data = envelope.event_data
        company_id = envelope.aggregate_id
        telegram_group_id = event_data['telegram_group_id']

        log.info(f"Projecting TelegramSupergroupUnlinked: company={company_id}, group={telegram_group_id}")

        await self.company_read_repo.delete_telegram_supergroup(
            company_id=company_id,
            telegram_group_id=telegram_group_id,
        )

    @sync_projection("TelegramSupergroupUpdated")
    async def on_telegram_supergroup_updated(self, envelope: EventEnvelope) -> None:
        """Project TelegramSupergroupUpdated event"""
        event_data = envelope.event_data
        company_id = envelope.aggregate_id
        telegram_group_id = event_data['telegram_group_id']

        log.info(f"Projecting TelegramSupergroupUpdated: company={company_id}, group={telegram_group_id}")

        await self.company_read_repo.update_telegram_supergroup(
            company_id=company_id,
            telegram_group_id=telegram_group_id,
            title=event_data.get('title'),
            description=event_data.get('description'),
            invite_link=event_data.get('invite_link'),
            updated_at=envelope.timestamp,
        )

    # =========================================================================
    # Balance Projections
    # =========================================================================

    @sync_projection("CompanyBalanceUpdated")
    @monitor_projection
    async def on_company_balance_updated(self, envelope: EventEnvelope) -> None:
        """Project CompanyBalanceUpdated event"""
        event_data = envelope.event_data
        company_id = envelope.aggregate_id

        log.info(f"Projecting CompanyBalanceUpdated: company={company_id}")

        # Update company balance
        await self.company_read_repo.update_company_balance(
            company_id=company_id,
            new_balance=Decimal(event_data['new_balance']),
            updated_at=envelope.timestamp,
        )

        # Insert balance transaction record
        await self.company_read_repo.insert_balance_transaction(
            company_id=company_id,
            old_balance=Decimal(event_data['old_balance']),
            new_balance=Decimal(event_data['new_balance']),
            change_amount=Decimal(event_data['change_amount']),
            reason=event_data['reason'],
            reference_id=event_data.get('reference_id'),
            updated_by=uuid.UUID(event_data['updated_by']),
            created_at=envelope.timestamp,
        )
