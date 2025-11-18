# =============================================================================
# File: app/config/cache_config.py
# Description: Unified Cache Management Configuration
# IMPORTANT: This file is ONLY imported by cache_manager.py
# NO modules should import this directly - they use cache_manager methods instead
# =============================================================================

from typing import Dict, Any
import os

# Comprehensive Cache Configuration
CACHE_CONFIG: Dict[str, Any] = {
    # =========================================================================
    # Core Cache Settings
    # =========================================================================
    "core": {
        "enabled": True,
        "key_prefix": "wellwon",
        "default_ttl": 300,  # 5 minutes default
        "max_key_length": 256,
        "compression_enabled": False,
        "compression_threshold": 1024,  # bytes
    },

    # =========================================================================
    # Redis Connection Settings
    # =========================================================================
    "redis": {
        "decode_responses": True,
        "scan_count": 100,  # Keys per SCAN iteration
        "pipeline_max_size": 100,
        "max_connections": 150,  # Increased from 50 to handle multi-worker load
        "socket_keepalive": 60,
        "socket_timeout": 10.0,  # Reduced from 15s for faster timeout
        "socket_connect_timeout": 3.0,  # Reduced from 5s for faster connection
    },

    # =========================================================================
    # TTL Configuration by Domain (in seconds)
    # =========================================================================
    "ttl": {
        # User & Authentication
        "user": {
            "profile": 3600,  # 1 hour
            "settings": 3600,  # 1 hour
            "permissions": 900,  # 15 minutes
            "accounts": 300,  # 5 minutes - for user account lists
        },
        "auth": {
            "session": 3600,  # 1 hour
            "token": 1800,  # 30 minutes
            "permissions": 900,  # 15 minutes
            "ratelimit": 60,  # 1 minute
        },

        # OAuth tokens - broker specific
        "oauth": {
            # Default OAuth TTLs
            "access_token": 3600,  # 1 hour default
            "refresh_token": 2592000,  # 30 days default
            "state": 600,  # 10 minutes for OAuth state

            # Broker-specific OAuth TTLs
            "alpaca": {
                "access_token": 3600,  # 60 minutes for Alpaca
                "refresh_token": 2592000,  # 30 days
            },
            "tradestation": {
                "access_token": 1200,  # 20 minutes for TradeStation
                "refresh_token": 5184000,  # 60 days
            },
            "virtual": {
                "access_token": 86400,  # 24 hours for Virtual (no real expiry)
                "refresh_token": 31536000,  # 1 year (effectively permanent)
            },
        },

        # Broker Connections
        "broker": {
            "health": 60,  # 1 minute
            "auth": 1800,  # 30 minutes
            "accounts": 300,  # 5 minutes
            "ratelimit": 60,  # 1 minute
            "config": 3600,  # 1 hour
            "capabilities": 86400,  # 24 hours
            "connection": 300,  # 5 minutes - for connection state
        },

        # Monitoring Service - For BrokerMonitoringService
        "monitoring": {
            "health_status": 60,  # 1 minute - broker health status
            "metrics": 3600,  # 1 hour - health metrics
            "module_health": 120,  # 2 minutes - module-level health
            "pool_health": 30,  # 30 seconds - adapter pool health
            "connection_stats": 300,  # 5 minutes - connection statistics
            "error_rates": 180,  # 3 minutes - error rate tracking
            "performance": 300,  # 5 minutes - performance metrics
            "alerts": 900,  # 15 minutes - monitoring alerts
            "heartbeat": 10,  # 10 seconds - heartbeat/keepalive
        },

        # Data Integrity Monitor - NEW SECTION
        "integrity": {
            "check_result": 60,  # 1 minute - integrity check results
            "discovery_result": 300,  # 5 minutes - account discovery results
            "recovery_state": 600,  # 10 minutes - recovery operation state
            "connection_state": 120,  # 2 minutes - connection state tracking
            "pending_discovery": 180,  # 3 minutes - pending discovery tracking
            "issue_tracking": 900,  # 15 minutes - issue deduplication
            "metrics": 300,  # 5 minutes - integrity metrics
            "alert_history": 3600,  # 1 hour - alert history for throttling
            "batch_results": 600,  # 10 minutes - discovery batch results
            "check_basic": 30,  # 30 seconds - basic check results (count only)
            "check_standard": 60,  # 1 minute - standard check results
            "check_deep": 300,  # 5 minutes - deep check results (full validation)
        },

        # Virtual Broker - REDUCED TTLs to minimize duplicate issues
        "vb": {
            "adapter": 300,  # 5 minutes - REDUCED from 1 hour
            "account": 120,  # 2 minutes - REDUCED from 5 minutes
            "balance": 30,  # 30 seconds - real-time feel
            "position": 30,  # 30 seconds
            "order": 60,  # 1 minute
            "execution": 300,  # 5 minutes
            "market": 5,  # 5 seconds - near real-time
            "session": 3600,  # 1 hour
        },

        # Trading Account Data - COMPLETE with all module TTLs
        "account": {
            "info": 300,  # 5 minutes - account info
            "data": 300,  # 5 minutes - general account data
            "balance": 30,  # 30 seconds - account balances
            "list": 120,  # 2 minutes - account lists
            "summary": 60,  # 1 minute - account summary
            "portfolio_history": 300,  # 5 minutes - portfolio history
            "activities": 120,  # 2 minutes - account activities
            "config": 600,  # 10 minutes - account configurations
            "configurations": 600,  # 10 minutes - alias for config
            "day_trading": 60,  # 1 minute - day trading info
        },

        # Order Data
        "order": {
            "status": 10,  # 10 seconds - critical
            "history": 300,  # 5 minutes
        },

        # Position Data
        "position": {
            "list": 30,  # 30 seconds - positions list
            "detail": 20,  # 20 seconds - single position detail
            "current": 60,  # 1 minute - current positions
            "history": 3600,  # 1 hour - position history
        },

        # Portfolio Data
        "portfolio": {
            "summary": 60,  # 1 minute - composite portfolio summary
            "activities": 120,  # 2 minutes - account activities (fills, dividends, fees)
            "snapshots": 300,  # 5 minutes - equity curve snapshots
            "performance": 300,  # 5 minutes - performance statistics (win rate, profit factor, etc.)
            "query": 60,  # 1 minute - general portfolio queries
        },

        # Market Data - Complete with all types
        "market": {
            "quote": 5,  # 5 seconds - real-time quotes
            "quotes": 5,  # 5 seconds - alias for quote
            "bars": 60,  # 1 minute - historical bars
            "trades": 10,  # 10 seconds - trade data
            "hours": 86400,  # 24 hours - market hours
            "symbols": 3600,  # 1 hour - symbol lists
            "news": 300,  # 5 minutes - news articles
            "snapshot": 5,  # 5 seconds - market snapshots
            "snapshots": 5,  # 5 seconds - alias for snapshot
            "depth": 5,  # 5 seconds - order book depth
            "status": 60,  # 1 minute - market status
            "auctions": 300,  # 5 minutes - auction data
        },

        # Market Hours Data - NEW SECTION
        "hours": {
            "clock": 5,  # 5 seconds - market clock changes frequently
            "calendar": 86400,  # 24 hours - calendar rarely changes
            "trading_days": 86400,  # 24 hours - trading days are static
            "early_close": 86400,  # 24 hours - early close days known in advance
        },

        # Options Market Data
        "options": {
            "quote": 5,  # 5 seconds - options are less liquid
            "quotes": 5,  # 5 seconds - alias
            "trades": 10,  # 10 seconds - options trades
            "bars": 60,  # 1 minute - options bars
            "snapshot": 5,  # 5 seconds - includes Greeks
            "snapshots": 5,  # 5 seconds - alias
            "chain": 60,  # 1 minute - full option chain
        },

        # Crypto Market Data
        "crypto": {
            "quote": 2,  # 2 seconds - crypto is very volatile
            "quotes": 2,  # 2 seconds - alias
            "trades": 5,  # 5 seconds - crypto trades
            "bars": 30,  # 30 seconds - crypto bars
            "snapshot": 5,  # 5 seconds - crypto snapshots
            "snapshots": 5,  # 5 seconds - alias
            "orderbook": 2,  # 2 seconds - orderbooks change rapidly
            "orderbooks": 2,  # 2 seconds - alias
        },

        # Market Metadata
        "metadata": {
            "conditions": 86400,  # 24 hours - rarely changes
            "exchanges": 86400,  # 24 hours - static data
            "trade_conditions": 86400,  # 24 hours - same as conditions
            "quote_conditions": 86400,  # 24 hours - same as conditions
        },

        # Corporate Actions - NEW SECTION
        "corporate": {
            "announcements": 86400,  # 24 hours - corporate actions rarely change
            "announcement": 86400,  # 24 hours - individual announcement
            "upcoming_events": 21600,  # 6 hours - upcoming events cache
            "dividend": 86400,  # 24 hours - dividend announcements
            "split": 86400,  # 24 hours - split announcements
            "merger": 86400,  # 24 hours - merger announcements
            "spinoff": 86400,  # 24 hours - spinoff announcements
        },

        # News Data - NEW SECTION
        "news": {
            "news": 3600,  # 1 hour - general news
            "news_by_symbol": 1800,  # 30 minutes - symbol-specific news
            "market_news": 1800,  # 30 minutes - market news
            "search": 1800,  # 30 minutes - search results
            "latest": 900,  # 15 minutes - latest news
        },

        # Watchlist Data - NEW SECTION
        "watchlist": {
            "watchlists": 300,  # 5 minutes - list of watchlists
            "watchlist": 120,  # 2 minutes - individual watchlist
            "all_symbols": 300,  # 5 minutes - all symbols across watchlists
        },

        # System & API
        "system": {
            "config": 3600,  # 1 hour
            "status": 60,  # 1 minute
        },
        "api": {
            "response": 300,  # 5 minutes
            "schema": 3600,  # 1 hour
            "metadata": 86400,  # 24 hours
        },

        # Event Store & CQRS - NEW SECTION
        "event_store": {
            "version": 60,  # 1 minute - aggregate version cache
            "metadata": 300,  # 5 minutes - snapshot metadata cache
            "checkpoint": 60,  # 1 minute - projection checkpoints
            "stream": 30,  # 30 seconds - stream metadata
        },
        "aggregate": {
            "instance": 60,  # 1 minute - full aggregate instance cache
            "state": 120,  # 2 minutes - aggregate state snapshots
        },
        "sequence": {
            "tracking": 60,  # 1 minute - event sequence tracking per aggregate
            "checkpoint": 30,  # 30 seconds - sequence checkpoints
        },
    },

    # =========================================================================
    # Cleanup & Maintenance - ENHANCED
    # =========================================================================
    "cleanup": {
        "on_startup": True,  # Clear stale entries on startup
        "batch_size": 1000,  # Keys per cleanup batch
        "interval_hours": 6,  # Run cleanup every 6 hours
        "max_age_hours": 24,  # Max age for orphaned keys

        # Virtual Broker specific
        "vb": {
            "clear_on_disconnect": True,
            "clear_on_reset": True,
            "clear_on_delete": True,
            "cleanup_orphaned": True,
            "clear_adapter_cache": True,  # Clear adapter discovery cache
        },

        # Broker specific - ENHANCED
        "broker": {
            "clear_on_disconnect": True,
            "clear_on_auth_fail": True,
            "clear_on_rate_limit": False,
            "aggressive_cleanup": True,  # Enable comprehensive cleanup
            "clear_account_balances": True,  # Clear all account balances
            "clear_api_cache": True,  # Clear API response cache
            "pre_disconnect_clear": True,  # Clear before disconnect operations
        },

        # Account specific
        "account": {
            "clear_on_delete": True,
            "clear_related_data": True,  # Clear orders, positions, etc.
            "clear_vb_data": True,  # Clear virtual broker data
            "cascade_clear": True,  # Clear all related caches
        },

        # Connection specific
        "connection": {
            "clear_on_error": True,
            "clear_on_reauth": True,
            "clear_health_data": True,
            "nuclear_on_critical": True,  # Nuclear clear on critical errors
        },

        # Integrity specific - NEW
        "integrity": {
            "clear_on_recovery": True,  # Clear cache after successful recovery
            "clear_on_discovery": True,  # Clear cache after account discovery
            "clear_stale_results": True,  # Clear old check results
            "clear_on_connection_remove": True,  # Clear when connection removed
            "preserve_metrics": True,  # Don't clear metrics on cleanup
        },
    },

    # =========================================================================
    # Monitoring & Metrics - ENHANCED
    # =========================================================================
    "monitoring": {
        "metrics_enabled": True,
        "metrics_interval_sec": 60,
        "log_slow_operations": True,
        "slow_operation_threshold_ms": 50,  # Back to 50ms - investigate real issue
        "log_cache_hits": False,  # Verbose when true
        "log_cache_misses": True,
        "log_cache_clears": True,  # Log all cache clear operations

        # Performance tracking
        "track_hit_rate": True,
        "track_latency": True,
        "track_clears": True,  # Track cache clear operations
        "latency_buckets": [1, 5, 10, 25, 50, 100, 250, 500, 1000],  # ms
    },

    # =========================================================================
    # Feature Flags - ENHANCED
    # =========================================================================
    "features": {
        # Enable/disable specific cache domains
        "enable_user": True,
        "enable_auth": True,
        "enable_broker": True,
        "enable_vb": True,
        "enable_trading": True,
        "enable_market": True,
        "enable_api": True,
        "enable_oauth": True,  # Enable OAuth caching
        "enable_monitoring": True,  # Enable monitoring cache
        "enable_integrity": True,  # Enable integrity monitor cache
        "enable_portfolio": True,  # Enable portfolio cache

        # Cache strategies
        "write_through": True,  # Write to cache and DB
        "lazy_load": True,  # Load cache on demand
        "refresh_ahead": False,  # Refresh before expiry

        # Advanced features
        "distributed_invalidation": True,
        "cache_warming": False,
        "auto_retry": True,
        "batch_operations": True,  # Enable batch cache operations
        "pattern_deletion": True,  # Enable pattern-based deletion
    },

    # =========================================================================
    # Resource Limits
    # =========================================================================
    "limits": {
        "max_memory_mb": 1024,  # Redis maxmemory
        "eviction_policy": "allkeys-lru",
        "max_entries_per_key": 1000,  # For lists/sets
        "max_key_size": 250,  # Characters
        "max_value_size": 1048576,  # 1MB
        "max_pipeline_size": 100,  # Max commands in pipeline
    },

    # =========================================================================
    # Rate Limiting
    # =========================================================================
    "rate_limiting": {
        "default_window": 60,  # Default window in seconds
        "default_limit": 100,  # Default requests per window

        # Specific limits by resource
        "limits": {
            "api": 1000,  # API calls per minute
            "auth": 10,  # Auth attempts per minute
            "broker": 100,  # Broker operations per minute
            "market": 2000,  # Market data requests per minute
            "cache_clear": 50,  # Cache clear operations per minute
            "oauth_exchange": 20,  # OAuth code exchanges per minute
            "oauth_refresh": 10,  # OAuth token refreshes per minute per user
            "monitoring_health": 120,  # Health checks per minute
            "monitoring_metrics": 60,  # Metrics updates per minute
            "integrity_check": 100,  # Integrity checks per minute
            "integrity_recovery": 10,  # Recovery operations per minute
        },
    },

    # =========================================================================
    # Critical Operations
    # =========================================================================
    "critical": {
        "disconnect_reasons": [  # Reasons that trigger nuclear cleanup
            "auth_failure",
            "security_breach",
            "force_cleanup",
            "credential_revoked",
            "rate_limit_exceeded",
        ],
        "nuclear_cleanup_delay_ms": 100,  # Delay before nuclear cleanup
        "verify_cleanup": True,  # Verify cache is cleared
        "retry_cleanup": True,  # Retry failed cleanups
        "max_cleanup_retries": 3,
    },

    # =========================================================================
    # Debug & Development - ENHANCED
    # =========================================================================
    "debug": {
        "enabled": False,  # Debug mode
        "bypass_cache": False,  # Bypass all caching
        "fake_miss_rate": 0,  # Simulate misses (0-100%)
        "log_keys": False,  # Log all keys (security risk!)
        "stats_endpoint": True,  # Enable /cache/stats endpoint
        "verbose_errors": False,  # Detailed error logging
        "trace_operations": False,  # Trace all cache operations
        "pattern_test_mode": False,  # Test pattern matching without deletion
    },
}


