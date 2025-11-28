# Chat Command Handlers
# Import all handlers to trigger auto-registration via decorators

from app.chat.command_handlers.telegram_handlers import (
    LinkTelegramChatHandler,
    UnlinkTelegramChatHandler,
    ProcessTelegramMessageHandler,
)

__all__ = [
    'LinkTelegramChatHandler',
    'UnlinkTelegramChatHandler',
    'ProcessTelegramMessageHandler',
]
