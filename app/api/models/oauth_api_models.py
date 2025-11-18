# =============================================================================
#  File: app/api/models/oauth_api_models.py  –  
# =============================================================================
#  OAuth2 Flow API Models
#  ---------------------------------------------------------------------------
#  • Request/response models for broker OAuth2 authentication flows
#  • PKCE support for enhanced security
#  • Token management & status checking
#  • Error handling for OAuth2 specific scenarios
# =============================================================================

from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
#  OAUTH FLOW MODELS
# =============================================================================
class OAuthStartFlowResponse(BaseModel):
    """Response when initiating an OAuth2 authorization flow."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    authorization_url: str = Field(
        ...,
        description="URL to redirect user for broker authorization"
    )
    broker_connection_id: str = Field(
        ...,
        description="Connection ID for tracking this OAuth session"
    )
    state: Optional[str] = Field(
        None,
        description="OAuth state parameter for CSRF protection"
    )


class OAuthCallbackSuccessResponse(BaseModel):
    """Successful response from the OAuth callback endpoint."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    message: str = Field(
        ...,
        description="Human-readable success message"
    )


class OAuthErrorResponse(BaseModel):
    """Error response for OAuth operations."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    error: str = Field(
        ...,
        description="OAuth error code or type"
    )
    error_description: Optional[str] = Field(
        None,
        description="Detailed error description"
    )


# =============================================================================
#  TOKEN MANAGEMENT MODELS
# =============================================================================
class OAuthTokenRefreshAPIResponse(BaseModel):
    """Response model for refreshing an access token."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    access_token: str = Field(
        ...,
        description="Newly issued access token"
    )
    expires_in: int = Field(
        ...,
        description="Seconds until the new token expires"
    )
    refresh_token: Optional[str] = Field(
        None,
        description="New refresh token if rotated"
    )
    token_type: str = Field(
        "Bearer",
        description="Token type (usually Bearer)"
    )


class OAuthTokenStatusAPIResponse(BaseModel):
    """Response model for checking the validity of an access token."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    valid: bool = Field(
        ...,
        description="True if the access token is currently valid"
    )
    reason: str = Field(
        ...,
        description="Status description (e.g., 'valid', 'expired', 'revoked')"
    )
    expires_at: Optional[str] = Field(
        None,
        description="ISO timestamp when token expires"
    )
    expires_in: Optional[int] = Field(
        None,
        description="Seconds until token expires"
    )
    scopes: Optional[List[str]] = Field(
        None,
        description="OAuth scopes associated with the token"
    )


class OAuthRevokeResponse(BaseModel):
    """Response for a token revocation request."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    status: str = Field(
        ...,
        description="Status of revocation operation"
    )
    message: str = Field(
        ...,
        description="Detailed status message"
    )


# =============================================================================
#  PKCE SUPPORT MODELS
# =============================================================================
class OAuthPKCEParams(BaseModel):
    """PKCE parameters for enhanced OAuth security."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    code_challenge: str = Field(
        ...,
        description="PKCE code challenge (base64 URL-encoded)"
    )
    code_challenge_method: str = Field(
        "S256",
        description="PKCE challenge method (typically S256)"
    )
    code_verifier: Optional[str] = Field(
        None,
        description="PKCE code verifier (stored securely, not sent to client)"
    )


# =============================================================================
#  BROKER-SPECIFIC TOKEN MODELS
# =============================================================================
class BrokerTokenInfo(BaseModel):
    """Detailed token information from a broker."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    access_token: str = Field(
        ...,
        description="OAuth access token"
    )
    refresh_token: Optional[str] = Field(
        None,
        description="OAuth refresh token"
    )
    expires_in: int = Field(
        ...,
        description="Token lifetime in seconds"
    )
    token_type: str = Field(
        "Bearer",
        description="Token type"
    )
    scope: Optional[str] = Field(
        None,
        description="Granted scopes as space-separated string"
    )
    broker_user_id: Optional[str] = Field(
        None,
        description="Broker's user identifier"
    )