# Helper functions used ONLY by cache_manager.py
def get_cache_config(path: str, default: Any = None) -> Any:
    """
    Get a configuration value by dot-separated path.
    Example: get_cache_config('ttl.market.quote', 5)
    ONLY called from cache_manager.py
    """
    keys = path.split('.')
    value = CACHE_CONFIG

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def get_ttl(cache_type: str) -> int:
    """
    Get TTL for a specific cache type.
    Example: get_ttl('market:quote') returns 5
    ONLY called from cache_manager.py
    """
    # Convert 'market:quote' to 'ttl.market.quote'
    parts = cache_type.split(':')
    if len(parts) == 2:
        domain, type_ = parts
        return get_cache_config(f'ttl.{domain}.{type_}', CACHE_CONFIG['core']['default_ttl'])
    return CACHE_CONFIG['core']['default_ttl']


def get_module_ttl(module_name: str, cache_type: str, default: int = None) -> int:
    """
    Get TTL for a specific module and cache type.
    ONLY called from cache_manager.py's get_module_ttl method

    Args:
        module_name: Module name (e.g., 'market', 'account', 'position')
        cache_type: Cache type within module (e.g., 'quote', 'balance', 'list')
        default: Default TTL if not found

    Returns:
        TTL in seconds
    """
    ttl = get_cache_config(f'ttl.{module_name}.{cache_type}')
    if ttl is not None:
        return ttl

    # If no default provided, use core default
    if default is None:
        return CACHE_CONFIG['core']['default_ttl']

    return default


