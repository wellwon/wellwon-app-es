# =============================================================================
# File: app/infra/telegram/bot_client.py
# Description: Telegram Bot API client using aiogram 3.x
# =============================================================================

from __future__ import annotations

import logging
import asyncio
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass
from datetime import datetime

from app.infra.telegram.config import TelegramConfig

log = logging.getLogger("wellwon.telegram.bot_client")

# Lazy import aiogram to avoid import errors when not installed
try:
    from aiogram import Bot, Dispatcher
    from aiogram.types import (
        Message,
        Update,
        InputFile,
        FSInputFile,
        URLInputFile,
        BufferedInputFile,
        InlineKeyboardMarkup,
        InlineKeyboardButton,
        ReplyKeyboardMarkup,
        KeyboardButton,
        ChatMemberUpdated,
    )
    from aiogram.enums import ParseMode, ChatType
    from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
    AIOGRAM_AVAILABLE = True
except ImportError:
    AIOGRAM_AVAILABLE = False
    Bot = None
    Dispatcher = None
    Message = None
    Update = None
    log.warning("aiogram not installed. Telegram Bot API features will be disabled.")


@dataclass
class TelegramMessage:
    """Wrapper for Telegram message data"""
    message_id: int
    chat_id: int
    topic_id: Optional[int] = None
    from_user_id: Optional[int] = None
    from_username: Optional[str] = None
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

    Uses aiogram 3.x for modern async implementation.
    Handles:
    - Sending messages (text, files, voice)
    - Receiving webhook updates
    - Forwarding messages
    - Editing/deleting messages
    """

    def __init__(self, config: TelegramConfig):
        self.config = config
        self._bot: Optional['Bot'] = None
        self._dispatcher: Optional['Dispatcher'] = None
        self._initialized = False
        self._rate_limiter: Dict[int, List[datetime]] = {}  # chat_id -> timestamps

    async def initialize(self) -> bool:
        """Initialize the bot client"""
        if not AIOGRAM_AVAILABLE:
            log.error("aiogram not installed. Cannot initialize Telegram bot.")
            return False

        if self._initialized:
            return True

        try:
            self._bot = Bot(token=self.config.bot_token)
            self._dispatcher = Dispatcher()

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
            await self._bot.session.close()
            self._bot = None
            self._dispatcher = None
            self._initialized = False
            log.info("Telegram bot client closed")

    @property
    def bot(self) -> Optional['Bot']:
        """Get bot instance"""
        return self._bot

    @property
    def dispatcher(self) -> Optional['Dispatcher']:
        """Get dispatcher instance"""
        return self._dispatcher

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
        """
        if not AIOGRAM_AVAILABLE or not self._initialized:
            return None

        try:
            update = Update.model_validate(update_data)

            if update.message:
                return self._parse_message(update.message)
            elif update.edited_message:
                return self._parse_message(update.edited_message)
            elif update.channel_post:
                return self._parse_message(update.channel_post)

            return None

        except Exception as e:
            log.error(f"Failed to process update: {e}", exc_info=True)
            return None

    def _parse_message(self, msg: 'Message') -> TelegramMessage:
        """Parse aiogram Message to TelegramMessage"""
        result = TelegramMessage(
            message_id=msg.message_id,
            chat_id=msg.chat.id,
            topic_id=msg.message_thread_id,
            from_user_id=msg.from_user.id if msg.from_user else None,
            from_username=msg.from_user.username if msg.from_user else None,
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
        """Send a text message"""
        if not self._initialized:
            return SendMessageResult(success=False, error="Bot not initialized")

        # Rate limiting check
        if not await self._check_rate_limit(chat_id):
            return SendMessageResult(success=False, error="Rate limit exceeded")

        try:
            msg = await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                message_thread_id=topic_id,
                reply_to_message_id=reply_to_message_id,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
            )

            self._record_message(chat_id)
            return SendMessageResult(success=True, message_id=msg.message_id)

        except TelegramRetryAfter as e:
            log.warning(f"Rate limited by Telegram. Retry after {e.retry_after}s")
            return SendMessageResult(success=False, error=f"Rate limited. Retry after {e.retry_after}s")

        except TelegramAPIError as e:
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

        if not await self._check_rate_limit(chat_id):
            return SendMessageResult(success=False, error="Rate limit exceeded")

        try:
            # Determine file type from extension
            file_ext = file_url.lower().split(".")[-1] if "." in file_url else ""
            input_file = URLInputFile(file_url, filename=file_name)

            if file_ext in ("jpg", "jpeg", "png", "gif", "webp"):
                msg = await self._bot.send_photo(
                    chat_id=chat_id,
                    photo=input_file,
                    caption=caption,
                    message_thread_id=topic_id,
                )
            else:
                msg = await self._bot.send_document(
                    chat_id=chat_id,
                    document=input_file,
                    caption=caption,
                    message_thread_id=topic_id,
                )

            self._record_message(chat_id)
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

        if not await self._check_rate_limit(chat_id):
            return SendMessageResult(success=False, error="Rate limit exceeded")

        try:
            input_file = URLInputFile(voice_url)
            msg = await self._bot.send_voice(
                chat_id=chat_id,
                voice=input_file,
                duration=duration,
                caption=caption,
                message_thread_id=topic_id,
            )

            self._record_message(chat_id)
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

        try:
            await self._bot.edit_message_text(
                chat_id=chat_id,
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

        try:
            await self._bot.delete_message(chat_id=chat_id, message_id=message_id)
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

        try:
            msg = await self._bot.forward_message(
                chat_id=chat_id,
                from_chat_id=from_chat_id,
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
        """Get download URL for a file"""
        if not self._initialized:
            return None

        try:
            file = await self._bot.get_file(file_id)
            return f"https://api.telegram.org/file/bot{self.config.bot_token}/{file.file_path}"

        except Exception as e:
            log.error(f"Failed to get file URL: {e}", exc_info=True)
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
