# =============================================================================
# File: app/security/encryption.py  — Encryption Module
# =============================================================================
# Centralized encryption and hashing utilities.
# - Bcrypt for password/secret hashing.
# - Fernet (AES-128-CBC + HMAC) for symmetric encryption.
# - Supports Fernet key rotation via FERNET_KEY_OLD.
# Requires .env: FERNET_KEY (mandatory), FERNET_KEY_OLD (optional).
# =============================================================================

import os
import logging
from typing import Union, Optional, Final  # Union is used

import bcrypt
# from dotenv import load_dotenv # Assuming load_dotenv() is called once at app startup
from cryptography.fernet import Fernet, InvalidToken

_log = logging.getLogger("app.security.encryption")

# --- Fernet Key Configuration ---
# FERNET_KEY must be a URL-safe base64-encoded 32-byte key.
# Generate one with: from cryptography.fernet import Fernet; Fernet.generate_key().decode()
FERNET_KEY_STRING: Final[str] = os.getenv("FERNET_KEY", "")
FERNET_KEY_OLD_STRING: Final[Optional[str]] = os.getenv("FERNET_KEY_OLD")

if not FERNET_KEY_STRING:
    _log.critical("CRITICAL: FERNET_KEY is NOT SET in environment variables. Application cannot run securely.")
    raise RuntimeError("FERNET_KEY is required for symmetric encryption and is not configured.")

try:
    _PRIMARY_FERNET_ENGINE: Final[Fernet] = Fernet(FERNET_KEY_STRING.encode('utf-8'))
except Exception as key_init_err:  # Renamed 'e' to 'key_init_err'
    _log.critical(f"Invalid FERNET_KEY: {key_init_err}. Key must be a URL-safe base64-encoded 32-byte string.")
    raise RuntimeError(f"Invalid FERNET_KEY: {key_init_err}") from key_init_err

_SECONDARY_FERNET_ENGINE: Optional[Fernet] = None
if FERNET_KEY_OLD_STRING:
    try:
        _SECONDARY_FERNET_ENGINE = Fernet(FERNET_KEY_OLD_STRING.encode('utf-8'))
        _log.info("FERNET_KEY_OLD loaded successfully for decryption fallback.")
    except Exception as old_key_err:  # Renamed 'e' to 'old_key_err'
        _log.warning(f"Failed to load FERNET_KEY_OLD (will not be used for fallback): {old_key_err}")
        # _SECONDARY_FERNET_ENGINE remains None, which is fine.


# =============================================================================
# Password & Secret Hashing (bcrypt)
# =============================================================================
def hash_password(password: str) -> str:
    """Hashes a password using bcrypt. Returns the hash as a string."""
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_bytes.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """Validates a plaintext password against its bcrypt hash."""
    if not password or not hashed_password:
        _log.debug("Attempted to verify empty password or hash.")
        return False
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except (ValueError, TypeError) as bcrypt_err:  # Renamed 'e' to 'bcrypt_err'
        _log.warning(f"Password verification error (e.g., malformed hash or salt): {bcrypt_err}")
        return False


# =============================================================================
# Symmetric Encryption (Fernet)
# =============================================================================
def encrypt_data(data: Union[str, bytes]) -> str:
    """Encrypts data using the primary Fernet key. Returns URL-safe base64 string."""
    if isinstance(data, str):
        data_bytes = data.encode('utf-8')
    elif isinstance(data, bytes):
        data_bytes = data
    else:
        raise TypeError("Data to encrypt must be str or bytes.")
    return _PRIMARY_FERNET_ENGINE.encrypt(data_bytes).decode('utf-8')


def decrypt_data(encrypted_token: str) -> Optional[str]:
    """
    Decrypts a Fernet token. Tries current key, then old key if available.
    Returns plaintext string or None on any decryption failure.
    """
    if not encrypted_token:
        _log.debug("Attempted to decrypt an empty token.")
        return None

    token_bytes = encrypted_token.encode('utf-8')

    # Try with the current (primary) key first
    try:
        decrypted_bytes = _PRIMARY_FERNET_ENGINE.decrypt(token_bytes)
        return decrypted_bytes.decode('utf-8')
    except InvalidToken:
        _log.debug("Token decryption failed with primary Fernet key. Trying secondary key if available.")
    except Exception as primary_decrypt_err:  # Renamed 'e'
        _log.error(f"Unexpected error decrypting with primary key: {primary_decrypt_err}", exc_info=True)
        # Fall through to try the old key, as it might be a non-InvalidToken error with a primary but old key might work.

    # Try with the old (secondary) key if it exists
    if _SECONDARY_FERNET_ENGINE:
        try:
            decrypted_bytes = _SECONDARY_FERNET_ENGINE.decrypt(token_bytes)
            _log.info("Token successfully decrypted using the secondary (old) Fernet key.")
            return decrypted_bytes.decode('utf-8')
        except InvalidToken:
            _log.warning(
                "Token decryption failed with both primary and secondary Fernet keys (token is invalid for both).")
            return None
        except Exception as secondary_decrypt_err:  # Renamed 'e'
            _log.error(f"Unexpected error decrypting with secondary key: {secondary_decrypt_err}", exc_info=True)
            return None  # If secondary key also leads to an unexpected error

    # If the primary key failed (InvalidToken), and no secondary key was available, or it also failed
    _log.warning("Token decryption ultimately failed. All configured keys were tried or applicable.")
    return None


# Utility to get the current primary key if needed elsewhere (e.g., for key management display)
def get_primary_fernet_key_string() -> str:
    """Returns the string representation of the primary Fernet key (for informational purposes only)."""
    return FERNET_KEY_STRING