def get_oauth_ttl(broker_id: str, token_type: str = 'access_token') -> int:
    """
    Get OAuth TTL for specific broker and token type.
    ONLY called from cache_manager.py's get_oauth_ttl method

    Args:
        broker_id: Broker identifier ('alpaca', 'tradestation', 'virtual')
        token_type: Type of token ('access_token' or 'refresh_token')

    Returns:
        TTL in seconds
    """
    # Try broker-specific TTL first
    broker_ttl = get_cache_config(f'ttl.oauth.{broker_id}.{token_type}')
    if broker_ttl is not None:
        return broker_ttl

    # Fall back to default OAuth TTL
    default_ttl = get_cache_config(f'ttl.oauth.{token_type}')
    if default_ttl is not None:
        return default_ttl

    # Final fallback based on token type
    return 3600 if token_type == 'access_token' else 2592000


def get_broker_cache_ttl(broker_id: str, cache_type: str) -> int:
    """
    Get cache TTL for broker-specific data.
    ONLY called from cache_manager.py

    Args:
        broker_id: Broker identifier
        cache_type: Type of cache (e.g., 'health', 'accounts', 'connection')

    Returns:
        TTL in seconds
    """
    # Try broker-specific TTL
    broker_ttl = get_cache_config(f'ttl.broker.{broker_id}.{cache_type}')
    if broker_ttl is not None:
        return broker_ttl

    # Fall back to general broker TTL
    return get_cache_config(f'ttl.broker.{cache_type}', CACHE_CONFIG['core']['default_ttl'])


