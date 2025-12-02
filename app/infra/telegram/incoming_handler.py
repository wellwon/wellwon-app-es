# =============================================================================
# File: app/infra/telegram/incoming_handler.py
# Description: Handles incoming Telegram messages -> Domain Events
# =============================================================================
# Bidirectional Sync:
#   - Incoming messages from Telegram webhook -> Chat Domain Events
#   - Outgoing messages from Chat Domain Events -> Telegram (in listener.py)
# =============================================================================

from __future__ import annotations

import asyncio
from typing import Optional, Any, Dict, TYPE_CHECKING
from uuid import UUID, uuid4
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config.logging_config import get_logger
from app.security.telegram_security import (
    TelegramRedisDeduplicator,
    MessageDeduplicator,
    DeduplicationResult,
)

# Metrics import (optional)
try:
    from app.infra.metrics.telegram_metrics import (
        telegram_webhook_messages_total,
        record_dedup_check,
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

if TYPE_CHECKING:
    from app.infra.cqrs.command_bus import CommandBus
    from app.infra.cqrs.query_bus import QueryBus
    from app.infra.event_bus.redpanda_event_bus import RedpandaEventBus
    from app.infra.telegram.mtproto_client import ReadEventInfo

log = get_logger("wellwon.telegram.incoming")


@dataclass
class IncomingTelegramMessage:
    """Parsed incoming Telegram message."""
    # Telegram identifiers
    telegram_message_id: int
    telegram_chat_id: int
    telegram_topic_id: Optional[int] = None
    telegram_user_id: Optional[int] = None
    telegram_username: Optional[str] = None

    # Message content
    text: Optional[str] = None
    message_type: str = "text"  # text, photo, document, voice, video, sticker

    # File info (for media)
    file_id: Optional[str] = None
    file_unique_id: Optional[str] = None
    file_size: Optional[int] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None

    # Reply info
    reply_to_message_id: Optional[int] = None

    # Voice/audio specific
    voice_duration: Optional[int] = None  # seconds

    # Timestamps
    date: Optional[datetime] = None

    # Raw data for debugging
    raw_data: Optional[Dict[str, Any]] = None


class TelegramIncomingHandler:
    """
    Handles incoming Telegram messages and converts them to domain commands.

    This is the Telegram -> WellWon direction of bidirectional sync.

    Flow:
    1. Webhook receives update from Telegram
    2. Parse message into IncomingTelegramMessage
    3. Deduplicate (prevent double processing)
    4. Lookup WellWon chat by telegram_chat_id + telegram_topic_id
    5. Lookup or create WellWon user by telegram_user_id
    6. Dispatch SendMessageCommand to Chat Domain
    7. Chat Domain emits MessageSent event (listener.py ignores source="telegram")
    """

    def __init__(
        self,
        command_bus: 'CommandBus',
        query_bus: 'QueryBus',
        event_bus: Optional['RedpandaEventBus'] = None,
        redis_client: Optional[Any] = None,
        dedup_ttl: int = 300,  # 5 minutes
    ):
        """
        Initialize incoming handler.

        Args:
            command_bus: CQRS command bus for dispatching commands
            query_bus: CQRS query bus for lookups
            event_bus: Event bus for publishing domain events (read receipts)
            redis_client: Redis for distributed deduplication
            dedup_ttl: Deduplication TTL in seconds
        """
        self._command_bus = command_bus
        self._query_bus = query_bus
        self._event_bus = event_bus

        # Deduplication
        if redis_client:
            self._deduplicator = TelegramRedisDeduplicator(
                redis_client=redis_client,
                ttl_seconds=dedup_ttl,
            )
        else:
            self._deduplicator = MessageDeduplicator(
                ttl_seconds=dedup_ttl,
            )

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize handler."""
        self._initialized = True
        log.info("TelegramIncomingHandler initialized")

    async def handle_update(self, update: Dict[str, Any]) -> Optional[UUID]:
        """
        Handle incoming Telegram update.

        Args:
            update: Raw Telegram update dict from webhook

        Returns:
            WellWon message ID if message was processed, None otherwise
        """
        if not self._initialized:
            log.warning("Handler not initialized")
            return None

        # Parse the update
        message = self._parse_update(update)
        if not message:
            log.debug("Update is not a processable message")
            return None

        # Deduplicate
        dedup_result = await self._check_duplicate(message)
        if dedup_result.is_duplicate:
            log.debug(
                f"Duplicate message {message.telegram_message_id} "
                f"from chat {message.telegram_chat_id}"
            )
            if METRICS_AVAILABLE:
                record_dedup_check(is_duplicate=True)
            return None

        if METRICS_AVAILABLE:
            record_dedup_check(is_duplicate=False)
            telegram_webhook_messages_total.labels(
                message_type=message.message_type
            ).inc()

        # Process the message
        return await self._process_message(message)

    def _parse_update(self, update: Dict[str, Any]) -> Optional[IncomingTelegramMessage]:
        """Parse Telegram update into IncomingTelegramMessage."""
        # Get message from update (could be message, edited_message, channel_post, etc.)
        msg = (
            update.get("message") or
            update.get("edited_message") or
            update.get("channel_post") or
            update.get("edited_channel_post")
        )

        if not msg:
            # Could be callback_query, inline_query, etc.
            return None

        # Extract chat info
        chat = msg.get("chat", {})
        telegram_chat_id = chat.get("id")
        if not telegram_chat_id:
            return None

        # Extract topic (for forum groups)
        telegram_topic_id = msg.get("message_thread_id")

        # Extract user info
        from_user = msg.get("from", {})
        telegram_user_id = from_user.get("id")
        telegram_username = from_user.get("username")

        # Determine message type and content
        message_type = "text"
        text = None
        file_id = None
        file_unique_id = None
        file_size = None
        file_name = None
        mime_type = None
        voice_duration = None

        if msg.get("text"):
            message_type = "text"
            text = msg["text"]
        elif msg.get("photo"):
            message_type = "photo"
            # Get largest photo
            photo = max(msg["photo"], key=lambda p: p.get("file_size", 0))
            file_id = photo.get("file_id")
            file_unique_id = photo.get("file_unique_id")
            file_size = photo.get("file_size")
            text = msg.get("caption")
        elif msg.get("document"):
            message_type = "document"
            doc = msg["document"]
            file_id = doc.get("file_id")
            file_unique_id = doc.get("file_unique_id")
            file_size = doc.get("file_size")
            file_name = doc.get("file_name")
            mime_type = doc.get("mime_type")
            text = msg.get("caption")
        elif msg.get("voice"):
            message_type = "voice"
            voice = msg["voice"]
            file_id = voice.get("file_id")
            file_unique_id = voice.get("file_unique_id")
            file_size = voice.get("file_size")
            mime_type = voice.get("mime_type")
            voice_duration = voice.get("duration")  # Voice duration in seconds
        elif msg.get("video"):
            message_type = "video"
            video = msg["video"]
            file_id = video.get("file_id")
            file_unique_id = video.get("file_unique_id")
            file_size = video.get("file_size")
            file_name = video.get("file_name")
            mime_type = video.get("mime_type")
            text = msg.get("caption")
        elif msg.get("sticker"):
            message_type = "sticker"
            sticker = msg["sticker"]
            file_id = sticker.get("file_id")
            file_unique_id = sticker.get("file_unique_id")
        elif msg.get("audio"):
            message_type = "audio"
            audio = msg["audio"]
            file_id = audio.get("file_id")
            file_unique_id = audio.get("file_unique_id")
            file_size = audio.get("file_size")
            file_name = audio.get("file_name")
            mime_type = audio.get("mime_type")
            text = msg.get("caption")
        else:
            # Unsupported message type
            return None

        # Parse date
        date = None
        if msg.get("date"):
            date = datetime.fromtimestamp(msg["date"], tz=timezone.utc)

        return IncomingTelegramMessage(
            telegram_message_id=msg.get("message_id", 0),
            telegram_chat_id=telegram_chat_id,
            telegram_topic_id=telegram_topic_id,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            text=text,
            message_type=message_type,
            file_id=file_id,
            file_unique_id=file_unique_id,
            file_size=file_size,
            file_name=file_name,
            mime_type=mime_type,
            reply_to_message_id=msg.get("reply_to_message", {}).get("message_id"),
            voice_duration=voice_duration,
            date=date,
            raw_data=msg,
        )

    async def _check_duplicate(
        self,
        message: IncomingTelegramMessage
    ) -> DeduplicationResult:
        """Check if message is duplicate."""
        if isinstance(self._deduplicator, TelegramRedisDeduplicator):
            return await self._deduplicator.check_and_mark(
                message.telegram_chat_id,
                message.telegram_message_id,
            )
        else:
            return self._deduplicator.check_and_mark(
                message.telegram_chat_id,
                message.telegram_message_id,
            )

    async def _process_message(
        self,
        message: IncomingTelegramMessage
    ) -> Optional[UUID]:
        """
        Process incoming message and dispatch to Chat Domain.

        Returns WellWon message ID if successful.
        """
        try:
            # 1. Lookup WellWon chat by Telegram IDs
            chat_id = await self._lookup_chat(
                message.telegram_chat_id,
                message.telegram_topic_id,
            )

            if not chat_id:
                log.debug(
                    f"No WellWon chat found for Telegram chat "
                    f"{message.telegram_chat_id} topic {message.telegram_topic_id}"
                )
                return None

            # 2. Lookup or create WellWon user
            user_id = await self._lookup_or_create_user(message)
            if not user_id:
                log.warning(f"Could not resolve user for Telegram user {message.telegram_user_id}")
                # Use system user or anonymous
                user_id = await self._get_system_user_id()

            # 3. Download file if present
            file_url = None
            if message.file_id:
                file_url = await self._download_and_store_file(message)

            # 4. Dispatch SendMessageCommand
            from app.chat.commands import SendMessageCommand

            command = SendMessageCommand(
                chat_id=chat_id,
                sender_id=user_id,
                content=message.text or "",
                message_type=message.message_type,
                file_url=file_url,
                file_name=message.file_name,
                file_size=message.file_size,
                file_type=message.mime_type,
                voice_duration=message.voice_duration,  # For voice messages
                source="telegram",  # Mark source so listener ignores it
                telegram_message_id=message.telegram_message_id,  # For bidirectional tracking
            )

            result = await self._command_bus.send(command)

            log.info(
                f"Processed Telegram message {message.telegram_message_id} "
                f"-> WellWon message {result}"
            )

            return result

        except Exception as e:
            log.error(f"Error processing Telegram message: {e}", exc_info=True)
            return None

    async def _lookup_chat(
        self,
        telegram_chat_id: int,
        telegram_topic_id: Optional[int],
    ) -> Optional[UUID]:
        """
        Lookup WellWon chat by Telegram identifiers.

        Returns WellWon chat_id if found.
        """
        try:
            from app.chat.queries import GetChatByExternalIdQuery

            result = await self._query_bus.query(
                GetChatByExternalIdQuery(
                    external_channel_type="telegram",
                    external_channel_id=str(telegram_chat_id),
                    external_topic_id=str(telegram_topic_id) if telegram_topic_id else None,
                )
            )

            return result.chat_id if result else None

        except Exception as e:
            log.warning(f"Error looking up chat: {e}")
            return None

    async def _lookup_or_create_user(
        self,
        message: IncomingTelegramMessage
    ) -> Optional[UUID]:
        """
        Lookup WellWon user by Telegram user ID.

        If user doesn't exist, could create a placeholder or return None.
        """
        if not message.telegram_user_id:
            return None

        try:
            from app.user_account.queries import GetUserByExternalIdQuery

            result = await self._query_bus.query(
                GetUserByExternalIdQuery(
                    provider="telegram",
                    external_id=str(message.telegram_user_id),
                )
            )

            return result.user_id if result else None

        except Exception as e:
            log.debug(f"User lookup failed: {e}")
            return None

    async def _get_system_user_id(self) -> UUID:
        """Get system user ID for anonymous messages."""
        # Return a fixed system user UUID or lookup from config
        return UUID("00000000-0000-0000-0000-000000000000")

    async def _download_and_store_file(
        self,
        message: IncomingTelegramMessage
    ) -> Optional[str]:
        """
        Download file from Telegram and store in WellWon storage.

        Returns WellWon file URL.
        """
        if not message.file_id:
            return None

        try:
            from app.infra.telegram.adapter import get_telegram_adapter

            adapter = await get_telegram_adapter()

            # Get Telegram file URL
            telegram_url = await adapter.get_file_url(message.file_id)
            if not telegram_url:
                log.warning(f"Could not get URL for file {message.file_id}")
                return None

            # TODO: Download and store in WellWon storage (MinIO/S3)
            # For now, return the Telegram URL
            # In production, you'd want to:
            # 1. Download the file from Telegram
            # 2. Upload to your storage
            # 3. Return the permanent URL

            return telegram_url

        except Exception as e:
            log.error(f"Error downloading file: {e}")
            return None


    # =========================================================================
    # Read Status Handling (Telegram -> WellWon)
    # =========================================================================

    async def handle_read_event(self, read_event: 'ReadEventInfo') -> bool:
        """
        Handle incoming read event from Telegram MTProto.

        Two cases:
        1. is_outbox=True: Others read YOUR messages -> Set telegram_read_at (blue checkmarks)
        2. is_outbox=False: YOU read messages on Telegram -> Sync your read status to WellWon

        Args:
            read_event: Read event info from Telegram (chat_id, max_id, is_outbox)

        Returns:
            True if handled successfully
        """
        try:
            if read_event.is_outbox:
                # OUTBOX: Others read messages YOU sent -> Blue checkmarks!
                return await self._handle_outbox_read_event(read_event)
            else:
                # INBOX: YOU read messages on Telegram -> Sync to WellWon
                return await self._handle_inbox_read_event(read_event)
        except Exception as e:
            log.error(f"Error handling Telegram read event: {e}", exc_info=True)
            return False

    async def _handle_outbox_read_event(self, read_event: 'ReadEventInfo') -> bool:
        """
        Handle when others read YOUR messages on Telegram.
        This triggers blue checkmarks (telegram_read_at).

        Publishes MessagesReadOnTelegram event to the event bus, which:
        1. Gets picked up by WSE DomainPublisher
        2. Broadcasts to WebSocket clients
        3. Frontend updates message with telegram_read_at -> blue checkmarks
        """
        if not self._event_bus:
            log.warning("Event bus not available - cannot publish MessagesReadOnTelegram")
            return False

        log.info(
            f"Telegram read receipt: others read messages up to {read_event.max_id} "
            f"in chat {read_event.chat_id}"
        )

        try:
            # 1. Lookup WellWon chat by Telegram chat_id
            chat_id = await self._lookup_chat_by_telegram_id(read_event.chat_id)

            if not chat_id:
                log.debug(f"No WellWon chat found for Telegram chat {read_event.chat_id}")
                return False

            # 2. Find the WellWon message that corresponds to the Telegram max_id
            wellwon_message_id = await self._find_message_by_telegram_id(
                chat_id,
                read_event.chat_id,
                read_event.max_id
            )

            # If we can't find the specific message, still emit the event with chat_id only
            if not wellwon_message_id:
                log.debug(
                    f"No WellWon message found for Telegram message {read_event.max_id} "
                    f"in chat {read_event.chat_id} - emitting event anyway"
                )

            # 3. Publish MessagesReadOnTelegram event to trigger blue checkmarks
            telegram_read_at = datetime.now(timezone.utc)
            event_dict = {
                "event_id": str(uuid4()),
                "event_type": "MessagesReadOnTelegram",
                "aggregate_id": str(chat_id),
                "aggregate_type": "Chat",
                "chat_id": str(chat_id),
                "last_read_message_id": str(wellwon_message_id) if wellwon_message_id else None,
                "last_read_telegram_message_id": read_event.max_id,
                "telegram_read_at": telegram_read_at.isoformat(),
                "timestamp": telegram_read_at.isoformat(),
            }

            await self._event_bus.publish("transport.chat-events", event_dict)

            log.info(
                f"Blue checkmark event published: chat={chat_id}, "
                f"telegram_max_id={read_event.max_id}, wellwon_message_id={wellwon_message_id}"
            )

            return True

        except Exception as e:
            log.error(f"Error handling outbox read event: {e}", exc_info=True)
            return False

    async def _handle_inbox_read_event(self, read_event: 'ReadEventInfo') -> bool:
        """
        Handle when YOU read messages on Telegram.
        Syncs your read status to WellWon.
        """
        try:
            # 1. Lookup WellWon chat by Telegram chat_id
            chat_id = await self._lookup_chat_by_telegram_id(read_event.chat_id)

            if not chat_id:
                log.debug(f"No WellWon chat found for Telegram chat {read_event.chat_id}")
                return False

            # 2. Find the WellWon message that corresponds to the Telegram max_id
            wellwon_message_id = await self._find_message_by_telegram_id(
                chat_id,
                read_event.chat_id,
                read_event.max_id
            )

            if not wellwon_message_id:
                log.debug(
                    f"No WellWon message found for Telegram message {read_event.max_id} "
                    f"in chat {read_event.chat_id}"
                )
                return False

            # 3. Get the user who read (from the MTProto session - this is the logged-in user)
            user_id = await self._get_mtproto_user_id()
            if not user_id:
                log.warning("Could not determine MTProto user ID for read event")
                return False

            # 4. Dispatch MarkMessagesAsReadCommand with source='telegram'
            from app.chat.commands import MarkMessagesAsReadCommand

            command = MarkMessagesAsReadCommand(
                chat_id=chat_id,
                user_id=user_id,
                last_read_message_id=wellwon_message_id,
                source="telegram",  # Prevents sync loop back to Telegram
                telegram_message_id=read_event.max_id,  # Include for completeness
            )

            await self._command_bus.send(command)

            log.info(
                f"Synced read status from Telegram: chat={read_event.chat_id}, "
                f"max_id={read_event.max_id} -> WellWon chat={chat_id}"
            )

            return True

        except Exception as e:
            log.error(f"Error handling Telegram read event: {e}", exc_info=True)
            return False

    async def _lookup_chat_by_telegram_id(self, telegram_chat_id: int) -> Optional[UUID]:
        """Lookup WellWon chat by Telegram chat ID only (no topic)."""
        try:
            from app.chat.queries import GetChatByTelegramIdQuery

            result = await self._query_bus.query(
                GetChatByTelegramIdQuery(telegram_chat_id=telegram_chat_id)
            )
            return result.id if result else None  # ChatDetail has 'id' not 'chat_id'

        except Exception as e:
            log.debug(f"Chat lookup by telegram_id failed: {e}")
            # Fallback to external ID lookup
            return await self._lookup_chat(telegram_chat_id, None)

    async def _find_message_by_telegram_id(
        self,
        chat_id: UUID,
        telegram_chat_id: int,
        telegram_message_id: int
    ) -> Optional[int]:
        """Find WellWon message Snowflake ID by Telegram message ID."""
        try:
            from app.chat.queries import GetMessageByTelegramIdQuery

            result = await self._query_bus.query(
                GetMessageByTelegramIdQuery(
                    chat_id=chat_id,
                    telegram_chat_id=telegram_chat_id,
                    telegram_message_id=telegram_message_id
                )
            )
            # Return snowflake_id (int) for use with MarkMessagesAsReadCommand
            return result.snowflake_id if result else None

        except Exception as e:
            log.debug(f"Message lookup by telegram_id failed: {e}")
            return None

    async def _get_mtproto_user_id(self) -> Optional[UUID]:
        """
        Get the WellWon user ID for the logged-in MTProto session.

        The MTProto session is owned by a specific user - we need to map
        that Telegram user to a WellWon user.
        """
        try:
            from app.infra.telegram.adapter import get_telegram_adapter

            adapter = await get_telegram_adapter()
            if not adapter.mtproto_client:
                return None

            # Get the Telegram user ID of the MTProto session owner
            telegram_user_id = await adapter.mtproto_client.get_me_id()
            if not telegram_user_id:
                return None

            # Lookup WellWon user by Telegram ID
            from app.user_account.queries import GetUserByExternalIdQuery

            result = await self._query_bus.query(
                GetUserByExternalIdQuery(
                    provider="telegram",
                    external_id=str(telegram_user_id),
                )
            )

            return result.user_id if result else None

        except Exception as e:
            log.debug(f"MTProto user lookup failed: {e}")
            return None


# =============================================================================
# Factory
# =============================================================================

_incoming_handler: Optional[TelegramIncomingHandler] = None


async def get_incoming_handler(
    command_bus: 'CommandBus',
    query_bus: 'QueryBus',
    event_bus: Optional['RedpandaEventBus'] = None,
    redis_client: Optional[Any] = None,
) -> TelegramIncomingHandler:
    """Get or create incoming handler singleton."""
    global _incoming_handler
    if _incoming_handler is None:
        _incoming_handler = TelegramIncomingHandler(
            command_bus=command_bus,
            query_bus=query_bus,
            event_bus=event_bus,
            redis_client=redis_client,
        )
        await _incoming_handler.initialize()
    return _incoming_handler
