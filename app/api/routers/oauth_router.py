# =============================================================================
# File: app/api/routers/oauth_router.py
# REFACTORED: OAuth flow with queries instead of direct Redis access
# =============================================================================

from __future__ import annotations

import asyncio
import uuid
import logging
import base64
import secrets
import json
import urllib.parse
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

# API Models
from app.api.models.oauth_api_models import (
    OAuthRevokeResponse,
    OAuthTokenStatusAPIResponse,
    OAuthTokenRefreshAPIResponse,
)

# Security
from app.security.jwt_auth import get_current_user

# Domain Commands
from app.broker_connection.commands import (
    StartOAuthFlowCommand,
    CompleteOAuthFlowCommand,
    ExchangeOAuthCodeCommand,
    RefreshBrokerTokensCommand,
    RequestBrokerDisconnectCommand,
)

# Domain Queries
from app.broker_connection.queries import (
    GetBrokerConnectionDetailsQuery,
    GetBrokerConnectionByUserBrokerEnvQuery,
    CreateTemporaryOAuthTokenQuery,
    ValidateTemporaryOAuthTokenQuery,
    StoreOAuthStateQuery,
    ValidateOAuthStateQuery,
    CleanupOAuthSessionQuery,
    BrokerConnectionDetails,
)

# Enums
from app.infra.broker_adapters.common.adapter_enums import (
    BrokerConnectionStatusEnum,
)

log = logging.getLogger("tradecore.api.oauth_router")
router = APIRouter()

# Configuration
FRONTEND_BASE_URL = "http://localhost:5173"
OAUTH_TOKEN_TTL = 300  # 5 minutes


# =============================================================================
# API MODELS
# =============================================================================

class OAuthPrepareRequest(BaseModel):
    broker_connection_id: str
    environment: str
    redirect_uri: str
    scope: Optional[str] = None


class OAuthPrepareResponse(BaseModel):
    oauth_url: str
    expires_in: int
    token: str


# =============================================================================
# DEPENDENCY INJECTION
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
# OAUTH FLOW ENDPOINTS
# =============================================================================

@router.post("/prepare", response_model=OAuthPrepareResponse)
async def prepare_oauth_flow(
        payload: OAuthPrepareRequest,
        current_user_id_str: str = Depends(get_current_user),
        command_bus=Depends(get_command_bus),
        query_bus=Depends(get_query_bus),
):
    """
    Step 1: Prepare OAuth flow with authentication.
    Returns a temporary token for starting OAuth.
    REQUIRES JWT AUTHENTICATION.
    """
    user_id = uuid.UUID(current_user_id_str)
    log.info(f"Preparing OAuth flow for user {user_id}")

    try:
        connection_uuid = uuid.UUID(payload.broker_connection_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid broker_connection_id format"
        )

    # Verify connection belongs to user
    conn_query = GetBrokerConnectionDetailsQuery(
        broker_connection_id=connection_uuid,
        user_id=user_id
    )

    connection = await query_bus.query(conn_query)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker connection not found"
        )

    # Create temporary token using query
    token_query = CreateTemporaryOAuthTokenQuery(
        user_id=user_id,
        broker_connection_id=connection_uuid,
        broker_id=connection.broker_id,
        environment=payload.environment,
        redirect_uri=payload.redirect_uri,
        scope=payload.scope,
        ttl_seconds=OAUTH_TOKEN_TTL
    )

    token_result = await query_bus.query(token_query)

    # Build OAuth URL with token
    oauth_url = f"/oauth/{connection.broker_id}/start_flow?token={token_result.token}"

    log.info(f"OAuth prepared for user {user_id}, token expires in {token_result.expires_in}s")

    return OAuthPrepareResponse(
        oauth_url=oauth_url,
        expires_in=token_result.expires_in,
        token=token_result.token
    )


