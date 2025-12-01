# =============================================================================
# File: app/config/telegram_config.py
# Description: Telegram integration configuration (Bot API + MTProto)
# =============================================================================

from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from app.config.logging_config import get_logger

log = get_logger("wellwon.config.telegram")


class TelegramConfig(BaseSettings):
    """
    Telegram integration configuration.

    Controls:
    - Bot API settings (webhook, token)
    - MTProto settings (Telethon for user-level operations)
    - Rate limiting and flood protection
    - Reconnection and caching
    """

    # =========================================================================
    # Bot API Settings
    # =========================================================================

    bot_token: str = Field(
        default="",
        description="Bot API token from @BotFather"
    )

    webhook_url: Optional[str] = Field(
        default=None,
        description="Public URL for webhook (e.g., https://api.wellwon.com)"
    )

    webhook_secret: str = Field(
        default="",
        description="Secret token for webhook verification"
    )

    webhook_path: str = Field(
        default="/api/telegram/webhook",
        description="Webhook endpoint path"
    )

    # =========================================================================
    # MTProto Settings (Telethon)
    # =========================================================================

    api_id: int = Field(
        default=0,
        description="MTProto API ID (from my.telegram.org)"
    )

    api_hash: str = Field(
        default="",
        description="MTProto API hash (from my.telegram.org)"
    )

    session_string: Optional[str] = Field(
        default=None,
        description="Telethon session string"
    )

    session_name: str = Field(
        default="wellwon_telegram",
        description="Session file name (fallback if no session_string)"
    )

    admin_phone: Optional[str] = Field(
        default=None,
        description="Phone number for MTProto admin operations"
    )

    # =========================================================================
    # Bots Configuration
    # =========================================================================

    bot_usernames: str = Field(
        default="WellWonAssist_bot,wellwon_app_bot",
        description="Comma-separated bot usernames to add as admins"
    )

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    messages_per_second: float = Field(
        default=30.0,
        description="Global rate limit (Telegram limit: 30 msg/s to different chats)"
    )

    messages_per_chat_per_minute: int = Field(
        default=20,
        description="Per-chat rate limit"
    )

    # =========================================================================
    # Retry Settings
    # =========================================================================

    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts"
    )

    retry_delay_seconds: float = Field(
        default=1.0,
        description="Initial retry delay in seconds"
    )

    # =========================================================================
    # MTProto Flood Protection (Telethon best practices)
    # =========================================================================

    flood_sleep_threshold: int = Field(
        default=60,
        description="Auto-sleep threshold for FloodWaitError (seconds). 0=disable, 86400=always sleep"
    )

    backoff_initial_delay: float = Field(
        default=1.0,
        description="Initial exponential backoff delay (seconds)"
    )

    backoff_max_delay: float = Field(
        default=300.0,
        description="Maximum exponential backoff delay (5 minutes)"
    )

    backoff_multiplier: float = Field(
        default=2.0,
        description="Exponential backoff multiplier"
    )

    backoff_jitter: bool = Field(
        default=True,
        description="Add random jitter to avoid thundering herd"
    )

    # =========================================================================
    # Reconnection Settings
    # =========================================================================

    auto_reconnect: bool = Field(
        default=True,
        description="Automatically reconnect on connection loss"
    )

    reconnect_delay: float = Field(
        default=5.0,
        description="Initial reconnection delay (seconds)"
    )

    max_reconnect_attempts: int = Field(
        default=5,
        description="Maximum reconnection attempts"
    )

    # =========================================================================
    # Entity Caching
    # =========================================================================

    cache_dialogs_on_connect: bool = Field(
        default=True,
        description="Pre-populate entity cache on connect (reduces API calls)"
    )

    entity_cache_ttl: int = Field(
        default=3600,
        description="Entity cache TTL in seconds (1 hour)"
    )

    # =========================================================================
    # Feature Flags
    # =========================================================================

    enable_webhook: bool = Field(
        default=True,
        description="Enable Bot API webhook"
    )

    enable_mtproto: bool = Field(
        default=True,
        description="Enable MTProto client"
    )

    # =========================================================================
    # Environment Configuration
    # =========================================================================

    model_config = {
        "env_prefix": "TELEGRAM_",
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "allow"
    }

    # =========================================================================
    # Validators
    # =========================================================================

    @field_validator('bot_usernames', mode='before')
    @classmethod
    def parse_bot_usernames(cls, v):
        """Accept string or list for bot_usernames."""
        if isinstance(v, list):
            return ','.join(v)
        return v or "WellWonAssist_bot,wellwon_app_bot"

    @field_validator('api_id', mode='before')
    @classmethod
    def parse_api_id(cls, v):
        """Convert string to int for api_id."""
        if isinstance(v, str):
            return int(v) if v else 0
        return v or 0

    @field_validator('flood_sleep_threshold', mode='before')
    @classmethod
    def parse_flood_sleep_threshold(cls, v):
        """Convert string to int."""
        if isinstance(v, str):
            return int(v) if v else 60
        return v or 60

    # =========================================================================
    # Computed Properties
    # =========================================================================

    @property
    def full_webhook_url(self) -> str:
        """Get full webhook URL."""
        if not self.webhook_url:
            return ""
        base = self.webhook_url.rstrip("/")
        return f"{base}{self.webhook_path}"

    @property
    def bot_api_available(self) -> bool:
        """Check if Bot API is configured."""
        return bool(self.bot_token)

    @property
    def mtproto_available(self) -> bool:
        """Check if MTProto is configured."""
        return bool(self.api_id and self.api_hash and (self.session_string or self.admin_phone))

    @property
    def bot_usernames_list(self) -> List[str]:
        """Get bot usernames as list."""
        if not self.bot_usernames:
            return ["WellWonAssist_bot", "wellwon_app_bot"]
        return [u.strip() for u in self.bot_usernames.split(",") if u.strip()]

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def validate_config(self) -> None:
        """Validate configuration and log warnings."""
        if self.enable_webhook and not self.bot_token:
            log.warning("TELEGRAM_BOT_TOKEN not set - Bot API features disabled")

        if self.enable_mtproto:
            if not self.api_id or not self.api_hash:
                log.warning("TELEGRAM_API_ID or TELEGRAM_API_HASH not set - MTProto disabled")
            if not self.session_string and not self.admin_phone:
                log.warning("Neither TELEGRAM_SESSION_STRING nor TELEGRAM_ADMIN_PHONE set")


# =============================================================================
# Singleton
# =============================================================================

_telegram_config: TelegramConfig | None = None


def get_telegram_config() -> TelegramConfig:
    """Get Telegram configuration singleton."""
    global _telegram_config
    if _telegram_config is None:
        _telegram_config = TelegramConfig()
        _telegram_config.validate_config()
    return _telegram_config


def reset_telegram_config() -> None:
    """Reset config singleton (for testing)."""
    global _telegram_config
    _telegram_config = None
