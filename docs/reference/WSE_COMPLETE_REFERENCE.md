# WebSocket Streaming Engine (WSE) - Complete Reference

**For:** Future Projects | **Status:** Reference | **Updated:** Nov 16, 2025

---

## Overview

**WebSocket Streaming Engine (WSE)** is a real-time event streaming system that bridges event-driven backends with reactive frontends.

**Purpose:** Stream domain events from EventStore to WebSocket clients with guaranteed delivery, multi-tenancy, and instant snapshots.

**Domain Agnostic:** Works for any event-driven system (trading, chat, collaboration, IoT, etc.)

---

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                  WSE Complete Architecture                      │
└────────────────────────────────────────────────────────────────┘

BACKEND (Event-Driven)
──────────────────────

┌──────────────────┐
│ Domain Events    │ ──→ EventBus (Redpanda/Kafka)
│ (Published by    │         ↓
│  Command         │         ↓
│  Handlers)       │    ┌─────────────┐
└──────────────────┘    │ EventStore  │
                        │ (Persistent │
                        │  Event Log) │
                        └─────────────┘
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
          ┌───────────────┐   ┌──────────────┐
          │ Projectors    │   │ WSE Consumer │
          │ (Read Model)  │   │ (Real-time)  │
          └───────────────┘   └──────────────┘
                                      ↓
                            ┌─────────────────┐
                            │ WSE Domain      │
                            │ Publisher       │
                            │ (Transform +    │
                            │  Route)         │
                            └─────────────────┘
                                      ↓
                            ┌─────────────────┐
                            │ Redis Pub/Sub   │
                            │ (User Channels) │
                            └─────────────────┘
                                      ↓
                    ┌─────────────────┴─────────────┐
                    ↓                               ↓
          ┌──────────────────┐          ┌──────────────────┐
          │ WSE Event        │          │ WSE Event        │
          │ Transformer      │          │ Transformer      │
          │ (Protocol v2)    │          │ (Protocol v2)    │
          └──────────────────┘          └──────────────────┘
                    ↓                               ↓
          ┌──────────────────┐          ┌──────────────────┐
          │ WebSocket        │          │ WebSocket        │
          │ Connection 1     │          │ Connection 2     │
          │ (User A)         │          │ (User B)         │
          └──────────────────┘          └──────────────────┘
                    ↓                               ↓
FRONTEND
────────
          ┌──────────────────┐          ┌──────────────────┐
          │ React Query      │          │ React Query      │
          │ Cache (User A)   │          │ Cache (User B)   │
          └──────────────────┘          └──────────────────┘
                    ↓                               ↓
          ┌──────────────────┐          ┌──────────────────┐
          │ UI Components    │          │ UI Components    │
          │ (User A)         │          │ (User B)         │
          └──────────────────┘          └──────────────────┘
```

---

## Components

### 1. WSE Consumer

**Purpose:** Consume events from EventStore (Kafka/Redpanda) and route to WSE Domain Publisher

**File:** `app/wse/consumers/wse_event_consumer.py`

```python
class WSEEventConsumer:
    def __init__(self, event_bus, domain_publisher):
        self.event_bus = event_bus
        self.domain_publisher = domain_publisher

    async def consume_events(self):
        # Subscribe to all domain event topics
        async for event in self.event_bus.subscribe_all():
            # Route to domain publisher
            await self.domain_publisher.publish_event(event)
```

**Key Features:**
- Consumes from multiple topics (broker-connection, broker-account, order, position, etc.)
- Consumer group for distributed processing
- Exactly-once delivery guarantee (manual offset management)
- Error handling and retry logic

---

### 2. WSE Domain Publisher

**Purpose:** Transform domain events to WebSocket format and route to user channels

**File:** `app/wse/publishers/domain_publisher.py`

```python
class WSEDomainPublisher:
    def __init__(self, redis, event_transformer):
        self.redis = redis
        self.event_transformer = event_transformer

    async def publish_event(self, event: dict):
        # 1. Extract user_id for routing
        user_id = self._extract_user_id(event)
        if not user_id:
            return  # Skip events without user context

        # 2. Transform to WebSocket format
        ws_event = self._transform_event(event)

        # 3. Publish to user-specific Redis channel
        channel = f"wse:user:{user_id}"
        await self.redis.publish(channel, json.dumps(ws_event))

    def _transform_event(self, event: dict) -> dict:
        event_type = event.get('event_type')

        # Map domain event type → WebSocket event type
        ws_event_type = EVENT_TYPE_MAPPING.get(event_type, event_type)

        # Build WebSocket event
        ws_event = {
            'event_type': ws_event_type,
            'original_event_type': event_type,  # CRITICAL: Preserve original
            'user_id': event.get('user_id'),
            'data': self._transform_payload(event),
            'timestamp': event.get('timestamp'),
            'event_id': event.get('event_id'),
        }

        return ws_event
