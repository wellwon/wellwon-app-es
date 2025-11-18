# =============================================================================
# File: app/services/user_auth_service.py
# Description: Service for user authentication related tasks for 
# - Handles password hashing and verification.
# =============================================================================

from __future__ import annotations

from app.security.encryption import hash_password as bcrypt_hash_password
from app.security.encryption import verify_password as bcrypt_verify_password

class UserAuthenticationService:
    """
    Service class for user authentication operations like password hashing and verification.
    """

    @staticmethod
    def hash_user_password(password: str) -> str:
        """
        Hashes a given plaintext password.
        Args:
            password: The plaintext password to hash.
        Returns:
            The hashed password string.
        """
        return bcrypt_hash_password(password)

    @staticmethod
    def verify_user_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verifies a plaintext password against a stored hashed password.
        Args:
            plain_password: The plaintext password to verify.
            hashed_password: The stored hashed password.
        Returns:
            True if the password matches, False otherwise.
        """
        return bcrypt_verify_password(plain_password, hashed_password)