# =============================================================================
# File: app/api/routers/admin_router.py
# Description: Admin API endpoints for user management
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request

from app.security.jwt_auth import get_current_user

# API Models
from app.api.models.admin_api_models import (
    AdminUserUpdateRequest,
    AdminUserResponse,
)

# Read Repository
from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo

log = logging.getLogger("wellwon.api.admin")

router = APIRouter(prefix="/admin", tags=["Admin"])


# =============================================================================
# User Management Endpoints
# =============================================================================

@router.get("/users", response_model=List[AdminUserResponse])
async def get_all_users(
    current_user: Annotated[dict, Depends(get_current_user)],
    include_inactive: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Get all users for admin management panel.

    Returns list of users with their active/developer status.
    """
    try:
        users = await UserAccountReadRepo.get_all_users_for_admin(
            include_inactive=include_inactive,
            limit=limit,
            offset=offset,
        )

        return [
            AdminUserResponse(
                id=str(user.id),
                user_id=str(user.id),
                first_name=user.first_name,
                last_name=user.last_name,
                active=user.is_active,
                developer=user.is_developer,
                created_at=user.created_at,
            )
            for user in users
        ]

    except Exception as e:
        log.error(f"Failed to get users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user_status(
    user_id: uuid.UUID,
    request: AdminUserUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Update user admin status (active/developer flags).
    """
    try:
        # Update user status
        updated_user = await UserAccountReadRepo.update_user_admin_status(
            user_id=user_id,
            is_active=request.active,
            is_developer=request.developer,
        )

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        log.info(f"User {user_id} updated by admin {current_user['user_id']}: active={request.active}, developer={request.developer}")

        return AdminUserResponse(
            id=str(updated_user.id),
            user_id=str(updated_user.id),
            first_name=updated_user.first_name,
            last_name=updated_user.last_name,
            active=updated_user.is_active,
            developer=updated_user.is_developer,
            created_at=updated_user.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to update user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )
