# =============================================================================
# File: app/config/cache_config.py
# Description: Unified Cache Management Configuration
# UPDATED: Using BaseConfig pattern with Pydantic v2
# =============================================================================

from functools import lru_cache
from typing import Dict, Any, Optional
from pydantic import Field, BaseModel
from pydantic_settings import SettingsConfigDict

from app.common.base.base_config import BaseConfig


# =============================================================================
# Nested Configuration Models (for structured access)
# =============================================================================

class CoreCacheSettings(BaseModel):
    """Core cache settings"""
    enabled: bool = True
    key_prefix: str = "wellwon"
    default_ttl: int = 300  # 5 minutes
    max_key_length: int = 256
    compression_enabled: bool = False
    compression_threshold: int = 1024


class RedisCacheSettings(BaseModel):
    """Redis connection settings for cache"""
    decode_responses: bool = True
    scan_count: int = 100
    pipeline_max_size: int = 100
    max_connections: int = 150
    socket_keepalive: int = 60
    socket_timeout: float = 10.0
    socket_connect_timeout: float = 3.0


class MonitoringSettings(BaseModel):
    """Cache monitoring settings"""
    metrics_enabled: bool = True
    metrics_interval_sec: int = 60
    log_slow_operations: bool = True
    slow_operation_threshold_ms: int = 50
    log_cache_hits: bool = False
    log_cache_misses: bool = True
    log_cache_clears: bool = True
    track_hit_rate: bool = True
    track_latency: bool = True
    track_clears: bool = True


class CleanupSettings(BaseModel):
    """Cache cleanup settings"""
    on_startup: bool = True
    batch_size: int = 1000
    interval_hours: int = 6
    max_age_hours: int = 24


class DebugSettings(BaseModel):
    """Debug settings"""
    enabled: bool = False
    bypass_cache: bool = False
    fake_miss_rate: int = 0
    log_keys: bool = False
    stats_endpoint: bool = True
    verbose_errors: bool = False
    trace_operations: bool = False


# =============================================================================
# Main Cache Configuration
# =============================================================================

