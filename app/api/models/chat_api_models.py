# =============================================================================
#  File: app/api/models/chat_api_models.py
#  WellWon API Models - Chat Domain
# =============================================================================
#  Pydantic models for Chat and Messaging endpoints
# =============================================================================

from __future__ import annotations

from typing import Optional, Dict, Any, List, Annotated
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    StringConstraints,
    field_validator,
)


# =============================================================================
#  ENUMS
# =============================================================================

class ChatStatus(str, Enum):
    """Chat status."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    CLOSED = "closed"


class MessageType(str, Enum):
    """Message content types."""
    TEXT = "text"
    PHOTO = "photo"
    DOCUMENT = "document"
    VOICE = "voice"
    AUDIO = "audio"
    VIDEO = "video"
    SYSTEM = "system"
    TEMPLATE = "template"


class MessageDirection(str, Enum):
    """Message sync direction."""
    WEB_TO_TELEGRAM = "web_to_telegram"
    TELEGRAM_TO_WEB = "telegram_to_web"
    BIDIRECTIONAL = "bidirectional"
    INTERNAL = "internal"


class ExternalChannelType(str, Enum):
    """External communication channel types."""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    SMS = "sms"


class ParticipantRole(str, Enum):
    """Participant roles in a chat."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    EXTERNAL = "external"
    BOT = "bot"


# =============================================================================
#  TYPE ALIASES
# =============================================================================

ChatTitle = Annotated[str, StringConstraints(min_length=1, max_length=255)]
MessageContent = Annotated[str, StringConstraints(min_length=1, max_length=10000)]


# =============================================================================
#  CHAT MODELS
# =============================================================================

class CreateChatRequest(BaseModel):
    """Request to create a new chat."""
    title: ChatTitle = Field(..., description="Chat title")
    company_id: UUID = Field(..., description="Company this chat belongs to")
    deal_id: Optional[UUID] = Field(default=None, description="Associated deal ID")
    description: Optional[str] = Field(default=None, max_length=2000)

    # Telegram integration
    create_telegram_topic: bool = Field(default=False, description="Create a Telegram topic for this chat")
    telegram_group_id: Optional[int] = Field(default=None, description="Telegram group to create topic in")
    topic_emoji: Optional[str] = Field(default=None, max_length=10, description="Emoji for Telegram topic")

    # Sync settings
    sync_enabled: bool = Field(default=True, description="Enable message sync with external channel")

    metadata: Optional[Dict[str, Any]] = Field(default=None)


