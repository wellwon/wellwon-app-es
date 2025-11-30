# =============================================================================
# File: app/infra/telegram/bot_client.py
# Description: Telegram Bot API client using python-telegram-bot 22.x
# =============================================================================

from __future__ import annotations

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from app.config.logging_config import get_logger
from app.infra.telegram.config import TelegramConfig

log = get_logger("wellwon.telegram.bot_client")

# Lazy import python-telegram-bot to avoid import errors when not installed
try:
    from telegram import Bot, Update, InputFile
    from telegram.constants import ParseMode
    from telegram.error import TelegramError, RetryAfter
    PTB_AVAILABLE = True
except ImportError:
    PTB_AVAILABLE = False
    Bot = None
    Update = None
    log.warning("python-telegram-bot not installed. Telegram Bot API features will be disabled.")


@dataclass
class TelegramMessage:
    """Wrapper for Telegram message data"""
    message_id: int
    chat_id: int
    topic_id: Optional[int] = None
    from_user_id: Optional[int] = None
    from_username: Optional[str] = None
    from_first_name: Optional[str] = None
    from_last_name: Optional[str] = None
    from_is_bot: bool = False
    text: Optional[str] = None
    date: Optional[datetime] = None
    reply_to_message_id: Optional[int] = None
    # File info
    file_id: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None  # photo, document, audio, voice, video
    # Voice/audio specific
    voice_duration: Optional[int] = None


@dataclass
class SendMessageResult:
    """Result of sending a message"""
    success: bool
    message_id: Optional[int] = None
    error: Optional[str] = None


