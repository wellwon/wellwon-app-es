# TradeCore Reference Documentation - Complete Index

**Created**: 2025-11-10
**Version**: 1.0
**Status**: Complete

---

## Overview

This is the **complete reference library** for TradeCore's event-driven architecture. All guides are production-ready and based on real code from TradeCore v0.5+.

**Total Documentation**: 20+ comprehensive guides covering every aspect of the infrastructure.

---

## Quick Navigation

### For New Developers
1. Start: `00_ARCHITECTURE_OVERVIEW.md` (understand the system)
2. Practice: `01_DOMAIN_CREATION_GUIDE.md` (build your first domain)
3. Learn: `COMMON_PITFALLS.md` (avoid 14 documented bugs)
4. Test: `UNIT_TESTING_GUIDE.md` (write tests)

### For Experienced Developers
- API: `03_API_ROUTER_GUIDE.md`
- Services: `04_SERVICE_CREATION_GUIDE.md`
- Sagas: `02_TRUE_SAGA_GUIDE.md`
- Performance: `PERFORMANCE_OPTIMIZATION_GUIDE.md`

### For Architects
- Architecture: `00_ARCHITECTURE_OVERVIEW.md`
- Patterns: `AGGREGATE_PATTERNS.md`, `SAGA_PATTERNS.md`
- Infrastructure: `EVENT_BUS_GUIDE.md`, `DATABASE_PATTERNS.md`

### For Troubleshooting
- Bugs: `COMMON_PITFALLS.md` (14 bugs documented)
- Debug: `DEBUGGING_EVENT_FLOW.md` (step-by-step tracing)
- Tests: `INTEGRATION_TESTING_GUIDE.md`

---

## Complete Guide List

### 1. Architecture & Overview (1 guide)

| Guide | Lines | Description |
|-------|-------|-------------|
| `00_ARCHITECTURE_OVERVIEW.md` | ~2,000 | Complete system architecture, CQRS/ES/DDD, data flows, tech stack |

**Key Topics**: CQRS, Event Sourcing, DDD, Sagas, Redpanda, Granian

---

### 2. Domain Layer (4 guides)

| Guide | Lines | Description |
|-------|-------|-------------|
| `01_DOMAIN_CREATION_GUIDE.md` | ~2,500 | Step-by-step domain creation (10 steps) |
| `AGGREGATE_PATTERNS.md` | ~2,000 | Aggregate design, state management, event application |
| `EVENT_DESIGN_PATTERNS.md` | ~1,800 | Event schema, enrichment, versioning, serialization |
| `VALUE_OBJECTS_GUIDE.md` | ~1,700 | Immutable value objects, validation, equality |

**Key Topics**: Aggregates, Events (BaseEvent), Commands, Value Objects (frozen dataclasses), Business Rules

**Real Examples**: Automation (4,309 lines), BrokerConnection (2,500 lines), Position (1,819 lines)

---

### 3. CQRS Implementation (3 guides)

| Guide | Lines | Description |
|-------|-------|-------------|
| `COMMAND_HANDLER_GUIDE.md` | ~1,500 | Write operations, validation, aggregate loading |
| `QUERY_HANDLER_GUIDE.md` | ~1,400 | Read operations, BaseQueryHandler, authorization |
| `PROJECTOR_GUIDE.md` | ~1,300 | Event-to-read-model, SYNC/ASYNC, idempotency |

**Key Topics**: CommandBus, QueryBus, Handlers, Projectors, SYNC projections (2s timeout)

---

### 4. Sagas & Orchestration (4 guides)

| Guide | Lines | Description |
|-------|-------|-------------|
| `02_TRUE_SAGA_GUIDE.md` | ~2,200 | True Saga pattern, event enrichment, context builder |
| `SAGA_PATTERNS.md` | ~1,600 | Common patterns (connection, disconnection, recovery, deletion) |
| `COMPENSATION_GUIDE.md` | ~1,500 | Rollback strategies, when to compensate |
| `SYNC_VS_ASYNC_EVENTS.md` | ~1,400 | SYNC (2s) vs ASYNC events, performance implications |

**Key Topics**: Event-driven orchestration, Compensation, Context builder bug fix, TRUE SAGA pattern

**Real Examples**: BrokerConnectionSaga (883 lines), BrokerDisconnectionSaga (1,336 lines)

---

### 5. API Layer (2 guides)

| Guide | Lines | Description |
|-------|-------|-------------|
| `03_API_ROUTER_GUIDE.md` | ~1,600 | REST API routers, FastAPI, CQRS integration |
| `WEBSOCKET_GUIDE.md` | ~800 | WebSocket Engine (WSE), real-time updates |

**Key Topics**: FastAPI routers, Authentication (JWT), Request/Response models, WebSocket

---

### 6. Application Services (1 guide)

| Guide | Lines | Description |
|-------|-------|-------------|
| `04_SERVICE_CREATION_GUIDE.md` | ~2,000 | Service patterns (Facade, Handler, Coordinator, Background) |