```

**Event Type Mapping:**

```python
EVENT_TYPE_MAPPING = {
    # Broker Connection Events
    'BrokerConnectionEstablished': 'broker_connection_update',
    'BrokerConnectionEstablishedSagaCompleted': 'broker_connection_update',
    'BrokerDisconnected': 'broker_connection_update',

    # Broker Account Events
    'BrokerAccountLinked': 'broker_account_update',
    'AccountDataFromBrokerUpdated': 'broker_account_update',

    # Order Events
    'OrderPlaced': 'order_update',
    'OrderFilled': 'order_filled',
    'OrderCancelled': 'order_cancelled',
    'OrderRejected': 'order_rejected',

    # Position Events
    'PositionOpened': 'position_update',
    'PositionClosed': 'position_update',
}
```

**Key Features:**
- Multi-tenancy (user_id-based routing)
- Event transformation (domain → WebSocket)
- Original event type preservation
- Redis Pub/Sub for fan-out

---

### 3. WSE Event Transformer

**Purpose:** Format events to WSE Protocol v2 specification

**File:** `app/wse/core/event_transformer.py`

```python
class EventTransformer:
    @staticmethod
    def transform_to_ws_protocol(event: dict, metadata: dict) -> dict:
        event_type = event.get('event_type')
        ws_event_type = EVENT_TYPE_MAPPING.get(event_type, event_type)

        # Build WSE Protocol v2 event
        ws_event = {
            'v': 2,  # Protocol version
            'id': metadata.get('event_id', str(uuid.uuid4())),
            't': ws_event_type,  # Transformed type
            'ts': metadata.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'seq': metadata.get('sequence', 0),
            'p': EventTransformer._transform_payload(ws_event_type, event),
        }

        # CRITICAL: Preserve original event type (Nov 16, 2025 fix)
        if event_type != ws_event_type:
            ws_event['original_event_type'] = event_type

        # Add latency metadata
        if metadata.get('latency_ms'):
            ws_event['latency_ms'] = metadata['latency_ms']

        return ws_event
```

**WSE Protocol v2 Specification:**

```typescript
interface WSEvent {
  v: 2;                      // Protocol version
  id: string;                // Event ID (UUID)
  t: string;                 // Event type (transformed, e.g., "order_update")
  ts: string;                // Timestamp (ISO 8601)
  seq: number;               // Sequence number
  p: any;                    // Payload (event-specific data)
  original_event_type?: string;  // Original domain event type (if transformed)
  latency_ms?: number;       // Event latency (for monitoring)
}
```

---

### 4. WSE WebSocket Server

**Purpose:** Maintain WebSocket connections and deliver events to clients

**File:** `app/wse/websocket/wse_server.py`

```python
class WSEWebSocketServer:
    def __init__(self, redis):
        self.redis = redis
        self.connections: Dict[str, Set[WebSocket]] = {}  # user_id → {websockets}

    async def handle_connection(self, websocket: WebSocket, user_id: str):
        # 1. Accept WebSocket connection
        await websocket.accept()

        # 2. Register connection
        if user_id not in self.connections:
            self.connections[user_id] = set()
        self.connections[user_id].add(websocket)

        # 3. Subscribe to user-specific Redis channel
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(f"wse:user:{user_id}")

        # 4. Forward messages from Redis → WebSocket
        async for message in pubsub.listen():
            if message['type'] == 'message':
                event = json.loads(message['data'])
                await websocket.send_json(event)

    async def disconnect(self, websocket: WebSocket, user_id: str):
        # Unregister connection
        self.connections[user_id].discard(websocket)
        if not self.connections[user_id]:
            del self.connections[user_id]
