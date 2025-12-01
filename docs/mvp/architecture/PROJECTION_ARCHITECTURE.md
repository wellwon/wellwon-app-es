# WellWon Projection Architecture

**Version:** 1.0.0
**Last Updated:** 2025-12-01
**Status:** Production Ready

## Overview

WellWon uses a dual-decorator projection system implementing CQRS (Command Query Responsibility Segregation) with Event Sourcing. This document describes the production architecture for projection handling.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT REQUEST                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               FASTAPI SERVER                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────────┐ │
│  │   Router    │───▶│   Handler   │───▶│         Aggregate               │ │
│  └─────────────┘    └─────────────┘    │  ┌─────────────────────────┐   │ │
│                                         │  │   Domain Event Emitted  │   │ │
│                                         │  └─────────────────────────┘   │ │
│                                         └─────────────────────────────────┘ │
│                                                        │                     │
│                                                        ▼                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    KurrentDB Event Store                                ││
│  │   ┌──────────────────────────────────────────────────────────────────┐ ││
│  │   │  Stream: UserAccount-{uuid}  │  Events: UserAccountCreated, ...  │ ││
│  │   └──────────────────────────────────────────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                      │                                       │
│                    ┌─────────────────┴─────────────────┐                    │
│                    ▼                                   ▼                    │
│  ┌──────────────────────────────┐    ┌──────────────────────────────────┐  │
│  │    @sync_projection          │    │    Transactional Outbox          │  │
│  │    (Immediate Consistency)   │    │    (PostgreSQL → Kafka)          │  │
│  │                              │    │                                  │  │
│  │  execute_sync_projections()  │    │  OutboxPublisher                 │  │
│  │           │                  │    │  LISTEN/NOTIFY                   │  │
│  │           ▼                  │    └──────────────────────────────────┘  │
│  │  ┌────────────────────────┐  │                    │                     │
│  │  │ PostgreSQL Read Model  │  │                    │                     │
│  │  │ (Updated BEFORE resp.) │  │                    │                     │
│  │  └────────────────────────┘  │                    │                     │
│  └──────────────────────────────┘                    │                     │
│                                                       │                     │
│                          HTTP Response ◀─────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Kafka Message
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           KAFKA / REDPANDA                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  transport.user-account-events  │  transport.company-events  │ ...  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EVENT PROCESSOR WORKER                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      ConsumerManager                                 │   │
│  │   - Subscribes to: transport.user-account-events                    │   │
│  │                     transport.company-events                        │   │
│  │                     transport.chat-events                           │   │
│  │   - Consumer Group: event-processor-workers                         │   │
│  │   - Manual Commits (at-least-once)                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       EventProcessor                                 │   │
│  │                                                                      │   │
│  │   1. Try execute_sync_projections()  ← Check for sync handlers      │   │
│  │              │                                                       │   │
│  │              ▼                                                       │   │
│  │   2. If no sync handlers executed:                                  │   │
│  │      execute_async_projections()     ← Process async handlers       │   │
│  │              │                                                       │   │
│  │              ▼                                                       │   │
│  │   3. If no async handlers:                                          │   │
│  │      handle_event() legacy fallback                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    @async_projection                                 │   │
│  │                    (Eventual Consistency)                            │   │
│  │                                                                      │   │
│  │  ┌────────────────────────┐    ┌────────────────────────┐          │   │
│  │  │ PostgreSQL Read Model  │    │   ScyllaDB Messages    │          │   │
│  │  │ (Updated by Worker)    │    │   (Chat domain)        │          │   │
│  │  └────────────────────────┘    └────────────────────────┘          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Projection Types

### @sync_projection (Server-Side)

**When:** Executes on SERVER before HTTP response is sent.

**Characteristics:**
- Blocking - client waits
- Immediate consistency
- Timeout enforced (default 2.0s)
- Used for critical user-facing operations

**Example Events:**
- `UserAccountCreated` - User must see profile immediately after registration
- `CompanyCreated` - Saga needs company in read model for next step
- `ChatCreated` - Chat must be visible immediately
- `MessageSent` - Message must appear in chat instantly

### @async_projection (Worker-Side)

**When:** Executes on WORKER via Kafka after response is sent.

**Characteristics:**
- Non-blocking - response returns immediately
- Eventual consistency (typically < 100ms)
- No timeout - Worker manages execution
- Used for non-critical operations

**Example Events:**
- `CompanyUpdated` - UI uses optimistic update
- `MessageEdited` - Edit can propagate async
- `UserPasswordChanged` - No immediate UI feedback needed
- `CompanyBalanceUpdated` - Financial transactions (tracked, but async OK)

