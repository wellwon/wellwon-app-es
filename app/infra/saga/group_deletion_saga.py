# =============================================================================
# File: app/infra/saga/group_deletion_saga.py
# Description: Saga for orchestrating group deletion (cascading hard delete)
# TRUE SAGA Pattern: Uses ONLY CommandBus and EventBus, NO queries, NO SQL
# Deletes: Chats (with messages) → Telegram Supergroup → Company
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from app.infra.saga.saga_manager import BaseSaga, SagaStep
from app.config.saga_config import saga_config

log = logging.getLogger("wellwon.saga.group_deletion")


class GroupDeletionSaga(BaseSaga):
    """
    TRUE SAGA: Orchestrates cascading group deletion.

    CRITICAL: This saga follows TRUE SAGA pattern:
    - NO query_bus usage - all data comes from ENRICHED event
    - NO direct SQL - only commands to domains
    - Uses ONLY: CommandBus, EventBus

    Trigger Event: CompanyDeleteRequested (ENRICHED by handler with all data)

    Context from enriched event (populated by RequestCompanyDeletionHandler):
    - company_id: UUID
    - company_name: str
    - deleted_by: UUID
    - telegram_group_id: Optional[int] - enriched from handler query
    - chat_ids: List[UUID] - enriched from handler query (CRITICAL!)
    - cascade: bool
    - preserve_company: bool - if True, keep company record for re-linking (default: False)

    Steps (Cascading Delete):
    1. Delete all chats via DeleteChatCommand (each chat deletes its own messages)
    2. Delete Telegram supergroup via DeleteTelegramSupergroupCommand
    3. Delete company via DeleteCompanyCommand (skipped if preserve_company=True)
    4. Publish completion event

    FUTURE FLEXIBILITY:
    - preserve_company=True: Keeps company record for re-linking to new Telegram group
    - Useful when company has other linked entities (ERP, invoices, etc.)

    Note: This is a destructive saga. Compensation only logs failures
    since we can't restore deleted data. Manual intervention required on failure.
    """

    def __init__(self, saga_id: Optional[uuid.UUID] = None):
        super().__init__(saga_id)
        # Track deletion progress
        self._chats_deleted: int = 0
        self._telegram_deleted: bool = False

    def get_saga_type(self) -> str:
        return "GroupDeletionSaga"

    def get_timeout(self) -> timedelta:
        # Deletion can take longer for large companies
        return timedelta(minutes=10)

    def define_steps(self) -> List[SagaStep]:
        return [
            SagaStep(
                name="delete_all_chats",
                execute=self._delete_all_chats,
                compensate=self._log_compensation_required,
                timeout_seconds=120,
                retry_count=1
            ),
            SagaStep(
                name="delete_telegram_supergroup",
                execute=self._delete_telegram_supergroup,
                compensate=self._log_compensation_required,
                timeout_seconds=60,
                retry_count=2
            ),
            SagaStep(
                name="delete_company",
                execute=self._delete_company,
                compensate=self._log_compensation_required,
                timeout_seconds=30,
                retry_count=1
            ),
            SagaStep(
                name="publish_completion",
                execute=self._publish_completion,
                compensate=self._noop_compensate,
                timeout_seconds=10,
                retry_count=1
            ),
        ]

    # =========================================================================
    # Step 1: Delete All Chats (with their messages) - TRUE SAGA
    # =========================================================================
    async def _delete_all_chats(self, **context) -> Dict[str, Any]:
        """
        Delete all company chats via DeleteChatCommand.

        TRUE SAGA: Uses chat_ids from ENRICHED event context, NOT from query.
        Each DeleteChatCommand triggers the Chat domain to delete its messages.
        """
        # Get chat_ids from ENRICHED event context (NOT from query!)
        chat_ids = context.get('chat_ids', [])
        deleted_by = context.get('deleted_by')

        if isinstance(deleted_by, str):
            deleted_by = uuid.UUID(deleted_by)

        if not chat_ids:
            log.info(f"Saga {self.saga_id}: No chats to delete (from enriched event)")
            return {'chats_deleted': 0}

        # Get command_bus from context (TRUE SAGA: only CommandBus allowed)
        command_bus = context['command_bus']

        log.info(f"Saga {self.saga_id}: Deleting {len(chat_ids)} chats via commands")

        try:
            from app.chat.commands import DeleteChatCommand

            deleted_count = 0
            for chat_id in chat_ids:
                # Convert to UUID if string
                if isinstance(chat_id, str):
                    chat_id = uuid.UUID(chat_id)

                try:
                    # Send command to Chat domain
                    # Chat domain handles message deletion internally (domain responsibility)
                    command = DeleteChatCommand(
                        chat_id=chat_id,
                        deleted_by=deleted_by,
                        reason="Group deletion saga - cascading delete"
                    )
                    await command_bus.send(command)
                    deleted_count += 1

                    log.debug(f"Saga {self.saga_id}: Deleted chat {chat_id}")

                except Exception as e:
                    log.warning(f"Saga {self.saga_id}: Failed to delete chat {chat_id}: {e}")
                    # Continue with other chats

            self._chats_deleted = deleted_count

            log.info(f"Saga {self.saga_id}: Deleted {deleted_count}/{len(chat_ids)} chats")

            return {
                'chats_deleted': deleted_count
            }

        except Exception as e:
            log.error(f"Saga {self.saga_id}: Failed to delete chats: {e}")
            raise

    # =========================================================================
    # Step 2: Delete Telegram Supergroup - TRUE SAGA
    # =========================================================================
    async def _delete_telegram_supergroup(self, **context) -> Dict[str, Any]:
        """
        Delete Telegram supergroup via DeleteTelegramSupergroupCommand.

        TRUE SAGA: telegram_group_id comes from ENRICHED event context.

        This step:
        1. Calls TelegramAdapter to actually leave/delete the group from Telegram
        2. Sends DeleteTelegramSupergroupCommand to update the database
        """
        # Get telegram_group_id from ENRICHED event context (NOT from query!)
        telegram_group_id = context.get('telegram_group_id')
        deleted_by = context.get('deleted_by')

        if isinstance(deleted_by, str):
            deleted_by = uuid.UUID(deleted_by)

        if not telegram_group_id:
            log.info(f"Saga {self.saga_id}: No Telegram group to delete (from enriched event)")
            return {
                'telegram_deleted': False,
                'telegram_skipped': True
            }

        # Get command_bus from context (TRUE SAGA: only CommandBus allowed)
        command_bus = context['command_bus']

        log.info(f"Saga {self.saga_id}: Deleting Telegram supergroup {telegram_group_id}")

        # Step 2a: Actually leave/delete the group from Telegram
        telegram_left = False
        try:
            from app.api.dependencies.adapter_deps import get_telegram_adapter
            adapter = await get_telegram_adapter()
            if adapter:
                telegram_left = await adapter.leave_group(telegram_group_id)
                if telegram_left:
                    log.info(f"Saga {self.saga_id}: Left/deleted Telegram group {telegram_group_id}")
                else:
                    log.warning(f"Saga {self.saga_id}: Failed to leave Telegram group {telegram_group_id}")
            else:
                log.warning(f"Saga {self.saga_id}: TelegramAdapter not available")
        except Exception as e:
            log.warning(f"Saga {self.saga_id}: Error leaving Telegram group: {e}")

        # Step 2b: Update database via command
        try:
            from app.company.commands import DeleteTelegramSupergroupCommand

            command = DeleteTelegramSupergroupCommand(
                telegram_group_id=telegram_group_id,
                deleted_by=deleted_by,
                reason="Group deletion saga - cascading delete"
            )

            await command_bus.send(command)

            self._telegram_deleted = True
            log.info(f"Saga {self.saga_id}: Telegram supergroup {telegram_group_id} record deleted")

            return {
                'telegram_deleted': True,
                'telegram_left': telegram_left
            }

        except Exception as e:
            log.warning(f"Saga {self.saga_id}: Telegram deletion error: {e}")
            # Don't fail saga for Telegram errors - data is more important
            return {
                'telegram_deleted': False,
                'telegram_left': telegram_left,
                'telegram_error': str(e)
            }

    # =========================================================================
    # Step 3: Delete Company - TRUE SAGA (with preserve_company option)
    # =========================================================================
    async def _delete_company(self, **context) -> Dict[str, Any]:
        """
        Hard delete company via DeleteCompanyCommand.

        TRUE SAGA: company_id comes from ENRICHED event context.

        FUTURE FLEXIBILITY:
        - preserve_company=True: Skip company deletion, keep for re-linking
        - Default: preserve_company=False (delete everything)
        """
        # Log step start for tracing
        log.debug(
            f"Saga {self.saga_id}: _delete_company step - "
            f"preserve_company={context.get('preserve_company')}, "
            f"company_id={context.get('company_id')}"
        )

        # Check preserve_company flag (default: False = delete company)
        preserve_company = context.get('preserve_company', False)
        company_id = context['company_id']
        deleted_by = context.get('deleted_by')

        if isinstance(company_id, str):
            company_id = uuid.UUID(company_id)
        if isinstance(deleted_by, str):
            deleted_by = uuid.UUID(deleted_by)

        # FUTURE FLEXIBILITY: Skip company deletion if preserve_company=True
        if preserve_company:
            log.info(
                f"Saga {self.saga_id}: Skipping company deletion - preserve_company=True, "
                f"company {company_id} will be preserved for re-linking"
            )
            return {
                'company_deleted': False,
                'company_preserved': True,
                'company_id': str(company_id),
            }

        # Get command_bus from context (TRUE SAGA: only CommandBus allowed)
        command_bus = context['command_bus']

        log.info(f"Saga {self.saga_id}: Deleting company {company_id}")

        try:
            from app.company.commands import DeleteCompanyCommand

            command = DeleteCompanyCommand(
                company_id=company_id,
                deleted_by=deleted_by,
                force=True  # Bypass permission checks for saga-initiated deletion
            )

            await command_bus.send(command)

            log.info(f"Saga {self.saga_id}: Company {company_id} deleted")

            return {
                'company_deleted': True
            }

        except Exception as e:
            log.error(f"Saga {self.saga_id}: Failed to delete company: {e}")
            raise

    # =========================================================================
    # Step 4: Publish Completion
    # =========================================================================
    async def _publish_completion(self, **context) -> Dict[str, Any]:
        """Publish saga completion event"""
        from app.infra.saga.saga_events import GroupDeletionSagaCompleted

        company_id = context['company_id']
        company_name = context.get('company_name', 'Unknown')
        deleted_by = context['deleted_by']
        chats_deleted = context.get('chats_deleted', 0)
        telegram_deleted = context.get('telegram_deleted', False)

        # Get event_bus from context (TRUE SAGA: EventBus allowed)
        event_bus = context['event_bus']

        log.info(f"Saga {self.saga_id}: Publishing completion event")

        completion_event = GroupDeletionSagaCompleted(
            saga_id=str(self.saga_id),
            company_id=str(company_id),
            company_name=company_name,
            messages_deleted=0,  # Messages deleted by Chat domain internally
            chats_deleted=chats_deleted,
            telegram_group_deleted=telegram_deleted,
            deleted_by=str(deleted_by),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        await event_bus.publish("saga.events", completion_event.model_dump(mode='json'))

        log.info(
            f"Saga {self.saga_id}: GroupDeletionSaga completed - "
            f"Company: {company_id}, Chats: {chats_deleted}, Telegram: {telegram_deleted}"
        )

        return {
            'completion_published': True
        }

    # =========================================================================
    # Compensation Methods
    # =========================================================================
    async def _noop_compensate(self, **context) -> None:
        """No compensation needed for this step"""
        pass

    async def _log_compensation_required(self, **context) -> None:
        """
        Log that manual intervention is required.
        Deletion is destructive - we can't restore deleted data.
        """
        company_id = context.get('company_id', 'unknown')

        log.error(
            f"Saga {self.saga_id}: MANUAL INTERVENTION REQUIRED - "
            f"Group deletion for company {company_id} partially completed. "
            f"Chats deleted: {self._chats_deleted}, "
            f"Telegram deleted: {self._telegram_deleted}"
        )

        # Publish alert for manual intervention
        event_bus = context.get('event_bus')
        if event_bus:
            from app.infra.saga.saga_events import GroupDeletionSagaFailed

            failure_event = GroupDeletionSagaFailed(
                saga_id=str(self.saga_id),
                company_id=str(company_id),
                failure_reason="Partial deletion - manual intervention required",
                failed_step=self.current_step or "unknown",
                requires_manual_intervention=True,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            try:
                await event_bus.publish("saga.events", failure_event.model_dump(mode='json'))
            except Exception as e:
                log.error(f"Failed to publish deletion failure event: {e}")


# =============================================================================
# EOF
# =============================================================================
