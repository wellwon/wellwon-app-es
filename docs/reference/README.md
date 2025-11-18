# TradeCore Infrastructure Reference Guides

**Purpose**: Reusable architecture patterns and implementation guides for building any event-driven application using TradeCore's battle-tested infrastructure.

**Last Updated**: 2025-11-10

---

## What This Is

TradeCore's infrastructure is **domain-agnostic** and can be reused for **any event-driven application**:
- E-commerce platforms
- CRM systems
- Booking/reservation systems
- IoT management platforms
- Financial applications (beyond trading)
- Healthcare management systems
- Logistics/supply chain platforms

This reference library provides **step-by-step implementation guides** with real production examples from TradeCore.

---

## Quick Start

**New to this architecture?** Read in this order:

1. `00_ARCHITECTURE_OVERVIEW.md` - Understand the infrastructure
2. `01_DOMAIN_CREATION_GUIDE.md` - Create your first domain
3. `02_TRUE_SAGA_GUIDE.md` - Build distributed workflows
4. `03_API_ROUTER_GUIDE.md` - Expose REST APIs
5. `04_SERVICE_CREATION_GUIDE.md` - Application services

**Already familiar?** Jump to specific guides below.

---

## Reference Guides

### Core Architecture

| Guide | Description | Use When |
|-------|-------------|----------|
| `00_ARCHITECTURE_OVERVIEW.md` | Infrastructure overview, patterns, and design principles | Starting a new project |
| `INFRASTRUCTURE_SETUP.md` | Docker, Postgres, Redis, Redpanda setup | Setting up environment |

### Domain Layer (Business Logic)

| Guide | Description | Use When |
|-------|-------------|----------|
| `01_DOMAIN_CREATION_GUIDE.md` | Complete domain implementation (aggregate, events, commands) | Creating new business domain |
| `AGGREGATE_PATTERNS.md` | Aggregate design patterns with examples | Designing aggregates |
| `EVENT_DESIGN_PATTERNS.md` | Event schema design and versioning | Creating domain events |
| `VALUE_OBJECTS_GUIDE.md` | Immutable value objects | Creating domain value types |

### CQRS & Event Sourcing

| Guide | Description | Use When |
|-------|-------------|----------|
| `COMMAND_HANDLER_GUIDE.md` | Command handlers and validation | Processing commands |
| `QUERY_HANDLER_GUIDE.md` | Query handlers and read models | Building queries |
| `PROJECTOR_GUIDE.md` | Event projectors and read model updates | Updating read models |
| `SYNC_VS_ASYNC_EVENTS.md` | When to use SYNC vs ASYNC events | Event configuration |

### Sagas & Orchestration

| Guide | Description | Use When |
|-------|-------------|----------|
| `02_TRUE_SAGA_GUIDE.md` | True Saga pattern implementation | Building distributed workflows |
| `SAGA_PATTERNS.md` | Common saga patterns (connection, cleanup, etc.) | Saga design |
| `COMPENSATION_GUIDE.md` | Rollback and error handling | Saga failure recovery |

### API Layer

| Guide | Description | Use When |
|-------|-------------|----------|
| `03_API_ROUTER_GUIDE.md` | REST API routers with FastAPI | Exposing APIs |
| `WEBSOCKET_GUIDE.md` | WebSocket Engine (WSE) integration | Real-time updates |
| `API_SECURITY_GUIDE.md` | Authentication and authorization | Securing APIs |

### Application Services

| Guide | Description | Use When |
|-------|-------------|----------|
| `04_SERVICE_CREATION_GUIDE.md` | Application service patterns | Orchestrating workflows |
| `ADAPTER_PATTERN_GUIDE.md` | External system adapters | Integrating 3rd parties |
| `BACKGROUND_WORKERS.md` | Event consumers and workers | Processing events |

### Infrastructure

| Guide | Description | Use When |
|-------|-------------|----------|
| `EVENT_BUS_GUIDE.md` | EventBus and Redpanda integration | Publishing/subscribing events |
| `CACHE_STRATEGY_GUIDE.md` | Redis caching patterns | Optimizing performance |
| `DATABASE_PATTERNS.md` | Postgres read/write models | Database design |
| `CIRCUIT_BREAKER_GUIDE.md` | Reliability patterns | Fault tolerance |

### Testing & Troubleshooting

| Guide | Description | Use When |
|-------|-------------|----------|
| `UNIT_TESTING_GUIDE.md` | Testing aggregates, handlers, projectors | Writing unit tests |
| `INTEGRATION_TESTING_GUIDE.md` | Testing CQRS flow, sagas, API endpoints | Writing integration tests |
| `COMMON_PITFALLS.md` | Actual bugs we've fixed and how to avoid them | Code reviews, debugging |
| `DEBUGGING_EVENT_FLOW.md` | Tracing events through system with tools | Debugging production issues |

---

## Example Domains

Real production examples from TradeCore:

### Simple Domain
- **Example**: `app/user_account/`
- **Complexity**: Low
- **Events**: 8
- **Good for**: Learning basics

### Medium Domain
- **Example**: `app/broker_connection/`
- **Complexity**: Medium
- **Events**: 15+
- **Features**: OAuth, encryption, health monitoring
- **Good for**: Real-world patterns

