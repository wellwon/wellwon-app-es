# =============================================================================
# File: app/security/jwt_config.py — JWT Configuration Management
# =============================================================================

import os
import logging
import secrets
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from pathlib import Path
import json
import yaml

log = logging.getLogger("app.security.jwt_config")


@dataclass
class JWTSecuritySettings:
    """JWT Security-related settings"""
    # Token rotation settings
    refresh_rotation_enabled: bool = True
    token_family_size_limit: int = 10

    # Session management
    max_concurrent_sessions: int = 5
    token_fingerprint_enabled: bool = True

    # Token reuse detection
    refresh_token_reuse_window: int = 5  # seconds

    # Blacklist settings
    blacklist_cleanup_days: int = 30

    # Rate limiting
    token_creation_rate_limit: int = 100  # per minute

    # Encryption settings
    oauth_token_encryption_enabled: bool = True


@dataclass
class JWTTokenSettings:
    """JWT Token lifecycle settings"""
    # Expiration times
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    password_reset_token_expire_minutes: int = 30
    email_verification_token_expire_hours: int = 24
    api_key_token_expire_days: int = 365

    # Token properties
    issuer: str = "wse-platform"
    audience: str = "wse-api"
    algorithm: str = "HS256"

    # Additional claims
    include_jti: bool = True
    include_iat: bool = True
    include_nbf: bool = False  # Not before claim


@dataclass
class JWTRedisSettings:
    """Redis-related JWT settings"""
    # Key prefixes
    token_metadata_prefix: str = "token_metadata"
    refresh_token_prefix: str = "refresh_token"
    blacklisted_token_prefix: str = "blacklisted_token"
    token_family_prefix: str = "token_family"
    token_use_prefix: str = "token_use"

    # TTL settings
    metadata_cleanup_buffer_seconds: int = 300
    family_cleanup_delay_seconds: int = 86400  # 1 day

    # Connection settings
    connection_pool_enabled: bool = True
    connection_timeout_seconds: int = 5
    retry_attempts: int = 3


@dataclass
class JWTMonitoringSettings:
    """JWT Monitoring and logging settings"""
    # Security event logging
    log_security_events: bool = True
    log_token_creation: bool = False  # Too verbose for production
    log_token_validation: bool = False
    log_token_refresh: bool = True
    log_token_revocation: bool = True

    # Metrics collection
    collect_token_metrics: bool = True
    metrics_retention_days: int = 7

    # Alerting thresholds
    failed_validation_threshold: int = 10  # per minute
    token_reuse_alert_threshold: int = 3  # per hour
    blacklist_growth_alert_threshold: int = 100  # per hour


