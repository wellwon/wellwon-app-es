# =============================================================================
# File: app/api/routers/admin_router.py
# Description: Admin endpoints for user management - CQRS COMPLIANT
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import Annotated, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel

from app.security.jwt_auth import get_current_user

# CQRS Commands and Queries
from app.user_account.commands import UpdateUserAdminStatusCommand
from app.user_account.queries import GetAllUsersAdminQuery, AdminUserInfo

log = logging.getLogger("wellwon.api.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


# =============================================================================
# Models
# =============================================================================

class AdminUserResponse(BaseModel):
    """User response for admin panel"""
    id: str
    user_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    active: bool = True
    developer: bool = False
    created_at: datetime


class UpdateUserRequest(BaseModel):
    """Request to update user"""
    active: Optional[bool] = None
    developer: Optional[bool] = None


# =============================================================================
# Dependency Injection
# =============================================================================

async def get_command_bus(request: Request):
    """Get command bus from application state"""
    if not hasattr(request.app.state, 'command_bus'):
        raise RuntimeError("Command bus not configured")
    return request.app.state.command_bus


async def get_query_bus(request: Request):
    """Get query bus from application state"""
    if not hasattr(request.app.state, 'query_bus'):
        raise RuntimeError("Query bus not configured")
    return request.app.state.query_bus


# =============================================================================
# Endpoints - CQRS Compliant
# =============================================================================

@router.get("/users", response_model=List[AdminUserResponse])
async def get_all_users(
    current_user: Annotated[dict, Depends(get_current_user)],
    query_bus=Depends(get_query_bus),
):
    """
    Get all users for admin management.
    Only accessible to developers/admins.
    """
    try:
        # Use CQRS query to fetch users
        query = GetAllUsersAdminQuery(include_inactive=True)
        users: List[AdminUserInfo] = await query_bus.query(query)

        return [
            AdminUserResponse(
                id=str(user.id),
                user_id=str(user.id),
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
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
            detail="Failed to get users"
        )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: uuid.UUID,
    request_data: UpdateUserRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    request: Request,
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """
    Update user status or developer flag.
    Only accessible to developers/admins.
    """
    try:
        # Get current user ID (admin performing the action)
        admin_user_id = uuid.UUID(current_user['user_id'])

        if request_data.active is None and request_data.developer is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No updates provided"
            )

        # Use CQRS command to update user
        command = UpdateUserAdminStatusCommand(
            user_id=user_id,
            admin_user_id=admin_user_id,
            is_active=request_data.active,
            is_developer=request_data.developer,
        )
        await command_bus.send(command)

        # Fetch updated user info
        query = GetAllUsersAdminQuery(include_inactive=True, limit=1)
        users: List[AdminUserInfo] = await query_bus.query(query)

        # Find the updated user
        updated_user = None
        for user in users:
            if user.id == user_id:
                updated_user = user
                break

        if not updated_user:
            # Fetch all users to find the updated one
            query = GetAllUsersAdminQuery(include_inactive=True)
            users = await query_bus.query(query)
            for user in users:
                if user.id == user_id:
                    updated_user = user
                    break

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        log.info(f"User {user_id} updated by admin {admin_user_id}")

        return AdminUserResponse(
            id=str(updated_user.id),
            user_id=str(updated_user.id),
            first_name=updated_user.first_name,
            last_name=updated_user.last_name,
            email=updated_user.email,
            active=updated_user.is_active,
            developer=updated_user.is_developer,
            created_at=updated_user.created_at,
        )

    except HTTPException:
        raise
    except ValueError as e:
        log.warning(f"Failed to update user: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Failed to update user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )
