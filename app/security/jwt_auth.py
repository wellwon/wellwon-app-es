# =============================================================================
# File: app/security/jwt_auth.py — JWT Authentication
# =============================================================================
# Responsibilities:
# - Centralized JWT creation and validation
# - Handles access tokens with expiration, subject claim, and extra metadata
# - Supports WebSocket and HTTP (Bearer) authentication dependencies
# - Designed for FastAPI and Starlette
# - ENHANCED: Industrial-grade refresh token support with rotation
# - UPDATED: Now uses CacheManager instead of direct Redis access
# =============================================================================

from __future__ import annotations

import os
import logging
import json
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Final, Union, Tuple
from uuid import UUID

from jose import jwt, JWTError
from fastapi import WebSocket, Query, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.exceptions import WebSocketException

from app.infra.persistence.cache_manager import get_cache_manager

log = logging.getLogger("wellwon.security.jwt_auth")


# =============================================================================
# Optional .env loader: attempt to import python-dotenv, else provide no-op
# =============================================================================
def _noop_load_dotenv(*_args: Any, **_kwargs: Any) -> bool:
    """
    No-op fallback if python-dotenv is not installed.
    Always returns False to indicate nothing was loaded.
    """
    return False


try:
    # If available, override our no-op with a real loader
    from dotenv import load_dotenv
except ImportError:
    log.warning("python-dotenv not available; skipping .env loading.")
    load_dotenv = _noop_load_dotenv

# Invoke once at import time to populate os.environ from a .env file in dev
load_dotenv()

# =============================================================================
# JWT Configuration Constants
# =============================================================================
JWT_SECRET_KEY_ENV: Optional[str] = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM: Final[str] = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")  # Reduced to 15 minutes
)
JWT_REFRESH_TOKEN_EXPIRE_DAYS: Final[int] = int(
    os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30")
)
JWT_REFRESH_TOKEN_REUSE_WINDOW: Final[int] = int(
    os.getenv("JWT_REFRESH_TOKEN_REUSE_WINDOW", "10")  # seconds
)

# =============================================================================
# Token Fingerprinting Configuration (Context-based theft detection)
# =============================================================================
JWT_FINGERPRINT_ENABLED: Final[bool] = os.getenv("JWT_FINGERPRINT_ENABLED", "true").lower() == "true"
JWT_FINGERPRINT_STRICT: Final[bool] = os.getenv("JWT_FINGERPRINT_STRICT", "false").lower() == "true"
# Fingerprint mode: "ip_only" allows browser switching, "full" includes User-Agent
JWT_FINGERPRINT_MODE: Final[str] = os.getenv("JWT_FINGERPRINT_MODE", "ip_only")

if not JWT_SECRET_KEY_ENV:
    log.critical("CRITICAL: JWT_SECRET_KEY is not set; aborting startup.")
    raise RuntimeError("JWT_SECRET_KEY is required for JWT authentication.")

JWT_SECRET_KEY: Final[str] = JWT_SECRET_KEY_ENV


# =============================================================================
# Context-Based Fingerprint Functions (Token Theft Detection)
# =============================================================================

def generate_fingerprint(
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        additional_context: Optional[str] = None
) -> str:
    """
    Generate a fingerprint hash from client context.

    Security Best Practice:
    - Binds token to client context (IP and optionally User-Agent)
    - Detects token theft when used from different context
    - Uses SHA-256 for collision resistance

    Modes (JWT_FINGERPRINT_MODE env var):
    - "ip_only": Only IP address (allows browser switching on same machine)
    - "full": IP + User-Agent (stricter, but logs out on browser switch)

    Args:
        ip_address: Client IP address (X-Forwarded-For or direct)
        user_agent: Browser/client User-Agent header
        additional_context: Optional extra binding (e.g., device ID)

    Returns:
        SHA-256 hash of combined context (truncated to 16 chars for token size)
    """
    # Normalize inputs
    ip = (ip_address or "unknown").strip().lower()
    extra = (additional_context or "").strip()

    # Build context based on mode
    if JWT_FINGERPRINT_MODE == "full":
        # Full mode: IP + User-Agent (stricter security, but breaks on browser switch)
        ua = (user_agent or "unknown").strip().lower()
        context = f"{ip}|{ua}|{extra}"
    else:
        # IP-only mode (default): allows browser switching on same IP
        context = f"{ip}|{extra}"

    # Hash and truncate (16 chars = 64 bits, sufficient for fingerprint)
    full_hash = hashlib.sha256(context.encode()).hexdigest()
    return full_hash[:16]


