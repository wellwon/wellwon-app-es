# =============================================================================
# File: app/common/enums/enums.py
# Description: Common enumerations for WellWon
# =============================================================================

from enum import IntEnum


class CacheTTL(IntEnum):
    """Cache TTL values in seconds"""

    # Token caching
    ACCESS_TOKEN = 3600  # 1 hour
    REFRESH_TOKEN = 86400  # 24 hours

    # Health check caching
    BROKER_HEALTH_CACHE = 30  # 30 seconds

    # User data caching
    USER_PROFILE = 300  # 5 minutes
    USER_SESSION = 1800  # 30 minutes

    # General caching
    SHORT = 60  # 1 minute
    MEDIUM = 300  # 5 minutes
    LONG = 3600  # 1 hour
    VERY_LONG = 86400  # 24 hours
