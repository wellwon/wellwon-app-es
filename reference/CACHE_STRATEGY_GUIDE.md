# Cache Strategy Guide

**Version**: TradeCore v0.5
**Last Updated**: 2025-11-10
**Component**: `app/infra/persistence/cache_manager.py`

## Overview

The CacheManager provides centralized caching for TradeCore using Redis with support for distributed operations, TTL strategies, cache invalidation patterns, and Lua script execution. All caching operations are async and include comprehensive metrics tracking.

**Key Features**:
- Domain-specific caching (User, Broker, VB, Trading, Market)
- Configurable TTLs per cache type
- Pattern-based cache invalidation
- Distributed locking (stampede prevention)
- Rate limiting with Lua scripts
- Background cleanup and maintenance
- Comprehensive metrics and monitoring

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      CacheManager                               │
│            (Centralized Caching Layer)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            Cache Domains (Namespaced)                    │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  USER       │ profile, session, settings                 │  │
│  │  AUTH       │ JWT tokens, sessions, OAuth                │  │
│  │  BROKER     │ health, connections, credentials           │  │
│  │  VB         │ virtual broker accounts, balances          │  │
│  │  TRADING    │ orders, positions, portfolios              │  │
│  │  MARKET     │ quotes, bars, market data                  │  │
│  │  API        │ response caching                           │  │
│  │  SYSTEM     │ locks, rate limits, metrics                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Key Features                                 │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  • TTL Management (per cache type)                       │  │
│  │  • Pattern Invalidation (wildcard cleanup)               │  │
│  │  • Distributed Locking (Redis-based)                     │  │
│  │  • Lua Scripts (atomic operations)                       │  │
│  │  • Metrics Tracking (hits, misses, latency)              │  │
│  │  • Background Tasks (cleanup, maintenance)               │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Redis Client                                 │
│                (AsyncIO Redis Driver)                           │
├─────────────────────────────────────────────────────────────────┤
│  • Connection pooling                                           │
│  • Pipelining for batch operations                              │
│  • Lua script execution                                         │
│  • SCAN for safe pattern operations                             │
└─────────────────────────────────────────────────────────────────┘
```

## Key Naming Convention

```
{prefix}:{domain}:{type}:{identifiers}

Examples:
- tradecore:user:profile:user-123
- tradecore:auth:session:sess-456
- tradecore:broker:health:alpaca:conn-789
- tradecore:vb:adapter:u:user-123:c:conn-456
- tradecore:market:quote:AAPL
- tradecore:api:response:get_orders:hash-abc123
- tradecore:ratelimit:api:user-123
```

**Components**:
- `prefix`: Namespace (default: "tradecore")
- `domain`: Cache domain (user, broker, vb, market, etc.)
- `type`: Cache type (profile, session, quote, etc.)
- `identifiers`: Entity IDs (user_id, symbol, etc.)

## Basic Usage

### 1. Initialize CacheManager

```python
from app.infra.persistence.cache_manager import initialize_cache_manager, get_cache_manager

# Initialize once at startup (starts background tasks)
cache_manager = await initialize_cache_manager()

# Later: Get singleton instance
cache = get_cache_manager()
```

### 2. Get and Set Operations

```python
# Set value with TTL
await cache.set("mykey", "myvalue", ttl=300)  # 5 minutes

# Get value
value = await cache.get("mykey")
print(value)  # "myvalue"

# Check existence
exists = await cache.exists("mykey")

# Delete
await cache.delete("mykey")
```

### 3. JSON Operations

```python
# Cache Python dict
data = {"user_id": "123", "name": "Alice", "balance": 1000.0}
await cache.set_json("user:123", data, ttl=600)

# Retrieve as dict
user_data = await cache.get_json("user:123")
print(user_data["name"])  # "Alice"
```

### 4. Pattern Operations

```python
# Get keys matching pattern
keys = await cache.keys("tradecore:user:*")
# ["tradecore:user:profile:123", "tradecore:user:profile:456", ...]

# Delete all keys matching pattern
deleted_count = await cache.delete_pattern("tradecore:user:*")
print(f"Deleted {deleted_count} keys")
```

## Domain-Specific Caching

### 1. User & Auth

```python
# Cache user profile
profile = {"user_id": "123", "email": "user@example.com"}
await cache.cache_user_profile("123", profile)

# Get cached profile
profile = await cache.get_user_profile("123")

# Cache session
session_data = {"user_id": "123", "token": "jwt-token"}
await cache.cache_session("sess-456", session_data)

# Get session
session = await cache.get_session("sess-456")

