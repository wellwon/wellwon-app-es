# Circuit Breaker Pattern Guide

**Version**: TradeCore v0.5
**Last Updated**: 2025-11-10
**Component**: `app/infra/reliability/circuit_breaker.py`

## Overview

Circuit breakers protect TradeCore from cascading failures by automatically stopping requests to failing services. When a service fails repeatedly, the circuit breaker "opens" and blocks requests, preventing resource exhaustion and allowing the service time to recover.

**Key Features**:
- Three-state pattern (CLOSED → OPEN → HALF_OPEN)
- Configurable failure thresholds and timeouts
- Sliding window failure rate detection
- Prometheus metrics integration
- Redis-based state persistence (optional)
- Async execution support

## The Circuit Breaker Pattern

### State Machine

```
     ┌──────────────────────────────────────────────────────┐
     │                                                        │
     │                     CLOSED                            │
     │               (Normal Operation)                      │
     │    ┌──────────────────────────────────────┐          │
     │    │ Requests pass through                │          │
     │    │ Count failures                       │          │
     │    │ Reset on success                     │          │
     │    └──────────────────────────────────────┘          │
     │                      ↓                                │
     │         Failure threshold reached (5 failures)       │
     │                      ↓                                │
     ├──────────────────────────────────────────────────────┤
     │                     OPEN                              │
     │                (Circuit Tripped)                      │
     │    ┌──────────────────────────────────────┐          │
     │    │ Requests blocked immediately         │          │
     │    │ Fast-fail (no remote call)           │          │
     │    │ Wait for timeout (30s)               │          │
     │    └──────────────────────────────────────┘          │
     │                      ↓                                │
     │          Reset timeout elapsed (30 seconds)          │
     │                      ↓                                │
     ├──────────────────────────────────────────────────────┤
     │                   HALF_OPEN                           │
     │              (Testing Recovery)                       │
     │    ┌──────────────────────────────────────┐          │
     │    │ Allow limited requests (3 calls)     │          │
     │    │ Test if service recovered            │          │
     │    └──────────────────────────────────────┘          │
     │           ↙                      ↘                    │
     │   Success threshold          Any failure             │
     │   met (3 successes)                                  │
     │           ↓                      ↓                    │
     └─────► CLOSED                   OPEN ◄─────────────────┘
```

### Why Circuit Breakers Matter

**Without Circuit Breaker**:
```
Service A → Service B (failing)
   ↓
Keeps trying repeatedly
   ↓
Thread pool exhausted
   ↓
Service A also fails
   ↓
CASCADE FAILURE
```

**With Circuit Breaker**:
```
Service A → Circuit Breaker → Service B (failing)
   ↓
Circuit breaker opens after 5 failures
   ↓
Service A immediately fails fast (no remote call)
   ↓
Service B gets time to recover
   ↓
Circuit breaker tests recovery in HALF_OPEN
   ↓
Service B recovered → Circuit closes
```

## Basic Usage

### 1. Initialize Circuit Breaker

```python
from app.infra.reliability.circuit_breaker import CircuitBreaker, get_circuit_breaker
from app.config.reliability_config import CircuitBreakerConfig

# Option 1: Create new instance
config = CircuitBreakerConfig(
    name="postgres_query",
    failure_threshold=5,        # Open after 5 failures
    success_threshold=3,        # Close after 3 successes in HALF_OPEN
    reset_timeout_seconds=30,   # Wait 30s before testing recovery
    half_open_max_calls=3       # Allow 3 test calls in HALF_OPEN
)
circuit = CircuitBreaker(config)

# Option 2: Get from global registry (recommended)
circuit = get_circuit_breaker(
    name="postgres_query",
    config=config  # Optional, uses default if omitted
)
```

### 2. Execute with Circuit Breaker Protection

```python
async def risky_database_query():
    """Query that might fail due to connection issues"""
    async with pg_pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM orders")

# Execute with circuit breaker
try:
    result = await circuit.call(risky_database_query)
    print(f"Query result: {result}")
except CircuitBreakerOpenError:
    print("Circuit breaker is OPEN - service unavailable")
except Exception as e:
    print(f"Query failed: {e}")
```