class CacheConfig(BaseConfig):
    """
    Unified cache configuration using Pydantic v2 BaseConfig pattern.
    Provides structured access to cache settings via env vars.
    """

    model_config = SettingsConfigDict(
        **BaseConfig.model_config,
        env_prefix='CACHE_',
    )

    # =========================================================================
    # Core Settings
    # =========================================================================
    enabled: bool = Field(default=True, description="Cache enabled")
    key_prefix: str = Field(default="wellwon", description="Cache key prefix")
    default_ttl: int = Field(default=300, description="Default TTL in seconds")

    # =========================================================================
    # Environment
    # =========================================================================
    environment: str = Field(default="development", description="Environment")

    # =========================================================================
    # Redis Settings
    # =========================================================================
    redis_max_connections: int = Field(default=150, description="Max Redis connections")
    redis_socket_timeout: float = Field(default=10.0, description="Socket timeout")
    redis_socket_connect_timeout: float = Field(default=3.0, description="Connect timeout")

    # =========================================================================
    # TTL Settings - Flat structure for env var compatibility
    # =========================================================================
    # User & Auth
    ttl_user_profile: int = Field(default=3600, description="User profile TTL")
    ttl_user_settings: int = Field(default=3600, description="User settings TTL")
    ttl_auth_session: int = Field(default=3600, description="Auth session TTL")
    ttl_auth_token: int = Field(default=1800, description="Auth token TTL")

    # Account
    ttl_account_info: int = Field(default=300, description="Account info TTL")
    ttl_account_balance: int = Field(default=30, description="Account balance TTL")
    ttl_account_list: int = Field(default=120, description="Account list TTL")

    # Market
    ttl_market_quote: int = Field(default=5, description="Market quote TTL")
    ttl_market_bars: int = Field(default=60, description="Market bars TTL")
    ttl_market_hours: int = Field(default=86400, description="Market hours TTL")
    ttl_market_symbols: int = Field(default=3600, description="Market symbols TTL")

    # Order & Position
    ttl_order_status: int = Field(default=10, description="Order status TTL")
    ttl_order_history: int = Field(default=300, description="Order history TTL")
    ttl_position_list: int = Field(default=30, description="Position list TTL")
    ttl_position_detail: int = Field(default=20, description="Position detail TTL")

    # Portfolio
    ttl_portfolio_summary: int = Field(default=60, description="Portfolio summary TTL")
    ttl_portfolio_activities: int = Field(default=120, description="Portfolio activities TTL")

    # Event Store & CQRS
    ttl_event_store_version: int = Field(default=60, description="Event store version TTL")
    ttl_aggregate_instance: int = Field(default=60, description="Aggregate instance TTL")
    ttl_sequence_tracking: int = Field(default=60, description="Sequence tracking TTL")

    # System
    ttl_system_config: int = Field(default=3600, description="System config TTL")
    ttl_system_status: int = Field(default=60, description="System status TTL")

    # =========================================================================
    # Monitoring Settings
    # =========================================================================
    metrics_enabled: bool = Field(default=True, description="Enable metrics")
    metrics_interval_sec: int = Field(default=60, description="Metrics interval")
    log_slow_operations: bool = Field(default=True, description="Log slow operations")
    slow_operation_threshold_ms: int = Field(default=50, description="Slow op threshold")
    log_cache_hits: bool = Field(default=False, description="Log cache hits")
    log_cache_misses: bool = Field(default=True, description="Log cache misses")
    log_cache_clears: bool = Field(default=True, description="Log cache clears")

    # =========================================================================
    # Cleanup Settings
    # =========================================================================
    cleanup_on_startup: bool = Field(default=True, description="Cleanup on startup")
    cleanup_batch_size: int = Field(default=1000, description="Cleanup batch size")
    cleanup_interval_hours: int = Field(default=6, description="Cleanup interval")
    cleanup_max_age_hours: int = Field(default=24, description="Max age for cleanup")

    # =========================================================================
    # Feature Flags
    # =========================================================================
    enable_user_cache: bool = Field(default=True, description="Enable user cache")
    enable_auth_cache: bool = Field(default=True, description="Enable auth cache")
    enable_market_cache: bool = Field(default=True, description="Enable market cache")
    enable_api_cache: bool = Field(default=True, description="Enable API cache")
    write_through: bool = Field(default=True, description="Write-through caching")
    lazy_load: bool = Field(default=True, description="Lazy load caching")
    auto_retry: bool = Field(default=True, description="Auto retry on failure")

    # =========================================================================
    # Limits
    # =========================================================================
    max_memory_mb: int = Field(default=1024, description="Max memory in MB")
    max_entries_per_key: int = Field(default=1000, description="Max entries per key")
    max_key_size: int = Field(default=250, description="Max key size")
    max_value_size: int = Field(default=1048576, description="Max value size (1MB)")
    max_pipeline_size: int = Field(default=100, description="Max pipeline size")

    # =========================================================================
    # Rate Limiting
    # =========================================================================
    rate_limit_window: int = Field(default=60, description="Rate limit window (sec)")
    rate_limit_default: int = Field(default=100, description="Default rate limit")
    rate_limit_api: int = Field(default=1000, description="API rate limit")
    rate_limit_auth: int = Field(default=10, description="Auth rate limit")
    rate_limit_market: int = Field(default=2000, description="Market data rate limit")

    # =========================================================================
    # Debug Settings
    # =========================================================================
    debug_enabled: bool = Field(default=False, description="Debug mode")
    debug_bypass_cache: bool = Field(default=False, description="Bypass cache")
    debug_verbose_errors: bool = Field(default=False, description="Verbose errors")
    debug_trace_operations: bool = Field(default=False, description="Trace operations")

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def get_ttl(self, domain: str, cache_type: str) -> int:
        """Get TTL for domain:cache_type pattern."""
        attr_name = f"ttl_{domain}_{cache_type}"
        return getattr(self, attr_name, self.default_ttl)

    def get_core_settings(self) -> CoreCacheSettings:
        """Get core cache settings as nested object."""
        return CoreCacheSettings(
            enabled=self.enabled,
            key_prefix=self.key_prefix,
            default_ttl=self.default_ttl,
        )

    def get_redis_settings(self) -> RedisCacheSettings:
        """Get Redis settings as nested object."""
        return RedisCacheSettings(
            max_connections=self.redis_max_connections,
            socket_timeout=self.redis_socket_timeout,
            socket_connect_timeout=self.redis_socket_connect_timeout,
        )

    def get_monitoring_settings(self) -> MonitoringSettings:
        """Get monitoring settings as nested object."""
        return MonitoringSettings(
            metrics_enabled=self.metrics_enabled,
            metrics_interval_sec=self.metrics_interval_sec,
            log_slow_operations=self.log_slow_operations,
            slow_operation_threshold_ms=self.slow_operation_threshold_ms,
            log_cache_hits=self.log_cache_hits,
            log_cache_misses=self.log_cache_misses,
            log_cache_clears=self.log_cache_clears,
        )

    def get_cleanup_settings(self) -> CleanupSettings:
        """Get cleanup settings as nested object."""
        return CleanupSettings(
            on_startup=self.cleanup_on_startup,
            batch_size=self.cleanup_batch_size,
            interval_hours=self.cleanup_interval_hours,
            max_age_hours=self.cleanup_max_age_hours,
        )

    def get_debug_settings(self) -> DebugSettings:
        """Get debug settings as nested object."""
        return DebugSettings(
            enabled=self.debug_enabled,
            bypass_cache=self.debug_bypass_cache,
            verbose_errors=self.debug_verbose_errors,
            trace_operations=self.debug_trace_operations,
        )

    def apply_environment_overrides(self) -> 'CacheConfig':
        """Apply environment-specific overrides."""
        overrides = {}

        if self.environment == "production":
            overrides.update({
                'ttl_market_quote': 10,
                'ttl_market_bars': 120,
                'ttl_account_balance': 60,
                'log_cache_hits': False,
                'log_cache_misses': False,
                'debug_enabled': False,
                'cleanup_interval_hours': 24,
            })
        elif self.environment == "development":
            overrides.update({
                'ttl_market_quote': 2,
                'ttl_market_bars': 30,
                'ttl_account_balance': 15,
                'log_cache_hits': True,
                'log_cache_clears': True,
                'debug_enabled': True,
                'debug_verbose_errors': True,
                'debug_trace_operations': True,
            })
        elif self.environment == "testing":
            overrides.update({
                'ttl_market_quote': 1,
                'ttl_market_bars': 5,
                'ttl_account_balance': 2,
                'cleanup_on_startup': False,
            })

        if overrides:
            return CacheConfig(**{**self.model_dump(), **overrides})
        return self