# Invalidate session
await cache.invalidate_session("sess-456")
```

**TTLs** (from config):
- User profile: 3600s (1 hour)
- Session: 7200s (2 hours)
- Settings: 1800s (30 minutes)

### 2. Broker Connections

```python
# Cache broker health check
health_data = {
    "healthy": True,
    "latency_ms": 50,
    "last_check": "2025-11-10T12:00:00Z"
}
await cache.cache_broker_health("alpaca", "conn-789", health_data)

# Get cached health
health = await cache.get_broker_health("alpaca", "conn-789")
```

**TTL**: 60s (health checks expire quickly)

### 3. Virtual Broker (VB)

```python
# Cache VB adapter accounts (critical for performance)
accounts = [
    {"id": "vb-1", "name": "Paper Account", "balance": 100000.0},
    {"id": "vb-2", "name": "Test Account", "balance": 50000.0}
]
await cache.cache_vb_adapter_accounts(
    user_id="user-123",
    broker_connection_id="conn-456",
    accounts=accounts
)

# Get cached accounts
accounts = await cache.get_vb_adapter_accounts("user-123", "conn-456")

# Cache VB balance
balance = {"cash": 95000.0, "equity": 100000.0}
await cache.cache_vb_balance("vb-1", balance)

# Get balance
balance = await cache.get_vb_balance("vb-1")
```

**TTLs**:
- VB adapter accounts: 60s (frequently updated)
- VB balance: 30s (real-time)

### 4. Trading Data

```python
# Cache account balance
balance = {"cash": 10000.0, "equity": 12000.0, "buying_power": 10000.0}
await cache.cache_account_balance("acct-123", balance)

# Get balance
balance = await cache.get_account_balance("acct-123")

# Cache order status
order = {"order_id": "ord-456", "status": "filled", "filled_at": "..."}
await cache.cache_order_status("ord-456", order)

# Get order status
order = await cache.get_order_status("ord-456")
```

**TTLs**:
- Account balance: 60s
- Order status: 300s (5 minutes)
- Position: 60s

### 5. Market Data

```python
# Cache quote
quote = {
    "symbol": "AAPL",
    "bid": 150.10,
    "ask": 150.15,
    "last": 150.12,
    "timestamp": "2025-11-10T12:00:00Z"
}
await cache.cache_quote("AAPL", quote)

# Get quote
quote = await cache.get_quote("AAPL")
```

**TTL**: 5s (market data is real-time)

### 6. API Response Caching

```python
# Cache API response (GET requests only)
response_data = {
    "orders": [...],
    "total": 50,
    "page": 1
}
await cache.cache_api_response(
    endpoint="/api/orders",
    params={"page": 1, "limit": 50},
    response=response_data,
    ttl=60  # Custom TTL (default: 300s)
)

# Get cached response
cached_response = await cache.get_api_response(
    endpoint="/api/orders",
    params={"page": 1, "limit": 50}
)
```

**How it works**:
- Parameters hashed (MD5) for cache key uniqueness
- Full response cached with metadata (endpoint, params, cached_at)
- Cache key format: `tradecore:api:response:get_orders:hash-abc123`

## Advanced Patterns

### 1. Cache Decorators

```python
from app.infra.persistence.cache_manager import cached

# Decorate function with caching
@cached('user:profile', ttl=3600)
async def get_user_profile(user_id: str) -> Dict:
    # Expensive database query
    user = await db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    return dict(user)

# First call: executes query + caches result
profile = await get_user_profile("user-123")

# Second call: returns cached result (no query)
profile = await get_user_profile("user-123")
```

**Custom key function**:
```python
@cached(
    'account:balance',
    ttl=60,
    key_func=lambda account_id, include_positions: f"{account_id}:{include_positions}"
)
async def get_account_balance(account_id: str, include_positions: bool = False):
    # ...
    return balance
```

### 2. Cache Invalidation Decorator

```python
from app.infra.persistence.cache_manager import cache_invalidate

@cache_invalidate(['user:profile:{user_id}', 'user:settings:{user_id}'])
async def update_user_profile(user_id: str, data: Dict):
    # Update database
    await db.execute("UPDATE users SET ... WHERE id = $1", user_id)
    # Cache automatically invalidated after function returns
    return updated_user
```

### 3. Rate Limiting

```python
# Check rate limit
user_id = "user-123"
resource = "api_orders"
limit = 100  # 100 requests per window

if await cache.check_rate_limit(resource, user_id, limit=limit):
    # Increment counter
    count = await cache.increment_rate_limit(resource, user_id, window=60)
    print(f"Request {count}/{limit}")
    # Process request
