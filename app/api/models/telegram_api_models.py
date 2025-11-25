# =============================================================================
#  File: app/api/models/telegram_api_models.py
#  WellWon API Models - Telegram Adapter
# =============================================================================
#  Pydantic models for Telegram webhook and group management endpoints
# =============================================================================

from __future__ import annotations

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
#  ENUMS
# =============================================================================

class TelegramMessageType(str, Enum):
    """Telegram message types."""
    TEXT = "text"
    PHOTO = "photo"
    DOCUMENT = "document"
    VOICE = "voice"
    AUDIO = "audio"
    VIDEO = "video"
    STICKER = "sticker"
    ANIMATION = "animation"


class TopicEmojiCategory(str, Enum):
    """Categories of topic emojis."""
    ORGANIZATION = "organization"
    STATUS = "status"
    BUSINESS = "business"


# =============================================================================
#  WEBHOOK MODELS
# =============================================================================

class WebhookResponse(BaseModel):
    """Standard webhook response."""
    ok: bool
    message: Optional[str] = None


class WebhookInfoResponse(BaseModel):
    """Webhook configuration info."""
    webhook_url: str
    webhook_configured: bool
    bot_api_available: bool
    mtproto_available: bool


class TelegramUpdateModel(BaseModel):
    """Telegram update structure (minimal for validation)."""
    update_id: int
    message: Optional[Dict[str, Any]] = None
    edited_message: Optional[Dict[str, Any]] = None
    channel_post: Optional[Dict[str, Any]] = None
    callback_query: Optional[Dict[str, Any]] = None


# =============================================================================
#  GROUP MANAGEMENT MODELS
# =============================================================================

class CreateGroupRequest(BaseModel):
    """Request to create a Telegram company group."""
    title: str = Field(..., min_length=1, max_length=255, description="Group title")
    description: Optional[str] = Field(default="", max_length=2000, description="Group description")
    photo_url: Optional[str] = Field(default=None, max_length=500, description="URL of group photo")
    setup_bots: bool = Field(default=True, description="Whether to add configured bots as admins")


class CreateGroupResponse(BaseModel):
    """Response after creating a group."""
    success: bool
    group_id: Optional[int] = None
    group_title: Optional[str] = None
    invite_link: Optional[str] = None
    bots_results: Optional[List[Dict[str, Any]]] = None
    permissions_set: Optional[bool] = None
    error: Optional[str] = None


class GroupInfoResponse(BaseModel):
    """Information about a Telegram group."""
    model_config = ConfigDict(from_attributes=True)

    success: bool
    group_id: int
    title: str
    description: Optional[str] = None
    invite_link: Optional[str] = None
    members_count: Optional[int] = None


class UpdateGroupRequest(BaseModel):
    """Request to update group info."""
    group_id: int = Field(..., description="Telegram group ID")
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)


# =============================================================================
#  TOPIC MANAGEMENT MODELS
# =============================================================================

class CreateTopicRequest(BaseModel):
    """Request to create a forum topic."""
    group_id: int = Field(..., description="Telegram group ID")
    topic_name: str = Field(..., min_length=1, max_length=128, description="Topic title")
    icon_emoji: Optional[str] = Field(default=None, max_length=10, description="Emoji icon for topic")


class CreateTopicResponse(BaseModel):
    """Response after creating a topic."""
    success: bool
    topic_id: Optional[int] = None
    title: Optional[str] = None
    emoji: Optional[str] = None
    emoji_id: Optional[int] = None
    error: Optional[str] = None


class UpdateTopicRequest(BaseModel):
    """Request to update a forum topic."""
    group_id: int = Field(..., description="Telegram group ID")
    topic_id: int = Field(..., description="Topic ID to update")
    new_name: Optional[str] = Field(None, min_length=1, max_length=128, description="New topic title")
    new_emoji: Optional[str] = Field(None, max_length=10, description="New emoji icon")


class TopicActionRequest(BaseModel):
    """Request for topic actions (delete, pin, etc.)."""
    group_id: int = Field(..., description="Telegram group ID")
    topic_id: int = Field(..., description="Topic ID")


class TopicInfoResponse(BaseModel):
    """Information about a single topic."""
    topic_id: int
    title: str
    emoji: Optional[str] = None
    emoji_id: Optional[int] = None
    pinned: bool = False


class TopicsListResponse(BaseModel):
    """List of topics in a group."""
    success: bool
    topics: List[TopicInfoResponse]


# =============================================================================
#  USER MANAGEMENT MODELS
# =============================================================================

class UserActionRequest(BaseModel):
    """Request for user actions (invite, remove)."""
    group_id: int = Field(..., description="Telegram group ID")
    username: str = Field(..., min_length=1, max_length=64, description="Telegram username (without @)")


# =============================================================================
#  MESSAGE MODELS
# =============================================================================

class SendMessageRequest(BaseModel):
    """Request to send a message."""
    chat_id: int = Field(..., description="Telegram chat ID")
    text: str = Field(..., min_length=1, max_length=4096, description="Message text")
    topic_id: Optional[int] = Field(default=None, description="Forum topic ID")
    reply_to_message_id: Optional[int] = Field(default=None, description="Message ID to reply to")
    parse_mode: str = Field(default="HTML", description="Parse mode (HTML, Markdown)")
    disable_notification: bool = Field(default=False, description="Send silently")


class SendMessageResponse(BaseModel):
    """Response after sending a message."""
    success: bool
    message_id: Optional[int] = None
    error: Optional[str] = None


class SendFileRequest(BaseModel):
    """Request to send a file."""
    chat_id: int = Field(..., description="Telegram chat ID")
    file_url: str = Field(..., max_length=1000, description="URL of file to send")
    file_name: Optional[str] = Field(None, max_length=255, description="File name")
    caption: Optional[str] = Field(None, max_length=1024, description="File caption")
    topic_id: Optional[int] = Field(default=None, description="Forum topic ID")


class TelegramMessageResponse(BaseModel):
    """Parsed Telegram message data."""
    model_config = ConfigDict(from_attributes=True)

    message_id: int
    chat_id: int
    topic_id: Optional[int] = None
    from_user_id: Optional[int] = None
    from_username: Optional[str] = None
    text: Optional[str] = None
    date: Optional[datetime] = None
    reply_to_message_id: Optional[int] = None
    file_id: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[TelegramMessageType] = None
    voice_duration: Optional[int] = None


# =============================================================================
#  EMOJI MODELS
# =============================================================================

class EmojiInfo(BaseModel):
    """Information about a single emoji."""
    emoji: str
    emoji_id: int
    category: Optional[TopicEmojiCategory] = None


class AvailableEmojisResponse(BaseModel):
    """List of available emojis for topics."""
    emojis: List[str]
    emoji_map: Dict[str, int]


# =============================================================================
#  BOT STATUS MODELS
# =============================================================================

class BotStatusResponse(BaseModel):
    """Telegram bot status."""
    bot_id: int
    bot_username: str
    bot_name: str
    can_join_groups: bool
    can_read_all_group_messages: bool
    supports_inline_queries: bool
    webhook_configured: bool
    webhook_url: Optional[str] = None
