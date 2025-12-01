# TradeCore Projection System Architecture

## Overview

TradeCore uses a dual-decorator projection system where methods must be explicitly marked as either `@sync_projection` (server-side, blocking) or `@async_projection` (worker-side, non-blocking).

**Location:** `app/infra/cqrs/projector_decorators.py`

## Architecture Changes (November 2025)

### File Reorganization

The projection decorator system was reorganized to properly align with CQRS architecture:

| Before | After | Reason |
|--------|-------|--------|
| `app/infra/event_store/sync_decorators.py` | `app/infra/cqrs/projector_decorators.py` | Projections are Query-side of CQRS |
| `app/infra/cqrs/decorators.py` | `app/infra/cqrs/cqrs_decorators.py` | Clarify purpose (command/query handlers) |

### Import Updates

All imports were updated across the codebase:

```python
# OLD (deprecated)
from app.infra.event_store.sync_decorators import sync_projection
from app.infra.cqrs.decorators import command_handler, query_handler

# NEW (current)
from app.infra.cqrs.projector_decorators import sync_projection, async_projection
from app.infra.cqrs.cqrs_decorators import command_handler, query_handler
```

### Bug Fix: Dead Code Prevention

**Problem:** Methods without `@sync_projection` decorator were never executed (dead code).

**Root Cause:** `handle_event()` routing only checked for `_is_sync_projection` attribute.

**Solution:** Added `@async_projection` decorator for explicit async registration.

## Decorator Registration

### @sync_projection

```python
from app.infra.cqrs.projector_decorators import sync_projection

@sync_projection(
    "OrderPlacedEvent",      # Event type to handle
    timeout=2.0,              # Max execution time (default: 2.0s)
    priority=1,               # Execution order (lower = first)
    description="Update orders table"
)
async def on_order_placed(self, envelope: EventEnvelope) -> None:
    # Executed on SERVER before response
    ...
```

### @async_projection

```python
from app.infra.cqrs.projector_decorators import async_projection

@async_projection(
    "AccountDiscoveryCompleted",  # Event type to handle
    priority=15,                   # Execution order
    description="Update account metrics"
)
async def on_account_discovery_completed(self, envelope: EventEnvelope) -> None:
    # Executed by WORKER asynchronously
    ...
```

## TradeCore Domain Classification

### SYNC Projections (Server-Side, Blocking)

| Domain | Events | Reason |
|--------|--------|--------|
| **order** | OrderPlaced, OrderFilled, OrderCancelled, OrderRejected, OrderExpired, OrderPending, OrderPartiallyFilled | Trading state machine - user must see immediately |
| **broker_connection** | TokensStored, ConnectionEstablished, ConnectionDisconnected | OAuth/Auth flow - must complete before redirect |
| **user_account** | UserCreated, UserDeleted, UserUpdated | Auth critical - affects login/permissions |
| **broker_account** | AccountLinked, BalanceUpdated | Balance accuracy for trading |
| **position** | PositionOpened, PositionClosed, PositionUpdated | P&L accuracy critical |

### ASYNC Projections (Worker-Side, Non-Blocking)

| Domain | Events | Reason |
|--------|--------|--------|
| **broker_account** | AccountDiscoveryCompleted, BulkArchiveCompleted | Notifications, eventual consistency OK |
| **broker_connection** | HealthChecked, StatusReset | Monitoring, not user-facing |
| **position** | PnLUpdated, MetricsUpdated | Non-critical aggregations |
| **portfolio** | All portfolio events | Historical/reporting data |
| **automation** | All automation events | Workflow triggers, can be eventual |

## Execution Flow

```
                    SERVER (Write Side)
                           |
    Command --> Handler --> Aggregate --> Event
                                           |
                           +---------------+---------------+
                           |                               |
                           v                               v
                   @sync_projection               Publish to Kafka
                   (blocking, timeout)                     |
                           |                               |
                           v                               |
                   [Read Model Updated]                    |
                           |                               |
                           v                               |
                      Response                             |
                                                           |
                    WORKER (Read Side) <-------------------+
                           |
                           v
                   @async_projection
                   (non-blocking)
                           |
                           v
                   [Read Model Updated]
```

## File Structure

```
app/infra/cqrs/
├── projector_decorators.py    # @sync_projection, @async_projection
├── cqrs_decorators.py         # @command_handler, @query_handler
├── command_bus.py             # Command routing
└── query_bus.py               # Query routing

app/{domain}/
└── projectors.py              # Domain projectors with decorators
```

## Implementation Details

### Global Registries

```python
# In projector_decorators.py
_SYNC_PROJECTION_HANDLERS: Dict[str, List[ProjectionHandler]] = {}
_ASYNC_PROJECTION_HANDLERS: Dict[str, List[ProjectionHandler]] = {}
```

### Handler Metadata

```python
@dataclass
class ProjectionHandler:
    handler_func: Callable[[Any, EventEnvelope], Awaitable[None]]
    event_type: str
    domain: str
    projector_class: Optional[Type] = None
    method_name: Optional[str] = None
    timeout: float = 2.0        # Only for sync
    priority: int = 10
    description: Optional[str] = None
    module: Optional[str] = None
```

### Execution Functions

```python
# Execute sync projections (server-side)
result = await execute_sync_projections(
    envelope=event_envelope,
    projector_instances={"order": order_projector, ...},
    timeout_override=None
)

# Execute async projections (worker-side)
result = await execute_async_projections(
    envelope=event_envelope,
    projector_instances={"order": order_projector, ...}
)
```

