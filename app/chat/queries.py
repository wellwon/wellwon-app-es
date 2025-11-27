# =============================================================================
# File: app/chat/queries.py
# Description: Chat domain queries
# =============================================================================

from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field
import uuid
from datetime import datetime

from app.infra.cqrs.query_bus import Query


# =============================================================================
# Chat Queries
# =============================================================================

class GetChatByIdQuery(Query):
    """Get chat details by ID"""
    chat_id: uuid.UUID


class GetChatsByUserQuery(Query):
    """Get all chats for a user"""
    user_id: uuid.UUID
    include_archived: bool = False
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class GetChatsByCompanyQuery(Query):
    """Get all chats for a company"""
    company_id: uuid.UUID
    include_archived: bool = False
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class GetChatByTelegramIdQuery(Query):
    """Get chat by Telegram chat ID"""
    telegram_chat_id: int
    telegram_topic_id: Optional[int] = None


class SearchChatsQuery(Query):
    """Search chats by name"""
    user_id: uuid.UUID
    search_term: str = Field(..., min_length=1, max_length=100)
    limit: int = Field(default=20, ge=1, le=50)


# =============================================================================
# Participant Queries
# =============================================================================

class GetChatParticipantsQuery(Query):
    """Get participants of a chat"""
    chat_id: uuid.UUID
    include_inactive: bool = False


class GetUserParticipationQuery(Query):
    """Check if user is participant in chat"""
    chat_id: uuid.UUID
    user_id: uuid.UUID


# =============================================================================
# Message Queries
# =============================================================================

class GetChatMessagesQuery(Query):
    """Get messages from a chat (paginated)"""
    chat_id: uuid.UUID
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    before_id: Optional[uuid.UUID] = None  # For cursor-based pagination
    after_id: Optional[uuid.UUID] = None


class GetMessageByIdQuery(Query):
    """Get a single message by ID"""
    message_id: uuid.UUID


class GetUnreadMessagesCountQuery(Query):
    """Get count of unread messages for user in chat"""
    chat_id: uuid.UUID
    user_id: uuid.UUID


class GetUnreadChatsCountQuery(Query):
    """Get count of chats with unread messages for user"""
    user_id: uuid.UUID


class SearchMessagesQuery(Query):
    """Search messages in chat"""
    chat_id: uuid.UUID
    search_term: str = Field(..., min_length=1, max_length=200)
    limit: int = Field(default=20, ge=1, le=50)


# =============================================================================
# Result Types
# =============================================================================

class ChatDetail(BaseModel):
    """Chat details for API response"""
    id: uuid.UUID
    name: Optional[str] = None
    chat_type: str
    created_by: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool = True
    participant_count: int = 0
    last_message_at: Optional[datetime] = None
    unread_count: int = 0
    # Telegram
    telegram_chat_id: Optional[int] = None
    telegram_topic_id: Optional[int] = None
    # Last message preview
    last_message_content: Optional[str] = None
    last_message_sender_id: Optional[uuid.UUID] = None


class ChatSummary(BaseModel):
    """Chat summary for list views"""
    id: uuid.UUID
    name: Optional[str] = None
    chat_type: str
    participant_count: int = 0
    last_message_at: Optional[datetime] = None
    last_message_content: Optional[str] = None
    unread_count: int = 0
    is_active: bool = True


class ParticipantInfo(BaseModel):
    """Participant information"""
    user_id: uuid.UUID
    role: str
    joined_at: datetime
    is_active: bool = True
    last_read_at: Optional[datetime] = None
    # User details (joined from user table)
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_avatar_url: Optional[str] = None


class MessageDetail(BaseModel):
    """Message details for API response"""
    id: uuid.UUID
    chat_id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    message_type: str = "text"
    reply_to_id: Optional[uuid.UUID] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    voice_duration: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_edited: bool = False
    is_deleted: bool = False
    read_by_count: int = 0
    # Source tracking
    source: str = "web"
    telegram_message_id: Optional[int] = None
    # Sender info (joined)
    sender_name: Optional[str] = None
    sender_avatar_url: Optional[str] = None
    # Reply preview
    reply_to_content: Optional[str] = None
    reply_to_sender_name: Optional[str] = None


class MessageSummary(BaseModel):
    """Lightweight message for lists"""
    id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    message_type: str
    created_at: datetime
    is_deleted: bool = False


class UnreadCount(BaseModel):
    """Unread messages count"""
    chat_id: uuid.UUID
    count: int


class UserParticipation(BaseModel):
    """User participation status in chat"""
    chat_id: uuid.UUID
    user_id: uuid.UUID
    is_participant: bool
    role: Optional[str] = None
    joined_at: Optional[datetime] = None
