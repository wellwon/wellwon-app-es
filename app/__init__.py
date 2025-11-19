# =============================================================================
# WellWon Platform Main Package - Dynamic Version Loading
# =============================================================================
"""
WellWon Platform - Main Package

Version is loaded dynamically from pyproject.toml via importlib.metadata.
This follows Python Packaging Guide best practices (2025).

Single Source of Truth: pyproject.toml [project] version = "0.5.1"
"""

from __future__ import annotations

import sys
from typing import Optional

# =============================================================================
# DYNAMIC VERSION LOADING (Industry Best Practice)
# =============================================================================
def _get_version() -> str:
    """
    Get package version dynamically from installed metadata.

    Falls back to reading pyproject.toml if package not installed.
    This is the industry-standard approach per Python Packaging Guide 2025.

    Returns:
        Version string (e.g., "0.5.1")
    """
    # Try installed package metadata first (recommended)
    if sys.version_info >= (3, 8):
        try:
            from importlib.metadata import version, PackageNotFoundError
            return version("wellwon")
        except PackageNotFoundError:
            pass  # Package not installed, try fallback
        except ImportError:
            pass  # importlib.metadata not available

    # Fallback: Read from pyproject.toml
    try:
        # Python 3.11+ has tomllib built-in
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            # Python 3.10 and below need tomli
            import tomli as tomllib  # type: ignore

        from pathlib import Path

        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                return data["project"]["version"]
    except Exception:
        pass  # Fallback failed

    # Last resort fallback (should never happen)
    return "0.1.0-unknown"


__version__: str = _get_version()
__description__: str = "WellWon - Logistics, Customs & Fintech Platform"
__author__: str = "WellWon Team"

# =============================================================================
# EXPORTS
# =============================================================================
__all__ = [
    "__version__",
    "__description__",
    "__author__",
]
