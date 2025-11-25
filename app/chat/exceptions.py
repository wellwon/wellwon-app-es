# =============================================================================
# File: app/chat/exceptions.py
# Description: Chat domain exceptions
# =============================================================================

from app.common.exceptions.exceptions import DomainError, ResourceNotFoundError


class ChatError(DomainError):
    """Base exception for Chat domain"""
    pass


class ChatNotFoundError(ResourceNotFoundError):
    """Chat not found"""
    def __init__(self, chat_id: str):
        super().__init__(f"Chat not found: {chat_id}")
        self.chat_id = chat_id


class ChatAlreadyExistsError(ChatError):
    """Chat already exists"""
    def __init__(self, chat_id: str):
        super().__init__(f"Chat already exists: {chat_id}")
        self.chat_id = chat_id


class ParticipantNotFoundError(ResourceNotFoundError):
    """Participant not found in chat"""
    def __init__(self, chat_id: str, user_id: str):
        super().__init__(f"Participant {user_id} not found in chat {chat_id}")
        self.chat_id = chat_id
        self.user_id = user_id


class UserNotParticipantError(ChatError):
    """User is not a participant of the chat"""
    def __init__(self, chat_id: str, user_id: str):
        super().__init__(f"User {user_id} is not a participant of chat {chat_id}")
        self.chat_id = chat_id
        self.user_id = user_id


class UserAlreadyParticipantError(ChatError):
    """User is already a participant of the chat"""
    def __init__(self, chat_id: str, user_id: str):
        super().__init__(f"User {user_id} is already a participant of chat {chat_id}")
        self.chat_id = chat_id
        self.user_id = user_id


class MessageNotFoundError(ResourceNotFoundError):
    """Message not found"""
    def __init__(self, message_id: str):
        super().__init__(f"Message not found: {message_id}")
        self.message_id = message_id


class UnauthorizedToDeleteMessageError(ChatError):
    """User cannot delete this message"""
    def __init__(self, message_id: str, user_id: str):
        super().__init__(f"User {user_id} cannot delete message {message_id}")
        self.message_id = message_id
        self.user_id = user_id


class UnauthorizedToEditMessageError(ChatError):
    """User cannot edit this message"""
    def __init__(self, message_id: str, user_id: str):
        super().__init__(f"User {user_id} cannot edit message {message_id}")
        self.message_id = message_id
        self.user_id = user_id


class ChatInactiveError(ChatError):
    """Chat is not active"""
    def __init__(self, chat_id: str):
        super().__init__(f"Chat {chat_id} is not active")
        self.chat_id = chat_id


class InsufficientPermissionsError(ChatError):
    """User does not have sufficient permissions"""
    def __init__(self, user_id: str, action: str):
        super().__init__(f"User {user_id} does not have permission to {action}")
        self.user_id = user_id
        self.action = action
