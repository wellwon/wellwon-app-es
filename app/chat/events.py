# =============================================================================
# File: app/chat/events.py
# Description: Chat domain events
# =============================================================================

from __future__ import annotations

from typing import Literal, Optional, Dict, Any, List
from pydantic import Field
import uuid
from datetime import datetime, timezone

from app.common.base.base_model import BaseEvent
from app.infra.event_bus.event_decorators import domain_event


# =============================================================================
# Chat Lifecycle Events
# =============================================================================

@domain_event(category="domain")
class ChatCreated(BaseEvent):
    """Event emitted when a new chat is created"""
    event_type: Literal["ChatCreated"] = "ChatCreated"
    chat_id: uuid.UUID
    name: Optional[str] = None
    chat_type: str  # direct, group, company
    created_by: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    telegram_chat_id: Optional[int] = None  # Legacy - for backward compat
    telegram_supergroup_id: Optional[int] = None  # Telegram supergroup ID
    telegram_topic_id: Optional[int] = None  # For Telegram forum topics


@domain_event(category="domain")
class ChatUpdated(BaseEvent):
    """Event emitted when chat details are updated"""
    event_type: Literal["ChatUpdated"] = "ChatUpdated"
    chat_id: uuid.UUID
    name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    updated_by: uuid.UUID


@domain_event(category="domain")
class ChatArchived(BaseEvent):
    """Event emitted when a chat is archived (soft delete)"""
    event_type: Literal["ChatArchived"] = "ChatArchived"
    chat_id: uuid.UUID
    archived_by: uuid.UUID
    telegram_supergroup_id: Optional[int] = None  # For syncing to Telegram
    telegram_topic_id: Optional[int] = None  # Topic to close/archive


@domain_event(category="domain")
class ChatRestored(BaseEvent):
    """Event emitted when an archived chat is restored"""
    event_type: Literal["ChatRestored"] = "ChatRestored"
    chat_id: uuid.UUID
    restored_by: uuid.UUID


@domain_event(category="domain")
class ChatHardDeleted(BaseEvent):
    """Event emitted when a chat is permanently deleted (hard delete)"""
    event_type: Literal["ChatHardDeleted"] = "ChatHardDeleted"
    chat_id: uuid.UUID
    deleted_by: uuid.UUID
    reason: Optional[str] = None
    telegram_supergroup_id: Optional[int] = None  # For syncing to Telegram
    telegram_topic_id: Optional[int] = None  # Topic to delete


# =============================================================================
# Company Linking Events
# =============================================================================

@domain_event(category="domain")
class ChatLinkedToCompany(BaseEvent):
    """Event emitted when a chat is linked to a company"""
    event_type: Literal["ChatLinkedToCompany"] = "ChatLinkedToCompany"
    chat_id: uuid.UUID
    company_id: uuid.UUID
    telegram_supergroup_id: Optional[int] = None
    linked_by: uuid.UUID


@domain_event(category="domain")
class ChatUnlinkedFromCompany(BaseEvent):
    """Event emitted when a chat is unlinked from a company"""
    event_type: Literal["ChatUnlinkedFromCompany"] = "ChatUnlinkedFromCompany"
    chat_id: uuid.UUID
    previous_company_id: uuid.UUID
    unlinked_by: uuid.UUID
    reason: Optional[str] = None


# =============================================================================
# Participant Events
# =============================================================================

@domain_event(category="domain")
class ParticipantAdded(BaseEvent):
    """Event emitted when a participant is added to chat"""
    event_type: Literal["ParticipantAdded"] = "ParticipantAdded"
    chat_id: uuid.UUID
    user_id: uuid.UUID
    role: str = "member"  # member, admin, observer
    added_by: Optional[uuid.UUID] = None
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="domain")
class ParticipantRemoved(BaseEvent):
    """Event emitted when a participant is removed from chat"""
    event_type: Literal["ParticipantRemoved"] = "ParticipantRemoved"
    chat_id: uuid.UUID
    user_id: uuid.UUID
    removed_by: Optional[uuid.UUID] = None
    reason: Optional[str] = None


