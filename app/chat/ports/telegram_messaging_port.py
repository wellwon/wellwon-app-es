# =============================================================================
# File: app/chat/ports/telegram_messaging_port.py
# Description: Port interface for Telegram messaging operations
# Pattern: Hexagonal Architecture / Ports & Adapters
# =============================================================================

from __future__ import annotations

from typing import Protocol, Optional, List, Dict, Any, Callable, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.infra.telegram.bot_client import SendMessageResult, TelegramMessage
    from app.infra.telegram.mtproto_client import TopicInfo


@runtime_checkable
class TelegramMessagingPort(Protocol):
    """
    Port: Telegram Messaging

    Defined by: Chat Domain
    Implemented by: TelegramAdapter (app/infra/telegram/adapter.py)

    This port defines the contract for messaging operations with Telegram.
    The Chat domain uses this interface without knowing about the underlying
    implementation (Bot API, MTProto, etc.).

    Categories:
    - Message sending (5 methods)
    - Message editing/deletion (2 methods)
    - Read status (2 methods)
    - File operations (2 methods)
    - Topic management (4 methods)
    - Callbacks (4 methods)

    Total: 19 methods
    """

    # =========================================================================
    # Message Sending (5 methods)
    # =========================================================================

    async def send_message(
        self,
        chat_id: int,
        text: str,
        topic_id: Optional[int] = None,
        reply_to: Optional[int] = None,
        parse_mode: str = "HTML"
    ) -> 'SendMessageResult':
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
        ...

    async def send_file(
        self,
        chat_id: int,
        file_url: str,
        file_name: Optional[str] = None,
        caption: Optional[str] = None,
        topic_id: Optional[int] = None
    ) -> 'SendMessageResult':
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
        ...

    async def send_voice(
        self,
        chat_id: int,
        voice_url: str,
        duration: Optional[int] = None,
        caption: Optional[str] = None,
        topic_id: Optional[int] = None
    ) -> 'SendMessageResult':
        """
        Send a voice message.

        Args:
            chat_id: Telegram chat ID
            voice_url: URL of voice recording
            duration: Voice duration in seconds
            caption: Optional caption
            topic_id: Forum topic ID

        Returns:
            SendMessageResult with success status
        """
        ...

    async def send_file_by_id(
        self,
        chat_id: int,
        file_id: str,
        file_type: str = "document",
        caption: Optional[str] = None,
        topic_id: Optional[int] = None
    ) -> 'SendMessageResult':
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
        ...

    # =========================================================================
    # Message Editing/Deletion (2 methods)
    # =========================================================================

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str
    ) -> 'SendMessageResult':
        """
        Edit an existing message.

        Args:
            chat_id: Telegram chat ID
            message_id: Message ID to edit
            text: New message text

        Returns:
            SendMessageResult with success status
        """
        ...

    async def delete_message(
        self,
        chat_id: int,
        message_id: int
    ) -> bool:
        """
        Delete a message.

        Args:
            chat_id: Telegram chat ID
            message_id: Message ID to delete

        Returns:
            True if successful
        """
        ...

    # =========================================================================
    # Read Status (2 methods)
    # =========================================================================

    async def mark_messages_read(
        self,
        chat_id: int,
        max_id: int = 0
    ) -> bool:
        """
        Mark messages as read in a Telegram chat.

        Args:
            chat_id: Telegram chat ID (as stored in DB, without -100 prefix)
            max_id: Mark all messages up to this ID as read (0 = all messages)

        Returns:
            True if successful
        """
        ...

    async def mark_topic_messages_read(
        self,
        group_id: int,
        topic_id: int,
        max_id: int = 0
    ) -> bool:
        """
        Mark messages as read in a Telegram forum topic.

        Args:
            group_id: Telegram group ID (as stored in DB, without -100 prefix)
            topic_id: Forum topic ID
            max_id: Mark all messages up to this ID as read (0 = all messages)

        Returns:
            True if successful
        """
        ...

    # =========================================================================
    # File Operations (2 methods)
    # =========================================================================

    async def get_file_url(
        self,
        file_id: str
    ) -> Optional[str]:
        """
        Get download URL for a Telegram file.

        Args:
            file_id: Telegram file ID

        Returns:
            Download URL, or None if not available
        """
        ...

    async def download_file(
        self,
        file_id: str
    ) -> Optional[bytes]:
        """
        Download file content from Telegram.

        Limit: 20MB maximum file size via Bot API.
        For larger files, use MTProto-based download.

        Args:
            file_id: Telegram file ID

        Returns:
            File content as bytes, or None on error
        """
        ...

    # =========================================================================
    # Topic Management (4 methods)
    # =========================================================================

    async def create_chat_topic(
        self,
        group_id: int,
        topic_name: str,
        emoji: Optional[str] = None
    ) -> Optional['TopicInfo']:
        """
        Create a forum topic for a chat.

        Args:
            group_id: Telegram group ID
            topic_name: Topic name
            emoji: Optional emoji character for topic icon

        Returns:
            TopicInfo if successful, None otherwise
        """
        ...

    async def update_chat_topic(
        self,
        group_id: int,
        topic_id: int,
        new_name: Optional[str] = None,
        new_emoji: Optional[str] = None
    ) -> bool:
        """
        Update a forum topic.

        Args:
            group_id: Telegram group ID
            topic_id: Topic ID
            new_name: New topic name
            new_emoji: New emoji icon

        Returns:
            True if successful
        """
        ...

    async def delete_chat_topic(
        self,
        group_id: int,
        topic_id: int
    ) -> bool:
        """
        Delete a forum topic.

        Args:
            group_id: Telegram group ID
            topic_id: Topic ID

        Returns:
            True if successful
        """
        ...

    async def close_topic(
        self,
        group_id: int,
        topic_id: int,
        closed: bool = True
    ) -> bool:
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
        ...

    # =========================================================================
    # Callbacks (4 methods)
    # =========================================================================

    def set_incoming_message_handler(
        self,
        handler: Callable
    ) -> None:
        """
        Set handler for incoming messages from Telegram.

        The handler will be called with IncomingMessage for each incoming message.

        Args:
            handler: Async callable to handle incoming messages
        """
        ...

    def set_read_status_handler(
        self,
        handler: Callable
    ) -> None:
        """
        Set handler for message read events from Telegram.

        The handler will be called with ReadEventInfo for each read event.
        Used to sync read status from Telegram to WellWon.

        Args:
            handler: Async callable to handle read events
        """
        ...

    def set_chat_filter(
        self,
        filter_callback: Callable
    ) -> None:
        """
        Set callback to filter messages/events by linked chats.

        Prevents logging and processing of messages from Telegram groups
        that are not linked to WellWon. Only messages from linked chats
        will be processed.

        Args:
            filter_callback: Callable(chat_id, topic_id) -> bool
                Returns True if chat should be processed, False to skip.
        """
        ...

    async def notify_chat_linked(
        self,
        chat_id: int,
        topic_id: Optional[int] = None
    ) -> None:
        """
        Notify that a new chat has been linked to Telegram.

        Triggers cache refresh so new chats are immediately recognized
        by the filter.

        Args:
            chat_id: Telegram chat/supergroup ID
            topic_id: Optional Telegram topic ID for forum topics
        """
        ...


# =============================================================================
# EOF
# =============================================================================