else:
    raise RateLimitExceededError("Too many requests")

# Reset rate limit
await cache.reset_rate_limit(resource, user_id)
```

**With Lua scripts** (atomic, more efficient):
```python
# Rate limiting Lua script (sliding window)
lua_script = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local current = tonumber(redis.call('GET', key) or "0")

if current < limit then
    redis.call('INCR', key)
    if current == 0 then
        redis.call('EXPIRE', key, window)
    end
    return 1
else
    return 0
end
"""

# Execute
allowed = await cache.eval_script(
    lua_script,
    keys=["ratelimit:api:user-123"],
    args=[100, 60]  # 100 requests per 60 seconds
)

if allowed:
    # Process request
    pass
else:
    raise RateLimitExceededError()
```

### 4. Distributed Locking

```python
# Prevent cache stampede (multiple processes fetching same data)
from app.infra.reliability.distributed_lock import DistributedLock
from app.config.reliability_config import ReliabilityConfigs

lock_config = ReliabilityConfigs.cache_distributed_lock()
lock = DistributedLock(lock_config)

cache_key = "expensive_data:123"
lock_resource = f"lock:{cache_key}"

# Try to get from cache
data = await cache.get_json(cache_key)

if data is None:
    # Acquire lock
    async with lock.lock_context(lock_resource, ttl_seconds=5):
        # Double-check cache (another process may have populated it)
        data = await cache.get_json(cache_key)

        if data is None:
            # Fetch expensive data (only one process does this)
            data = await fetch_expensive_data()

            # Cache for others
            await cache.set_json(cache_key, data, ttl=300)

return data
```

## Cache Cleanup Patterns

### 1. Clear Broker Connection (Critical)

**Use case**: User disconnects from broker, clear ALL related caches

```python
# Comprehensive cleanup
deleted = await cache.clear_broker_connection(
    broker_id="alpaca",
    user_id="user-123",
    connection_id="conn-456"
)

# Clears patterns:
# - tradecore:broker:*:alpaca*
# - tradecore:broker:*:conn-456*
# - tradecore:account:*:b:alpaca*
# - tradecore:account:*:c:conn-456*
# - tradecore:vb:*:c:conn-456*
# - tradecore:order:*:c:conn-456*
# - tradecore:position:*:c:conn-456*
# - tradecore:api:*:*user-123*
# - tradecore:ratelimit:*:alpaca*

print(f"Deleted {deleted} cache keys")
```

**Why critical**: Prevents stale account data on reconnection.

### 2. Clear Account Cache

```python
# Clear all caches for a specific account
deleted = await cache.clear_account_cache(
    account_id="acct-123",
    user_id="user-123",
    broker_id="alpaca",
    connection_id="conn-456"
)

# Clears:
# - Account balance
# - Orders for account
# - Positions for account
# - VB account data
# - VB adapter cache entry
```

### 3. Clear User Cache

```python
# Clear all user-related caches
deleted = await cache.clear_user_cache("user-123")

# Clears:
# - User profile
# - Sessions
# - Broker connections
# - Virtual broker data
# - Accounts
# - Rate limits
```

### 4. Clear by Domain

```python
from app.infra.persistence.cache_manager import CacheDomain

# Clear entire domain
deleted = await cache.clear_domain(CacheDomain.MARKET)
# Clears all market data: tradecore:market:*

deleted = await cache.clear_domain(CacheDomain.API)
# Clears all API response caches: tradecore:api:*
```

### 5. Nuclear Option (Clear All)

```python
# ⚠️ WARNING: Clears ALL TradeCore caches
deleted = await cache.clear_all()
print(f"Cleared {deleted} keys")
```

## TTL Configuration

### 1. Default TTLs (from cache_config.py)

```python
# User domain
user:profile          = 3600s   (1 hour)
user:settings         = 1800s   (30 minutes)

# Auth domain
auth:session          = 7200s   (2 hours)
auth:token            = 3600s   (1 hour)
auth:oauth_state      = 600s    (10 minutes)

# Broker domain
broker:health         = 60s     (1 minute)
broker:credentials    = 3600s   (1 hour)

# Virtual Broker
vb:account_list       = 60s     (1 minute)
vb:balance            = 30s     (30 seconds)
vb:position           = 60s     (1 minute)

# Trading
account:balance       = 60s     (1 minute)
order:status          = 300s    (5 minutes)
position:list         = 60s     (1 minute)

# Market Data
market:quote          = 5s      (5 seconds)
market:bar            = 60s     (1 minute)

# API
api:response          = 300s    (5 minutes)
```

### 2. Get TTL Dynamically

```python
# Get TTL for cache type
ttl = cache.get_cache_ttl("market:quote")
print(ttl)  # 5

# Get module-specific TTL
ttl = cache.get_module_ttl("market", "quote")
print(ttl)  # 5

# Get OAuth TTL by broker
ttl = cache.get_oauth_ttl("alpaca", "access_token")
print(ttl)  # 3600

ttl = cache.get_oauth_ttl("alpaca", "refresh_token")
print(ttl)  # 2592000 (30 days)
```

### 3. Custom TTL

```python
# Override TTL on set
await cache.set_json("custom:key", data, ttl=120)  # 2 minutes

# Update TTL on existing key
await cache.expire("existing:key", ttl=600)
```

## Metrics and Monitoring

### 1. Get Metrics

```python
metrics = cache.get_metrics()

# Returns:
{
    'hits': 1523,
    'misses': 127,
    'errors': 2,
    'hit_rate': 92.3,               # Percentage
    'slow_operations': 5,
    'total_operations': 1650,
    'avg_latency_ms': 2.5,
    'cache_clears': 3,
    'keys_deleted': 450,
    'uptime_seconds': 3600.0
}
```

### 2. Health Check

```python
health = await cache.health_check()

# Returns:
{
    'healthy': True,
    'operations': {
        'set': True,
        'get': True,
        'delete': True
    },
    'redis': {
        'connected': True,
        'version': '7.0.5',
        'used_memory_human': '10.5M',
        'connected_clients': 5
    },
    'metrics': {
        'hits': 1523,
        'hit_rate': 92.3,
        # ... other metrics
    },
    'config': {
        'source': 'cache_config.py',
        'environment': 'production',
        'key_prefix': 'tradecore',
        'debug_mode': False,
        'aggressive_cleanup': True
    }
}
```

### 3. Reset Metrics

```python
# Reset counters (start fresh)
cache.reset_metrics()
```

## Lifecycle Management

### 1. Start CacheManager

```python
# Initialize and start (once at startup)
cache_manager = await initialize_cache_manager()

# Starts background tasks:
# - Startup cleanup (rate limits, sessions)
# - Periodic cleanup (every 6 hours)
```

### 2. Stop CacheManager

```python
# Graceful shutdown (at application exit)
await shutdown_cache_manager()

# Stops background tasks
# Logs final metrics
```

### 3. Manual Background Task Control

```python
cache = get_cache_manager()

# Check status
print(cache.is_running)  # True/False
print(cache.background_task_count)  # Number of active tasks

# Start manually (if not using initialize_cache_manager)
await cache.start()

# Stop manually
await cache.stop()
```

## Configuration Reference

### cache_config.py

```python
# Core
CACHE_ENABLED=true
CACHE_KEY_PREFIX=tradecore
CACHE_DEFAULT_TTL=300

# Redis
REDIS_SCAN_COUNT=100
REDIS_PIPELINE_MAX_SIZE=100

# Cleanup
CACHE_CLEANUP_ON_STARTUP=true
CACHE_CLEANUP_BATCH_SIZE=1000
CACHE_CLEANUP_INTERVAL_HOURS=6
CACHE_CLEANUP_MAX_AGE_HOURS=24

# VB cleanup
CACHE_VB_CLEAR_ON_DISCONNECT=true
CACHE_VB_CLEAR_ON_RESET=true
CACHE_VB_CLEAR_ON_DELETE=true

# Broker cleanup
CACHE_BROKER_CLEAR_ON_DISCONNECT=true
CACHE_BROKER_CLEAR_ON_AUTH_FAIL=true
CACHE_BROKER_AGGRESSIVE_CLEANUP=true

# Monitoring
CACHE_METRICS_ENABLED=true
CACHE_LOG_SLOW_OPS=true
CACHE_SLOW_OP_THRESHOLD_MS=50
CACHE_LOG_HITS=false
CACHE_LOG_MISSES=true

# Debug
CACHE_DEBUG_MODE=false
CACHE_BYPASS_CACHE=false
CACHE_FAKE_MISS_RATE=0
CACHE_LOG_KEYS=false
```

## Best Practices

### 1. Key Naming

✅ **Good**:
```python
key = cache._make_key('user', 'profile', user_id)
# tradecore:user:profile:user-123

key = cache._make_key('broker', 'health', broker_id, connection_id)
# tradecore:broker:health:alpaca:conn-456
```

❌ **Bad**:
```python
key = f"user_{user_id}"  # No namespace, no domain
key = "cache:data:123"   # Generic, unclear purpose
```

### 2. TTL Selection

**Short TTL** (5-60s):
- Market data (real-time)
- Account balances (frequently updated)
- Health checks

**Medium TTL** (5-30 min):
- Order status
- API responses
- User settings

**Long TTL** (1-2 hours):
- User profiles (infrequently changed)
- OAuth credentials (long-lived)
- Static data

### 3. Cache Invalidation

✅ **Good** (specific invalidation):
```python
# On user profile update
await cache.delete(cache._make_key('user', 'profile', user_id))

# On account balance update
await cache.delete(cache._make_key('account', 'balance', account_id))
```

❌ **Bad** (over-invalidation):
```python
# Don't clear entire domain on single update
await cache.clear_domain(CacheDomain.USER)  # Too broad!
```

### 4. Error Handling

✅ **Good** (graceful degradation):
```python
try:
    data = await cache.get_json(cache_key)
    if data is None:
        data = await fetch_from_database()
        await cache.set_json(cache_key, data, ttl=300)
except Exception as e:
    log.error(f"Cache error: {e}")
    # Fall back to database
    data = await fetch_from_database()
```

❌ **Bad** (crash on cache failure):
```python
data = await cache.get_json(cache_key)
if data is None:
    data = await fetch_from_database()
    await cache.set_json(cache_key, data, ttl=300)
# Crashes if Redis is down!
```

### 5. Batch Operations

✅ **Good** (use pipelines):
```python
# Delete multiple keys efficiently
await cache.delete_pattern("tradecore:user:*")
# Uses Redis SCAN + pipeline internally
```

❌ **Bad** (one-by-one):
```python
# Don't delete keys individually in loop
keys = await cache.keys("tradecore:user:*")
for key in keys:
    await cache.delete(key)  # Slow! Many round-trips
```

## Troubleshooting

### High Cache Miss Rate

**Symptoms**: `hit_rate` < 50%

**Diagnosis**:
```python
metrics = cache.get_metrics()
print(f"Hits: {metrics['hits']}, Misses: {metrics['misses']}")
print(f"Hit rate: {metrics['hit_rate']}%")
```

**Solutions**:
1. Increase TTLs for stable data
2. Pre-warm cache on startup
3. Review cache key generation (typos?)
4. Check if data changes more frequently than TTL

### Memory Usage Growing

**Symptoms**: Redis memory usage increasing

**Diagnosis**:
```bash
# Check Redis memory
redis-cli INFO memory

# Check key count
redis-cli DBSIZE

# Sample keys
redis-cli SCAN 0 MATCH tradecore:* COUNT 100
```

**Solutions**:
1. Review TTLs (too long?)
2. Enable aggressive cleanup
3. Increase cleanup frequency
4. Add key expiration to all sets

### Slow Cache Operations

**Symptoms**: `avg_latency_ms` > 10ms

**Diagnosis**:
```python
metrics = cache.get_metrics()
print(f"Avg latency: {metrics['avg_latency_ms']}ms")
print(f"Slow ops: {metrics['slow_operations']}")
```

**Solutions**:
1. Check Redis server load
2. Reduce batch sizes
3. Use pipelining for bulk operations
4. Review network latency (Redis on same host?)

### Cache Not Clearing

**Symptoms**: Stale data persists after invalidation

**Diagnosis**:
```python
# Check if keys exist
keys = await cache.keys("tradecore:user:profile:*")
print(f"Found {len(keys)} keys")

# Check specific key
exists = await cache.exists("tradecore:user:profile:123")
```

**Solutions**:
1. Verify correct cache key format
2. Check if pattern matches keys
3. Ensure aggressive cleanup enabled
4. Manually delete with correct pattern

## Related Documentation

- **Distributed Locking**: See `app/infra/reliability/distributed_lock.py`
- **Redis Client**: See `app/infra/persistence/redis_client.py`
- **Cache Configuration**: See `app/config/cache_config.py`
- **Rate Limiting**: See `app/infra/reliability/rate_limiter.py`

## Summary

The CacheManager provides a powerful, centralized caching layer for TradeCore:

- **Domain-specific** caching with consistent key naming
- **Configurable TTLs** per cache type
- **Pattern-based** invalidation for bulk cleanup
- **Distributed locking** for cache stampede prevention
- **Comprehensive metrics** for monitoring performance
- **Background cleanup** for automatic maintenance

**Key takeaway**: Use domain-specific methods (e.g., `cache_user_profile`) for consistency, implement proper TTLs for your use case, and always handle cache failures gracefully with database fallback.