def get_integrity_ttl(check_type: str = 'standard') -> int:
    """
    Get TTL for integrity monitor cache.
    ONLY called from cache_manager.py

    Args:
        check_type: Type of integrity check or data

    Returns:
        TTL in seconds
    """
    # Map check levels to cache types
    ttl_map = {
        'basic': 'check_basic',
        'standard': 'check_standard',
        'deep': 'check_deep',
        'result': 'check_result',
        'discovery': 'discovery_result',
        'recovery': 'recovery_state',
        'connection': 'connection_state',
        'pending': 'pending_discovery',
        'issue': 'issue_tracking',
        'metrics': 'metrics',
        'alert': 'alert_history',
        'batch': 'batch_results'
    }

    cache_type = ttl_map.get(check_type, 'check_result')
    return get_cache_config(f'ttl.integrity.{cache_type}', CACHE_CONFIG['core']['default_ttl'])


def is_critical_disconnect_reason(reason: str) -> bool:
    """
    Check if a disconnect reason requires nuclear cleanup.
    ONLY called from cache_manager.py
    """
    critical_reasons = get_cache_config('critical.disconnect_reasons', [])
    return reason.lower() in [r.lower() for r in critical_reasons]


# OAuth rate limits by broker
OAUTH_RATE_LIMITS = {
    'default': {
        'exchange': 20,  # Token exchanges per minute
        'refresh': 10,  # Token refreshes per minute per user
        'introspect': 60,  # Token introspections per minute
    },
    'alpaca': {
        'exchange': 20,
        'refresh': 10,
    },
    'tradestation': {
        'exchange': 15,  # TradeStation is a bit more restrictive
        'refresh': 5,
    },
    'virtual': {
        'exchange': 100,  # Virtual broker has no real limits
        'refresh': 100,
    },
}


