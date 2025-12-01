# =============================================================================
# File: app/infra/read_repos/message_scylla_repo.py
# Description: ScyllaDB repository for high-volume message storage
# =============================================================================
"""
ScyllaDB Message Repository - Discord-Style High-Volume Message Storage

This module implements a production-ready repository for storing and retrieving
chat messages using ScyllaDB, following Discord's architecture for storing
trillions of messages.

Architecture Overview:
    - ScyllaDB: Message content, reactions, pinned messages, Telegram sync
    - PostgreSQL: Chat metadata, participants, unread tracking, templates
    - Redis: Typing indicators, presence (ephemeral data)

Key Design Decisions:
    1. Partition Key: (channel_id, bucket) - prevents unbounded partition growth
    2. Bucket: 10-day time window calculated from Snowflake ID timestamp
    3. Clustering Key: message_id DESC - Snowflake ID for time-ordered retrieval
    4. TWCS Compaction: 10-day windows aligned with bucket size
    5. telegram_message_mapping: O(1) Telegram dedup (no ALLOW FILTERING)

Usage Example:
    >>> from app.infra.read_repos.message_scylla_repo import (
    ...     MessageScyllaRepo, MessageData, MessageType, MessageSource
    ... )
    >>>
    >>> repo = MessageScyllaRepo()
    >>>
    >>> # Insert a message
    >>> message = MessageData(
    ...     channel_id=chat_uuid,
    ...     content="Hello, World!",
    ...     sender_id=user_uuid,
    ...     message_type=MessageType.TEXT,
    ...     source=MessageSource.WEB,
    ... )
    >>> snowflake_id = await repo.insert_message(message)
    >>>
    >>> # Fetch messages with pagination
    >>> messages = await repo.get_messages(
    ...     channel_id=chat_uuid,
    ...     limit=50,
    ...     before_id=last_message_id,
    ... )

Performance Characteristics:
    - Insert message: O(1) - single partition write
    - Get message by ID: O(1) - direct partition + clustering key lookup
    - Get messages (pagination): O(log n) - clustering key range scan
    - Get by Telegram ID: O(1) - via telegram_message_mapping table
    - Add/remove reaction: O(1) - partition write + counter update

References:
    - Discord Architecture: https://discord.com/blog/how-discord-stores-trillions-of-messages
    - ScyllaDB Best Practices: https://docs.scylladb.com/stable/get-started/data-modeling/best-practices.html
"""

from __future__ import annotations

import uuid
from typing import Optional, List, Dict, Any, Final
from datetime import datetime, timezone
from enum import Enum
import logging

from pydantic import BaseModel, Field, ConfigDict, model_validator

# =============================================================================
# Logging Configuration
# =============================================================================
try:
    from app.config.logging_config import get_logger
    log = get_logger("wellwon.read_repos.message_scylla")
except ImportError:
    log = logging.getLogger("wellwon.read_repos.message_scylla")

# =============================================================================
# ScyllaDB Client Import
# =============================================================================
try:
    from app.infra.persistence.scylladb import (
        ScyllaClient,
        get_scylla_client,
        generate_snowflake_id,
        calculate_message_bucket,
        get_bucket_range,
        SnowflakeIDParser,
    )
    SCYLLA_AVAILABLE: bool = True
except ImportError:
    SCYLLA_AVAILABLE = False
    log.warning("ScyllaDB client not available - install cassandra-driver")

# =============================================================================
# Constants
# =============================================================================
# Default pagination settings
DEFAULT_MESSAGE_LIMIT: Final[int] = 50
MAX_MESSAGE_LIMIT: Final[int] = 100
DEFAULT_EXPORT_LIMIT: Final[int] = 1000

# Bucket query depth (how many 10-day buckets to scan for pagination)
BUCKET_SCAN_DEPTH: Final[int] = 4

# Message content for deleted messages
DELETED_MESSAGE_PLACEHOLDER: Final[str] = "[deleted]"

# =============================================================================
# Type Aliases
# =============================================================================
ChannelID = uuid.UUID
UserID = uuid.UUID
MessageID = int  # Snowflake ID (64-bit)
TelegramID = int  # Telegram message/chat/user ID


# =============================================================================
# Enums
# =============================================================================
class MessageType(str, Enum):
    """
    Message content type enumeration.

    Attributes:
        TEXT: Plain text message
        FILE: File attachment (document, archive, etc.)
        VOICE: Voice message with duration
        IMAGE: Image attachment (photo, screenshot)
        SYSTEM: System-generated message (user joined, etc.)
    """
    TEXT = "text"
    FILE = "file"
    VOICE = "voice"
    IMAGE = "image"
    SYSTEM = "system"


class MessageSource(str, Enum):
    """
    Message origin source enumeration.

    Attributes:
        WEB: Message sent from web interface
        TELEGRAM: Message synced from Telegram
        API: Message sent via API (bots, integrations)
    """
    WEB = "web"
    TELEGRAM = "telegram"
    API = "api"


class SyncDirection(str, Enum):
    """
    Telegram synchronization direction enumeration.

    Attributes:
        TELEGRAM_TO_WEB: Message originated from Telegram, synced to WellWon
        WEB_TO_TELEGRAM: Message originated from WellWon, synced to Telegram
        BIDIRECTIONAL: Message synced in both directions
    """
    TELEGRAM_TO_WEB = "telegram_to_web"
    WEB_TO_TELEGRAM = "web_to_telegram"
    BIDIRECTIONAL = "bidirectional"


