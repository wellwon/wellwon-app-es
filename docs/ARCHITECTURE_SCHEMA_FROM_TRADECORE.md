# TradeCore Architecture Schema

**Version:** 0.7
**Date:** 2025-11-18
**Pattern:** CQRS + Event Sourcing + DDD

---

## Overview

TradeCore использует CQRS (разделение команд и запросов), Event Sourcing (хранение событий как источник истины) и Domain-Driven Design (доменная архитектура).

---

## Layers Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API LAYER (FastAPI)                      │
│                     app/api/routers/*.py                        │
└────────────┬──────────────────────────────────┬─────────────────┘
             │                                  │
             ▼ Commands                         ▼ Queries
┌────────────────────────┐           ┌──────────────────────────┐
│   COMMAND BUS (Write)  │           │   QUERY BUS (Read)       │
│  app/infra/cqrs/       │           │   app/infra/cqrs/        │
└────────────┬───────────┘           └───────────┬──────────────┘
             │                                   │
             ▼                                   ▼
┌────────────────────────┐           ┌──────────────────────────┐
│    DOMAIN LAYER        │           │   READ MODELS            │
│  Command Handlers      │           │   Query Handlers         │
│  Aggregates            │           │   Projections            │
│  app/{domain}/         │           │   app/{domain}/          │
└────────────┬───────────┘           └───────────┬──────────────┘
             │                                   │
             ▼ Events                            ▼ SELECT
┌────────────────────────┐           ┌──────────────────────────┐
│   INFRASTRUCTURE       │           │   POSTGRESQL             │
│   EventStore           │───────────▶   Read Models            │
│   EventBus (Redpanda)  │           │   Projections            │
│   Redis Cache          │           └──────────────────────────┘
└────────────────────────┘
```

---

## CQRS Flow

### Write Side (Commands)

```
API Request
    │
    ▼
POST /api/users/create
    │
    ▼
CommandBus.send(CreateUserCommand)
    │
    ▼
CommandHandler.handle(CreateUserCommand)
    │
    ▼
Aggregate.create_user(...)
    │
    ▼
Aggregate.apply(UserCreatedEvent)
    │
    ▼
AggregateRepository.save(aggregate)
    │
    ├─▶ EventStore.append(events)         [Redpanda: eventstore.{domain}]
    │
    └─▶ EventBus.publish(UserCreatedEvent) [Redpanda: transport.{domain}]
```

### Read Side (Queries)

```
API Request
    │
    ▼
GET /api/users/{id}
    │
    ▼
QueryBus.execute(GetUserByIdQuery)
    │
    ▼
QueryHandler.handle(GetUserByIdQuery)
    │
    ▼
PostgreSQL.query("SELECT * FROM users WHERE id = $1")
    │
    ▼
Return UserReadModel
```

### Event Processing (Projections)

```
EventBus (Redpanda: transport.*)
    │
    ▼
EventProcessorWorker.consume()
    │
    ▼
Projector.handle(UserCreatedEvent)
    │
    ▼
PostgreSQL.execute("INSERT INTO users ...")
    │
    ▼
Read Model Updated
```

---

## Event Sourcing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         EVENT SOURCING                          │
└─────────────────────────────────────────────────────────────────┘

1. COMMAND EXECUTION
   CreateUserCommand ──▶ Aggregate ──▶ UserCreatedEvent
                                            │
                                            ▼
2. EVENT PERSISTENCE
   EventStore.append(event) ──▶ Redpanda Topic: eventstore.user_account
                                            │
                                            ▼
3. EVENT PUBLICATION
   EventBus.publish(event) ──▶ Redpanda Topic: transport.user_account
                                            │
                                            ▼
4. EVENT PROJECTION
   EventProcessorWorker.consume() ──▶ Projector ──▶ PostgreSQL
                                            │
                                            ▼
5. READ MODEL UPDATED
   users table (id, username, email, created_at, ...)


AGGREGATE RECONSTRUCTION (Event Sourcing)
─────────────────────────────────────────
AggregateRepository.load(aggregate_id)
    │
    ▼
EventStore.get_events(aggregate_id)
    │
    ▼
[Event1, Event2, Event3, ...]
    │
    ▼
Aggregate.apply(Event1)
Aggregate.apply(Event2)
Aggregate.apply(Event3)
    │
    ▼
Current Aggregate State Reconstructed
```

---

## Domain-Driven Design Structure

### Domains in TradeCore

```
app/
├── user_account/              [Domain: User Management]
│   ├── aggregate.py           # UserAccountAggregate
│   ├── commands.py            # CreateUserCommand, UpdateUserCommand
│   ├── events.py              # UserCreatedEvent, UserUpdatedEvent
│   ├── command_handlers/      # Command handlers
│   ├── projectors.py          # Event projectors
│   ├── read_models.py         # UserReadModel
│   └── queries.py             # GetUserByIdQuery
│
├── broker_connection/         [Domain: Broker Connections]
│   ├── aggregate.py           # BrokerConnectionAggregate
│   ├── commands.py            # ConnectBrokerCommand
│   ├── events.py              # BrokerConnectedEvent
│   └── ...
│
├── broker_account/            [Domain: Broker Accounts]
│   ├── aggregate.py           # BrokerAccountAggregate
│   ├── commands.py            # CreateAccountCommand
│   ├── events.py              # AccountCreatedEvent
│   └── ...
│
├── order/                     [Domain: Order Management]
│   ├── aggregate.py           # OrderAggregate
│   ├── commands.py            # PlaceOrderCommand
│   ├── events.py              # OrderPlacedEvent, OrderFilledEvent
│   └── ...
│
├── position/                  [Domain: Position Management]
│   ├── aggregate.py           # PositionAggregate
│   ├── commands.py            # OpenPositionCommand
│   ├── events.py              # PositionOpenedEvent
│   └── ...
│
├── automation/                [Domain: Trading Automation]
│   ├── aggregate.py           # AutomationAggregate
│   ├── commands.py            # CreateAlertCommand
│   ├── events.py              # AlertCreatedEvent
│   └── ...
│
├── portfolio/                 [Domain: Portfolio Analytics]
│   ├── aggregate.py           # PortfolioAggregate
│   ├── commands.py            # CreatePortfolioCommand
│   ├── events.py              # PortfolioCreatedEvent
│   └── ...
│
└── virtual_broker/            [Domain: Paper Trading]
    ├── aggregate.py           # VirtualBrokerAggregate
    ├── commands.py            # SimulateTradeCommand
    ├── events.py              # TradeSimulatedEvent
    └── ...
```

### Domain Components

```
┌─────────────────────────────────────────────────────────────────┐
│                          DOMAIN LAYER                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────┐    ┌────────────────┐    ┌──────────────┐ │
│  │   Commands     │───▶│  Aggregate     │───▶│   Events     │ │
│  │  (Dataclass)   │    │  (Entity)      │    │  (Pydantic)  │ │
│  └────────────────┘    └────────────────┘    └──────────────┘ │
│         │                     │                      │         │
│         │                     │                      │         │
│  ┌─────▼──────────┐    ┌─────▼──────────┐    ┌─────▼────────┐│
│  │Command Handler │    │Value Objects   │    │ Projectors   ││
│  │                │    │(Frozen @data)  │    │              ││
│  └────────────────┘    └────────────────┘    └──────────────┘│
│         │                                            │         │
│         │                                            │         │
│  ┌─────▼──────────┐                          ┌─────▼────────┐│
│  │  Query Handler │                          │Read Models   ││
│  │                │                          │(Pydantic)    ││
│  └────────────────┘                          └──────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Infrastructure Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                      INFRASTRUCTURE LAYER                       │
│                     app/infra/*                                 │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐  ┌─────────────┐
│   EVENT BUS          │  │   EVENT STORE        │  │   REDIS     │
│  (Redpanda/Kafka)    │  │  (Redpanda/Kafka)    │  │   Cache     │
│                      │  │                      │  │             │
│  Topics:             │  │  Topics:             │  │  Usage:     │
│  - transport.*       │  │  - eventstore.*      │  │  - Cache    │
│  - saga.*            │  │                      │  │  - Lock     │
│  - system.*          │  │  Retention:          │  │  - Pub/Sub  │
│  - alerts.*          │  │  - 10 years          │  │             │
│                      │  │                      │  │  TTL:       │
│  Retention:          │  │  Purpose:            │  │  - 5-60 min │
│  - 7 days            │  │  - Source of Truth   │  │             │
│                      │  │  - Audit Trail       │  │             │
│  Purpose:            │  │  - Event Replay      │  │             │
│  - Event Transport   │  │  - Aggregate Rebuild │  │             │
└──────────────────────┘  └──────────────────────┘  └─────────────┘

┌──────────────────────┐  ┌──────────────────────┐  ┌─────────────┐
│   POSTGRESQL         │  │   CQRS BUS           │  │   SAGA      │
│   Read Models        │  │   Command/Query      │  │   Engine    │
│                      │  │                      │  │             │
│  Tables:             │  │  Components:         │  │  Features:  │
│  - users             │  │  - CommandBus        │  │  - Orchestr │
│  - connections       │  │  - QueryBus          │  │  - Compens  │
│  - accounts          │  │  - HandlerRegistry   │  │  - Rollback │
│  - orders            │  │  - @command_handler  │  │  - Timeout  │
│  - positions         │  │  - @query_handler    │  │             │
│  - portfolios        │  │                      │  │  Duration:  │
│  - ...               │  │  Routing:            │  │  - 30-300s  │
│                      │  │  - Command → Handler │  │             │
│  Purpose:            │  │  - Query → Handler   │  │             │
│  - Fast Reads        │  │                      │  │             │
│  - Projections       │  │  Async:              │  │             │
│  - Queries           │  │  - All async/await   │  │             │
└──────────────────────┘  └──────────────────────┘  └─────────────┘
```

---

## Workers Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         WORKERS LAYER                           │
└─────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  EventProcessorWorker (Read-Side Projections)                  │
│  ────────────────────────────────────────────────────────────  │
│  Consumes: transport.* (all domain events)                     │
│  Purpose:  Project events to PostgreSQL read models            │
│  Pattern:  Event → Projector → PostgreSQL                      │
│  Speed:    <100ms per event                                    │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  DataSyncWorker (Background Sync + Integrity)                  │
│  ────────────────────────────────────────────────────────────  │
│  Consumes: worker.data-sync.* , alerts.data-integrity          │
│  Purpose:  Background historical sync + integrity checks       │
│  Pattern:  Event → Command → Domain                            │
│  Layers:   Tier 2 (background) + Tier 4 (integrity)           │
└────────────────────────────────────────────────────────────────┘

Workers interact ONLY through:
  - CommandBus (send commands)
  - QueryBus (read data)
  - EventBus (publish/consume events)

NEVER direct service calls, NEVER direct DB access.
```

---

## Data Flow: Complete Request Lifecycle

### Example: Create User and Query

```
┌──────────────────────────────────────────────────────────────────┐
│ STEP 1: CLIENT SENDS COMMAND                                     │
└──────────────────────────────────────────────────────────────────┘

POST /api/users/create
Body: { "username": "john", "email": "john@example.com" }
    │
    ▼
API Router (app/api/routers/user_router.py)
    │
    ▼
await command_bus.send(CreateUserCommand(...))


┌──────────────────────────────────────────────────────────────────┐
│ STEP 2: COMMAND HANDLING (WRITE SIDE)                            │
└──────────────────────────────────────────────────────────────────┘

CommandBus
    │
    ▼
@command_handler(CreateUserCommand)
async def handle_create_user(cmd, deps)
    │
    ▼
aggregate = UserAccountAggregate.create(...)
aggregate.apply(UserCreatedEvent)
    │
    ▼
await aggregate_repository.save(aggregate)


┌──────────────────────────────────────────────────────────────────┐
│ STEP 3: EVENT PERSISTENCE                                        │
└──────────────────────────────────────────────────────────────────┘

AggregateRepository.save()
    │
    ├─▶ EventStore.append(events)
    │   ├─▶ Redpanda: eventstore.user_account (10 years)
    │   └─▶ PostgreSQL: event_store_events table
    │
    └─▶ EventBus.publish(UserCreatedEvent)
        └─▶ Redpanda: transport.user_account (7 days)


┌──────────────────────────────────────────────────────────────────┐
│ STEP 4: EVENT PROCESSING (READ SIDE)                             │
└──────────────────────────────────────────────────────────────────┘

EventProcessorWorker (listening on transport.user_account)
    │
    ▼
consume(UserCreatedEvent)
    │
    ▼
@projector(UserCreatedEvent)
async def project_user_created(event, pg_client)
    │
    ▼
await pg_client.execute(
    "INSERT INTO users (id, username, email, ...) VALUES (...)"
)
    │
    ▼
Read Model Updated in PostgreSQL


┌──────────────────────────────────────────────────────────────────┐
│ STEP 5: CLIENT QUERIES DATA                                      │
└──────────────────────────────────────────────────────────────────┘

GET /api/users/{user_id}
    │
    ▼
API Router
    │
    ▼
await query_bus.execute(GetUserByIdQuery(user_id))
    │
    ▼
@query_handler(GetUserByIdQuery)
async def handle_get_user(query, deps)
    │
    ▼
result = await pg_client.fetchrow(
    "SELECT * FROM users WHERE id = $1", query.user_id
)
    │
    ▼
return UserReadModel(**result)
    │
    ▼
Response: { "id": "...", "username": "john", "email": "..." }
```

---

## Saga Flow (Orchestration)

```
┌──────────────────────────────────────────────────────────────────┐
│                     SAGA ORCHESTRATION                           │
└──────────────────────────────────────────────────────────────────┘

Example: Connect Broker Saga

POST /api/connections/connect
    │
    ▼
StartConnectBrokerCommand
    │
    ▼
BrokerConnectionSaga.handle(ConnectionRequestedEvent)
    │
    ├─▶ Step 1: ValidateBrokerCredentialsCommand
    │   │
    │   ▼
    │   CredentialsValidatedEvent
    │   │
    ├─▶ Step 2: EstablishBrokerConnectionCommand
    │   │
    │   ▼
    │   ConnectionEstablishedEvent
    │   │
    ├─▶ Step 3: FetchAccountsFromBrokerCommand
    │   │
    │   ▼
    │   AccountsFetchedEvent
    │   │
    └─▶ Step 4: FinalizeBrokerConnectionCommand
        │
        ▼
        BrokerConnectionCompletedEvent

If any step fails:
    │
    ▼
Saga Compensation (Rollback)
    │
    ├─▶ DisconnectBrokerCommand
    ├─▶ CleanupAdapterCommand
    └─▶ BrokerConnectionFailedEvent


Saga State Storage: saga.* Redpanda topics
Timeout: 30-300 seconds
Compensation: Automatic rollback on failure
```

---

## Event Flow Diagram

```
┌─────────────┐
│   API       │  POST /api/orders/place
└──────┬──────┘
       │ PlaceOrderCommand
       ▼
┌─────────────┐
│CommandBus   │  Route to handler
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Order Domain │  OrderAggregate.place_order()
│Handler      │  aggregate.apply(OrderPlacedEvent)
└──────┬──────┘
       │ OrderPlacedEvent
       ▼
┌─────────────────────────┬─────────────────────────┐
│                         │                         │
▼                         ▼                         ▼
┌─────────────┐  ┌──────────────┐  ┌──────────────┐
│ EventStore  │  │  EventBus    │  │   Saga       │
│ (Redpanda)  │  │  (Redpanda)  │  │   Engine     │
│             │  │              │  │              │
│ eventstore  │  │ transport    │  │ saga.*       │
│ .order      │  │ .order       │  │              │
└─────────────┘  └──────┬───────┘  └──────┬───────┘
                        │                 │
         ┌──────────────┴──────┐         │
         │                     │         │
         ▼                     ▼         ▼
┌─────────────────┐   ┌────────────────────┐
│EventProcessor   │   │ Position Domain    │
│Worker           │   │ (Cross-Domain)     │
│                 │   │                    │
│ Projector       │   │ Saga triggers      │
│ ↓               │   │ UpdatePosition     │
│ PostgreSQL      │   │ Command            │
│ orders table    │   └────────────────────┘
└─────────────────┘
```

---

## Storage Strategy

### EventStore (Source of Truth)

```
Redpanda Topics: eventstore.*
Retention: 10 years
Purpose: Event Sourcing, Audit Trail, Aggregate Rebuild

eventstore.user_account       [UserCreatedEvent, UserUpdatedEvent, ...]
eventstore.broker_connection  [ConnectionRequestedEvent, ...]
eventstore.broker_account     [AccountCreatedEvent, ...]
eventstore.order              [OrderPlacedEvent, OrderFilledEvent, ...]
eventstore.position           [PositionOpenedEvent, PositionClosedEvent, ...]
eventstore.automation         [AlertCreatedEvent, AlertTriggeredEvent, ...]
```

### EventBus (Transport)

```
Redpanda Topics: transport.*, saga.*, system.*, alerts.*
Retention: 7 days
Purpose: Event Transport, Worker Communication

transport.user_account        [Domain events for projection]
transport.broker_connection   [Domain events for projection]
saga.broker_connection        [Saga orchestration events]
alerts.data-integrity         [Integrity check alerts]
worker.data-sync.sync-requests [Background sync triggers]
```

### PostgreSQL (Read Models)

```
Tables: users, connections, accounts, orders, positions, ...
Retention: 90 days (hot data)
Purpose: Fast queries, projections

SELECT * FROM orders WHERE user_id = $1 AND status = 'open'
```

### Redis (Cache + Coordination)

```
Purpose: Cache, Distributed Lock, Pub/Sub (WSE coordination only)
TTL: 5-60 minutes

Cache Keys:
  - user:{id}:profile
  - connection:{id}:status
  - account:{id}:balance

Locks:
  - lock:saga:{saga_id}
  - lock:sync:{account_id}
```

---

## Domain Communication

### Rule: Domains NEVER call each other directly

```
WRONG:
app/order/command_handlers/place_order.py
    │
    └─▶ position_service.update_position()  # FORBIDDEN

CORRECT:
app/order/command_handlers/place_order.py
    │
    └─▶ EventBus.publish(OrderPlacedEvent)
            │
            ▼
        Saga/Domain Subscriber
            │
            └─▶ CommandBus.send(UpdatePositionCommand)
```

### Cross-Domain Interaction Patterns

```
1. EVENT-DRIVEN (Preferred)
   Order Domain ─(OrderFilledEvent)─▶ EventBus ─▶ Position Domain

2. SAGA ORCHESTRATION
   Saga ─(PlaceOrderCommand)─▶ Order Domain
        ─(UpdatePositionCommand)─▶ Position Domain

3. QUERY (Read-Only)
   Order Domain ─(GetPositionQuery)─▶ QueryBus ─▶ Position Read Model
```

---

## Key Principles

### CQRS Principles

1. **Command Responsibility**: Write operations go through CommandBus to Aggregates
2. **Query Responsibility**: Read operations go through QueryBus to Read Models
3. **Eventual Consistency**: Write completes immediately, read model updates asynchronously
4. **Separation**: Commands change state, Queries return data (never both)

### Event Sourcing Principles

1. **Events are Immutable**: Once written, never modified
2. **Events are Append-Only**: New events added, old events never deleted
3. **Events are Source of Truth**: Aggregate state reconstructed from events
4. **Events are Timestamped**: Every event has occurred_at timestamp

### DDD Principles

1. **Bounded Contexts**: Each domain has clear boundaries
2. **Aggregates**: Consistency boundary (Order, Position, User)
3. **Value Objects**: Immutable (Price, Quantity, Symbol)
4. **Domain Events**: Capture business facts (OrderPlaced, PositionOpened)
5. **Anti-Corruption Layer**: Broker adapters translate external → domain

---

## Pattern Summary

```
┌────────────────────────────────────────────────────────────────┐
│                   TRADECORE ARCHITECTURE                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Pattern: CQRS + Event Sourcing + DDD + Saga                  │
│                                                                │
│  Write Side:  API → Command → Aggregate → Event → Store       │
│  Read Side:   Event → Worker → Projector → PostgreSQL         │
│  Query Side:  API → Query → PostgreSQL → Response             │
│                                                                │
│  Event Flow:  Domain → EventStore (10yr) → EventBus (7d)      │
│               → Worker → Projection → PostgreSQL              │
│                                                                │
│  Saga Flow:   Event → Saga → Command → Domain → Event         │
│               (with compensation on failure)                   │
│                                                                │
│  Storage:                                                      │
│    - EventStore (Redpanda): Source of Truth                   │
│    - PostgreSQL: Read Models (fast queries)                   │
│    - Redis: Cache + Coordination                              │
│                                                                │
│  Communication:                                                │
│    - CommandBus: Commands to domains                          │
│    - QueryBus: Queries to read models                         │
│    - EventBus: Events between domains                         │
│    - Saga: Orchestration across domains                       │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## References

- **CQRS**: `docs/cqrs.md`
- **Event Sourcing**: `docs/mvp/EVENT_STORE_MANUAL.md`
- **EventBus**: `docs/mvp/EVENT_BUS_MANUAL.md`
- **Domain Creation**: `docs/mvp/DOMAIN_CREATION_TEMPLATE.md`
- **Best Practices**: `docs/mvp/DOMAIN_IMPLEMENTATION_BEST_PRACTICES.md`
- **Workers**: `docs/mvp/WORKER_REFACTORING_SUMMARY.md`

---

**End of Architecture Schema**