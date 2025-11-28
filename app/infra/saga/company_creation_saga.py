# =============================================================================
# File: app/infra/saga/company_creation_saga.py
# Description: Saga for orchestrating company creation with Telegram group and Chat
# TRUE SAGA: Uses enriched event data, orchestrates via CommandBus
# =============================================================================

from __future__ import annotations

import uuid
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from app.infra.saga.saga_manager import BaseSaga, SagaStep
from app.config.saga_config import saga_config

log = logging.getLogger("wellwon.saga.company_creation")


class CompanyCreationSaga(BaseSaga):
    """
    TRUE SAGA: Orchestrates company creation with Telegram group and Chat.

    Trigger Event: CompanyCreated (enriched with company data and saga options)

    Context from enriched event:
    - company_id, company_name, created_by
    - create_telegram_group: bool - whether to create telegram group
    - telegram_group_title, telegram_group_description - telegram group options
    - link_chat_id: UUID - if provided, link existing chat instead of creating new

    Steps:
    1. Create Telegram Supergroup (via MTProto adapter) - only if create_telegram_group=True
    2. Link Telegram Supergroup to Company (CreateTelegramSupergroupCommand)
    3. Create/Link Company Chat (CreateChatCommand or LinkChatToCompanyCommand)
    4. Publish completion event

    Compensation:
    - Delete Telegram group on failure
    - Publish failure event for manual intervention
    """

    def __init__(self, saga_id: Optional[uuid.UUID] = None):
        super().__init__(saga_id)
        # Track created resources for compensation
        self._telegram_group_id: Optional[int] = None
        self._telegram_invite_link: Optional[str] = None
        self._chat_id: Optional[uuid.UUID] = None
        self._linked_existing_chat: bool = False

    def get_saga_type(self) -> str:
        return "CompanyCreationSaga"

    def get_timeout(self) -> timedelta:
        return saga_config.get_timeout_for_saga(self.get_saga_type())

    def define_steps(self) -> List[SagaStep]:
        return [
            SagaStep(
                name="create_telegram_group",
                execute=self._create_telegram_group,
                compensate=self._compensate_telegram_group,
                timeout_seconds=60,
                retry_count=2,
                retry_delay_base=1.0
            ),
            SagaStep(
                name="link_telegram_supergroup",
                execute=self._link_telegram_supergroup,
                compensate=self._noop_compensate,
                timeout_seconds=30,
                retry_count=2
            ),
            SagaStep(
                name="create_or_link_chat",
                execute=self._create_or_link_chat,
                compensate=self._compensate_chat,
                timeout_seconds=30,
                retry_count=2
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
    # Step 1: Create Telegram Group (conditional)
    # =========================================================================
    async def _create_telegram_group(self, **context) -> Dict[str, Any]:
        """
        Step 1: Create Telegram supergroup via MTProto adapter.
        Only executes if create_telegram_group=True in enriched event.
        TRUE SAGA: Company data from enriched CompanyCreated event.
        """
        # Check if we should create telegram group
        create_telegram_group = context.get('create_telegram_group', False)
        if not create_telegram_group:
            log.info(f"Saga {self.saga_id}: Skipping Telegram group creation (not requested)")
            return {
                'telegram_group_created': False,
                'telegram_group_skipped': True,
            }

        company_id = context['company_id']
        company_name = context['company_name']
        telegram_group_title = context.get('telegram_group_title') or company_name
        telegram_group_description = context.get('telegram_group_description') or f"Рабочая группа компании {company_name}"

        log.info(f"Saga {self.saga_id}: Creating Telegram group for company {company_name}")

        try:
            # Get Telegram adapter
            from app.infra.telegram.adapter import get_telegram_adapter

            adapter = await get_telegram_adapter()
            result = await adapter.create_company_group(
                company_name=telegram_group_title,
                description=telegram_group_description,
                setup_bots=True,
            )

            if not result.success:
                raise RuntimeError(f"Failed to create Telegram group: {result.error}")

            # Store for compensation
            self._telegram_group_id = result.group_id
            self._telegram_invite_link = result.invite_link

            log.info(
                f"Saga {self.saga_id}: Telegram group created - "
                f"ID: {result.group_id}, Title: {result.group_title}"
            )

            return {
                'telegram_group_created': True,
                'telegram_group_id': result.group_id,
                'telegram_group_title': result.group_title,
                'telegram_invite_link': result.invite_link,
            }

        except Exception as e:
            log.error(f"Saga {self.saga_id}: Failed to create Telegram group: {e}")
            raise

    async def _compensate_telegram_group(self, **context) -> None:
        """Compensation: Delete Telegram group if created"""
        if not self._telegram_group_id:
            log.info(f"Saga {self.saga_id}: No Telegram group to compensate")
            return

        log.warning(
            f"Saga {self.saga_id}: Compensating - attempting to delete Telegram group {self._telegram_group_id}"
        )

        try:
            from app.infra.telegram.adapter import get_telegram_adapter

            adapter = await get_telegram_adapter()
            # Note: Telegram doesn't allow deleting supergroups, only leaving them
            # We can leave the group and it will be orphaned
            await adapter.leave_group(self._telegram_group_id)

            log.info(f"Saga {self.saga_id}: Left Telegram group {self._telegram_group_id}")
        except Exception as e:
            log.error(f"Saga {self.saga_id}: Failed to compensate Telegram group: {e}")
            # Publish manual intervention event
            event_bus = context.get('event_bus')
            if event_bus:
                await event_bus.publish("saga.compensation", {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "TelegramGroupCompensationRequired",
                    "saga_id": str(self.saga_id),
                    "telegram_group_id": self._telegram_group_id,
                    "company_id": str(context.get('company_id')),
                    "requires_manual_intervention": True,
                    "reason": f"Failed to leave Telegram group: {e}"
                })

    # =========================================================================
    # Step 2: Link Telegram Supergroup to Company (conditional)
    # =========================================================================
    async def _link_telegram_supergroup(self, **context) -> Dict[str, Any]:
        """
        Step 2: Link Telegram supergroup to company via CreateTelegramSupergroupCommand.
        Only executes if telegram group was created in step 1.
        TRUE SAGA: Uses CommandBus orchestration.
        """
        # Check if telegram group was created
        telegram_group_id = context.get('telegram_group_id')
        telegram_group_skipped = context.get('telegram_group_skipped', False)

        if not telegram_group_id or telegram_group_skipped:
            log.info(f"Saga {self.saga_id}: Skipping Telegram supergroup linking (no group created)")
            return {
                'telegram_supergroup_linked': False,
                'telegram_supergroup_skipped': True,
            }

        company_id = uuid.UUID(context['company_id']) if isinstance(context['company_id'], str) else context['company_id']
        created_by = uuid.UUID(context['created_by']) if isinstance(context['created_by'], str) else context['created_by']
        telegram_group_title = context.get('telegram_group_title', '')
        telegram_invite_link = context.get('telegram_invite_link', '')

        command_bus = context['command_bus']

        log.info(
            f"Saga {self.saga_id}: Linking Telegram supergroup {telegram_group_id} to company {company_id}"
        )

        try:
            from app.company.commands import CreateTelegramSupergroupCommand

            command = CreateTelegramSupergroupCommand(
                company_id=company_id,
                telegram_group_id=telegram_group_id,
                title=telegram_group_title,
                invite_link=telegram_invite_link,
                is_forum=True,
                created_by=created_by,
            )

            await command_bus.send(command)

            log.info(f"Saga {self.saga_id}: Telegram supergroup linked to company")

            return {
                'telegram_supergroup_linked': True,
            }

        except Exception as e:
            log.error(f"Saga {self.saga_id}: Failed to link Telegram supergroup: {e}")
            raise

    # =========================================================================
    # Step 3: Create or Link Company Chat
    # =========================================================================
    async def _create_or_link_chat(self, **context) -> Dict[str, Any]:
        """
        Step 3: Create company chat or link existing chat.
        - If link_chat_id is provided: Link existing chat to company
        - Otherwise: Create new company chat

        TRUE SAGA: Cross-domain orchestration (Company → Chat domain).
        """
        company_id = uuid.UUID(context['company_id']) if isinstance(context['company_id'], str) else context['company_id']
        created_by = uuid.UUID(context['created_by']) if isinstance(context['created_by'], str) else context['created_by']
        company_name = context['company_name']
        telegram_group_id = context.get('telegram_group_id')
        link_chat_id = context.get('link_chat_id')

        command_bus = context['command_bus']

        # Convert link_chat_id to UUID if string
        if link_chat_id and isinstance(link_chat_id, str):
            link_chat_id = uuid.UUID(link_chat_id)

        # Case 1: Link existing chat to company
        if link_chat_id:
            log.info(f"Saga {self.saga_id}: Linking existing chat {link_chat_id} to company {company_name}")

            try:
                from app.chat.commands import LinkChatToCompanyCommand

                command = LinkChatToCompanyCommand(
                    chat_id=link_chat_id,
                    company_id=company_id,
                    telegram_supergroup_id=telegram_group_id,
                    linked_by=created_by,
                )

                await command_bus.send(command)

                self._chat_id = link_chat_id
                self._linked_existing_chat = True

                log.info(f"Saga {self.saga_id}: Existing chat {link_chat_id} linked to company")

                return {
                    'chat_linked': True,
                    'chat_created': False,
                    'chat_id': str(link_chat_id),
                }

            except Exception as e:
                log.error(f"Saga {self.saga_id}: Failed to link existing chat: {e}")
                raise

        # Case 2: Create new company chat
        log.info(f"Saga {self.saga_id}: Creating new company chat for {company_name}")

        try:
            from app.chat.commands import CreateChatCommand

            chat_id = uuid.uuid4()
            self._chat_id = chat_id
            self._linked_existing_chat = False

            command = CreateChatCommand(
                chat_id=chat_id,
                name=company_name,
                chat_type='company',
                created_by=created_by,
                company_id=company_id,
                telegram_supergroup_id=telegram_group_id,
                participant_ids=[created_by],  # Creator is first participant
            )

            await command_bus.send(command)

            log.info(f"Saga {self.saga_id}: Company chat created with ID {chat_id}")

            return {
                'chat_created': True,
                'chat_linked': False,
                'chat_id': str(chat_id),
            }

        except Exception as e:
            log.error(f"Saga {self.saga_id}: Failed to create company chat: {e}")
            raise

    async def _compensate_chat(self, **context) -> None:
        """Compensation: Archive/unlink chat if created/linked"""
        if not self._chat_id:
            log.info(f"Saga {self.saga_id}: No chat to compensate")
            return

        command_bus = context.get('command_bus')
        if not command_bus:
            log.error(f"Saga {self.saga_id}: No command_bus for chat compensation")
            return

        created_by = context.get('created_by')
        if isinstance(created_by, str):
            created_by = uuid.UUID(created_by)

        if self._linked_existing_chat:
            # Unlink the chat from company (don't delete it)
            log.warning(f"Saga {self.saga_id}: Compensating - unlinking chat {self._chat_id} from company")
            try:
                from app.chat.commands import UnlinkChatFromCompanyCommand

                command = UnlinkChatFromCompanyCommand(
                    chat_id=self._chat_id,
                    unlinked_by=created_by,
                    reason="Saga compensation - company creation failed"
                )
                await command_bus.send(command)
                log.info(f"Saga {self.saga_id}: Chat {self._chat_id} unlinked from company")
            except Exception as e:
                log.error(f"Saga {self.saga_id}: Failed to unlink chat: {e}")
        else:
            # Archive the newly created chat
            log.warning(f"Saga {self.saga_id}: Compensating - archiving chat {self._chat_id}")
            try:
                from app.chat.commands import ArchiveChatCommand

                command = ArchiveChatCommand(
                    chat_id=self._chat_id,
                    archived_by=created_by,
                    reason="Saga compensation - company creation failed"
                )
                await command_bus.send(command)
                log.info(f"Saga {self.saga_id}: Chat {self._chat_id} archived")
            except Exception as e:
                log.error(f"Saga {self.saga_id}: Failed to archive chat: {e}")

    # =========================================================================
    # Step 4: Publish Completion
    # =========================================================================
    async def _publish_completion(self, **context) -> Dict[str, Any]:
        """
        Step 4: Publish saga completion event using proper event class from saga_events.py.
        """
        from app.infra.saga.saga_events import CompanyCreationSagaCompleted

        company_id = context['company_id']
        company_name = context['company_name']
        created_by = context['created_by']
        telegram_group_id = context.get('telegram_group_id')
        telegram_invite_link = context.get('telegram_invite_link', '')
        chat_id = context.get('chat_id')
        chat_linked = context.get('chat_linked', False)

        event_bus = context['event_bus']

        log.info(f"Saga {self.saga_id}: Publishing completion event")

        # Create typed event from saga_events.py
        completion_event = CompanyCreationSagaCompleted(
            saga_id=str(self.saga_id),
            company_id=str(company_id),
            company_name=company_name,
            telegram_group_id=telegram_group_id,
            telegram_invite_link=telegram_invite_link or None,
            chat_id=str(chat_id) if chat_id else None,
            chat_linked=chat_linked,
            created_by=str(created_by),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Publish using model_dump for proper serialization
        await event_bus.publish("saga.events", completion_event.model_dump(mode='json'))

        log.info(
            f"Saga {self.saga_id}: CompanyCreationSaga completed successfully - "
            f"Company: {company_id}, Telegram: {telegram_group_id}, Chat: {chat_id}"
        )

        return {
            'completion_published': True,
            'telegram_invite_link': telegram_invite_link,
        }

    # =========================================================================
    # Utility Methods
    # =========================================================================
    async def _noop_compensate(self, **context) -> None:
        """No compensation needed for this step"""
        pass


# =============================================================================
# EOF
# =============================================================================
