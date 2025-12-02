# =============================================================================
# File: app/chat/command_handlers/message_handlers.py
# Description: Command handlers for message operations
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import TYPE_CHECKING, Optional

from app.chat.commands import (
    SendMessageCommand,
    EditMessageCommand,
    DeleteMessageCommand,
    MarkMessageAsReadCommand,
    MarkMessagesAsReadCommand,
    StartTypingCommand,
    StopTypingCommand,
)
from app.chat.aggregate import ChatAggregate
from app.chat.events import TypingStarted, TypingStopped
from app.chat.queries import GetChatByIdQuery
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies
    from app.infra.telegram.adapter import TelegramAdapter

log = logging.getLogger("wellwon.chat.handlers.message")


@command_handler(SendMessageCommand)
class SendMessageHandler(BaseCommandHandler):
    """
    Handle SendMessageCommand with bidirectional Telegram sync.

    When a message is sent from WellWon web:
    1. Store in event store (WellWon DB)
    2. Sync to Telegram if chat has telegram_chat_id
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)

    async def handle(self, command: SendMessageCommand) -> uuid.UUID:
        log.info(f"Sending message to chat {command.chat_id} from {command.sender_id}, source={command.source}")

        # Load aggregate
        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        # Send message in WellWon
        chat_aggregate.send_message(
            message_id=command.message_id,
            sender_id=command.sender_id,
            content=command.content,
            message_type=command.message_type,
            reply_to_id=command.reply_to_id,
            file_url=command.file_url,
            file_name=command.file_name,
            file_size=command.file_size,
            file_type=command.file_type,
            voice_duration=command.voice_duration,
            source=command.source,
            telegram_message_id=command.telegram_message_id,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        # Bidirectional sync: Send to Telegram if message is from WellWon (web or api), not from Telegram
        if command.source in ("web", "api") and self.telegram_adapter:
            await self._sync_to_telegram(command, chat_aggregate)

        log.info(f"Message sent: {command.message_id} to chat {command.chat_id}")
        return command.message_id

    async def _sync_to_telegram(self, command: SendMessageCommand, chat_aggregate: ChatAggregate) -> None:
        """Sync message to Telegram if chat is linked"""
        try:
            # Get chat details to find Telegram IDs
            chat_detail = await self.query_bus.query(GetChatByIdQuery(chat_id=command.chat_id))

            if not chat_detail or not chat_detail.telegram_chat_id:
                log.debug(f"Chat {command.chat_id} not linked to Telegram, skipping sync")
                return

            telegram_chat_id = chat_detail.telegram_chat_id
            telegram_topic_id = chat_detail.telegram_topic_id

            # Format chat_id for Telegram (supergroups need -100 prefix)
            # telegram_chat_id in DB is stored without prefix (e.g., 1234567890)
            # Telegram API needs format -1001234567890
            if telegram_chat_id > 0:
                telegram_chat_id = int(f"-100{telegram_chat_id}")

            log.info(f"Syncing message to Telegram: chat_id={telegram_chat_id}, topic_id={telegram_topic_id}")

            # Send based on message type
            if command.message_type == "text":
                result = await self.telegram_adapter.send_message(
                    chat_id=telegram_chat_id,
                    text=command.content,
                    topic_id=telegram_topic_id,
                )
            elif command.message_type == "voice" and command.file_url:
                result = await self.telegram_adapter.send_voice(
                    chat_id=telegram_chat_id,
                    voice_url=command.file_url,
                    duration=command.voice_duration,
                    topic_id=telegram_topic_id,
                )
            elif command.file_url:
                result = await self.telegram_adapter.send_file(
                    chat_id=telegram_chat_id,
                    file_url=command.file_url,
                    file_name=command.file_name,
                    caption=command.content if command.content else None,
                    topic_id=telegram_topic_id,
                )
            else:
                log.warning(f"Unsupported message type for Telegram sync: {command.message_type}")
                return

            if result and result.success and result.message_id:
                log.info(f"Message synced to Telegram: telegram_message_id={result.message_id}")

                # Emit MessageSyncedToTelegram event for real-time delivery status
                from app.chat.events import MessageSyncedToTelegram
                sync_event = MessageSyncedToTelegram(
                    message_id=command.message_id,
                    chat_id=command.chat_id,
                    telegram_message_id=result.message_id,
                    telegram_chat_id=telegram_chat_id,
                )

                # Publish directly to transport (no aggregate needed for this event)
                await self.event_bus.publish(
                    "transport.chat-events",
                    sync_event.model_dump()
                )
                log.debug(f"Published MessageSyncedToTelegram event for message {command.message_id}")
            else:
                log.warning(f"Failed to sync message to Telegram: {result.error if result else 'unknown error'}")

        except Exception as e:
            # Don't fail the command if Telegram sync fails
            log.error(f"Error syncing message to Telegram: {e}", exc_info=True)


@command_handler(EditMessageCommand)
class EditMessageHandler(BaseCommandHandler):
    """Handle EditMessageCommand with bidirectional Telegram sync"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)

    async def handle(self, command: EditMessageCommand) -> uuid.UUID:
        log.info(f"Editing message {command.message_id} in chat {command.chat_id}")

        # Lookup message to get telegram_message_id for sync
        telegram_message_id: Optional[int] = None
        telegram_chat_id: Optional[int] = None

        try:
            from app.chat.queries import GetMessageByIdQuery
            message = await self.query_bus.query(
                GetMessageByIdQuery(
                    chat_id=command.chat_id,
                    message_id=command.message_id
                )
            )
            if message:
                telegram_message_id = getattr(message, 'telegram_message_id', None)

            # Lookup chat to get telegram_chat_id
            chat = await self.query_bus.query(
                GetChatByIdQuery(chat_id=command.chat_id)
            )
            if chat:
                telegram_chat_id = getattr(chat, 'telegram_chat_id', None) or getattr(chat, 'telegram_supergroup_id', None)
        except Exception as e:
            log.warning(f"Failed to lookup telegram IDs for message edit: {e}")

        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        chat_aggregate.edit_message(
            message_id=command.message_id,
            edited_by=command.edited_by,
            new_content=command.new_content,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        # Bidirectional sync: Edit in Telegram if message has telegram_message_id
        if telegram_message_id and telegram_chat_id and self.telegram_adapter:
            await self._sync_edit_to_telegram(telegram_chat_id, telegram_message_id, command.new_content)

        log.info(f"Message edited: {command.message_id}, telegram_message_id={telegram_message_id}")
        return command.message_id

    async def _sync_edit_to_telegram(self, telegram_chat_id: int, telegram_message_id: int, new_content: str) -> None:
        """Sync message edit to Telegram"""
        try:
            # Format chat_id for Telegram (supergroups need -100 prefix)
            if telegram_chat_id > 0:
                telegram_chat_id = int(f"-100{telegram_chat_id}")

            log.info(f"Syncing message edit to Telegram: chat_id={telegram_chat_id}, message_id={telegram_message_id}")

            success = await self.telegram_adapter.edit_message(
                chat_id=telegram_chat_id,
                message_id=telegram_message_id,
                text=new_content
            )

            if success:
                log.info(f"Message edited in Telegram: message_id={telegram_message_id}")
            else:
                log.warning(f"Failed to edit message in Telegram: message_id={telegram_message_id}")

        except Exception as e:
            # Don't fail the command if Telegram sync fails
            log.error(f"Error syncing message edit to Telegram: {e}", exc_info=True)


@command_handler(DeleteMessageCommand)
class DeleteMessageHandler(BaseCommandHandler):
    """Handle DeleteMessageCommand (soft delete) with bidirectional Telegram sync"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)

    async def handle(self, command: DeleteMessageCommand) -> uuid.UUID:
        log.info(f"Deleting message {command.message_id} in chat {command.chat_id}")

        # Lookup message to get telegram_message_id for sync
        telegram_message_id: Optional[int] = None
        telegram_chat_id: Optional[int] = None

        try:
            from app.chat.queries import GetMessageByIdQuery
            message = await self.query_bus.query(
                GetMessageByIdQuery(
                    chat_id=command.chat_id,
                    message_id=command.message_id
                )
            )
            if message:
                telegram_message_id = getattr(message, 'telegram_message_id', None)

            # Lookup chat to get telegram_chat_id
            chat = await self.query_bus.query(
                GetChatByIdQuery(chat_id=command.chat_id)
            )
            if chat:
                telegram_chat_id = getattr(chat, 'telegram_chat_id', None) or getattr(chat, 'telegram_supergroup_id', None)
        except Exception as e:
            log.warning(f"Failed to lookup telegram IDs for message deletion: {e}")

        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        chat_aggregate.delete_message(
            message_id=command.message_id,
            deleted_by=command.deleted_by,
            telegram_message_id=telegram_message_id,
            telegram_chat_id=telegram_chat_id,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        # Bidirectional sync: Delete from Telegram if message has telegram_message_id
        if telegram_message_id and telegram_chat_id and self.telegram_adapter:
            await self._sync_delete_to_telegram(telegram_chat_id, telegram_message_id)

        log.info(f"Message deleted: {command.message_id}, telegram_message_id={telegram_message_id}")
        return command.message_id

    async def _sync_delete_to_telegram(self, telegram_chat_id: int, telegram_message_id: int) -> None:
        """Sync message deletion to Telegram"""
        try:
            # Format chat_id for Telegram (supergroups need -100 prefix)
            if telegram_chat_id > 0:
                telegram_chat_id = int(f"-100{telegram_chat_id}")

            log.info(f"Syncing message deletion to Telegram: chat_id={telegram_chat_id}, message_id={telegram_message_id}")

            success = await self.telegram_adapter.delete_message(
                chat_id=telegram_chat_id,
                message_id=telegram_message_id
            )

            if success:
                log.info(f"Message deleted from Telegram: message_id={telegram_message_id}")
            else:
                log.warning(f"Failed to delete message from Telegram: message_id={telegram_message_id}")

        except Exception as e:
            # Don't fail the command if Telegram sync fails
            log.error(f"Error syncing message deletion to Telegram: {e}", exc_info=True)


@command_handler(MarkMessageAsReadCommand)
class MarkMessageAsReadHandler(BaseCommandHandler):
    """Handle MarkMessageAsReadCommand"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: MarkMessageAsReadCommand) -> uuid.UUID:
        log.debug(f"Marking message {command.message_id} as read by {command.user_id}")

        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        chat_aggregate.mark_message_as_read(
            message_id=command.message_id,
            user_id=command.user_id,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        return command.message_id


@command_handler(MarkMessagesAsReadCommand)
class MarkMessagesAsReadHandler(BaseCommandHandler):
    """
    Handle MarkMessagesAsReadCommand (batch read) with bidirectional Telegram sync.

    When a user marks messages as read in WellWon:
    1. Update aggregate state (idempotent)
    2. Sync read status to Telegram (if chat is linked)
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)

    async def handle(self, command: MarkMessagesAsReadCommand) -> uuid.UUID:
        log.debug(f"Marking messages as read in chat {command.chat_id} by {command.user_id}")

        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        # TODO: Get actual count from read model
        # For now, use 0 as placeholder - projector will calculate actual count
        read_count = 0

        chat_aggregate.mark_messages_as_read(
            user_id=command.user_id,
            last_read_message_id=command.last_read_message_id,
            read_count=read_count,
            source=command.source,
        )

        # Check if events were actually emitted (idempotency check passed)
        events = chat_aggregate.get_uncommitted_events()
        if not events:
            log.debug(f"No events emitted - already at read position {command.last_read_message_id}")
            return command.last_read_message_id

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        # Bidirectional sync: Mark as read on Telegram if:
        # 1. Source is web/api (not from Telegram itself)
        # 2. Chat is linked to Telegram
        # 3. TelegramAdapter is available
        source = getattr(command, 'source', 'web')
        if source != 'telegram' and self.telegram_adapter:
            await self._sync_read_to_telegram(command, chat_aggregate)

        return command.last_read_message_id

    async def _sync_read_to_telegram(
        self,
        command: MarkMessagesAsReadCommand,
        chat_aggregate: ChatAggregate
    ) -> None:
        """Sync read status to Telegram"""
        try:
            # Get chat details from aggregate state first
            telegram_chat_id = chat_aggregate.state.telegram_chat_id
            telegram_topic_id = chat_aggregate.state.telegram_topic_id

            if not telegram_chat_id:
                log.debug(f"Chat {command.chat_id} not linked to Telegram, skipping read sync")
                return

            # Get telegram_message_id for the last_read_message_id
            # We need to look this up from ScyllaDB or the event data
            telegram_message_id = await self._get_telegram_message_id(
                command.chat_id,
                command.last_read_message_id
            )

            if not telegram_message_id:
                log.debug(f"No telegram_message_id found for {command.last_read_message_id}, skipping Telegram sync")
                return

            log.info(
                f"Syncing read status to Telegram: chat_id={telegram_chat_id}, "
                f"topic_id={telegram_topic_id}, max_id={telegram_message_id}"
            )

            if telegram_topic_id:
                # Forum group with topic
                success = await self.telegram_adapter.mark_topic_messages_read(
                    group_id=telegram_chat_id,
                    topic_id=telegram_topic_id,
                    max_id=telegram_message_id,
                )
            else:
                # Regular chat or group without topics
                success = await self.telegram_adapter.mark_messages_read(
                    chat_id=telegram_chat_id,
                    max_id=telegram_message_id,
                )

            if success:
                log.info(f"Read status synced to Telegram: max_id={telegram_message_id}")
            else:
                log.warning(f"Failed to sync read status to Telegram")

        except Exception as e:
            # Don't fail the command if Telegram sync fails
            log.error(f"Error syncing read status to Telegram: {e}", exc_info=True)

    async def _get_telegram_message_id(
        self,
        chat_id: uuid.UUID,
        message_id: uuid.UUID
    ) -> Optional[int]:
        """
        Get Telegram message ID for a WellWon message ID.

        Looks up the message in ScyllaDB to find the telegram_message_id.
        """
        try:
            from app.chat.queries import GetMessageByIdQuery
            message = await self.query_bus.query(
                GetMessageByIdQuery(chat_id=chat_id, message_id=message_id)
            )
            if message:
                return getattr(message, 'telegram_message_id', None)
        except Exception as e:
            log.debug(f"Could not lookup telegram_message_id: {e}")
        return None


@command_handler(StartTypingCommand)
class StartTypingHandler(BaseCommandHandler):
    """
    Handle StartTypingCommand.

    Note: Typing events are ephemeral and NOT stored in event store.
    They are only published to the transport for real-time delivery.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=None  # Don't store ephemeral events
        )

    async def handle(self, command: StartTypingCommand) -> uuid.UUID:
        log.debug(f"User {command.user_id} started typing in chat {command.chat_id}")

        # Create ephemeral event (not stored)
        event = TypingStarted(
            chat_id=command.chat_id,
            user_id=command.user_id,
        )

        # Publish directly to transport (no event store)
        event_dict = event.model_dump(mode='json', by_alias=True)
        await self.event_bus.publish(self.transport_topic, event_dict)

        return command.chat_id


@command_handler(StopTypingCommand)
class StopTypingHandler(BaseCommandHandler):
    """Handle StopTypingCommand (ephemeral)"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=None  # Don't store ephemeral events
        )

    async def handle(self, command: StopTypingCommand) -> uuid.UUID:
        log.debug(f"User {command.user_id} stopped typing in chat {command.chat_id}")

        event = TypingStopped(
            chat_id=command.chat_id,
            user_id=command.user_id,
        )

        # Publish directly to transport (no event store)
        event_dict = event.model_dump(mode='json', by_alias=True)
        await self.event_bus.publish(self.transport_topic, event_dict)

        return command.chat_id
