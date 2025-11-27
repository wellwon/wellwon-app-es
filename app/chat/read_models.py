# =============================================================================
# File: app/chat/read_models.py
# Description: Chat domain read models for database projections
# =============================================================================

from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
import uuid
from datetime import datetime


class ChatReadModel(BaseModel):
    """Read model for chat details (PostgreSQL table: chats)"""
    id: uuid.UUID
    name: Optional[str] = None
    chat_type: str  # direct, group, company
    company_id: Optional[uuid.UUID] = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool = True
    participant_count: int = 0
    last_message_at: Optional[datetime] = None
    last_message_content: Optional[str] = None
    last_message_sender_id: Optional[uuid.UUID] = None
    # Telegram integration
    telegram_chat_id: Optional[int] = None
    telegram_topic_id: Optional[int] = None
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: int = 0

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v)
        }
    )


class ChatParticipantReadModel(BaseModel):
    """Read model for chat participants (PostgreSQL table: chat_participants)"""
    id: uuid.UUID
    chat_id: uuid.UUID
    user_id: uuid.UUID
    role: str = "member"  # member, admin, observer
    joined_at: datetime
    last_read_at: Optional[datetime] = None
    last_read_message_id: Optional[uuid.UUID] = None
    is_active: bool = True

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v)
        }
    )


class MessageReadModel(BaseModel):
    """Read model for messages (PostgreSQL table: messages)"""
    id: uuid.UUID
    chat_id: uuid.UUID
    sender_id: Optional[uuid.UUID] = None  # None for external Telegram users
    content: str
    message_type: str = "text"  # text, file, voice, image, system
    reply_to_id: Optional[uuid.UUID] = None
    # File attachments
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    voice_duration: Optional[int] = None  # seconds
    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    # Status flags
    is_edited: bool = False
    is_deleted: bool = False
    # Source tracking
    source: str = "web"  # web, telegram, api
    # Telegram integration
    telegram_message_id: Optional[int] = None
    telegram_user_id: Optional[int] = None  # Telegram user ID (for unmapped users)
    telegram_user_data: Optional[Dict[str, Any]] = None  # {first_name, last_name, username, is_bot}
    telegram_forward_data: Optional[Dict[str, Any]] = None  # Forward info if forwarded
    telegram_topic_id: Optional[int] = None  # Forum topic ID
    sync_direction: Optional[str] = None  # 'telegram_to_web' | 'web_to_telegram' | 'bidirectional'
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v)
        }
    )


class MessageReadStatusModel(BaseModel):
    """Read model for message read status (PostgreSQL table: message_reads)"""
    id: uuid.UUID
    message_id: uuid.UUID
    user_id: uuid.UUID
    read_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v)
        }
    )


class TypingIndicatorModel(BaseModel):
    """Model for typing indicators (ephemeral, Redis-based)"""
    chat_id: uuid.UUID
    user_id: uuid.UUID
    started_at: datetime
    expires_at: datetime  # Auto-expire after ~10 seconds


# =============================================================================
# Composite Read Models (with joins)
# =============================================================================

class ChatWithParticipantsReadModel(BaseModel):
    """Chat with full participant list"""
    chat: ChatReadModel
    participants: List[ChatParticipantReadModel] = Field(default_factory=list)


class MessageWithSenderReadModel(BaseModel):
    """Message with sender information"""
    message: MessageReadModel
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    sender_avatar_url: Optional[str] = None


class ChatListItemReadModel(BaseModel):
    """Chat item for list views with aggregated data"""
    id: uuid.UUID
    name: Optional[str] = None
    chat_type: str
    participant_count: int = 0
    last_message_at: Optional[datetime] = None
    last_message_content: Optional[str] = None
    last_message_sender_name: Optional[str] = None
    unread_count: int = 0
    is_active: bool = True
    # Other participants (for direct chats - show other user's info)
    other_participant_name: Optional[str] = None
    other_participant_avatar_url: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v)
        }
    )
