# Event Bus Integration Guide

**Version**: TradeCore v0.5
**Last Updated**: 2025-11-10
**Component**: `app/infra/event_bus/event_bus.py`, `app/infra/event_bus/redpanda_adapter.py`

## Overview

The EventBus is TradeCore's universal async message broker that provides publish-subscribe and durable stream messaging patterns with built-in reliability features (circuit breakers, retry, DLQ).

**Key Features**:
- Dual messaging modes: Pub/Sub (ephemeral) and Stream (durable)
- Built-in circuit breakers per channel
- Configurable retry with exponential backoff
- Dead Letter Queue (DLQ) for failed messages
- Event validation using Pydantic registry
- Exactly-once delivery support via outbox pattern
- Health monitoring and metrics

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         EventBus                                │
│                  (Universal Message Broker)                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐              ┌──────────────────┐         │
│  │   Pub/Sub Mode   │              │   Stream Mode    │         │
│  │   (Ephemeral)    │              │   (Durable)      │         │
│  ├──────────────────┤              ├──────────────────┤         │
│  │ • Latest offset  │              │ • From beginning │         │
│  │ • Fire-and-forget│              │ • Consumer groups│         │
│  │ • No persistence │              │ • Offset commit  │         │
│  │ • Real-time      │              │ • Replay support │         │
│  └──────────────────┘              └──────────────────┘         │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Reliability Layer (per channel)                │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ • Circuit Breaker (failure_threshold=5, timeout=30s)     │  │
│  │ • Retry (max_attempts=5, backoff_factor=2.0)             │  │
│  │ • DLQ (failed messages → {channel}.dlq)                  │  │
│  │ • Event Validation (Pydantic registry)                   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    TransportAdapter                             │
│              (Pluggable Message Transport)                      │
├─────────────────────────────────────────────────────────────────┤
│  RedpandaTransportAdapter (Kafka-compatible)                    │
│  • Topic mapping and prefixing                                  │
│  • Partition assignment (CooperativeStickyAssignor)             │
│  • Consumer group management                                    │
│  • Connection pooling and health checks                         │
│  • Worker-specific configuration integration                    │
└─────────────────────────────────────────────────────────────────┘
```

## Core Concepts

### 1. Pub/Sub vs Stream

| Feature              | Pub/Sub                    | Stream                       |
|----------------------|----------------------------|------------------------------|
| **Use Case**         | Real-time notifications    | Event sourcing, audit logs   |
| **Durability**       | Ephemeral                  | Persistent (Redpanda)        |
| **Offset**           | Latest (newest messages)   | Earliest (from beginning)    |
| **Consumer Groups**  | Unique per subscriber      | Shared (load balancing)      |
| **Replay**           | Not supported              | Fully supported              |
| **Retention**        | Short (hours)              | Long (7 days - 10 years)     |
| **Delivery**         | At-most-once               | At-least-once (with commit)  |

**When to use**:
- **Pub/Sub**: WebSocket updates, real-time dashboards, cache invalidation
- **Stream**: Domain events, command processing, saga orchestration, audit trails

### 2. Event Enrichment

All events automatically get:
```python
{
    "event_id": "generated-uuid",           # Auto-generated if missing
    "timestamp": "2025-11-10T12:00:00Z",    # ISO format UTC
    "event_type": "EventTypeName",          # Must be present
    "version": 1,                           # Schema version
    # ... your event data
}
```

### 3. Circuit Breaker States

```
CLOSED → OPEN → HALF_OPEN → CLOSED
  ↑                             ↓
  └─────────────────────────────┘
```

- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Too many failures, requests blocked (logs warning)
- **HALF_OPEN**: Testing recovery, limited requests allowed

## Basic Usage

### 1. Initialize EventBus

```python
from app.infra.event_bus.event_bus import EventBus
from app.infra.event_bus.redpanda_adapter import RedpandaTransportAdapter
from app.config.eventbus_transport_config import EventBusConfig, TransportConfig

# Create transport adapter
adapter = RedpandaTransportAdapter(
    bootstrap_servers="localhost:19092",
    client_id="my-service",
    event_bus_config=EventBusConfig.from_env(),
    transport_config=TransportConfig.from_env()
)

# Initialize topics (optional but recommended)
await adapter.initialize_topics(enable_auto_create=True)