# =============================================================================
# Pydantic Models
# =============================================================================
class MessageData(BaseModel):
    """
    Message data model for ScyllaDB storage.

    This Pydantic v2 model handles message validation, Snowflake ID generation,
    and bucket calculation automatically via model validators.

    Attributes:
        channel_id: UUID of the chat/channel (maps to PostgreSQL chats.id)
        message_id: Snowflake ID (auto-generated if 0)
        sender_id: UUID of the sender (None for unmapped Telegram users)
        content: Message text content
        message_type: Type of message (text, file, voice, image, system)
        source: Origin of message (web, telegram, api)
        bucket: 10-day partition bucket (auto-calculated from message_id)

    Telegram Integration:
        telegram_message_id: Original Telegram message ID
        telegram_chat_id: Telegram chat ID (for mapping table deduplication)
        telegram_user_id: Telegram user ID who sent the message
        telegram_user_data: JSON string with Telegram user info
        telegram_forward_data: JSON string with forward metadata
        telegram_topic_id: Forum topic ID (bigint for large topic IDs)

    Example:
        >>> message = MessageData(
        ...     channel_id=uuid.uuid4(),
        ...     content="Hello!",
        ...     sender_id=uuid.uuid4(),
        ... )
        >>> print(message.message_id)  # Auto-generated Snowflake ID
        >>> print(message.bucket)       # Auto-calculated bucket
    """

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=False,  # MUST be False to avoid recursion in model_validator
        str_strip_whitespace=True,
    )

    # -------------------------------------------------------------------------
    # Required Fields
    # -------------------------------------------------------------------------
    channel_id: ChannelID = Field(
        description="UUID of the chat/channel (maps to PostgreSQL chats.id)"
    )
    message_id: MessageID = Field(
        default=0,
        description="Snowflake ID - auto-generated if not provided"
    )
    sender_id: Optional[UserID] = Field(
        default=None,
        description="Sender UUID (None for unmapped Telegram users)"
    )
    content: str = Field(
        description="Message text content"
    )

    # -------------------------------------------------------------------------
    # Message Type and Source
    # -------------------------------------------------------------------------
    message_type: MessageType = Field(
        default=MessageType.TEXT,
        description="Content type: text, file, voice, image, system"
    )
    source: MessageSource = Field(
        default=MessageSource.WEB,
        description="Origin: web, telegram, api"
    )

    # -------------------------------------------------------------------------
    # Reply Threading
    # -------------------------------------------------------------------------
    reply_to_id: Optional[MessageID] = Field(
        default=None,
        description="Snowflake ID of the message being replied to"
    )

    # -------------------------------------------------------------------------
    # File Attachments
    # -------------------------------------------------------------------------
    file_url: Optional[str] = Field(
        default=None,
        description="URL to the attached file"
    )
    file_name: Optional[str] = Field(
        default=None,
        description="Original filename"
    )
    file_size: Optional[int] = Field(
        default=None,
        ge=0,
        description="File size in bytes"
    )
    file_type: Optional[str] = Field(
        default=None,
        description="MIME type (e.g., 'image/png')"
    )
    voice_duration: Optional[int] = Field(
        default=None,
        ge=0,
        description="Voice message duration in seconds"
    )

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------
    created_at: Optional[datetime] = Field(
        default=None,
        description="Creation timestamp (derived from Snowflake if not set)"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last update timestamp"
    )

    # -------------------------------------------------------------------------
    # Status Flags
    # -------------------------------------------------------------------------
    is_edited: bool = Field(
        default=False,
        description="True if message content was edited"
    )
    is_deleted: bool = Field(
        default=False,
        description="True if message was soft-deleted"
    )

    # -------------------------------------------------------------------------
    # Telegram Integration
    # -------------------------------------------------------------------------
    telegram_message_id: Optional[TelegramID] = Field(
        default=None,
        description="Original Telegram message ID"
    )
    telegram_chat_id: Optional[TelegramID] = Field(
        default=None,
        description="Telegram chat ID for mapping table deduplication"
    )
    telegram_user_id: Optional[TelegramID] = Field(
        default=None,
        description="Telegram user ID who sent the message"
    )
    telegram_user_data: Optional[str] = Field(
        default=None,
        description="JSON: {first_name, last_name, username, is_bot}"
    )
    telegram_forward_data: Optional[str] = Field(
        default=None,
        description="JSON: forwarded message metadata"
    )
    telegram_topic_id: Optional[TelegramID] = Field(
        default=None,
        description="Forum topic ID (bigint for large topic IDs)"
    )
    sync_direction: Optional[SyncDirection] = Field(
        default=None,
        description="Telegram sync direction"
    )
    telegram_read_at: Optional[datetime] = Field(
        default=None,
        description="When message was read on Telegram"
    )

    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------
    metadata: Optional[str] = Field(
        default=None,
        description="JSON string for additional message metadata"
    )

    # -------------------------------------------------------------------------
    # Computed Field (Partition Bucket)
    # -------------------------------------------------------------------------
    bucket: int = Field(
        default=0,
        description="10-day bucket for ScyllaDB partitioning (auto-calculated)"
    )

    @model_validator(mode='after')
    def compute_bucket_and_defaults(self) -> 'MessageData':
        """
        Compute bucket from message_id and set timestamp defaults.

        This validator:
        1. Generates Snowflake ID if not provided (message_id == 0)
        2. Calculates 10-day bucket from Snowflake timestamp
        3. Derives created_at from Snowflake if not provided

        Returns:
            Self with computed fields populated
        """
        if SCYLLA_AVAILABLE:
            # Generate Snowflake ID if not provided
            if self.message_id == 0:
                self.message_id = generate_snowflake_id()

            # Calculate 10-day bucket from Snowflake timestamp
            self.bucket = calculate_message_bucket(self.message_id)

            # Derive created_at from Snowflake timestamp if not provided
            if self.created_at is None:
                self.created_at = SnowflakeIDParser().get_datetime(self.message_id)

        return self