### Complex Domain
- **Example**: `app/automation/`
- **Complexity**: High
- **Events**: 13
- **Features**: State machines, pyramiding, risk management
- **Good for**: Advanced patterns

### Cross-Domain Saga
- **Example**: `BrokerDisconnectionSaga`
- **Complexity**: High
- **Commands**: 5 domains
- **Good for**: Distributed orchestration

---

## Quick Reference Cards

### Command Flow
```
REST API → Command → Handler → Aggregate → Event → Projector → Read Model
```

### Query Flow
```
REST API → Query → Handler → Read Model → Response
```

### Saga Flow
```
Event → Saga Trigger → Saga Steps → Commands → Events → Completion
```

### Event Bus Flow
```
Domain Event → EventBus → Redpanda → Worker → Projector → Database
```

---

## Checklists

### New Domain Checklist
- [ ] Read `01_DOMAIN_CREATION_GUIDE.md`
- [ ] Create domain folder structure
- [ ] Define aggregates and events
- [ ] Implement command handlers
- [ ] Create projectors
- [ ] Add sync_events.py configuration
- [ ] Register in domain_registry.py
- [ ] Create database migrations
- [ ] Write unit tests
- [ ] Add API router

### New Saga Checklist
- [ ] Read `02_TRUE_SAGA_GUIDE.md`
- [ ] Design saga steps and compensation
- [ ] Ensure event enrichment in handlers
- [ ] Implement saga class with steps
- [ ] Add saga trigger configuration
- [ ] Test compensation logic
- [ ] Add timeout configuration
- [ ] Monitor saga metrics

### New API Router Checklist
- [ ] Read `03_API_ROUTER_GUIDE.md`
- [ ] Create router file in app/api/routers/
- [ ] Add authentication dependencies
- [ ] Implement endpoints (POST commands, GET queries)
- [ ] Add request/response models
- [ ] Add error handling
- [ ] Register in app/api/__init__.py
- [ ] Add OpenAPI documentation
- [ ] Write API tests

---

## Best Practices

### Critical Rules (Zero Tolerance)

1. **NEVER use `datetime.utcnow()`** - Always use `datetime.now(UTC)`
2. **ALWAYS use snake_case** for method names - Never use PascalCase
3. **ALL events MUST inherit from BaseEvent** - NOT @dataclass
4. **ALL events MUST have `event_type`** field with Literal type
5. **Value Objects MUST be frozen** - Use @dataclass(frozen=True)
6. **NO business logic in services** - Only in aggregates
7. **NO queries in sagas** - Only commands (True Saga pattern)
8. **NO direct database access** - Use CommandBus/QueryBus

### Code Quality Standards

- Type hints on all functions
- Async for all I/O operations
- Pydantic models for validation
- Proper error handling with custom exceptions
- Structured logging with context
- Metrics for monitoring
- Documentation for public APIs

---

## Migration from Monolith

If you're migrating from a traditional monolithic architecture:

1. **Start Small**: Pick one bounded context to extract
2. **Events First**: Define events before commands
3. **Read Model Separation**: CQRS gives you flexibility
4. **Gradual Sagas**: Start with simple workflows
5. **Keep Old System**: Run in parallel during migration

See: `MONOLITH_MIGRATION_GUIDE.md` for detailed steps.

---

## Performance Tuning

Each guide includes performance considerations, but see:
- `PERFORMANCE_OPTIMIZATION_GUIDE.md` - General optimization
- `SYNC_PROJECTION_OPTIMIZATION.md` - Fast projections
- `SAGA_PERFORMANCE_TUNING.md` - Saga optimization

---

## Troubleshooting

Common issues and solutions:
- `COMMON_PITFALLS.md` - 14 documented bugs we've fixed (datetime.utcnow, PascalCase methods, saga queries, etc.)
- `DEBUGGING_EVENT_FLOW.md` - Step-by-step event tracing with Redpanda Console, logs, and database queries
- `UNIT_TESTING_GUIDE.md` - Testing patterns for aggregates, handlers, and projectors
- `INTEGRATION_TESTING_GUIDE.md` - Testing complete CQRS flows and saga orchestration

---

## Reference Projects

Example applications built with this infrastructure:

1. **TradeCore** (This project) - Trading platform
2. **BookingCore** (Example) - Hotel/booking system
3. **InventoryCore** (Example) - Warehouse management
4. **HealthCore** (Example) - Patient management

See `REFERENCE_PROJECTS.md` for full list and links.

---

## Getting Help

1. **Read the guides** - Most questions answered here
2. **Check examples** - Look at TradeCore domains
3. **Review tests** - Tests show usage patterns
4. **Study logs** - Enable DEBUG logging

---

## Contributing

Improvements welcome! When adding guides:
1. Follow existing format
2. Include code examples
3. Add "Good" and "Bad" examples
4. Include troubleshooting section
5. Reference TradeCore examples

---

## Version History

- **v0.6** (2025-11-10) - True Saga migration, performance optimization
- **v0.5** (2025-11) - Granian migration, WebSocket fixes
- **v0.4** - Market data architecture refactor
- **v0.3** - SYNC projections implementation
- **v0.2** - Initial saga framework
- **v0.1** - Core CQRS/ES infrastructure

---

## License

This reference library is part of TradeCore and follows the same license.