```

**Features:**
- FastAPI WebSocket integration
- Connection pooling (multiple tabs per user)
- Automatic reconnection handling
- Heartbeat/ping-pong for connection health
- Graceful disconnect cleanup

---

### 5. WSE Handlers

**Purpose:** Handle special events (saga completion, snapshot requests)

**File:** `app/wse/websocket/wse_handlers.py`

```python
class WSEHandlers:
    def __init__(self, pg_client, query_client):
        self.pg_client = pg_client
        self.query_client = query_client

    async def handle_broker_connection_update(self, event: dict):
        # Detect saga completion via original_event_type
        original_type = event.get('original_event_type', event['event_type'])

        if original_type == 'BrokerConnectionEstablishedSagaCompleted':
            user_id = event.get('user_id')

            # Query fresh data from PostgreSQL (saga guarantees data is ready)
            accounts = await self.query_client.get_accounts(user_id)

            # Send instant snapshot
            await self._send_account_snapshot(user_id, accounts)

        # Forward event to client
        await self._forward_to_client(event)

    async def handle_snapshot_request(self, request: dict, user_id: str):
        # Client requests snapshot (e.g., on page refresh)
        snapshot_type = request.get('snapshot_type')

        if snapshot_type == 'accounts':
            accounts = await self.query_client.get_accounts(user_id)
            await self._send_account_snapshot(user_id, accounts)

        elif snapshot_type == 'orders':
            orders = await self.query_client.get_orders(user_id)
            await self._send_order_snapshot(user_id, orders)

    async def _send_account_snapshot(self, user_id: str, accounts: list):
        snapshot = {
            'v': 2,
            't': 'account_snapshot',
            'p': {
                'accounts': accounts,
                'total': len(accounts),
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
        }
        await self._send_to_user(user_id, snapshot)
```

**Handler Types:**
- **Saga Completion:** Detect completion → query DB → send snapshot
- **Snapshot Request:** Client request → query DB → send snapshot
- **Event Forwarding:** Route domain events → clients

---

## Data Flow

### 1. Event Publishing (Backend → Frontend)

```
┌─────────────┐
│ Command     │ → CreateBrokerConnection(user_id="123")
│ Handler     │
└─────────────┘
       ↓
┌─────────────┐
│ Aggregate   │ → apply(BrokerConnectionEstablished)
└─────────────┘
       ↓
┌─────────────┐
│ EventBus    │ → publish(transport.broker-connection-events)
└─────────────┘
       ↓
┌─────────────┐
│ EventStore  │ → persist(offset=100)
└─────────────┘
       ↓
┌─────────────┐
│ WSE         │ → consume(offset=100)
│ Consumer    │
└─────────────┘
       ↓
┌─────────────┐
│ WSE Domain  │ → transform(event) + extract user_id="123"
│ Publisher   │
└─────────────┘
       ↓
┌─────────────┐
│ Redis       │ → publish(wse:user:123, event)
│ Pub/Sub     │
└─────────────┘
       ↓
┌─────────────┐
│ WSE         │ → forward to WebSocket connection(user_id="123")
│ WebSocket   │
│ Server      │
└─────────────┘
       ↓
┌─────────────┐
│ Frontend    │ → EventHandlers.handleEvent(event)
│ (User 123)  │      ↓
└─────────────┘   queryClient.setQueryData(...)
                     ↓
                  UI Update (instant)
```

**Latency Breakdown:**
- EventBus publish: ~10ms
- EventStore persist: ~20ms
- WSE Consumer: ~5ms
- Redis Pub/Sub: ~2ms
- WebSocket delivery: ~3ms
- **Total:** ~40ms (backend → frontend)

---

### 2. Instant Snapshots (Saga Completion)

```
Time  Event                                    Action
──────────────────────────────────────────────────────────────

T+0s  User connects broker                     Command received

T+0.5s Saga discovers accounts                 API calls to broker

T+1.0s Saga publishes BrokerAccountLinked × N  Domain events

T+1.1s Projectors process events               PostgreSQL writes

T+1.2s Saga waits 150ms                        Propagation delay

T+1.35s Saga publishes SagaCompleted           Domain event

T+1.4s WSE Consumer receives event             EventStore → WSE

T+1.41s WSE Domain Publisher transforms        Preserves original_event_type

T+1.42s Redis Pub/Sub forwards                 Channel: wse:user:123

T+1.43s WSE Handler detects saga completion    Check original_event_type

T+1.44s WSE Handler queries PostgreSQL         Fetch fresh accounts

T+1.45s WSE Handler sends snapshot             WebSocket → Frontend

T+1.46s Frontend receives snapshot             EventHandlers.handleSnapshot()

T+1.47s React Query cache updated              setQueryData(accounts)

T+1.48s UI renders accounts                    ✅ USER SEES DATA!
```

**Total:** 1.48s from user action to data visible

---

### 3. Incremental Updates

```
T+0s  Account balance updates (broker API)     External event

T+0.1s Backend receives webhook/streaming      HTTP POST / WebSocket

T+0.2s Command handler processes               UpdateAccountBalance command

T+0.3s Aggregate applies event                 AccountDataFromBrokerUpdated

T+0.4s EventBus publishes                      transport.broker-account-events

T+0.5s EventStore persists                     offset=200

T+0.55s Projector updates PostgreSQL           Balance updated in DB

T+0.6s WSE Consumer receives                   EventStore → WSE

T+0.61s WSE Domain Publisher transforms        broker_account_update event

T+0.62s Redis Pub/Sub forwards                 Channel: wse:user:123

T+0.63s WSE WebSocket delivers                 WebSocket → Frontend

T+0.64s Frontend receives update               EventHandlers.handleUpdate()

T+0.65s React Query immutable merge            setQueryData((old) => ...)

T+0.66s Structural sharing check               prev === current?

T+0.67s UI updates (if changed)                ✅ BALANCE UPDATED!
```

**Total:** 670ms from external event to UI update

---

## Multi-Tenancy

### User Isolation

```python
# All events must have user_id for routing
event = {
    'event_type': 'ResourceCreated',
    'user_id': '123',  # REQUIRED
    'resource_id': '456',
    # ...
}

# WSE routes to user-specific channel
channel = f"wse:user:{user_id}"  # wse:user:123

# Only WebSocket connections for user_id=123 receive this event
```

### Redis Channel Pattern

```
wse:user:{user_id}       # User-specific events
wse:global               # Broadcast to all users (rare)
wse:role:{role_id}       # Role-based routing (optional)
wse:team:{team_id}       # Team-based routing (optional)
```

---

## Snapshot System

### Snapshot Types

#### 1. Saga Completion Snapshot (Automatic)

Triggered by saga completion events

```python
# Backend: Saga publishes completion event
completion_event = {
    'event_type': 'ProcessCompletedSagaCompleted',
    'user_id': user_id,
    'process_id': process_id,
}

# WSE Handler detects completion
if event.get('original_event_type') == 'ProcessCompletedSagaCompleted':
    # Query fresh data (process guaranteed complete in DB)
    resources = await query_resources(user_id)

    # Send snapshot
    await send_snapshot({
        't': 'resource_snapshot',
        'p': {'resources': resources}
    })
```

#### 2. Client-Requested Snapshot (Manual)

Triggered by client request (e.g., page refresh)

```typescript
// Frontend requests snapshot
wseApi.requestSnapshot({ snapshot_type: 'accounts' });
```

```python
# Backend handles request
@router.post("/wse/snapshot/request")
async def request_snapshot(request: SnapshotRequest, user: User):
    snapshot_type = request.snapshot_type

    if snapshot_type == 'accounts':
        accounts = await query_accounts(user.id)
        await wse.send_snapshot(user.id, {
            't': 'account_snapshot',
            'p': {'accounts': accounts}
        })
```

#### 3. Periodic Snapshot (Scheduled)

For large datasets that change frequently

```python
# Scheduled job (every 5 minutes)
async def periodic_snapshot_job():
    for user_id in active_users:
        resources = await query_resources(user_id)
        await wse.send_snapshot(user_id, {
            't': 'resource_snapshot',
            'p': {'resources': resources}
        })
```

---

## Error Handling

### Connection Errors

```python
try:
    await websocket.send_json(event)
except WebSocketDisconnect:
    # Client disconnected
    await cleanup_connection(user_id, websocket)
except Exception as e:
    # Other errors
    log.error(f"Failed to send event: {e}")
    # Don't crash the server - continue
```

### Event Processing Errors

```python
try:
    ws_event = transform_event(event)
    await publish_to_redis(ws_event)
except Exception as e:
    # Log error but don't lose event
    log.error(f"Event transformation failed: {e}", extra={'event': event})
    # Fallback: send raw event or dead-letter queue
```

### Backpressure Handling

```python
# If Redis channel is slow, buffer events
class EventBuffer:
    def __init__(self, max_size=1000):
        self.buffer = asyncio.Queue(maxsize=max_size)

    async def add(self, event):
        try:
            self.buffer.put_nowait(event)
        except asyncio.QueueFull:
            # Drop oldest event (or implement strategy)
            oldest = await self.buffer.get()
            await self.buffer.put(event)
            log.warning(f"Buffer full, dropped event: {oldest['id']}")
```

---

## Monitoring

### Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Events processed
wse_events_processed_total = Counter(
    'wse_events_processed_total',
    'Total events processed by WSE',
    ['event_type', 'status']
)

# Event latency
wse_event_latency_ms = Histogram(
    'wse_event_latency_ms',
    'Event latency from EventStore to WebSocket delivery',
    buckets=[10, 25, 50, 100, 250, 500, 1000]
)

# Active connections
wse_active_connections = Gauge(
    'wse_active_connections',
    'Number of active WebSocket connections',
    ['user_id']
)

# Snapshots sent
wse_snapshots_sent_total = Counter(
    'wse_snapshots_sent_total',
    'Total snapshots sent',
    ['snapshot_type', 'trigger']
)
```

### Logging

```python
import structlog

log = structlog.get_logger(__name__)

# Event processing
log.info("wse.event.processed", event_type=event_type, user_id=user_id, latency_ms=latency)

# Connection events
log.info("wse.connection.established", user_id=user_id, connection_id=conn_id)
log.info("wse.connection.closed", user_id=user_id, connection_id=conn_id, duration_s=duration)

# Snapshot events
log.info("wse.snapshot.sent", snapshot_type=snapshot_type, user_id=user_id, resource_count=count)

# Errors
log.error("wse.error", error=str(e), event_id=event_id, user_id=user_id)
```

---

## Configuration

### Environment Variables

```bash
# WSE Configuration
WSE_REDIS_URL=redis://localhost:6379/0
WSE_CONSUMER_GROUP=wse-consumer-group
WSE_CONSUMER_ID=wse-consumer-1
WSE_HEARTBEAT_INTERVAL=30  # seconds
WSE_MAX_CONNECTIONS_PER_USER=5
WSE_SNAPSHOT_TTL=300  # seconds
WSE_BUFFER_SIZE=1000
```

### Python Configuration

```python
# app/config/wse_config.py
from pydantic import BaseSettings

class WSEConfig(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    consumer_group: str = "wse-consumer-group"
    consumer_id: str = "wse-consumer-1"
    heartbeat_interval: int = 30
    max_connections_per_user: int = 5
    snapshot_ttl: int = 300
    buffer_size: int = 1000

    class Config:
        env_prefix = "WSE_"
```

---

## Testing

### Unit Tests

```python
# Test event transformation
async def test_event_transformation():
    event = {
        'event_type': 'ResourceCreated',
        'user_id': '123',
        'resource_id': '456',
    }

    ws_event = EventTransformer.transform_to_ws_protocol(event, {})

    assert ws_event['v'] == 2
    assert ws_event['t'] == 'resource_created'
    assert ws_event['original_event_type'] == 'ResourceCreated'
```

### Integration Tests

```python
# Test end-to-end flow
async def test_event_delivery():
    # Publish event
    await event_bus.publish('transport.resource-events', {
        'event_type': 'ResourceCreated',
        'user_id': '123',
    })

    # Wait for WebSocket delivery
    async with websocket_connect(f'ws://localhost/wse?user_id=123') as ws:
        message = await ws.receive_json()
        assert message['t'] == 'resource_created'
```

---

## Summary

**WSE Components:**
1. **Consumer:** EventStore → WSE
2. **Domain Publisher:** Transform + Route events
3. **Event Transformer:** Format to protocol v2
4. **WebSocket Server:** Deliver to clients
5. **Handlers:** Special events (saga completion, snapshots)

**Key Features:**
- Real-time delivery (~40ms latency)
- Multi-tenancy (user_id-based routing)
- Instant snapshots (saga completion triggers)
- Guaranteed delivery (Redis Pub/Sub)
- Protocol v2 (structured, versioned)

**Benefits:**
- Event-driven architecture
- Scalable (Redis fan-out)
- Reliable (offset tracking)
- Observable (Prometheus + logs)
- Testable (unit + integration tests)

---

**Author:** TradeCore Team
**Last Updated:** November 16, 2025
**Version:** 2.0 (Reference)