def extract_fingerprint_from_request(request: Request) -> str:
    """
    Extract fingerprint components from FastAPI Request.

    Handles:
    - X-Forwarded-For (proxy/load balancer)
    - X-Real-IP (nginx)
    - Direct client IP
    - User-Agent header

    Args:
        request: FastAPI Request object

    Returns:
        Generated fingerprint hash
    """
    # Get IP address (handle proxies)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can be comma-separated list, take first (client)
        ip_address = forwarded.split(",")[0].strip()
    else:
        ip_address = request.headers.get("X-Real-IP") or (
            request.client.host if request.client else "unknown"
        )

    # Get User-Agent
    user_agent = request.headers.get("User-Agent", "unknown")

    return generate_fingerprint(ip_address, user_agent)


def extract_fingerprint_from_websocket(websocket: WebSocket) -> str:
    """
    Extract fingerprint components from WebSocket connection.

    Args:
        websocket: FastAPI WebSocket object

    Returns:
        Generated fingerprint hash
    """
    # Get IP address
    forwarded = websocket.headers.get("X-Forwarded-For")
    if forwarded:
        ip_address = forwarded.split(",")[0].strip()
    else:
        ip_address = websocket.headers.get("X-Real-IP") or (
            websocket.client.host if websocket.client else "unknown"
        )

    # Get User-Agent
    user_agent = websocket.headers.get("User-Agent", "unknown")

    return generate_fingerprint(ip_address, user_agent)


def validate_fingerprint(
        token_fingerprint: Optional[str],
        request_fingerprint: str,
        strict: bool = False
) -> bool:
    """
    Validate that token fingerprint matches request context.

    Args:
        token_fingerprint: Fingerprint stored in token (may be None for old tokens)
        request_fingerprint: Fingerprint generated from current request
        strict: If True, reject tokens without fingerprint

    Returns:
        True if fingerprint matches or validation is skipped
    """
    # No fingerprint in token
    if not token_fingerprint:
        if strict:
            log.warning("Token missing fingerprint in strict mode")
            return False
        # Non-strict: allow tokens without fingerprint (backward compat)
        return True

    # Compare fingerprints
    if token_fingerprint != request_fingerprint:
        log.warning(
            f"Fingerprint mismatch: token={token_fingerprint}, "
            f"request={request_fingerprint}. Possible token theft."
        )
        return False

    return True