@dataclass
class JWTConfig:
    """Comprehensive JWT configuration"""

    # Secret key (required)
    secret_key: str = field(default_factory=lambda: "")

    # Sub-configurations
    security: JWTSecuritySettings = field(default_factory=JWTSecuritySettings)
    tokens: JWTTokenSettings = field(default_factory=JWTTokenSettings)
    redis: JWTRedisSettings = field(default_factory=JWTRedisSettings)
    monitoring: JWTMonitoringSettings = field(default_factory=JWTMonitoringSettings)

    # Environment-specific overrides
    environment: str = "development"

    def __post_init__(self):
        """Validate configuration after initialization"""
        self.validate()

    def validate(self) -> None:
        """Validate JWT configuration"""
        if not self.secret_key:
            raise RuntimeError("JWT secret_key is required")

        if len(self.secret_key) < 32:
            log.warning("JWT secret_key should be at least 32 characters long for security")

        if self.tokens.access_token_expire_minutes <= 0:
            raise ValueError("access_token_expire_minutes must be positive")

        if self.tokens.refresh_token_expire_days <= 0:
            raise ValueError("refresh_token_expire_days must be positive")

        if self.security.max_concurrent_sessions <= 0:
            raise ValueError("max_concurrent_sessions must be positive")

        # Validate algorithm
        supported_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        if self.tokens.algorithm not in supported_algorithms:
            raise ValueError(f"Unsupported algorithm: {self.tokens.algorithm}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JWTConfig":
        """Create config from dictionary"""
        # Extract nested configurations
        security_data = data.pop("security", {})
        tokens_data = data.pop("tokens", {})
        redis_data = data.pop("redis", {})
        monitoring_data = data.pop("monitoring", {})

        return cls(
            security=JWTSecuritySettings(**security_data),
            tokens=JWTTokenSettings(**tokens_data),
            redis=JWTRedisSettings(**redis_data),
            monitoring=JWTMonitoringSettings(**monitoring_data),
            **data
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "secret_key": self.secret_key,
            "environment": self.environment,
            "security": self.security.__dict__,
            "tokens": self.tokens.__dict__,
            "redis": self.redis.__dict__,
            "monitoring": self.monitoring.__dict__
        }

    def apply_environment_overrides(self) -> None:
        """Apply environment-specific configuration overrides"""
        if self.environment == "production":
            # Production-specific settings
            self.security.token_fingerprint_enabled = True
            self.security.refresh_rotation_enabled = True
            self.monitoring.log_token_creation = False
            self.monitoring.log_token_validation = False
            self.security.max_concurrent_sessions = 3

        elif self.environment == "development":
            # Development-specific settings
            self.tokens.access_token_expire_minutes = 480  # 8 hours for development
            self.monitoring.log_security_events = True
            self.security.max_concurrent_sessions = 10

        elif self.environment == "testing":
            # Testing-specific settings
            self.tokens.access_token_expire_minutes = 5
            self.tokens.refresh_token_expire_days = 1
            self.security.refresh_token_reuse_window = 1
            self.monitoring.collect_token_metrics = False


class JWTConfigManager:
    """JWT Configuration manager with multiple sources support"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self._config: Optional[JWTConfig] = None
        self._config_sources: List[str] = []

    def load_config(
            self,
            config_file: Optional[str] = None,
            environment: Optional[str] = None,
            fallback_to_env: bool = True
    ) -> JWTConfig:
        """
        Load JWT configuration from multiple sources

        Priority order:
        1. Explicit config file
        2. Environment-specific config file
        3. Default config file
        4. Environment variables (if fallback_to_env=True)
        5. Default configuration
        """
        config_data = {}

        # Try to load from config file
        if config_file:
            config_data = self._load_from_file(config_file)
            if config_data:
                self._config_sources.append(f"file:{config_file}")

        # Try environment-specific config
        if not config_data and environment:
            env_config_file = self._get_env_config_path(environment)
            if env_config_file:
                config_data = self._load_from_file(env_config_file)
                if config_data:
                    self._config_sources.append(f"env_file:{env_config_file}")

        # Try default config file
        if not config_data:
            default_config = self._get_default_config_path()
            if default_config:
                config_data = self._load_from_file(default_config)
                if config_data:
                    self._config_sources.append(f"default_file:{default_config}")

        # Fallback to environment variables
        if not config_data and fallback_to_env:
            config_data = self._load_from_env()
            if config_data:
                self._config_sources.append("environment_variables")

        # Create config with defaults if nothing found
        if not config_data:
            config_data = self._get_default_config()
            self._config_sources.append("defaults")

        # Set environment if provided
        if environment:
            config_data["environment"] = environment

        # Create and validate config
        config = JWTConfig.from_dict(config_data)
        config.apply_environment_overrides()

        self._config = config
        log.info(f"JWT config loaded from: {', '.join(self._config_sources)}")

        return config

    def _load_from_file(self, file_path: str) -> Dict[str, Any]:
        """Load configuration from file (JSON or YAML)"""
        try:
            path = Path(file_path)
            if not path.exists():
                return {}

            with open(path, 'r') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    return yaml.safe_load(f) or {}
                elif path.suffix.lower() == '.json':
                    return json.load(f) or {}
                else:
                    log.warning(f"Unsupported config file format: {path.suffix}")
                    return {}

        except Exception as e:
            log.error(f"Failed to load config from {file_path}: {e}")
            return {}

    def _load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        config_data = {}

        # Main settings
        if secret_key := os.getenv("JWT_SECRET_KEY"):
            config_data["secret_key"] = secret_key

        if environment := os.getenv("JWT_ENVIRONMENT"):
            config_data["environment"] = environment

        # Token settings
        tokens_config = {}
        if val := os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES"):
            tokens_config["access_token_expire_minutes"] = int(val)
        if val := os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS"):
            tokens_config["refresh_token_expire_days"] = int(val)
        if val := os.getenv("JWT_ISSUER"):
            tokens_config["issuer"] = val
        if val := os.getenv("JWT_AUDIENCE"):
            tokens_config["audience"] = val
        if val := os.getenv("JWT_ALGORITHM"):
            tokens_config["algorithm"] = val

        if tokens_config:
            config_data["tokens"] = tokens_config

        # Security settings
        security_config = {}
        if val := os.getenv("JWT_REFRESH_ROTATION_ENABLED"):
            security_config["refresh_rotation_enabled"] = val.lower() == "true"
        if val := os.getenv("JWT_TOKEN_FAMILY_SIZE_LIMIT"):
            security_config["token_family_size_limit"] = int(val)
        if val := os.getenv("JWT_MAX_CONCURRENT_SESSIONS"):
            security_config["max_concurrent_sessions"] = int(val)
        if val := os.getenv("JWT_TOKEN_FINGERPRINT_ENABLED"):
            security_config["token_fingerprint_enabled"] = val.lower() == "true"
        if val := os.getenv("JWT_REFRESH_TOKEN_REUSE_WINDOW"):
            security_config["refresh_token_reuse_window"] = int(val)

        if security_config:
            config_data["security"] = security_config

        # Monitoring settings
        monitoring_config = {}
        if val := os.getenv("JWT_LOG_SECURITY_EVENTS"):
            monitoring_config["log_security_events"] = val.lower() == "true"
        if val := os.getenv("JWT_COLLECT_TOKEN_METRICS"):
            monitoring_config["collect_token_metrics"] = val.lower() == "true"

        if monitoring_config:
            config_data["monitoring"] = monitoring_config

        return config_data

    def _get_env_config_path(self, environment: str) -> Optional[str]:
        """Get environment-specific config file path"""
        possible_paths = [
            f"config/jwt_{environment}.yaml",
            f"config/jwt_{environment}.yml",
            f"config/jwt_{environment}.json",
            f"jwt_{environment}.yaml",
            f"jwt_{environment}.yml",
            f"jwt_{environment}.json"
        ]

        for path in possible_paths:
            if Path(path).exists():
                return path

        return None

    def _get_default_config_path(self) -> Optional[str]:
        """Get default config file path"""
        possible_paths = [
            "config/jwt.yaml",
            "config/jwt.yml",
            "config/jwt.json",
            "jwt.yaml",
            "jwt.yml",
            "jwt.json"
        ]

        for path in possible_paths:
            if Path(path).exists():
                return path

        return None

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        # Generate a secure secret key if none provided
        secret_key = os.getenv("JWT_SECRET_KEY")
        if not secret_key:
            secret_key = secrets.token_urlsafe(32)
            log.warning("No JWT_SECRET_KEY provided, generated a random one. "
                        "This should be set properly in production!")

        return {
            "secret_key": secret_key,
            "environment": os.getenv("ENVIRONMENT", "development"),
            "tokens": {
                "issuer": "wse-platform",
                "audience": "wse-api"
            }
        }

    def get_config(self) -> Optional[JWTConfig]:
        """Get current configuration"""
        return self._config

    def get_config_sources(self) -> List[str]:
        """Get list of configuration sources used"""
        return self._config_sources.copy()

    def save_config(self, file_path: str, format: str = "yaml") -> bool:
        """Save current configuration to file"""
        if not self._config:
            log.error("No configuration loaded to save")
            return False

        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            config_dict = self._config.to_dict()

            with open(path, 'w') as f:
                if format.lower() in ['yaml', 'yml']:
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
                elif format.lower() == 'json':
                    json.dump(config_dict, f, indent=2)
                else:
                    raise ValueError(f"Unsupported format: {format}")

            log.info(f"JWT config saved to {file_path}")
            return True

        except Exception as e:
            log.error(f"Failed to save config to {file_path}: {e}")
            return False


# Global configuration manager instance
_config_manager = JWTConfigManager()


def get_jwt_config(
        config_file: Optional[str] = None,
        environment: Optional[str] = None,
        reload: bool = False
) -> JWTConfig:
    """
    Get JWT configuration (cached)

    Args:
        config_file: Specific config file to load
        environment: Environment name for config selection
        reload: Force reload of configuration

    Returns:
        JWT configuration instance
    """
    global _config_manager

    if reload or _config_manager.get_config() is None:
        env = environment or os.getenv("ENVIRONMENT", "development")
        return _config_manager.load_config(config_file, env)

    return _config_manager.get_config()


def create_sample_config(file_path: str = "config/jwt.yaml") -> bool:
    """
    Create a sample JWT configuration file

    Args:
        file_path: Path where to save the sample config

    Returns:
        True if successful
    """
    sample_config = {
        "secret_key": "your-super-secret-jwt-key-at-least-32-characters-long",
        "environment": "development",
        "tokens": {
            "access_token_expire_minutes": 15,
            "refresh_token_expire_days": 30,
            "issuer": "wse-platform",
            "audience": "wse-api",
            "algorithm": "HS256"
        },
        "security": {
            "refresh_rotation_enabled": True,
            "token_family_size_limit": 10,
            "max_concurrent_sessions": 5,
            "token_fingerprint_enabled": True,
            "refresh_token_reuse_window": 5
        },
        "monitoring": {
            "log_security_events": True,
            "log_token_refresh": True,
            "collect_token_metrics": True
        },
        "redis": {
            "token_metadata_prefix": "token_metadata",
            "refresh_token_prefix": "refresh_token",
            "connection_timeout_seconds": 5
        }
    }

    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            yaml.dump(sample_config, f, default_flow_style=False, indent=2)

        log.info(f"Sample JWT config created at {file_path}")
        return True

    except Exception as e:
        log.error(f"Failed to create sample config: {e}")
        return False