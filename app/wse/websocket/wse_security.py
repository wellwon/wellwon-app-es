# =============================================================================
# File: app/api/websocket/ws_security.py
# Description: Security manager for WebSocket connections using common security modules
# =============================================================================

import json
import secrets
import time
import hashlib
from typing import Optional, Dict, Any, Union
import logging

from app.security.encryption import encrypt_data, decrypt_data
from app.security.jwt_auth import JwtTokenManager
from app.security.security_utils import generate_access_token, parse_access_token

log = logging.getLogger("tradecore.wse_security")


class SecurityManager:
    """Handles WebSocket message encryption and signing using common security modules"""

    def __init__(self):
        self.encryption_enabled = False
        self.message_signing_enabled = False
        self.cipher_suite: Optional[str] = "Fernet"  # Using existing Fernet encryption
        self.key_rotation_interval: Optional[int] = 3600  # seconds
        self.last_key_rotation: Optional[float] = None

        # Use JWT manager for token operations
        self.jwt_manager = JwtTokenManager()

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize security with configuration"""
        self.encryption_enabled = config.get('encryption_enabled', False)
        self.message_signing_enabled = config.get('message_signing_enabled', False)

        if self.encryption_enabled:
            log.info("Encryption initialized using Fernet from common security module")

        if self.message_signing_enabled:
            log.info("Message signing initialized using JWT signatures")

    async def encrypt_message(self, data: Union[str, bytes, dict]) -> Optional[str]:
        """Encrypt message using Fernet encryption from common module"""
        if not self.encryption_enabled:
            return None

        try:
            # Convert to string if dict
            if isinstance(data, dict):
                data = json.dumps(data, sort_keys=True)

            # Use the common encrypt_data function which returns base64 string
            encrypted = encrypt_data(data)

            return encrypted

        except Exception as e:
            log.error(f"Encryption failed: {e}")
            return None

    async def decrypt_message(self, encrypted_data: str) -> Optional[Union[str, Dict[str, Any]]]:
        """Decrypt message using Fernet decryption from common module"""
        if not self.encryption_enabled:
            return None

        try:
            # Use the common decrypt_data function
            decrypted = decrypt_data(encrypted_data)

            if decrypted:
                # Try to parse as JSON if possible
                try:
                    return json.loads(decrypted)
                except json.JSONDecodeError:
                    return decrypted

            return None

        except Exception as e:
            log.error(f"Decryption failed: {e}")
            return None

    async def sign_message(self, data: Union[str, bytes, dict]) -> Optional[str]:
        """
        Sign message using JWT for integrity verification.

        CRITICAL FIX (Nov 11, 2025): Changed to return only signature string.
        - Previous: Returned {payload: dict, signature: str} causing circular reference
        - Now: Returns only JWT signature string with payload hash
        - Benefit: Eliminates circular reference, reduces message size

        Returns:
            JWT signature string, or None if signing disabled/failed
        """
        if not self.message_signing_enabled:
            return None

        try:
            # Serialize payload to JSON string for hashing
            if isinstance(data, dict):
                # Use sorted keys for consistent hashing
                payload_str = json.dumps(data, sort_keys=True, default=str)
            elif isinstance(data, bytes):
                payload_str = data.decode('utf-8')
            else:
                payload_str = str(data)

            # Create hash of payload for integrity verification
            payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()

            # Sign the hash with metadata (not the full payload)
            signature_token = self.jwt_manager.create_access_token(
                subject="ws_message",
                expires_delta=None,  # No expiration for message signatures
                additional_claims={
                    "hash": payload_hash,
                    "signed_at": time.time(),
                    "nonce": secrets.token_hex(8)
                }
            )

            # Return ONLY the signature string (not payload+signature dict)
            return signature_token

        except Exception as e:
            log.error(f"Message signing failed: {e}")
            return None

    async def verify_signature(self, signed_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Verify message signature using JWT validation"""
        if not self.message_signing_enabled:
            return signed_data.get("payload", signed_data)

        try:
            signature = signed_data.get("signature")
            if not signature:
                log.warning("No signature found in message")
                return None

            # Verify JWT signature
            decoded = self.jwt_manager.decode_token_payload(signature)
            if not decoded:
                log.warning("Invalid signature")
                return None

            # Return the original payload
            return decoded

        except Exception as e:
            log.error(f"Signature verification failed: {e}")
            return None

    async def create_session_token(self, user_id: str, conn_id: str) -> str:
        """Create a secure session token for WebSocket connection using access tokens"""
        # Use the common security utils to generate an access token
        # with custom lifetime for WebSocket sessions (24 hours)
        session_token = generate_access_token(
            user_id=user_id,
            environment=f"ws_{conn_id}",  # Use connection ID as environment
            lifetime_seconds=86400  # 24 hours
        )

        return session_token

    async def verify_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode session token using common security utils"""
        try:
            # Parse the access token
            parsed = parse_access_token(token)
            if not parsed:
                return None

            user_id, environment, issued_at, rand, lifetime = parsed

            # Check if token is expired
            if time.time() - issued_at > lifetime:
                log.debug("Session token expired")
                return None

            # Extract connection ID from environment
            conn_id = environment.replace("ws_", "") if environment.startswith("ws_") else environment

            return {
                "user_id": user_id,
                "conn_id": conn_id,
                "timestamp": issued_at,
                "nonce": rand
            }

        except Exception as e:
            log.error(f"Token verification failed: {e}")
            return None

    async def rotate_keys(self) -> None:
        """
        Key rotation for WebSocket sessions.
        Note: Actual Fernet key rotation should be handled at the application level
        by updating FERNET_KEY and moving old key to FERNET_KEY_OLD
        """
        log.info("Key rotation requested. Fernet keys should be rotated via environment variables.")
        self.last_key_rotation = time.time()

    def get_security_info(self) -> Dict[str, Any]:
        """Get security configuration info"""
        return {
            'encryption_enabled': self.encryption_enabled,
            'encryption_algorithm': self.cipher_suite if self.encryption_enabled else None,
            'message_signing_enabled': self.message_signing_enabled,
            'session_key_rotation': self.key_rotation_interval,
            'last_key_rotation': self.last_key_rotation
        }

    async def create_encrypted_channel(self, user_id: str, channel_name: str) -> Dict[str, Any]:
        """Create an encrypted channel configuration for sensitive data"""
        if not self.encryption_enabled:
            return {"encrypted": False, "channel": channel_name}

        # Generate a channel-specific token
        channel_token = generate_access_token(
            user_id=user_id,
            environment=f"channel_{channel_name}",
            lifetime_seconds=3600  # 1 hour for channel tokens
        )

        return {
            "encrypted": True,
            "channel": channel_name,
            "channel_token": channel_token,
            "expires_in": 3600
        }

    async def encrypt_for_channel(self, channel_token: str, data: Any) -> Optional[str]:
        """Encrypt data for a specific channel"""
        # Verify channel token first
        parsed = parse_access_token(channel_token)
        if not parsed:
            log.warning("Invalid channel token")
            return None

        user_id, environment, issued_at, rand, lifetime = parsed

        # Check if token is expired
        if time.time() - issued_at > lifetime:
            log.warning("Channel token expired")
            return None

        # Encrypt the data
        return await self.encrypt_message(data)

    async def decrypt_for_channel(self, channel_token: str, encrypted_data: str) -> Optional[Any]:
        """Decrypt data for a specific channel"""
        # Verify channel token first
        parsed = parse_access_token(channel_token)
        if not parsed:
            log.warning("Invalid channel token")
            return None

        user_id, environment, issued_at, rand, lifetime = parsed

        # Check if token is expired
        if time.time() - issued_at > lifetime:
            log.warning("Channel token expired")
            return None

        # Decrypt the data
        return await self.decrypt_message(encrypted_data)