class TelegramBotClient:
    """
    Telegram Bot API client for message operations.

    Uses python-telegram-bot 22.x for modern async implementation.
    Handles:
    - Sending messages (text, files, voice)
    - Receiving webhook updates
    - Forwarding messages
    - Editing/deleting messages
    """

    def __init__(self, config: TelegramConfig):
        self.config = config
        self._bot: Optional['Bot'] = None
        self._initialized = False
        self._rate_limiter: Dict[int, List[datetime]] = {}  # chat_id -> timestamps

    async def initialize(self) -> bool:
        """Initialize the bot client"""
        if not PTB_AVAILABLE:
            log.error("python-telegram-bot not installed. Cannot initialize Telegram bot.")
            return False

        if self._initialized:
            return True

        try:
            self._bot = Bot(token=self.config.bot_token)

            # Verify bot token
            me = await self._bot.get_me()
            log.info(f"Telegram bot initialized: @{me.username} (ID: {me.id})")

            self._initialized = True
            return True

        except Exception as e:
            log.error(f"Failed to initialize Telegram bot: {e}", exc_info=True)
            return False

    async def close(self) -> None:
        """Close the bot client"""
        if self._bot:
            await self._bot.shutdown()
            self._bot = None
            self._initialized = False
            log.info("Telegram bot client closed")

    @property
    def bot(self) -> Optional['Bot']:
        """Get bot instance"""
        return self._bot

    @staticmethod
    def _normalize_chat_id(chat_id: int) -> int:
        """
        Normalize chat ID to Bot API format.

        Telegram Bot API uses:
        - Supergroups/Channels: -100{id} (e.g., -1002381938572)
        - Groups: negative numbers (e.g., -123456789)
        - Users: positive numbers (e.g., 123456789)

        MTProto/Telethon returns raw IDs without the -100 prefix.
        This method ensures IDs are in the correct Bot API format.
        """
        # If already negative, assume it's already in the correct format
        if chat_id < 0:
            return chat_id

        # Large positive IDs are supergroup IDs - add -100 prefix
        if chat_id > 1000000000:
            return -int(f"100{chat_id}")

        # For smaller positive IDs, return as-is (user IDs)
        return chat_id

    # =========================================================================
    # Webhook Management
    # =========================================================================

    async def setup_webhook(self) -> bool:
        """Set up webhook for receiving updates"""
        if not self._initialized:
            log.error("Bot not initialized")
            return False

        if not self.config.webhook_url:
            log.warning("Webhook URL not configured")
            return False

        try:
            webhook_info = await self._bot.get_webhook_info()

            if webhook_info.url == self.config.full_webhook_url:
                log.info(f"Webhook already set to {self.config.full_webhook_url}")
                return True

            await self._bot.set_webhook(
                url=self.config.full_webhook_url,
                secret_token=self.config.webhook_secret if self.config.webhook_secret else None,
                drop_pending_updates=True,  # Don't process old updates
            )

            log.info(f"Webhook set to {self.config.full_webhook_url}")
            return True

        except Exception as e:
            log.error(f"Failed to set webhook: {e}", exc_info=True)
            return False

    async def remove_webhook(self) -> bool:
        """Remove webhook"""
        if not self._initialized:
            return False

        try:
            await self._bot.delete_webhook(drop_pending_updates=True)
            log.info("Webhook removed")
            return True
        except Exception as e:
            log.error(f"Failed to remove webhook: {e}", exc_info=True)
            return False

    async def process_update(self, update_data: Dict[str, Any]) -> Optional[TelegramMessage]:
        """
        Process incoming webhook update.

        Returns TelegramMessage if it's a message update, None otherwise.
        Handles:
        - Regular messages (text, files, voice, etc.)
        - Edited messages
        - Channel posts
        - Forum topic created events (service messages)
        """
        if not PTB_AVAILABLE or not self._initialized:
            return None

        try:
            update = Update.de_json(update_data, self._bot)

            if update.message:
                # Check for forum_topic_created service message
                if update.message.forum_topic_created:
                    return self._parse_forum_topic_created(update.message)
                return self._parse_message(update.message)
            elif update.edited_message:
                return self._parse_message(update.edited_message)
            elif update.channel_post:
                return self._parse_message(update.channel_post)

            return None

        except Exception as e:
            log.error(f"Failed to process update: {e}", exc_info=True)
            return None

    def _parse_forum_topic_created(self, msg) -> TelegramMessage:
        """
        Parse forum_topic_created service message.

        When a new forum topic is created in Telegram, this creates a TelegramMessage
        with the topic name as text and a special marker for the router to handle.
        """
        topic_info = msg.forum_topic_created
        topic_name = topic_info.name if topic_info else "New Topic"
        topic_emoji = topic_info.icon_custom_emoji_id if topic_info else None

        log.info(f"Parsed forum_topic_created: name={topic_name}, topic_id={msg.message_thread_id}, chat_id={msg.chat.id}")

        return TelegramMessage(
            message_id=msg.message_id,
            chat_id=msg.chat.id,
            topic_id=msg.message_thread_id,
            from_user_id=msg.from_user.id if msg.from_user else None,
            from_username=msg.from_user.username if msg.from_user else None,
            from_first_name=msg.from_user.first_name if msg.from_user else None,
            from_last_name=msg.from_user.last_name if msg.from_user else None,
            from_is_bot=msg.from_user.is_bot if msg.from_user else False,
            # Use special format to indicate this is a topic creation event
            text=f"__TOPIC_CREATED__:{topic_name}",
            date=msg.date,
        )

    def _parse_message(self, msg) -> TelegramMessage:
        """Parse telegram Message to TelegramMessage"""
        result = TelegramMessage(
            message_id=msg.message_id,
            chat_id=msg.chat.id,
            topic_id=msg.message_thread_id,
            from_user_id=msg.from_user.id if msg.from_user else None,
            from_username=msg.from_user.username if msg.from_user else None,
            from_first_name=msg.from_user.first_name if msg.from_user else None,
            from_last_name=msg.from_user.last_name if msg.from_user else None,
            from_is_bot=msg.from_user.is_bot if msg.from_user else False,
            text=msg.text or msg.caption,
            date=msg.date,
            reply_to_message_id=msg.reply_to_message.message_id if msg.reply_to_message else None,
        )

        # Handle different file types
        if msg.photo:
            # Get largest photo
            photo = msg.photo[-1]
            result.file_id = photo.file_id
            result.file_size = photo.file_size
            result.file_type = "photo"

        elif msg.document:
            result.file_id = msg.document.file_id
            result.file_name = msg.document.file_name
            result.file_size = msg.document.file_size
            result.file_type = "document"

        elif msg.voice:
            result.file_id = msg.voice.file_id
            result.file_size = msg.voice.file_size
            result.file_type = "voice"
            result.voice_duration = msg.voice.duration

        elif msg.audio:
            result.file_id = msg.audio.file_id
            result.file_name = msg.audio.file_name
            result.file_size = msg.audio.file_size
            result.file_type = "audio"
            result.voice_duration = msg.audio.duration

        elif msg.video:
            result.file_id = msg.video.file_id
            result.file_name = msg.video.file_name
            result.file_size = msg.video.file_size
            result.file_type = "video"

        return result

    # =========================================================================
    # Message Sending
    # =========================================================================

    async def send_message(
        self,
        chat_id: int,
        text: str,
        topic_id: Optional[int] = None,
        reply_to_message_id: Optional[int] = None,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
    ) -> SendMessageResult:
        """
        Send a text message with automatic retry logic.

        Retries:
        - If topic not found → retry without topic (General)
        - If HTML parse error → retry without parse_mode
        """
        if not self._initialized:
            return SendMessageResult(success=False, error="Bot not initialized")

        # Normalize chat_id to Bot API format (MTProto returns positive IDs)
        normalized_chat_id = self._normalize_chat_id(chat_id)

        # Rate limiting check
        if not await self._check_rate_limit(normalized_chat_id):
            return SendMessageResult(success=False, error="Rate limit exceeded")

        try:
            msg = await self._bot.send_message(
                chat_id=normalized_chat_id,
                text=text,
                message_thread_id=topic_id,
                reply_to_message_id=reply_to_message_id,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
            )

            self._record_message(normalized_chat_id)
            return SendMessageResult(success=True, message_id=msg.message_id)

        except RetryAfter as e:
            log.warning(f"Rate limited by Telegram. Retry after {e.retry_after}s")
            return SendMessageResult(success=False, error=f"Rate limited. Retry after {e.retry_after}s")

        except TelegramError as e:
            error_str = str(e).lower()

            # Auto-retry: Topic not found → send to General
            if "thread not found" in error_str or "message thread not found" in error_str:
                log.warning(f"Topic {topic_id} not found, retrying without topic (General)")
                try:
                    msg = await self._bot.send_message(
                        chat_id=normalized_chat_id,
                        text=text,
                        message_thread_id=None,  # Send to General
                        reply_to_message_id=None,  # Remove reply when switching to General
                        parse_mode=parse_mode,
                        disable_notification=disable_notification,
                    )
                    self._record_message(normalized_chat_id)
                    return SendMessageResult(success=True, message_id=msg.message_id)
                except Exception as retry_e:
                    log.error(f"Retry to General also failed: {retry_e}")
                    return SendMessageResult(success=False, error=str(retry_e))

            # Auto-retry: HTML parse error → send without parse_mode
            if "parse" in error_str or "can't parse" in error_str:
                log.warning("HTML parse error, retrying without parse_mode")
                try:
                    msg = await self._bot.send_message(
                        chat_id=normalized_chat_id,
                        text=text,
                        message_thread_id=topic_id,
                        reply_to_message_id=reply_to_message_id,
                        parse_mode=None,  # No parse mode
                        disable_notification=disable_notification,
                    )
                    self._record_message(normalized_chat_id)
                    return SendMessageResult(success=True, message_id=msg.message_id)
                except Exception as retry_e:
                    log.error(f"Retry without parse_mode also failed: {retry_e}")
                    return SendMessageResult(success=False, error=str(retry_e))

            log.error(f"Telegram API error: {e}")
            return SendMessageResult(success=False, error=str(e))

        except Exception as e:
            log.error(f"Failed to send message: {e}", exc_info=True)
            return SendMessageResult(success=False, error=str(e))

    async def send_file(
        self,
        chat_id: int,
        file_url: str,
        file_name: Optional[str] = None,
        caption: Optional[str] = None,
        topic_id: Optional[int] = None,
    ) -> SendMessageResult:
        """Send a file (document, photo, etc.)"""
        if not self._initialized:
            return SendMessageResult(success=False, error="Bot not initialized")

        # Normalize chat_id to Bot API format (MTProto returns positive IDs)
        normalized_chat_id = self._normalize_chat_id(chat_id)

        if not await self._check_rate_limit(normalized_chat_id):
            return SendMessageResult(success=False, error="Rate limit exceeded")

        try:
            # Determine file type from extension
            file_ext = file_url.lower().split(".")[-1] if "." in file_url else ""

            if file_ext in ("jpg", "jpeg", "png", "gif", "webp"):
                msg = await self._bot.send_photo(
                    chat_id=normalized_chat_id,
                    photo=file_url,
                    caption=caption,
                    message_thread_id=topic_id,
                )
            else:
                msg = await self._bot.send_document(
                    chat_id=normalized_chat_id,
                    document=file_url,
                    caption=caption,
                    message_thread_id=topic_id,
                    filename=file_name,
                )

            self._record_message(normalized_chat_id)
            return SendMessageResult(success=True, message_id=msg.message_id)

        except Exception as e:
            log.error(f"Failed to send file: {e}", exc_info=True)
            return SendMessageResult(success=False, error=str(e))

    async def send_voice(
        self,
        chat_id: int,
        voice_url: str,
        duration: Optional[int] = None,
        caption: Optional[str] = None,
        topic_id: Optional[int] = None,
    ) -> SendMessageResult:
        """Send a voice message"""
        if not self._initialized:
            return SendMessageResult(success=False, error="Bot not initialized")

        # Normalize chat_id to Bot API format (MTProto returns positive IDs)
        normalized_chat_id = self._normalize_chat_id(chat_id)

        if not await self._check_rate_limit(normalized_chat_id):
            return SendMessageResult(success=False, error="Rate limit exceeded")

        try:
            msg = await self._bot.send_voice(
                chat_id=normalized_chat_id,
                voice=voice_url,
                duration=duration,
                caption=caption,
                message_thread_id=topic_id,
            )

            self._record_message(normalized_chat_id)
            return SendMessageResult(success=True, message_id=msg.message_id)

        except Exception as e:
            log.error(f"Failed to send voice: {e}", exc_info=True)
            return SendMessageResult(success=False, error=str(e))

    # =========================================================================
    # Message Management
    # =========================================================================

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: str = "HTML",
    ) -> SendMessageResult:
        """Edit an existing message"""
        if not self._initialized:
            return SendMessageResult(success=False, error="Bot not initialized")

        # Normalize chat_id to Bot API format
        normalized_chat_id = self._normalize_chat_id(chat_id)

        try:
            await self._bot.edit_message_text(
                chat_id=normalized_chat_id,
                message_id=message_id,
                text=text,
                parse_mode=parse_mode,
            )
            return SendMessageResult(success=True, message_id=message_id)

        except Exception as e:
            log.error(f"Failed to edit message: {e}", exc_info=True)
            return SendMessageResult(success=False, error=str(e))

    async def delete_message(
        self,
        chat_id: int,
        message_id: int,
    ) -> bool:
        """Delete a message"""
        if not self._initialized:
            return False

        # Normalize chat_id to Bot API format
        normalized_chat_id = self._normalize_chat_id(chat_id)

        try:
            await self._bot.delete_message(chat_id=normalized_chat_id, message_id=message_id)
            return True

        except Exception as e:
            log.error(f"Failed to delete message: {e}", exc_info=True)
            return False

    async def forward_message(
        self,
        chat_id: int,
        from_chat_id: int,
        message_id: int,
        topic_id: Optional[int] = None,
    ) -> SendMessageResult:
        """Forward a message"""
        if not self._initialized:
            return SendMessageResult(success=False, error="Bot not initialized")

        # Normalize chat IDs to Bot API format
        normalized_chat_id = self._normalize_chat_id(chat_id)
        normalized_from_chat_id = self._normalize_chat_id(from_chat_id)

        try:
            msg = await self._bot.forward_message(
                chat_id=normalized_chat_id,
                from_chat_id=normalized_from_chat_id,
                message_id=message_id,
                message_thread_id=topic_id,
            )
            return SendMessageResult(success=True, message_id=msg.message_id)

        except Exception as e:
            log.error(f"Failed to forward message: {e}", exc_info=True)
            return SendMessageResult(success=False, error=str(e))

    # =========================================================================
    # File Handling
    # =========================================================================

    async def get_file_url(self, file_id: str) -> Optional[str]:
        """
        Get full download URL for a file.

        Returns the complete URL that can be used to download the file.
        Format: https://api.telegram.org/file/bot<token>/<file_path>
        """
        if not self._initialized:
            return None

        try:
            file = await self._bot.get_file(file_id)
            if file.file_path:
                # Build full download URL
                return f"https://api.telegram.org/file/bot{self.config.bot_token}/{file.file_path}"
            return None

        except Exception as e:
            log.error(f"Failed to get file URL: {e}", exc_info=True)
            return None

    async def download_file(self, file_id: str) -> Optional[bytes]:
        """
        Download file content from Telegram.

        Args:
            file_id: Telegram file ID

        Returns:
            File content as bytes, or None on error
        """
        if not self._initialized:
            return None

        try:
            file = await self._bot.get_file(file_id)
            if file.file_path:
                # Use python-telegram-bot's download method
                file_bytes = await file.download_as_bytearray()
                return bytes(file_bytes)
            return None

        except Exception as e:
            log.error(f"Failed to download file: {e}", exc_info=True)
            return None

    # =========================================================================
    # Chat Info
    # =========================================================================

    async def get_chat_info(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Get chat information"""
        if not self._initialized:
            return None

        try:
            chat = await self._bot.get_chat(chat_id)
            return {
                "id": chat.id,
                "type": chat.type,
                "title": chat.title,
                "username": chat.username,
                "first_name": chat.first_name,
                "last_name": chat.last_name,
                "is_forum": chat.is_forum,
            }

        except Exception as e:
            log.error(f"Failed to get chat info: {e}", exc_info=True)
            return None

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    async def _check_rate_limit(self, chat_id: int) -> bool:
        """Check if we can send to this chat (rate limiting)"""
        now = datetime.utcnow()
        window_start = now.timestamp() - 60  # 1 minute window

        if chat_id not in self._rate_limiter:
            self._rate_limiter[chat_id] = []

        # Remove old timestamps
        self._rate_limiter[chat_id] = [
            ts for ts in self._rate_limiter[chat_id]
            if ts.timestamp() > window_start
        ]

        # Check limit
        if len(self._rate_limiter[chat_id]) >= self.config.messages_per_chat_per_minute:
            return False

        return True

    def _record_message(self, chat_id: int) -> None:
        """Record that a message was sent"""
        now = datetime.utcnow()
        if chat_id not in self._rate_limiter:
            self._rate_limiter[chat_id] = []
        self._rate_limiter[chat_id].append(now)