# =============================================================================
# Factory Function
# =============================================================================

@lru_cache(maxsize=1)
def get_cache_config() -> CacheConfig:
    """Get cache configuration singleton (cached)."""
    config = CacheConfig()
    return config.apply_environment_overrides()


def reset_cache_config() -> None:
    """Reset config singleton (for testing)."""
    get_cache_config.cache_clear()


# =============================================================================
# Backward Compatibility - Dict-based access
# =============================================================================

def get_ttl(cache_type: str) -> int:
    """
    Get TTL for a specific cache type.
    Backward compatible with 'domain:type' format.
    """
    config = get_cache_config()
    parts = cache_type.split(':')
    if len(parts) == 2:
        return config.get_ttl(parts[0], parts[1])
    return config.default_ttl


def get_module_ttl(module_name: str, cache_type: str, default: int = None) -> int:
    """Get TTL for a specific module and cache type."""
    config = get_cache_config()
    ttl = config.get_ttl(module_name, cache_type)
    if ttl != config.default_ttl:
        return ttl
    return default if default is not None else config.default_ttl


def get_cache_config_dict(path: str, default: Any = None) -> Any:
    """
    Backward compatible dict access.
    Maps dot paths to config attributes.
    """
    config = get_cache_config()

    # Map common paths to new attribute names
    path_mapping = {
        'core.enabled': 'enabled',
        'core.key_prefix': 'key_prefix',
        'core.default_ttl': 'default_ttl',
        'monitoring.metrics_enabled': 'metrics_enabled',
        'monitoring.log_cache_hits': 'log_cache_hits',
        'debug.enabled': 'debug_enabled',
        'cleanup.on_startup': 'cleanup_on_startup',
    }

    if path in path_mapping:
        return getattr(config, path_mapping[path], default)

    # Try TTL paths
    if path.startswith('ttl.'):
        parts = path.replace('ttl.', '').split('.')
        if len(parts) == 2:
            attr_name = f"ttl_{parts[0]}_{parts[1]}"
            return getattr(config, attr_name, default)

    return default
