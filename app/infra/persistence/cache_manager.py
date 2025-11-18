# app/infra/persistence/cache_manager.py

"""
Centralized cache management for the entire WellWon system.
Uses dictionary-based configuration for better production management.
ENHANCED: Added TTL lookup methods to avoid direct cache_config imports.
FIXED: Added existence checks before clearing cache to avoid warnings.
"""
import os
from typing import Optional, List, Dict, Any, Union, Callable
import json
import hashlib
import time
import asyncio
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from app.config.cache_config import CACHE_CONFIG, get_cache_config, get_ttl
from app.config.logging_config import get_logger

logger = get_logger(__name__)


class CacheDomain(Enum):
    """Cache domains for different parts of the system"""
    USER = "user"
    AUTH = "auth"
    BROKER = "broker"
    VIRTUAL_BROKER = "vb"
    ACCOUNT = "account"
    ORDER = "order"
    POSITION = "position"
    PORTFOLIO = "portfolio"
    MARKET = "market"
    SYSTEM = "system"
    API = "api"
    # Event Store & CQRS
    EVENT_STORE = "event_store"  # KurrentDB version cache, metadata cache
    AGGREGATE = "aggregate"       # Aggregate instance cache
    SEQUENCE = "sequence"         # Event sequence tracking


class CacheMetrics:
    """Track cache performance metrics"""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.slow_operations = 0
        self.total_operations = 0
        self.total_latency_ms = 0
        self.cache_clears = 0
        self.keys_deleted = 0
        self.reset_time = datetime.now(timezone.utc)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0

    @property
    def avg_latency_ms(self) -> float:
        return (self.total_latency_ms / self.total_operations) if self.total_operations > 0 else 0

    def to_dict(self) -> Dict:
        return {
            'hits': self.hits,
            'misses': self.misses,
            'errors': self.errors,
            'hit_rate': round(self.hit_rate, 2),
            'slow_operations': self.slow_operations,
            'total_operations': self.total_operations,
            'avg_latency_ms': round(self.avg_latency_ms, 2),
            'cache_clears': self.cache_clears,
            'keys_deleted': self.keys_deleted,
            'uptime_seconds': (datetime.now(timezone.utc) - self.reset_time).total_seconds()
        }


