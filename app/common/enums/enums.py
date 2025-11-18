# =============================================================================
# File: app/common/enums.py
# Description: Common enumerations for the TradeCore application.
# Contains ONLY core domain enums used across domains, API, and infrastructure.
# Trading/broker-specific enums moved to adapter_enums.py
# =============================================================================

from enum import Enum


class WebSocketConnectionStatusEnum(str, Enum):
    """Defines the possible states of a WebSocket connection."""
    CONNECTED = "connected"
    CONNECTING = "connecting"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


class SystemHealthStatusEnum(str, Enum):
    """Defines the health status of system components."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"
    UNKNOWN = "unknown"


class ComponentStatusEnum(str, Enum):
    """Defines the status of individual components."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ALIVE = "alive"
    UNREACHABLE = "unreachable"
    ERROR = "error"
    ONLINE = "online"
    OFFLINE = "offline"
    WARNING = "warning"
    UNKNOWN = "unknown"


class CacheTTL:
    """Cache Time-To-Live values in seconds."""
    # Authentication & tokens
    ACCESS_TOKEN = 1800  # 30 minutes
    REFRESH_TOKEN = 172800  # 2 days
    OAUTH_TOKEN_STATUS = 60  # 1 minute

    # Account data
    ACCOUNT_SUMMARY = 300  # 5 minutes
    ACCOUNT_BALANCES = 120  # 2 minutes
    ACCOUNT_POSITIONS = 120  # 2 minutes
    ACCOUNT_ORDERS = 60  # 1 minute
    ACCOUNT_METADATA = 300  # 5 minutes

    # Automation & configuration
    AUTOMATION_SETTINGS = 86400  # 1 day
    AUTOMATION_MAPPING = 604800  # 1 week

    # Market data
    MARKET_HOURS = 3600  # 1 hour
    ASSET_DETAILS = 86400  # 1 day
    OPTION_CHAIN_DATA = 300  # 5 minutes
    QUOTE_SNAPSHOT = 5  # 5 seconds
    BAR_DATA = 60  # 1 minute
    TRADE_DATA = 10  # 10 seconds

    # System & monitoring
    CONNECTION_STATE = 60  # 1 minute
    SYSTEM_HEALTH = 30  # 30 seconds
    BROKER_HEALTH_CACHE = 30  # 30 seconds
    BROKER_DEEP_CHECK_INTERVAL = 300  # 5 minutes
    BROKER_MONITORING_INTERVAL = 60  # 1 minute
    BROKER_MODULE_HEALTH = 60  # 1 minute
    BROKER_CONNECTION_METRICS = 120  # 2 minutes
    BROKER_ERROR_CACHE = 300  # 5 minutes

    # User & webhook
    USER_PROFILE = 3600  # 1 hour
    WEBHOOK_URL = 86400  # 1 day


class MonitoringConfig:
    """Configuration constants for broker monitoring service."""
    MAX_CONSECUTIVE_FAILURES = 3
    AUTO_MONITOR_DEFAULT = False
    HEALTH_CHECK_TIMEOUT = 10  # seconds
    CIRCUIT_BREAKER_THRESHOLD = 5  # failures before circuit opens
    CIRCUIT_BREAKER_RESET_TIME = 300  # seconds before retry