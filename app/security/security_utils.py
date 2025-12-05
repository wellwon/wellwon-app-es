# =============================================================================
# File: app/utils/security_utils.py  — Token & Crypto Utilities
# =============================================================================
# Utility functions for generating, encrypting, and parsing tokens of all kinds:
#   - Webhook tokens (user/account/strategy scoped)
#   - Access tokens (user/environment scoped, expirable)
#   - Refresh tokens (user/environment scoped, long-lived)
# Uses Fernet encryption for all tokens.
# =============================================================================

import logging
from uuid import UUID
import time
from typing import Optional, Tuple
from app.common.enums.enums import CacheTTL

from app.security.encryption import encrypt_data, decrypt_data
from app.utils.uuid_utils import generate_uuid_hex

_log = logging.getLogger("app.utils.security_utils")

# -----------------------------------------------------------------------------
# Access/Refresh Token Helpers
# -----------------------------------------------------------------------------


def generate_access_token(user_id: str, environment: str, lifetime_seconds: int = None) -> str:
    """
    Generates a secure encrypted access token.
    Payload: user_id:environment:issued_at:random

    lifetime_seconds: Overrides default lifetime (in seconds), if provided.
    """
    if lifetime_seconds is None:
        lifetime_seconds = CacheTTL.ACCESS_TOKEN
    issued_at = int(time.time())
    rand = generate_uuid_hex()
    plaintext = f"{user_id}:{environment}:{issued_at}:{rand}:{lifetime_seconds}"
    return encrypt_data(plaintext)

def generate_refresh_token(user_id: str, environment: str) -> str:
    """
    Generates a secure encrypted refresh token.
    Payload: user_id:environment:random
    """
    rand = generate_uuid_hex()
    plaintext = f"{user_id}:{environment}:{rand}"
    return encrypt_data(plaintext)

def parse_access_token(token: str) -> Optional[Tuple[str, str, int, str, int]]:
    """
    Decrypts and parses an access token.
    Returns: (user_id, environment, issued_at, rand, lifetime_seconds)
    """
    try:
        decrypted = decrypt_data(token)
        user_id, environment, issued_at, rand, lifetime = decrypted.split(":", 4)
        return user_id, environment, int(issued_at), rand, int(lifetime)
    except Exception as e:
        _log.error(f"Failed to parse access token: {e}")
        return None

def parse_refresh_token(token: str) -> Optional[Tuple[str, str, str]]:
    """
    Decrypts and parses a refresh token.
    Returns: (user_id, environment, rand)
    """
    try:
        decrypted = decrypt_data(token)
        user_id, environment, rand = decrypted.split(":", 2)
        return user_id, environment, rand
    except Exception as e:
        _log.error(f"Failed to parse refresh token: {e}")
        return None

# =============================================================================
# EOF
# =============================================================================