**Key Topics**: Broker Streaming Architecture (2025 refactor), Direct subscription pattern, Industry best practices

---

### 7. Infrastructure (4 guides)

| Guide | Lines | Description |
|-------|-------|-------------|
| `EVENT_BUS_GUIDE.md` | ~2,000 | EventBus, Redpanda, pub/sub, exactly-once delivery |
| `CIRCUIT_BREAKER_GUIDE.md` | ~1,800 | Fault tolerance, 3-state pattern, get_state_sync() bug fix |
| `CACHE_STRATEGY_GUIDE.md` | ~1,900 | Redis caching, distributed locking, rate limiting |
| `DATABASE_PATTERNS.md` | ~2,300 | Postgres, AsyncPG, SYNC projections, migrations |

**Key Topics**: Redpanda/Kafka, Circuit breakers, Redis, PostgreSQL, Multi-worker safety (Granian)

---

### 8. Testing (2 guides)

| Guide | Lines | Description |
|-------|-------|-------------|
| `UNIT_TESTING_GUIDE.md` | ~900 | Aggregates, handlers, projectors, mocking |
| `INTEGRATION_TESTING_GUIDE.md` | ~900 | CQRS flow, sagas, API endpoints, event flow |

**Key Topics**: pytest, AsyncMock, fixtures, replay equivalence, idempotency testing

---

### 9. Troubleshooting (2 guides)

| Guide | Lines | Description |
|-------|-------|-------------|
| `COMMON_PITFALLS.md` | ~750 | 14 documented bugs we've fixed (datetime.utcnow, PascalCase, etc.) |
| `DEBUGGING_EVENT_FLOW.md` | ~850 | Event tracing, Redpanda Console, logs, database queries |

**Key Topics**: Bug fixes, Investigation techniques, Log patterns, Redpanda Console usage

**Real Bug Fixes**: Circuit breaker AttributeError, Saga context builder, datetime.utcnow(), PascalCase methods

---

### 10. Performance (1 guide)

| Guide | Lines | Description |
|-------|-------|-------------|
| `PERFORMANCE_OPTIMIZATION_GUIDE.md` | ~1,800 | Saga optimization, SYNC projections, cache, database, monitoring |

**Key Topics**: BrokerConnectionSaga (5-7x faster), SYNC projection strategy (72% reduction), Performance targets

---

## Documentation Statistics

- **Total Guides**: 24 comprehensive guides
- **Total Lines**: ~35,000+ lines of documentation
- **Code Examples**: 200+ working examples from production code
- **Bug Fixes Documented**: 14 real bugs with root cause and fix
- **Test Patterns**: 50+ testing patterns
- **Architecture Diagrams**: 30+ ASCII diagrams
- **Performance Benchmarks**: 10+ optimizations documented

---

## By Use Case

### Building a New Domain
1. `01_DOMAIN_CREATION_GUIDE.md` - Step-by-step (10 steps)
2. `AGGREGATE_PATTERNS.md` - Aggregate design
3. `EVENT_DESIGN_PATTERNS.md` - Event schema
4. `COMMAND_HANDLER_GUIDE.md` - Command handling
5. `PROJECTOR_GUIDE.md` - Read model updates
6. `UNIT_TESTING_GUIDE.md` - Testing

### Building a Saga
1. `02_TRUE_SAGA_GUIDE.md` - True Saga pattern
2. `SAGA_PATTERNS.md` - Common patterns
3. `COMPENSATION_GUIDE.md` - Rollback strategies
4. `PERFORMANCE_OPTIMIZATION_GUIDE.md` - Optimization

### Building an API
1. `03_API_ROUTER_GUIDE.md` - REST endpoints
2. `WEBSOCKET_GUIDE.md` - Real-time updates
3. `04_SERVICE_CREATION_GUIDE.md` - Application services

### Debugging Production Issues
1. `DEBUGGING_EVENT_FLOW.md` - Tracing events
2. `COMMON_PITFALLS.md` - Known bugs
3. `INTEGRATION_TESTING_GUIDE.md` - Testing flows

### Performance Optimization
1. `PERFORMANCE_OPTIMIZATION_GUIDE.md` - All optimizations
2. `SYNC_VS_ASYNC_EVENTS.md` - Projection strategy
3. `CACHE_STRATEGY_GUIDE.md` - Caching patterns
4. `DATABASE_PATTERNS.md` - Database optimization

---

## Critical Knowledge

### Must Read First
1. `00_ARCHITECTURE_OVERVIEW.md` - Understand the system
2. `COMMON_PITFALLS.md` - Avoid 14 documented bugs
3. `01_DOMAIN_CREATION_GUIDE.md` - Build correctly

### Critical Code Quality Rules

From `COMMON_PITFALLS.md`:

1. **NEVER use `datetime.utcnow()`** - DEPRECATED in Python 3.12+
   - ✅ Use `datetime.now(UTC)` instead

2. **ALWAYS use snake_case** for method names (PEP 8)
   - ✅ `def _on_position_opened_event(self, event):`
   - ❌ `def _on_PositionOpenedEvent(self, event):`