## Domain Statistics

| Domain | SYNC | ASYNC | Total | Kafka Topic |
|--------|------|-------|-------|-------------|
| User Account | 8 | 15 | 23 | `transport.user-account-events` |
| Company | 2 | 12 | 14 | `transport.company-events` |
| Chat | 4 | 12 | 16 | `transport.chat-events` |
| **TOTAL** | **14** | **39** | **53** | - |

## Key Components

### 1. projector_decorators.py

Location: `app/infra/cqrs/projector_decorators.py`

```python
# Decorator definitions
@sync_projection(event_type, timeout=2.0, priority=10)
@async_projection(event_type, priority=10)

# Execution functions
execute_sync_projections(envelope, projector_instances)
execute_async_projections(envelope, projector_instances)

# Registry functions
get_all_sync_events() -> Set[str]
get_all_async_events() -> Set[str]
has_sync_handler(event_type) -> bool
has_async_handler(event_type) -> bool
```

### 2. Domain Projectors

```python
# app/company/projectors.py
class CompanyProjector:
    @sync_projection("CompanyCreated")  # Saga dependency
    async def on_company_created(self, envelope): ...

    @async_projection("CompanyUpdated")  # UI optimistic
    async def on_company_updated(self, envelope): ...
```

### 3. Event Processor (Worker)

Location: `app/infra/worker_core/event_processor/event_processor.py`

```python
# Fallback chain: SYNC → ASYNC → legacy
result = await execute_sync_projections(envelope, projector_instances)

if result.get('handlers_executed', 0) == 0:
    async_result = await execute_async_projections(envelope, projector_instances)

    if async_result.get('handlers_executed', 0) == 0:
        # Legacy fallback
        await projector.handle_event(event_dict)
```

## Error Handling

### SYNC Projection Errors

1. Error logged with full traceback
2. Metrics tracked via `_track_error()`
3. Response NOT blocked (graceful degradation)
4. Event still published to Kafka for ASYNC retry

### ASYNC Projection Errors

1. Error logged with full traceback
2. Metrics tracked
3. **Exception re-raised** for Worker retry
4. After max retries → Dead Letter Queue (DLQ)

```python
# projector_decorators.py line 351
except Exception as e:
    log.error(error_msg, exc_info=True)
    _track_error(event_type)
    raise  # Re-raise for Worker retry mechanism
```

## Idempotency Pattern

All projections use `ON CONFLICT` for safe replay:

```sql
-- Insert or update pattern
INSERT INTO companies (id, name, created_at)
VALUES ($1, $2, $3)
ON CONFLICT (id) DO NOTHING;

-- Upsert pattern
INSERT INTO user_companies (user_id, company_id, role)
VALUES ($1, $2, $3)
ON CONFLICT (user_id, company_id) DO UPDATE SET role = EXCLUDED.role;
```

## Monitoring

### Health Endpoint

```json
GET /health

{
  "sync_projections": {
    "metrics": {
      "sync": { "event_types": 14, "total_handlers": 14 },
      "async": { "event_types": 39, "total_handlers": 39 }
    },
    "status": "enabled"
  }
}
```

### Metrics Functions

```python
from app.infra.cqrs.projector_decorators import get_sync_projection_metrics

metrics = get_sync_projection_metrics()
# {
#   "sync": { "event_types": 14, "domains": ["user_account", "company", "chat"] },
#   "async": { "event_types": 39, "domains": ["user_account", "company", "chat"] },
#   "performance": { "UserAccountCreated": { "avg_ms": 15.2, "p95_ms": 45.0 } },
#   "errors": {}
# }
```

## Best Practices

1. **Always use explicit decorators** - no implicit routing
2. **SYNC for user-facing operations** - immediate feedback
3. **ASYNC for background operations** - eventual consistency OK
4. **Idempotent handlers** - use `ON CONFLICT`
5. **Short timeouts for SYNC** - 2.0s default, max 5.0s
6. **Monitor error rates** - alert on elevated errors
7. **Test both paths** - SYNC server + ASYNC worker

## Related Documentation

- [PROJECTION_DECORATORS.md](../reference/PROJECTION_DECORATORS.md) - Decorator API reference
- [PROJECTION_SYSTEM.md](../reference/PROJECTION_SYSTEM.md) - Full system documentation
- [01_DOMAIN_CREATION_GUIDE.md](../reference/01_DOMAIN_CREATION_GUIDE.md) - How to create domains
- [SYNC_VS_ASYNC_EVENTS.md](../reference/SYNC_VS_ASYNC_EVENTS.md) - Decision guide
