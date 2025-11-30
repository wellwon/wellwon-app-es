# =============================================================================
# File: app/infra/telegram/config.py
# Description: Telegram adapter configuration
# =============================================================================

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, List

log = logging.getLogger("wellwon.telegram.config")


@dataclass
class TelegramConfig:
    """
    Configuration for Telegram adapter.

    Environment variables:
        # Bot API
        TELEGRAM_BOT_TOKEN: Bot API token from @BotFather
        TELEGRAM_WEBHOOK_URL: Public URL for webhook (e.g., https://api.wellwon.com)
        TELEGRAM_WEBHOOK_SECRET: Secret token for webhook verification

        # MTProto (Telethon)
        TELEGRAM_API_ID: MTProto API ID (from my.telegram.org)
        TELEGRAM_API_HASH: MTProto API hash (from my.telegram.org)
        TELEGRAM_SESSION_STRING: Telethon session string (generated via get_session_string.py)
        TELEGRAM_SESSION_NAME: Session file name (fallback if no session string)
        TELEGRAM_ADMIN_PHONE: Phone number for MTProto admin operations

        # Bots to add to groups
        TELEGRAM_BOT_USERNAMES: Comma-separated bot usernames to add as admins
    """

    # Bot API settings
    bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    webhook_url: Optional[str] = field(default_factory=lambda: os.getenv("TELEGRAM_WEBHOOK_URL"))
    webhook_secret: str = field(default_factory=lambda: os.getenv("TELEGRAM_WEBHOOK_SECRET", ""))
    webhook_path: str = "/api/telegram/webhook"

    # MTProto settings (for Telethon - group/topic creation)
    api_id: int = field(default_factory=lambda: int(os.getenv("TELEGRAM_API_ID", "0")))
    api_hash: str = field(default_factory=lambda: os.getenv("TELEGRAM_API_HASH", ""))
    session_string: Optional[str] = field(default_factory=lambda: os.getenv("TELEGRAM_SESSION_STRING"))
    session_name: str = field(default_factory=lambda: os.getenv("TELEGRAM_SESSION_NAME", "wellwon_telegram"))
    admin_phone: Optional[str] = field(default_factory=lambda: os.getenv("TELEGRAM_ADMIN_PHONE"))

    # Bots configuration
    bot_usernames: List[str] = field(default_factory=lambda: _parse_bot_usernames())

    # Rate limiting
    messages_per_second: float = 30.0  # Telegram limit: 30 msg/s to different chats
    messages_per_chat_per_minute: int = 20  # Per-chat limit

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    # Feature flags
    enable_webhook: bool = field(default_factory=lambda: os.getenv("TELEGRAM_ENABLE_WEBHOOK", "true").lower() == "true")
    enable_mtproto: bool = field(default_factory=lambda: os.getenv("TELEGRAM_ENABLE_MTPROTO", "true").lower() == "true")

    def __post_init__(self):
        """Validate configuration"""
        # Bot token is optional now - only required if webhook is enabled
        if self.enable_webhook and not self.bot_token:
            log.warning("TELEGRAM_BOT_TOKEN not set - Bot API features disabled")

        # MTProto validation
        if self.enable_mtproto:
            if not self.api_id or not self.api_hash:
                log.warning("TELEGRAM_API_ID or TELEGRAM_API_HASH not set - MTProto features disabled")
            if not self.session_string and not self.admin_phone:
                log.warning("Neither TELEGRAM_SESSION_STRING nor TELEGRAM_ADMIN_PHONE set - MTProto auth may fail")

    @property
    def full_webhook_url(self) -> str:
        """Get full webhook URL"""
        if not self.webhook_url:
            return ""
        base = self.webhook_url.rstrip("/")
        return f"{base}{self.webhook_path}"

    @property
    def bot_api_available(self) -> bool:
        """Check if Bot API is configured"""
        return bool(self.bot_token)

    @property
    def mtproto_available(self) -> bool:
        """Check if MTProto is configured"""
        return bool(self.api_id and self.api_hash and (self.session_string or self.admin_phone))

    @classmethod
    def from_env(cls) -> 'TelegramConfig':
        """Create config from environment variables"""
        return cls()


def _parse_bot_usernames() -> List[str]:
    """Parse bot usernames from environment"""
    env_value = os.getenv("TELEGRAM_BOT_USERNAMES", "WellWonAssist_bot,wellwon_app_bot")
    if not env_value:
        return ["WellWonAssist_bot", "wellwon_app_bot"]
    return [u.strip() for u in env_value.split(",") if u.strip()]


# Singleton instance
_config: Optional[TelegramConfig] = None


def get_telegram_config() -> TelegramConfig:
    """Get singleton Telegram config"""
    global _config
    if _config is None:
        _config = TelegramConfig.from_env()
    return _config


def reset_telegram_config() -> None:
    """Reset config singleton (for testing)"""
    global _config
    _config = None
