# app/infra/persistence/cache_manager.py

"""
Centralized cache management for WellWon platform.
Uses dictionary-based configuration for better production management.
"""
import os
from typing import Optional, List, Dict, Any, Callable
import json
import hashlib
import time
import asyncio
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from app.config.cache_config import CACHE_CONFIG, get_cache_config, get_ttl
from app.config.logging_config import get_logger

logger = get_logger(__name__)


class CacheDomain(Enum):
    """Cache domains for different parts of the system"""
    USER = "user"
    AUTH = "auth"
    SYSTEM = "system"
    API = "api"
    # Event Store & CQRS
    EVENT_STORE = "event_store"
    AGGREGATE = "aggregate"
    SEQUENCE = "sequence"
    # WellWon domains
    COMPANY = "company"
    CHAT = "chat"
    SHIPMENT = "shipment"
    DOCUMENT = "document"


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
    Centralized cache management for WellWon operations.

    Key patterns follow: {prefix}:{domain}:{type}:{identifiers}
    Examples:
    - wellwon:user:profile:{user_id}
    - wellwon:auth:session:{session_id}
    - wellwon:company:detail:{company_id}
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self.metrics = CacheMetrics()
        self._deletion_lock = asyncio.Lock()
        self._background_tasks = []
        self._running = False

        # Initialize from config
        self._init_from_config()

        logger.info(f"Cache manager initialized (enabled={self.enabled}, prefix={self.key_prefix})")

    async def start(self):
        """Start cache manager background tasks"""
        if self._running:
            logger.warning("Cache manager already running")
            return

        self._running = True

        if self.cleanup_on_startup:
            task = asyncio.create_task(self._startup_cleanup())
            self._background_tasks.append(task)

        if self.cleanup_interval_hours > 0:
            task = asyncio.create_task(self._periodic_cleanup())
            self._background_tasks.append(task)

        logger.info(f"Cache manager started with {len(self._background_tasks)} background tasks")

    async def stop(self):
        """Stop cache manager and cleanup"""
        if not self._running:
            return

        logger.info("Stopping cache manager...")
        self._running = False

        for task in self._background_tasks:
            if not task.done():
                task.cancel()

        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        self._background_tasks.clear()
        logger.info("Cache manager stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def _init_from_config(self):
        """Initialize settings from configuration"""
        self.enabled = get_cache_config('core.enabled', True)
        self.key_prefix = get_cache_config('core.key_prefix', 'wellwon')
        self.default_ttl = get_cache_config('core.default_ttl', 300)
        self.max_key_length = get_cache_config('core.max_key_length', 256)

        self.scan_count = get_cache_config('redis.scan_count', 100)
        self.pipeline_max_size = get_cache_config('redis.pipeline_max_size', 100)

        self.cleanup_on_startup = get_cache_config('cleanup.on_startup', True)
        self.cleanup_batch_size = get_cache_config('cleanup.batch_size', 1000)
        self.cleanup_interval_hours = get_cache_config('cleanup.interval_hours', 6)

        self.cache_enabled = {
            'user': get_cache_config('features.enable_user', True),
            'auth': get_cache_config('features.enable_auth', True),
            'api': get_cache_config('features.enable_api', True),
            'event_store': get_cache_config('features.enable_event_store', True),
            'aggregate': get_cache_config('features.enable_aggregate', True),
            'sequence': get_cache_config('features.enable_sequence', True),
        }

        self.metrics_enabled = get_cache_config('monitoring.metrics_enabled', True)
        self.log_slow_ops = get_cache_config('monitoring.log_slow_operations', True)
        self.slow_op_threshold_ms = get_cache_config('monitoring.slow_operation_threshold_ms', 100)
        self.log_hits = get_cache_config('monitoring.log_cache_hits', False)
        self.log_misses = get_cache_config('monitoring.log_cache_misses', True)

        self.debug_mode = get_cache_config('debug.enabled', False)
        self.bypass_cache = get_cache_config('debug.bypass_cache', False)

    def _get_ttl(self, cache_type: str) -> int:
        return get_ttl(cache_type)

    def get_cache_ttl(self, cache_type: str) -> int:
        """Public method to get TTL for a cache type"""
        return self._get_ttl(cache_type)

    def _make_key(self, *parts: str) -> str:
        key = ':'.join([self.key_prefix] + list(parts))
        if len(key) > self.max_key_length:
            logger.warning(f"Cache key too long ({len(key)} chars): {key[:50]}...")
        return key

    def _should_bypass_cache(self, domain: str = None) -> bool:
        if not self.enabled or self.bypass_cache:
            return True
        if domain and not self.cache_enabled.get(domain, True):
            return True
        return False

    async def _track_operation(self, operation: str, start_time: float,
                               success: bool = True, hit: bool = None):
        if not self.metrics_enabled:
            return

        elapsed_ms = (time.time() - start_time) * 1000
        self.metrics.total_operations += 1
        self.metrics.total_latency_ms += elapsed_ms

        if not success:
            self.metrics.errors += 1
        elif hit is True:
            self.metrics.hits += 1
        elif hit is False:
            self.metrics.misses += 1

        if elapsed_ms > self.slow_op_threshold_ms:
            self.metrics.slow_operations += 1
            if self.log_slow_ops:
                logger.warning(f"Slow cache operation: {operation} took {elapsed_ms:.1f}ms")

    async def _scan_and_delete(self, pattern: str, batch_delete: bool = True) -> int:
        deleted = 0
        try:
            if batch_delete:
                pipe = self.redis.pipeline()
                batch_count = 0

                async for key in self.redis.scan_iter(match=pattern, count=self.scan_count):
                    pipe.delete(key)
                    batch_count += 1

                    if batch_count >= self.pipeline_max_size:
                        results = await pipe.execute()
                        deleted += sum(1 for r in results if r)
                        pipe = self.redis.pipeline()
                        batch_count = 0

                if batch_count > 0:
                    results = await pipe.execute()
                    deleted += sum(1 for r in results if r)
            else:
                async for key in self.redis.scan_iter(match=pattern, count=self.scan_count):
                    if await self.redis.delete(key):
                        deleted += 1

        except Exception as e:
            logger.error(f"Pattern delete error for {pattern}: {e}")

        if deleted > 0:
            self.metrics.keys_deleted += deleted

        return deleted

    # === Generic Operations ===

    async def get(self, key: str, track_metrics: bool = True) -> Optional[str]:
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
        data = await self.get(key)
        if data:
            try:
                return await asyncio.to_thread(json.loads, data)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in cache for {key}")
        return None

    async def set_json(self, key: str, value: Dict, ttl: Optional[int] = None) -> bool:
        try:
            data = await asyncio.to_thread(json.dumps, value, default=str)
            return await self.set(key, data, ttl)
        except Exception as e:
            logger.error(f"JSON encoding error for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        if self._should_bypass_cache():
            return True
        try:
            return await self.redis.delete(key) > 0
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        if self._should_bypass_cache():
            return 0
        return await self._scan_and_delete(pattern, batch_delete=True)

    async def exists(self, key: str) -> bool:
        if self._should_bypass_cache():
            return False
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for {key}: {e}")
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        if self._should_bypass_cache():
            return True
        try:
            return await self.redis.expire(key, ttl)
        except Exception as e:
            logger.error(f"Cache expire error for {key}: {e}")
            return False

    # === User & Auth ===

    async def cache_user_profile(self, user_id: str, profile: Dict) -> bool:
        if self._should_bypass_cache('user'):
            return True
        key = self._make_key('user', 'profile', user_id)
        return await self.set_json(key, profile, self._get_ttl('user:profile'))

    async def get_user_profile(self, user_id: str) -> Optional[Dict]:
        if self._should_bypass_cache('user'):
            return None
        key = self._make_key('user', 'profile', user_id)
        return await self.get_json(key)

    async def cache_session(self, session_id: str, session_data: Dict) -> bool:
        if self._should_bypass_cache('auth'):
            return True
        key = self._make_key('auth', 'session', session_id)
        return await self.set_json(key, session_data, self._get_ttl('auth:session'))

    async def get_session(self, session_id: str) -> Optional[Dict]:
        if self._should_bypass_cache('auth'):
            return None
        key = self._make_key('auth', 'session', session_id)
        return await self.get_json(key)

    async def invalidate_session(self, session_id: str) -> bool:
        key = self._make_key('auth', 'session', session_id)
        return await self.delete(key)

    # === API Response Caching ===

    def _api_cache_key(self, endpoint: str, params: Dict) -> str:
        param_str = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
        clean_endpoint = endpoint.replace('/', '_').strip('_')
        return self._make_key('api', 'response', clean_endpoint, param_hash)

    async def cache_api_response(
            self, endpoint: str, params: Dict, response: Dict, ttl: Optional[int] = None
    ) -> bool:
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
        if limit is None:
            limit = get_cache_config(f'rate_limiting.limits.{resource}',
                                     get_cache_config('rate_limiting.default_limit', 100))

        key = self._make_key('ratelimit', resource, identifier)

        try:
            count = await self.redis.get(key)
            return int(count or 0) < limit
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return True

    # === Cleanup Operations ===

    async def clear_user_cache(self, user_id: str) -> int:
        patterns = [
            f"{self.key_prefix}:user:*:{user_id}",
            f"{self.key_prefix}:auth:*:{user_id}*",
            f"{self.key_prefix}:ratelimit:*:{user_id}",
        ]

        total_deleted = 0
        for pattern in patterns:
            deleted = await self.delete_pattern(pattern)
            total_deleted += deleted

        if total_deleted > 0:
            logger.info(f"Cleared {total_deleted} cache keys for user {user_id}")

        return total_deleted

    async def clear_domain(self, domain: CacheDomain) -> int:
        pattern = f"{self.key_prefix}:{domain.value}:*"
        deleted = await self.delete_pattern(pattern)
        if deleted > 0:
            logger.warning(f"Cleared {deleted} cache keys for domain {domain.value}")
        return deleted

    async def clear_all(self) -> int:
        pattern = f"{self.key_prefix}:*"
        deleted = await self.delete_pattern(pattern)
        if deleted > 0:
            logger.warning(f"Cleared ALL {deleted} cache keys")
        return deleted

    # === Maintenance ===

    async def _startup_cleanup(self):
        try:
            logger.info("Running startup cache cleanup...")
            deleted = await self.delete_pattern(f"{self.key_prefix}:ratelimit:*")
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} rate limit keys")
        except Exception as e:
            logger.error(f"Startup cleanup error: {e}")

    async def _periodic_cleanup(self):
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval_hours * 3600)
                if not self._running:
                    break
                logger.info("Running periodic cache cleanup...")
                if self.metrics_enabled:
                    logger.info(f"Cache metrics: {self.metrics.to_dict()}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic cleanup error: {e}")
                if self._running:
                    await asyncio.sleep(60)

    # === Metrics ===

    def get_metrics(self) -> Dict:
        return self.metrics.to_dict()

    def reset_metrics(self):
        self.metrics = CacheMetrics()

    async def health_check(self) -> Dict:
        try:
            test_key = self._make_key('health', 'check')
            test_value = str(datetime.now(timezone.utc).timestamp())

            set_ok = await self.set(test_key, test_value, 10, track_metrics=False)
            get_value = await self.get(test_key, track_metrics=False)
            get_ok = get_value == test_value
            delete_ok = await self.delete(test_key)

            info = await self.redis.info()

            return {
                'healthy': set_ok and get_ok and delete_ok,
                'operations': {'set': set_ok, 'get': get_ok, 'delete': delete_ok},
                'redis': {
                    'connected': True,
                    'version': info.get('redis_version', 'unknown'),
                    'used_memory_human': info.get('used_memory_human', 'unknown'),
                },
                'metrics': self.get_metrics() if self.metrics_enabled else None,
            }
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return {'healthy': False, 'error': str(e)}


# === Singleton ===

_cache_manager: Optional[CacheManager] = None


def get_cache_manager(redis_client=None) -> CacheManager:
    global _cache_manager
    if _cache_manager is None:
        if redis_client is None:
            from app.infra.persistence.redis_client import get_global_client
            redis_client = get_global_client()
        _cache_manager = CacheManager(redis_client)
    return _cache_manager


async def initialize_cache_manager(redis_client=None) -> CacheManager:
    cache_manager = get_cache_manager(redis_client)
    if not cache_manager.is_running:
        await cache_manager.start()
    return cache_manager


async def shutdown_cache_manager():
    global _cache_manager
    if _cache_manager and _cache_manager.is_running:
        await _cache_manager.stop()


# === Decorators ===

def cached(cache_type: str, ttl: Optional[int] = None, key_func: Optional[Callable] = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache_manager()

            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = cache._make_key(cache_type, *key_parts)

            cached_value = await cache.get_json(cache_key)
            if cached_value is not None:
                return cached_value

            result = await func(*args, **kwargs)

            if result is not None:
                await cache.set_json(cache_key, result, ttl or cache._get_ttl(cache_type))

            return result

        return wrapper

    return decorator