@router.get("/{broker}/start_flow")  # NO response_model - returns redirect!
async def start_oauth_flow_endpoint(
        broker: str,
        token: str = Query(..., description="Temporary OAuth token"),
        command_bus=Depends(get_command_bus),
        query_bus=Depends(get_query_bus),
):
    """
    Step 2: Start OAuth flow with temporary token.
    Returns REDIRECT to broker's OAuth page, not JSON!
    """
    log.info(f"Starting OAuth flow for {broker} with token")

    # Validate token using query
    validate_query = ValidateTemporaryOAuthTokenQuery(
        token=token,
        delete_after_use=True
    )

    token_data = await query_bus.query(validate_query)

    if not token_data:
        # Redirect to frontend with error
        error_url = f"{FRONTEND_BASE_URL}/brokers?oauth_error=true&broker={broker}&error=Invalid+or+expired+token"
        return RedirectResponse(url=error_url, status_code=302)

    # Verify broker matches
    if token_data.broker_id != broker:
        error_url = f"{FRONTEND_BASE_URL}/brokers?oauth_error=true&broker={broker}&error=Token+broker+mismatch"
        return RedirectResponse(url=error_url, status_code=302)

    user_id = token_data.user_id
    broker_connection_id = token_data.connection_id
    environment = token_data.environment
    redirect_uri = token_data.redirect_uri
    scope = token_data.scope

    log.info(f"OAuth token validated for user {user_id}, connection {broker_connection_id}")

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Store state using query
    state_query = StoreOAuthStateQuery(
        user_id=user_id,
        broker_connection_id=broker_connection_id,
        state=state,
        environment=environment,  # Store user-selected environment
        ttl_seconds=600  # 10 minutes
    )

    await query_bus.query(state_query)

    # Start OAuth flow
    command = StartOAuthFlowCommand(
        broker_connection_id=broker_connection_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        scopes=scope.split(",") if scope else None,
        state=state,
        environment=environment,
    )

    try:
        authorization_url = await command_bus.send(command)

        log.info(f"Redirecting to broker OAuth: {authorization_url[:50]}...")

        # REDIRECT TO BROKER'S OAUTH PAGE!
        return RedirectResponse(url=authorization_url, status_code=302)

    except Exception as e:
        log.error(f"Failed to start OAuth flow: {e}", exc_info=True)
        error_msg = urllib.parse.quote(str(e) if len(str(e)) < 100 else "Failed to start OAuth flow")
        error_url = f"{FRONTEND_BASE_URL}/brokers?oauth_error=true&broker={broker}&error={error_msg}"
        return RedirectResponse(url=error_url, status_code=302)


@router.get("/{broker}/callback")
async def oauth_callback(
        broker: str,
        request: Request,
        response: Response,
        command_bus=Depends(get_command_bus),
        query_bus=Depends(get_query_bus),
        code: Optional[str] = Query(None),
        state_from_provider: Optional[str] = Query(None, alias="state"),
        error_from_provider: Optional[str] = Query(None, alias="error"),
        error_description_from_provider: Optional[str] = Query(None, alias="error_description"),
        env: Optional[str] = Query(None),  # Alpaca sends environment
):
    """
    Handle OAuth callback from broker.
    Validates state parameter for security.
    """
    log.info(f"OAuth callback for broker: {broker}")

    # Handle OAuth errors
    if error_from_provider:
        error_desc = error_description_from_provider or "Unknown OAuth error"
        log.error(f"OAuth error from {broker}: {error_from_provider} - {error_desc}")
        error_encoded = urllib.parse.quote(error_desc)
        frontend_url = f"{FRONTEND_BASE_URL}/brokers?oauth_error=true&broker={broker}&error={error_encoded}"
        return RedirectResponse(url=frontend_url, status_code=302)

    if not code or not state_from_provider:
        error_msg = "Missing authorization code or state"
        frontend_url = f"{FRONTEND_BASE_URL}/brokers?oauth_error=true&broker={broker}&error={urllib.parse.quote(error_msg)}"
        return RedirectResponse(url=frontend_url, status_code=302)

    # Validate state using query
    validate_state_query = ValidateOAuthStateQuery(
        state=state_from_provider,
        delete_after_use=True
    )

    state_data = await query_bus.query(validate_state_query)

    if not state_data:
        error_msg = "Invalid or expired OAuth state. Please try again."
        frontend_url = f"{FRONTEND_BASE_URL}/brokers?oauth_error=true&broker={broker}&error={urllib.parse.quote(error_msg)}"
        return RedirectResponse(url=frontend_url, status_code=302)

    # Extract user context from validated state
    user_id = state_data.user_id
    broker_connection_id = state_data.broker_connection_id
    # Retrieve environment from OAuth state (stored during authorization)
    environment = state_data.environment or "paper"  # Default to paper if not specified

    log.info(f"OAuth state validated - User: {user_id}, Connection: {broker_connection_id}")

    # Build redirect URI for token exchange
    redirect_uri = f"http://localhost:5001/oauth/{broker}/callback"

    try:
        # Step 1: Exchange authorization code for tokens
        exchange_command = ExchangeOAuthCodeCommand(
            broker_connection_id=broker_connection_id,
            user_id=user_id,
            broker_id=broker.lower(),
            code=code,
            redirect_uri=redirect_uri,
            state=state_from_provider,
            environment=environment
        )

        log.info(f"Exchanging OAuth code for {broker}")
        oauth_result = await command_bus.send(exchange_command)

        # Step 2: Store tokens and complete OAuth flow
        complete_command = CompleteOAuthFlowCommand(
            broker_connection_id=broker_connection_id,
            user_id=user_id,
            access_token=oauth_result.access_token,
            refresh_token=oauth_result.refresh_token,
            expires_in=oauth_result.expires_in,
            scopes_granted=oauth_result.scopes,
            environment=environment
        )

        await command_bus.send(complete_command)

        log.info(f"OAuth flow completed for {broker}, connection: {broker_connection_id}")

        # CRITICAL FIX: Wait for the connection to be properly established in read model
        # before redirecting to frontend. This prevents race condition where frontend
        # polls status before sync projection completes.
        max_wait_time = 10.0  # Maximum 10 seconds
        check_interval = 0.5  # Check every 500ms
        elapsed_time = 0.0
        connection_ready = False

        log.info(f"Waiting for connection {broker_connection_id} to be marked as connected before redirecting...")

        while elapsed_time < max_wait_time:
            try:
                conn_query = GetBrokerConnectionDetailsQuery(
                    broker_connection_id=broker_connection_id,
                    user_id=user_id
                )
                connection = await query_bus.query(conn_query)

                if connection and (
                    connection.connected or
                    connection.last_connection_status == BrokerConnectionStatusEnum.CONNECTED.value
                ):
                    connection_ready = True
                    log.info(f"Connection {broker_connection_id} is now connected (waited {elapsed_time:.1f}s)")
                    break

            except Exception as e_check:
                log.warning(f"Error checking connection readiness: {e_check}")

            await asyncio.sleep(check_interval)
            elapsed_time += check_interval

        if not connection_ready:
            log.warning(f"Connection {broker_connection_id} not confirmed as connected after {max_wait_time}s, redirecting anyway")

        # Cleanup OAuth session data
        cleanup_query = CleanupOAuthSessionQuery(
            broker_id=broker,
            user_id=user_id
        )
        await query_bus.query(cleanup_query)

    except Exception as e:
        log.error(f"OAuth callback error: {e}", exc_info=True)
        error_msg = str(e) if len(str(e)) < 100 else "Authentication failed"
        frontend_url = f"{FRONTEND_BASE_URL}/brokers?oauth_error=true&broker={broker}&error={urllib.parse.quote(error_msg)}"
        return RedirectResponse(url=frontend_url, status_code=302)

    # Redirect to frontend with success
    frontend_url = f"{FRONTEND_BASE_URL}/brokers?oauth_success=true&broker={broker}&connection_id={broker_connection_id}&environment={environment}"
    return RedirectResponse(url=frontend_url, status_code=302)


