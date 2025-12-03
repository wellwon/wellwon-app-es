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

        PERFORMANCE OPTIMIZATION (Fire-and-Forget Pattern):
        - Messages with files: Get temp Telegram CDN URL (~10ms), dispatch immediately
        - Background task downloads file and uploads to MinIO (700ms-10s)
        - UpdateMessageFileUrlCommand updates message with permanent URL
        - Frontend receives update via WSE and updates UI seamlessly

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

            # 3. Get temporary Telegram CDN URL (fast, ~10ms)
            # This URL expires in ~1 hour but allows instant message display
            temp_file_url = None
            if message.file_id:
                temp_file_url = await self._get_temp_file_url(message.file_id)

            # 4. Dispatch SendMessageCommand IMMEDIATELY with temp URL
            from app.chat.commands import SendMessageCommand

            # Convert Telegram message_type to domain message_type
            domain_message_type = self._convert_message_type(message.message_type)

            command = SendMessageCommand(
                chat_id=chat_id,
                sender_id=user_id,
                content=message.text or "",
                message_type=domain_message_type,
                file_url=temp_file_url,  # Temporary Telegram CDN URL
                file_name=message.file_name,
                file_size=message.file_size,
                file_type=message.mime_type,
                voice_duration=message.voice_duration,
                source="telegram",
                telegram_message_id=message.telegram_message_id,
            )

            result = await self._command_bus.send(command)

            log.info(
                f"Processed Telegram message {message.telegram_message_id} "
                f"-> WellWon message {result} (instant)"
            )

            # 5. Fire-and-forget: Download file and update URL in background
            if message.file_id:
                asyncio.create_task(
                    self._process_file_async(
                        message_id=result,  # Snowflake ID from command result
                        chat_id=chat_id,
                        message=message,
                    )
                )

            return result

        except Exception as e:
            log.error(f"Error processing Telegram message: {e}", exc_info=True)
            return None

    async def _get_temp_file_url(self, file_id: str) -> Optional[str]:
        """
        Get temporary Telegram CDN URL for a file (fast, ~10ms).

        This URL expires in ~1 hour but allows instant message display.
        """
        try:
            from app.infra.telegram.adapter import get_telegram_adapter

            adapter = await get_telegram_adapter()
            return await adapter.get_file_url(file_id)
        except Exception as e:
            log.warning(f"Could not get temp file URL for {file_id}: {e}")
            return None

    async def _process_file_async(
        self,
        message_id: int,
        chat_id: UUID,
        message: IncomingTelegramMessage,
    ) -> None:
        """
        Background task: Download file from Telegram, upload to MinIO, update message.

        This runs asynchronously after the message has already been delivered to the UI.
        When complete, it dispatches UpdateMessageFileUrlCommand which:
        1. Updates ScyllaDB with permanent MinIO URL
        2. Publishes MessageFileUrlUpdated event to WSE
        3. Frontend updates the message seamlessly
        """
        try:
            log.debug(
                f"Background file processing started for message {message_id}, "
                f"file_id={message.file_id}"
            )

            # Download and store the file
            permanent_url = await self._download_and_store_file(message)

            if permanent_url and not permanent_url.startswith("https://api.telegram.org"):
                # We got a MinIO URL (not a fallback Telegram URL)
                from app.chat.commands import UpdateMessageFileUrlCommand

                update_command = UpdateMessageFileUrlCommand(
                    message_id=message_id,
                    chat_id=chat_id,
                    new_file_url=permanent_url,
                    file_name=message.file_name,
                    file_size=message.file_size,
                    file_type=message.mime_type,
                )

                await self._command_bus.send(update_command)

                log.info(
                    f"Background file processing complete for message {message_id}: "
                    f"{permanent_url}"
                )
            else:
                log.warning(
                    f"Background file processing failed for message {message_id}, "
                    f"keeping temp URL"
                )

        except Exception as e:
            # Don't fail - the message was already delivered with temp URL
            log.error(
                f"Background file processing error for message {message_id}: {e}",
                exc_info=True
            )

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
        Download file from Telegram and store in MinIO/S3.

        Strategy:
        - Files ≤20MB: Use Bot API (faster, simpler)
        - Files >20MB: Use MTProto (supports up to 2GB)

        Returns MinIO public URL (permanent, unlike Telegram CDN URLs).
        """
        if not message.file_id:
            return None

        try:
            from app.infra.telegram.adapter import get_telegram_adapter
            from app.infra.storage.minio_provider import get_storage_provider

            adapter = await get_telegram_adapter()
            storage = get_storage_provider()

            # Determine download method based on file size
            file_size = message.file_size or 0
            BOT_API_LIMIT = 20 * 1024 * 1024  # 20MB

            file_bytes: Optional[bytes] = None

            if file_size <= BOT_API_LIMIT or file_size == 0:
                # Use Bot API for small files (or unknown size)
                file_bytes = await adapter.download_file(message.file_id)
                if not file_bytes and file_size == 0:
                    # Unknown size, Bot API might have failed - try MTProto
                    log.info(f"Bot API download failed, trying MTProto for {message.file_id}")
                    file_bytes = await adapter.download_file_mtproto(message.raw_data)
            else:
                # Use MTProto for large files (up to 2GB)
                log.info(f"Large file ({file_size} bytes), using MTProto for {message.file_id}")
                file_bytes = await adapter.download_file_mtproto(message.raw_data)

            if not file_bytes:
                log.warning(f"Could not download file {message.file_id}")
                # Fallback to Telegram CDN URL (expires after ~1h)
                return await adapter.get_file_url(message.file_id)

            # Determine content type
            content_type = message.mime_type or self._guess_content_type(message)

            # Upload to MinIO
            result = await storage.upload_file(
                bucket="chat-files",
                file_content=file_bytes,
                content_type=content_type,
                original_filename=message.file_name,
            )

            if result.success:
                log.info(
                    f"File stored in MinIO: {message.file_id} -> {result.public_url} "
                    f"({len(file_bytes)} bytes, {content_type})"
                )
                return result.public_url
            else:
                log.error(f"MinIO upload failed: {result.error}")
                # Fallback to Telegram CDN URL
                return await adapter.get_file_url(message.file_id)

        except Exception as e:
            log.error(f"Error downloading/storing file: {e}", exc_info=True)
            return None

    def _guess_content_type(self, message: IncomingTelegramMessage) -> str:
        """Guess content type from message type and filename."""
        # Try to guess from filename extension first
        if message.file_name:
            ext = message.file_name.lower().split(".")[-1] if "." in message.file_name else ""
            ext_map = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "gif": "image/gif",
                "webp": "image/webp",
                "pdf": "application/pdf",
                "doc": "application/msword",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "xls": "application/vnd.ms-excel",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "mp4": "video/mp4",
                "webm": "video/webm",
                "mp3": "audio/mpeg",
                "ogg": "audio/ogg",
                "wav": "audio/wav",
                "txt": "text/plain",
                "csv": "text/csv",
                "json": "application/json",
                "xml": "application/xml",
                "zip": "application/zip",
            }
            if ext in ext_map:
                return ext_map[ext]

        # Fall back to message type
        type_map = {
            "photo": "image/jpeg",
            "voice": "audio/ogg",
            "video": "video/mp4",
            "audio": "audio/mpeg",
            "sticker": "image/webp",
            "document": "application/octet-stream",
        }
        return type_map.get(message.message_type, "application/octet-stream")

    def _convert_message_type(self, telegram_type: str) -> str:
        """
        Convert Telegram message_type to domain message_type.

        Telegram types: text, photo, document, voice, video, sticker, audio
        Domain types: text, file, voice, image, system
        """
        conversion_map = {
            "text": "text",
            "photo": "image",      # Telegram photo -> domain image
            "document": "file",    # Telegram document -> domain file
            "voice": "voice",      # Same
            "video": "file",       # Telegram video -> domain file
            "audio": "file",       # Telegram audio -> domain file
            "sticker": "image",    # Telegram sticker -> domain image
        }
        return conversion_map.get(telegram_type, "text")


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
        log.info(
            f"[READ-DEBUG] handle_read_event called: chat_id={read_event.chat_id}, "
            f"max_id={read_event.max_id}, is_outbox={read_event.is_outbox}"
        )
        try:
            if read_event.is_outbox:
                # OUTBOX: Others read messages YOU sent -> Blue checkmarks!
                log.info("[READ-DEBUG] Processing OUTBOX read event (blue checkmarks)")
                return await self._handle_outbox_read_event(read_event)
            else:
                # INBOX: YOU read messages on Telegram -> Sync to WellWon
                log.info("[READ-DEBUG] Processing INBOX read event (sync to WellWon)")
                return await self._handle_inbox_read_event(read_event)
        except Exception as e:
            log.error(f"[READ-DEBUG] Error handling Telegram read event: {e}", exc_info=True)
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
            log.warning("[READ-DEBUG] Event bus not available - cannot publish MessagesReadOnTelegram")
            return False

        log.info(
            f"[READ-DEBUG] Telegram read receipt: others read messages up to {read_event.max_id} "
            f"in Telegram chat {read_event.chat_id}"
        )

        try:
            # 1. Lookup WellWon chat by Telegram chat_id
            chat_id = await self._lookup_chat_by_telegram_id(read_event.chat_id)

            if not chat_id:
                log.warning(f"[READ-DEBUG] No WellWon chat found for Telegram chat {read_event.chat_id}")
                return False

            log.info(f"[READ-DEBUG] Found WellWon chat: {chat_id}")

            # 2. Find the WellWon message that corresponds to the Telegram max_id
            wellwon_message_id = await self._find_message_by_telegram_id(
                chat_id,
                read_event.chat_id,
                read_event.max_id
            )

            # If we can't find the specific message, still emit the event with chat_id only
            if not wellwon_message_id:
                log.warning(
                    f"[READ-DEBUG] No WellWon message found for Telegram message {read_event.max_id} "
                    f"in chat {read_event.chat_id} - emitting event anyway"
                )
            else:
                log.info(f"[READ-DEBUG] Found WellWon message: {wellwon_message_id}")

            # 3. Get chat participants for WSE routing
            participant_ids = await self._get_chat_participant_ids(chat_id)
            log.info(f"[READ-DEBUG] Chat participants: {participant_ids}")

            # 4. Publish MessagesReadOnTelegram event to trigger blue checkmarks
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
                "participant_ids": participant_ids,  # For WSE routing to user topics
            }

            await self._event_bus.publish("transport.chat-events", event_dict)

            log.info(
                f"[READ-DEBUG] MessagesReadOnTelegram published to event bus: chat={chat_id}, "
                f"telegram_max_id={read_event.max_id}, wellwon_message_id={wellwon_message_id}, "
                f"participants={len(participant_ids)}"
            )

            return True

        except Exception as e:
            log.error(f"[READ-DEBUG] Error handling outbox read event: {e}", exc_info=True)
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

    async def _get_chat_participant_ids(self, chat_id: UUID) -> list:
        """
        Get participant IDs for a chat.

        Used to include participant_ids in events for WSE routing to user topics.

        Args:
            chat_id: WellWon chat UUID

        Returns:
            List of participant user IDs as strings
        """
        try:
            from app.chat.queries import GetChatParticipantsQuery

            participants = await self._query_bus.query(
                GetChatParticipantsQuery(chat_id=chat_id)
            )

            if participants:
                return [str(p.user_id) for p in participants]
            return []

        except Exception as e:
            log.warning(f"[READ-DEBUG] Could not get participants for chat {chat_id}: {e}")
            return []


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