@domain_event(category="domain")
class ParticipantRoleChanged(BaseEvent):
    """Event emitted when a participant's role is changed"""
    event_type: Literal["ParticipantRoleChanged"] = "ParticipantRoleChanged"
    chat_id: uuid.UUID
    user_id: uuid.UUID
    old_role: str
    new_role: str
    changed_by: uuid.UUID


@domain_event(category="domain")
class ParticipantLeft(BaseEvent):
    """Event emitted when a participant leaves the chat voluntarily"""
    event_type: Literal["ParticipantLeft"] = "ParticipantLeft"
    chat_id: uuid.UUID
    user_id: uuid.UUID


# =============================================================================
# Message Events
# =============================================================================

@domain_event(category="domain")
class MessageSent(BaseEvent):
    """
    Event emitted when a message is sent.

    ID Strategy (Discord/Slack pattern):
    - message_id: Server-generated Snowflake ID (int64) - permanent, time-ordered
    - client_temp_id: Optional client temp ID for optimistic UI reconciliation
    """
    event_type: Literal["MessageSent"] = "MessageSent"
    message_id: int  # Server-generated Snowflake ID (int64)
    chat_id: uuid.UUID
    sender_id: Optional[uuid.UUID] = None  # None for external Telegram users
    content: str
    message_type: str = "text"  # text, file, voice, image, system
    reply_to_id: Optional[int] = None  # Snowflake ID of replied message
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    voice_duration: Optional[int] = None  # seconds
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Source tracking
    source: str = "web"  # web, telegram, api
    # Participant IDs for real-time routing (avoids read model query race condition)
    participant_ids: Optional[List[uuid.UUID]] = None
    # Telegram integration
    telegram_message_id: Optional[int] = None
    telegram_chat_id: Optional[int] = None  # Telegram supergroup ID (for group_members tracking)
    telegram_user_id: Optional[int] = None  # Telegram user ID (for unmapped users)
    telegram_user_data: Optional[Dict[str, Any]] = None  # {first_name, last_name, username, is_bot}
    telegram_forward_data: Optional[Dict[str, Any]] = None  # Forward info if forwarded
    telegram_topic_id: Optional[int] = None  # Forum topic ID
    # Client temp ID for frontend reconciliation (NOT stored in DB)
    client_temp_id: Optional[str] = None


@domain_event(category="domain")
class MessageEdited(BaseEvent):
    """Event emitted when a message is edited"""
    event_type: Literal["MessageEdited"] = "MessageEdited"
    message_id: uuid.UUID
    chat_id: uuid.UUID
    edited_by: uuid.UUID
    old_content: str
    new_content: str
    edited_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="domain")
class MessageDeleted(BaseEvent):
    """Event emitted when a message is deleted (soft delete)"""
    event_type: Literal["MessageDeleted"] = "MessageDeleted"
    message_id: uuid.UUID
    chat_id: uuid.UUID
    deleted_by: uuid.UUID
    telegram_message_id: Optional[int] = None  # For syncing deletion to Telegram
    telegram_chat_id: Optional[int] = None  # Telegram chat/group ID


@domain_event(category="domain")
class MessageReadStatusUpdated(BaseEvent):
    """Event emitted when a message is marked as read"""
    event_type: Literal["MessageReadStatusUpdated"] = "MessageReadStatusUpdated"
    message_id: uuid.UUID
    chat_id: uuid.UUID
    user_id: uuid.UUID
    read_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="domain")