# =============================================================================
# TOKEN MANAGEMENT (Authenticated endpoints)
# =============================================================================

@router.post("/{broker}/token/refresh", response_model=OAuthTokenRefreshAPIResponse)
async def refresh_oauth_token_endpoint(
        broker: str,
        environment: str = Query(...),
        current_user_id_str: str = Depends(get_current_user),
        command_bus=Depends(get_command_bus),
        query_bus=Depends(get_query_bus),
):
    """Refresh OAuth access token - REQUIRES AUTHENTICATION"""
    log.info(f"API: /oauth/{broker}/token/refresh for user={current_user_id_str}")
    user_id = uuid.UUID(current_user_id_str)

    # Get connection
    conn_query = GetBrokerConnectionByUserBrokerEnvQuery(
        user_id=user_id,
        broker_id=broker,
        environment=environment
    )

    connection = await query_bus.query(conn_query)

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker connection not found"
        )

    broker_connection_id = connection.id

    # Check if broker supports refresh
    if broker.lower() == "alpaca":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alpaca does not support token refresh (tokens don't expire)"
        )

    # Send refresh command
    command = RefreshBrokerTokensCommand(
        broker_connection_id=broker_connection_id,
        user_id=user_id,
    )

    try:
        result = await command_bus.send(command)

        return OAuthTokenRefreshAPIResponse(
            access_token=result['access_token'],
            expires_at=result['expires_at'],
            expires_in=result['expires_in'],
            scope=result.get('scope'),
        )

    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        log.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/{broker}/revoke", response_model=OAuthRevokeResponse)
async def revoke_oauth_token_endpoint(
        broker: str,
        environment: str = Query(...),
        current_user_id_str: str = Depends(get_current_user),
        command_bus=Depends(get_command_bus),
        query_bus=Depends(get_query_bus),
):
    """Revoke OAuth tokens and disconnect - REQUIRES AUTHENTICATION"""
    log.info(f"API: /oauth/{broker}/revoke for user={current_user_id_str}")
    user_id = uuid.UUID(current_user_id_str)

    # Get connection
    conn_query = GetBrokerConnectionByUserBrokerEnvQuery(
        user_id=user_id,
        broker_id=broker,
        environment=environment
    )

    connection = await query_bus.query(conn_query)

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker connection not found"
        )

    broker_connection_id = connection.id

    # Send disconnect command (handles revoke based on broker)
    command = RequestBrokerDisconnectCommand(
        broker_connection_id=broker_connection_id,
        user_id=user_id,
    )

    try:
        await command_bus.send(command)

        # Different messages for different brokers
        if broker.lower() == "alpaca":
            message = "Alpaca connection disconnected. Tokens cleared locally (Alpaca tokens don't expire)."
        elif broker.lower() == "tradestation":
            message = "TradeStation tokens revoked and connection disconnected."
        else:
            message = f"{broker.capitalize()} connection disconnected."

        return OAuthRevokeResponse(
            status="success",
            message=message,
        )

    except Exception as e:
        log.error(f"Token revocation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token revocation failed"
        )