### Query Functions

```python
# Get all registered sync event types
sync_events = get_all_sync_events()  # Returns Set[str]

# Get all registered async event types
async_events = get_all_async_events()  # Returns Set[str]

# Get performance metrics
metrics = get_sync_projection_metrics()

# Get handler info
handlers = get_sync_handlers("OrderPlacedEvent")
```

## Idempotency Pattern

All TradeCore projections use `ON CONFLICT` for idempotency:

```python
@sync_projection("OrderPlacedEvent", priority=1)
async def on_order_placed(self, envelope: EventEnvelope) -> None:
    await self.pg.execute(
        """
        INSERT INTO orders (id, user_id, symbol, status, created_at)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            updated_at = NOW()
        """,
        envelope.aggregate_id,
        envelope.event_data["user_id"],
        envelope.event_data["symbol"],
        "pending",
        envelope.timestamp
    )
```

**Why Idempotency:**
1. Server sync projection + Worker async may both execute
2. Worker retry on failure
3. Projection rebuild replays all events
4. Kafka at-least-once delivery

## Worker Integration

### event_processor.py

```python
async def process_event(self, event_dict: Dict[str, Any]) -> None:
    envelope = EventEnvelope.from_partial_data(event_dict)

    # Check for sync projections (fallback execution)
    sync_result = await execute_sync_projections(
        envelope, self.projector_instances
    )

    # Execute async projections
    async_result = await execute_async_projections(
        envelope, self.projector_instances
    )

    # Fall back to handle_event() for legacy/undecorated methods
    if sync_result["handlers_executed"] == 0 and async_result["handlers_executed"] == 0:
        projector = self.projector_instances.get(domain)
        if projector and hasattr(projector, "handle_event"):
            await projector.handle_event(event_dict)
```

## Monitoring

### Performance Metrics

```python
metrics = get_sync_projection_metrics()
# Returns:
{
    "total_event_types": 48,
    "total_handlers": 65,
    "domains": ["order", "position", "broker_account", ...],
    "performance": {
        "OrderPlacedEvent": {
            "avg_ms": 12.5,
            "min_ms": 8.2,
            "max_ms": 45.1,
            "p95_ms": 23.4,
            "samples": 100
        }
    },
    "errors": {
        "PositionClosedEvent": 2
    }
}
```

### Timeout Warnings

Logged when execution approaches timeout:

```
WARNING: Sync projection on_order_placed for OrderPlacedEvent took 1.8s (close to timeout 2.0s)
```

### Error Tracking

```python
_PROJECTION_ERRORS: Dict[str, int] = {}  # Event type -> error count
```

## Migration Checklist

When adding new projection methods:

1. Choose decorator based on decision matrix:
   - User expects immediate feedback? -> `@sync_projection`
   - Trading/financial accuracy? -> `@sync_projection`
   - Notifications/analytics? -> `@async_projection`

2. Add decorator with appropriate parameters:
   ```python
   @sync_projection("MyEvent", priority=5, timeout=2.0)
   async def on_my_event(self, envelope: EventEnvelope) -> None:
       ...
   ```

3. Implement idempotent database operations:
   ```python
   ON CONFLICT (id) DO UPDATE SET ...
   -- or --
   ON CONFLICT (id) DO NOTHING
   ```

4. Test projection execution:
   ```python
   # Verify registration
   from app.infra.cqrs.projector_decorators import get_all_sync_events
   assert "MyEvent" in get_all_sync_events()
   ```

## Removed/Deprecated

### Removed Files

- `app/infra/event_store/sync_decorators.py` - Moved to `cqrs/projector_decorators.py`
- `app/{domain}/sync_events.py` - No longer needed (decorators are source of truth)

### Removed Functions

- `load_domain_sync_events()` in `domain_registry.py` - Dead code, tried to import non-existent files

### Removed Topics

- `transport.admin-events` from worker subscription - No handler existed, caused DLQ noise

## Troubleshooting

### Projection Not Executing

1. Check decorator is present:
   ```python
   # Verify method has decorator
   print(hasattr(method, '_is_sync_projection'))
   print(hasattr(method, '_is_async_projection'))
   ```

2. Check event type matches exactly:
   ```python
   # Event type is case-sensitive
   @sync_projection("OrderPlacedEvent")  # CORRECT
   @sync_projection("orderPlacedEvent")  # WRONG
   ```

3. Check projector instance is registered:
   ```python
   # In domain_registry.py
   projector_instances = {"order": OrderProjector(), ...}
   ```

### Timeout Errors

1. Increase timeout for slow operations:
   ```python
   @sync_projection("HeavyEvent", timeout=5.0)
   ```

2. Move to async if not time-critical:
   ```python
   @async_projection("HeavyEvent")  # No timeout enforced
   ```

### Dead Code Detection

Run validation to check for undecorated methods:

```python
from app.infra.cqrs.projector_decorators import validate_sync_projections

issues = validate_sync_projections()
print(issues["performance_warnings"])
```

## Related Documentation

- `docs/reference/PROJECTION_DECORATORS.md` - Generic decorator reference
- `docs/mvp/DOMAIN_CREATION_TEMPLATE.md` - Domain creation guide
- `docs/reference/PROJECTOR_GUIDE.md` - Projector patterns