class MessagesMarkedAsRead(BaseEvent):
    """Event emitted when multiple messages are marked as read (batch).

    Bidirectional sync:
    - source='web': User read on WellWon -> Listener syncs to Telegram
    - source='telegram': User read on Telegram -> Already synced, no action needed
    """
    event_type: Literal["MessagesMarkedAsRead"] = "MessagesMarkedAsRead"
    chat_id: uuid.UUID
    user_id: uuid.UUID
    last_read_message_id: int  # Snowflake ID (bigint) - matches ScyllaDB message_id
    read_count: int
    read_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "web"  # 'web' or 'telegram' - prevents bidirectional sync loop
    # Telegram sync data (enriched by command, used by listener)
    telegram_message_id: Optional[int] = None  # Telegram message ID for sync
    telegram_chat_id: Optional[int] = None  # From aggregate state
    telegram_topic_id: Optional[int] = None  # From aggregate state


@domain_event(category="domain")
class MessageSyncedToTelegram(BaseEvent):
    """Event emitted when a WellWon message is successfully delivered to Telegram.

    This enables bidirectional delivery tracking:
    - Single checkmark: Message sent to WellWon server
    - Double checkmark: Message delivered to Telegram (this event)
    - Blue double checkmark: Message read on Telegram (MessagesReadOnTelegram)
    """
    event_type: Literal["MessageSyncedToTelegram"] = "MessageSyncedToTelegram"
    message_id: int  # Snowflake ID (int64)
    chat_id: uuid.UUID
    telegram_message_id: int  # Telegram's message ID
    telegram_chat_id: int  # Telegram chat/supergroup ID
    synced_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Participant IDs for real-time routing (avoids read model query in DomainPublisher)
    participant_ids: List[uuid.UUID] = Field(default_factory=list)


@domain_event(category="domain")
class MessagesReadOnTelegram(BaseEvent):
    """Event emitted when recipient reads messages on Telegram.

    This triggers blue double checkmarks for messages YOU sent.
    The Telegram MTProto client receives MessageRead events with is_outbox=True,
    which means "others read messages you sent".
    """
    event_type: Literal["MessagesReadOnTelegram"] = "MessagesReadOnTelegram"
    chat_id: uuid.UUID
    last_read_message_id: Optional[int] = None  # Snowflake ID (bigint), None if message not found
    last_read_telegram_message_id: int  # Telegram's max_id
    telegram_read_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Participant IDs for real-time routing (avoids read model query in DomainPublisher)
    participant_ids: List[uuid.UUID] = Field(default_factory=list)


@domain_event(category="domain")
class MessageFileUrlUpdated(BaseEvent):
    """Event emitted when a message's file URL is updated after async upload.

    Fire-and-forget pattern for fast incoming Telegram messages:
    1. Message stored immediately with temp Telegram CDN URL
    2. Background task downloads and uploads to MinIO
    3. This event updates the message with permanent MinIO URL
    4. Frontend receives via WSE and updates the UI seamlessly
    """
    event_type: Literal["MessageFileUrlUpdated"] = "MessageFileUrlUpdated"
    message_id: int  # Snowflake ID (bigint)
    chat_id: uuid.UUID
    new_file_url: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Typing Events (ephemeral, not stored in event store)
# =============================================================================

@domain_event(category="ephemeral")
class TypingStarted(BaseEvent):
    """Event emitted when user starts typing"""
    event_type: Literal["TypingStarted"] = "TypingStarted"
    chat_id: uuid.UUID
    user_id: uuid.UUID


@domain_event(category="ephemeral")
class TypingStopped(BaseEvent):
    """Event emitted when user stops typing"""
    event_type: Literal["TypingStopped"] = "TypingStopped"
    chat_id: uuid.UUID
    user_id: uuid.UUID


# =============================================================================
# Telegram Integration Events
# =============================================================================

@domain_event(category="domain")
class TelegramChatLinked(BaseEvent):
    """Event emitted when a Telegram chat is linked to WellWon chat"""
    event_type: Literal["TelegramChatLinked"] = "TelegramChatLinked"
    chat_id: uuid.UUID
    telegram_chat_id: int
    telegram_supergroup_id: Optional[int] = None  # Raw supergroup ID for frontend filtering
    telegram_topic_id: Optional[int] = None
    linked_by: uuid.UUID


