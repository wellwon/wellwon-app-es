# app/core/__init__.py
"""
TradeCore Core Module
Central location for shared constants and metadata
"""

# =============================================================================
# VERSION LOADING (Dynamic from pyproject.toml)
# =============================================================================
# Import version from main app package (loads from pyproject.toml)
from app import __version__, __description__, __author__

# Export commonly used items
from app.core.app_state import AppState, get_start_time

__all__ = [
    "__version__",
    "__description__",
    "__author__",
    "AppState",
    "get_start_time"
]