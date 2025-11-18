# TradeCore Architecture Overview

**Version**: 0.5.1
**Document Status**: Comprehensive Reference Guide
**Last Updated**: 2025-01-10

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Infrastructure Overview](#infrastructure-overview)
3. [Architecture Layers](#architecture-layers)
4. [Data Flow Diagrams](#data-flow-diagrams)
5. [Technology Stack](#technology-stack)
6. [Design Patterns](#design-patterns)
7. [Key Concepts](#key-concepts)
8. [Reusability for Non-Trading Applications](#reusability-for-non-trading-applications)
9. [Performance Optimization](#performance-optimization)
10. [Reliability & Fault Tolerance](#reliability--fault-tolerance)

---

## Executive Summary

TradeCore is an **enterprise-grade, event-driven trading platform** built with **Python, FastAPI, and Granian**. It implements **CQRS (Command Query Responsibility Segregation)**, **Event Sourcing**, **Domain-Driven Design (DDD)**, and the **True Saga Pattern** for distributed transaction orchestration.

### What Makes TradeCore Unique?

1. **True CQRS + Event Sourcing**: 10-year event retention, complete audit trails, optimistic locking
2. **True Saga Pattern**: Distributed transaction orchestration with automatic compensation
3. **Multi-Broker Support**: Alpaca, TradeStation, Virtual/Paper Trading with unified adapter pattern
4. **Real-Time Streaming**: WebSocket/HTTP Chunked streaming with market data + trading data handlers
5. **Production-Ready Reliability**: Circuit breakers, retry with backoff, distributed locking, exactly-once delivery
6. **High Performance**: Granian ASGI server (3x faster than Uvicorn), StickyPartitionAssignor for Kafka

### Core Statistics

- **3 Broker Adapters**: Alpaca (WebSocket), TradeStation (HTTP Chunked), Virtual (Event-Driven)
- **4 Primary Domains**: User Account, Broker Connection, Broker Account, Virtual Broker
- **13 REST API Routers**: Full CRUD + WebSocket engine
- **10-Year Event Retention**: Complete audit trail for compliance
- **Sub-10ms Command Processing**: Optimized CQRS with fast-track sagas

---

## Infrastructure Overview

### 1. CQRS Pattern (Command Query Responsibility Segregation)

```
┌─────────────────────────────────────────────────────────────────┐
│                    WRITE SIDE (Server Context)                   │
├─────────────────────────────────────────────────────────────────┤
│  API Request → CommandBus → Handler → Aggregate → Event         │
│                                                     ↓            │
│                                            EventBus (Redpanda)   │
│                                                     ↓            │
│  Event → Saga Trigger → SagaManager → CommandBus → More Logic   │
└─────────────────────────────────────────────────────────────────┘
                                ↓ (Domain Events)
┌─────────────────────────────────────────────────────────────────┐
│                    READ SIDE (Worker Context)                    │
├─────────────────────────────────────────────────────────────────┤
│              Event → Projector → Read Model (PostgreSQL)         │
│              ↓                                                   │
│  API Query → QueryBus → QueryHandler → Read Model → Response    │
└─────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- **Write Side**: Commands modify state via Aggregates, emit Events
- **Read Side**: Events update Read Models, Queries fetch denormalized data
- **Separation**: Write optimized for consistency, Read optimized for performance
- **Benefits**: Independent scaling, eventual consistency, audit trails

### 2. Event Sourcing (10-Year Retention)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Event Store                               │
│                    (Redpanda Topics)                             │
├─────────────────────────────────────────────────────────────────┤
│  eventstore.user-account-events       (10-year retention)       │
│  eventstore.broker-connection-events  (10-year retention)       │
│  eventstore.broker-account-events     (10-year retention)       │
│  eventstore.virtual-broker-events     (10-year retention)       │
│  eventstore.order-events              (10-year retention)       │
│  eventstore.position-events           (10-year retention)       │
└─────────────────────────────────────────────────────────────────┘
                    ↓ (Stream to Workers)
┌─────────────────────────────────────────────────────────────────┐
│                    Transport Topics                              │
│                    (Redpanda Topics)                             │
├─────────────────────────────────────────────────────────────────┤
│  transport.user-account-events       (7-day retention)          │
│  transport.broker-connection-events  (7-day retention)          │
│  transport.order-events              (7-day retention)          │
│  saga.events                         (7-day retention)          │
└─────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- **Immutable Event Log**: All state changes recorded as events
- **Dual Retention**: 10-year event store (compliance), 7-day transport (cost optimization)
- **Snapshots**: Fast aggregate rebuilding from latest snapshot + events
- **Replay**: Rebuild read models from event history
- **Audit Trail**: Complete history of all system changes

### 3. Domain-Driven Design (DDD)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Domain Layer                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Aggregate Root (BrokerConnectionAggregate)              │   │
│  │  ├─ State (BrokerConnectionAggregateState)               │   │
│  │  ├─ Commands (connect, disconnect, store_credentials)    │   │
│  │  ├─ Events (BrokerConnectionEstablished, etc.)           │   │
│  │  ├─ Business Rules (can_perform_operation, etc.)         │   │
│  │  └─ Version (Optimistic Locking)                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Command Handlers (handle commands → aggregate methods)  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Projectors (apply events → read models)                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Query Handlers (fetch read models)                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- **Aggregates**: Encapsulate business logic, ensure consistency boundaries
- **Value Objects**: Immutable types (`@dataclass(frozen=True)`)
- **Domain Events**: Pydantic BaseEvent with `event_type: Literal["EventName"]`
- **Bounded Contexts**: 4 primary domains with clear boundaries

### 4. True Saga Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                    Saga Orchestration                            │
│                   (Server Context Only)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Domain Event → Saga Trigger                                    │
│       ↓                                                          │
│  SagaManager.start_saga(saga, context)                          │
│       ↓                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Saga Steps (Orchestrated Transaction)                   │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │ Step 1: Disconnect Broker                          │  │   │
│  │  │   Execute: disconnect_broker_connection()          │  │   │
│  │  │   Compensate: restore_broker_connection()          │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │ Step 2: Delete Accounts                            │  │   │
│  │  │   Execute: delete_broker_accounts()                │  │   │
│  │  │   Compensate: restore_broker_accounts()            │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │ Step 3: Purge Virtual Accounts                     │  │   │
│  │  │   Execute: purge_virtual_accounts()                │  │   │
│  │  │   Compensate: restore_virtual_accounts()           │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│       ↓ (All steps succeed)                                     │
│  SagaCompleted Event                                            │
│                                                                  │
│       ↓ (Any step fails)                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Compensation (Reverse Order)                            │   │
│  │  Step 3 Compensate → Step 2 Compensate → Step 1 Compensate │
│  └──────────────────────────────────────────────────────────┘   │
│       ↓                                                          │
│  SagaCompensated Event                                          │
└─────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- **Orchestration**: SagaManager coordinates distributed transactions
- **Compensation**: Automatic rollback on failure (reverse order)
- **Timeout Handling**: 30-60s timeout with monitoring
- **Redis State**: Saga state persisted for recovery
- **Context Injection**: CommandBus, QueryBus, EventBus, EventStore injected

### 5. Event Bus (Redpanda/Kafka)

```
┌─────────────────────────────────────────────────────────────────┐
│                        EventBus                                  │
│                  (Universal Async Pub/Sub)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Publisher → EventBus.publish_stream(topic, event)               │
│       ↓                                                          │
│  [Middleware Pipeline]                                           │
│  ├─ Validation (Pydantic schema)                                │
│  ├─ Enrichment (event_id, timestamp, correlation_id)            │
│  ├─ Circuit Breaker (prevent cascading failures)                │
│  └─ Retry (exponential backoff)                                 │
│       ↓                                                          │
│  RedpandaAdapter.publish_stream(topic, event)                   │
│       ↓                                                          │
│  AIOKafkaProducer.send(topic, event_bytes)                      │
│       ↓                                                          │
│  Redpanda Broker (Kafka-compatible)                             │
│       ↓                                                          │
│  AIOKafkaConsumer.getmany(topic)                                │
│       ↓                                                          │
│  RedpandaAdapter → EventBus → Handler                           │
└─────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- **Transport Abstraction**: EventBus abstracts Redpanda/Kafka
- **Reliability**: Circuit breaker, retry, DLQ (dead letter queue)
- **Exactly-Once Delivery**: Transactional outbox pattern
- **Sticky Assignor**: Minimizes partition movement during rebalancing
- **Compression**: LZ4 compression for large messages

---

## Architecture Layers

### Layer 1: API Layer (FastAPI)

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI API Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  app/api/routers/                                                │
│  ├─ user_account_router.py          (User management)           │
│  ├─ broker_connection_router.py     (Connection lifecycle)      │
│  ├─ broker_account_router.py        (Account discovery)         │
│  ├─ oauth_router.py                 (OAuth2 flows)              │
│  ├─ adapter_pool_router.py          (Connection pooling)        │
│  ├─ projection_rebuilder_router.py  (Projection sync)           │
│  ├─ data_integrity_router.py        (Data validation)           │
│  ├─ streaming_router.py             (Real-time streaming)       │
│  ├─ wse_router.py                   (WebSocket engine)          │
│  ├─ strategy_router.py              (Trading strategies)        │
│  ├─ webhook_router.py               (Webhook integrations)      │
│  ├─ admin_router.py                 (Admin operations)          │
│  └─ system_router.py                (Health checks, metrics)    │
└─────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- **13 REST API Routers**: Full CRUD for all domains
- **OpenAPI Documentation**: Auto-generated Swagger UI at `/docs`
- **Middleware**: CORS, authentication, request/response logging
- **Validation**: Pydantic models for request/response schemas

### Layer 2: Application Layer (Services)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Application Services                          │
├─────────────────────────────────────────────────────────────────┤
│  app/services/                                                   │
│  ├─ broker_auth_service.py         (OAuth2, credentials)        │
│  ├─ broker_operation_service.py    (Order execution)            │
│  ├─ broker_streaming/              (Real-time streaming)        │
│  │  ├─ streaming_service.py        (Facade coordinator)         │
│  │  ├─ lifecycle_manager.py        (Connection lifecycle)       │
│  │  ├─ market_data_handler.py      (Market data streaming)      │
│  │  └─ trading_data_handler.py     (Trading data streaming)     │
│  ├─ adapter_monitoring/            (Adapter health)             │
│  ├─ data_integrity_monitor.py      (Consistency checks)         │
│  ├─ projection_rebuilder_service.py (Gap detection/rebuild)     │
│  ├─ saga_service.py                (Saga lifecycle)             │
│  └─ connection_recovery/           (Connection monitoring)      │
└─────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- **Orchestration Layer**: Services coordinate between domains
- **No Business Logic**: Business logic in aggregates, not services
- **CQRS Compliance**: Services use CommandBus/QueryBus
- **Facade Pattern**: StreamingService unifies streaming operations

### Layer 3: Domain Layer (Aggregates, Events, Commands)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Domain Layer                              │
├─────────────────────────────────────────────────────────────────┤
│  app/{domain}/                                                   │
│  ├─ aggregate.py             (Aggregate root + state)           │
│  ├─ commands.py              (Command definitions)              │
│  ├─ events.py                (Domain events, Pydantic)          │
│  ├─ value_objects.py         (Immutable VOs)                    │
│  ├─ enums.py                 (Domain enumerations)              │
│  ├─ exceptions.py            (Domain exceptions)                │
│  ├─ projectors.py            (Event projectors)                 │
│  ├─ read_models.py           (Read model schemas)               │
│  ├─ queries.py               (Query definitions)                │
│  ├─ sync_events.py           (SYNC event configuration)         │
│  └─ command_handlers/        (Modular handlers)                 │
│     ├─ lifecycle_handlers.py                                    │
│     └─ [other]_handlers.py                                      │
└─────────────────────────────────────────────────────────────────┘
```

**Domain Examples:**
- **User Account Domain**: Registration, authentication, preferences
- **Broker Connection Domain**: Connection lifecycle, credentials, health
- **Broker Account Domain**: Account discovery, balance, equity tracking
- **Virtual Broker Domain**: Paper trading, order simulation, P&L

**Key Points:**
- **Aggregates**: Business logic encapsulated, optimistic locking (version)
- **Events**: Pydantic BaseEvent, `event_type: Literal["EventName"]`
- **Commands**: `@dataclass` with validation
- **Projectors**: `@projector(EventType)` decorator, async functions

### Layer 4: Infrastructure Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                          │
├─────────────────────────────────────────────────────────────────┤
│  app/infra/                                                      │
│  ├─ cqrs/                   (Command/Query buses)               │
│  │  ├─ command_bus.py       (CommandBus with middleware)        │
│  │  └─ query_bus.py         (QueryBus with caching)             │
│  │                                                               │
│  ├─ event_bus/              (Event Bus)                         │
│  │  ├─ event_bus.py         (Universal async pub/sub)           │
│  │  └─ redpanda_adapter.py  (Kafka transport)                   │
│  │                                                               │
│  ├─ event_store/            (Event Sourcing)                    │
│  │  ├─ redpanda_event_store.py (Event persistence)              │
│  │  ├─ outbox_service.py        (Exactly-once delivery)         │
│  │  └─ projection_rebuilder.py  (Gap healing)                   │
│  │                                                               │
│  ├─ saga/                   (Saga Orchestration)                │
│  │  ├─ saga_manager.py      (Saga lifecycle)                    │
│  │  └─ [saga implementations]                                   │
│  │                                                               │
│  ├─ broker_adapters/        (Broker Integrations)               │
│  │  ├─ adapter_factory.py   (Factory pattern)                   │
│  │  ├─ adapter_manager.py   (Unified interface)                 │
│  │  ├─ adapter_pool/        (Connection pooling)                │
│  │  ├─ alpaca/              (Alpaca broker)                     │
│  │  ├─ tradestation/        (TradeStation broker)               │
│  │  └─ virtual/             (Virtual/paper trading)             │
│  │                                                               │
│  ├─ consumers/              (Event Processing Workers)          │
│  │  ├─ consumer_manager.py  (Worker lifecycle)                  │
│  │  └─ event_processor.py   (Event routing)                     │
│  │                                                               │
│  ├─ persistence/            (Database Access)                   │
│  │  ├─ pg_client.py         (PostgreSQL async client)           │
│  │  ├─ redis_client.py      (Redis async client)                │
│  │  └─ cache_manager.py     (Multi-level caching)               │
│  │                                                               │
│  ├─ reliability/            (Circuit breaker, retry, etc.)      │
│  ├─ metrics/                (Prometheus metrics)                │
│  └─ market_data/            (Market data providers)             │
└─────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- **CQRS Buses**: Middleware pipeline (logging, validation, metrics)
- **Event Store**: Dual retention (10-year + 7-day), snapshots
- **Saga Manager**: Redis state, timeout monitoring, compensation
- **Broker Adapters**: Factory pattern, adapter pool (max 1000)
- **Reliability**: Circuit breaker, retry with backoff, distributed locking

---

## Data Flow Diagrams

### Command Flow (Write Side)

```
┌─────────────────────────────────────────────────────────────────┐
│  1. API Request                                                  │
│     POST /api/broker-connection/connect                          │
│     {user_id, broker_id, credentials}                            │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  2. Router → Command                                             │
│     ConnectBrokerCommand(user_id, broker_id, credentials)       │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  3. CommandBus Middleware Pipeline                               │
│     ├─ LoggingMiddleware (log command)                          │
│     ├─ ValidationMiddleware (validate Pydantic)                 │
│     ├─ SagaContextMiddleware (inject saga_id)                   │
│     └─ MetricsMiddleware (track execution time)                 │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  4. Command Handler                                              │
│     @command_handler(ConnectBrokerCommand)                       │
│     async def handle_connect_broker(cmd, deps):                  │
│         aggregate = await deps.aggregate_repo.load(cmd.id)      │
│         aggregate.connect(cmd.credentials)                       │
│         await deps.aggregate_repo.save(aggregate)                │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  5. Aggregate Business Logic                                     │
│     def connect(self, credentials):                              │
│         # Business rules validation                              │
│         if not self.can_perform_operation('connect'):            │
│             raise DomainException("Cannot connect")              │
│         # Emit event                                             │
│         event = BrokerConnectionEstablished(...)                 │
│         self.apply(event)  # Update state                        │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  6. Event Persistence                                            │
│     EventStore.append(aggregate_id, events, version)             │
│     ├─ Optimistic locking (version check)                       │
│     ├─ Append to eventstore.broker-connection-events            │
│     └─ Publish to transport.broker-connection-events            │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  7. Event Bus → Redpanda                                         │
│     EventBus.publish_stream(topic, event)                        │
│     ├─ Circuit breaker check                                    │
│     ├─ Retry with exponential backoff                           │
│     └─ DLQ (dead letter queue) on failure                       │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  8. Response                                                     │
│     200 OK {connection_id, status: "CONNECTED"}                  │
└─────────────────────────────────────────────────────────────────┘
```

### Query Flow (Read Side)

```
┌─────────────────────────────────────────────────────────────────┐
│  1. API Request                                                  │
│     GET /api/broker-connection/{connection_id}                   │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  2. Router → Query                                               │
│     GetBrokerConnectionQuery(connection_id)                      │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  3. QueryBus Middleware Pipeline                                 │
│     ├─ LoggingMiddleware (log query)                            │
│     ├─ CachingMiddleware (check cache, TTL 60s)                 │
│     └─ MetricsMiddleware (track execution time)                 │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  4. Query Handler                                                │
│     @query_handler(GetBrokerConnectionQuery)                     │
│     async def handle_get_broker_connection(query, pg_client):    │
│         result = await pg_client.fetch_one(                      │
│             "SELECT * FROM broker_connections WHERE id = $1",    │
│             query.connection_id                                  │
│         )                                                        │
│         return BrokerConnectionReadModel(**result)               │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  5. PostgreSQL Read Model                                        │
│     Table: broker_connections (denormalized)                     │
│     ├─ id, user_id, broker_id, status                           │
│     ├─ encrypted_credentials, api_endpoint                      │
│     └─ last_successful_connection_at, created_at                │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  6. Response (with caching)                                      │
│     200 OK {connection_id, status: "CONNECTED", ...}             │
│     Cache-Control: max-age=60                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Event Flow (Projection Update)

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Event Published to Redpanda                                  │
│     Topic: transport.broker-connection-events                    │
│     Event: BrokerConnectionEstablished                           │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  2. Worker Consumer (Event Processor)                            │
│     AIOKafkaConsumer.getmany(batch_size=500)                     │
│     ├─ Consumer Group: worker-event-processor                   │
│     ├─ StickyPartitionAssignor (minimize rebalance)             │
│     └─ Manual commit (batch_size=100 or 5s interval)            │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  3. Event Router                                                 │
│     EventProcessor.route_event(event)                            │
│     ├─ Lookup projector by event_type                           │
│     └─ Lookup saga trigger by event_type                        │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  4. Projector (Update Read Model)                                │
│     @projector(BrokerConnectionEstablished)                      │
│     async def project_connection_established(event, pg_client):  │
│         await pg_client.execute(                                 │
│             "UPDATE broker_connections SET status = $1 ...",     │
│             "CONNECTED", event.connection_id                     │
│         )                                                        │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  5. PostgreSQL Write (Projection)                                │
│     Table: broker_connections (updated)                          │
│     ├─ status = "CONNECTED"                                     │
│     ├─ last_successful_connection_at = now()                    │
│     └─ updated_at = now()                                       │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  6. Commit Offset                                                │
│     consumer.commit() after batch processed                      │
└─────────────────────────────────────────────────────────────────┘
```

### Saga Flow (Distributed Transaction)

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Trigger Event                                                │
│     Event: UserDeletionRequested                                 │
│     Published to: saga.events                                    │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  2. Saga Service (Event Handler)                                 │
│     @saga_trigger(UserDeletionRequested)                         │
│     async def trigger_user_deletion_saga(event, saga_service):   │
│         saga = UserDeletionSaga(user_id=event.user_id)           │
│         await saga_service.start_saga(saga, context={...})       │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  3. SagaManager.start_saga()                                     │
│     ├─ Create SagaState (status=STARTED)                        │
│     ├─ Inject context (CommandBus, QueryBus, EventStore)        │
│     ├─ Persist state to Redis (TTL = timeout + 1h)              │
│     ├─ Start timeout monitor (background task)                  │
│     └─ Execute steps sequentially                               │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  4. Execute Step 1: Disconnect Broker                            │
│     ├─ step.execute(context)                                    │
│     │  ├─ DisconnectBrokerCommand → CommandBus                  │
│     │  └─ Wait for result                                       │
│     ├─ Record compensation: step.compensate                     │
│     └─ Store result in saga context                             │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  5. Execute Step 2: Delete Accounts                              │
│     ├─ step.execute(context)                                    │
│     │  ├─ BatchDeleteAccountsCommand → CommandBus              │
│     │  └─ Wait for result                                       │
│     ├─ Record compensation: step.compensate                     │
│     └─ Store result in saga context                             │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  6. Execute Step 3: Purge Virtual Accounts                       │
│     ├─ step.execute(context)                                    │
│     │  ├─ PurgeVirtualAccountsCommand → CommandBus             │
│     │  └─ Wait for result                                       │
│     ├─ Record compensation: step.compensate                     │
│     └─ Store result in saga context                             │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  7. Saga Completed                                               │
│     ├─ Update status: COMPLETED                                 │
│     ├─ Publish SagaCompletedEvent                               │
│     ├─ Cleanup Redis state                                      │
│     └─ Cancel timeout monitor                                   │
└─────────────────────────────────────────────────────────────────┘

                        (If any step fails)
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  Compensation Flow (Reverse Order)                               │
│  ├─ Step 3 Compensate: restore_virtual_accounts()               │
│  ├─ Step 2 Compensate: restore_broker_accounts()                │
│  ├─ Step 1 Compensate: restore_broker_connection()              │
│  ├─ Update status: COMPENSATED                                  │
│  └─ Publish SagaCompensatedEvent                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Core Framework

| Component | Version | Purpose |
|-----------|---------|---------|
| **Python** | 3.x | Programming language |
| **FastAPI** | 0.115+ | Modern async web framework |
| **Granian** | 1.6+ | High-performance Rust-based ASGI server (3x faster than Uvicorn) |
| **Pydantic** | 2.5+ | Data validation using type hints |

### Message Queue & Event Streaming

| Component | Version | Purpose |
|-----------|---------|---------|
| **Redpanda** | Latest | Kafka-compatible event streaming broker (primary transport) |
| **AIoKafka** | 0.12+ | Async Kafka/Redpanda Python client |
| **StickyPartitionAssignor** | Built-in | Minimize partition movement during rebalancing |

### Database & Persistence

| Component | Version | Purpose |
|-----------|---------|---------|
| **PostgreSQL** | 15+ | Main data store with async driver |
| **AsyncPG** | 0.30+ | Async PostgreSQL driver |
| **Redis** | 7.0+ | Caching, session management, distributed coordination |

### Data & Finance

| Component | Version | Purpose |
|-----------|---------|---------|
| **Pandas** | 2.2+ | Data analysis |
| **NumPy** | 2.2+ | Numerical computing |
| **yfinance** | 0.2+ | Market data provider |
| **Decimal** | Built-in | Precise financial calculations |

### Security

| Component | Version | Purpose |
|-----------|---------|---------|
| **python-jose** | 3.4+ | JWT token handling |
| **PyJWT** | 2.10+ | JWT encoding/decoding |
| **bcrypt** | 4.3+ | Password hashing |
| **cryptography** | 44.0+ | Encryption (Fernet for credentials) |

### Data Validation & Serialization

| Component | Version | Purpose |
|-----------|---------|---------|
| **Pydantic** | 2.5+ | Data validation using Python type hints |
| **msgpack** | 1.0+ | Binary serialization |
| **JSON** | Built-in | Event serialization (with custom encoder) |

---

## Design Patterns

### 1. Aggregate Pattern (DDD)

**Purpose**: Encapsulate business logic and ensure consistency boundaries

**Implementation**:
```python
class BrokerConnectionAggregate:
    def __init__(self, aggregate_id: uuid.UUID):
        self.id = aggregate_id
        self.version = 0  # Optimistic locking
        self.state = BrokerConnectionAggregateState()
        self._uncommitted_events = []

    def connect(self, credentials):
        # Business rules validation
        if not self.can_perform_operation('connect'):
            raise DomainException("Cannot connect in current state")

        # Emit event
        event = BrokerConnectionEstablished(...)
        self._apply_and_record(event)

    def _apply_and_record(self, event):
        self._apply(event)  # Update state
        self._uncommitted_events.append(event)
        self.version += 1
```

**Benefits**:
- Business logic isolated in aggregates
- Optimistic locking prevents concurrent modification conflicts
- Events provide audit trail

### 2. Repository Pattern

**Purpose**: Abstract persistence layer

**Implementation**:
```python
class AggregateRepository:
    async def load(self, aggregate_id: uuid.UUID) -> BrokerConnectionAggregate:
        # Load events from event store
        events = await self.event_store.get_events(aggregate_id)

        # Rebuild aggregate from events
        aggregate = BrokerConnectionAggregate(aggregate_id)
        for event in events:
            aggregate._apply(event)

        return aggregate

    async def save(self, aggregate: BrokerConnectionAggregate):
        # Get uncommitted events
        events = aggregate.get_uncommitted_events()

        # Persist with optimistic locking
        await self.event_store.append(
            aggregate.id,
            events,
            expected_version=aggregate.version - len(events)
        )

        # Mark events as committed
        aggregate.mark_events_committed()
```

### 3. Saga Pattern (Orchestration)

**Purpose**: Distributed transaction coordination with automatic compensation

**Implementation**:
```python
class UserDeletionSaga(BaseSaga):
    def define_steps(self) -> List[SagaStep]:
        return [
            SagaStep(
                name="disconnect_broker",
                execute=disconnect_broker_connection,
                compensate=restore_broker_connection,
                timeout_seconds=30,
                retry_count=3
            ),
            SagaStep(
                name="delete_accounts",
                execute=delete_broker_accounts,
                compensate=restore_broker_accounts,
                timeout_seconds=60,
                retry_count=3
            ),
        ]

    def get_timeout(self) -> timedelta:
        return timedelta(minutes=10)
```

**Benefits**:
- Automatic compensation on failure
- Timeout handling
- Redis state persistence for recovery

### 4. Circuit Breaker Pattern

**Purpose**: Prevent cascading failures

**Implementation**:
```python
circuit_breaker = get_circuit_breaker(
    "redpanda_transport",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=3,
        reset_timeout_seconds=30
    )
)

async def publish_event(topic, event):
    if not circuit_breaker.can_execute():
        raise ConnectionError("Circuit breaker is open")

    return await circuit_breaker.execute_async(
        lambda: producer.send(topic, event)
    )
```

**States**:
- **CLOSED**: Normal operation
- **OPEN**: Too many failures, reject all requests
- **HALF_OPEN**: Test if service recovered

### 5. Adapter Pattern (Broker Integration)

**Purpose**: Unified interface for multiple brokers

**Implementation**:
```python
class BrokerAdapter(ABC):
    @abstractmethod
    async def connect(self, credentials):
        pass

    @abstractmethod
    async def get_accounts(self):
        pass

    @abstractmethod
    async def place_order(self, order):
        pass

class AlpacaAdapter(BrokerAdapter):
    # Alpaca-specific implementation
    pass

class TradeStationAdapter(BrokerAdapter):
    # TradeStation-specific implementation
    pass
```

**Benefits**:
- Swap brokers without changing application code
- Consistent error handling
- Adapter-specific optimizations

### 6. Facade Pattern (Streaming Service)

**Purpose**: Unified entry point for complex streaming subsystem

**Implementation**:
```python
class StreamingService:
    def __init__(
        self,
        lifecycle_manager: StreamingLifecycleManager,
        market_data_handler: MarketDataHandler,
        trading_data_handler: TradingDataHandler
    ):
        self.lifecycle_manager = lifecycle_manager
        self.market_data_handler = market_data_handler
        self.trading_data_handler = trading_data_handler

    async def start_streaming(self, broker_name, symbols, user_id):
        # Coordinate all components
        await self.lifecycle_manager.ensure_streaming_for_broker(broker_name)
        await self.market_data_handler.subscribe_to_broker(broker_name, symbols)
        await self.trading_data_handler.setup_for_broker(broker_name)
```

**Benefits**:
- Simplified API for complex subsystem
- Centralized coordination
- Hide implementation details

### 7. Handler Pattern (Market Data)

**Purpose**: Process real-time streams

**Implementation**:
```python
class MarketDataHandler:
    async def on_quote(self, quote_data):
        # Normalize broker-specific data
        quote = self._normalize_quote(quote_data)

        # Distribute to multiple channels
        await self.wse_publisher.publish_quote(quote)
        await self.command_bus.dispatch(UpdatePositionValueCommand(quote))
        await self.cache_manager.set(f"quote:{quote.symbol}", quote)
```

**Benefits**:
- Broker-agnostic data processing
- Multiple distribution channels
- Real-time data normalization

---

## Key Concepts

### 1. SYNC vs ASYNC Events

**SYNC Events** (Immediate Projection Update):
- Projector runs synchronously in server context
- Read model updated before command returns
- Strong consistency for critical operations
- Example: `BrokerConnectionEstablished` (connection status)

**Configuration**:
```python
# app/broker_connection/sync_events.py
SYNC_EVENT_TYPES = {
    "BrokerConnectionEstablished",
    "BrokerConnectionFailed",
    "BrokerDisconnected",
}
```

**ASYNC Events** (Eventual Consistency):
- Projector runs in worker context
- Read model updated eventually (sub-second latency)
- Normal for non-critical operations
- Example: `BrokerHealthUpdated` (periodic health check)

### 2. Event Enrichment for Sagas

**Purpose**: Sagas need related entity IDs for cleanup operations

**Implementation**:
```python
class BrokerConnectionAggregateState:
    # Track related entities for event enrichment
    linked_account_ids: List[uuid.UUID] = []
    virtual_account_ids: List[uuid.UUID] = []
    active_automation_ids: List[uuid.UUID] = []

# When emitting disconnection event
event = BrokerDisconnected(
    connection_id=self.id,
    linked_account_ids=self.state.linked_account_ids,
    virtual_account_ids=self.state.virtual_account_ids,
    active_automation_ids=self.state.active_automation_ids
)
```

**Benefits**:
- Saga gets all context in trigger event
- No additional queries needed
- Faster saga execution

### 3. Projection Rebuilding

**Purpose**: Recover from read model corruption or add new projections

**Process**:
1. **Gap Detection**: Monitor event sequence numbers
2. **Rebuild Request**: API endpoint or automatic trigger
3. **Replay Events**: Fetch events from event store
4. **Apply Projections**: Rebuild read model from events
5. **Verification**: Validate read model consistency

**Usage**:
```bash
POST /api/projection-rebuilder/rebuild
{
  "domain": "broker_account",
  "start_time": "2025-01-01T00:00:00Z"
}
```

### 4. Exactly-Once Delivery (Outbox Pattern)

**Problem**: Events published to Redpanda might be lost if EventStore write succeeds but publish fails

**Solution**: Transactional Outbox Pattern

**Implementation**:
```python
async def save_events(aggregate_id, events, version):
    async with transaction:
        # 1. Write events to event store
        await event_store.append(aggregate_id, events, version)

        # 2. Write to outbox table
        for event in events:
            await pg_client.execute(
                "INSERT INTO outbox (event_id, event_data) VALUES ($1, $2)",
                event.event_id, event.to_json()
            )

    # 3. Outbox worker publishes to Redpanda
    outbox_worker.process()
```

**Benefits**:
- Guaranteed delivery
- No event loss
- Exactly-once semantics

### 5. Distributed Locking

**Purpose**: Prevent concurrent saga execution on same aggregate

**Implementation**:
```python
async def acquire_aggregate_lock(conflict_key: str, saga_id: str):
    lock_key = f"saga_aggregate_lock:{conflict_key}"

    # Try to set lock (NX = only if not exists)
    success = await redis.set(
        lock_key,
        json.dumps({"saga_id": saga_id, "acquired_at": now()}),
        nx=True,
        ex=300  # 5 min TTL
    )

    if not success:
        raise ConcurrentSagaException("Another saga is already processing this aggregate")
```

**Benefits**:
- Prevent race conditions
- Saga isolation
- Automatic cleanup (TTL)

### 6. Circuit Breakers

**Purpose**: Prevent cascading failures

**States**:
- **CLOSED**: Normal operation (failures < threshold)
- **OPEN**: Too many failures, reject all requests
- **HALF_OPEN**: Test if service recovered (limited requests)

**Configuration**:
```python
CircuitBreakerConfig(
    failure_threshold=5,      # Open after 5 failures
    success_threshold=3,      # Close after 3 successes in half-open
    reset_timeout_seconds=30  # Try half-open after 30s
)
```

---

## Reusability for Non-Trading Applications

TradeCore's architecture is **domain-agnostic** and can be adapted to any application requiring:

### Core Reusable Components

1. **CQRS Infrastructure** (`app/infra/cqrs/`)
   - CommandBus, QueryBus
   - Middleware pipeline
   - Handler registration
   - **Use Case**: Any app with write/read separation

2. **Event Sourcing** (`app/infra/event_store/`)
   - EventBus, RedpandaAdapter
   - Event Store (dual retention)
   - Projection rebuilding
   - **Use Case**: Audit trails, compliance, time-travel debugging

3. **Saga Pattern** (`app/infra/saga/`)
   - SagaManager
   - Compensation logic
   - Timeout handling
   - **Use Case**: Distributed transactions (e-commerce, booking systems)

4. **Reliability Patterns** (`app/infra/reliability/`)
   - Circuit breaker
   - Retry with backoff
   - Distributed locking
   - **Use Case**: Microservices, external API integration

5. **WebSocket Streaming** (`app/api/wse/`)
   - WebSocket engine
   - Message batching/compression
   - Event sequencing
   - **Use Case**: Real-time notifications, chat, dashboards

### Example: E-Commerce Application

**Domains**:
- Order Domain → `app/order/`
- Inventory Domain → `app/inventory/`
- Payment Domain → `app/payment/`

**Sagas**:
- Order Fulfillment Saga
  - Step 1: Reserve inventory
  - Step 2: Process payment
  - Step 3: Ship order
  - Compensation: Release inventory, refund payment

**Events**:
- `OrderPlaced`, `InventoryReserved`, `PaymentProcessed`, `OrderShipped`

**Read Models**:
- `orders` table (denormalized)
- `inventory_availability` table
- `payment_history` table

### Example: Healthcare Application

**Domains**:
- Patient Domain → `app/patient/`
- Appointment Domain → `app/appointment/`
- Billing Domain → `app/billing/`

**Sagas**:
- Appointment Scheduling Saga
  - Step 1: Check availability
  - Step 2: Reserve slot
  - Step 3: Send notification
  - Compensation: Release slot, cancel notification

**Benefits**:
- **HIPAA Compliance**: 10-year event retention for audit trails
- **Exactly-Once Delivery**: No lost appointments or duplicate billing
- **Saga Pattern**: Distributed transaction coordination

---

## Performance Optimization

### 1. Granian ASGI Server (3x Faster than Uvicorn)

**Benchmark** (1000 req/s):
- **Uvicorn**: ~300 req/s
- **Granian**: ~900 req/s (3x improvement)

**Configuration**:
```bash
granian --interface asgi app.server:app \
    --host 0.0.0.0 \
    --port 5001 \
    --workers 4 \
    --http 2 \
    --websockets
```

### 2. StickyPartitionAssignor (Kafka)

**Problem**: RoundRobinAssignor causes stop-the-world rebalancing (30-60s)

**Solution**: StickyPartitionAssignor minimizes partition movement

**Benefits**:
- Faster rebalancing (3-5s vs 30-60s)
- Zero downtime during rebalancing
- Better for high-throughput systems

**Configuration**:
```python
consumer_config = {
    'partition_assignment_strategy': (StickyPartitionAssignor,),
}
```

### 3. Batch Commit (Kafka)

**Problem**: Committing offset after every message is slow

**Solution**: Batch commit (100 messages or 5s interval)

**Implementation**:
```python
messages_since_last_commit = 0
last_commit_time = time.time()

for message in consumer.getmany():
    process_message(message)
    messages_since_last_commit += 1

    if messages_since_last_commit >= 100 or time.time() - last_commit_time >= 5:
        await consumer.commit()
        messages_since_last_commit = 0
        last_commit_time = time.time()
```

### 4. Query Caching (60s TTL)

**Implementation**:
```python
@query_handler(GetBrokerConnectionQuery)
async def handle_get_broker_connection(query, pg_client):
    # QueryBus middleware checks cache first (TTL 60s)
    result = await pg_client.fetch_one(
        "SELECT * FROM broker_connections WHERE id = $1",
        query.connection_id
    )
    return BrokerConnectionReadModel(**result)
```

**Benefits**:
- Reduce database load
- Sub-10ms query response
- Automatic invalidation (TTL)

### 5. Fast-Track Sagas (Virtual Broker)

**Problem**: Virtual broker sagas don't need external API calls

**Solution**: Fast-track mode with reduced timeouts

**Implementation**:
```python
if saga.is_fast_track():
    timeout_seconds = min(step.timeout_seconds, 10)  # Max 10s
    retry_delay_seconds = min(retry_delay_seconds, 0.5)  # 500ms
```

**Benefits**:
- Sub-second saga execution for virtual brokers
- Reduced Redis I/O
- Faster user deletion

---

## Reliability & Fault Tolerance

### 1. Circuit Breaker (Prevent Cascading Failures)

**States**:
- **CLOSED**: Normal operation (failures < threshold)
- **OPEN**: Too many failures, reject all requests (fail fast)
- **HALF_OPEN**: Test if service recovered

**Example**:
```python
circuit_breaker = get_circuit_breaker("redpanda_transport")

# Check before executing
if not circuit_breaker.can_execute():
    raise ConnectionError("Circuit breaker is open")

# Execute with circuit breaker protection
result = await circuit_breaker.execute_async(
    lambda: producer.send(topic, event)
)
```

**Benefits**:
- Prevent cascading failures
- Automatic recovery testing
- Metrics (failure count, last failure time)

### 2. Retry with Exponential Backoff

**Configuration**:
```python
RetryConfig(
    max_attempts=5,
    initial_delay_ms=200,
    max_delay_ms=5000,
    backoff_factor=2.0  # 200ms → 400ms → 800ms → 1600ms → 3200ms
)
```

**Implementation**:
```python
await retry_async(
    lambda: producer.send(topic, event),
    retry_config=retry_config,
    context="publish_event"
)
```

**Benefits**:
- Transient failure recovery
- Automatic retry
- Configurable backoff

### 3. Dead Letter Queue (DLQ)

**Purpose**: Store failed events for manual intervention

**Implementation**:
```python
async def _send_to_dlq(channel: str, event: Dict[str, Any], error: Exception):
    dlq_topic = f"{channel}.dlq"
    dlq_event = {
        **event,
        "_dlq_metadata": {
            "original_channel": channel,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": event.get("_dlq_metadata", {}).get("retry_count", 0) + 1
        }
    }
    await adapter.publish_stream(dlq_topic, dlq_event)
```

**Benefits**:
- No event loss
- Manual intervention for unrecoverable errors
- Retry count tracking

### 4. Distributed Locking (Redis)

**Purpose**: Prevent concurrent saga execution on same aggregate

**Implementation**:
```python
lock_key = f"saga_aggregate_lock:{conflict_key}"

# Acquire lock with TTL
success = await redis.set(
    lock_key,
    json.dumps({"saga_id": saga_id}),
    nx=True,  # Only set if not exists
    ex=300    # 5 min TTL (automatic cleanup)
)

if not success:
    raise ConcurrentSagaException("Another saga is already processing this aggregate")
```

**Benefits**:
- Saga isolation
- Race condition prevention
- Automatic cleanup (TTL)

### 5. Health Checks

**Endpoints**:
- `/health/server` - Server health (database, Redis, Redpanda)
- `/health/worker` - Worker health (consumer lag, error rate)
- `/health/adapters` - Adapter health (broker connections)

**Example Response**:
```json
{
  "status": "healthy",
  "database": {
    "status": "healthy",
    "connections": 10,
    "max_connections": 100
  },
  "redis": {
    "status": "healthy",
    "ping": "PONG"
  },
  "event_bus": {
    "status": "healthy",
    "circuit_breakers": {
      "transport.broker-connection-events": "CLOSED"
    }
  }
}
```

### 6. Optimistic Locking (Event Store)

**Purpose**: Prevent concurrent modification conflicts

**Implementation**:
```python
async def save_events(aggregate_id, events, expected_version):
    # Check current version
    current_version = await event_store.get_version(aggregate_id)

    if current_version != expected_version:
        raise ConcurrencyException(
            f"Aggregate {aggregate_id} version mismatch: "
            f"expected {expected_version}, got {current_version}"
        )

    # Append events
    await event_store.append(aggregate_id, events, current_version)
```

**Benefits**:
- Prevent lost updates
- Safe concurrent access
- ACID guarantees

---

## Conclusion

TradeCore is a **production-ready, enterprise-grade event-driven architecture** that demonstrates:

1. **True CQRS + Event Sourcing**: Write-side optimized for consistency, read-side optimized for performance
2. **True Saga Pattern**: Distributed transaction orchestration with automatic compensation
3. **Production-Ready Reliability**: Circuit breakers, retry, DLQ, distributed locking
4. **High Performance**: Granian (3x faster), StickyPartitionAssignor, batch commit, query caching
5. **Domain-Driven Design**: Business logic in aggregates, clear bounded contexts
6. **Reusable Infrastructure**: CQRS, Event Sourcing, Sagas can be used for **any application**

### Next Steps

- **Read Detailed Guides**: `/docs/reference/` contains deep-dives on each component
- **Study Domain Examples**: `app/broker_connection/`, `app/user_account/`, `app/virtual_broker/`
- **Run the System**: `granian --interface asgi app.server:app --host 0.0.0.0 --port 5001 --reload`
- **Explore API**: http://localhost:5001/docs (OpenAPI Swagger UI)

---

**Document Version**: 1.0
**TradeCore Version**: 0.5.1
**Last Updated**: 2025-01-10