def get_oauth_rate_limit(broker_id: str, operation: str) -> int:
    """
    Get OAuth rate limit for specific broker and operation.
    ONLY called from cache_manager.py

    Args:
        broker_id: Broker identifier
        operation: Operation type ('exchange', 'refresh', 'introspect')

    Returns:
        Rate limit (requests per minute)
    """
    broker_limits = OAUTH_RATE_LIMITS.get(broker_id, OAUTH_RATE_LIMITS['default'])
    return broker_limits.get(operation, 10)  # Default to 10 per minute


def override_from_env() -> None:
    """
    Override configuration from environment variables if present
    ONLY called during module initialization
    """
    # Core settings
    if env_val := os.getenv('CACHE_ENABLED'):
        CACHE_CONFIG['core']['enabled'] = env_val.lower() in ('true', '1', 'yes')

    if env_val := os.getenv('CACHE_KEY_PREFIX'):
        CACHE_CONFIG['core']['key_prefix'] = env_val

    if env_val := os.getenv('CACHE_DEFAULT_TTL'):
        CACHE_CONFIG['core']['default_ttl'] = int(env_val)

    # TTL overrides - example for VB balance
    if env_val := os.getenv('CACHE_TTL_VB_BALANCE'):
        CACHE_CONFIG['ttl']['vb']['balance'] = int(env_val)

    if env_val := os.getenv('CACHE_TTL_VB_ADAPTER'):
        CACHE_CONFIG['ttl']['vb']['adapter'] = int(env_val)

    # OAuth TTL overrides
    if env_val := os.getenv('CACHE_TTL_OAUTH_ALPACA_ACCESS'):
        CACHE_CONFIG['ttl']['oauth']['alpaca']['access_token'] = int(env_val)

    if env_val := os.getenv('CACHE_TTL_OAUTH_TRADESTATION_ACCESS'):
        CACHE_CONFIG['ttl']['oauth']['tradestation']['access_token'] = int(env_val)

    # Market data TTL overrides
    if env_val := os.getenv('CACHE_TTL_MARKET_QUOTE'):
        CACHE_CONFIG['ttl']['market']['quote'] = int(env_val)

    if env_val := os.getenv('CACHE_TTL_MARKET_BARS'):
        CACHE_CONFIG['ttl']['market']['bars'] = int(env_val)

    # Options market data TTL overrides
    if env_val := os.getenv('CACHE_TTL_OPTIONS_QUOTE'):
        CACHE_CONFIG['ttl']['options']['quote'] = int(env_val)

    if env_val := os.getenv('CACHE_TTL_OPTIONS_SNAPSHOT'):
        CACHE_CONFIG['ttl']['options']['snapshot'] = int(env_val)

    # Crypto market data TTL overrides
    if env_val := os.getenv('CACHE_TTL_CRYPTO_QUOTE'):
        CACHE_CONFIG['ttl']['crypto']['quote'] = int(env_val)

    if env_val := os.getenv('CACHE_TTL_CRYPTO_ORDERBOOK'):
        CACHE_CONFIG['ttl']['crypto']['orderbook'] = int(env_val)

    # Metadata TTL overrides
    if env_val := os.getenv('CACHE_TTL_METADATA_CONDITIONS'):
        CACHE_CONFIG['ttl']['metadata']['conditions'] = int(env_val)

    # Market Hours TTL overrides
    if env_val := os.getenv('CACHE_TTL_HOURS_CLOCK'):
        CACHE_CONFIG['ttl']['hours']['clock'] = int(env_val)

    # Corporate Actions TTL overrides
    if env_val := os.getenv('CACHE_TTL_CORPORATE_ANNOUNCEMENTS'):
        CACHE_CONFIG['ttl']['corporate']['announcements'] = int(env_val)

    # News TTL overrides
    if env_val := os.getenv('CACHE_TTL_NEWS_MARKET'):
        CACHE_CONFIG['ttl']['news']['market_news'] = int(env_val)

    # Watchlist TTL overrides
    if env_val := os.getenv('CACHE_TTL_WATCHLIST_LISTS'):
        CACHE_CONFIG['ttl']['watchlist']['watchlists'] = int(env_val)

    # Account TTL overrides
    if env_val := os.getenv('CACHE_TTL_ACCOUNT_BALANCE'):
        CACHE_CONFIG['ttl']['account']['balance'] = int(env_val)

    # Monitoring TTL overrides
    if env_val := os.getenv('CACHE_TTL_MONITORING_HEALTH'):
        CACHE_CONFIG['ttl']['monitoring']['health_status'] = int(env_val)

    if env_val := os.getenv('CACHE_TTL_MONITORING_METRICS'):
        CACHE_CONFIG['ttl']['monitoring']['metrics'] = int(env_val)

    if env_val := os.getenv('CACHE_TTL_MONITORING_POOL'):
        CACHE_CONFIG['ttl']['monitoring']['pool_health'] = int(env_val)

    # Integrity TTL overrides - NEW
    if env_val := os.getenv('CACHE_TTL_INTEGRITY_CHECK'):
        CACHE_CONFIG['ttl']['integrity']['check_result'] = int(env_val)

    if env_val := os.getenv('CACHE_TTL_INTEGRITY_DISCOVERY'):
        CACHE_CONFIG['ttl']['integrity']['discovery_result'] = int(env_val)

    if env_val := os.getenv('CACHE_TTL_INTEGRITY_RECOVERY'):
        CACHE_CONFIG['ttl']['integrity']['recovery_state'] = int(env_val)

    # Cleanup settings
    if env_val := os.getenv('CACHE_BROKER_AGGRESSIVE_CLEANUP'):
        CACHE_CONFIG['cleanup']['broker']['aggressive_cleanup'] = env_val.lower() in ('true', '1', 'yes')

    if env_val := os.getenv('CACHE_INTEGRITY_CLEAR_ON_RECOVERY'):
        CACHE_CONFIG['cleanup']['integrity']['clear_on_recovery'] = env_val.lower() in ('true', '1', 'yes')

    # Debug mode
    if env_val := os.getenv('CACHE_DEBUG_MODE'):
        CACHE_CONFIG['debug']['enabled'] = env_val.lower() in ('true', '1', 'yes')


