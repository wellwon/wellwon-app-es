# =============================================================================
# File: app/config/jwt_config.py - JWT Configuration Management
# UPDATED: Using BaseConfig pattern with Pydantic v2
# =============================================================================

from functools import lru_cache
from typing import Optional, Dict, Any
from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from app.common.base.base_config import BaseConfig, BASE_CONFIG_DICT
from app.config.logging_config import get_logger

log = get_logger("wellwon.config.jwt")


class JWTConfig(BaseConfig):
    """
    Comprehensive JWT configuration using Pydantic v2 BaseConfig pattern.
    All settings are flattened for simpler env var mapping.
    """

    model_config = SettingsConfigDict(
        **BASE_CONFIG_DICT,
        env_prefix='JWT_',
    )

    # =========================================================================
    # Core Settings
    # =========================================================================

    secret_key: SecretStr = Field(
        default=SecretStr(""),
        description="JWT secret key (required, min 32 chars)"
    )

    environment: str = Field(
        default="development",
        description="Environment (development, production, testing)"
    )

    # =========================================================================
    # Token Lifecycle Settings
    # =========================================================================

    access_token_expire_minutes: int = Field(
        default=15,
        description="Access token expiration in minutes"
    )

    refresh_token_expire_days: int = Field(
        default=30,
        description="Refresh token expiration in days"
    )

    password_reset_token_expire_minutes: int = Field(
        default=30,
        description="Password reset token expiration in minutes"
    )

    email_verification_token_expire_hours: int = Field(
        default=24,
        description="Email verification token expiration in hours"
    )

    api_key_token_expire_days: int = Field(
        default=365,
        description="API key token expiration in days"
    )

    # Token properties
    issuer: str = Field(
        default="wellwon-platform",
        description="JWT issuer claim"
    )

    audience: str = Field(
        default="wellwon-api",
        description="JWT audience claim"
    )

    algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )

    include_jti: bool = Field(
        default=True,
        description="Include JWT ID claim"
    )

    include_iat: bool = Field(
        default=True,
        description="Include issued-at claim"
    )

    include_nbf: bool = Field(
        default=False,
        description="Include not-before claim"
    )

    # =========================================================================
    # Security Settings
    # =========================================================================

    refresh_rotation_enabled: bool = Field(
        default=True,
        description="Enable refresh token rotation"
    )

    token_family_size_limit: int = Field(
        default=10,
        description="Maximum tokens in a family"
    )

    max_concurrent_sessions: int = Field(
        default=5,
        description="Maximum concurrent sessions per user"
    )

    token_fingerprint_enabled: bool = Field(
        default=True,
        description="Enable token fingerprinting"
    )

    refresh_token_reuse_window: int = Field(
        default=5,
        description="Refresh token reuse detection window (seconds)"
    )

    blacklist_cleanup_days: int = Field(
        default=30,
        description="Days to keep blacklisted tokens"
    )

    token_creation_rate_limit: int = Field(
        default=100,
        description="Token creation rate limit (per minute)"
    )

    oauth_token_encryption_enabled: bool = Field(
        default=True,
        description="Enable OAuth token encryption"
    )

    # =========================================================================
    # Redis Settings
    # =========================================================================

    token_metadata_prefix: str = Field(
        default="token_metadata",
        description="Redis key prefix for token metadata"
    )

    refresh_token_prefix: str = Field(
        default="refresh_token",
        description="Redis key prefix for refresh tokens"
    )

    blacklisted_token_prefix: str = Field(
        default="blacklisted_token",
        description="Redis key prefix for blacklisted tokens"
    )

    token_family_prefix: str = Field(
        default="token_family",
        description="Redis key prefix for token families"
    )

    token_use_prefix: str = Field(
        default="token_use",
        description="Redis key prefix for token usage"
    )

    metadata_cleanup_buffer_seconds: int = Field(
        default=300,
        description="Buffer seconds for metadata cleanup"
    )

    family_cleanup_delay_seconds: int = Field(
        default=86400,
        description="Delay seconds for family cleanup (1 day)"
    )

    connection_timeout_seconds: int = Field(
        default=5,
        description="Redis connection timeout"
    )

    redis_retry_attempts: int = Field(
        default=3,
        description="Redis retry attempts"
    )

    # =========================================================================
    # Monitoring Settings
    # =========================================================================

    log_security_events: bool = Field(
        default=True,
        description="Log security events"
    )

    log_token_creation: bool = Field(
        default=False,
        description="Log token creation (verbose)"
    )

    log_token_validation: bool = Field(
        default=False,
        description="Log token validation (verbose)"
    )

    log_token_refresh: bool = Field(
        default=True,
        description="Log token refresh events"
    )

    log_token_revocation: bool = Field(
        default=True,
        description="Log token revocation events"
    )

    collect_token_metrics: bool = Field(
        default=True,
        description="Collect token metrics"
    )

    metrics_retention_days: int = Field(
        default=7,
        description="Metrics retention in days"
    )

    failed_validation_threshold: int = Field(
        default=10,
        description="Failed validation alert threshold (per minute)"
    )

    token_reuse_alert_threshold: int = Field(
        default=3,
        description="Token reuse alert threshold (per hour)"
    )

    blacklist_growth_alert_threshold: int = Field(
        default=100,
        description="Blacklist growth alert threshold (per hour)"
    )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def validate_config(self) -> None:
        """Validate JWT configuration"""
        secret = self.secret_key.get_secret_value()
        if not secret:
            raise RuntimeError("JWT secret_key is required")

        if len(secret) < 32:
            log.warning("JWT secret_key should be at least 32 characters long for security")

        if self.access_token_expire_minutes <= 0:
            raise ValueError("access_token_expire_minutes must be positive")

        if self.refresh_token_expire_days <= 0:
            raise ValueError("refresh_token_expire_days must be positive")

        if self.max_concurrent_sessions <= 0:
            raise ValueError("max_concurrent_sessions must be positive")

        supported_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        if self.algorithm not in supported_algorithms:
            raise ValueError(f"Unsupported algorithm: {self.algorithm}")

    def get_secret_key(self) -> str:
        """Get secret key as plain string"""
        return self.secret_key.get_secret_value()

    def apply_environment_overrides(self) -> 'JWTConfig':
        """Apply environment-specific configuration overrides"""
        overrides = {}

        if self.environment == "production":
            overrides.update({
                'token_fingerprint_enabled': True,
                'refresh_rotation_enabled': True,
                'log_token_creation': False,
                'log_token_validation': False,
                'max_concurrent_sessions': 3,
            })
        elif self.environment == "development":
            overrides.update({
                'access_token_expire_minutes': 480,  # 8 hours for dev
                'log_security_events': True,
                'max_concurrent_sessions': 10,
            })
        elif self.environment == "testing":
            overrides.update({
                'access_token_expire_minutes': 5,
                'refresh_token_expire_days': 1,
                'refresh_token_reuse_window': 1,
                'collect_token_metrics': False,
            })

        if overrides:
            return JWTConfig(**{**self.model_dump(), **overrides})
        return self


# =============================================================================
# Factory Function
# =============================================================================

@lru_cache(maxsize=1)
def get_jwt_config() -> JWTConfig:
    """Get JWT configuration singleton (cached)."""
    config = JWTConfig()
    config.validate_config()
    return config.apply_environment_overrides()


def reset_jwt_config() -> None:
    """Reset config singleton (for testing)."""
    get_jwt_config.cache_clear()
