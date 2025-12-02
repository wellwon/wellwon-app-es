# =============================================================================
# File: app/chat/command_handlers/chat_handlers.py
# Description: Command handlers for chat lifecycle operations
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import TYPE_CHECKING, List, Optional

from app.chat.commands import (
    CreateChatCommand,
    UpdateChatCommand,
    ArchiveChatCommand,
    RestoreChatCommand,
    DeleteChatCommand,
    LinkChatToCompanyCommand,
    UnlinkChatFromCompanyCommand,
)
from app.chat.aggregate import ChatAggregate
from app.chat.enums import ParticipantRole
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies
    from app.infra.telegram.adapter import TelegramAdapter

log = logging.getLogger("wellwon.chat.handlers.chat")


@command_handler(CreateChatCommand)
class CreateChatHandler(BaseCommandHandler):
    """
    Handle CreateChatCommand using pure Event Sourcing.

    Creates a new chat and optionally adds initial participants.
    The creator is automatically added as admin.

    IMPORTANT: All data (company_id, telegram_supergroup_id) must come in the command,
    pre-enriched by the caller (API router or Saga). Command handlers do NOT query.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)

    async def handle(self, command: CreateChatCommand) -> uuid.UUID:
        log.info(f"Creating {command.chat_type} chat by user {command.created_by}")

        # All data comes from command (pre-enriched by caller)
        telegram_supergroup_id = command.telegram_supergroup_id
        telegram_topic_id = command.telegram_topic_id
        company_id = command.company_id

        # If we have a supergroup and no topic_id yet, create a Telegram topic
        # (telegram_adapter is infrastructure, not a query - this is allowed)
        if telegram_supergroup_id and not telegram_topic_id and self.telegram_adapter:
            telegram_topic_id = await self._create_telegram_topic(
                telegram_supergroup_id,
                command.name or "Новый чат",
            )

        # Create new aggregate
        chat_aggregate = ChatAggregate(chat_id=command.chat_id)

        # Create the chat with data from command
        chat_aggregate.create_chat(
            name=command.name,
            chat_type=command.chat_type,
            created_by=command.created_by,
            company_id=company_id,
            telegram_supergroup_id=telegram_supergroup_id,
            telegram_topic_id=telegram_topic_id,
        )

        # Add creator as admin
        chat_aggregate.add_participant(
            user_id=command.created_by,
            role=ParticipantRole.ADMIN.value,
            added_by=command.created_by,
        )

        # Add other participants as members
        for participant_id in command.participant_ids:
            if participant_id != command.created_by:
                chat_aggregate.add_participant(
                    user_id=participant_id,
                    role=ParticipantRole.MEMBER.value,
                    added_by=command.created_by,
                )

        # Publish all events
        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Chat created: {command.chat_id} with {len(command.participant_ids) + 1} participants, telegram_topic_id={telegram_topic_id}")
        return command.chat_id

    async def _create_telegram_topic(
        self,
        supergroup_id: int,
        chat_name: str,
    ) -> Optional[int]:
        """
        Create a Telegram topic in the supergroup.
        This is infrastructure operation (not a query).
        """
        try:
            log.info(f"Creating Telegram topic '{chat_name}' in supergroup {supergroup_id}")

            topic_info = await self.telegram_adapter.create_chat_topic(
                group_id=supergroup_id,
                topic_name=chat_name,
            )

            if topic_info:
                log.info(f"Telegram topic created: id={topic_info.topic_id}, name={topic_info.title}")
                return topic_info.topic_id
            else:
                log.warning(f"Failed to create Telegram topic for chat '{chat_name}'")
                return None

        except Exception as e:
            # Don't fail chat creation if Telegram sync fails
            log.error(f"Error creating Telegram topic: {e}", exc_info=True)
            return None


@command_handler(UpdateChatCommand)
class UpdateChatHandler(BaseCommandHandler):
    """Handle UpdateChatCommand - Telegram sync via TelegramEventListener"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UpdateChatCommand) -> uuid.UUID:
        log.info(f"Updating chat {command.chat_id}")

        # Load aggregate from event store
        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        log.debug(f"Chat state: company_id={chat_aggregate.state.company_id}, participants={list(chat_aggregate.state.participants.keys())}, version={chat_aggregate.version}")

        # Auto-enroll user as participant if they're not yet a participant
        # For company chats, we allow any authenticated user to manage (they should be company members)
        if not chat_aggregate.is_participant(command.updated_by):
            log.info(f"User {command.updated_by} is not a participant, auto-enrolling as admin")
            chat_aggregate.add_participant(
                user_id=command.updated_by,
                role=ParticipantRole.ADMIN.value,
                added_by=command.updated_by,
            )

        # Update chat
        chat_aggregate.update_chat(
            name=command.name,
            updated_by=command.updated_by,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        # Telegram sync (topic rename) handled by TelegramEventListener via EventBus (CQRS pattern)
        log.info(f"Chat updated: {command.chat_id}")
        return command.chat_id


@command_handler(ArchiveChatCommand)
class ArchiveChatHandler(BaseCommandHandler):
    """Handle ArchiveChatCommand (soft delete) with bidirectional Telegram sync"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)

    async def handle(self, command: ArchiveChatCommand) -> uuid.UUID:
        log.info(f"Archiving chat {command.chat_id}")

        # Load aggregate - telegram IDs come from aggregate state (Event Sourcing)
        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        # Get telegram IDs from aggregate state (set by TelegramChatLinked event)
        telegram_supergroup_id = chat_aggregate.state.telegram_chat_id
        telegram_topic_id = chat_aggregate.state.telegram_topic_id

        log.info(f"Chat state for archive: company_id={chat_aggregate.state.company_id}, participants={list(chat_aggregate.state.participants.keys())}")

        # Auto-enroll user as admin if they're not yet a participant
        if not chat_aggregate.is_participant(command.archived_by):
            log.info(f"User {command.archived_by} is not a participant, auto-enrolling as admin for archive")
            chat_aggregate.add_participant(
                user_id=command.archived_by,
                role=ParticipantRole.ADMIN.value,
                added_by=command.archived_by,
            )

        chat_aggregate.archive_chat(
            archived_by=command.archived_by,
            telegram_supergroup_id=telegram_supergroup_id,
            telegram_topic_id=telegram_topic_id,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        # Bidirectional sync: Close topic in Telegram (preserves messages, prevents new ones)
        if telegram_supergroup_id and telegram_topic_id and self.telegram_adapter:
            await self._sync_archive_to_telegram(telegram_supergroup_id, telegram_topic_id)

        log.info(f"Chat archived: {command.chat_id}, telegram_topic_id={telegram_topic_id}")
        return command.chat_id

    async def _sync_archive_to_telegram(self, group_id: int, topic_id: int) -> None:
        """Sync chat archive to Telegram by closing the topic"""
        try:
            log.info(f"Closing Telegram topic: group_id={group_id}, topic_id={topic_id}")

            success = await self.telegram_adapter.close_topic(
                group_id=group_id,
                topic_id=topic_id,
                closed=True
            )

            if success:
                log.info(f"Telegram topic {topic_id} closed successfully")
            else:
                log.warning(f"Failed to close Telegram topic {topic_id}")

        except Exception as e:
            # Don't fail the command if Telegram sync fails
            log.error(f"Error closing Telegram topic: {e}", exc_info=True)


@command_handler(RestoreChatCommand)
class RestoreChatHandler(BaseCommandHandler):
    """Handle RestoreChatCommand with bidirectional Telegram sync"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)

    async def handle(self, command: RestoreChatCommand) -> uuid.UUID:
        log.info(f"Restoring chat {command.chat_id}")

        # Load aggregate - telegram IDs come from aggregate state (Event Sourcing)
        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        # Get telegram IDs from aggregate state
        telegram_supergroup_id = chat_aggregate.state.telegram_chat_id
        telegram_topic_id = chat_aggregate.state.telegram_topic_id

        chat_aggregate.restore_chat(restored_by=command.restored_by)

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        # Bidirectional sync: Reopen topic in Telegram
        if telegram_supergroup_id and telegram_topic_id and self.telegram_adapter:
            await self._sync_restore_to_telegram(telegram_supergroup_id, telegram_topic_id)

        log.info(f"Chat restored: {command.chat_id}, telegram_topic_id={telegram_topic_id}")
        return command.chat_id

    async def _sync_restore_to_telegram(self, group_id: int, topic_id: int) -> None:
        """Sync chat restore to Telegram by reopening the topic"""
        try:
            log.info(f"Reopening Telegram topic: group_id={group_id}, topic_id={topic_id}")

            success = await self.telegram_adapter.close_topic(
                group_id=group_id,
                topic_id=topic_id,
                closed=False  # Reopen
            )

            if success:
                log.info(f"Telegram topic {topic_id} reopened successfully")
            else:
                log.warning(f"Failed to reopen Telegram topic {topic_id}")

        except Exception as e:
            # Don't fail the command if Telegram sync fails
            log.error(f"Error reopening Telegram topic: {e}", exc_info=True)


@command_handler(DeleteChatCommand)
class DeleteChatHandler(BaseCommandHandler):
    """Handle DeleteChatCommand (hard delete) with bidirectional Telegram sync"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)

    async def handle(self, command: DeleteChatCommand) -> uuid.UUID:
        log.info(f"Hard deleting chat {command.chat_id}")

        # Retry loop for optimistic concurrency conflicts
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Load aggregate - telegram IDs come from aggregate state (Event Sourcing)
                chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

                # Get telegram IDs from aggregate state
                telegram_supergroup_id = chat_aggregate.state.telegram_chat_id
                telegram_topic_id = chat_aggregate.state.telegram_topic_id

                chat_aggregate.hard_delete_chat(
                    deleted_by=command.deleted_by,
                    reason=command.reason,
                    telegram_supergroup_id=telegram_supergroup_id,
                    telegram_topic_id=telegram_topic_id,
                )

                # Check if any events were generated
                has_new_events = len(chat_aggregate.get_uncommitted_events()) > 0

                if has_new_events:
                    await self.publish_events(
                        aggregate=chat_aggregate,
                        aggregate_id=command.chat_id,
                        command=command
                    )
                else:
                    # Already deleted - projector will handle read model cleanup via event replay
                    log.info(f"Chat {command.chat_id} already deleted in EventStore")

                # Success - break retry loop
                break

            except Exception as e:
                if "concurrency" in str(e).lower() and attempt < max_retries - 1:
                    log.warning(f"Concurrency conflict on delete attempt {attempt + 1}, retrying...")
                    continue
                raise

        # Telegram sync handled by TelegramEventListener via EventBus (CQRS pattern)
        log.info(f"Chat hard deleted: {command.chat_id}, telegram_topic_id={telegram_topic_id}")
        return command.chat_id


# =============================================================================
# Company Linking Handlers (used by CompanyCreationSaga)
# =============================================================================

@command_handler(LinkChatToCompanyCommand)
class LinkChatToCompanyHandler(BaseCommandHandler):
    """
    Handle LinkChatToCompanyCommand.
    Used by CompanyCreationSaga to link existing chats to newly created companies.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: LinkChatToCompanyCommand) -> uuid.UUID:
        log.info(f"Linking chat {command.chat_id} to company {command.company_id}")

        # Load aggregate from event store
        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        # Link to company
        chat_aggregate.link_to_company(
            company_id=command.company_id,
            linked_by=command.linked_by,
            telegram_supergroup_id=command.telegram_supergroup_id,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Chat {command.chat_id} linked to company {command.company_id}")
        return command.chat_id


@command_handler(UnlinkChatFromCompanyCommand)
class UnlinkChatFromCompanyHandler(BaseCommandHandler):
    """
    Handle UnlinkChatFromCompanyCommand.
    Used by saga compensation when company creation fails.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UnlinkChatFromCompanyCommand) -> uuid.UUID:
        log.info(f"Unlinking chat {command.chat_id} from company")

        # Load aggregate from event store
        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        # Unlink from company
        chat_aggregate.unlink_from_company(
            unlinked_by=command.unlinked_by,
            reason=command.reason,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Chat {command.chat_id} unlinked from company")
        return command.chat_id
