# JWT Token Fingerprinting Migration Guide

**Version:** 1.1
**Date:** 2025-11-25
**Purpose:** Migrate existing JWT infrastructure to support context-based token fingerprinting for theft detection + Redis-resilient refresh tokens.

---

## Overview

This guide explains how to add **context-based token fingerprinting** to an existing JWT authentication system. The fingerprint binds tokens to client context (IP address), allowing detection of token theft when used from a different context.

**Also includes:** Fix for "refresh token error" when Redis restarts or loses data.

### Security Benefits

1. **Token Theft Detection** - Stolen tokens fail validation when used from different IP
2. **Session Hijacking Prevention** - Attackers can't reuse tokens from different context
3. **Audit Trail** - Fingerprint mismatches are logged for security monitoring
4. **Backward Compatible** - Old tokens without fingerprint still work (non-strict mode)
5. **Redis-Resilient** - Sessions survive Redis restart (no more random logouts)

### Trade-offs

- **IP Changes** - Mobile users switching networks may need to re-authenticate
- **VPN Users** - VPN IP changes trigger re-authentication
- **Browser Switching** - Works fine with `ip_only` mode (default)

---

## Implementation Steps

### Step 1: Add Configuration Constants

Add these constants to your `jwt_auth.py`:

```python
import os
from typing import Final

# Token Fingerprinting Configuration
JWT_FINGERPRINT_ENABLED: Final[bool] = os.getenv("JWT_FINGERPRINT_ENABLED", "true").lower() == "true"
JWT_FINGERPRINT_STRICT: Final[bool] = os.getenv("JWT_FINGERPRINT_STRICT", "false").lower() == "true"

# Fingerprint mode: "ip_only" allows browser switching, "full" includes User-Agent
JWT_FINGERPRINT_MODE: Final[str] = os.getenv("JWT_FINGERPRINT_MODE", "ip_only")
```

**Environment Variables:**
- `JWT_FINGERPRINT_ENABLED=true` - Enable fingerprint validation (default: true)
- `JWT_FINGERPRINT_STRICT=false` - Reject tokens without fingerprint (default: false for backward compat)
- `JWT_FINGERPRINT_MODE=ip_only` - Use IP only (allows browser switching) or `full` (IP + User-Agent)

---

### Step 2: Add Fingerprint Generation Functions

Add these functions to `jwt_auth.py`:

```python
import hashlib
from typing import Optional
from fastapi import Request, WebSocket

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
```

---

### Step 3: Update Token Creation

Modify your `create_token_pair()` or `create_access_token()` to accept fingerprint:

```python
async def create_token_pair(
        self,
        subject: Union[str, Dict[str, Any]],
        additional_claims: Optional[Dict[str, Any]] = None,
        fingerprint: Optional[str] = None  # NEW PARAMETER
) -> Tuple[str, str]:
    """
    Create both access and refresh tokens.

    Args:
        subject: User ID or claims dict
        additional_claims: Extra claims for access token
        fingerprint: Client context fingerprint for theft detection

    Returns:
        Tuple of (access_token, refresh_token)
    """
    # ... existing code ...

    # Merge claims
    merged_claims = {**extra_claims, **(additional_claims or {})}

    # Add fingerprint if provided and enabled
    if fingerprint and JWT_FINGERPRINT_ENABLED:
        merged_claims["fgp"] = fingerprint  # 'fgp' = fingerprint claim

    # Create access token with fingerprint
    access_token = self.create_access_token(
        subject,
        additional_claims={
            **merged_claims,
            "family": token_family,
        }
    )

    # Create refresh token with same fingerprint
    refresh_token = self.create_refresh_token(
        user_id,
        token_family,
        additional_claims=merged_claims  # Includes 'fgp' if present
    )

    return access_token, refresh_token
```

---

### Step 4: Update HTTP Authentication Dependency

Modify `get_current_user()` to validate fingerprint:

```python
async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
        request: Request = None,
) -> str:
    """
    FastAPI dependency for HTTP endpoints.
    Returns subject (user_id) or raises HTTPException(401).
    """
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth scheme")

    # Decode token to get payload
    payload = JwtTokenManager.decode_token_payload(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    # SECURITY: Validate fingerprint if enabled
    if JWT_FINGERPRINT_ENABLED and request:
        token_fingerprint = payload.get("fgp")  # fingerprint claim
        request_fingerprint = extract_fingerprint_from_request(request)

        if not validate_fingerprint(token_fingerprint, request_fingerprint, JWT_FINGERPRINT_STRICT):
            log.warning(f"Token fingerprint validation failed for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token context mismatch - please re-authenticate"
            )

    # ... rest of existing validation ...

    return user_id
```

---

### Step 5: Update WebSocket Authentication

Modify `get_current_user_ws()` to validate fingerprint:

```python
async def get_current_user_ws(
        websocket: WebSocket,
        token_from_query: Optional[str] = Query(None, alias="token")
) -> str:
    """
    FastAPI dependency for WebSocket routes.
    """
    # ... existing token extraction code ...

    # Decode token to get payload and validate fingerprint
    payload = JwtTokenManager.decode_token_payload(token)
    if not payload:
        raise WebSocketException(code=WS_1008_POLICY_VIOLATION, reason="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
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

    return user_id
```

---

### Step 6: Update Login Endpoint (Router)

Modify your login endpoint to include fingerprint in tokens:

```python
from app.security.jwt_auth import (
    JwtTokenManager, get_current_user, extract_fingerprint_from_request,
    JWT_FINGERPRINT_ENABLED
)

@router.post("/login", response_model=AuthResponse)
async def login(
        payload: AuthRequest,
        request: Request,
        response: Response,
        # ... dependencies ...
) -> AuthResponse:
    """User login with context fingerprinting."""

    # ... authentication logic ...

    # Generate context fingerprint from request
    context_fingerprint = extract_fingerprint_from_request(request) if JWT_FINGERPRINT_ENABLED else None

    # Build token claims
    token_claims = {
        "username": username,
        "role": role,
        "session_id": session_id,
        # ... other claims ...
    }

    # Add context fingerprint if enabled
    if context_fingerprint:
        token_claims["fgp"] = context_fingerprint

    # Create access token
    access_token = jwt_manager.create_access_token(
        subject=user_id_str,
        additional_claims=token_claims,
    )

    # Create refresh token with same fingerprint
    refresh_claims = {}
    if context_fingerprint:
        refresh_claims["fgp"] = context_fingerprint

    refresh_token = jwt_manager.create_refresh_token(
        subject=user_id_str,
        token_family=token_family_id,
        additional_claims=refresh_claims
    )

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        # ... other fields ...
    )
```

---

## Configuration Options

### Environment Variables

```bash
# Enable/disable fingerprint validation (default: true)
JWT_FINGERPRINT_ENABLED=true

# Strict mode - reject old tokens without fingerprint (default: false)
JWT_FINGERPRINT_STRICT=false

# Fingerprint mode: "ip_only" (default) or "full" (IP + User-Agent)
JWT_FINGERPRINT_MODE=ip_only
```

### Recommended Settings

| Environment | ENABLED | STRICT | MODE | Rationale |
|-------------|---------|--------|------|-----------|
| Development | `true` | `false` | `ip_only` | Test fingerprinting, allow browser switch |
| Staging | `true` | `false` | `ip_only` | Same as production config |
| Production | `true` | `false` | `ip_only` | Security + browser flexibility |
| High Security | `true` | `true` | `full` | Maximum security, no browser switching |

---

## Migration Path

### Phase 1: Deploy with Fingerprinting Disabled
```bash
JWT_FINGERPRINT_ENABLED=false
```
Deploy code changes. No behavior change for users.

### Phase 2: Enable Non-Strict Mode
```bash
JWT_FINGERPRINT_ENABLED=true
JWT_FINGERPRINT_STRICT=false
```
New logins get fingerprinted tokens. Old tokens still work.

### Phase 3: (Optional) Enable Strict Mode After Token Rotation
```bash
JWT_FINGERPRINT_ENABLED=true
JWT_FINGERPRINT_STRICT=true
```
Only enable after all old tokens have expired (30 days default).

---

## Logging and Monitoring

The implementation logs these events:

```python
# Fingerprint mismatch (possible theft)
log.warning(f"Fingerprint mismatch: token={token_fingerprint}, request={request_fingerprint}. Possible token theft.")

# Strict mode rejection
log.warning("Token missing fingerprint in strict mode")

# Validation failure
log.warning(f"Token fingerprint validation failed for user {user_id}")
```

### Alerts to Set Up

1. **High fingerprint mismatch rate** - May indicate attack or VPN users
2. **Sudden spike in re-authentications** - May indicate deployment issue
3. **Geographic anomalies** - Token used from different country

---

## Troubleshooting

### Users Getting Logged Out When Switching Browsers

**Fixed!** Set `JWT_FINGERPRINT_MODE=ip_only` (default). This uses only IP address for fingerprint, so different browsers on the same machine work fine.

If you need stricter security and want to block browser switching, use `JWT_FINGERPRINT_MODE=full`.

### "Refresh Token Error" After Redis Restart

**Problem:** Users get "Invalid refresh token" error randomly, especially after server restarts.

**Root Cause:** Original implementation stored refresh token metadata in Redis. If Redis restarts, TTL expires, or data is lost, the token validation fails even though the JWT is cryptographically valid.

**Fix:** Update `_validate_refresh_token()` to trust JWT signature as fallback:

```python
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
```

**Key Changes:**
1. If token not in Redis → trust JWT signature + re-store token
2. Added blacklist check for explicit revocations
3. On errors → fail open (trust JWT) instead of fail closed

### Mobile Users Getting Logged Out Frequently

IP addresses change frequently on mobile networks.

**Solutions:**
1. Use User-Agent only fingerprinting for mobile apps
2. Implement device ID binding instead of IP
3. Increase access token lifetime for mobile clients

### VPN Users Getting Logged Out

VPN IP changes trigger re-authentication.

**Solutions:**
1. Document this behavior for VPN users
2. Consider disabling fingerprinting for known VPN users
3. Add VPN detection and skip fingerprint validation

---

## Security Considerations

### What Fingerprinting Protects Against

- Token stolen via XSS attack
- Token intercepted by man-in-the-middle
- Token leaked in logs or error messages
- Token stolen from browser storage

### What Fingerprinting Does NOT Protect Against

- Attacker on same network/IP
- Attacker with same browser (spoofed User-Agent)
- Attacker with full browser session takeover
- Insider threats

### Defense in Depth

Fingerprinting should be ONE layer of security:
1. Short access token lifetime (15 min)
2. Refresh token rotation
3. Secure cookie storage
4. HTTPS only
5. Rate limiting
6. IP blocklisting

---

## Complete Code Example

See files:
- `app/security/jwt_auth.py` - Core JWT implementation with fingerprinting
- `app/api/routers/user_account_router.py` - Login endpoint with fingerprint injection

---

## References

- [Auth0 Token Best Practices](https://auth0.com/docs/secure/tokens/token-best-practices)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [RFC 9700 OAuth 2.0 Security BCP](https://datatracker.ietf.org/doc/rfc9700/)

---

**Document Version:** 1.0
**Last Updated:** 2025-11-25
