# =============================================================================
# File: app/chat/enums.py
# Description: Chat domain enumerations
# =============================================================================

from enum import Enum


class ChatType(str, Enum):
    """Types of chats"""
    DIRECT = "direct"
    GROUP = "group"
    COMPANY = "company"


class ParticipantRole(str, Enum):
    """Participant roles in chat"""
    MEMBER = "member"
    ADMIN = "admin"
    OBSERVER = "observer"


class MessageType(str, Enum):
    """Types of messages"""
    TEXT = "text"
    FILE = "file"
    VOICE = "voice"
    IMAGE = "image"
    SYSTEM = "system"


class MessageStatus(str, Enum):
    """Message delivery status"""
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