@router.get("/{broker}/token/status", response_model=OAuthTokenStatusAPIResponse)
async def get_oauth_token_status_endpoint(
        broker: str,
        environment: str = Query(...),
        current_user_id_str: str = Depends(get_current_user),
        query_bus=Depends(get_query_bus),
):
    """Check OAuth token status - REQUIRES AUTHENTICATION"""
    log.debug(f"API: /oauth/{broker}/token/status for user={current_user_id_str}")
    user_id = uuid.UUID(current_user_id_str)

    # Get connection
    conn_query = GetBrokerConnectionByUserBrokerEnvQuery(
        user_id=user_id,
        broker_id=broker,
        environment=environment
    )

    connection = await query_bus.query(conn_query)

    if not connection:
        return OAuthTokenStatusAPIResponse(
            valid=False,
            reason="Broker connection not configured",
            expires_at=None,
            expires_in=None,
            scopes=None
        )

    # Check token status from connection data
    if broker.lower() == "alpaca" and connection.has_api_keys and not connection.has_oauth_tokens:
        return OAuthTokenStatusAPIResponse(
            valid=True,
            reason="Using API key authentication",
            expires_at=None,
            expires_in=None,
            scopes=None
        )

    if not connection.has_oauth_tokens:
        return OAuthTokenStatusAPIResponse(
            valid=False,
            reason="No access token stored",
            expires_at=None,
            expires_in=None,
            scopes=None
        )

    if connection.reauth_required:
        return OAuthTokenStatusAPIResponse(
            valid=False,
            reason="Re-authentication required",
            expires_at=None,
            expires_in=None,
            scopes=None
        )

    # Check expiration
    expires_at = connection.token_expires_at
    if expires_at:
        now = datetime.now(timezone.utc)
        if expires_at < now:
            return OAuthTokenStatusAPIResponse(
                valid=False,
                reason="Access token expired",
                expires_at=None,
                expires_in=None,
                scopes=None
            )

        expires_in = int((expires_at - now).total_seconds())

        return OAuthTokenStatusAPIResponse(
            valid=True,
            reason="Access token valid",
            expires_at=expires_at.isoformat(),
            expires_in=expires_in,
            scopes=connection.metadata.get('scopes') if connection.metadata else None,
        )

    # No expiration info (Alpaca case)
    return OAuthTokenStatusAPIResponse(
        valid=True,
        reason="Access token present (no expiration)",
        expires_at=None,
        expires_in=None,
        scopes=connection.metadata.get('scopes') if connection.metadata else None,
    )


# =============================================================================
# PUBLIC ENDPOINTS (No authentication)
# =============================================================================

@router.get("/{broker}/status/{connection_id}")
async def oauth_status(
        broker: str,
        connection_id: str,
        query_bus=Depends(get_query_bus),
):
    """
    Check OAuth connection status.
    PUBLIC endpoint - used by frontend after redirect.
    """
    try:
        connection_uuid = uuid.UUID(connection_id)

        # Get connection details
        query = GetBrokerConnectionDetailsQuery(
            broker_connection_id=connection_uuid,
            user_id=None  # Admin query - no user restriction
        )

        connection = await query_bus.query(query)

        if not connection:
            return {
                "connected": False,
                "status": "not_found",
                "message": "Connection not found"
            }

        # Check if connected
        is_connected = (
                connection.last_connection_status == BrokerConnectionStatusEnum.CONNECTED.value and
                connection.connected
        )

        return {
            "connected": is_connected,
            "status": connection.last_connection_status or BrokerConnectionStatusEnum.UNKNOWN.value,
            "broker_connection_id": str(connection.id),
            "broker": connection.broker_id,
            "environment": connection.environment,
            "message": connection.last_status_reason or "Connection status unknown"
        }

    except ValueError:
        return {
            "connected": False,
            "status": "invalid_id",
            "message": "Invalid connection ID format"
        }
    except Exception as e:
        log.error(f"Error checking OAuth status: {e}")
        return {
            "connected": False,
            "status": "error",
            "message": "Error checking connection status"
        }


@router.get("/health")
async def oauth_health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "oauth_router",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }