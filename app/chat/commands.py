# =============================================================================
# File: app/chat/commands.py
# Description: Chat domain commands
# =============================================================================

from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import Field, field_validator
from uuid import UUID
from datetime import datetime

from app.infra.cqrs.command_bus import Command
from app.chat.enums import ChatType, ParticipantRole, MessageType
from app.utils.uuid_utils import generate_uuid


# =============================================================================
# Chat Lifecycle Commands
# =============================================================================

class CreateChatCommand(Command):
    """Create a new chat"""
    chat_id: UUID = Field(default_factory=generate_uuid)
    name: Optional[str] = Field(None, max_length=255)
    chat_type: str = Field(default="direct", description="direct, group, or company")
    created_by: UUID
    company_id: Optional[UUID] = None
    participant_ids: List[UUID] = Field(default_factory=list)
    # Telegram integration
    telegram_supergroup_id: Optional[int] = None  # Telegram supergroup ID
    telegram_topic_id: Optional[int] = None

    @field_validator('chat_type')
    @classmethod
    def validate_chat_type(cls, v: str) -> str:
        valid_types = [t.value for t in ChatType]
        if v not in valid_types:
            raise ValueError(f"chat_type must be one of {valid_types}")
        return v


class UpdateChatCommand(Command):
    """Update chat details"""
    chat_id: UUID
    name: Optional[str] = Field(None, max_length=255)
    updated_by: UUID


class ArchiveChatCommand(Command):
    """Archive (soft delete) a chat"""
    chat_id: UUID
    archived_by: UUID
    reason: Optional[str] = Field(None, max_length=500)


class RestoreChatCommand(Command):
    """Restore an archived chat"""
    chat_id: UUID
    restored_by: UUID


class DeleteChatCommand(Command):
    """Hard delete a chat (permanent, removes from database)"""
    chat_id: UUID
    deleted_by: UUID
    reason: Optional[str] = Field(None, max_length=500)


# =============================================================================
# Company Linking Commands
# =============================================================================

class LinkChatToCompanyCommand(Command):
    """Link an existing chat to a company (used by saga)"""
    chat_id: UUID
    company_id: UUID
    telegram_supergroup_id: Optional[int] = None
    linked_by: UUID


class UnlinkChatFromCompanyCommand(Command):
    """Unlink a chat from its company (used by saga compensation)"""
    chat_id: UUID
    unlinked_by: UUID
    reason: Optional[str] = Field(None, max_length=500)


# =============================================================================
# Participant Commands
# =============================================================================

class AddParticipantCommand(Command):
    """Add participant to chat"""
    chat_id: UUID
    user_id: UUID
    role: str = Field(default="member", description="member, admin, or observer")
    added_by: Optional[UUID] = None

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = [r.value for r in ParticipantRole]
        if v not in valid_roles:
            raise ValueError(f"role must be one of {valid_roles}")
        return v


class RemoveParticipantCommand(Command):
    """Remove participant from chat"""
    chat_id: UUID
    user_id: UUID
    removed_by: UUID
    reason: Optional[str] = None


class ChangeParticipantRoleCommand(Command):
    """Change participant's role in chat"""
    chat_id: UUID
    user_id: UUID
    new_role: str
    changed_by: UUID

    @field_validator('new_role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = [r.value for r in ParticipantRole]
        if v not in valid_roles:
            raise ValueError(f"new_role must be one of {valid_roles}")
        return v


class LeaveChatCommand(Command):
    """Leave chat voluntarily"""
    chat_id: UUID
    user_id: UUID


# =============================================================================
# Message Commands
# =============================================================================

class SendMessageCommand(Command):
    """
    Send message to chat.

    ID Strategy (Industry Standard - Discord/Slack pattern):
    - client_temp_id: Optional client-generated UUID for optimistic UI reconciliation
    - snowflake_id: Server-generated Snowflake ID (set by handler, not client)
    - idempotency_key: Optional UUID for exactly-once delivery (prevents duplicates on retry)

    The server generates the permanent snowflake_id, client_temp_id is only
    used to reconcile optimistic UI updates with server response.
    """
    chat_id: UUID
    sender_id: UUID
    content: str = Field(..., max_length=10000)
    message_type: str = Field(default="text", description="text, file, voice, image, system")
    reply_to_id: Optional[int] = None  # Snowflake ID of replied message
    # Client temp ID for optimistic UI reconciliation (NOT stored permanently)
    client_temp_id: Optional[str] = Field(
        default=None,
        description="Client-generated temp ID for optimistic UI reconciliation"
    )
    # Idempotency key for exactly-once delivery (prevents duplicate messages on retry)
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Client-generated UUID for deduplication - if same key sent twice, return existing message"
    )
    # File attachments
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    voice_duration: Optional[int] = None  # seconds
    # Source tracking
    source: str = Field(default="web", description="web, telegram, api")
    telegram_message_id: Optional[int] = None

    @field_validator('message_type')
    @classmethod
    def validate_message_type(cls, v: str) -> str:
        valid_types = [t.value for t in MessageType]
        if v not in valid_types:
            raise ValueError(f"message_type must be one of {valid_types}")
        return v


class EditMessageCommand(Command):
    """Edit an existing message.

    telegram_message_id should be enriched by the caller (router) before sending.
    """
    message_id: UUID
    chat_id: UUID
    edited_by: UUID
    new_content: str = Field(..., max_length=10000)
    telegram_message_id: Optional[int] = None  # Enriched by router for Telegram sync


class DeleteMessageCommand(Command):
    """Soft-delete a message.

    telegram_message_id should be enriched by the caller (router) before sending.
    """
    message_id: UUID
    chat_id: UUID
    deleted_by: UUID
    telegram_message_id: Optional[int] = None  # Enriched by router for Telegram sync


class MarkMessageAsReadCommand(Command):
    """Mark a single message as read"""
    message_id: UUID
    chat_id: UUID
    user_id: UUID


class MarkMessagesAsReadCommand(Command):
    """
    Mark all messages up to a point as read.

    Attributes:
        chat_id: Chat to mark as read
        user_id: User who is reading
        last_read_message_id: Snowflake ID of the last read message (bigint)
        source: Origin of read event (web, telegram, api) - prevents sync loops
        telegram_message_id: Telegram message ID for syncing (enriched by router)
    """
    chat_id: UUID
    user_id: UUID
    last_read_message_id: int  # Snowflake ID (bigint) - matches ScyllaDB schema
    source: str = Field(default="web", description="web, telegram, api - prevents sync loops")
    telegram_message_id: Optional[int] = None  # Enriched by router for Telegram sync


# =============================================================================
# Typing Commands (ephemeral, not persisted)
# =============================================================================

class StartTypingCommand(Command):
    """Indicate user started typing"""
    chat_id: UUID
    user_id: UUID


class StopTypingCommand(Command):
    """Indicate user stopped typing"""
    chat_id: UUID
    user_id: UUID


# =============================================================================
# Telegram Integration Commands
# =============================================================================

class LinkTelegramChatCommand(Command):
    """Link a Telegram chat to WellWon chat"""
    chat_id: UUID
    telegram_chat_id: int
    telegram_topic_id: Optional[int] = None
    linked_by: UUID


class LinkChatToTelegramCommand(Command):
    """
    Link an existing WellWon chat to Telegram supergroup (used by saga).
    Creates a Telegram topic in the supergroup and updates the chat.
    """
    chat_id: UUID
    telegram_supergroup_id: int
    linked_by: UUID


class UnlinkTelegramChatCommand(Command):
    """Unlink a Telegram chat from WellWon chat"""
    chat_id: UUID
    unlinked_by: UUID


class ProcessTelegramMessageCommand(Command):
    """
    Process incoming message from Telegram.

    Note: message_id (Snowflake) is generated by the handler, not provided by client.
    This follows Discord's pattern where server generates permanent IDs.
    """
    chat_id: UUID
    telegram_message_id: int
    telegram_chat_id: int  # Required for deduplication lookup
    telegram_user_id: int
    sender_id: Optional[UUID] = None  # Mapped WellWon user if exists
    content: str
    message_type: str = Field(default="text")
    # File attachments
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    voice_duration: Optional[int] = None  # seconds
    # Telegram-specific metadata
    telegram_user_data: Optional[Dict[str, Any]] = None  # {first_name, last_name, username, is_bot}
    telegram_forward_data: Optional[Dict[str, Any]] = None  # Forward info if forwarded message
    telegram_topic_id: Optional[int] = None  # Forum topic ID


class UpdateMessageFileUrlCommand(Command):
    """
    Update a message's file URL after async upload completes.

    Used for fire-and-forget file processing:
    1. Telegram message arrives with file_id
    2. Message is stored immediately with temporary Telegram CDN URL
    3. Background task downloads file, uploads to MinIO
    4. This command updates the message with permanent MinIO URL

    This enables instant message display while file processing happens in background.
    """
    message_id: int  # Snowflake ID (bigint) - matches ScyllaDB message_id
    chat_id: UUID
    new_file_url: str = Field(..., min_length=1)
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None


# =============================================================================
# Client Invitation Commands
# =============================================================================

class InviteClientCommand(Command):
    """
    Invite external client to chat's Telegram group.

    Auto-resolves contact (phone or @username) to telegram_user_id via MTProto
    and invites them to the group.

    Args:
        chat_id: Chat whose Telegram group to invite client to
        contact: Phone (+79001234567) or username (@username or username)
        client_name: Client's name for contact import (e.g., "Ivan Petrov")
        invited_by: User who initiated the invitation
    """
    chat_id: UUID
    contact: str = Field(..., min_length=1, max_length=100, description="Phone (+79001234567) or @username")
    client_name: str = Field(..., min_length=1, max_length=255, description="Client name for contact import")
    invited_by: UUID