### 3. Check if Execution is Allowed

```python
# Check before expensive operations
if circuit.can_execute():
    result = await perform_operation()
else:
    # Circuit is OPEN - fail fast
    raise CircuitBreakerOpenError("Service unavailable")
```

### 4. Manual Success/Failure Recording

```python
# For operations not using circuit.call()
try:
    result = await some_operation()
    circuit.record_success()
except Exception as e:
    circuit.record_failure(error_details=str(e))
    raise
```

## Advanced Configuration

### 1. Sliding Window Failure Rate

Instead of counting consecutive failures, track failure rate over a window:

```python
config = CircuitBreakerConfig(
    name="broker_api",
    failure_threshold=5,          # Still count failures
    window_size=20,               # Track last 20 calls
    failure_rate_threshold=0.5,   # Open if 50% failure rate
    reset_timeout_seconds=60
)

# Circuit opens if:
# - failure_threshold (5) consecutive failures, OR
# - failure_rate_threshold (50%) in sliding window
```

**Benefits**:
- More tolerant of sporadic failures
- Better for intermittent issues
- Prevents false positives

### 2. Custom Timeout (Alias Support)

```python
config = CircuitBreakerConfig(
    name="external_api",
    failure_threshold=3,
    reset_timeout_seconds=45,     # Primary field
    timeout_seconds=45            # Alias (for compatibility)
)
```

### 3. Redis State Persistence

Persist circuit breaker state across restarts:

```python
from app.infra.persistence.cache_manager import get_cache_manager

cache_manager = get_cache_manager()

config = CircuitBreakerConfig(name="critical_service")
circuit = CircuitBreaker(config, cache_manager=cache_manager)

# State automatically saved to Redis:
# Key: circuit_breaker:critical_service:state
# Value: "CLOSED" | "OPEN" | "HALF_OPEN"
# TTL: 3600 seconds (1 hour)
```

## Integration Patterns

### 1. Database Operations (pg_client.py)

**Pattern**: Circuit breaker per database

```python
# In app/infra/persistence/pg_client.py

# Circuit breaker initialized per database
_CIRCUIT_BREAKERS: Dict[str, CircuitBreaker] = {}

def get_circuit_breaker(database: str) -> CircuitBreaker:
    if database not in _CIRCUIT_BREAKERS:
        config = ReliabilityConfigs.postgres_circuit_breaker(database)
        _CIRCUIT_BREAKERS[database] = CircuitBreaker(config)
    return _CIRCUIT_BREAKERS[database]

# Used in acquire_connection_for_db
async def acquire_connection_for_db(database: str = "main"):
    circuit = get_circuit_breaker(database)

    # Check circuit before acquiring connection
    if not circuit.can_execute():
        raise ConnectionError(f"Circuit breaker is open for {database}")

    try:
        conn = await pool.acquire()
        circuit.record_success()
        return conn
    except Exception as e:
        circuit.record_failure(str(e))
        raise
```

### 2. EventBus (event_bus.py)

**Pattern**: Circuit breaker per channel

```python
# In app/infra/event_bus/event_bus.py

class EventBus:
    def __init__(self, adapter):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

    def _get_circuit_breaker(self, channel: str) -> CircuitBreaker:
        if channel not in self._circuit_breakers:
            config = CircuitBreakerConfig(
                name=f"eventbus-{channel}",
                failure_threshold=5,
                reset_timeout_seconds=30
            )
            self._circuit_breakers[channel] = CircuitBreaker(config)
        return self._circuit_breakers[channel]

    async def publish_stream(self, stream_name: str, event_data: dict):
        circuit = self._get_circuit_breaker(stream_name)

        # Check circuit
        if not circuit.can_execute():
            log.warning(f"Circuit breaker OPEN for {stream_name}")
            return

        # Execute with circuit breaker
        await circuit.call(
            self._adapter.publish_stream,
            stream_name,
            event_data
        )
```

### 3. Broker Adapters (broker_adapters/)

**Pattern**: Circuit breaker per broker connection