@domain_event(category="domain")
class TelegramChatUnlinked(BaseEvent):
    """Event emitted when a Telegram chat is unlinked"""
    event_type: Literal["TelegramChatUnlinked"] = "TelegramChatUnlinked"
    chat_id: uuid.UUID
    telegram_chat_id: int
    unlinked_by: uuid.UUID


@domain_event(category="domain")
class TelegramMessageReceived(BaseEvent):
    """Event emitted when a message is received from Telegram"""
    event_type: Literal["TelegramMessageReceived"] = "TelegramMessageReceived"
    message_id: uuid.UUID
    chat_id: uuid.UUID
    telegram_message_id: int
    telegram_user_id: int
    sender_id: Optional[uuid.UUID] = None  # Mapped WellWon user if exists
    content: str
    message_type: str = "text"
    file_url: Optional[str] = None
    file_name: Optional[str] = None


# =============================================================================
# Client Invitation Events
# =============================================================================

@domain_event(category="domain")
class ClientInvited(BaseEvent):
    """
    Event emitted when a client is invited to Telegram group.

    Used for tracking invitations and populating telegram_group_members table.
    """
    event_type: Literal["ClientInvited"] = "ClientInvited"
    chat_id: uuid.UUID
    contact_type: str  # 'phone' or 'username'
    contact_value: str  # Phone number or @username
    telegram_user_id: int  # Resolved Telegram user ID
    client_name: str  # Client name for display
    invited_by: uuid.UUID
    status: str = "success"  # 'success', 'already_member'


@domain_event(category="domain")
class ClientInvitationFailed(BaseEvent):
    """
    Event emitted when client invitation fails.

    Reasons:
    - user_not_found: User not on Telegram or number not registered
    - privacy_restricted: User blocked invitations from unknown users
    - rate_limit: Telegram API rate limit hit
    - already_member: User is already in the group (not really a failure)
    """
    event_type: Literal["ClientInvitationFailed"] = "ClientInvitationFailed"
    chat_id: uuid.UUID
    contact_value: str  # Phone number or @username that failed
    reason: str  # 'user_not_found', 'privacy_restricted', 'rate_limit', etc.
    invited_by: uuid.UUID


# =============================================================================
# Event Type Registry (for deserialization)
# =============================================================================

CHAT_EVENT_TYPES = {
    "ChatCreated": ChatCreated,
    "ChatUpdated": ChatUpdated,
    "ChatArchived": ChatArchived,
    "ChatRestored": ChatRestored,
    "ChatHardDeleted": ChatHardDeleted,
    "ChatLinkedToCompany": ChatLinkedToCompany,
    "ChatUnlinkedFromCompany": ChatUnlinkedFromCompany,
    "ParticipantAdded": ParticipantAdded,
    "ParticipantRemoved": ParticipantRemoved,
    "ParticipantRoleChanged": ParticipantRoleChanged,
    "ParticipantLeft": ParticipantLeft,
    "MessageSent": MessageSent,
    "MessageEdited": MessageEdited,
    "MessageDeleted": MessageDeleted,
    "MessageReadStatusUpdated": MessageReadStatusUpdated,
    "MessagesMarkedAsRead": MessagesMarkedAsRead,
    "MessageSyncedToTelegram": MessageSyncedToTelegram,
    "MessagesReadOnTelegram": MessagesReadOnTelegram,
    "MessageFileUrlUpdated": MessageFileUrlUpdated,
    "TypingStarted": TypingStarted,
    "TypingStopped": TypingStopped,
    "TelegramChatLinked": TelegramChatLinked,
    "TelegramChatUnlinked": TelegramChatUnlinked,
    "TelegramMessageReceived": TelegramMessageReceived,
    "ClientInvited": ClientInvited,
    "ClientInvitationFailed": ClientInvitationFailed,
}