# =============================================================================
# Repository Implementation
# =============================================================================
class MessageScyllaRepo:
    """
    ScyllaDB repository for high-volume message storage.

    This repository implements Discord-style message storage with:
    - Partition key: (channel_id, bucket) for bounded partition growth
    - Clustering key: message_id DESC for time-ordered retrieval
    - Snowflake IDs for globally unique, time-sortable identifiers
    - telegram_message_mapping for O(1) Telegram deduplication

    Thread Safety:
        This class is thread-safe. The underlying ScyllaClient handles
        connection pooling and prepared statement caching.

    Usage:
        >>> repo = MessageScyllaRepo()
        >>>
        >>> # Insert message
        >>> msg = MessageData(channel_id=chan_id, content="Hello", sender_id=user_id)
        >>> snowflake_id = await repo.insert_message(msg)
        >>>
        >>> # Fetch with pagination
        >>> messages = await repo.get_messages(channel_id=chan_id, limit=50)
        >>>
        >>> # Telegram deduplication lookup
        >>> existing = await repo.get_message_by_telegram_id(
        ...     channel_id=chan_id,
        ...     telegram_message_id=tg_msg_id,
        ...     telegram_chat_id=tg_chat_id,
        ... )

    Attributes:
        client: ScyllaClient instance (lazy-loaded if not provided)
    """

    def __init__(self, client: Optional[ScyllaClient] = None) -> None:
        """
        Initialize the message repository.

        Args:
            client: Optional ScyllaClient instance. If not provided,
                   the global client will be used (lazy-loaded on first access).
        """
        self._client = client

    @property
    def client(self) -> ScyllaClient:
        """
        Get the ScyllaDB client (lazy-loaded).

        Returns:
            ScyllaClient instance

        Raises:
            RuntimeError: If ScyllaDB client is not initialized
        """
        if self._client is None:
            self._client = get_scylla_client()
        return self._client

    # =========================================================================
    # Message Operations
    # =========================================================================

    async def insert_message(self, message: MessageData) -> MessageID:
        """
        Insert a message into ScyllaDB.

        This method:
        1. Inserts the message into the `messages` table
        2. If Telegram message, inserts into `telegram_message_mapping` for O(1) lookup

        The MessageData model automatically generates Snowflake ID and calculates
        bucket if not provided.

        Args:
            message: MessageData instance with message content and metadata

        Returns:
            Snowflake ID of the inserted message

        Raises:
            CircuitBreakerOpenError: If ScyllaDB circuit breaker is open

        Example:
            >>> msg = MessageData(
            ...     channel_id=channel_uuid,
            ...     content="Hello!",
            ...     sender_id=user_uuid,
            ...     telegram_message_id=12345,
            ...     telegram_chat_id=67890,
            ... )
            >>> snowflake_id = await repo.insert_message(msg)
        """
        # Insert into messages table
        await self.client.execute_prepared(
            """
            INSERT INTO messages (
                channel_id, bucket, message_id, sender_id, content, message_type,
                reply_to_id, file_url, file_name, file_size, file_type, voice_duration,
                created_at, updated_at, is_edited, is_deleted, source,
                telegram_message_id, telegram_user_id, telegram_user_data,
                telegram_forward_data, telegram_topic_id, sync_direction,
                telegram_read_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.channel_id,
                message.bucket,
                message.message_id,
                message.sender_id,
                message.content,
                message.message_type.value if message.message_type else "text",
                message.reply_to_id,
                message.file_url,
                message.file_name,
                message.file_size,
                message.file_type,
                message.voice_duration,
                message.created_at,
                message.updated_at,
                message.is_edited,
                message.is_deleted,
                message.source.value if message.source else "web",
                message.telegram_message_id,
                message.telegram_user_id,
                message.telegram_user_data,
                message.telegram_forward_data,
                message.telegram_topic_id,
                message.sync_direction.value if message.sync_direction else None,
                message.telegram_read_at,
                message.metadata,
            ),
            execution_profile='write',
        )

        # Insert into telegram_message_mapping for O(1) Telegram deduplication
        if message.telegram_message_id and message.telegram_chat_id:
            try:
                await self.client.execute_prepared(
                    """INSERT INTO telegram_message_mapping
                       (telegram_message_id, telegram_chat_id, channel_id, bucket, message_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        message.telegram_message_id,
                        message.telegram_chat_id,
                        message.channel_id,
                        message.bucket,
                        message.message_id,
                        message.created_at or datetime.now(timezone.utc),
                    ),
                    execution_profile='write',
                )
            except Exception as mapping_error:
                # Log but don't fail - message insert succeeded
                log.warning(f"Failed to insert telegram_message_mapping: {mapping_error}")

        return message.message_id

    async def get_message(
            self,
            channel_id: ChannelID,
            message_id: MessageID,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single message by ID.

        Complexity: O(1) - direct partition + clustering key lookup

        Args:
            channel_id: UUID of the channel
            message_id: Snowflake ID of the message

        Returns:
            Message dict if found, None otherwise

        Example:
            >>> msg = await repo.get_message(channel_id, snowflake_id)
            >>> if msg:
            ...     print(msg['content'])
        """
        bucket = calculate_message_bucket(message_id)
        result = await self.client.execute_prepared(
            "SELECT * FROM messages WHERE channel_id = ? AND bucket = ? AND message_id = ?",
            (channel_id, bucket, message_id),
        )
        return result[0] if result else None

    async def get_messages(
            self,
            channel_id: ChannelID,
            limit: int = DEFAULT_MESSAGE_LIMIT,
            before_id: Optional[MessageID] = None,
            after_id: Optional[MessageID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get messages with cursor-based pagination.

        This method efficiently queries across multiple 10-day buckets
        to fetch messages before or after a given cursor.

        Complexity: O(log n) per bucket - clustering key range scan

        Args:
            channel_id: UUID of the channel
            limit: Maximum number of messages to return (default 50, max 100)
            before_id: Fetch messages older than this Snowflake ID (exclusive)
            after_id: Fetch messages newer than this Snowflake ID (exclusive)

        Returns:
            List of message dicts ordered by message_id DESC

        Example:
            >>> # Get latest 50 messages
            >>> messages = await repo.get_messages(channel_id)
            >>>
            >>> # Get next page (older messages)
            >>> older = await repo.get_messages(
            ...     channel_id,
            ...     before_id=messages[-1]['message_id']
            ... )
        """
        # Clamp limit
        limit = min(limit, MAX_MESSAGE_LIMIT)
        messages: List[Dict[str, Any]] = []

        # Determine buckets to query based on cursor
        if before_id:
            end_bucket = calculate_message_bucket(before_id)
            buckets = list(range(end_bucket, max(0, end_bucket - BUCKET_SCAN_DEPTH) - 1, -1))
        elif after_id:
            start_bucket = calculate_message_bucket(after_id)
            buckets = list(range(start_bucket, start_bucket + BUCKET_SCAN_DEPTH))
        else:
            # No cursor - start from current time bucket
            now = datetime.now(timezone.utc)
            current_bucket = int(now.timestamp() * 1000) // (1000 * 60 * 60 * 24 * 10)
            buckets = list(range(current_bucket, max(0, current_bucket - BUCKET_SCAN_DEPTH + 1), -1))

        # Query each bucket until we have enough messages
        for bucket in buckets:
            if len(messages) >= limit:
                break

            remaining = limit - len(messages)

            if before_id:
                result = await self.client.execute_prepared(
                    """SELECT * FROM messages
                       WHERE channel_id = ? AND bucket = ? AND message_id < ?
                       ORDER BY message_id DESC LIMIT ?""",
                    (channel_id, bucket, before_id, remaining),
                )
            elif after_id:
                result = await self.client.execute_prepared(
                    """SELECT * FROM messages
                       WHERE channel_id = ? AND bucket = ? AND message_id > ?
                       ORDER BY message_id ASC LIMIT ?""",
                    (channel_id, bucket, after_id, remaining),
                )
            else:
                result = await self.client.execute_prepared(
                    """SELECT * FROM messages
                       WHERE channel_id = ? AND bucket = ?
                       ORDER BY message_id DESC LIMIT ?""",
                    (channel_id, bucket, remaining),
                )

            messages.extend(result)

        return messages[:limit]

    async def update_message_content(
            self,
            channel_id: ChannelID,
            message_id: MessageID,
            content: str,
    ) -> None:
        """
        Update message content (edit).

        Sets is_edited=True and updates the updated_at timestamp.

        Args:
            channel_id: UUID of the channel
            message_id: Snowflake ID of the message
            content: New message content
        """
        bucket = calculate_message_bucket(message_id)
        await self.client.execute_prepared(
            """UPDATE messages SET content = ?, is_edited = true, updated_at = ?
               WHERE channel_id = ? AND bucket = ? AND message_id = ?""",
            (content, datetime.now(timezone.utc), channel_id, bucket, message_id),
            execution_profile='write',
        )

    async def soft_delete_message(
            self,
            channel_id: ChannelID,
            message_id: MessageID,
    ) -> None:
        """
        Soft delete a message.

        Sets is_deleted=True and replaces content with placeholder.
        Original message metadata is preserved for audit purposes.

        Args:
            channel_id: UUID of the channel
            message_id: Snowflake ID of the message
        """
        bucket = calculate_message_bucket(message_id)
        await self.client.execute_prepared(
            """UPDATE messages SET is_deleted = true, content = ?, updated_at = ?
               WHERE channel_id = ? AND bucket = ? AND message_id = ?""",
            (DELETED_MESSAGE_PLACEHOLDER, datetime.now(timezone.utc), channel_id, bucket, message_id),
            execution_profile='write',
        )

    async def get_messages_by_author(
            self,
            channel_id: ChannelID,
            sender_id: UserID,
            limit: int = DEFAULT_MESSAGE_LIMIT,
    ) -> List[Dict[str, Any]]:
        """
        Get messages by author using application-level filtering.

        NOTE: ScyllaDB 5.x+ tablets are incompatible with Materialized Views.
        This method fetches recent messages and filters by sender_id in application.
        For high-volume channels, consider using PostgreSQL search instead.

        Args:
            channel_id: UUID of the channel
            sender_id: UUID of the message author
            limit: Maximum number of messages to return

        Returns:
            List of message dicts from the specified author
        """
        # Fetch more messages than needed to find enough from this author
        # This is less efficient than MV but works with tablets
        fetch_limit = min(limit * 10, MAX_MESSAGE_LIMIT)
        all_messages = await self.get_messages(channel_id, limit=fetch_limit)

        # Filter by sender_id in application
        author_messages = [
            msg for msg in all_messages
            if msg.get('sender_id') == sender_id
        ]

        return author_messages[:limit]

    async def get_message_by_telegram_id(
            self,
            channel_id: ChannelID,
            telegram_message_id: TelegramID,
            telegram_chat_id: Optional[TelegramID] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find message by Telegram ID for deduplication.

        Uses the `telegram_message_mapping` table for O(1) lookup instead
        of ALLOW FILTERING, following ScyllaDB best practices.

        Complexity: O(1) when telegram_chat_id is provided

        Args:
            channel_id: UUID of the WellWon channel
            telegram_message_id: Telegram message ID to look up
            telegram_chat_id: Telegram chat ID (strongly recommended for O(1) lookup)

        Returns:
            Message dict if found, None otherwise

        Example:
            >>> existing = await repo.get_message_by_telegram_id(
            ...     channel_id=channel_uuid,
            ...     telegram_message_id=12345,
            ...     telegram_chat_id=67890,
            ... )
            >>> if existing:
            ...     print("Message already synced, skipping")
        """
        # Primary path: O(1) lookup via mapping table with full partition key
        if telegram_chat_id:
            mapping_result = await self.client.execute_prepared(
                """SELECT channel_id, bucket, message_id
                   FROM telegram_message_mapping
                   WHERE telegram_message_id = ? AND telegram_chat_id = ?""",
                (telegram_message_id, telegram_chat_id),
            )
            if mapping_result:
                mapping = mapping_result[0]
                if mapping.get('channel_id') == channel_id:
                    return await self.get_message(channel_id, mapping['message_id'])

        # Fallback: Scan mapping table (still better than ALLOW FILTERING on messages)
        # This path is taken when telegram_chat_id is not available
        mapping_results = await self.client.execute(
            """SELECT channel_id, bucket, message_id
               FROM telegram_message_mapping
               WHERE telegram_message_id = ? ALLOW FILTERING""",
            (telegram_message_id,),
        )
        for mapping in mapping_results:
            if mapping.get('channel_id') == channel_id:
                return await self.get_message(channel_id, mapping['message_id'])

        return None

    # =========================================================================
    # Reaction Operations
    # =========================================================================

    async def add_reaction(
            self,
            channel_id: ChannelID,
            message_id: MessageID,
            emoji: str,
            user_id: UserID,
    ) -> None:
        """
        Add an emoji reaction to a message.

        This method:
        1. Inserts the individual reaction record
        2. Increments the counter in message_reaction_counts

        Args:
            channel_id: UUID of the channel
            message_id: Snowflake ID of the message
            emoji: Emoji string (e.g., "👍", "❤️")
            user_id: UUID of the user adding the reaction
        """
        # Insert individual reaction record
        await self.client.execute_prepared(
            """INSERT INTO message_reactions (channel_id, message_id, emoji, user_id, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (channel_id, message_id, emoji, user_id, datetime.now(timezone.utc)),
            execution_profile='write',
        )
        # Increment counter (ScyllaDB counter table)
        await self.client.execute(
            """UPDATE message_reaction_counts SET count = count + 1
               WHERE channel_id = ? AND message_id = ? AND emoji = ?""",
            (channel_id, message_id, emoji),
            execution_profile='write',
        )

    async def remove_reaction(
            self,
            channel_id: ChannelID,
            message_id: MessageID,
            emoji: str,
            user_id: UserID,
    ) -> None:
        """
        Remove an emoji reaction from a message.

        Args:
            channel_id: UUID of the channel
            message_id: Snowflake ID of the message
            emoji: Emoji string to remove
            user_id: UUID of the user removing the reaction
        """
        # Delete individual reaction record
        await self.client.execute_prepared(
            """DELETE FROM message_reactions
               WHERE channel_id = ? AND message_id = ? AND emoji = ? AND user_id = ?""",
            (channel_id, message_id, emoji, user_id),
            execution_profile='write',
        )
        # Decrement counter
        await self.client.execute(
            """UPDATE message_reaction_counts SET count = count - 1
               WHERE channel_id = ? AND message_id = ? AND emoji = ?""",
            (channel_id, message_id, emoji),
            execution_profile='write',
        )

    async def get_reactions(
            self,
            channel_id: ChannelID,
            message_id: MessageID,
    ) -> List[Dict[str, Any]]:
        """
        Get reaction counts for a message.

        Returns aggregated counts from the counter table for efficient
        retrieval without scanning individual reactions.

        Args:
            channel_id: UUID of the channel
            message_id: Snowflake ID of the message

        Returns:
            List of {emoji: str, count: int} dicts
        """
        return await self.client.execute_prepared(
            "SELECT emoji, count FROM message_reaction_counts WHERE channel_id = ? AND message_id = ?",
            (channel_id, message_id),
        )

    async def get_reaction_users(
            self,
            channel_id: ChannelID,
            message_id: MessageID,
            emoji: str,
    ) -> List[UserID]:
        """
        Get users who reacted with a specific emoji.

        Args:
            channel_id: UUID of the channel
            message_id: Snowflake ID of the message
            emoji: Emoji string to look up

        Returns:
            List of user UUIDs who reacted with the emoji
        """
        result = await self.client.execute_prepared(
            """SELECT user_id FROM message_reactions
               WHERE channel_id = ? AND message_id = ? AND emoji = ?""",
            (channel_id, message_id, emoji),
        )
        return [row['user_id'] for row in result]

    # =========================================================================
    # Pinned Messages
    # =========================================================================

    async def pin_message(
            self,
            channel_id: ChannelID,
            message_id: MessageID,
            pinned_by: UserID,
            content_preview: str,
            sender_id: UserID,
    ) -> None:
        """
        Pin a message to a channel.

        Args:
            channel_id: UUID of the channel
            message_id: Snowflake ID of the message to pin
            pinned_by: UUID of the user pinning the message
            content_preview: First ~200 chars of message for preview
            sender_id: UUID of the original message sender
        """
        await self.client.execute_prepared(
            """INSERT INTO pinned_messages
               (channel_id, message_id, pinned_by, pinned_at, content_preview, sender_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (channel_id, message_id, pinned_by, datetime.now(timezone.utc),
             content_preview[:200] if content_preview else "", sender_id),
            execution_profile='write',
        )

    async def unpin_message(
            self,
            channel_id: ChannelID,
            message_id: MessageID,
    ) -> None:
        """
        Unpin a message from a channel.

        Args:
            channel_id: UUID of the channel
            message_id: Snowflake ID of the message to unpin
        """
        await self.client.execute_prepared(
            "DELETE FROM pinned_messages WHERE channel_id = ? AND message_id = ?",
            (channel_id, message_id),
            execution_profile='write',
        )

    async def get_pinned_messages(
            self,
            channel_id: ChannelID,
            limit: int = DEFAULT_MESSAGE_LIMIT,
    ) -> List[Dict[str, Any]]:
        """
        Get pinned messages for a channel.

        Args:
            channel_id: UUID of the channel
            limit: Maximum number of pinned messages to return

        Returns:
            List of pinned message dicts ordered by message_id DESC
        """
        return await self.client.execute_prepared(
            "SELECT * FROM pinned_messages WHERE channel_id = ? LIMIT ?",
            (channel_id, min(limit, MAX_MESSAGE_LIMIT)),
        )

    # =========================================================================
    # Read Positions (Discord pattern - unread tracking)
    # =========================================================================

    async def get_unread_count(
            self,
            channel_id: ChannelID,
            user_id: UserID,
    ) -> int:
        """
        Get unread message count for a user in a channel.

        Uses the message_read_positions table which stores cached unread counts.
        The unread_count is approximate and updated asynchronously.

        Args:
            channel_id: UUID of the channel
            user_id: UUID of the user

        Returns:
            Unread message count (0 if no read position exists)

        Example:
            >>> count = await repo.get_unread_count(channel_id, user_id)
            >>> print(f"You have {count} unread messages")
        """
        result = await self.client.execute_prepared(
            "SELECT unread_count FROM message_read_positions WHERE channel_id = ? AND user_id = ?",
            (channel_id, user_id),
        )
        return result[0]['unread_count'] if result else 0

    async def update_read_position(
            self,
            channel_id: ChannelID,
            user_id: UserID,
            last_read_message_id: MessageID,
    ) -> None:
        """
        Update user's read position in a channel.

        Sets the last read message and resets unread count to 0.
        This is an upsert operation (INSERT with implicit update semantics).

        Args:
            channel_id: UUID of the channel
            user_id: UUID of the user
            last_read_message_id: Snowflake ID of the last read message

        Example:
            >>> await repo.update_read_position(
            ...     channel_id=channel_uuid,
            ...     user_id=user_uuid,
            ...     last_read_message_id=snowflake_id,
            ... )
        """
        await self.client.execute_prepared(
            """INSERT INTO message_read_positions
               (channel_id, user_id, last_read_message_id, last_read_at, unread_count)
               VALUES (?, ?, ?, ?, 0)""",
            (channel_id, user_id, last_read_message_id, datetime.now(timezone.utc)),
            execution_profile='write',
        )

    async def get_read_position(
            self,
            channel_id: ChannelID,
            user_id: UserID,
    ) -> Optional[Dict[str, Any]]:
        """
        Get user's read position in a channel.

        Args:
            channel_id: UUID of the channel
            user_id: UUID of the user

        Returns:
            Read position dict with last_read_message_id, last_read_at, unread_count
            None if no position exists
        """
        result = await self.client.execute_prepared(
            "SELECT * FROM message_read_positions WHERE channel_id = ? AND user_id = ?",
            (channel_id, user_id),
        )
        return result[0] if result else None

    async def increment_unread_count(
            self,
            channel_id: ChannelID,
            user_id: UserID,
    ) -> None:
        """
        Increment unread count for a user in a channel.

        Called when a new message is sent to update unread counts for other participants.
        Note: This requires the read position to already exist.

        Args:
            channel_id: UUID of the channel
            user_id: UUID of the user whose unread count should increment
        """
        # First check if position exists
        current = await self.get_read_position(channel_id, user_id)
        if current:
            new_count = (current.get('unread_count') or 0) + 1
            await self.client.execute_prepared(
                """INSERT INTO message_read_positions
                   (channel_id, user_id, last_read_message_id, last_read_at, unread_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (channel_id, user_id, current.get('last_read_message_id'),
                 current.get('last_read_at'), new_count),
                execution_profile='write',
            )

    # =========================================================================
    # Telegram Sync State
    # =========================================================================

    async def update_telegram_sync_state(
            self,
            channel_id: ChannelID,
            telegram_chat_id: TelegramID,
            telegram_topic_id: Optional[TelegramID] = None,
            last_synced_message_id: Optional[MessageID] = None,
    ) -> None:
        """
        Update Telegram synchronization state for a channel.

        Args:
            channel_id: UUID of the WellWon channel
            telegram_chat_id: Telegram chat ID being synced
            telegram_topic_id: Forum topic ID (for topic-based chats)
            last_synced_message_id: Snowflake ID of last synced message
        """
        await self.client.execute_prepared(
            """INSERT INTO telegram_sync_state
               (channel_id, telegram_chat_id, telegram_topic_id, last_synced_message_id,
                last_sync_at, sync_enabled)
               VALUES (?, ?, ?, ?, ?, true)""",
            (channel_id, telegram_chat_id, telegram_topic_id,
             last_synced_message_id, datetime.now(timezone.utc)),
            execution_profile='write',
        )

    async def get_telegram_sync_state(
            self,
            channel_id: ChannelID,
    ) -> Optional[Dict[str, Any]]:
        """
        Get Telegram sync state for a channel.

        Args:
            channel_id: UUID of the WellWon channel

        Returns:
            Sync state dict if configured, None otherwise
        """
        result = await self.client.execute_prepared(
            "SELECT * FROM telegram_sync_state WHERE channel_id = ?",
            (channel_id,),
        )
        return result[0] if result else None

    async def get_channel_by_telegram_chat(
            self,
            telegram_chat_id: TelegramID,
            telegram_topic_id: Optional[TelegramID] = None,
    ) -> Optional[ChannelID]:
        """
        Find WellWon channel by Telegram chat ID.

        Args:
            telegram_chat_id: Telegram chat ID to look up
            telegram_topic_id: Forum topic ID (for topic-specific lookup)

        Returns:
            Channel UUID if found, None otherwise
        """
        # Note: Uses ALLOW FILTERING on secondary index - acceptable for rare lookups
        result = await self.client.execute(
            "SELECT channel_id FROM telegram_sync_state WHERE telegram_chat_id = ? ALLOW FILTERING",
            (telegram_chat_id,),
        )
        for row in result:
            if telegram_topic_id is not None:
                state = await self.get_telegram_sync_state(row['channel_id'])
                if state and state.get('telegram_topic_id') == telegram_topic_id:
                    return row['channel_id']
            else:
                return row['channel_id']
        return None

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def get_messages_in_time_range(
            self,
            channel_id: ChannelID,
            start_time: datetime,
            end_time: datetime,
            limit: int = DEFAULT_EXPORT_LIMIT,
    ) -> List[Dict[str, Any]]:
        """
        Get messages within a time range (for exports/analytics).

        Efficiently queries across multiple buckets using Snowflake ID
        range derived from timestamps.

        Args:
            channel_id: UUID of the channel
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            limit: Maximum number of messages to return (default 1000)

        Returns:
            List of message dicts ordered by message_id ASC
        """
        buckets = get_bucket_range(start_time, end_time)
        start_id = SnowflakeIDParser.snowflake_from_datetime(start_time)
        end_id = SnowflakeIDParser.snowflake_from_datetime(end_time)

        messages: List[Dict[str, Any]] = []
        for bucket in buckets:
            if len(messages) >= limit:
                break
            remaining = limit - len(messages)
            result = await self.client.execute_prepared(
                """SELECT * FROM messages
                   WHERE channel_id = ? AND bucket = ?
                     AND message_id >= ? AND message_id <= ?
                   ORDER BY message_id ASC LIMIT ?""",
                (channel_id, bucket, start_id, end_id, remaining),
            )
            messages.extend(result)

        return messages[:limit]

    # =========================================================================
    # Channel Deletion (for saga cleanup)
    # =========================================================================

    async def delete_messages_for_channel(self, channel_id: ChannelID) -> int:
        """
        Delete ALL messages for a channel from ScyllaDB.

        ScyllaDB partition key is (channel_id, bucket), so we need to:
        1. Find all buckets that have messages for this channel
        2. Delete from each bucket

        This is called by GroupDeletionSaga when deleting a company/chat.

        Args:
            channel_id: UUID of the channel to delete messages from

        Returns:
            Number of buckets deleted from (approximate message count not available)
        """
        # Get distinct buckets for this channel by scanning recent buckets
        # Start from current bucket and go back BUCKET_SCAN_DEPTH * 10 (100 buckets = ~3 years)
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        current_bucket = int(now.timestamp() * 1000) // (1000 * 60 * 60 * 24 * 10)

        # Scan back 100 buckets (~3 years of data)
        buckets_deleted = 0
        for bucket in range(current_bucket, max(0, current_bucket - 100), -1):
            try:
                # Check if bucket has any messages
                result = await self.client.execute_prepared(
                    "SELECT message_id FROM messages WHERE channel_id = ? AND bucket = ? LIMIT 1",
                    (channel_id, bucket),
                )
                if result:
                    # Delete all messages in this bucket
                    await self.client.execute(
                        "DELETE FROM messages WHERE channel_id = %s AND bucket = %s",
                        (channel_id, bucket),
                        execution_profile='write',
                    )
                    buckets_deleted += 1
                    log.debug(f"Deleted messages from channel {channel_id} bucket {bucket}")
            except Exception as e:
                log.warning(f"Error deleting messages from bucket {bucket}: {e}")

        log.info(f"Deleted messages from {buckets_deleted} buckets for channel {channel_id}")
        return buckets_deleted

    async def delete_reactions_for_channel(self, channel_id: ChannelID) -> int:
        """
        Delete ALL reactions for a channel.

        Reactions are partitioned by (channel_id, message_id), so we need to
        find all message_ids first, then delete reactions for each.

        Args:
            channel_id: UUID of the channel

        Returns:
            Number of reaction records deleted (approximate)
        """
        deleted = 0
        try:
            # Get all reactions for this channel (scan is acceptable for deletion)
            reactions = await self.client.execute(
                "SELECT DISTINCT message_id FROM message_reactions WHERE channel_id = %s ALLOW FILTERING",
                (channel_id,),
            )
            for row in reactions:
                message_id = row['message_id']
                # Delete reactions
                await self.client.execute(
                    "DELETE FROM message_reactions WHERE channel_id = %s AND message_id = %s",
                    (channel_id, message_id),
                    execution_profile='write',
                )
                # Delete reaction counts
                await self.client.execute(
                    "DELETE FROM message_reaction_counts WHERE channel_id = %s AND message_id = %s",
                    (channel_id, message_id),
                    execution_profile='write',
                )
                deleted += 1
        except Exception as e:
            log.warning(f"Error deleting reactions for channel {channel_id}: {e}")

        log.info(f"Deleted reactions for {deleted} messages in channel {channel_id}")
        return deleted

    async def delete_pinned_for_channel(self, channel_id: ChannelID) -> int:
        """
        Delete ALL pinned messages for a channel.

        Args:
            channel_id: UUID of the channel

        Returns:
            Number of pinned messages deleted
        """
        try:
            # Count first
            pinned = await self.client.execute_prepared(
                "SELECT message_id FROM pinned_messages WHERE channel_id = ?",
                (channel_id,),
            )
            count = len(pinned)

            # Delete all pinned for this channel
            await self.client.execute(
                "DELETE FROM pinned_messages WHERE channel_id = %s",
                (channel_id,),
                execution_profile='write',
            )
            log.info(f"Deleted {count} pinned messages for channel {channel_id}")
            return count
        except Exception as e:
            log.warning(f"Error deleting pinned messages for channel {channel_id}: {e}")
            return 0

    async def delete_read_positions_for_channel(self, channel_id: ChannelID) -> int:
        """
        Delete ALL read positions for a channel.

        Args:
            channel_id: UUID of the channel

        Returns:
            Number of read positions deleted
        """
        try:
            # Get all user read positions for this channel
            positions = await self.client.execute(
                "SELECT user_id FROM message_read_positions WHERE channel_id = %s ALLOW FILTERING",
                (channel_id,),
            )
            count = 0
            for row in positions:
                await self.client.execute(
                    "DELETE FROM message_read_positions WHERE channel_id = %s AND user_id = %s",
                    (channel_id, row['user_id']),
                    execution_profile='write',
                )
                count += 1

            log.info(f"Deleted {count} read positions for channel {channel_id}")
            return count
        except Exception as e:
            log.warning(f"Error deleting read positions for channel {channel_id}: {e}")
            return 0

    async def delete_telegram_sync_state_for_channel(self, channel_id: ChannelID) -> bool:
        """
        Delete Telegram sync state for a channel.

        Args:
            channel_id: UUID of the channel

        Returns:
            True if deleted, False otherwise
        """
        try:
            await self.client.execute(
                "DELETE FROM telegram_sync_state WHERE channel_id = %s",
                (channel_id,),
                execution_profile='write',
            )
            log.info(f"Deleted telegram_sync_state for channel {channel_id}")
            return True
        except Exception as e:
            log.warning(f"Error deleting telegram_sync_state for channel {channel_id}: {e}")
            return False

    async def delete_telegram_mappings_for_channel(self, channel_id: ChannelID) -> int:
        """
        Delete ALL telegram_message_mapping entries for a channel.

        This requires scanning since the mapping table is partitioned by
        (telegram_message_id, telegram_chat_id), not by channel_id.

        Args:
            channel_id: UUID of the channel

        Returns:
            Number of mappings deleted
        """
        try:
            # Scan mappings for this channel (acceptable for deletion)
            mappings = await self.client.execute(
                "SELECT telegram_message_id, telegram_chat_id FROM telegram_message_mapping WHERE channel_id = %s ALLOW FILTERING",
                (channel_id,),
            )
            count = 0
            for row in mappings:
                await self.client.execute(
                    "DELETE FROM telegram_message_mapping WHERE telegram_message_id = %s AND telegram_chat_id = %s",
                    (row['telegram_message_id'], row['telegram_chat_id']),
                    execution_profile='write',
                )
                count += 1

            log.info(f"Deleted {count} telegram_message_mappings for channel {channel_id}")
            return count
        except Exception as e:
            log.warning(f"Error deleting telegram_message_mappings for channel {channel_id}: {e}")
            return 0

    async def delete_all_channel_data(self, channel_id: ChannelID) -> Dict[str, int]:
        """
        Delete ALL ScyllaDB data for a channel.

        This is the main method called by chat deletion to clean up all
        ScyllaDB data associated with a channel.

        Deletes from:
        - messages (all buckets)
        - message_reactions
        - message_reaction_counts
        - pinned_messages
        - message_read_positions
        - telegram_sync_state
        - telegram_message_mapping

        Args:
            channel_id: UUID of the channel to delete

        Returns:
            Dict with counts of deleted items per table
        """
        log.info(f"Deleting all ScyllaDB data for channel {channel_id}")

        results = {
            'messages_buckets': await self.delete_messages_for_channel(channel_id),
            'reactions': await self.delete_reactions_for_channel(channel_id),
            'pinned': await self.delete_pinned_for_channel(channel_id),
            'read_positions': await self.delete_read_positions_for_channel(channel_id),
            'telegram_sync': 1 if await self.delete_telegram_sync_state_for_channel(channel_id) else 0,
            'telegram_mappings': await self.delete_telegram_mappings_for_channel(channel_id),
        }

        log.info(f"ScyllaDB cleanup complete for channel {channel_id}: {results}")
        return results

    @staticmethod
    def create_dm_channel_id(user1_id: UserID, user2_id: UserID) -> ChannelID:
        """
        Create deterministic DM channel ID from two user IDs.

        Generates a consistent UUID for direct message channels between
        two users, regardless of which user initiates the conversation.

        Args:
            user1_id: First user's UUID
            user2_id: Second user's UUID

        Returns:
            Deterministic UUID for the DM channel

        Example:
            >>> dm_id = MessageScyllaRepo.create_dm_channel_id(user_a, user_b)
            >>> # Same result regardless of argument order
            >>> assert dm_id == MessageScyllaRepo.create_dm_channel_id(user_b, user_a)
        """
        # Sort IDs to ensure consistent result regardless of argument order
        ids = sorted([str(user1_id), str(user2_id)])
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"{ids[0]}:{ids[1]}")


# =============================================================================
# Global Instance Factory
# =============================================================================
_GLOBAL_REPO: Optional[MessageScyllaRepo] = None


def get_message_scylla_repo() -> MessageScyllaRepo:
    """
    Get or create the global message repository singleton.

    Returns:
        MessageScyllaRepo instance

    Example:
        >>> repo = get_message_scylla_repo()
        >>> messages = await repo.get_messages(channel_id)
    """
    global _GLOBAL_REPO
    if _GLOBAL_REPO is None:
        _GLOBAL_REPO = MessageScyllaRepo()
    return _GLOBAL_REPO


# =============================================================================
# Module Exports
# =============================================================================
__all__ = [
    # Enums
    "MessageType",
    "MessageSource",
    "SyncDirection",
    # Models
    "MessageData",
    # Repository
    "MessageScyllaRepo",
    "get_message_scylla_repo",
    # Constants
    "DEFAULT_MESSAGE_LIMIT",
    "MAX_MESSAGE_LIMIT",
    "DEFAULT_EXPORT_LIMIT",
    # Type Aliases
    "ChannelID",
    "UserID",
    "MessageID",
    "TelegramID",
]
