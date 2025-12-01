# =============================================================================
# Telegram Adapter (Infrastructure Layer)
# =============================================================================
#
# This package implements the Telegram integration as an infrastructure adapter
# following the Hexagonal Architecture (Ports & Adapters) pattern.
#
# Architecture:
#   - TelegramAdapter: Main facade for Telegram operations
#   - TelegramBotClient: aiogram-based Bot API client (messages, webhook)
#   - TelegramMTProtoClient: Telethon-based MTProto client (groups, topics, user-level ops)
#   - webhook_handler: FastAPI router for Telegram webhook
#   - event_listener: Listens to domain events and sends to Telegram
#
# The adapter bridges between:
#   - WellWon Chat Domain (internal) <-> Telegram Bot API/MTProto (external)
#
# Dependencies:
#   - aiogram 3.x for Bot API
#   - telethon for MTProto operations
# =============================================================================

from app.config.telegram_config import (
    TelegramConfig,
    get_telegram_config,
    reset_telegram_config,
)
from app.infra.telegram.bot_client import (
    TelegramBotClient,
    TelegramMessage,
    SendMessageResult,
)
from app.infra.telegram.mtproto_client import (
    TelegramMTProtoClient,
    GroupInfo,
    TopicInfo,
    OperationResult,
    EMOJI_MAP,
)
from app.infra.telegram.adapter import (
    TelegramAdapter,
    CompanyGroupResult,
    get_telegram_adapter,
    close_telegram_adapter,
)

__all__ = [
    # Config
    "TelegramConfig",
    "get_telegram_config",
    "reset_telegram_config",
    # Bot API Client
    "TelegramBotClient",
    "TelegramMessage",
    "SendMessageResult",
    # MTProto Client
    "TelegramMTProtoClient",
    "GroupInfo",
    "TopicInfo",
    "OperationResult",
    "EMOJI_MAP",
    # Unified Adapter
    "TelegramAdapter",
    "CompanyGroupResult",
    "get_telegram_adapter",
    "close_telegram_adapter",
]