```python
# In app/infra/broker_adapters/base_adapter.py

class BrokerAdapter:
    def __init__(self, broker_id: str):
        config = ReliabilityConfigs.broker_api_circuit_breaker(broker_id)
        self.circuit = CircuitBreaker(config)

    async def fetch_account_balance(self, account_id: str):
        # Check circuit before API call
        if not self.circuit.can_execute():
            raise CircuitBreakerOpenError(f"{self.broker_id} API unavailable")

        # Execute with circuit protection
        async def api_call():
            response = await self.client.get(f"/accounts/{account_id}/balance")
            return response.json()

        return await self.circuit.call(api_call)
```

### 4. RedpandaTransportAdapter (redpanda_adapter.py)

**Pattern**: Single circuit breaker for transport

```python
# In app/infra/event_bus/redpanda_adapter.py

class RedpandaTransportAdapter:
    def __init__(self):
        config = CircuitBreakerConfig(
            name="redpanda_transport",
            failure_threshold=5,
            reset_timeout_seconds=30
        )
        self._circuit_breaker = CircuitBreaker(config)

    async def _wrapped_send(self, topic: str, value: bytes):
        # Check circuit before send
        if not self._circuit_breaker.can_execute():
            raise ConnectionError(f"Circuit breaker is open for topic {topic}")

        async def send_message():
            producer = await self._ensure_producer()
            return await producer.send_and_wait(topic, value=value)

        # Execute with circuit protection
        return await self._circuit_breaker.execute_async(send_message)
```

## Monitoring and Metrics

### 1. Get Circuit State

```python
# Get detailed state (async)
state = await circuit.get_state()
print(state)
# {
#     "name": "postgres_query",
#     "state": "CLOSED",
#     "failure_count": 0,
#     "success_count": 10,
#     "last_failure_time": None,
#     "failure_rate": 0.0,
#     "metrics_window": 20
# }

# Get state synchronously (compatibility)
state_name = circuit.get_state_sync()  # "CLOSED" | "OPEN" | "HALF_OPEN"
```

### 2. Get Metrics

```python
# Get metrics (sync, lightweight)
metrics = circuit.get_metrics()
print(metrics)
# {
#     "name": "postgres_query",
#     "state": "CLOSED",
#     "failure_count": 0,
#     "success_count": 10
# }
```

### 3. Prometheus Metrics (if enabled)

```python
# Metrics exported automatically if prometheus-client installed
from app.infra.metrics.circuit_breaker import (
    circuit_breaker_state,
    circuit_breaker_failures,
    circuit_breaker_trips
)

# State gauge (0=CLOSED, 1=OPEN, 2=HALF_OPEN)
circuit_breaker_state.labels(name="postgres_query").set(0)

# Failure counter
circuit_breaker_failures.labels(name="postgres_query").inc()

# Trip counter (CLOSED → OPEN)
circuit_breaker_trips.labels(name="postgres_query").inc()
```

### 4. Health Check Integration

```python
# In EventBus health check
async def health_check() -> Dict[str, Any]:
    status = await event_bus.get_circuit_breaker_status()

    # Find open circuits
    open_circuits = [
        channel for channel, info in status.items()
        if info["state"] == "OPEN"
    ]

    return {
        "circuit_breakers": status,
        "open_circuits": open_circuits,
        "open_circuits_count": len(open_circuits),
        "healthy": len(open_circuits) == 0  # Unhealthy if any open
    }
```

## Pre-configured Circuit Breakers

TradeCore provides pre-configured circuit breakers in `reliability_config.py`:

### 1. Kafka/Redpanda

```python
from app.config.reliability_config import ReliabilityConfigs

config = ReliabilityConfigs.kafka_circuit_breaker("event_store")
# failure_threshold=5, reset_timeout_seconds=30
```

### 2. PostgreSQL

```python
# Standard PostgreSQL
config = ReliabilityConfigs.postgres_circuit_breaker("main_db")
# failure_threshold=5, reset_timeout_seconds=30

# Auto-adjusts for multi-worker environments (Granian):
# - Higher failure_threshold (10 vs 5)
# - Longer reset_timeout (60s vs 30s)
# - Sliding window (window_size=20, failure_rate_threshold=0.5)
```

