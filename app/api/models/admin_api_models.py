# =============================================================================
# File: app/api/models/admin_api_models.py
# Description: Admin API models (Pydantic v2)
# =============================================================================

from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


# =============================================================================
# Request Models
# =============================================================================

class AdminUserUpdateRequest(BaseModel):
    """Request to update user admin status"""
    active: Optional[bool] = Field(None, description="User active status")
    developer: Optional[bool] = Field(None, description="User developer flag")
    user_type: Optional[str] = Field(None, description="User type (ww_admin, client, etc.)")
    role: Optional[str] = Field(None, description="User role (admin, user, etc.)")


# =============================================================================
# Response Models
# =============================================================================

class AdminUserResponse(BaseModel):
    """User info for admin panel"""
    id: str
    user_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    active: bool
    developer: bool
    created_at: datetime


class AdminUsersListResponse(BaseModel):
    """List of users for admin panel"""
    users: List[AdminUserResponse]
    total: int
