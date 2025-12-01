# =============================================================================
# File: app/infra/telegram/adapter.py
# Description: Unified Telegram Adapter (Hexagonal Architecture Port)
# =============================================================================

from __future__ import annotations

from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from app.config.logging_config import get_logger
from app.config.telegram_config import TelegramConfig, get_telegram_config
from app.infra.telegram.bot_client import TelegramBotClient, TelegramMessage, SendMessageResult
from app.infra.telegram.mtproto_client import TelegramMTProtoClient, GroupInfo, TopicInfo, MemberInfo, IncomingMessage

log = get_logger("wellwon.telegram.adapter")


@dataclass
class CompanyGroupResult:
    """Result of creating a company group"""
    success: bool
    group_id: Optional[int] = None
    group_title: Optional[str] = None
    invite_link: Optional[str] = None
    bots_results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


class TelegramAdapter:
    """
    Unified Telegram Adapter for Chat Domain (Hexagonal Architecture).

    This adapter provides a clean interface for the Chat Domain to interact
    with Telegram without knowing about the underlying implementation details.

    Architecture:
    - Bot API (aiogram): For sending/receiving messages, webhooks
    - MTProto (Telethon): For user-level operations (create groups, topics, etc.)

    Usage:
        adapter = TelegramAdapter()
        await adapter.initialize()

        # Send message (Bot API)
        await adapter.send_message(chat_id=-1001234567890, text="Hello!", topic_id=123)

        # Create group (MTProto)
        result = await adapter.create_company_group("Company Name")

        # Create topic (MTProto)
        topic = await adapter.create_chat_topic(group_id, "Topic Name", emoji="🎯")
    """

    def __init__(
        self,
        config: Optional[TelegramConfig] = None,
        redis_client: Optional[Any] = None,
    ):
        self.config = config or get_telegram_config()
        self._redis = redis_client
        self._bot_client: Optional[TelegramBotClient] = None
        self._mtproto_client: Optional[TelegramMTProtoClient] = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the adapter with all clients"""
        if self._initialized:
            return True

        success = True

        # Initialize Bot API client if available
        if self.config.bot_api_available:
            self._bot_client = TelegramBotClient(self.config, redis_client=self._redis)
            bot_ok = await self._bot_client.initialize()
            if not bot_ok:
                log.warning("Bot API client initialization failed")
                success = False
            else:
                log.info("Bot API client initialized")

        # Initialize MTProto client if available
        if self.config.mtproto_available and self.config.enable_mtproto:
            self._mtproto_client = TelegramMTProtoClient(self.config)
            mtproto_ok = await self._mtproto_client.connect()
            if not mtproto_ok:
                log.warning("MTProto client initialization failed")
                # MTProto failure is not critical
            else:
                log.info("MTProto client initialized")

        self._initialized = True
        return success

    async def close(self) -> None:
        """Close all clients"""
        if self._bot_client:
            await self._bot_client.close()
            self._bot_client = None

        if self._mtproto_client:
            await self._mtproto_client.disconnect()
            self._mtproto_client = None

        self._initialized = False
        log.info("Telegram adapter closed")

    @property
    def bot_client(self) -> Optional[TelegramBotClient]:
        """Get Bot API client"""
        return self._bot_client

    @property
    def mtproto_client(self) -> Optional[TelegramMTProtoClient]:
        """Get MTProto client"""
        return self._mtproto_client

    def set_incoming_message_handler(self, handler: callable) -> None:
        """
        Set handler for incoming messages from Telegram via MTProto.

        The handler will be called with IncomingMessage for each incoming message.
        """
        if self._mtproto_client:
            self._mtproto_client.set_message_callback(handler)
            log.info("Incoming message handler registered with MTProto client")
        else:
            log.warning("Cannot set message handler - MTProto client not available")

    # =========================================================================
    # MESSAGING (Bot API)
    # =========================================================================

    async def send_message(
        self,
        chat_id: int,
        text: str,
        topic_id: Optional[int] = None,
        reply_to: Optional[int] = None,
        parse_mode: str = "HTML"
    ) -> SendMessageResult:
        """
        Send a text message to a Telegram chat.

        Args:
            chat_id: Telegram chat ID (negative for groups)
            text: Message text
            topic_id: Forum topic ID (if in a forum group)
            reply_to: Message ID to reply to
            parse_mode: Parse mode (HTML, Markdown, etc.)

        Returns:
            SendMessageResult with success status and message_id
        """
        if not self._bot_client:
            return SendMessageResult(success=False, error="Bot client not available")

        return await self._bot_client.send_message(
            chat_id=chat_id,
            text=text,
            topic_id=topic_id,
            reply_to_message_id=reply_to,
            parse_mode=parse_mode
        )

    async def send_file(
        self,
        chat_id: int,
        file_url: str,
        file_name: Optional[str] = None,
        caption: Optional[str] = None,
        topic_id: Optional[int] = None
    ) -> SendMessageResult:
        """
        Send a file to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            file_url: URL of the file to send
            file_name: Optional file name
            caption: Optional caption
            topic_id: Forum topic ID

        Returns:
            SendMessageResult with success status and message_id
        """
        if not self._bot_client:
            return SendMessageResult(success=False, error="Bot client not available")

        return await self._bot_client.send_file(
            chat_id=chat_id,
            file_url=file_url,
            file_name=file_name,
            caption=caption,
            topic_id=topic_id
        )

    async def send_voice(
        self,
        chat_id: int,
        voice_url: str,
        duration: Optional[int] = None,
        caption: Optional[str] = None,
        topic_id: Optional[int] = None
    ) -> SendMessageResult:
        """Send a voice message"""
        if not self._bot_client:
            return SendMessageResult(success=False, error="Bot client not available")

        return await self._bot_client.send_voice(
            chat_id=chat_id,
            voice_url=voice_url,
            duration=duration,
            caption=caption,
            topic_id=topic_id
        )

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str
    ) -> SendMessageResult:
        """Edit an existing message"""
        if not self._bot_client:
            return SendMessageResult(success=False, error="Bot client not available")

        return await self._bot_client.edit_message(
            chat_id=chat_id,
            message_id=message_id,
            text=text
        )

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        """Delete a message"""
        if not self._bot_client:
            return False

        return await self._bot_client.delete_message(chat_id, message_id)

    async def get_file_url(self, file_id: str) -> Optional[str]:
        """Get download URL for a Telegram file"""
        if not self._bot_client:
            return None

        return await self._bot_client.get_file_url(file_id)

    # =========================================================================
    # WEBHOOK HANDLING (Bot API)
    # =========================================================================

    async def setup_webhook(self) -> bool:
        """Set up webhook for receiving updates"""
        if not self._bot_client:
            return False
        return await self._bot_client.setup_webhook()

    async def remove_webhook(self) -> bool:
        """Remove webhook"""
        if not self._bot_client:
            return False
        return await self._bot_client.remove_webhook()

    async def process_webhook_update(self, update_data: Dict[str, Any]) -> Optional[TelegramMessage]:
        """Process incoming webhook update"""
        if not self._bot_client:
            return None
        return await self._bot_client.process_update(update_data)

    # =========================================================================
    # GROUP MANAGEMENT (MTProto)
    # =========================================================================

    async def create_company_group(
        self,
        company_name: str,
        description: str = "",
        photo_url: Optional[str] = None,
        setup_bots: bool = True
    ) -> CompanyGroupResult:
        """
        Create a full company group with forum, bots, and permissions.

        Args:
            company_name: Name for the group
            description: Group description
            photo_url: Optional photo URL
            setup_bots: Whether to add configured bots as admins

        Returns:
            CompanyGroupResult with group details
        """
        if not self._mtproto_client:
            return CompanyGroupResult(success=False, error="MTProto client not available")

        try:
            # Create supergroup with forum
            group_info = await self._mtproto_client.create_supergroup(
                title=company_name,
                description=description,
                forum=True
            )

            if not group_info:
                return CompanyGroupResult(success=False, error="Failed to create group")

            # Set permissions
            await self._mtproto_client.set_group_permissions(group_info.group_id)

            # Rename and pin general topic
            await self._mtproto_client.update_forum_topic(
                group_id=group_info.group_id,
                topic_id=1,  # General topic is always ID 1
                new_title="General"
            )
            await self._mtproto_client.pin_forum_topic(group_info.group_id, topic_id=1)

            # Add bots
            bots_results = []
            if setup_bots:
                bots_results = await self._mtproto_client.setup_group_bots(group_info.group_id)

            # Set photo if provided
            if photo_url:
                await self._mtproto_client.set_group_photo(group_info.group_id, photo_url)

            # Get invite link
            invite_link = await self._mtproto_client.get_invite_link(group_info.group_id)

            return CompanyGroupResult(
                success=True,
                group_id=group_info.group_id,
                group_title=group_info.title,
                invite_link=invite_link,
                bots_results=bots_results
            )

        except Exception as e:
            log.error(f"Failed to create company group: {e}", exc_info=True)
            return CompanyGroupResult(success=False, error=str(e))

    async def create_chat_topic(
        self,
        group_id: int,
        topic_name: str,
        emoji: Optional[str] = None
    ) -> Optional[TopicInfo]:
        """
        Create a forum topic for a chat.

        Args:
            group_id: Telegram group ID
            topic_name: Topic name
            emoji: Optional emoji character

        Returns:
            TopicInfo if successful, None otherwise
        """
        if not self._mtproto_client:
            log.error("MTProto client not available")
            return None

        return await self._mtproto_client.create_forum_topic(
            group_id=group_id,
            title=topic_name,
            icon_emoji=emoji
        )

    async def update_chat_topic(
        self,
        group_id: int,
        topic_id: int,
        new_name: Optional[str] = None,
        new_emoji: Optional[str] = None
    ) -> bool:
        """Update a forum topic"""
        if not self._mtproto_client:
            return False

        return await self._mtproto_client.update_forum_topic(
            group_id=group_id,
            topic_id=topic_id,
            new_title=new_name,
            new_emoji=new_emoji
        )

    async def delete_chat_topic(self, group_id: int, topic_id: int) -> bool:
        """Delete a forum topic"""
        if not self._mtproto_client:
            return False

        return await self._mtproto_client.delete_forum_topic(group_id, topic_id)

    async def close_topic(self, group_id: int, topic_id: int, closed: bool = True) -> bool:
        """
        Close or reopen a forum topic.

        Closing a topic prevents new messages from being sent to it.
        The topic is hidden from the list but can still be found via search.
        All existing messages are preserved.

        Args:
            group_id: Telegram supergroup ID
            topic_id: Forum topic ID
            closed: True to close, False to reopen

        Returns:
            True if successful
        """
        if not self._mtproto_client:
            log.error("MTProto client not available for close_topic")
            return False

        return await self._mtproto_client.close_forum_topic(group_id, topic_id, closed)

    async def get_group_topics(self, group_id: int) -> List[TopicInfo]:
        """Get all topics in a group"""
        if not self._mtproto_client:
            return []

        return await self._mtproto_client.get_forum_topics(group_id)

    async def get_group_info(self, group_id: int) -> Optional[GroupInfo]:
        """Get group information"""
        if not self._mtproto_client:
            return None

        return await self._mtproto_client.get_group_info(group_id)

    async def update_group(
        self,
        group_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> bool:
        """Update group title and/or description"""
        if not self._mtproto_client:
            return False

        success = True
        if title:
            success = success and await self._mtproto_client.update_group_title(group_id, title)
        if description:
            success = success and await self._mtproto_client.update_group_description(group_id, description)
        return success

    # =========================================================================
    # USER MANAGEMENT (MTProto)
    # =========================================================================

    async def invite_user_to_group(self, group_id: int, username: str) -> bool:
        """Invite a user to a group"""
        if not self._mtproto_client:
            return False

        return await self._mtproto_client.invite_user(group_id, username)

    async def remove_user_from_group(self, group_id: int, username: str) -> bool:
        """Remove a user from a group"""
        if not self._mtproto_client:
            return False

        return await self._mtproto_client.remove_user(group_id, username)

    async def get_group_members(self, group_id: int) -> List[MemberInfo]:
        """Get all members of a group"""
        if not self._mtproto_client:
            return []

        return await self._mtproto_client.get_group_members(group_id)

    async def update_member_role(self, group_id: int, user_id: int, role: str) -> bool:
        """
        Update a member's role in a group.

        Args:
            group_id: Telegram group ID
            user_id: Telegram user ID
            role: New role (administrator, member, restricted)

        Returns:
            True if successful
        """
        if not self._mtproto_client:
            return False

        if role == "administrator":
            return await self._mtproto_client.promote_user(group_id, user_id, admin=True)
        elif role == "member":
            # First remove admin rights, then remove restrictions
            await self._mtproto_client.promote_user(group_id, user_id, admin=False)
            return await self._mtproto_client.restrict_user(group_id, user_id, restricted=False)
        elif role == "restricted":
            # Remove admin rights and add restrictions
            await self._mtproto_client.promote_user(group_id, user_id, admin=False)
            return await self._mtproto_client.restrict_user(group_id, user_id, restricted=True)
        else:
            log.warning(f"Unknown role: {role}")
            return False

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    @staticmethod
    def normalize_chat_id(telegram_id: int) -> str:
        """
        Normalize Telegram chat ID for storage.

        Telegram uses negative IDs for groups (e.g., -1001234567890).
        We store them as positive strings.
        """
        if telegram_id > 0:
            return str(telegram_id)
        # Remove -100 prefix for supergroups
        return str(abs(telegram_id) - 1000000000000)

    @staticmethod
    def denormalize_chat_id(normalized_id: str) -> int:
        """
        Convert normalized chat ID back to Telegram format.

        Returns negative ID for groups.
        """
        id_int = int(normalized_id)
        # Private chats have small positive IDs
        if id_int < 1000000000:
            return id_int
        # Supergroups need -100 prefix
        return -(id_int + 1000000000000)

    @staticmethod
    def get_available_emojis() -> Dict[str, int]:
        """Get all available topic emojis"""
        from app.infra.telegram.mtproto_client import EMOJI_MAP
        return EMOJI_MAP.copy()


# =========================================================================
# Singleton Instance
# =========================================================================

_adapter: Optional[TelegramAdapter] = None


async def get_telegram_adapter(redis_client: Optional[Any] = None) -> TelegramAdapter:
    """Get singleton Telegram adapter instance"""
    global _adapter
    if _adapter is None:
        _adapter = TelegramAdapter(redis_client=redis_client)
        await _adapter.initialize()
    return _adapter


async def close_telegram_adapter() -> None:
    """Close and reset singleton adapter"""
    global _adapter
    if _adapter:
        await _adapter.close()
        _adapter = None
