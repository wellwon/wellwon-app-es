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
from app.infra.cqrs.projector_decorators import sync_projection, async_projection, monitor_projection
from app.common.exceptions.projection_exceptions import RetriableProjectionError

if TYPE_CHECKING:
    from app.infra.read_repos.company_read_repo import CompanyReadRepo

log = logging.getLogger("wellwon.company.projectors")


class CompanyProjector:
    """
    Projects company domain events to PostgreSQL read models.

    Handles all company-related events and updates the corresponding
    read model tables (companies, user_companies, telegram_supergroups).

    SYNC vs ASYNC projections:
    - SYNC: CompanyCreated, UserAddedToCompany, CompanyBalanceUpdated
            (Frontend queries immediately after WSE events)
    - ASYNC: CompanyUpdated, CompanyArchived, CompanyRestored, Telegram events
            (Not time-critical, eventual consistency OK)
    """

    def __init__(self, company_read_repo: 'CompanyReadRepo'):
        self.company_read_repo = company_read_repo

    # =========================================================================
    # Company Lifecycle Projections
    # =========================================================================

    # ASYNC: Testing Worker projection processing
    @async_projection("CompanyCreated")
    @monitor_projection
    async def on_company_created(self, envelope: EventEnvelope) -> None:
        """
        Project CompanyCreated event to read model.

        ASYNC: Worker processes via RedPanda (testing).
        """
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
            created_at=envelope.stored_at,
        )

    # ASYNC: Company update is not time-critical
    @async_projection("CompanyUpdated")
    async def on_company_updated(self, envelope: EventEnvelope) -> None:
        """Project CompanyUpdated event (ASYNC - eventual consistency OK)"""
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
            updated_at=envelope.stored_at,
        )

    # ASYNC: Archive/restore operations are not time-critical
    @async_projection("CompanyArchived")
    async def on_company_archived(self, envelope: EventEnvelope) -> None:
        """Project CompanyArchived event (ASYNC)"""
        company_id = envelope.aggregate_id

        log.info(f"Projecting CompanyArchived: company_id={company_id}")

        await self.company_read_repo.update_company_status(
            company_id=company_id,
            is_active=False,
            updated_at=envelope.stored_at,
        )

    @async_projection("CompanyRestored")
    async def on_company_restored(self, envelope: EventEnvelope) -> None:
        """Project CompanyRestored event (ASYNC)"""
        company_id = envelope.aggregate_id

        log.info(f"Projecting CompanyRestored: company_id={company_id}")

        await self.company_read_repo.update_company_status(
            company_id=company_id,
            is_active=True,
            updated_at=envelope.stored_at,
        )

    # ASYNC: UI uses optimistic update, Worker handles projection
    @async_projection("CompanyDeleted")
    @monitor_projection
    async def on_company_deleted(self, envelope: EventEnvelope) -> None:
        """
        Project CompanyDeleted event.

        ASYNC: UI uses optimistic update, eventual consistency acceptable.
        """
        company_id = envelope.aggregate_id

        log.info(f"Projecting CompanyDeleted: company_id={company_id}")

        try:
            await self.company_read_repo.delete_company(
                company_id=company_id,
                updated_at=envelope.stored_at,
            )
            log.info(f"CompanyDeleted projection SUCCESS: company_id={company_id}")
        except Exception as e:
            log.error(f"CompanyDeleted projection FAILED: company_id={company_id}, error={e}", exc_info=True)
            raise

    # Saga trigger event - no projection needed, just acknowledge
    @async_projection("CompanyDeleteRequested")
    async def on_company_delete_requested(self, envelope: EventEnvelope) -> None:
        """
        Acknowledge CompanyDeleteRequested event.

        This is a saga trigger event - GroupDeletionSaga handles the actual deletion.
        No read model update needed here.
        """
        company_id = envelope.aggregate_id
        log.debug(f"CompanyDeleteRequested acknowledged: company_id={company_id} (saga will handle deletion)")

    # =========================================================================
    # User-Company Relationship Projections
    # =========================================================================

    # ASYNC: Frontend uses optimistic UI + WSE notification
    @async_projection("UserAddedToCompany")
    @monitor_projection
    async def on_user_added_to_company(self, envelope: EventEnvelope) -> None:
        """
        Project UserAddedToCompany event.

        ASYNC: Frontend uses optimistic UI, WSE notifies when ready.
        """
        event_data = envelope.event_data
        company_id = envelope.aggregate_id
        user_id = uuid.UUID(event_data['user_id'])

        log.info(f"Projecting UserAddedToCompany: company={company_id}, user={user_id}")

        await self.company_read_repo.insert_user_company(
            company_id=company_id,
            user_id=user_id,
            relationship_type=event_data.get('relationship_type', 'participant'),
            joined_at=envelope.stored_at,
        )

        # Update user count on company
        await self.company_read_repo.increment_user_count(company_id)

    # ASYNC: User removal is not time-critical
    @async_projection("UserRemovedFromCompany")
    async def on_user_removed_from_company(self, envelope: EventEnvelope) -> None:
        """Project UserRemovedFromCompany event (ASYNC)"""
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

    # ASYNC: Role changes are not time-critical
    @async_projection("UserCompanyRoleChanged")
    async def on_user_company_role_changed(self, envelope: EventEnvelope) -> None:
        """Project UserCompanyRoleChanged event (ASYNC)"""
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

    # ASYNC: Saga reads telegram_group_id from context, has retry logic for FK
    @async_projection("TelegramSupergroupCreated")
    @monitor_projection
    async def on_telegram_supergroup_created(self, envelope: EventEnvelope) -> None:
        """
        Project TelegramSupergroupCreated event.

        ASYNC: Saga reads telegram_group_id from context, RetriableProjectionError handles FK delays.
        """
        event_data = envelope.event_data
        company_id = envelope.aggregate_id
        telegram_group_id = event_data['telegram_group_id']

        log.info(f"Projecting TelegramSupergroupCreated: company={company_id}, group={telegram_group_id}")

        try:
            await self.company_read_repo.insert_telegram_supergroup(
                company_id=company_id,
                telegram_group_id=telegram_group_id,
                title=event_data['title'],
                username=event_data.get('username'),
                description=event_data.get('description'),
                invite_link=event_data.get('invite_link'),
                is_forum=event_data.get('is_forum', True),
                created_at=envelope.stored_at,
            )
        except Exception as e:
            error_str = str(e).lower()
            # Check for FK violation (company doesn't exist yet)
            if 'foreign key' in error_str or 'violates foreign key constraint' in error_str:
                log.warning(
                    f"FK violation for TelegramSupergroupCreated: company={company_id} may not exist yet. "
                    f"Event will be retried."
                )
                raise RetriableProjectionError(
                    f"Company {company_id} not yet projected. TelegramSupergroupCreated will be retried."
                ) from e
            raise

    # ASYNC: Linking existing group is not time-critical
    @async_projection("TelegramSupergroupLinked")
    async def on_telegram_supergroup_linked(self, envelope: EventEnvelope) -> None:
        """Project TelegramSupergroupLinked event (ASYNC)"""
        event_data = envelope.event_data
        company_id = envelope.aggregate_id
        telegram_group_id = event_data['telegram_group_id']

        log.info(f"Projecting TelegramSupergroupLinked: company={company_id}, group={telegram_group_id}")

        await self.company_read_repo.insert_telegram_supergroup(
            company_id=company_id,
            telegram_group_id=telegram_group_id,
            title="",  # Will be updated when we get group info
            created_at=envelope.stored_at,
        )

    # ASYNC: Unlinking is not time-critical
    @async_projection("TelegramSupergroupUnlinked")
    async def on_telegram_supergroup_unlinked(self, envelope: EventEnvelope) -> None:
        """Project TelegramSupergroupUnlinked event (ASYNC)"""
        event_data = envelope.event_data
        company_id = envelope.aggregate_id
        telegram_group_id = event_data['telegram_group_id']

        log.info(f"Projecting TelegramSupergroupUnlinked: company={company_id}, group={telegram_group_id}")

        await self.company_read_repo.delete_telegram_supergroup(
            company_id=company_id,
            telegram_group_id=telegram_group_id,
        )

    # ASYNC: Metadata updates are not time-critical
    @async_projection("TelegramSupergroupUpdated")
    async def on_telegram_supergroup_updated(self, envelope: EventEnvelope) -> None:
        """Project TelegramSupergroupUpdated event (ASYNC)"""
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
            updated_at=envelope.stored_at,
        )

    # ASYNC: UI uses optimistic update, Worker handles projection
    @async_projection("TelegramSupergroupDeleted")
    @monitor_projection
    async def on_telegram_supergroup_deleted(self, envelope: EventEnvelope) -> None:
        """
        Project TelegramSupergroupDeleted event - hard delete from read model.

        ASYNC: UI uses optimistic update, eventual consistency acceptable.
        """
        event_data = envelope.event_data
        telegram_group_id = event_data['telegram_group_id']

        log.info(f"Projecting TelegramSupergroupDeleted: group={telegram_group_id}")

        try:
            await self.company_read_repo.hard_delete_telegram_supergroup(
                telegram_group_id=telegram_group_id,
            )
            log.info(f"TelegramSupergroupDeleted projection SUCCESS: group={telegram_group_id}")
        except Exception as e:
            log.error(f"TelegramSupergroupDeleted projection FAILED: group={telegram_group_id}, error={e}", exc_info=True)
            raise

    # =========================================================================
    # Balance Projections
    # =========================================================================

    # ASYNC: No saga dependency, Worker handles via eventual consistency
    @async_projection("CompanyBalanceUpdated")
    @monitor_projection
    async def on_company_balance_updated(self, envelope: EventEnvelope) -> None:
        """
        Project CompanyBalanceUpdated event.

        ASYNC: No saga depends on this. Worker processes via RedPanda.
        """
        event_data = envelope.event_data
        company_id = envelope.aggregate_id

        log.info(f"Projecting CompanyBalanceUpdated: company={company_id}")

        # Update company balance
        await self.company_read_repo.update_company_balance(
            company_id=company_id,
            new_balance=Decimal(event_data['new_balance']),
            updated_at=envelope.stored_at,
        )