3. **Events MUST inherit from BaseEvent** (Pydantic)
   - ✅ `class PositionOpenedEvent(BaseEvent):`
   - ❌ `@dataclass class PositionOpenedEvent:`

4. **Events MUST have `event_type`** field
   - ✅ `event_type: Literal["PositionOpenedEvent"] = "PositionOpenedEvent"`

5. **NO queries in sagas** (True Saga pattern)
   - ✅ Use event enrichment in handlers
   - ❌ Query in saga steps

6. **Business logic ONLY in aggregates**
   - ✅ Aggregate methods contain business rules
   - ❌ Business logic in services or handlers

---

## Real Production Examples

### Simple Domain (Learning)
- **Example**: `app/broker_account/`
- **Size**: ~1,200 lines
- **Events**: 8
- **SYNC Rate**: 28%
- **Good for**: Understanding basics

### Medium Domain (Real-World)
- **Example**: `app/broker_connection/`
- **Size**: ~2,500 lines
- **Events**: 15+
- **SYNC Rate**: 8% (optimized)
- **Good for**: OAuth, encryption, state management

### Complex Domain (Advanced)
- **Example**: `app/automation/`
- **Size**: 4,309 lines
- **Events**: 13
- **SYNC Rate**: 75%
- **Good for**: State machines, pyramiding, derivatives

### Complex Saga (Orchestration)
- **Example**: `BrokerDisconnectionSaga`
- **Size**: 1,336 lines
- **Commands**: 5 domains
- **Pattern**: TRUE SAGA (event enrichment)
- **Good for**: Multi-domain cleanup, compensation

---

## Recent Updates (2025-11-10)

### Performance Optimizations Documented
- BrokerConnectionSaga: 15s → 2-3s (5-7x faster)
- SYNC projection strategy: 72% reduction
- Circuit breaker bug fix: `get_state_sync()` vs `.state`

### Bug Fixes Documented
1. Circuit breaker AttributeError (WSE disconnect)
2. Saga context builder missing enriched fields (disconnection)
3. Account creation performance (saga retry optimization)

### Architecture Improvements
- TRUE SAGA pattern (event enrichment eliminates queries)
- Broker streaming refactor (Facade + Handler pattern)
- SYNC projection optimization (2s timeout)

---

## Reusability

**This infrastructure works for ANY event-driven application:**

- E-commerce (order fulfillment, inventory)
- Healthcare (appointments, patient records)
- Booking systems (reservations, availability)
- IoT platforms (device management, telemetry)
- Financial services (payments, accounts)
- Logistics (shipments, tracking)

**What's reusable:**
- CQRS/Event Sourcing infrastructure
- Saga orchestration patterns
- Event Bus (Redpanda)
- Circuit breakers and retry
- Caching and database patterns
- API router patterns
- Testing strategies

**What's domain-specific:**
- Broker adapters (Alpaca, TradeStation)
- Trading business logic (orders, positions)
- Market data streaming

---

## Getting Started

### Day 1: Architecture Understanding
1. Read `00_ARCHITECTURE_OVERVIEW.md`
2. Review `COMMON_PITFALLS.md`
3. Explore example domains (`app/broker_account/`, `app/automation/`)

### Day 2: Build First Domain
1. Follow `01_DOMAIN_CREATION_GUIDE.md` (10 steps)
2. Reference `AGGREGATE_PATTERNS.md` for design
3. Use `UNIT_TESTING_GUIDE.md` for tests

### Day 3: Build API
1. Follow `03_API_ROUTER_GUIDE.md`
2. Reference `04_SERVICE_CREATION_GUIDE.md` for services
3. Test with `INTEGRATION_TESTING_GUIDE.md`

### Day 4: Build Saga
1. Read `02_TRUE_SAGA_GUIDE.md`
2. Review `SAGA_PATTERNS.md` for patterns
3. Implement compensation with `COMPENSATION_GUIDE.md`

### Day 5: Optimize & Debug
1. Review `PERFORMANCE_OPTIMIZATION_GUIDE.md`
2. Learn debugging with `DEBUGGING_EVENT_FLOW.md`
3. Set up monitoring and metrics

---

## Contributing to Documentation

When adding new guides:
1. Follow existing format (Overview, Steps, Examples, Testing, Best Practices)
2. Include code examples from real production code
3. Add "Good" and "Bad" examples
4. Include troubleshooting section
5. Reference related guides
6. Update this index

---

## Support

**Documentation Issues**: Check `COMMON_PITFALLS.md` first
**Architecture Questions**: See `00_ARCHITECTURE_OVERVIEW.md`
**Debugging Help**: Follow `DEBUGGING_EVENT_FLOW.md`
**Code Examples**: All guides include production code

---

## Version History

- **v1.0** (2025-11-10) - Complete reference library created
  - 24 comprehensive guides
  - 35,000+ lines of documentation
  - 200+ code examples
  - 14 bug fixes documented
  - Performance optimizations documented

---

**Total Documentation Coverage: COMPLETE** ✅