class CacheManager:
    """
    Centralized cache management for all WellWon operations.

    Key patterns follow: {prefix}:{domain}:{type}:{identifiers}
    Examples:
    - wellwon:user:profile:{user_id}
    - wellwon:auth:session:{session_id}
    - wellwon:broker:health:{broker_id}:{connection_id}
    - wellwon:vb:adapter:u:{user_id}:c:{connection_id}
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self.metrics = CacheMetrics()
        self._deletion_lock = asyncio.Lock()
        self._background_tasks = []
        self._running = False

        # Initialize from config
        self._init_from_config()

        # DON'T start background tasks in __init__ - use start() method
        logger.info(f"Cache manager initialized (enabled={self.enabled}, prefix={self.key_prefix})")

    async def start(self):
        """Start cache manager background tasks"""
        if self._running:
            logger.warning("Cache manager already running")
            return

        self._running = True

        # Start background tasks if enabled
        if self.cleanup_on_startup:
            task = asyncio.create_task(self._startup_cleanup())
            self._background_tasks.append(task)

        if self.cleanup_interval_hours > 0:
            task = asyncio.create_task(self._periodic_cleanup())
            self._background_tasks.append(task)

        logger.info(f"Cache manager started with {len(self._background_tasks)} background tasks")

        # Log initial metrics
        if self.metrics_enabled:
            logger.info(f"Initial cache metrics: {self.get_metrics()}")

    async def stop(self):
        """Stop cache manager and cleanup"""
        if not self._running:
            logger.debug("Cache manager not running")
            return

        logger.info("Stopping cache manager...")
        self._running = False

        # Cancel all background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
                logger.debug(f"Cancelled task: {task.get_name() if hasattr(task, 'get_name') else 'unnamed'}")

        # Wait for tasks to complete
        if self._background_tasks:
            results = await asyncio.gather(*self._background_tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    logger.error(f"Task {i} error during shutdown: {result}")

        self._background_tasks.clear()

        # Log final metrics
        if self.metrics_enabled:
            logger.info(f"Final cache metrics: {self.get_metrics()}")

        logger.info("Cache manager stopped")

    @property
    def is_running(self) -> bool:
        """Check if cache manager is running"""
        return self._running

    @property
    def background_task_count(self) -> int:
        """Get the number of active background tasks"""
        return len(self._background_tasks)

    def _init_from_config(self):
        """Initialize settings from configuration"""
        # Core settings
        self.enabled = get_cache_config('core.enabled', True)
        self.key_prefix = get_cache_config('core.key_prefix', 'wellwon')
        self.default_ttl = get_cache_config('core.default_ttl', 300)
        self.max_key_length = get_cache_config('core.max_key_length', 256)

        # Redis settings
        self.scan_count = get_cache_config('redis.scan_count', 100)
        self.pipeline_max_size = get_cache_config('redis.pipeline_max_size', 100)

        # Cleanup settings
        self.cleanup_on_startup = get_cache_config('cleanup.on_startup', True)
        self.cleanup_batch_size = get_cache_config('cleanup.batch_size', 1000)
        self.cleanup_interval_hours = get_cache_config('cleanup.interval_hours', 6)
        self.cleanup_max_age_hours = get_cache_config('cleanup.max_age_hours', 24)

        # VB cleanup settings
        self.vb_clear_on_disconnect = get_cache_config('cleanup.vb.clear_on_disconnect', True)
        self.vb_clear_on_reset = get_cache_config('cleanup.vb.clear_on_reset', True)
        self.vb_clear_on_delete = get_cache_config('cleanup.vb.clear_on_delete', True)

        # Broker cleanup settings
        self.broker_clear_on_disconnect = get_cache_config('cleanup.broker.clear_on_disconnect', True)
        self.broker_clear_on_auth_fail = get_cache_config('cleanup.broker.clear_on_auth_fail', True)
        self.broker_aggressive_cleanup = get_cache_config('cleanup.broker.aggressive_cleanup', True)

        # Feature flags
        self.cache_enabled = {
            'user': get_cache_config('features.enable_user', True),
            'auth': get_cache_config('features.enable_auth', True),
            'broker': get_cache_config('features.enable_broker', True),
            'vb': get_cache_config('features.enable_vb', True),
            'trading': get_cache_config('features.enable_trading', True),
            'market': get_cache_config('features.enable_market', True),
            'api': get_cache_config('features.enable_api', True),
            'event_store': get_cache_config('features.enable_event_store', True),
            'aggregate': get_cache_config('features.enable_aggregate', True),
            'sequence': get_cache_config('features.enable_sequence', True),
        }

        # Monitoring settings
        self.metrics_enabled = get_cache_config('monitoring.metrics_enabled', True)
        self.log_slow_ops = get_cache_config('monitoring.log_slow_operations', True)
        # Increased from 50ms to 100ms (2025-11-11) - Complex operations like get_vb_adapter_accounts
        # include deserialization and can take 50-100ms legitimately
        self.slow_op_threshold_ms = get_cache_config('monitoring.slow_operation_threshold_ms', 100)
        self.log_hits = get_cache_config('monitoring.log_cache_hits', False)
        self.log_misses = get_cache_config('monitoring.log_cache_misses', True)

        # Debug settings
        self.debug_mode = get_cache_config('debug.enabled', False)
        self.bypass_cache = get_cache_config('debug.bypass_cache', False)
        self.fake_miss_rate = get_cache_config('debug.fake_miss_rate', 0)
        self.log_keys = get_cache_config('debug.log_keys', False)

    # === TTL LOOKUP METHODS ===
    # These methods allow other components to get TTLs without importing cache_config directly

    def get_module_ttl(self, module_name: str, cache_type: str, default: int = None) -> int:
        """
        Get TTL for a specific module and cache type.
        This allows modules to get TTLs without importing cache_config directly.

        Args:
            module_name: Module name (e.g., 'market', 'account', 'position')
            cache_type: Cache type within module (e.g., 'quote', 'balance', 'list')
            default: Default TTL if not found

        Returns:
            TTL in seconds
        """
        from app.config.cache_config import get_module_ttl as config_get_ttl
        return config_get_ttl(module_name, cache_type, default or self.default_ttl)

    def get_oauth_ttl(self, broker_id: str, token_type: str = 'access_token') -> int:
        """
        Get OAuth TTL for specific broker and token type.

        Args:
            broker_id: Broker identifier ('alpaca', 'tradestation', 'virtual')
            token_type: Type of token ('access_token' or 'refresh_token')

        Returns:
            TTL in seconds
        """
        from app.config.cache_config import get_oauth_ttl as config_get_oauth_ttl
        return config_get_oauth_ttl(broker_id, token_type)

    def get_cache_ttl(self, cache_path: str) -> int:
        """
        Get TTL by cache path (e.g., 'market:quote').

        Args:
            cache_path: Colon-separated cache path

        Returns:
            TTL in seconds
        """
        from app.config.cache_config import get_ttl
        return get_ttl(cache_path)

    # === Helper Methods ===

    def _get_ttl(self, cache_type: str) -> int:
        """Get TTL for cache type from config"""
        return get_ttl(cache_type)

    def _make_key(self, *parts: str) -> str:
        """Create cache key from parts"""
        key = ':'.join([self.key_prefix] + list(parts))

        # Validate key length
        if len(key) > self.max_key_length:
            logger.warning(f"Cache key too long ({len(key)} chars): {key[:50]}...")

        if self.log_keys and self.debug_mode:
            logger.debug(f"Cache key: {key}")

        return key

    def _should_bypass_cache(self, domain: str = None) -> bool:
        """Check if cache should be bypassed"""
        if not self.enabled or self.bypass_cache:
            return True

        if domain and not self.cache_enabled.get(domain, True):
            return True

        # Simulate cache miss for testing
        if self.fake_miss_rate > 0:
            import random
            if random.randint(1, 100) <= self.fake_miss_rate:
                return True

        return False

    async def _track_operation(self, operation: str, start_time: float,
                               success: bool = True, hit: bool = None):
        """Track cache operation metrics"""
        if not self.metrics_enabled:
            return

        elapsed_ms = (time.time() - start_time) * 1000
        self.metrics.total_operations += 1
        self.metrics.total_latency_ms += elapsed_ms

        if not success:
            self.metrics.errors += 1
        elif hit is True:
            self.metrics.hits += 1
            if self.log_hits:
                logger.debug(f"Cache hit: {operation} ({elapsed_ms:.1f}ms)")
        elif hit is False:
            self.metrics.misses += 1
            if self.log_misses:
                logger.debug(f"Cache miss: {operation} ({elapsed_ms:.1f}ms)")

        if elapsed_ms > self.slow_op_threshold_ms:
            self.metrics.slow_operations += 1
            if self.log_slow_ops:
                logger.warning(f"Slow cache operation: {operation} took {elapsed_ms:.1f}ms")

    async def _scan_and_delete(self, pattern: str, batch_delete: bool = True) -> int:
        """Scan and delete keys matching pattern with improved performance"""
        deleted = 0
        keys_found = 0

        try:
            # First, check if any keys exist matching the pattern
            key_sample = []
            async for key in self.redis.scan_iter(match=pattern, count=1):
                key_sample.append(key)
                keys_found += 1
                if keys_found >= 1:  # Just check if at least one key exists
                    break

            if keys_found == 0:
                logger.debug(f"No keys found matching pattern: {pattern}")
                return 0

            # Keys exist, proceed with deletion
            if batch_delete:
                # Use pipeline for batch deletion
                pipe = self.redis.pipeline()
                batch_count = 0

                async for key in self.redis.scan_iter(match=pattern, count=self.scan_count):
                    pipe.delete(key)
                    batch_count += 1

                    # Execute pipeline in batches
                    if batch_count >= self.pipeline_max_size:
                        results = await pipe.execute()
                        deleted += sum(1 for r in results if r)
                        pipe = self.redis.pipeline()
                        batch_count = 0

                # Execute remaining commands
                if batch_count > 0:
                    results = await pipe.execute()
                    deleted += sum(1 for r in results if r)
            else:
                # Single key deletion
                async for key in self.redis.scan_iter(match=pattern, count=self.scan_count):
                    if await self.redis.delete(key):
                        deleted += 1

        except Exception as e:
            logger.error(f"Pattern delete error for {pattern}: {e}")

        if deleted > 0:
            logger.info(f"Deleted {deleted} keys matching pattern: {pattern}")
            self.metrics.keys_deleted += deleted

        return deleted

    # === Generic Operations ===

    async def get(self, key: str, track_metrics: bool = True) -> Optional[str]:
        """Get raw value from cache"""
        if self._should_bypass_cache():
            return None

        start = time.time()
        try:
            value = await self.redis.get(key)
            if track_metrics:
                await self._track_operation(f"GET {key}", start, True, value is not None)
            return value
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            if track_metrics:
                await self._track_operation(f"GET {key}", start, False)
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None,
                  track_metrics: bool = True) -> bool:
        """Set raw value in cache"""
        if self._should_bypass_cache():
            return True

        start = time.time()
        try:
            if ttl:
                result = await self.redis.setex(key, ttl, value)
            else:
                result = await self.redis.set(key, value)

            if track_metrics:
                await self._track_operation(f"SET {key}", start, True)
            return bool(result)
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            if track_metrics:
                await self._track_operation(f"SET {key}", start, False)
            return False

    async def get_json(self, key: str) -> Optional[Dict]:
        """Get and decode JSON data (non-blocking)"""
        data = await self.get(key)
        if data:
            try:
                # Run JSON parsing in thread pool to avoid blocking event loop
                return await asyncio.to_thread(json.loads, data)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in cache for {key}")
        return None

    async def set_json(self, key: str, value: Dict, ttl: Optional[int] = None) -> bool:
        """Encode and set JSON data (non-blocking)"""
        try:
            # Run JSON serialization in thread pool to avoid blocking event loop for large objects
            data = await asyncio.to_thread(json.dumps, value, default=str)
            return await self.set(key, data, ttl)
        except Exception as e:
            logger.error(f"JSON encoding error for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key"""
        if self._should_bypass_cache():
            return True

        try:
            return await self.redis.delete(key) > 0
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if self._should_bypass_cache():
            return 0

        return await self._scan_and_delete(pattern, batch_delete=True)

    async def keys(self, pattern: str) -> list[str]:
        """Get all keys matching pattern"""
        if self._should_bypass_cache():
            return []

        try:
            keys_found = []
            async for key in self.redis.scan_iter(match=pattern, count=self.scan_count):
                # Decode bytes to string if needed
                if isinstance(key, bytes):
                    key = key.decode('utf-8')
                keys_found.append(key)
            return keys_found
        except Exception as e:
            logger.error(f"Error getting keys for pattern {pattern}: {e}")
            return []

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if self._should_bypass_cache():
            return False

        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for {key}: {e}")
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL on existing key"""
        if self._should_bypass_cache():
            return True

        try:
            return await self.redis.expire(key, ttl)
        except Exception as e:
            logger.error(f"Cache expire error for {key}: {e}")
            return False

    # === User & Auth ===

    async def cache_user_profile(self, user_id: str, profile: Dict) -> bool:
        """Cache user profile data"""
        if self._should_bypass_cache('user'):
            return True

        key = self._make_key('user', 'profile', user_id)
        return await self.set_json(key, profile, self._get_ttl('user:profile'))

    async def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """Get cached user profile"""
        if self._should_bypass_cache('user'):
            return None

        key = self._make_key('user', 'profile', user_id)
        return await self.get_json(key)

    async def cache_session(self, session_id: str, session_data: Dict) -> bool:
        """Cache user session"""
        if self._should_bypass_cache('auth'):
            return True

        key = self._make_key('auth', 'session', session_id)
        return await self.set_json(key, session_data, self._get_ttl('auth:session'))

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Get cached session"""
        if self._should_bypass_cache('auth'):
            return None

        key = self._make_key('auth', 'session', session_id)
        return await self.get_json(key)

    async def invalidate_session(self, session_id: str) -> bool:
        """Invalidate user session"""
        key = self._make_key('auth', 'session', session_id)
        return await self.delete(key)

    # === Broker Connections ===

    async def cache_broker_health(
            self, broker_id: str, connection_id: str, health_data: Dict
    ) -> bool:
        """Cache broker health check"""
        if self._should_bypass_cache('broker'):
            return True

        key = self._make_key('broker', 'health', broker_id, connection_id)
        return await self.set_json(key, health_data, self._get_ttl('broker:health'))

    async def get_broker_health(
            self, broker_id: str, connection_id: str
    ) -> Optional[Dict]:
        """Get cached broker health"""
        if self._should_bypass_cache('broker'):
            return None

        key = self._make_key('broker', 'health', broker_id, connection_id)
        return await self.get_json(key)

    # === Virtual Broker ===

    async def cache_vb_adapter_accounts(
            self,
            user_id: str,
            broker_connection_id: str,
            accounts: List[Any]  # Using Any to handle both AccountInfo and dict types
    ) -> None:
        """Cache virtual broker adapter accounts with proper serialization."""
        if not self.enabled or self._should_bypass_cache():
            return

        start_time = time.time()

        # FIXED: Use the correct key format that matches what the account module expects
        # OLD: cache_key = f"{self.key_prefix}vb_adapter:{user_id}:{broker_connection_id}:accounts"
        # NEW: Match the format expected by the account module
        cache_key = f"{self.key_prefix}:vb:adapter:u:{user_id}:c:{broker_connection_id}"

        try:
            # Convert AccountInfo objects to dictionaries for proper JSON serialization
            account_dicts = []
            for account in accounts:
                if hasattr(account, '__dict__'):
                    # Convert AccountInfo to dict using the virtual mapper
                    try:
                        from app.infra.broker_adapters.virtual.mappers import virtual_mapper
                        if hasattr(virtual_mapper, '_object_to_dict'):
                            account_dict = virtual_mapper._object_to_dict(account)
                            account_dicts.append(account_dict)
                        else:
                            # Fallback to dict conversion
                            account_dicts.append(account.__dict__)
                    except ImportError:
                        # Fallback if virtual mapper not available
                        account_dicts.append(account.__dict__)
                elif isinstance(account, dict):
                    # Already a dict
                    account_dicts.append(account)
                else:
                    # Convert to dict as best effort
                    account_dicts.append(dict(account) if hasattr(account, '__iter__') else str(account))

            ttl = self.get_module_ttl('virtual_broker', 'account_list', default=60)
            await self.set_json(cache_key, account_dicts, ttl)

            await self._track_operation('cache_vb_adapter_accounts', start_time, success=True, hit=False)

            if self.log_keys:
                logger.debug(f"Cached {len(accounts)} VB adapter accounts with TTL {ttl}s: {cache_key}")

        except Exception as e:
            logger.error(f"Failed to cache VB adapter accounts for {user_id}:{broker_connection_id}: {e}")
            await self._track_operation('cache_vb_adapter_accounts', start_time, success=False, hit=False)

    async def get_vb_adapter_accounts(
            self,
            user_id: str,
            broker_connection_id: str
    ) -> Optional[List[Any]]:
        """Get cached virtual broker adapter accounts with proper deserialization."""
        if not self.enabled or self._should_bypass_cache():
            return None

        start_time = time.time()

        # FIXED: Use the correct key format that matches what we save
        # OLD: cache_key = f"{self.key_prefix}vb_adapter:{user_id}:{broker_connection_id}:accounts"
        # NEW: Match the format we use when saving
        cache_key = f"{self.key_prefix}:vb:adapter:u:{user_id}:c:{broker_connection_id}"

        try:
            # Use get_json to properly deserialize the data
            cached_data = await self.get_json(cache_key)

            if cached_data is None:
                await self._track_operation('get_vb_adapter_accounts', start_time, success=True, hit=False)
                if self.log_misses:
                    logger.debug(f"Cache miss for VB adapter accounts: {cache_key}")
                return None

            if not isinstance(cached_data, list):
                logger.warning(f"Expected list in VB adapter cache, got {type(cached_data)} for key: {cache_key}")
                await self._track_operation('get_vb_adapter_accounts', start_time, success=False, hit=False)
                return None

            # Convert dictionaries back to AccountInfo objects
            accounts = []
            conversion_errors = 0

            for idx, item in enumerate(cached_data):
                try:
                    # Handle different data types that might be in cache
                    if isinstance(item, str):
                        # If it's still a string, parse it as JSON
                        import json
                        item = json.loads(item)

                    if isinstance(item, dict):
                        # Convert dict back to AccountInfo using the virtual mapper
                        try:
                            from app.infra.broker_adapters.virtual.mappers import virtual_mapper
                            if hasattr(virtual_mapper, '_map_from_dict'):
                                account_info = virtual_mapper._map_from_dict(item)
                                if account_info:
                                    accounts.append(account_info)
                                else:
                                    # Fallback: return as dict if mapper fails
                                    accounts.append(item)
                            else:
                                # Fallback: return as dict if mapper method not available
                                accounts.append(item)
                        except ImportError:
                            # Fallback: return as dict if import fails
                            accounts.append(item)
                        except Exception as mapper_error:
                            logger.debug(f"Mapper conversion failed for item {idx}: {mapper_error}, returning as dict")
                            accounts.append(item)
                    else:
                        logger.warning(f"Unexpected type in VB adapter cache at index {idx}: {type(item)}")
                        conversion_errors += 1

                except Exception as e:
                    logger.error(f"Failed to convert VB adapter cached item at index {idx}: {e}")
                    conversion_errors += 1
                    continue

            # Log conversion warnings if there were issues
            if conversion_errors > 0 or len(accounts) != len(cached_data):
                logger.warning(
                    f"VB adapter cache conversion issues: started with {len(cached_data)} items, "
                    f"converted {len(accounts)} successfully, {conversion_errors} errors"
                )

            await self._track_operation('get_vb_adapter_accounts', start_time, success=True, hit=True)

            if self.log_hits:
                logger.debug(f"Retrieved {len(accounts)} VB adapter accounts from cache: {cache_key}")

            return accounts if accounts else None

        except Exception as e:
            logger.error(f"Failed to get VB adapter accounts for {user_id}:{broker_connection_id}: {e}")
            await self._track_operation('get_vb_adapter_accounts', start_time, success=False, hit=False)
            return None

    async def remove_vb_account_from_adapter(
            self, user_id: str, connection_id: str, account_id: str
    ) -> bool:
        """Remove account from VB adapter cache"""
        accounts = await self.get_vb_adapter_accounts(user_id, connection_id)
        if not accounts:
            return False

        updated = [a for a in accounts if str(a.get('id')) != str(account_id)]

        if updated:
            return await self.cache_vb_adapter_accounts(user_id, connection_id, updated)
        else:
            # FIXED: Use the consistent key format
            # OLD: key = self._make_key('vb', 'adapter', f'u:{user_id}', f'c:{connection_id}')
            # NEW: Use the format that matches cache_vb_adapter_accounts
            key = f"{self.key_prefix}:vb:adapter:u:{user_id}:c:{connection_id}"
            return await self.delete(key)

    async def cache_vb_balance(self, account_id: str, balance: Dict) -> bool:
        """Cache VB account balance"""
        if self._should_bypass_cache('vb'):
            return True

        key = self._make_key('vb', 'balance', account_id)
        return await self.set_json(key, balance, self._get_ttl('vb:balance'))

    async def get_vb_balance(self, account_id: str) -> Optional[Dict]:
        """Get cached VB balance"""
        if self._should_bypass_cache('vb'):
            return None

        key = self._make_key('vb', 'balance', account_id)
        return await self.get_json(key)

    # === Trading Data ===

    async def cache_account_balance(self, account_id: str, balance: Dict) -> bool:
        """Cache account balance"""
        if self._should_bypass_cache('trading'):
            return True

        key = self._make_key('account', 'balance', account_id)
        return await self.set_json(key, balance, self._get_ttl('account:balance'))

    async def get_account_balance(self, account_id: str) -> Optional[Dict]:
        """Get cached balance"""
        if self._should_bypass_cache('trading'):
            return None

        key = self._make_key('account', 'balance', account_id)
        return await self.get_json(key)

    async def cache_order_status(self, order_id: str, status: Dict) -> bool:
        """Cache order status"""
        if self._should_bypass_cache('trading'):
            return True

        key = self._make_key('order', 'status', order_id)
        return await self.set_json(key, status, self._get_ttl('order:status'))

    async def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get cached order status"""
        if self._should_bypass_cache('trading'):
            return None

        key = self._make_key('order', 'status', order_id)
        return await self.get_json(key)

    # === Market Data ===

    async def cache_quote(self, symbol: str, quote: Dict) -> bool:
        """Cache market quote"""
        if self._should_bypass_cache('market'):
            return True

        key = self._make_key('market', 'quote', symbol.upper())
        return await self.set_json(key, quote, self._get_ttl('market:quote'))

    async def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get cached quote"""
        if self._should_bypass_cache('market'):
            return None

        key = self._make_key('market', 'quote', symbol.upper())
        return await self.get_json(key)

    # === API Response Caching ===

    def _api_cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate cache key for API responses"""
        param_str = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
        clean_endpoint = endpoint.replace('/', '_').strip('_')
        return self._make_key('api', 'response', clean_endpoint, param_hash)

    async def cache_api_response(
            self, endpoint: str, params: Dict, response: Dict, ttl: Optional[int] = None
    ) -> bool:
        """Cache API response"""
        if self._should_bypass_cache('api'):
            return True

        key = self._api_cache_key(endpoint, params)
        ttl = ttl or self._get_ttl('api:response')

        data = {
            'response': response,
            'cached_at': datetime.now(timezone.utc).isoformat(),
            'endpoint': endpoint,
            'params': params
        }

        return await self.set_json(key, data, ttl)

    async def get_api_response(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """Get cached API response"""
        if self._should_bypass_cache('api'):
            return None

        key = self._api_cache_key(endpoint, params)
        data = await self.get_json(key)

        if data:
            return data.get('response')
        return None

    # === Rate Limiting ===

    async def increment_rate_limit(
            self, resource: str, identifier: str, window: int = None
    ) -> int:
        """Increment rate limit counter"""
        window = window or get_cache_config('rate_limiting.default_window', 60)
        key = self._make_key('ratelimit', resource, identifier)

        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, window)
            return count
        except Exception as e:
            logger.error(f"Rate limit increment error: {e}")
            return 0

    async def check_rate_limit(
            self, resource: str, identifier: str, limit: int = None
    ) -> bool:
        """Check if rate limit exceeded (returns True if OK)"""
        if limit is None:
            limit = get_cache_config(f'rate_limiting.limits.{resource}',
                                     get_cache_config('rate_limiting.default_limit', 100))

        key = self._make_key('ratelimit', resource, identifier)

        try:
            count = await self.redis.get(key)
            return int(count or 0) < limit
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return True  # Allow on error

    async def reset_rate_limit(self, resource: str, identifier: str) -> bool:
        """Reset rate limit counter"""
        key = self._make_key('ratelimit', resource, identifier)
        return await self.delete(key)

    # === ENHANCED Cleanup Operations ===

    async def clear_broker_connection(
            self, broker_id: str, user_id: str, connection_id: str
    ) -> int:
        """
        ENHANCED: Clear ALL broker connection caches - comprehensive cleanup.
        This is critical to prevent duplicate accounts on reconnection.
        FIXED: Check if keys exist before attempting to clear.
        """
        if not self.broker_clear_on_disconnect:
            logger.debug("Broker cache clear on disconnect disabled")
            return 0

        async with self._deletion_lock:
            logger.info(f"Starting comprehensive cache cleanup for broker {broker_id}, "
                        f"connection {connection_id}, user {user_id}")

            self.metrics.cache_clears += 1

            # Build comprehensive patterns to catch ALL possible cache entries
            patterns = [
                # Direct broker patterns
                f"{self.key_prefix}:broker:*:{broker_id}*",
                f"{self.key_prefix}:broker:*:{connection_id}*",
                f"{self.key_prefix}:broker:*:*:{connection_id}*",
                f"{self.key_prefix}:broker:health:{broker_id}:{connection_id}",

                # Account patterns linked to this broker/connection
                f"{self.key_prefix}:account:*:b:{broker_id}*",
                f"{self.key_prefix}:account:*:c:{connection_id}*",

                # Virtual broker patterns
                f"{self.key_prefix}:vb:*:b:{broker_id}*",
                f"{self.key_prefix}:vb:*:c:{connection_id}*",
                f"{self.key_prefix}:vb:adapter:u:{user_id}:c:{connection_id}*",

                # Trading data patterns
                f"{self.key_prefix}:order:*:b:{broker_id}*",
                f"{self.key_prefix}:order:*:c:{connection_id}*",
                f"{self.key_prefix}:position:*:b:{broker_id}*",
                f"{self.key_prefix}:position:*:c:{connection_id}*",

                # API cache patterns
                f"{self.key_prefix}:api:*:*{broker_id}*",
                f"{self.key_prefix}:api:*:*{connection_id}*",
                f"{self.key_prefix}:api:*:*{user_id}*",

                # Rate limiting patterns
                f"{self.key_prefix}:ratelimit:*:{broker_id}*",
                f"{self.key_prefix}:ratelimit:*:{connection_id}*",
            ]

            # If aggressive cleanup is enabled, add more patterns
            if self.broker_aggressive_cleanup:
                patterns.extend([
                    # Clear ALL account balances for this user
                    f"{self.key_prefix}:account:balance:*",
                    f"{self.key_prefix}:vb:balance:*",
                    # Clear user-specific caches
                    f"{self.key_prefix}:user:accounts:{user_id}",
                    f"{self.key_prefix}:user:brokers:{user_id}",
                ])

            total_deleted = 0

            for pattern in patterns:
                try:
                    deleted = await self._scan_and_delete(pattern, batch_delete=True)
                    total_deleted += deleted
                except Exception as e:
                    logger.error(f"Error clearing pattern {pattern}: {e}")

            if total_deleted > 0:
                logger.info(f"Cleared {total_deleted} cache keys for broker {broker_id} connection {connection_id}")
            else:
                logger.debug(f"No cache keys found to clear for broker {broker_id} connection {connection_id}")

            return total_deleted

    async def clear_account_cache(
            self, account_id: str, user_id: str, broker_id: str = None,
            connection_id: str = None
    ) -> int:
        """
        ENHANCED: Clear all caches for a specific account.
        Used when an account is deleted or marked as deleted.
        FIXED: Check existence before clearing.
        """
        async with self._deletion_lock:
            logger.info(f"Clearing all cache for account {account_id}")

            self.metrics.cache_clears += 1

            patterns = [
                # Account-specific patterns
                f"{self.key_prefix}:account:*:{account_id}*",
                f"{self.key_prefix}:account:balance:{account_id}",

                # Order patterns for this account
                f"{self.key_prefix}:order:*:aid:{account_id}*",
                f"{self.key_prefix}:order:*:account:{account_id}*",

                # Position patterns
                f"{self.key_prefix}:position:*:{account_id}*",

                # Virtual broker account patterns
                f"{self.key_prefix}:vb:account:{account_id}",
                f"{self.key_prefix}:vb:balance:{account_id}",
                f"{self.key_prefix}:vb:position:{account_id}*",
                f"{self.key_prefix}:vb:order:*:aid:{account_id}",
            ]

            # Also clear user/broker/connection related caches
            if user_id:
                patterns.extend([
                    f"{self.key_prefix}:user:accounts:{user_id}",
                    f"{self.key_prefix}:api:*:*{user_id}*",
                ])

            if broker_id:
                patterns.append(f"{self.key_prefix}:broker:accounts:{broker_id}*")

            if connection_id:
                # Remove from VB adapter cache
                await self.remove_vb_account_from_adapter(user_id, connection_id, account_id)
                patterns.append(f"{self.key_prefix}:vb:adapter:*:c:{connection_id}*")

            total_deleted = 0
            for pattern in patterns:
                deleted = await self._scan_and_delete(pattern, batch_delete=True)
                total_deleted += deleted

            if total_deleted > 0:
                logger.info(f"Cleared {total_deleted} cache keys for account {account_id}")
            else:
                logger.debug(f"No cache keys found to clear for account {account_id}")

            return total_deleted

    async def clear_all_user_broker_data(
            self, user_id: str, broker_id: str = None
    ) -> int:
        """
        Nuclear option: Clear ALL cache data for a user's broker connections.
        Use when we need to ensure absolutely no stale data remains.
        FIXED: Log as warning instead of error when intentionally clearing.
        """
        async with self._deletion_lock:
            logger.warning(f"NUCLEAR CACHE CLEAR: Clearing ALL cache for user {user_id} "
                           f"broker {broker_id or 'ALL'}")

            self.metrics.cache_clears += 1

            patterns = [
                # User patterns
                f"{self.key_prefix}:*:*{user_id}*",
            ]

            if broker_id:
                patterns.append(f"{self.key_prefix}:*:*{broker_id}*")

            total_deleted = 0
            for pattern in patterns:
                deleted = await self._scan_and_delete(pattern, batch_delete=True)
                total_deleted += deleted

            if total_deleted > 0:
                logger.warning(f"NUCLEAR CACHE CLEAR: Deleted {total_deleted} keys")
            else:
                logger.info(f"NUCLEAR CACHE CLEAR: No keys found to delete")

            return total_deleted

    async def clear_user_cache(self, user_id: str) -> int:
        """Clear all caches for a user"""
        patterns = [
            f"{self.key_prefix}:user:*:{user_id}",
            f"{self.key_prefix}:auth:*:u:{user_id}*",
            f"{self.key_prefix}:broker:*:u:{user_id}*",
            f"{self.key_prefix}:vb:*:u:{user_id}*",
            f"{self.key_prefix}:account:*:u:{user_id}*",
            f"{self.key_prefix}:ratelimit:*:{user_id}",
        ]

        total_deleted = 0
        for pattern in patterns:
            deleted = await self.delete_pattern(pattern)
            total_deleted += deleted

        if total_deleted > 0:
            logger.info(f"Cleared {total_deleted} cache keys for user {user_id}")
        else:
            logger.debug(f"No cache keys found to clear for user {user_id}")

        return total_deleted

    async def clear_connection_cache(self, connection_id: str) -> int:
        """Clear all caches for a connection"""
        patterns = [
            f"{self.key_prefix}:broker:*:c:{connection_id}*",
            f"{self.key_prefix}:vb:*:c:{connection_id}*",
        ]

        total_deleted = 0
        for pattern in patterns:
            deleted = await self.delete_pattern(pattern)
            total_deleted += deleted

        if total_deleted > 0:
            logger.info(f"Cleared {total_deleted} cache keys for connection {connection_id}")
        else:
            logger.debug(f"No cache keys found to clear for connection {connection_id}")

        return total_deleted

    async def clear_vb_connection(self, user_id: str, connection_id: str) -> int:
        """Clear virtual broker connection caches"""
        if not self.vb_clear_on_disconnect:
            logger.debug("VB cache clear on disconnect disabled")
            return 0

        patterns = [
            f"{self.key_prefix}:vb:adapter:u:{user_id}:c:{connection_id}",
            f"{self.key_prefix}:vb:*:c:{connection_id}*",
            f"{self.key_prefix}:vb:*:u:{user_id}:c:{connection_id}*",
        ]

        # OPTIMIZED (Nov 2025): Parallel pattern deletion for faster cache clearing
        delete_tasks = [self.delete_pattern(pattern) for pattern in patterns]
        results = await asyncio.gather(*delete_tasks, return_exceptions=True)

        # Sum up successful deletions, ignore errors
        total_deleted = sum(r for r in results if isinstance(r, int))

        if total_deleted > 0:
            logger.info(f"Cleared {total_deleted} VB cache keys for connection {connection_id}")
        else:
            logger.debug(f"No VB cache keys found to clear for connection {connection_id}")

        return total_deleted

    async def clear_vb_account(
            self, account_id: str, user_id: str, connection_id: str
    ) -> int:
        """Clear all caches for a VB account"""
        if not self.vb_clear_on_delete:
            logger.debug("VB cache clear on delete disabled")
            return 0

        # Remove from adapter cache first
        await self.remove_vb_account_from_adapter(user_id, connection_id, account_id)

        # Clear account-specific caches
        patterns = [
            f"{self.key_prefix}:vb:account:{account_id}",
            f"{self.key_prefix}:vb:balance:{account_id}",
            f"{self.key_prefix}:vb:position:{account_id}*",
            f"{self.key_prefix}:vb:order:*:aid:{account_id}",
        ]

        total_deleted = 0
        for pattern in patterns:
            deleted = await self.delete_pattern(pattern)
            total_deleted += deleted

        if total_deleted > 0:
            logger.info(f"Cleared {total_deleted} cache keys for VB account {account_id}")
        else:
            logger.debug(f"No cache keys found to clear for VB account {account_id}")

        return total_deleted

    async def clear_domain(self, domain: CacheDomain) -> int:
        """Clear all caches for a domain"""
        pattern = f"{self.key_prefix}:{domain.value}:*"
        deleted = await self.delete_pattern(pattern)

        if deleted > 0:
            logger.warning(f"Cleared {deleted} cache keys for domain {domain.value}")
        else:
            logger.info(f"No cache keys found to clear for domain {domain.value}")

        return deleted

    async def clear_all(self) -> int:
        """Clear ALL caches (use with caution)"""
        pattern = f"{self.key_prefix}:*"
        deleted = await self.delete_pattern(pattern)

        if deleted > 0:
            logger.warning(f"Cleared ALL {deleted} cache keys")
        else:
            logger.info("No cache keys found to clear")

        return deleted

    # === Maintenance Operations ===

    async def _startup_cleanup(self):
        """Clean up stale entries on startup"""
        try:
            logger.info("Running startup cache cleanup...")

            # Clean up orphaned rate limit keys
            deleted = await self.delete_pattern(f"{self.key_prefix}:ratelimit:*")
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} rate limit keys")

            # Clean up expired sessions
            deleted = await self.delete_pattern(f"{self.key_prefix}:auth:session:*")
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} session keys")

        except Exception as e:
            logger.error(f"Startup cleanup error: {e}")

    async def _periodic_cleanup(self):
        """Run periodic cache cleanup"""
        while self._running:
            try:
                # Wait for the configured interval
                await asyncio.sleep(self.cleanup_interval_hours * 3600)

                # Check if still running after sleep
                if not self._running:
                    logger.debug("Periodic cleanup stopping - manager no longer running")
                    break

                logger.info("Running periodic cache cleanup...")

                # Add cleanup logic here
                # For now, just log metrics
                if self.metrics_enabled:
                    metrics = self.metrics.to_dict()
                    logger.info(f"Cache metrics: {metrics}")

                # Could add more cleanup tasks here like:
                # - Clear orphaned keys
                # - Compact memory
                # - Archive old data

            except asyncio.CancelledError:
                logger.info("Periodic cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Periodic cleanup error: {e}", exc_info=True)
                # Continue running even if cleanup fails
                if self._running:
                    await asyncio.sleep(60)  # Brief pause before retry

    # === Metrics & Monitoring ===

    def get_metrics(self) -> Dict:
        """Get cache performance metrics"""
        return self.metrics.to_dict()

    def reset_metrics(self):
        """Reset cache metrics"""
        self.metrics = CacheMetrics()
        logger.info("Cache metrics reset")

    async def eval_script(self, script: str, keys: list, args: list) -> Any:
        """Execute a Lua script in Redis for atomic operations like rate limiting"""
        if not self.redis:
            raise RuntimeError("Redis client not available for script execution")

        start_time = time.time()
        try:
            # Convert all args to strings as Redis expects
            str_args = [str(arg) for arg in args]

            # Use Redis EVAL command
            result = await self.redis.eval(script, len(keys), *keys, *str_args)

            # Track metrics if enabled
            if self.metrics_enabled:
                duration_ms = (time.time() - start_time) * 1000
                self.metrics.total_operations += 1
                self.metrics.total_latency_ms += duration_ms

                if duration_ms > self.slow_op_threshold_ms:
                    self.metrics.slow_operations += 1
                    if self.log_slow_ops:
                        logger.warning(f"Slow Redis script execution: {duration_ms:.2f}ms")

            return result

        except Exception as e:
            if self.metrics_enabled:
                self.metrics.errors += 1
            logger.error(f"Failed to execute Lua script: {e}")
            raise

    async def script_load(self, script: str) -> str:
        """Load a Lua script into Redis and return its SHA hash for later execution"""
        if not self.redis:
            raise RuntimeError("Redis client not available for script loading")

        try:
            sha = await self.redis.script_load(script)
            logger.debug(f"Loaded Lua script, SHA: {sha}")
            return sha

        except Exception as e:
            logger.error(f"Failed to load Lua script: {e}")
            raise

    async def evalsha(self, sha: str, keys: list, args: list) -> Any:
        """Execute a previously loaded Lua script by its SHA hash"""
        if not self.redis:
            raise RuntimeError("Redis client not available for script execution")

        start_time = time.time()
        try:
            # Convert all args to strings as Redis expects
            str_args = [str(arg) for arg in args]

            # Use Redis EVALSHA command
            result = await self.redis.evalsha(sha, len(keys), *keys, *str_args)

            # Track metrics if enabled
            if self.metrics_enabled:
                duration_ms = (time.time() - start_time) * 1000
                self.metrics.total_operations += 1
                self.metrics.total_latency_ms += duration_ms

                if duration_ms > self.slow_op_threshold_ms:
                    self.metrics.slow_operations += 1
                    if self.log_slow_ops:
                        logger.warning(f"Slow Redis EVALSHA execution: {duration_ms:.2f}ms")

            return result

        except Exception as e:
            if self.metrics_enabled:
                self.metrics.errors += 1

            # If script not found, fall back to eval_script
            if "NOSCRIPT" in str(e):
                logger.warning(f"Script SHA {sha} not found, falling back to eval_script")
                # This would require the original script, which we don't have here
                # The caller should handle this case
                raise

            logger.error(f"Failed to execute Lua script by SHA {sha}: {e}")
            raise

    async def script_exists(self, *shas: str) -> list:
        """Check if one or more scripts exist in Redis by their SHA hashes"""
        if not self.redis:
            raise RuntimeError("Redis client not available")

        try:
            return await self.redis.script_exists(*shas)
        except Exception as e:
            logger.error(f"Failed to check script existence: {e}")
            raise

    async def script_flush(self) -> bool:
        """Remove all cached scripts from Redis"""
        if not self.redis:
            raise RuntimeError("Redis client not available")

        try:
            await self.redis.script_flush()
            logger.info("Flushed all cached Redis scripts")
            return True
        except Exception as e:
            logger.error(f"Failed to flush Redis scripts: {e}")
            return False

    async def health_check(self) -> Dict:
        """Check cache health"""
        try:
            # Test basic operations
            test_key = self._make_key('health', 'check')
            test_value = str(datetime.now(timezone.utc).timestamp())

            # Test set
            set_ok = await self.set(test_key, test_value, 10, track_metrics=False)

            # Test get
            get_value = await self.get(test_key, track_metrics=False)
            get_ok = get_value == test_value

            # Test delete
            delete_ok = await self.delete(test_key)

            # Get info
            info = await self.redis.info()

            return {
                'healthy': set_ok and get_ok and delete_ok,
                'operations': {
                    'set': set_ok,
                    'get': get_ok,
                    'delete': delete_ok
                },
                'redis': {
                    'connected': True,
                    'version': info.get('redis_version', 'unknown'),
                    'used_memory_human': info.get('used_memory_human', 'unknown'),
                    'connected_clients': info.get('connected_clients', 0)
                },
                'metrics': self.get_metrics() if self.metrics_enabled else None,
                'config': {
                    'source': 'cache_config.py',
                    'environment': os.getenv('ENVIRONMENT', 'development'),
                    'key_prefix': self.key_prefix,
                    'debug_mode': self.debug_mode,
                    'aggressive_cleanup': self.broker_aggressive_cleanup
                }
            }

        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'metrics': self.get_metrics() if self.metrics_enabled else None
            }


# === Singleton Instance ===

_cache_manager: Optional[CacheManager] = None


def get_cache_manager(redis_client=None) -> CacheManager:
    """
    Get or create cache manager singleton.
    Note: Call start() after getting the manager for the first time.
    """
    global _cache_manager

    if _cache_manager is None:
        if redis_client is None:
            from app.infra.persistence.redis_client import get_global_client
            redis_client = get_global_client()

        _cache_manager = CacheManager(redis_client)
        logger.info("Created cache manager singleton - remember to call start()")

    return _cache_manager


async def initialize_cache_manager(redis_client=None) -> CacheManager:
    """
    Initialize and start the cache manager.
    This should be called once during application startup.
    """
    cache_manager = get_cache_manager(redis_client)

    if not cache_manager.is_running:
        await cache_manager.start()
        logger.info("Cache manager initialized and started")
    else:
        logger.debug("Cache manager already running")

    return cache_manager


async def shutdown_cache_manager():
    """
    Shutdown the cache manager.
    This should be called during application shutdown.
    """
    global _cache_manager

    if _cache_manager and _cache_manager.is_running:
        await _cache_manager.stop()
        logger.info("Cache manager shutdown complete")

    # Optionally reset the singleton
    # _cache_manager = None


# === Cache Decorators ===

def cached(
        cache_type: str,
        ttl: Optional[int] = None,
        key_func: Optional[Callable] = None
):
    """
    Decorator for caching function results.

    Usage:
        @cached('user:profile', ttl=3600)
        async def get_user_profile(user_id: str) -> Dict:
            # expensive operation
            return profile
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache_manager()

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = cache._make_key(cache_type, *key_parts)

            # Try to get from cache
            cached_value = await cache.get_json(cache_key)
            if cached_value is not None:
                return cached_value

            # Call function
            result = await func(*args, **kwargs)

            # Cache result
            if result is not None:
                await cache.set_json(cache_key, result, ttl or cache._get_ttl(cache_type))

            return result

        return wrapper

    return decorator


def cache_invalidate(
        patterns: List[str]
):
    """
    Decorator to invalidate cache patterns after function execution.

    Usage:
        @cache_invalidate(['user:profile:{user_id}', 'user:settings:{user_id}'])
        async def update_user_profile(user_id: str, data: Dict):
            # update profile
            return updated
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Call function
            result = await func(*args, **kwargs)

            # Invalidate cache patterns
            cache = get_cache_manager()
            for pattern in patterns:
                # Format pattern with args/kwargs
                formatted = pattern.format(*args, **kwargs)
                await cache.delete_pattern(cache.key_prefix + ':' + formatted)

            return result

        return wrapper

    return decorator