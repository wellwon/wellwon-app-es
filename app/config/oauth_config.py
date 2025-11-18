# =============================================================================
# File: app/config/oauth_config.py
# Description: OAuth Configuration with Complete Alpaca Scopes
# =============================================================================

import os
from typing import Dict, Any, Optional

# =============================================================================
# OAuth Configuration
# =============================================================================
OAUTH_CONFIG: Dict[str, Any] = {
    # =========================================================================
    # Alpaca - FIXED with all 3 required scopes
    # =========================================================================
    "alpaca": {
        "client_id": os.getenv("ALPACA_OAUTH_CLIENT_ID", ""),
        "client_secret": os.getenv("ALPACA_OAUTH_CLIENT_SECRET", ""),
        "auth_url": "https://app.alpaca.markets/oauth/authorize",
        "token_url": "https://api.alpaca.markets/oauth/token",
        "redirect_uri": os.getenv("ALPACA_OAUTH_REDIRECT_URI", "http://localhost:5001/oauth/alpaca/callback"),
        "scopes": ["account:write", "trading", "data"],  # FIXED: Added "data" scope
        "pkce_required": False,
        "api_endpoints": {
            "paper": "https://paper-api.alpaca.markets",
            "live": "https://api.alpaca.markets"
        }
    },

    # =========================================================================
    # TradeStation - Uses HTTP Chunked Transfer for streaming (NOT WebSocket!)
    # =========================================================================
    "tradestation": {
        "client_id": os.getenv("TRADESTATION_CLIENT_ID", ""),
        "client_secret": os.getenv("TRADESTATION_CLIENT_SECRET", ""),
        "auth_url": os.getenv("TRADESTATION_AUTH_URL", "https://signin.tradestation.com/oauth/authorize"),
        "token_url": os.getenv("TRADESTATION_TOKEN_URL", "https://signin.tradestation.com/oauth/token"),
        "redirect_uri": os.getenv("TRADESTATION_REDIRECT_URI", "http://localhost:5001/oauth/tradestation/callback"),
        "scopes": os.getenv(
            "TRADESTATION_SCOPES",
            "openid profile offline_access MarketData ReadAccount Trade OptionSpreads"
        ).split(),
        "pkce_required": True,
        "api_endpoints": {
            "sim": os.getenv("TRADESTATION_SIM_API_URL", "https://sim-api.tradestation.com/v3"),
            "live": os.getenv("TRADESTATION_LIVE_API_URL", "https://api.tradestation.com/v3")
        },
        "stream_endpoints": {
            "sim": os.getenv("TRADESTATION_SIM_STREAM_URL", "https://sim-api.tradestation.com"),
            "live": os.getenv("TRADESTATION_LIVE_STREAM_URL", "https://api.tradestation.com")
        },
        "audience": os.getenv("TRADESTATION_AUDIENCE", "https://api.tradestation.com")
    }
}


# =============================================================================
# Helper Functions
# =============================================================================
def get_oauth_config(broker_id: str, environment: str = None) -> Optional[Dict[str, Any]]:
    """
    Get OAuth configuration for a broker

    Args:
        broker_id: 'alpaca' or 'tradestation'
        environment: 'paper'/'live' for alpaca, 'sim'/'live' for tradestation

    Returns:
        OAuth config dict or None
    """
    config = OAUTH_CONFIG.get(broker_id)
    if not config:
        return None

    # Create a copy to avoid modifying the original
    config = config.copy()

    # Check if credentials are set
    if not config.get("client_id") or not config.get("client_secret"):
        raise ValueError(f"OAuth credentials not set for {broker_id}. Set environment variables!")

    # Add API endpoint for specific environment
    if environment and "api_endpoints" in config:
        config["api_endpoint"] = config["api_endpoints"].get(environment)

    return config


def validate_oauth_config() -> Dict[str, bool]:
    """Check which brokers have OAuth configured"""
    return {
        broker: bool(config.get("client_id") and config.get("client_secret"))
        for broker, config in OAUTH_CONFIG.items()
    }


# =============================================================================
# Quick access
# =============================================================================
def get_alpaca_oauth() -> Dict[str, Any]:
    """Get Alpaca OAuth configuration"""
    return get_oauth_config("alpaca")


def get_tradestation_oauth() -> Dict[str, Any]:
    """Get TradeStation OAuth configuration"""
    return get_oauth_config("tradestation")


# =============================================================================
# Scope helpers
# =============================================================================
def get_alpaca_scopes_string() -> str:
    """Get Alpaca scopes as a space-separated string"""
    alpaca_config = OAUTH_CONFIG.get("alpaca", {})
    scopes = alpaca_config.get("scopes", [])
    return " ".join(scopes)


def get_tradestation_scopes_string() -> str:
    """Get TradeStation scopes as a space-separated string"""
    ts_config = OAUTH_CONFIG.get("tradestation", {})
    scopes = ts_config.get("scopes", [])
    return " ".join(scopes)