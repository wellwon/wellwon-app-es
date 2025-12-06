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
from app.infra.telegram.mtproto_client import TelegramMTProtoClient, GroupInfo, TopicInfo, MemberInfo, IncomingMessage, ReadEventInfo

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

    def set_read_status_handler(self, handler: callable) -> None:
        """
        Set handler for message read events from Telegram via MTProto.

        The handler will be called with ReadEventInfo for each read event.
        This is used to sync read status from Telegram to WellWon.
        """
        if self._mtproto_client:
            self._mtproto_client.set_read_callback(handler)
            log.info("Read status handler registered with MTProto client")
        else:
            log.warning("Cannot set read handler - MTProto client not available")

    def set_chat_filter(self, filter_callback: callable) -> None:
        """
        Set callback to filter messages/events by linked chats.

        This prevents logging and processing of messages from Telegram groups
        that are not linked to WellWon. Only messages from linked chats will
        be processed and logged.

        Args:
            filter_callback: Callable(chat_id, topic_id) -> bool
                Returns True if chat should be processed, False to skip silently.
        """
        if self._mtproto_client:
            self._mtproto_client.set_chat_filter(filter_callback)
            log.info("Chat filter registered with MTProto client")
        else:
            log.warning("Cannot set chat filter - MTProto client not available")

    def set_chat_filter_cache_update_callback(self, callback: callable) -> None:
        """
        Set callback to refresh chat filter cache.

        Called when a new chat is linked to Telegram so the filter cache
        is updated immediately without waiting for TTL expiry.

        Args:
            callback: Async callable that refreshes the linked chats cache.
        """
        self._chat_filter_cache_update_callback = callback
        log.info("Chat filter cache update callback registered")

    async def notify_chat_linked(self, chat_id: int, topic_id: Optional[int] = None) -> None:
        """
        Notify that a new chat has been linked to Telegram.

        Triggers cache refresh so new chats are immediately recognized
        by the filter.

        Args:
            chat_id: Telegram chat/supergroup ID
            topic_id: Optional Telegram topic ID for forum topics
        """
        if hasattr(self, '_chat_filter_cache_update_callback') and self._chat_filter_cache_update_callback:
            try:
                await self._chat_filter_cache_update_callback()
                log.info(f"Chat filter cache updated for new linked chat {chat_id}/{topic_id}")
            except Exception as e:
                log.warning(f"Failed to update chat filter cache: {e}")

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

    async def send_file_by_id(
        self,
        chat_id: int,
        file_id: str,
        file_type: str = "document",
        caption: Optional[str] = None,
        topic_id: Optional[int] = None
    ) -> SendMessageResult:
        """
        Send a file using cached Telegram file_id (faster, no re-upload).

        Args:
            chat_id: Telegram chat ID
            file_id: Cached Telegram file_id
            file_type: Type (photo, document, voice, video)
            caption: Optional caption
            topic_id: Forum topic ID

        Returns:
            SendMessageResult with success status
        """
        if not self._bot_client:
            return SendMessageResult(success=False, error="Bot client not available")

        return await self._bot_client.send_file_by_id(
            chat_id=chat_id,
            file_id=file_id,
            file_type=file_type,
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

    async def download_file(self, file_id: str) -> Optional[bytes]:
        """
        Download file content from Telegram via Bot API.

        Limit: 20MB maximum file size.

        Args:
            file_id: Telegram file ID

        Returns:
            File content as bytes, or None on error
        """
        if not self._bot_client:
            log.warning("Bot client not available for file download")
            return None

        return await self._bot_client.download_file(file_id)

    async def download_file_mtproto(self, raw_message: Optional[Dict[str, Any]]) -> Optional[bytes]:
        """
        Download file from Telegram via MTProto (up to 2GB).

        Uses Telethon's download_media with in-memory buffer.
        Best for large files that exceed Bot API's 20MB limit.

        Args:
            raw_message: Original Telegram message dict containing media

        Returns:
            File content as bytes, or None on error
        """
        if not self._mtproto_client:
            log.warning("MTProto client not available for large file download")
            return None

        if not raw_message:
            log.warning("No raw message data provided for MTProto download")
            return None

        try:
            import io

            # Download to memory buffer using Telethon
            buffer = io.BytesIO()

            # Telethon can download from message dict directly in some cases,
            # but for reliability we should reconstruct from chat_id + message_id
            chat_id = raw_message.get("chat", {}).get("id")
            message_id = raw_message.get("message_id")

            if not chat_id or not message_id:
                log.error("Missing chat_id or message_id for MTProto download")
                return None

            # Get the message from Telegram and download media
            client = self._mtproto_client._client
            if not client:
                log.error("MTProto client connection not available")
                return None

            # Get messages and download
            from telethon.tl.types import PeerChannel

            # Normalize chat_id for Telethon
            if chat_id < 0:
                # Remove -100 prefix if present
                if str(abs(chat_id)).startswith("100"):
                    peer_id = int(str(abs(chat_id))[3:])
                else:
                    peer_id = abs(chat_id)
            else:
                peer_id = chat_id

            messages = await client.get_messages(peer_id, ids=message_id)
            if not messages:
                log.error(f"Could not find message {message_id} in chat {peer_id}")
                return None

            message = messages if not isinstance(messages, list) else messages[0]

            if not message or not message.media:
                log.error(f"Message {message_id} has no media")
                return None

            # Download media to buffer
            await client.download_media(message, file=buffer)

            file_bytes = buffer.getvalue()
            log.info(f"MTProto downloaded {len(file_bytes)} bytes from message {message_id}")
            return file_bytes

        except Exception as e:
            log.error(f"MTProto download failed: {e}", exc_info=True)
            return None

    async def download_file_mtproto_by_message(self, chat_id: int, message_id: int) -> Optional[bytes]:
        """
        Download file from Telegram via MTProto using chat_id and message_id.

        This is a simpler interface for downloading when you have the message identifiers.

        Args:
            chat_id: Telegram chat ID (may include -100 prefix or not)
            message_id: Telegram message ID

        Returns:
            File content as bytes, or None on error
        """
        if not self._mtproto_client:
            log.warning("MTProto client not available for file download")
            return None

        try:
            import io

            client = self._mtproto_client._client
            if not client:
                log.error("MTProto client connection not available")
                return None

            # Normalize chat_id for Telethon (needs -100 prefix for supergroups)
            peer_id = self._mtproto_client._to_telegram_peer_id(chat_id)

            log.info(f"[FILE] MTProto download: chat={chat_id} -> peer={peer_id}, msg={message_id}")

            # Get the message
            messages = await client.get_messages(peer_id, ids=message_id)
            if not messages:
                log.error(f"Could not find message {message_id} in chat {peer_id}")
                return None

            message = messages if not isinstance(messages, list) else messages[0]

            if not message or not message.media:
                log.error(f"Message {message_id} has no media")
                return None

            # Download media to buffer
            buffer = io.BytesIO()
            await client.download_media(message, file=buffer)

            file_bytes = buffer.getvalue()
            log.info(f"[FILE] MTProto downloaded {len(file_bytes)} bytes from message {message_id}")
            return file_bytes

        except Exception as e:
            log.error(f"MTProto download by message failed: {e}", exc_info=True)
            return None

    # =========================================================================
    # READ STATUS (MTProto)
    # =========================================================================

    async def mark_messages_read(
        self,
        chat_id: int,
        max_id: int = 0,
    ) -> bool:
        """
        Mark messages as read in a Telegram chat.

        Args:
            chat_id: Telegram chat ID (as stored in DB, without -100 prefix)
            max_id: Mark all messages up to this ID as read (0 = all messages)

        Returns:
            True if successful, False otherwise
        """
        if not self._mtproto_client:
            log.warning("Cannot mark messages read - MTProto client not available")
            return False

        return await self._mtproto_client.mark_messages_read(chat_id, max_id)

    async def mark_topic_messages_read(
        self,
        group_id: int,
        topic_id: int,
        max_id: int = 0,
    ) -> bool:
        """
        Mark messages as read in a Telegram forum topic.

        Args:
            group_id: Telegram group ID (as stored in DB, without -100 prefix)
            topic_id: Forum topic ID
            max_id: Mark all messages up to this ID as read (0 = all messages)

        Returns:
            True if successful, False otherwise
        """
        if not self._mtproto_client:
            log.warning("Cannot mark topic messages read - MTProto client not available")
            return False

        return await self._mtproto_client.mark_topic_messages_read(group_id, topic_id, max_id)

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

    async def leave_group(self, group_id: int) -> bool:
        """
        Leave/delete a Telegram supergroup.

        Attempts to delete the group if we're the owner,
        otherwise just leaves the group.

        Args:
            group_id: Telegram group ID

        Returns:
            True if successful
        """
        if not self._mtproto_client:
            log.error("MTProto client not available for leave_group")
            return False

        return await self._mtproto_client.leave_group(group_id)

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

    async def resolve_and_invite_by_contact(
        self,
        group_id: int,
        contact: str,
        client_name: str
    ) -> tuple[bool, int | None, str]:
        """
        Resolve contact (phone or @username) to telegram_user_id and invite to group.

        Args:
            group_id: Telegram supergroup ID to invite user to
            contact: Phone (+79001234567) or username (@username or just username)
            client_name: Client's name for contact import

        Returns:
            Tuple of (success, telegram_user_id, status)
            Status: 'success', 'already_member', 'user_not_found',
                    'privacy_restricted', 'rate_limit', etc.
        """
        if not self._mtproto_client:
            return (False, None, "mtproto_not_available")

        return await self._mtproto_client.resolve_and_invite_by_contact(
            group_id=group_id,
            contact=contact,
            client_name=client_name
        )

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
