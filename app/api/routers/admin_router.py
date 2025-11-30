# =============================================================================
# File: app/api/routers/admin_router.py
# Description: Admin API endpoints for user management
# Uses Event Sourcing: Commands -> Events -> WSE -> Frontend
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

# CQRS Commands
from app.user_account.commands import UpdateUserAdminStatusCommand

# Read Repository
from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo

log = logging.getLogger("wellwon.api.admin")

router = APIRouter(prefix="/admin", tags=["Admin"])


# =============================================================================
# Dependency Injection
# =============================================================================

async def get_command_bus(request: Request):
    """Get command bus from application state"""
    if not hasattr(request.app.state, 'command_bus'):
        raise RuntimeError("Command bus not configured")
    return request.app.state.command_bus


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
    command_bus=Depends(get_command_bus),
):
    """
    Update user admin status (active/developer flags).

    Uses Event Sourcing pattern:
    Command -> Event -> EventBus -> WSE -> Frontend (real-time update)
    """
    try:
        # First check if user exists
        user = await UserAccountReadRepo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Create and send command (Event Sourcing pattern)
        cmd = UpdateUserAdminStatusCommand(
            user_id=user_id,
            admin_user_id=uuid.UUID(current_user['user_id']),
            is_active=request.active,
            is_developer=request.developer,
            user_type=request.user_type,
            role=request.role,
        )

        # Send command -> Handler -> Event -> EventBus -> Projector + WSE
        await command_bus.send(cmd)

        log.info(
            f"User {user_id} status update command sent by admin {current_user['user_id']}: "
            f"active={request.active}, developer={request.developer}"
        )

        # Fetch updated user from read model
        # Note: Due to eventual consistency, we fetch again after command
        updated_user = await UserAccountReadRepo.get_by_id(user_id)

        return AdminUserResponse(
            id=str(updated_user.id),
            user_id=str(updated_user.id),
            first_name=updated_user.first_name,
            last_name=updated_user.last_name,
            active=request.active if request.active is not None else updated_user.is_active,
            developer=request.developer if request.developer is not None else updated_user.is_developer,
            created_at=updated_user.created_at,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Failed to update user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )
