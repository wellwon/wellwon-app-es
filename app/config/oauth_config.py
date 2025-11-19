# =============================================================================
# File: app/config/oauth_config.py
# Description: OAuth Configuration for WellWon (Telegram)
# =============================================================================

import os
from typing import Dict, Any, Optional

# =============================================================================
# OAuth Configuration
# =============================================================================
OAUTH_CONFIG: Dict[str, Any] = {
    # =========================================================================
    # Telegram Bot OAuth
    # =========================================================================
    "telegram": {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "webhook_secret": os.getenv("TELEGRAM_WEBHOOK_SECRET", ""),
        "api_url": "https://api.telegram.org",
    }
}


# =============================================================================
# Helper Functions
# =============================================================================
def get_oauth_config(provider_id: str) -> Optional[Dict[str, Any]]:
    """
    Get OAuth configuration for a provider

    Args:
        provider_id: 'telegram'

    Returns:
        OAuth config dict or None
    """
    config = OAUTH_CONFIG.get(provider_id)
    if not config:
        return None

    return config.copy()


def validate_oauth_config() -> Dict[str, bool]:
    """Check which providers have OAuth configured"""
    return {
        "telegram": bool(OAUTH_CONFIG["telegram"].get("bot_token"))
    }


# =============================================================================
# Quick access
# =============================================================================
def get_telegram_config() -> Dict[str, Any]:
    """Get Telegram Bot configuration"""
    return get_oauth_config("telegram")