class CreateChatResponse(BaseModel):
    """Response after creating a chat."""
    success: bool
    chat_id: Optional[UUID] = None
    title: Optional[str] = None
    telegram_topic_id: Optional[int] = None
    error: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat information response."""
    model_config = ConfigDict(from_attributes=True)

    chat_id: UUID
    title: str
    company_id: UUID
    deal_id: Optional[UUID] = None
    status: ChatStatus = ChatStatus.ACTIVE
    description: Optional[str] = None

    # External channel info
    external_channel_type: Optional[ExternalChannelType] = None
    external_channel_id: Optional[str] = None
    external_topic_id: Optional[str] = None
    sync_enabled: bool = True

    # Stats
    unread_count: int = 0
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    participants_count: int = 0

    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateChatRequest(BaseModel):
    """Request to update a chat."""
    title: Optional[ChatTitle] = None
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[ChatStatus] = None
    sync_enabled: Optional[bool] = None
    topic_emoji: Optional[str] = Field(None, max_length=10)
    metadata: Optional[Dict[str, Any]] = None


class ChatListResponse(BaseModel):
    """List of chats response."""
    chats: List[ChatResponse]
    total: int
    page: int = 1
    page_size: int = 50
    has_more: bool = False


class ChatFilterParams(BaseModel):
    """Chat filter parameters."""
    company_id: Optional[UUID] = None
    deal_id: Optional[UUID] = None
    status: Optional[ChatStatus] = None
    search: Optional[str] = Field(None, max_length=100)
    has_unread: Optional[bool] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


# =============================================================================
#  MESSAGE MODELS
# =============================================================================

class SendMessageRequest(BaseModel):
    """Request to send a message."""
    chat_id: UUID = Field(..., description="Chat to send message to")
    content: MessageContent = Field(..., description="Message content")
    message_type: MessageType = Field(default=MessageType.TEXT)

    # File attachment
    file_url: Optional[str] = Field(None, max_length=1000)
    file_name: Optional[str] = Field(None, max_length=255)
    file_size: Optional[int] = Field(None, ge=0)

    # Reply
    reply_to_message_id: Optional[UUID] = None

    # Template message
    template_id: Optional[str] = Field(None, max_length=100)
    template_data: Optional[Dict[str, Any]] = None

    metadata: Optional[Dict[str, Any]] = None


class SendMessageResponse(BaseModel):
    """Response after sending a message."""
    success: bool
    message_id: Optional[UUID] = None
    external_message_id: Optional[str] = None
    error: Optional[str] = None


class MessageResponse(BaseModel):
    """Message information response."""
    model_config = ConfigDict(from_attributes=True)

    message_id: UUID
    chat_id: UUID
    sender_id: UUID
    sender_name: str
    sender_avatar: Optional[str] = None

    content: str
    message_type: MessageType = MessageType.TEXT

    # File info
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_mime_type: Optional[str] = None

    # Voice specific
    voice_duration: Optional[int] = None

    # Reply info
    reply_to_message_id: Optional[UUID] = None
    reply_to_preview: Optional[str] = None

    # External sync
    external_message_id: Optional[str] = None
    sync_direction: Optional[MessageDirection] = None

    # Telegram sync (for checkmarks)
    telegram_message_id: Optional[int] = None  # Delivery status (double gray checkmark)
    telegram_chat_id: Optional[int] = None
    telegram_read_at: Optional[datetime] = None  # Read status (double blue checkmark)

    # Template
    template_id: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None

    # Status
    is_read: bool = False
    is_edited: bool = False
    is_deleted: bool = False

    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MessageListResponse(BaseModel):
    """List of messages response."""
    messages: List[MessageResponse]
    total: int
    has_more: bool = False
    oldest_message_id: Optional[UUID] = None
    newest_message_id: Optional[UUID] = None


class MessageFilterParams(BaseModel):
    """Message filter parameters."""
    chat_id: UUID
    before_message_id: Optional[UUID] = None
    after_message_id: Optional[UUID] = None
    message_type: Optional[MessageType] = None
    sender_id: Optional[UUID] = None
    search: Optional[str] = Field(None, max_length=100)
    limit: int = Field(default=50, ge=1, le=100)


class EditMessageRequest(BaseModel):
    """Request to edit a message."""
    message_id: UUID
    content: MessageContent


class DeleteMessageRequest(BaseModel):
    """Request to delete a message."""
    message_id: UUID
    delete_for_everyone: bool = Field(default=True)


# =============================================================================
#  PARTICIPANT MODELS
# =============================================================================

class AddParticipantRequest(BaseModel):
    """Request to add a participant to a chat."""
    chat_id: UUID
    user_id: UUID
    role: ParticipantRole = Field(default=ParticipantRole.MEMBER)


class RemoveParticipantRequest(BaseModel):
    """Request to remove a participant from a chat."""
    chat_id: UUID
    user_id: UUID


class ParticipantResponse(BaseModel):
    """Participant information."""
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    chat_id: UUID
    role: ParticipantRole

    # User info (denormalized)
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None

    # External user info (for Telegram users)
    external_user_id: Optional[str] = None
    external_username: Optional[str] = None
    is_external: bool = False

    joined_at: datetime
    last_read_at: Optional[datetime] = None
    unread_count: int = 0


class ParticipantsListResponse(BaseModel):
    """List of participants."""
    participants: List[ParticipantResponse]
    total: int


# =============================================================================
#  TYPING & PRESENCE MODELS
# =============================================================================

class TypingIndicatorRequest(BaseModel):
    """Request to send typing indicator."""
    chat_id: UUID
    is_typing: bool = True


class PresenceStatus(str, Enum):
    """User presence status."""
    ONLINE = "online"
    AWAY = "away"
    OFFLINE = "offline"


class UserPresenceResponse(BaseModel):
    """User presence information."""
    user_id: UUID
    status: PresenceStatus
    last_seen: Optional[datetime] = None
    current_chat_id: Optional[UUID] = None


# =============================================================================
#  READ RECEIPT MODELS
# =============================================================================

class MarkAsReadRequest(BaseModel):
    """Request to mark messages as read."""
    chat_id: UUID
    last_read_message_id: UUID


class ReadReceiptResponse(BaseModel):
    """Read receipt response."""
    success: bool
    unread_count: int = 0


# =============================================================================
#  EXTERNAL CHANNEL MODELS
# =============================================================================

class LinkExternalChannelRequest(BaseModel):
    """Request to link an external channel to a chat."""
    chat_id: UUID
    channel_type: ExternalChannelType
    channel_id: str = Field(..., max_length=100)
    topic_id: Optional[str] = Field(None, max_length=100)
    sync_enabled: bool = True


class UnlinkExternalChannelRequest(BaseModel):
    """Request to unlink external channel."""
    chat_id: UUID


class ExternalMessageRequest(BaseModel):
    """Incoming message from external channel."""
    channel_type: ExternalChannelType
    channel_id: str
    topic_id: Optional[str] = None
    external_message_id: str
    external_sender_id: str
    external_sender_name: str
    content: str
    message_type: MessageType = MessageType.TEXT
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None


# =============================================================================
#  STATUS RESPONSES
# =============================================================================

class ChatStatusResponse(BaseModel):
    """Generic chat status response."""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
#  CONVERSATION LIST MODELS (for sidebar)
# =============================================================================

class ConversationItem(BaseModel):
    """Conversation item for sidebar list."""
    model_config = ConfigDict(from_attributes=True)

    chat_id: UUID
    title: str
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: int = 0

    # Associated entities
    deal_id: Optional[UUID] = None
    company_id: Optional[UUID] = None

    # Status
    status: ChatStatus = ChatStatus.ACTIVE

    # Telegram info
    telegram_supergroup_id: Optional[int] = None
    telegram_topic_id: Optional[int] = None
    telegram_sync: bool = False

    # Visual
    avatar_url: Optional[str] = None
    emoji: Optional[str] = None


class ConversationsListResponse(BaseModel):
    """List of conversations for sidebar."""
    conversations: List[ConversationItem]
    total: int
    unread_total: int = 0
