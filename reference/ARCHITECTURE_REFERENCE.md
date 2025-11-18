# Event-Driven Architecture Reference

**Purpose**: Reusable architecture patterns for event-sourced CQRS systems
**Audience**: Architects and senior developers building new event-driven systems
**Based On**: TradeCore v0.5 (November 2025)

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Event Store Pattern](#event-store-pattern)
3. [Event Bus Pattern](#event-bus-pattern)
4. [Exactly-Once Delivery](#exactly-once-delivery)
5. [Technology Stack](#technology-stack)
6. [Design Decisions](#design-decisions)
7. [Implementation Checklist](#implementation-checklist)

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer (FastAPI)                      │
│  - REST endpoints                                                │
│  - WebSocket streaming                                           │
│  - Authentication/Authorization                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Command/Query Handlers                        │
│  - Command validation                                            │
│  - Business logic orchestration                                  │
│  - Query execution                                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────┬──────────────────────────────────────────┐
│   Write Side (CQRS)  │         Read Side (CQRS)                 │
├──────────────────────┼──────────────────────────────────────────┤
│  Domain Aggregates   │     PostgreSQL Read Models               │
│       ↓              │              ↑                            │
│  Event Store         │         Projectors                       │
│  (PostgreSQL)        │              ↑                            │
│       ↓              │              │                            │
│  Transactional       │              │                            │
│  Outbox              │              │                            │
└──────────────────────┴──────────────┼───────────────────────────┘
                              ↓       │
                    ┌─────────────────┴──────────────┐
                    │     Event Bus (Kafka/Redpanda)  │
                    │  - Durable event streams        │
                    │  - Consumer groups              │
                    │  - Exactly-once delivery        │
                    └─────────────────────────────────┘
```

### Component Interaction

```
User Request
    ↓
[API Endpoint]
    ↓
[Command Handler]
    ↓
[Aggregate.apply(Event)]
    ↓
[Event Store]
    ├─→ event_store table (10yr retention)
    └─→ event_outbox table (transactional)
    ↓
[PostgreSQL TRIGGER → NOTIFY]
    ↓
[Outbox Publisher (LISTEN)] (<5ms)
    ↓
[Kafka Topic]
    ├─→ Consumer Group A (Worker 1, 2, 3)
    ├─→ Consumer Group B (Worker 1)
    └─→ Consumer Group C (Worker 1, 2)
    ↓
[Projectors]
    ↓
[Read Models (PostgreSQL)]
    ↓
[Query Endpoints]
    ↓
User Response
```

---

## Event Store Pattern

### Purpose
Persist all domain events as immutable facts for:
- Complete audit trail (10-year retention)
- Event replay capability
- Debugging and analysis
- Regulatory compliance

### Implementation

**Tables**:
```sql
CREATE TABLE event_store (
    event_id UUID PRIMARY KEY,
    aggregate_id UUID NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_version INTEGER NOT NULL,
    event_type VARCHAR(200) NOT NULL,
    event_data JSONB NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    correlation_id UUID,
    causation_id UUID,
    saga_id UUID,
    metadata JSONB,
    UNIQUE (aggregate_id, aggregate_version)
);

CREATE INDEX idx_event_store_aggregate ON event_store(aggregate_id, aggregate_version);
CREATE INDEX idx_event_store_type ON event_store(event_type, timestamp);
CREATE INDEX idx_event_store_timestamp ON event_store(timestamp DESC);
```

**Aggregate Base Class**:
```python
class BaseAggregate:
    def __init__(self, aggregate_id: str, aggregate_type: str):
        self.id = aggregate_id
        self._type = aggregate_type
        self._version = 0
        self._uncommitted_events = []

    def apply(self, event: BaseEvent):
        """Apply event to aggregate state"""
        self._version += 1
        event.aggregate_version = self._version
        self._uncommitted_events.append(event)
        self._apply(event)

    def _apply(self, event: BaseEvent):
        """Route to specific handler"""
        handler_name = self._get_handler_name(event)
        handler = getattr(self, handler_name, None)
        if handler:
            handler(event)

    @staticmethod
    def _get_handler_name(event: BaseEvent) -> str:
        """Convert OrderCreatedEvent → _on_order_created_event"""
        class_name = event.__class__.__name__
        snake_case = re.sub('([a-z0-9])([A-Z])', r'\1_\2', class_name).lower()
        return f"_on_{snake_case}"

    def get_uncommitted_events(self) -> List[BaseEvent]:
        return self._uncommitted_events

    def clear_uncommitted_events(self):
        self._uncommitted_events = []
```

**Event Store Service**:
```python
class EventStore:
    async def save_aggregate(self, aggregate: BaseAggregate):
        """Save aggregate events atomically"""
        events = aggregate.get_uncommitted_events()
        if not events:
            return

        async with transaction() as conn:
            # 1. Save to event_store
            for event in events:
                await conn.execute(
                    """
                    INSERT INTO event_store (
                        event_id, aggregate_id, aggregate_type,
                        aggregate_version, event_type, event_data, timestamp
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    event.event_id, aggregate.id, aggregate._type,
                    event.aggregate_version, event.event_type,
                    json.dumps(event.dict()), event.timestamp
                )

            # 2. Save to outbox (same transaction)
            await self.outbox.save_events_to_outbox(events, conn)

        aggregate.clear_uncommitted_events()

    async def load_aggregate(
        self,
        aggregate_id: str,
        aggregate_type: str
    ) -> BaseAggregate:
        """Rebuild aggregate from events"""
        rows = await db.fetch(
            """
            SELECT event_id, event_type, event_data, aggregate_version
            FROM event_store
            WHERE aggregate_id = $1 AND aggregate_type = $2
            ORDER BY aggregate_version ASC
            """,
            aggregate_id, aggregate_type
        )

        # Create empty aggregate
        aggregate_class = self._get_aggregate_class(aggregate_type)
        aggregate = aggregate_class(aggregate_id)

        # Replay events
        for row in rows:
            event_data = json.loads(row['event_data'])
            event_class = self._get_event_class(row['event_type'])
            event = event_class(**event_data)
            aggregate._apply(event)
            aggregate._version = row['aggregate_version']

        return aggregate
```

### Concurrency Control

**Optimistic Locking**:
```python
async def save_aggregate(
    self,
    aggregate: BaseAggregate,
    expected_version: Optional[int] = None
):
    """Save with optimistic locking"""
    events = aggregate.get_uncommitted_events()

    async with transaction() as conn:
        if expected_version is not None:
            # Verify current version
            current_version = await conn.fetchval(
                """
                SELECT MAX(aggregate_version)
                FROM event_store
                WHERE aggregate_id = $1
                """,
                aggregate.id
            )

            if current_version != expected_version:
                raise ConcurrencyException(
                    f"Expected version {expected_version}, "
                    f"but found {current_version}"
                )

        # Save events...
```

---

## Event Bus Pattern

### Purpose
Distribute events across services for:
- Decoupled service communication
- Asynchronous processing
- Scalability (consumer groups)
- Reliability (durable storage)

### Implementation

**Redpanda/Kafka Configuration**:
```yaml
# docker-compose.yml
redpanda:
  image: redpandadata/redpanda:latest
  command:
    - redpanda start
    - --smp 1
    - --overprovisioned
    - --kafka-addr PLAINTEXT://0.0.0.0:29092,OUTSIDE://0.0.0.0:9092
    - --advertise-kafka-addr PLAINTEXT://redpanda:29092,OUTSIDE://localhost:9092
  ports:
    - 9092:9092  # Kafka API
    - 8081:8081  # Schema Registry
    - 8080:8080  # Admin Console
```

**Event Bus Service**:
```python
class EventBus:
    def __init__(self, bootstrap_servers: str):
        self._bootstrap_servers = bootstrap_servers
        self._producer = None
        self._consumers = {}

    async def publish(self, channel: str, event: dict):
        """Publish single event"""
        topic = f"transport.{channel}"

        await self._producer.send(
            topic,
            value=json.dumps(event).encode('utf-8'),
            key=event.get('aggregate_id', '').encode('utf-8')
        )

    async def publish_batch(self, channel: str, events: List[dict]):
        """Publish batch (more efficient)"""
        topic = f"transport.{channel}"

        for event in events:
            await self._producer.send(
                topic,
                value=json.dumps(event).encode('utf-8'),
                key=event.get('aggregate_id', '').encode('utf-8')
            )

        await self._producer.flush()

    async def subscribe(
        self,
        channel: str,
        handler: Callable,
        consumer_group: str,
        consumer_key: str
    ):
        """Subscribe to events"""
        topic = f"transport.{channel}"

        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id=consumer_group,
            enable_auto_commit=False,
            auto_offset_reset='earliest'
        )

        await consumer.start()

        # Start consumer loop
        asyncio.create_task(
            self._consumer_loop(consumer, handler, consumer_key)
        )

    async def _consumer_loop(
        self,
        consumer: AIOKafkaConsumer,
        handler: Callable,
        consumer_key: str
    ):
        """Process events"""
        async for msg in consumer:
            try:
                event_data = json.loads(msg.value.decode('utf-8'))
                await handler(event_data)

                # Commit offset
                await consumer.commit()

            except Exception as e:
                log.error(f"Handler error: {e}", exc_info=True)
```

### Topic Organization

**Naming Convention**:
- `transport.*` - Domain events (e.g., `transport.order-events`)
- `system.*` - System events (e.g., `system.dlq-events`)
- `saga.*` - Saga coordination (e.g., `saga.order-placement`)
- `alerts.*` - User notifications (e.g., `alerts.user-notifications`)

**Partitioning Strategy**:
```python
# Partition by aggregate ID (ensures ordering per aggregate)
await event_bus.publish(
    channel="order-events",
    event=event,
    partition_key=f"order-{order_id}"  # Same order → same partition
)
```

---

## Exactly-Once Delivery

### 3-Layer Defense Strategy

**Layer 1: Kafka Transactions**
```python
# Transactional consumer loop
async def consumer_loop_transactional(adapter, consumer_key, consumer_info):
    # Create transactional producer
    txn_producer = await adapter._create_transactional_producer(txn_id)

    while running:
        # Fetch messages
        records = await consumer.getmany()

        # Process within transaction
        for msg in records:
            await handler(msg.value)

        # Atomic commit (processing + offsets)
        await txn_producer.send_offsets_to_transaction(offsets, group_id)
        await txn_producer.commit_transaction()
        await txn_producer.begin_transaction()
```

**Layer 2: Broker API Idempotency**
```python
# Use UUIDs as idempotency keys
client_order_id = str(uuid.uuid4())

response = await broker_api.place_order(
    symbol="AAPL",
    quantity=100,
    client_order_id=client_order_id  # Deduplication key
)

# Duplicate request → broker returns existing order
```

**Layer 3: Idempotent Handlers**
```python
@projector(OrderCreatedEvent)
async def project_order_created(event, pg_client):
    # UPSERT pattern
    await pg_client.execute(
        """
        INSERT INTO orders (order_id, symbol, quantity, status)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (order_id) DO UPDATE  # Handles duplicates
        SET status = EXCLUDED.status
        """,
        event.order_id, event.symbol, event.quantity, "PENDING"
    )
```

### Transactional Outbox

**PostgreSQL Trigger**:
```sql
CREATE FUNCTION notify_outbox_event()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('outbox_events', NEW.event_id::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER outbox_insert_notify
    AFTER INSERT ON event_outbox
    FOR EACH ROW
    EXECUTE FUNCTION notify_outbox_event();
```

**Outbox Publisher with LISTEN/NOTIFY**:
```python
# Dedicated connection for LISTEN
notify_conn = await asyncpg.connect(dsn)
await notify_conn.add_listener('outbox_events', callback)

# Instant processing (<5ms latency)
def callback(connection, pid, channel, payload):
    notification_queue.put_nowait(payload)

# Main loop
while running:
    payload = await notification_queue.get()
    # Process event immediately
    await publish_to_kafka(payload)
```

---

## Technology Stack

### Required Components

| Component | Technology | Version | Purpose |
|---|---|---|---|
| **API Framework** | FastAPI | 0.115+ | REST/WebSocket endpoints |
| **ASGI Server** | Granian | 1.6+ | High-performance server |
| **Message Broker** | Redpanda | Latest | Kafka-compatible event bus |
| **Database** | PostgreSQL | 15+ | Event store + read models |
| **Cache** | Redis | 7.0+ | Distributed caching |
| **Kafka Client** | aiokafka | 0.12+ | Async Kafka operations |
| **DB Client** | asyncpg | 0.30+ | Async PostgreSQL |
| **Validation** | Pydantic | 2.5+ | Data validation |

### Optional Components

| Component | Technology | Purpose |
|---|---|---|---|
| **Metrics** | Prometheus | Monitoring |
| **Tracing** | OpenTelemetry | Distributed tracing |
| **Logging** | Structured logging | JSON logs |
| **Admin UI** | Redpanda Console | Kafka management |

---

## Design Decisions

### 1. Why Event Sourcing?

**Pros**:
- Complete audit trail (regulatory compliance)
- Event replay capability (rebuild projections)
- Temporal queries (state at any point in time)
- Natural fit for event-driven systems

**Cons**:
- Higher complexity than CRUD
- Storage overhead (all events kept)
- Eventual consistency (read lag)

**When to Use**:
- Financial systems (audit requirements)
- Complex domains (many state transitions)
- Need for historical analysis
- Event-driven architecture

**When NOT to Use**:
- Simple CRUD applications
- Real-time requirements (<10ms lag)
- Limited storage budget

### 2. Why Redpanda over Kafka?

**Pros**:
- Faster performance (C++ vs JVM)
- Lower resource usage (no Zookeeper)
- Kafka-compatible API
- Better for development (single binary)

**Cons**:
- Less mature ecosystem
- Fewer integrations

**Decision**: Use Redpanda for development, can switch to Kafka for production if needed (API compatible).

### 3. Why PostgreSQL for Event Store?

**Pros**:
- ACID transactions
- Strong consistency
- Powerful querying (Window Functions)
- LISTEN/NOTIFY for instant pub/sub

**Cons**:
- Not specialized for event sourcing
- Slower than purpose-built event stores

**Decision**: PostgreSQL provides best balance of features, reliability, and operational simplicity.

### 4. Why Transactional Outbox?

**Pros**:
- Atomic database + event bus operations
- Exactly-once delivery guarantee
- No distributed transactions needed

**Cons**:
- Eventual consistency (events publish async)
- Additional complexity (outbox table, publisher)

**Decision**: Transactional outbox is industry best practice for event-driven systems (microservices.io pattern).

---

## Implementation Checklist

### Phase 1: Infrastructure Setup

- [ ] Deploy Redpanda/Kafka cluster
- [ ] Deploy PostgreSQL database
- [ ] Deploy Redis cache
- [ ] Setup Prometheus metrics
- [ ] Setup Redpanda Console (admin UI)

### Phase 2: Event Store

- [ ] Create `event_store` table with indexes
- [ ] Create `event_outbox` table
- [ ] Implement `BaseAggregate` class
- [ ] Implement `EventStore` service
- [ ] Add concurrency control (optimistic locking)
- [ ] Create PostgreSQL trigger for LISTEN/NOTIFY

### Phase 3: Event Bus

- [ ] Implement `EventBus` service with aiokafka
- [ ] Configure producer (compression, batching, acks)
- [ ] Configure consumers (consumer groups, offsets)
- [ ] Implement topic auto-creation
- [ ] Add metrics (Prometheus)

### Phase 4: Exactly-Once Delivery

- [ ] Enable Kafka transactions (`enable_transactions=true`)
- [ ] Implement transactional consumer loop
- [ ] Configure `isolation_level=read_committed`
- [ ] Implement transactional outbox publisher
- [ ] Add reconciliation service (detect orphans)
- [ ] Implement idempotent projectors (UPSERT pattern)

### Phase 5: Domain Implementation

- [ ] Define domain events (Pydantic models)
- [ ] Implement aggregates with event handlers
- [ ] Create command handlers
- [ ] Create projectors for read models
- [ ] Add query endpoints
- [ ] Write tests (unit + integration)

### Phase 6: Monitoring & Operations

- [ ] Setup Prometheus alerts (lag, errors, duplicates)
- [ ] Create health check endpoints
- [ ] Add structured logging
- [ ] Document runbooks
- [ ] Setup backup/restore procedures

---

## See Also

- [Event Store Manual](../mvp/EVENT_STORE_MANUAL.md) - Usage guide
- [Event Bus Manual](../mvp/EVENT_BUS_MANUAL.md) - Configuration
- [Exactly-Once Manual](../mvp/EXACTLY_ONCE_MANUAL.md) - Delivery guarantees
- [Compliance Report](../../EXACTLY_ONCE_2025_COMPLIANCE_REPORT.md) - Audit results

---

**Last Updated**: November 2025
**Template Version**: 1.0 (TradeCore v0.5)