def apply_environment_config(env: str = "development") -> None:
    """
    Apply environment-specific configuration
    ONLY called during module initialization
    """
    if env == "production":
        # Production optimizations
        CACHE_CONFIG['ttl']['vb']['balance'] = 60  # Longer TTL
        CACHE_CONFIG['ttl']['vb']['position'] = 60
        CACHE_CONFIG['ttl']['vb']['adapter'] = 600  # 10 minutes
        CACHE_CONFIG['ttl']['market']['quote'] = 10  # Less aggressive
        CACHE_CONFIG['ttl']['market']['bars'] = 120  # 2 minutes
        CACHE_CONFIG['ttl']['account']['balance'] = 60  # 1 minute
        CACHE_CONFIG['ttl']['options']['quote'] = 10  # 10 seconds
        CACHE_CONFIG['ttl']['crypto']['quote'] = 5  # 5 seconds
        CACHE_CONFIG['ttl']['crypto']['orderbook'] = 5  # 5 seconds
        CACHE_CONFIG['ttl']['hours']['clock'] = 10  # 10 seconds in prod
        CACHE_CONFIG['ttl']['news']['market_news'] = 3600  # 1 hour in prod

        # Monitoring TTLs for production
        CACHE_CONFIG['ttl']['monitoring']['health_status'] = 120  # 2 minutes
        CACHE_CONFIG['ttl']['monitoring']['metrics'] = 3600  # 1 hour
        CACHE_CONFIG['ttl']['monitoring']['pool_health'] = 60  # 1 minute
        CACHE_CONFIG['ttl']['monitoring']['connection_stats'] = 600  # 10 minutes
        CACHE_CONFIG['ttl']['monitoring']['heartbeat'] = 15  # 15 seconds

        # Integrity TTLs for production
        CACHE_CONFIG['ttl']['integrity']['check_result'] = 120  # 2 minutes
        CACHE_CONFIG['ttl']['integrity']['discovery_result'] = 600  # 10 minutes
        CACHE_CONFIG['ttl']['integrity']['recovery_state'] = 900  # 15 minutes
        CACHE_CONFIG['ttl']['integrity']['metrics'] = 600  # 10 minutes

        CACHE_CONFIG['monitoring']['log_cache_hits'] = False
        CACHE_CONFIG['monitoring']['log_cache_misses'] = False
        CACHE_CONFIG['debug']['enabled'] = False
        CACHE_CONFIG['cleanup']['interval_hours'] = 24  # Daily cleanup
        CACHE_CONFIG['cleanup']['broker']['aggressive_cleanup'] = True  # Always aggressive in prod

    elif env == "development":
        # Development settings
        CACHE_CONFIG['ttl']['vb']['balance'] = 10  # Faster updates
        CACHE_CONFIG['ttl']['vb']['adapter'] = 60  # 1 minute for testing
        CACHE_CONFIG['ttl']['market']['quote'] = 2  # Near real-time
        CACHE_CONFIG['ttl']['market']['bars'] = 30  # 30 seconds
        CACHE_CONFIG['ttl']['account']['balance'] = 15  # 15 seconds
        CACHE_CONFIG['ttl']['options']['quote'] = 2  # 2 seconds
        CACHE_CONFIG['ttl']['crypto']['quote'] = 1  # 1 second
        CACHE_CONFIG['ttl']['crypto']['orderbook'] = 1  # 1 second
        CACHE_CONFIG['ttl']['hours']['clock'] = 2  # 2 seconds in dev
        CACHE_CONFIG['ttl']['corporate']['announcements'] = 3600  # 1 hour in dev
        CACHE_CONFIG['ttl']['news']['market_news'] = 600  # 10 minutes in dev
        CACHE_CONFIG['ttl']['watchlist']['watchlists'] = 60  # 1 minute in dev

        # Monitoring TTLs for development - shorter for faster feedback
        CACHE_CONFIG['ttl']['monitoring']['health_status'] = 30  # 30 seconds
        CACHE_CONFIG['ttl']['monitoring']['metrics'] = 600  # 10 minutes
        CACHE_CONFIG['ttl']['monitoring']['pool_health'] = 15  # 15 seconds
        CACHE_CONFIG['ttl']['monitoring']['connection_stats'] = 120  # 2 minutes
        CACHE_CONFIG['ttl']['monitoring']['heartbeat'] = 5  # 5 seconds

        # Integrity TTLs for development - shorter for testing
        CACHE_CONFIG['ttl']['integrity']['check_result'] = 30  # 30 seconds
        CACHE_CONFIG['ttl']['integrity']['discovery_result'] = 120  # 2 minutes
        CACHE_CONFIG['ttl']['integrity']['recovery_state'] = 300  # 5 minutes
        CACHE_CONFIG['ttl']['integrity']['metrics'] = 120  # 2 minutes
        CACHE_CONFIG['ttl']['integrity']['check_basic'] = 15  # 15 seconds
        CACHE_CONFIG['ttl']['integrity']['check_deep'] = 120  # 2 minutes

        CACHE_CONFIG['monitoring']['log_cache_hits'] = True
        CACHE_CONFIG['monitoring']['log_cache_clears'] = True
        CACHE_CONFIG['debug']['enabled'] = True
        CACHE_CONFIG['debug']['verbose_errors'] = True
        CACHE_CONFIG['debug']['trace_operations'] = True

    elif env == "testing":
        # Testing settings
        CACHE_CONFIG['ttl']['vb']['balance'] = 1  # Minimal caching
        CACHE_CONFIG['ttl']['vb']['adapter'] = 5  # Very short for tests
        CACHE_CONFIG['ttl']['market']['quote'] = 1  # Minimal for tests
        CACHE_CONFIG['ttl']['market']['bars'] = 5  # Short for tests
        CACHE_CONFIG['ttl']['account']['balance'] = 2  # Very short
        CACHE_CONFIG['ttl']['options']['quote'] = 1  # Minimal
        CACHE_CONFIG['ttl']['crypto']['quote'] = 1  # Minimal
        CACHE_CONFIG['ttl']['metadata']['conditions'] = 60  # 1 minute for tests
        CACHE_CONFIG['ttl']['hours']['clock'] = 1  # 1 second for tests
        CACHE_CONFIG['ttl']['corporate']['announcements'] = 60  # 1 minute for tests
        CACHE_CONFIG['ttl']['news']['market_news'] = 30  # 30 seconds for tests
        CACHE_CONFIG['ttl']['watchlist']['watchlists'] = 10  # 10 seconds for tests

        # Monitoring TTLs for testing - very short
        CACHE_CONFIG['ttl']['monitoring']['health_status'] = 5  # 5 seconds
        CACHE_CONFIG['ttl']['monitoring']['metrics'] = 60  # 1 minute
        CACHE_CONFIG['ttl']['monitoring']['pool_health'] = 5  # 5 seconds
        CACHE_CONFIG['ttl']['monitoring']['connection_stats'] = 30  # 30 seconds
        CACHE_CONFIG['ttl']['monitoring']['heartbeat'] = 2  # 2 seconds

        # Integrity TTLs for testing - minimal
        CACHE_CONFIG['ttl']['integrity']['check_result'] = 5  # 5 seconds
        CACHE_CONFIG['ttl']['integrity']['discovery_result'] = 30  # 30 seconds
        CACHE_CONFIG['ttl']['integrity']['recovery_state'] = 60  # 1 minute
        CACHE_CONFIG['ttl']['integrity']['metrics'] = 30  # 30 seconds
        CACHE_CONFIG['ttl']['integrity']['alert_history'] = 60  # 1 minute

        CACHE_CONFIG['debug']['fake_miss_rate'] = 10  # 10% fake misses
        CACHE_CONFIG['debug']['pattern_test_mode'] = True  # Safe pattern testing
        CACHE_CONFIG['cleanup']['on_startup'] = False  # Don't cleanup test data
        CACHE_CONFIG['cleanup']['broker']['aggressive_cleanup'] = True  # Test aggressive mode


# Initialize configuration on import
_env = os.getenv('ENVIRONMENT', 'development')
apply_environment_config(_env)
override_from_env()  # Allow env overrides even with dict config