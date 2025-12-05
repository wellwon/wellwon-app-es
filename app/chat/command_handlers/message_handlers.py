# =============================================================================
# File: app/chat/command_handlers/message_handlers.py
# Description: Command handlers for message operations
# =============================================================================

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Optional, Tuple

from app.chat.commands import (
    SendMessageCommand,
    EditMessageCommand,
    DeleteMessageCommand,
    MarkMessageAsReadCommand,
    MarkMessagesAsReadCommand,
    StartTypingCommand,
    StopTypingCommand,
    UpdateMessageFileUrlCommand,
)
from app.chat.aggregate import ChatAggregate
from app.chat.events import TypingStarted, TypingStopped, MessageFileUrlUpdated
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler
from app.infra.persistence.scylladb import generate_snowflake_id

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies
    from app.infra.telegram.adapter import TelegramAdapter

log = logging.getLogger("wellwon.chat.handlers.message")


@command_handler(SendMessageCommand)
class SendMessageHandler(BaseCommandHandler):
    """
    Handle SendMessageCommand with bidirectional Telegram sync.

    When a message is sent from WellWon web:
    1. Check idempotency key (prevents duplicate messages on retry)
    2. Store in event store (WellWon DB)
    3. Sync to Telegram if chat has telegram_chat_id (from aggregate state)
    """

    # Redis key prefix for idempotency
    IDEMPOTENCY_PREFIX = "msg:idempotency:"
    IDEMPOTENCY_TTL = 3600 * 24  # 24 hours

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)
        self.redis_client = getattr(deps, 'redis_client', None)

    async def handle(self, command: SendMessageCommand) -> Tuple[int, Optional[str]]:
        """
        Handle SendMessageCommand.

        Returns:
            Tuple of (snowflake_id, client_temp_id) for response reconciliation.
            - snowflake_id: Server-generated permanent ID (int64)
            - client_temp_id: Echo back client's temp ID for optimistic UI reconciliation

        Exactly-once delivery:
            If idempotency_key is provided and was already processed,
            returns the existing snowflake_id without creating a duplicate message.
        """
        # Check idempotency key for exactly-once delivery
        if command.idempotency_key and self.redis_client:
            existing_id = await self._check_idempotency(command.idempotency_key)
            if existing_id:
                log.info(
                    f"[IDEMPOTENCY] Duplicate request detected: key={command.idempotency_key}, "
                    f"returning existing snowflake_id={existing_id}"
                )
                return (existing_id, command.client_temp_id)

        # Generate server-side Snowflake ID (Discord/Twitter pattern)
        snowflake_id = generate_snowflake_id()

        # Store idempotency key -> snowflake_id mapping ATOMICALLY
        # This prevents race conditions with concurrent requests
        if command.idempotency_key and self.redis_client:
            stored = await self._store_idempotency_atomic(command.idempotency_key, snowflake_id)
            if not stored:
                # Another request won the race - fetch their result
                existing_id = await self._check_idempotency(command.idempotency_key)
                if existing_id:
                    log.info(
                        f"[IDEMPOTENCY] Race condition resolved: key={command.idempotency_key}, "
                        f"returning winner's snowflake_id={existing_id}"
                    )
                    return (existing_id, command.client_temp_id)
                # If still no existing_id, proceed anyway (Redis inconsistency, rare)
                log.warning(f"[IDEMPOTENCY] Race detected but no existing_id found, proceeding")

        log.info(
            f"Sending message to chat {command.chat_id} from {command.sender_id}, "
            f"snowflake_id={snowflake_id}, source={command.source}"
        )

        # Load aggregate from Event Store
        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        # Send message in WellWon with server-generated Snowflake ID
        chat_aggregate.send_message(
            message_id=snowflake_id,  # Server-generated Snowflake (int64)
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
            client_temp_id=command.client_temp_id,  # For frontend reconciliation
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        # Bidirectional sync: Send to Telegram if message is from WellWon (web or api), not from Telegram
        if command.source in ("web", "api") and self.telegram_adapter:
            await self._sync_to_telegram(command, chat_aggregate, snowflake_id)

        log.info(f"Message sent: snowflake_id={snowflake_id} to chat {command.chat_id}")
        # Return both IDs for frontend reconciliation
        return (snowflake_id, command.client_temp_id)

    async def _sync_to_telegram(self, command: SendMessageCommand, chat_aggregate: ChatAggregate, snowflake_id: int) -> None:
        """Sync message to Telegram if chat is linked (using aggregate state, not query)"""
        try:
            # Get Telegram IDs from aggregate state (set by TelegramChatLinked event)
            telegram_chat_id_raw = chat_aggregate.state.telegram_chat_id
            telegram_topic_id = chat_aggregate.state.telegram_topic_id

            if not telegram_chat_id_raw:
                log.debug(f"Chat {command.chat_id} not linked to Telegram, skipping sync")
                return

            # Format chat_id for Telegram API (supergroups need -100 prefix)
            # telegram_chat_id in DB is stored without prefix (e.g., 1234567890)
            # Telegram API needs format -1001234567890
            # IMPORTANT: Keep the RAW ID for telegram_message_mapping (read receipts use raw ID)
            telegram_chat_id_for_api = telegram_chat_id_raw
            if telegram_chat_id_raw > 0:
                telegram_chat_id_for_api = int(f"-100{telegram_chat_id_raw}")

            log.info(f"Syncing message to Telegram: chat_id={telegram_chat_id_for_api}, topic_id={telegram_topic_id}")

            # Send based on message type (use API-formatted chat_id)
            if command.message_type == "text":
                result = await self.telegram_adapter.send_message(
                    chat_id=telegram_chat_id_for_api,
                    text=command.content,
                    topic_id=telegram_topic_id,
                )
            elif command.message_type == "voice" and command.file_url:
                result = await self.telegram_adapter.send_voice(
                    chat_id=telegram_chat_id_for_api,
                    voice_url=command.file_url,
                    duration=command.voice_duration,
                    topic_id=telegram_topic_id,
                )
            elif command.file_url:
                result = await self.telegram_adapter.send_file(
                    chat_id=telegram_chat_id_for_api,
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
                # IMPORTANT: Use telegram_chat_id_raw (without -100 prefix) for mapping
                # This matches what Telegram sends in read receipts (ReadHistoryOutbox)
                from app.chat.events import MessageSyncedToTelegram
                sync_event = MessageSyncedToTelegram(
                    message_id=snowflake_id,  # Use server-generated Snowflake ID
                    chat_id=command.chat_id,
                    telegram_message_id=result.message_id,
                    telegram_chat_id=telegram_chat_id_raw,  # RAW ID for mapping lookup
                )

                # Publish directly to transport (no aggregate needed for this event)
                # IMPORTANT: Use mode='json' to serialize UUIDs as strings for Kafka
                await self.event_bus.publish(
                    "transport.chat-events",
                    sync_event.model_dump(mode='json')
                )
                log.debug(f"Published MessageSyncedToTelegram event for message {snowflake_id}")
            else:
                log.warning(f"Failed to sync message to Telegram: {result.error if result else 'unknown error'}")

        except Exception as e:
            # Don't fail the command if Telegram sync fails
            log.error(f"Error syncing message to Telegram: {e}")

    async def _check_idempotency(self, idempotency_key: str) -> Optional[int]:
        """Check if idempotency key was already processed, return existing snowflake_id."""
        try:
            key = f"{self.IDEMPOTENCY_PREFIX}{idempotency_key}"
            result = await self.redis_client.get(key)
            if result:
                return int(result)
            return None
        except ValueError:
            log.error(f"[IDEMPOTENCY] Invalid snowflake_id in cache for key={idempotency_key}")
            return None
        except Exception as e:
            # Fail safe: proceed without dedup (may create duplicate, but service works)
            log.error(f"[IDEMPOTENCY] Redis failure checking key: {e}")
            return None

    async def _store_idempotency_atomic(self, idempotency_key: str, snowflake_id: int) -> bool:
        """
        Store idempotency key -> snowflake_id mapping ATOMICALLY using SET NX.

        Returns True if stored successfully (key was new).
        Returns False if key already existed (another request won the race).

        This prevents race conditions where two concurrent requests both pass
        the idempotency check and create duplicate messages.
        """
        try:
            key = f"{self.IDEMPOTENCY_PREFIX}{idempotency_key}"
            # SET NX: Only set if key doesn't exist (atomic operation)
            result = await self.redis_client.set(
                key,
                str(snowflake_id),
                nx=True,  # CRITICAL: Only set if Not eXists
                ex=self.IDEMPOTENCY_TTL
            )
            if result:
                log.debug(f"[IDEMPOTENCY] Stored key={idempotency_key} -> snowflake_id={snowflake_id}")
                return True
            else:
                log.info(f"[IDEMPOTENCY] Key already exists (race condition): {idempotency_key}")
                return False
        except Exception as e:
            log.error(f"[IDEMPOTENCY] Failed to store key atomically: {e}")
            # Fail safe: assume stored (may duplicate, but won't lose message)
            return True


@command_handler(EditMessageCommand)
class EditMessageHandler(BaseCommandHandler):
    """Handle EditMessageCommand with bidirectional Telegram sync.

    telegram_message_id comes in the command (enriched by router).
    telegram_chat_id comes from aggregate state.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)

    async def handle(self, command: EditMessageCommand) -> uuid.UUID:
        log.info(f"Editing message {command.message_id} in chat {command.chat_id}")

        # Load aggregate from Event Store
        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        # Get Telegram IDs: chat_id from aggregate state, message_id from command
        telegram_chat_id = chat_aggregate.state.telegram_chat_id
        telegram_message_id = command.telegram_message_id

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
    """Handle DeleteMessageCommand (soft delete) with bidirectional Telegram sync.

    telegram_message_id comes in the command (enriched by router).
    telegram_chat_id comes from aggregate state.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)

    async def handle(self, command: DeleteMessageCommand) -> uuid.UUID:
        log.info(f"Deleting message {command.message_id} in chat {command.chat_id}")

        # Load aggregate from Event Store
        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        # Get Telegram IDs: chat_id from aggregate state, message_id from command
        telegram_chat_id = chat_aggregate.state.telegram_chat_id
        telegram_message_id = command.telegram_message_id

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
    Handle MarkMessagesAsReadCommand (batch read) - Pure Event Sourcing.

    When a user marks messages as read in WellWon:
    1. Update aggregate state (idempotent)
    2. Emit MessagesMarkedAsRead event with Telegram sync data
    3. TelegramListener handles actual sync to Telegram (separate concern)

    telegram_message_id comes in the command (enriched by router).
    telegram_chat_id/topic_id come from aggregate state and are included in event.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        # NO telegram_adapter - listener handles sync

    async def handle(self, command: MarkMessagesAsReadCommand) -> int:
        log.debug(f"Marking messages as read in chat {command.chat_id} by {command.user_id}")

        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        # TODO: Get actual count from read model
        # For now, use 0 as placeholder - projector will calculate actual count
        read_count = 0

        # Pass telegram_message_id to aggregate - it will include all Telegram data in event
        chat_aggregate.mark_messages_as_read(
            user_id=command.user_id,
            last_read_message_id=command.last_read_message_id,
            read_count=read_count,
            source=command.source,
            telegram_message_id=command.telegram_message_id,  # For bidirectional sync
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

        # Telegram sync is handled by TelegramListener.on_messages_marked_as_read()
        # Event contains telegram_chat_id, telegram_topic_id, telegram_message_id

        return command.last_read_message_id


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


@command_handler(UpdateMessageFileUrlCommand)
class UpdateMessageFileUrlHandler(BaseCommandHandler):
    """
    Handle UpdateMessageFileUrlCommand - update message file URL after async upload.

    This handler is part of the fire-and-forget pattern for fast incoming Telegram messages:
    1. Message arrives from Telegram with file_id
    2. Message is stored immediately with temp Telegram CDN URL
    3. Background task downloads file, uploads to MinIO
    4. This handler updates the message with permanent MinIO URL
    5. Event is published to WSE for real-time frontend update

    Performance: Direct ScyllaDB update (no aggregate needed) + WSE publish.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=None  # Direct ScyllaDB update, not via aggregate
        )
        # Lazy import to avoid circular dependency
        self._scylla_repo = None

    @property
    def scylla_repo(self):
        if self._scylla_repo is None:
            from app.infra.read_repos.message_scylla_repo import get_message_scylla_repo
            self._scylla_repo = get_message_scylla_repo()
        return self._scylla_repo

    async def handle(self, command: UpdateMessageFileUrlCommand) -> int:
        log.info(
            f"Updating file URL for message {command.message_id} in chat {command.chat_id}"
        )

        # Direct ScyllaDB update (no aggregate - performance optimization)
        await self.scylla_repo.update_message_file_url(
            channel_id=command.chat_id,
            message_id=command.message_id,
            file_url=command.new_file_url,
            file_name=command.file_name,
            file_size=command.file_size,
            file_type=command.file_type,
        )

        # Create and publish event for WSE real-time update
        event = MessageFileUrlUpdated(
            message_id=command.message_id,
            chat_id=command.chat_id,
            new_file_url=command.new_file_url,
            file_name=command.file_name,
            file_size=command.file_size,
            file_type=command.file_type,
        )

        # Publish directly to transport for real-time delivery
        event_dict = event.model_dump(mode='json', by_alias=True)
        await self.event_bus.publish(self.transport_topic, event_dict)

        log.info(
            f"File URL updated for message {command.message_id}: {command.new_file_url}"
        )
        return command.message_id