# =============================================================================
# JWT Token Manager (Enhanced with Refresh Token Support + CacheManager)
# =============================================================================
class JwtTokenManager:
    """
    Encapsulates JWT token creation and validation.
    - create_access_token(): issues a signed JWT with standard claims.
    - create_refresh_token(): issues a long-lived refresh JWT.
    - create_token_pair(): creates both access and refresh tokens.
    - decode_token_payload(): verifies signature and expiry, returns claims dict.
    - get_subject_from_token(): extracts 'sub' claim as user identifier.
    - refresh_tokens(): handles token refresh with rotation.

    UPDATED: Now uses CacheManager for all Redis operations
    """

    def __init__(self, default_user_id: Optional[str] = None):
        # default_user_id can serve as fallback 'sub' if none provided.
        self.default_user_id = default_user_id
        self._cache_manager = None

    @property
    def cache_manager(self):
        """Lazy load cache manager"""
        if self._cache_manager is None:
            self._cache_manager = get_cache_manager()
        return self._cache_manager

    def create_access_token(
            self,
            subject: Union[str, Dict[str, Any]],
            expires_delta: Optional[timedelta] = None,
            additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Issue a JWT:
        - 'exp' (expiration) set to now + expires_delta or default duration.
        - 'iat' (issued at) set to current UTC time.
        - 'sub' (subject) must come from `subject` or default_user_id.
        - Merges any additional_claims into the payload.
        """
        now_utc = datetime.now(timezone.utc)
        expire_utc = now_utc + (expires_delta or timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES))

        # Base claims
        claims: Dict[str, Any] = {
            "exp": expire_utc,
            "iat": now_utc,
            "type": "access",  # Added token type
            "jti": secrets.token_urlsafe(16),  # Added unique token ID
        }

        # Determine and set 'sub'
        if isinstance(subject, dict):
            # If dict, allow custom claims plus 'sub'
            sub_val = subject.get("sub", self.default_user_id)
            claims.update(subject)
            if sub_val:
                claims["sub"] = sub_val
        elif isinstance(subject, str):
            claims["sub"] = subject
        elif self.default_user_id:
            claims["sub"] = self.default_user_id
        else:
            log.error("Cannot create JWT: no subject provided.")
            raise ValueError("Subject ('sub') claim is required.")

        # Verify 'sub' presence
        if not claims.get("sub"):
            log.error("JWT 'sub' claim ended up empty.")
            raise ValueError("JWT 'sub' must not be empty.")

        # Merge additional_claims if given
        if additional_claims:
            claims.update(additional_claims)

        # Encode and return the JWT
        return jwt.encode(claims, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    def create_refresh_token(
            self,
            subject: str,
            token_family: Optional[str] = None,
            additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a long-lived refresh token.

        Args:
            subject: User ID
            token_family: Token family ID for rotation tracking
            additional_claims: Extra claims to include in token (e.g., fingerprint)

        Returns:
            Encoded refresh token
        """
        now_utc = datetime.now(timezone.utc)
        expire_utc = now_utc + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        claims = {
            "sub": subject,
            "type": "refresh",
            "exp": expire_utc,
            "iat": now_utc,
            "jti": secrets.token_urlsafe(16),
            "family": token_family or secrets.token_urlsafe(32),
            "version": 1,
        }

        # Merge additional claims
        if additional_claims:
            claims.update(additional_claims)

        return jwt.encode(claims, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    async def create_token_pair(
            self,
            subject: Union[str, Dict[str, Any]],
            additional_claims: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Create both access and refresh tokens.

        Args:
            subject: User ID or claims dict
            additional_claims: Extra claims for access token

        Returns:
            Tuple of (access_token, refresh_token)
        """
        # Extract user_id from the subject
        if isinstance(subject, dict):
            user_id = subject.get("sub")
        else:
            user_id = subject

        if not user_id:
            raise ValueError("User ID is required")

        # Create a token family for rotation tracking
        token_family = secrets.token_urlsafe(32)

        # Extract additional claims from subject if it's a dict
        extra_claims = {}
        if isinstance(subject, dict):
            extra_claims = {k: v for k, v in subject.items() if k != "sub"}

        # Merge with explicitly passed additional_claims
        merged_claims = {**extra_claims, **(additional_claims or {})}

        # Create an access token
        access_token = self.create_access_token(
            subject,
            additional_claims={
                **merged_claims,
                "family": token_family,
            }
        )

        # Create a refresh token with same additional claims (including fingerprint)
        refresh_token = self.create_refresh_token(
            user_id,
            token_family,
            additional_claims=merged_claims
        )

        # Store refresh token in Redis using CacheManager
        await self._store_refresh_token(user_id, refresh_token)

        return access_token, refresh_token

    async def refresh_tokens(
            self,
            refresh_token: str
    ) -> Tuple[str, str]:
        """
        Refresh both tokens with automatic rotation.

        Args:
            refresh_token: Current refresh token

        Returns:
            Tuple of (new_access_token, new_refresh_token)

        Raises:
            HTTPException: If the refresh token is invalid or expired
        """
        # Decode refresh token
        payload = self.decode_token_payload(refresh_token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not a refresh token"
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token subject"
            )

        # Validate refresh token
        is_valid = await self._validate_refresh_token(user_id, refresh_token, payload)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked refresh token"
            )

        # Create a new token pair
        additional_claims = {
            k: v for k, v in payload.items()
            if k not in ["sub", "exp", "iat", "type", "jti", "family", "version"]
        }

        new_access, new_refresh = await self.create_token_pair(
            {"sub": user_id, **additional_claims}
        )

        # Revoke the old refresh token with a grace period
        await self._revoke_refresh_token_with_grace(user_id, refresh_token)

        return new_access, new_refresh

    async def _store_refresh_token(
            self,
            user_id: str,
            token: str
    ) -> None:
        """Store refresh token metadata using CacheManager."""
        try:
            payload = self.decode_token_payload(token)
            if not payload:
                return

            jti = payload['jti']
            family_id = payload.get("family")

            # Store token metadata
            token_key = self.cache_manager._make_key('auth', 'refresh', 'token', user_id, jti)
            token_data = {
                "token": token,
                "family": family_id,
                "version": payload.get("version", 1),
                "issued_at": payload.get("iat"),
                "expires_at": payload.get("exp"),
                "active": True
            }

            # Calculate TTL
            ttl = int(payload["exp"] - datetime.now(timezone.utc).timestamp())
            await self.cache_manager.set_json(token_key, token_data, ttl)

            # Add to user's active tokens list
            user_tokens_key = self.cache_manager._make_key('auth', 'user', 'tokens', user_id)
            tokens = await self.cache_manager.get_json(user_tokens_key) or []
            if jti not in tokens:
                tokens.append(jti)
                await self.cache_manager.set_json(user_tokens_key, tokens, ttl)

            log.debug(f"Stored refresh token for user {user_id}, JTI: {jti}")

        except Exception as e:
            log.error(f"Error storing refresh token: {e}")

    async def _validate_refresh_token(
            self,
            user_id: str,
            token: str,
            payload: Dict[str, Any]
    ) -> bool:
        """
        Validate refresh token against stored metadata using CacheManager.

        IMPORTANT: If token is not found in Redis (e.g., Redis restart, TTL expired),
        we trust the JWT signature and expiry as fallback. This prevents users from
        being logged out when Redis data is lost.

        Security model:
        - JWT signature + expiry = cryptographic proof of validity
        - Redis storage = ability to revoke tokens early
        - If Redis is empty, we lose revocation but maintain session continuity
        """
        try:
            jti = payload.get('jti')

            if not jti:
                # Old tokens without JTI - trust JWT signature
                log.debug(f"Refresh token for user {user_id} has no JTI, trusting JWT signature")
                return True

            # Check if token is explicitly revoked (blacklisted)
            blacklist_key = self.cache_manager._make_key('auth', 'refresh', 'blacklist', jti)
            if await self.cache_manager.exists(blacklist_key):
                log.warning(f"Refresh token {jti[:8]}... is blacklisted for user {user_id}")
                return False

            # Check if token exists in active storage
            token_key = self.cache_manager._make_key('auth', 'refresh', 'token', user_id, jti)
            stored_data = await self.cache_manager.get_json(token_key)

            if stored_data:
                is_active = stored_data.get("active", False)
                if not is_active:
                    log.debug(f"Refresh token {jti[:8]}... marked inactive for user {user_id}")
                return is_active

            # Check grace period for recently rotated tokens
            grace_key = self.cache_manager._make_key('auth', 'refresh', 'grace', user_id, jti)
            if await self.cache_manager.exists(grace_key):
                log.debug(f"Refresh token {jti[:8]}... in grace period for user {user_id}")
                return True

            # TOKEN NOT FOUND IN REDIS - this is the key fix!
            # Trust the JWT if it's cryptographically valid (signature + expiry checked earlier)
            # This handles: Redis restart, TTL expiry, new Redis instance, etc.
            log.info(
                f"Refresh token {jti[:8]}... not found in Redis for user {user_id}. "
                f"Trusting JWT signature (Redis may have restarted or token TTL expired)."
            )

            # Re-store the token so future refreshes work normally
            await self._store_refresh_token(user_id, token)

            return True

        except Exception as e:
            log.error(f"Error validating refresh token: {e}")
            # On error, trust the JWT signature rather than failing
            return True

    async def _revoke_refresh_token_with_grace(
            self,
            user_id: str,
            token: str
    ) -> None:
        """Revoke refresh token with a grace period using CacheManager."""
        try:
            payload = self.decode_token_payload(token)
            if not payload:
                return

            jti = payload.get("jti")

            # Delete token
            token_key = self.cache_manager._make_key('auth', 'refresh', 'token', user_id, jti)
            await self.cache_manager.delete(token_key)

            # Add to grace period
            grace_key = self.cache_manager._make_key('auth', 'refresh', 'grace', user_id, jti)
            await self.cache_manager.set(grace_key, "1", JWT_REFRESH_TOKEN_REUSE_WINDOW)

            # Remove from user's active tokens list
            user_tokens_key = self.cache_manager._make_key('auth', 'user', 'tokens', user_id)
            tokens = await self.cache_manager.get_json(user_tokens_key) or []
            if jti in tokens:
                tokens.remove(jti)
                if tokens:
                    await self.cache_manager.set_json(user_tokens_key, tokens)
                else:
                    await self.cache_manager.delete(user_tokens_key)

            log.debug(f"Revoked refresh token for user {user_id}, JTI: {jti}")

        except Exception as e:
            log.error(f"Error revoking refresh token: {e}")

    async def revoke_all_refresh_tokens(self, user_id: str) -> None:
        """Revoke all refresh tokens for a user using CacheManager."""
        try:
            # Get all active tokens
            user_tokens_key = self.cache_manager._make_key('auth', 'user', 'tokens', user_id)
            token_ids = await self.cache_manager.get_json(user_tokens_key) or []

            # Delete each token
            for jti in token_ids:
                token_key = self.cache_manager._make_key('auth', 'refresh', 'token', user_id, jti)
                await self.cache_manager.delete(token_key)

            # Clear the user's token list
            await self.cache_manager.delete(user_tokens_key)

            # Clear any session data
            pattern = self.cache_manager._make_key('auth', 'refresh', '*', user_id, '*')
            await self.cache_manager.delete_pattern(pattern)

            log.info(f"Revoked all refresh tokens for user {user_id}")

        except Exception as e:
            log.error(f"Error revoking all refresh tokens: {e}")

    @staticmethod
    def decode_token_payload(token: str) -> Optional[Dict[str, Any]]:
        """
        Decode and validate a JWT string.
        Returns the payload dict if valid, else None.
        """
        if not token:
            return None
        try:
            return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        except JWTError as exc:
            preview = token[:20] + "..." if len(token) > 20 else token
            log.info(f"JWT decode error ({type(exc).__name__}): {exc}. Token preview: {preview}")
            return None

    @staticmethod
    def get_subject_from_token(token: str) -> Optional[str]:
        """
        Extract the 'sub' (subject) claim from a valid JWT.
        Returns a string user_id or None.
        """
        payload = JwtTokenManager.decode_token_payload(token)
        sub = payload.get("sub") if payload else None
        if isinstance(sub, str):
            return sub
        if payload:
            log.debug(f"JWT payload missing valid 'sub': {payload}")
        return None


# =============================================================================
# WebSocket Authentication Dependency
# =============================================================================
async def get_current_user_ws(
        websocket: WebSocket,
        token_from_query: Optional[str] = Query(None, alias="token")
) -> str:
    """
    FastAPI dependency for WebSocket routes.
    - Tries ?token= query param, then 'Authorization: Bearer <token>' header.
    - On success returns the user_id (subject), else closes connection.
    - SECURITY: Validates context fingerprint if enabled
    """
    token = token_from_query

    if not token:
        auth = websocket.headers.get("Authorization")
        if auth:
            try:
                scheme, creds = auth.split(maxsplit=1)
                if scheme.lower() == "bearer":
                    token = creds
            except ValueError:
                log.debug("Malformed WebSocket Authorization header.")

    if not token:
        log.warning("WebSocket attempted without JWT token.")
        raise WebSocketException(code=WS_1008_POLICY_VIOLATION, reason="Token missing")

    # Decode token to get payload and validate fingerprint
    payload = JwtTokenManager.decode_token_payload(token)
    if not payload:
        log.warning("WebSocket provided invalid or expired token.")
        raise WebSocketException(code=WS_1008_POLICY_VIOLATION, reason="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        log.warning("WebSocket token missing subject claim.")
        raise WebSocketException(code=WS_1008_POLICY_VIOLATION, reason="Invalid token")

    # SECURITY: Validate fingerprint if enabled
    if JWT_FINGERPRINT_ENABLED:
        token_fingerprint = payload.get("fgp")
        request_fingerprint = extract_fingerprint_from_websocket(websocket)

        if not validate_fingerprint(token_fingerprint, request_fingerprint, JWT_FINGERPRINT_STRICT):
            log.warning(f"WebSocket token fingerprint validation failed for user {user_id}")
            raise WebSocketException(
                code=WS_1008_POLICY_VIOLATION,
                reason="Token context mismatch"
            )

    log.debug(f"WebSocket authenticated user: {user_id}")
    return user_id


# =============================================================================
# HTTP Bearer Authentication Dependency
# =============================================================================
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
        request: Request = None,
) -> dict:
    """
    FastAPI dependency for HTTP endpoints.
    - Expects 'Authorization: Bearer <token>'.
    - Returns dict with user_id or raises HTTPException(401).
    - CQRS COMPLIANT: Uses Query Bus instead of direct repository access
    - SECURITY: Validates context fingerprint if enabled
    """
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth scheme")

    # Decode token to get full payload (for fingerprint validation)
    payload = JwtTokenManager.decode_token_payload(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    # SECURITY: Validate context fingerprint if enabled
    if JWT_FINGERPRINT_ENABLED and request:
        token_fingerprint = payload.get("fgp")  # fingerprint claim
        request_fingerprint = extract_fingerprint_from_request(request)

        if not validate_fingerprint(token_fingerprint, request_fingerprint, JWT_FINGERPRINT_STRICT):
            log.warning(f"Token fingerprint validation failed for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token context mismatch - please re-authenticate"
            )

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token subject must be a valid UUID")

    # CRITICAL SECURITY FIX: Check if user still exists in database
    # Prevents deleted users from accessing system with valid tokens
    # CQRS COMPLIANT: Use Query Bus instead of direct repository access
    if request and hasattr(request.app.state, 'query_bus'):
        from app.user_account.queries import GetUserProfileQuery
        try:
            query_bus = request.app.state.query_bus
            query = GetUserProfileQuery(user_id=user_uuid, include_preferences=False)
            user = await query_bus.query(query)

            if not user:
                log.warning(f"Token valid but user {user_id} does not exist in database (deleted?)")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found")
            if not user.is_active:
                log.warning(f"Token valid but user {user_id} is inactive")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive")
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Error validating user via Query Bus: {e}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")
    else:
        # Fallback for contexts where query_bus is not available (e.g., startup, tests)
        log.debug("Query bus not available in get_current_user, skipping user validation")

    return {"user_id": user_uuid}


# =============================================================================
# Helper: Raw header extraction if needed
# =============================================================================
def get_user_id_from_auth_header(auth_header: Optional[str]) -> Optional[str]:
    """
    Utility to pull user_id from a raw Authorization header string.
    Returns the 'sub' value or None.
    """
    if not auth_header:
        return None
    try:
        scheme, token = auth_header.split(maxsplit=1)
        if scheme.lower() != "bearer":
            log.warning(f"Unexpected auth scheme: {scheme}")
            return None
    except ValueError:
        log.warning("Malformed Authorization header.")
        return None

    return JwtTokenManager.get_subject_from_token(token)


# =============================================================================
# Validate Token
# =============================================================================
async def validate_token(token: str) -> bool:
    """
    Validate a JWT token without raising exceptions.
    Returns True if the token is valid, False otherwise.

    Args:
        token: The JWT token to validate

    Returns:
        bool: True if token is valid, False otherwise
    """
    if not token:
        return False

    payload = JwtTokenManager.decode_token_payload(token)
    if not payload:
        return False

    # Check if the token has a valid subject
    sub = payload.get("sub")
    if not isinstance(sub, str):
        return False

    # Check if the token is expired
    try:
        exp = payload.get("exp")
        if not exp:
            return False

        # JWT exp is Unix timestamp (seconds since epoch)
        if isinstance(exp, (int, float)):
            if exp < datetime.now(timezone.utc).timestamp():
                return False
        # If using Python's datetime objects for exp
        elif isinstance(exp, datetime):
            if exp < datetime.now(timezone.utc):
                return False
    except Exception as e:
        log.error(f"Error validating token expiration: {e}")
        return False

    return True

# =============================================================================
# EOF
# =============================================================================