### 3. Redis

```python
config = ReliabilityConfigs.redis_circuit_breaker("cache")
# More aggressive: failure_threshold=3, reset_timeout_seconds=15
```

### 4. Broker APIs

```python
config = ReliabilityConfigs.broker_api_circuit_breaker("alpaca")
# failure_threshold=5, reset_timeout_seconds=60 (longer for external APIs)
# Includes sliding window: window_size=20, failure_rate_threshold=0.5
```

### 5. WebSocket Engine (WSE)

```python
config = ReliabilityConfigs.wse_circuit_breaker("conn-123")
# More tolerant: failure_threshold=10, reset_timeout_seconds=30
# window_size=50, failure_rate_threshold=0.3 (30%)
```

### 6. Connection Recovery

```python
config = ReliabilityConfigs.connection_recovery_circuit_breaker("alpaca")
# failure_threshold=5, reset_timeout_seconds=30
# window_size=10, failure_rate_threshold=0.5
```

## Bug Fix History

### Critical Fix (2025-11-10): get_state_sync vs .state

**Problem**: Direct access to `circuit._state` caused AttributeError in some contexts.

**Before (WRONG)**:
```python
# Direct access to private attribute
if circuit_breaker._state == CircuitState.OPEN:
    raise ConnectionError("Circuit breaker is open")
```

**After (CORRECT)**:
```python
# Use public method (synchronous)
if circuit_breaker.get_state_sync() == "OPEN":
    raise ConnectionError("Circuit breaker is open")

# Or use enum for comparison
from app.infra.reliability.circuit_breaker import CircuitState
state = circuit_breaker._state  # Internal use only
if state == CircuitState.OPEN:
    raise ConnectionError("Circuit breaker is open")
```

**Methods Available**:
- `get_state()` - Async, returns full state dict
- `get_state_sync()` - Sync, returns state name string ("CLOSED" | "OPEN" | "HALF_OPEN")
- `get_metrics()` - Sync, returns metrics dict
- `can_execute()` - Sync, returns boolean (True if CLOSED or HALF_OPEN with capacity)

## Best Practices

### 1. Naming Convention

✅ **Good**:
```python
# Descriptive, hierarchical names
get_circuit_breaker("postgres_main_db")
get_circuit_breaker("broker_alpaca_api")
get_circuit_breaker("eventbus_order_events")
```

❌ **Bad**:
```python
# Too generic, hard to debug
get_circuit_breaker("db")
get_circuit_breaker("api")
get_circuit_breaker("events")
```

### 2. Threshold Configuration

**Conservative** (external APIs, critical services):
```python
CircuitBreakerConfig(
    failure_threshold=3,        # Low threshold
    reset_timeout_seconds=60,   # Long timeout
    half_open_max_calls=2       # Few test calls
)
```

**Tolerant** (internal services, high throughput):
```python
CircuitBreakerConfig(
    failure_threshold=10,       # High threshold
    reset_timeout_seconds=15,   # Short timeout
    half_open_max_calls=5,      # More test calls
    window_size=50,             # Sliding window
    failure_rate_threshold=0.3  # 30% failure rate
)
```

### 3. Error Handling

✅ **Good**:
```python
try:
    result = await circuit.call(risky_operation)
except CircuitBreakerOpenError:
    # Circuit is open - service unavailable
    logger.warning("Circuit breaker open, using fallback")
    result = get_cached_value()  # Fallback strategy
except Exception as e:
    # Operation failed
    logger.error(f"Operation failed: {e}")
    raise
```

❌ **Bad**:
```python
# No fallback for circuit breaker open
try:
    result = await circuit.call(risky_operation)
except Exception as e:
    # Catches CircuitBreakerOpenError too - wrong!
    logger.error(f"Error: {e}")
    raise
```

### 4. Testing Circuit Behavior

