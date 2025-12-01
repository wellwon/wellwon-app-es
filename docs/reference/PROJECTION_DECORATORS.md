# Projection Decorators: @sync_projection vs @async_projection

## Overview

Explicit decorators for controlling projection execution timing in CQRS/Event Sourcing systems. This dual-decorator pattern follows industry best practices from frameworks like Marten (C#), Axon Framework (Java), and Ecotone (PHP).

## The Problem

Without explicit decorator marking, projection methods can become "dead code" - methods that exist in projector classes but are never executed because the routing system doesn't know about them.

**Common Anti-Pattern (Implicit Routing):**
```python
class OrderProjector:
    async def on_order_placed(self, event):  # NEVER CALLED - no decorator
        await self.update_read_model(event)
```

**Solution (Explicit Registration):**
```python
class OrderProjector:
    @sync_projection("OrderPlacedEvent")  # Explicitly registered
    async def on_order_placed(self, envelope):
        await self.update_read_model(envelope)
```

## Decorators

### @sync_projection

Executes projection **synchronously** on the server before returning response to client.

**Characteristics:**
- Blocking - client waits for projection to complete
- Immediate consistency - read model updated before response
- Timeout enforced (default: 2.0 seconds)
- Priority-ordered execution

**Syntax:**
```python
@sync_projection(
    event_type: str,           # Required: Event type to handle
    timeout: float = 2.0,      # Max execution time (seconds)
    priority: int = 10,        # Lower = higher priority
    description: str = None    # Documentation
)
```

**Use Cases:**
- Order state changes (user must see immediately)
- Authentication/OAuth flows (must complete before redirect)
- Balance updates (trading accuracy critical)
- Position open/close (P&L accuracy critical)
- Any operation where user expects immediate feedback

### @async_projection

Executes projection **asynchronously** by background worker process.

**Characteristics:**
- Non-blocking - response returns immediately
- Eventual consistency - read model updated "soon"
- No timeout (worker manages execution)
- Priority-ordered execution

**Syntax:**
```python
@async_projection(
    event_type: str,           # Required: Event type to handle
    priority: int = 10,        # Lower = higher priority
    description: str = None    # Documentation
)
```

**Use Cases:**
- Notifications/alerts
- Analytics and metrics aggregation
- Historical data snapshots
- Audit logging
- Report generation
- Non-critical cache updates

## Example Usage

```python
from app.infra.cqrs.projector_decorators import sync_projection, async_projection

class OrderProjector:
    """Projector for Order domain read models."""

    # SYNC: User expects immediate order confirmation
    @sync_projection("OrderPlacedEvent", priority=1, timeout=2.0)
    async def on_order_placed(self, envelope: EventEnvelope) -> None:
        """Update orders table immediately - user waiting for confirmation."""
        await self.pg.execute(
            """
            INSERT INTO orders (id, symbol, side, quantity, status, placed_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                placed_at = EXCLUDED.placed_at
            """,
            envelope.aggregate_id,
            envelope.event_data["symbol"],
            envelope.event_data["side"],
            envelope.event_data["quantity"],
            "pending",
            envelope.timestamp
        )

    # SYNC: Critical for order tracking
    @sync_projection("OrderFilledEvent", priority=1, timeout=2.0)
    async def on_order_filled(self, envelope: EventEnvelope) -> None:
        """Update order status to filled - affects trading state."""
        await self.pg.execute(
            """
            UPDATE orders SET status = 'filled', filled_at = $2, fill_price = $3
            WHERE id = $1
            """,
            envelope.aggregate_id,
            envelope.timestamp,
            envelope.event_data["fill_price"]
        )

    # ASYNC: Metrics can be eventually consistent
    @async_projection("OrderPlacedEvent", priority=15)
    async def update_order_metrics(self, envelope: EventEnvelope) -> None:
        """Aggregate order statistics - not time-sensitive."""
        await self.pg.execute(
            """
            INSERT INTO order_metrics (date, symbol, order_count)
            VALUES (CURRENT_DATE, $1, 1)
            ON CONFLICT (date, symbol) DO UPDATE SET
                order_count = order_metrics.order_count + 1
            """,
            envelope.event_data["symbol"]
        )

    # ASYNC: Historical snapshots
    @async_projection("DayClosedEvent")
    async def snapshot_daily_orders(self, envelope: EventEnvelope) -> None:
        """Create daily order snapshot for reporting."""
        await self.create_daily_snapshot(envelope.event_data["date"])
```

## Decision Matrix: When to Use SYNC vs ASYNC

| Criteria | @sync_projection | @async_projection |
|----------|-----------------|-------------------|
| User expects immediate feedback | YES | NO |
| Trading/financial accuracy | YES | NO |
| Authentication/OAuth flow | YES | NO |
| Order state machine | YES | NO |
| Position changes | YES | NO |
| Balance updates | YES | NO |
| Notifications | NO | YES |
| Analytics/metrics | NO | YES |
| Historical data | NO | YES |
| Audit logging | NO | YES |
| Report generation | NO | YES |
| Cache warming | NO | YES |

## Architecture

### Execution Flow

```
                        SERVER                              WORKER
                          |                                   |
Command --> Handler --> Event --> @sync_projection            |
                          |            |                      |
                          |       (blocking)                  |
                          |            |                      |
                          |            v                      |
                          |     [Read Model Updated]          |
                          |            |                      |
                          v            v                      |
                      Response --> Publish to Kafka --------> |
                                                              v
                                                   @async_projection
                                                              |
                                                         (non-blocking)
                                                              |
                                                              v
                                                     [Read Model Updated]
```

### Component Responsibilities

**projector_decorators.py** (CQRS layer):
- `@sync_projection` decorator - marks methods for synchronous execution
- `@async_projection` decorator - marks methods for asynchronous execution
- `execute_sync_projections()` - runs sync projections with timeout
- `execute_async_projections()` - runs async projections
- `get_all_sync_events()` - returns set of sync event types
- `get_all_async_events()` - returns set of async event types
- Global registries: `_SYNC_PROJECTION_HANDLERS`, `_ASYNC_PROJECTION_HANDLERS`

**event_processor.py** (Worker layer):
- Consumes events from Kafka
- Calls `execute_async_projections()` for registered async events
- Falls back to `handle_event()` for undecorated methods (legacy support)

## Idempotency Requirement

**CRITICAL:** All projections MUST be idempotent using database constraints.

```python
# CORRECT: Idempotent with ON CONFLICT
await pg.execute(
    """
    INSERT INTO orders (id, status) VALUES ($1, $2)
    ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status
    """,
    order_id, status
)

# WRONG: Not idempotent - will fail on replay
await pg.execute(
    "INSERT INTO orders (id, status) VALUES ($1, $2)",
    order_id, status
)
```

**Why Idempotency Matters:**
1. Events may be replayed during projection rebuilds
2. Worker may process same event twice (at-least-once delivery)
3. Server sync projection + worker async projection may both run
4. System recovery requires safe re-execution

## Best Practices

### 1. Explicit Over Implicit

Always use decorators - never rely on naming conventions or implicit routing.

```python
# BAD: Implicit routing based on method name
async def on_user_created(self, event): ...

# GOOD: Explicit decorator registration
@sync_projection("UserCreatedEvent")
async def on_user_created(self, envelope): ...
```

### 2. One Event, Multiple Projections

An event can have both sync and async projections:

```python
# SYNC: Update user table immediately
@sync_projection("UserCreatedEvent", priority=1)
async def create_user_record(self, envelope): ...

# ASYNC: Send welcome notification later
@async_projection("UserCreatedEvent", priority=20)
async def send_welcome_notification(self, envelope): ...
```

### 3. Priority Guidelines

| Priority Range | Use Case |
|---------------|----------|
| 1-5 | Critical state changes (orders, auth) |
| 6-10 | Standard domain projections |
| 11-15 | Secondary updates (metrics, cache) |
| 16-20 | Background tasks (notifications, reports) |

### 4. Timeout Guidelines for @sync_projection

| Operation Type | Recommended Timeout |
|---------------|-------------------|
| Simple UPDATE | 1.0s |
| INSERT with constraints | 2.0s |
| Multi-table transaction | 3.0s |
| External API call | 5.0s (avoid in sync) |

### 5. Error Handling

Sync projections with errors will:
- Log the error
- Track in error metrics
- NOT block the response (graceful degradation)
- Worker will retry via async fallback

## Migration Guide

### From Implicit to Explicit

**Before (dead code risk):**
```python
class UserProjector:
    async def handle_event(self, event_dict):
        event_type = event_dict.get("event_type")
        if event_type == "UserCreatedEvent":
            await self.on_user_created(event_dict)

    async def on_user_created(self, event):  # May be dead code
        ...
```

**After (explicit registration):**
```python
class UserProjector:
    @sync_projection("UserCreatedEvent")
    async def on_user_created(self, envelope: EventEnvelope):
        ...

    @async_projection("UserLoginEvent")
    async def on_user_login(self, envelope: EventEnvelope):
        ...
```

### Classification Process

1. List all projection methods in each projector
2. Classify each as SYNC or ASYNC based on decision matrix
3. Add appropriate decorator
4. Test projection execution
5. Monitor for dead code warnings

## Validation Tools

```python
from app.infra.cqrs.projector_decorators import (
    get_all_sync_events,
    get_all_async_events,
    get_sync_projection_metrics,
    validate_sync_projections
)

# Get all registered event types
sync_events = get_all_sync_events()
async_events = get_all_async_events()

# Check for performance issues
metrics = get_sync_projection_metrics()
for event_type, stats in metrics["performance"].items():
    if stats["avg_ms"] > 500:
        print(f"WARNING: {event_type} avg {stats['avg_ms']:.0f}ms")

# Validate configuration
issues = validate_sync_projections()
if issues["performance_warnings"]:
    print("Performance warnings:", issues["performance_warnings"])
```

## WellWon Implementation Statistics

**Last Updated:** 2025-12-01 (Optimized)

### Domain Breakdown

| Domain | @sync_projection | @async_projection | Total |
|--------|-----------------|-------------------|-------|
| **User Account** | 7 | 16 | 23 |
| **Company** | 0 | 14 | 14 |
| **Chat** | 4 | 12 | 16 |
| **TOTAL** | **11** | **42** | **53** |

**SYNC Ratio:** 21% (industry standard: 10-20%)

### Key Files

```
app/infra/cqrs/projector_decorators.py    # Decorator definitions
app/infra/cqrs/cqrs_decorators.py         # Command/Query decorators
app/user_account/projectors.py            # User Account projections
app/company/projectors.py                 # Company projections
app/chat/projectors.py                    # Chat projections
```

### Worker Event Flow

```
Kafka Topic (transport.*)
         ↓
ConsumerManager (consumer_manager.py)
         ↓
EventProcessor (event_processor.py)
         ↓
execute_sync_projections()  ← Try SYNC first
         ↓
[If no SYNC handlers]
         ↓
execute_async_projections() ← Then ASYNC
         ↓
[If no ASYNC handlers]
         ↓
handle_event() legacy fallback
```

### TopicConfig

```python
# eventbus_transport_config.py
"transport.user-account-events" → event-processor-workers
"transport.company-events"      → event-processor-workers
"transport.chat-events"         → event-processor-workers
```

## References

- **Python eventsourcing library**: Uses `@subscribe_to()` decorator pattern
- **Marten (C#)**: Explicit `Inline` vs `Async` lifecycle configuration
- **Axon Framework (Java)**: Defaults to async, explicit override for sync
- **Ecotone (PHP)**: "By default, projections work synchronously... switch to Asynchronous"
- **Python Zen**: "Explicit is better than implicit"
- **Greg Young**: Event Sourcing - Projection patterns
- **Confluent**: Kafka consumer best practices