# Create EventBus
event_bus = EventBus(
    adapter=adapter,
    validate_on_publish=True,  # Enable Pydantic validation
    event_bus_config=EventBusConfig.from_env(),
    transport_config=TransportConfig.from_env()
)
```

### 2. Publish to Pub/Sub (Ephemeral)

```python
# Real-time notification (fire-and-forget)
await event_bus.publish(
    channel="realtime.price-updates",
    event_data_dict={
        "event_type": "PriceUpdated",
        "symbol": "AAPL",
        "price": 150.25,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
)
```

### 3. Publish to Stream (Durable)

```python
# Domain event (persistent, replayable)
await event_bus.publish_stream(
    stream_name="transport.broker-connection-events",
    event_data_dict={
        "event_type": "ConnectionEstablished",
        "connection_id": "conn-123",
        "broker_id": "alpaca",
        "user_id": "user-456"
    }
)
```

### 4. Subscribe to Pub/Sub

```python
async def handle_price_update(event: Dict[str, Any]):
    print(f"Price update for {event['symbol']}: ${event['price']}")

# Subscribe (returns subscription_id for unsubscribe)
subscription_id = await event_bus.subscribe(
    channel="realtime.price-updates",
    handler=handle_price_update,
    filter_fn=lambda e: e.get("symbol") == "AAPL"  # Optional filter
)

# Later: Unsubscribe
await event_bus.unsubscribe(subscription_id)
```

### 5. Subscribe to Stream (Consumer Group)

```python
async def handle_domain_event(event: Dict[str, Any]):
    print(f"Processing event: {event['event_type']}")

# Subscribe to durable stream with consumer group
await event_bus.subscribe_stream(
    channel="transport.broker-connection-events",
    handler=handle_domain_event,
    group="event-processor-workers",
    consumer="worker-1",
    batch_size=500,      # Max events per poll
    block_ms=10000       # Poll timeout
)
```

### 6. Batch Publishing

```python
# Publish multiple events efficiently
events = [
    {"event_type": "OrderPlaced", "order_id": "1"},
    {"event_type": "OrderPlaced", "order_id": "2"},
    {"event_type": "OrderPlaced", "order_id": "3"}
]

await event_bus.publish_batch(
    channel="transport.order-events",
    events_data_list=events,
    partition_key="user-123"  # Optional: ensure same partition
)
```

## Advanced Patterns

### 1. Mark Channel as Critical

Critical channels get more aggressive reliability:
- Lower failure threshold (3 vs 5)
- Shorter reset timeout (15s vs 30s)
- More retry attempts (5 vs 3)

```python
# Mark channel as critical (before first publish)
event_bus.mark_channel_as_critical("transport.order-events")

# Now publishes to this channel use enhanced reliability
await event_bus.publish_stream("transport.order-events", event_data)
```

### 2. Custom Retry Configuration

```python
from app.infra.reliability.retry import RetryConfig

# Configure per-topic retry in EventBusConfig
config = EventBusConfig.from_env()
config.add_topic_config(
    topic_name="critical-events",
    topic_type="stream",
    retry_config=RetryConfig(
        max_attempts=10,
        initial_delay_ms=50,
        max_delay_ms=30000,
        backoff_factor=1.5
    )
)
```

### 3. Dead Letter Queue (DLQ)

Failed messages automatically go to DLQ if enabled:

```python
# Enable DLQ in config (.env)
ENABLE_DLQ=true
DLQ_TOPIC_SUFFIX=.dlq

# Failed events go to: {channel}.dlq
# Example: transport.order-events → transport.order-events.dlq
```

DLQ events include metadata:
```python
{
    # Original event data
    "event_id": "...",
    "event_type": "OrderPlaced",

    # DLQ metadata
    "_dlq_metadata": {
        "original_channel": "transport.order-events",
        "error_type": "KafkaConnectionError",
        "error_message": "Connection refused",
        "failed_at": "2025-11-10T12:00:00Z",
        "retry_count": 3
    }
}
```

### 4. Event Validation

Register events in Pydantic registry:

```python
# app/infra/event_bus/event_registry.py
from app.common.base.base_model import BaseEvent

class OrderPlacedEvent(BaseEvent):
    event_type: Literal["OrderPlaced"] = "OrderPlaced"
    order_id: str
    symbol: str
    quantity: int

# Register in EVENT_TYPE_TO_PYDANTIC_MODEL
EVENT_TYPE_TO_PYDANTIC_MODEL = {
    "OrderPlaced": OrderPlacedEvent,
    # ... other events
}
```

Validation happens automatically on publish:
```python
# Valid event - passes
await event_bus.publish_stream("orders", {
    "event_type": "OrderPlaced",
    "order_id": "123",
    "symbol": "AAPL",
    "quantity": 100
})

# Invalid event - rejected (missing quantity)
await event_bus.publish_stream("orders", {
    "event_type": "OrderPlaced",
    "order_id": "123",
    "symbol": "AAPL"
    # ValidationError logged, event NOT sent
})
```

### 5. Exactly-Once Delivery (Outbox Pattern)

For critical operations requiring exactly-once semantics:

```python
from app.infra.event_store.outbox_service import OutboxService

outbox = OutboxService(event_bus, pg_client)

# Publish with transaction guarantee
async with pg_client.transaction() as conn:
    # Save to database
    await conn.execute("INSERT INTO orders (...) VALUES (...)")

    # Queue event in outbox (same transaction)
    await outbox.queue_event(
        stream_name="transport.order-events",
        event_data={"event_type": "OrderPlaced", ...},
        transaction_conn=conn
    )
    # Commit transaction

# Background worker processes outbox → publishes to EventBus
# Guarantees: event published IFF database committed
```

## Health Monitoring

### 1. Health Check

```python
health = await event_bus.health_check()

# Returns:
{
    "circuit_breakers": {
        "transport.order-events": {
            "state": "CLOSED",
            "failure_count": 0,
            "consecutive_successes": 10,
            "total_failures": 2,
            "total_success": 100,
            "last_failure_time": None
        }
    },
    "open_circuits": [],
    "open_circuits_count": 0,
    "adapter": {
        "healthy": True,
        "details": {
            "ping_successful": True,
            "producer_started": True,
            "messages_sent": 1523,
            "messages_received": 1520,
            "active_consumers": 3
        }
    },
    "healthy": True,
    "config": {
        "dlq_enabled": True,
        "validation_enabled": True,
        "critical_channels": ["transport.order-events"],
        "total_channels_monitored": 12
    }
}
```

### 2. Circuit Breaker Status

```python
# Get status for all circuit breakers
status = await event_bus.get_circuit_breaker_status()

# Check specific channel
if status["transport.order-events"]["state"] == "OPEN":
    print("Circuit breaker is open - messages blocked!")
```

### 3. Connection Check

```python
# Quick ping test
is_connected = await event_bus.check_connection()
if not is_connected:
    print("EventBus adapter connection failed")
```

## RedpandaTransportAdapter Specifics

### 1. Topic Naming Convention

```
{prefix}.{category}.{name}

Examples:
- transport.broker-connection-events  (durable stream)
- realtime.price-updates              (pub/sub)
- system.worker-events                (system events)
- saga.user-deletion                  (saga orchestration)
- eventstore.all-events               (event store)
```

**Categories**:
- `transport.*` - Domain event streams (durable, 7 days retention)
- `realtime.*` - Real-time pub/sub (ephemeral, hours retention)
- `system.*` - System events (DLQ, worker status)
- `saga.*` - Saga orchestration events
- `eventstore.*` - Event store topics (10 year retention)

### 2. Partition Assignment Strategy

**CooperativeStickyAssignor** (Kafka 2.4+):
- Incremental rebalancing (no stop-the-world)
- Zero downtime during partition reassignment
- Avoids "assigned to multiple consumers" warnings
- 3-5s rebalance vs 30-60s with traditional assignor

```python
# Configured in RedpandaTransportAdapter
partition_assignment_strategy = "sticky"  # Uses CooperativeStickyAssignor
```

**Fallback**: StickyPartitionAssignor (minimizes partition movement)

### 3. Consumer Group Management

```python
# Worker-specific configuration integration
from app.config.worker_consumer_groups import WorkerType

adapter = RedpandaTransportAdapter(
    bootstrap_servers="localhost:19092",
    client_id="event-processor",
    worker_type=WorkerType.EVENT_PROCESSOR  # Auto-configures consumer groups
)

# Worker-specific consumer groups:
# - event-processor-workers (EVENT_PROCESSOR)
# - integrity-checker-workers (DATA_INTEGRITY)
# - recovery-workers (CONNECTION_RECOVERY)
```

### 4. Commit Strategy

**Smart batching** to reduce commit overhead:

```python
# Commit triggers:
# 1. Batch size reached (default: 100 messages)
# 2. Time interval passed (default: 5 seconds)

# Configure via env:
KAFKA_COMMIT_BATCH_SIZE=100
KAFKA_COMMIT_INTERVAL_MS=5000
```

**Benefits**:
- Reduces Redpanda load (fewer commit requests)
- Better throughput (batch processing)
- Automatic recovery on failure (uncommitted messages replayed)

### 5. Connection Pool Monitoring

```python
health = await adapter.health_check()

# Monitor pool exhaustion:
{
    "active_consumers": 15,
    "total_consumers": 15,
    "consumer_error_rate": 0.2,  # 0.2% errors
    "consumers": {
        "transport.order-events:event-processor-workers": {
            "messages_processed": 10523,
            "errors": 2,
            "last_message_age": 1.5,  # seconds
            "active": True,
            "consecutive_empty_fetches": 0,
            "current_backoff": 0.0
        }
    }
}
```

## Configuration Reference

### EventBusConfig (.env)

```bash
# Core
ENABLE_EVENT_BUS=true
ENABLE_DLQ=true
DLQ_TOPIC_SUFFIX=.dlq

# Validation
EVENT_BUS_VALIDATE_ON_PUBLISH=true

# Circuit Breaker (per channel)
EVENT_BUS_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
EVENT_BUS_CIRCUIT_BREAKER_SUCCESS_THRESHOLD=3
EVENT_BUS_CIRCUIT_BREAKER_TIMEOUT_SECONDS=30
EVENT_BUS_CIRCUIT_BREAKER_HALF_OPEN_CALLS=3

# Retry (publish)
EVENT_BUS_PUBLISH_RETRY_MAX_ATTEMPTS=5
EVENT_BUS_PUBLISH_RETRY_INITIAL_DELAY_MS=200
EVENT_BUS_PUBLISH_RETRY_MAX_DELAY_MS=5000
EVENT_BUS_PUBLISH_RETRY_BACKOFF_FACTOR=2.0

# Consumer
EVENT_BUS_SUB_BATCH_SIZE=10
EVENT_BUS_SUB_BLOCK_MS=10000
EVENT_BUS_CONSUMER_POLL_TIMEOUT_MS=15000
```

### TransportConfig (.env)

```bash
# Redpanda/Kafka
REDPANDA_BOOTSTRAP_SERVERS=localhost:19092
REDPANDA_CLIENT_ID=tradecore

# Topic prefix
KAFKA_TOPIC_PREFIX=

# Producer
KAFKA_PRODUCER_ACKS=all
KAFKA_PRODUCER_COMPRESSION_TYPE=lz4
KAFKA_PRODUCER_LINGER_MS=10
KAFKA_PRODUCER_BATCH_SIZE=16384

# Consumer
KAFKA_CONSUMER_GROUP_ID_PREFIX=tradecore
KAFKA_CONSUMER_SESSION_TIMEOUT_MS=45000
KAFKA_CONSUMER_HEARTBEAT_INTERVAL_MS=3000
KAFKA_CONSUMER_MAX_POLL_RECORDS=500
KAFKA_CONSUMER_AUTO_OFFSET_RESET=earliest
KAFKA_CONSUMER_PARTITION_ASSIGNMENT_STRATEGY=sticky

# Commit
KAFKA_COMMIT_INTERVAL_MS=5000
KAFKA_COMMIT_BATCH_SIZE=100
```

## Best Practices

### 1. Channel Naming

✅ **Good**:
```python
await event_bus.publish_stream("transport.order-events", ...)
await event_bus.publish("realtime.price-updates", ...)
```

❌ **Bad**:
```python
await event_bus.publish_stream("my-events", ...)  # Unclear category
await event_bus.publish("OrderEvents", ...)        # Wrong convention
```

### 2. Event Structure

✅ **Good**:
```python
{
    "event_type": "OrderPlaced",     # Required
    "order_id": "uuid",              # Domain ID
    "symbol": "AAPL",
    "quantity": 100,
    "timestamp": "2025-11-10T...",   # ISO format
    "user_id": "user-123"            # Context
}
```

❌ **Bad**:
```python
{
    "type": "order_placed",          # Wrong field name
    "data": {...},                   # Don't nest unnecessarily
    "time": 1699622400               # Use ISO string, not epoch
}
```

### 3. Error Handling

✅ **Good**:
```python
try:
    await event_bus.publish_stream("transport.orders", event)
except CircuitBreakerOpenError:
    # Circuit breaker tripped - system unhealthy
    logger.error("EventBus circuit breaker open")
    # Fallback: queue locally, retry later
except Exception as e:
    logger.error(f"Failed to publish: {e}")
    # Don't crash the application
```

❌ **Bad**:
```python
# No error handling - crashes on failure
await event_bus.publish_stream("transport.orders", event)
```

### 4. Graceful Shutdown

✅ **Good**:
```python
async def shutdown():
    logger.info("Shutting down EventBus...")
    await event_bus.close()  # Waits for in-flight messages
    logger.info("EventBus closed")
```

❌ **Bad**:
```python
# Abrupt shutdown - messages lost
await event_bus.close()
sys.exit(0)  # Doesn't wait for close to complete
```

### 5. Testing

✅ **Good**:
```python
# Use in-memory adapter for tests
from app.infra.event_bus.memory_adapter import MemoryTransportAdapter

adapter = MemoryTransportAdapter()
event_bus = EventBus(adapter, validate_on_publish=True)

# Test message flow
await event_bus.publish("test.channel", {"event_type": "Test"})
messages = adapter.get_published_messages("test.channel")
assert len(messages) == 1
```

## Troubleshooting

### Circuit Breaker Keeps Opening

**Symptoms**: Messages blocked, logs show "Circuit breaker is OPEN"

**Diagnosis**:
```python
status = await event_bus.get_circuit_breaker_status()
print(status["transport.order-events"])
```

**Solutions**:
1. Check Redpanda connectivity: `docker ps`, `nc -zv localhost 19092`
2. Review failure logs for root cause
3. Increase failure threshold if transient errors
4. Wait for reset timeout (default: 30s)

### Messages Not Being Consumed

**Symptoms**: Messages published but handler not called

**Diagnosis**:
```python
health = await event_bus.health_check()
print(health["adapter"]["details"]["active_consumers"])
```

**Solutions**:
1. Verify consumer is subscribed: `await event_bus.subscribe_stream(...)`
2. Check consumer group lag in Redpanda Console
3. Ensure consumer task not crashed (check worker logs)
4. Verify topic exists: `rpk topic list`

### High Memory Usage

**Symptoms**: Memory grows over time, OOM errors

**Diagnosis**:
```bash
# Check Redpanda metrics
rpk topic describe transport.order-events

# Check consumer lag
rpk group describe event-processor-workers
```

**Solutions**:
1. Reduce `batch_size` in `subscribe_stream()`
2. Increase commit frequency (lower `KAFKA_COMMIT_INTERVAL_MS`)
3. Add backpressure: limit concurrent message processing
4. Check for memory leaks in event handlers

### DLQ Growing

**Symptoms**: DLQ topic has many messages

**Diagnosis**:
```bash
# Check DLQ size
rpk topic describe transport.order-events.dlq
```

**Solutions**:
1. Review DLQ messages for common error patterns
2. Fix root cause (validation errors, handler bugs)
3. Replay DLQ messages after fix (manual or automated)

## Migration from Old Patterns

### Before (Manual Kafka)
```python
from aiokafka import AIOKafkaProducer

producer = AIOKafkaProducer(bootstrap_servers="localhost:19092")
await producer.start()
await producer.send_and_wait("my-topic", value=json.dumps(event).encode())
await producer.stop()
```

### After (EventBus)
```python
from app.infra.event_bus.event_bus import get_event_bus

event_bus = get_event_bus()  # Singleton, already started
await event_bus.publish_stream("transport.my-events", event)
# Circuit breaker, retry, DLQ, validation - all automatic
```

**Benefits**:
- No manual connection management
- Built-in reliability (circuit breaker, retry)
- Event validation
- Health monitoring
- Consistent error handling

## Related Documentation

- **Circuit Breaker**: See `CIRCUIT_BREAKER_GUIDE.md`
- **Event Store**: See `docs/event_store_architecture.md`
- **Redpanda Architecture**: See `docs/redpanda_comprehensive_architecture_v06.md`
- **Worker Configuration**: See `app/config/worker_consumer_groups.py`

## Summary

The EventBus provides a unified, reliable messaging layer for TradeCore:

- **Two modes**: Pub/Sub (ephemeral) and Stream (durable)
- **Built-in reliability**: Circuit breakers, retry, DLQ
- **Event validation**: Pydantic registry integration
- **Health monitoring**: Metrics, status checks
- **Production-ready**: Handles Kafka/Redpanda complexity

Use **Pub/Sub** for real-time notifications, **Stream** for domain events and audit logs. Mark critical channels for enhanced reliability. Monitor circuit breaker status to detect system issues early.