```python
# Test circuit opens after threshold
circuit = CircuitBreaker(CircuitBreakerConfig(
    name="test",
    failure_threshold=3,
    reset_timeout_seconds=1
))

# Trigger failures
for i in range(3):
    circuit.record_failure()

assert circuit.get_state_sync() == "OPEN"

# Wait for reset timeout
await asyncio.sleep(1.5)

# Should transition to HALF_OPEN
assert circuit.can_execute()  # True (allows test calls)

# Successful test calls close circuit
for i in range(3):
    circuit.record_success()

assert circuit.get_state_sync() == "CLOSED"
```

### 5. Global Registry Usage

✅ **Good** (singleton pattern):
```python
# Get circuit breaker from global registry
circuit = get_circuit_breaker("postgres_query", config)

# Same instance returned on subsequent calls
circuit2 = get_circuit_breaker("postgres_query")
assert circuit is circuit2  # True
```

❌ **Bad** (multiple instances):
```python
# Creating new instance each time
circuit1 = CircuitBreaker(config)
circuit2 = CircuitBreaker(config)
# Different instances - state not shared!
```

## Troubleshooting

### Circuit Breaker Keeps Opening

**Symptoms**: Service constantly enters OPEN state

**Diagnosis**:
```python
state = await circuit.get_state()
print(f"Failures: {state['failure_count']}")
print(f"Last failure: {state['last_failure_time']}")
```

**Solutions**:
1. Check underlying service health (database, API, Redpanda)
2. Increase `failure_threshold` if transient errors
3. Add sliding window for intermittent failures
4. Review error logs for root cause

### Circuit Never Opens

**Symptoms**: Service fails repeatedly but circuit stays CLOSED

**Diagnosis**:
```python
# Check if failures are being recorded
metrics = circuit.get_metrics()
print(f"Total failures: {metrics['failure_count']}")
```

**Solutions**:
1. Ensure `circuit.record_failure()` is called on errors
2. Verify `failure_threshold` is not too high
3. Check if using `can_execute()` before operations
4. Add error logging to confirm failures detected

### HALF_OPEN State Stuck

**Symptoms**: Circuit stays in HALF_OPEN indefinitely

**Diagnosis**:
```python
state = await circuit.get_state()
print(f"Success count: {state['success_count']}")
print(f"Success threshold: {config.success_threshold}")
```

**Solutions**:
1. Verify service is actually recovering (health check)
2. Ensure `circuit.record_success()` is called on success
3. Reduce `success_threshold` if needed
4. Check for race conditions in async code

## Performance Considerations

### Circuit Breaker Overhead

**Negligible** for most use cases:
- `can_execute()`: ~1μs (checks boolean and timestamp)
- `record_success()`: ~5μs (increment counter)
- `record_failure()`: ~10μs (update counters + timestamp)
- `call()`: +15μs overhead (includes execute_async wrapper)

**Total overhead**: <20μs per operation

### When to Use Circuit Breakers

✅ **Use when**:
- Calling external services (APIs, databases)
- High-latency operations (>100ms)
- Operations that can fail transiently
- Cascading failure risk

❌ **Skip when**:
- In-memory operations (<1ms)
- Operations that never fail
- Single-use operations (no retry benefit)
- Critical operations requiring immediate failure

## Related Documentation

- **Retry Pattern**: See `app/infra/reliability/retry.py`
- **EventBus Integration**: See `EVENT_BUS_GUIDE.md`
- **Database Integration**: See `DATABASE_PATTERNS.md`
- **Reliability Configuration**: See `app/config/reliability_config.py`

## Summary

Circuit breakers are essential for building resilient distributed systems:

- **Three states**: CLOSED (normal), OPEN (failing), HALF_OPEN (testing recovery)
- **Automatic recovery**: Transitions to HALF_OPEN after timeout, closes on success
- **Configurable thresholds**: Failure threshold, success threshold, timeout
- **Sliding window**: Track failure rate over time window
- **Integration**: Used in EventBus, pg_client, broker adapters

**Key takeaway**: Always use `get_circuit_breaker()` for singleton behavior, use `get_state_sync()` for state checks, and implement fallback strategies for `CircuitBreakerOpenError`.
