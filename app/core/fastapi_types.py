# app/core/fastapi_types.py
"""
Type definitions for FastAPI with custom state.
This helps IDEs understand the dynamically added state attribute.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import FastAPI as _FastAPI

if TYPE_CHECKING:
    from app.core.app_state import AppState


class FastAPI(_FastAPI):
    """FastAPI with typed state attribute for better IDE support"""
    state: AppState