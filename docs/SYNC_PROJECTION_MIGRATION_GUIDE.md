# Sync Projection Migration Guide

**Last Updated**: November 19, 2025
**Status**: Production-Ready Pattern

## Overview

This guide explains how to migrate from file-based sync event configuration (`sync_events.py`) to decorator-based sync projection discovery (`@sync_projection`).

## Why Migrate?

**Old Pattern (Deprecated)**:
- Manually maintain `sync_events.py` files in each domain
- Duplicate configuration (decorators + files)
- Import errors if files don't exist
- Manual registry management
- Easy to get out of sync

**New Pattern (Current)**:
- Single source of truth: `@sync_projection` decorator
- Auto-discovery at runtime
- No manual configuration files needed
- Import-time registration
- Type-safe and maintainable

## Architecture Pattern

### Event Processing Flow

```
Event Published
     ↓
EventBus Transport (Kafka/Redpanda)
     ↓
     ├─→ SYNC Projection (immediate, @sync_projection)
     │   ├─ Execute within milliseconds
     │   ├─ Critical read model updates
     │   └─ Return to event flow
     ↓
     └─→ ASYNC Worker (delayed, EventProcessorWorker)
         ├─ Process non-critical projections
         ├─ Skip already-handled sync events
         └─ Update secondary read models
```

### Key Concepts

1. **Sync Projections**: Immediate event processing for critical read models
2. **Decorator Registration**: Events marked with `@sync_projection` are auto-discovered
3. **Worker Skip Logic**: Async worker skips events already handled by sync projections
4. **Single Source of Truth**: Decorators define which events are sync

## Migration Steps

### Step 1: Add Module-Level Import to Domain Registry

In your domain registry file (e.g., `domain_registry.py`):

```python
# Add this import at the top
from app.infra.event_store.sync_decorators import get_all_sync_events
```

### Step 2: Replace File-Based Loading

**BEFORE (Old Pattern)**:
```python
def create_my_domain() -> DomainRegistration:
    # ... domain setup ...

    # Load sync events from sync_events.py file
    sync_events, sync_event_config = load_domain_sync_events("my_domain")

    return DomainRegistration(
        name="my_domain",
        sync_events=sync_events,
        sync_event_config=sync_event_config,
        # ... other config ...
    )
```

**AFTER (New Pattern)**:
```python
def create_my_domain() -> DomainRegistration:
    # ... domain setup ...

    # SYNC events are auto-discovered from @sync_projection decorators
    sync_events = get_all_sync_events()
    sync_event_config = {}

    return DomainRegistration(
        name="my_domain",
        sync_events=sync_events,
        sync_event_config=sync_event_config,
        # ... other config ...
    )
```

### Step 3: Delete Deprecated Files

Remove all `sync_events.py` files from your domains:

```bash
# Example cleanup
rm app/user_account/sync_events.py
rm app/broker_account/sync_events.py
rm app/order/sync_events.py
# ... etc for all domains
```

### Step 4: Verify Decorator Usage

Ensure your projectors use the `@sync_projection` decorator:

```python
# In app/my_domain/projectors.py

from app.infra.event_store.sync_decorators import sync_projection

class MyProjector:

    @sync_projection("MyEventType", priority=1, timeout=1.0)
    async def on_my_event(self, envelope: EventEnvelope) -> None:
        """
        SYNC projection: Handle MyEventType immediately

        This event will be:
        1. Processed immediately when published
        2. Skipped by async EventProcessorWorker
        3. Auto-discovered by domain registry
        """
        event_data = envelope.event_data
        # ... projection logic ...
```

### Step 5: Remove Deprecated Helper Function (Optional)

If no code uses `load_domain_sync_events()`, you can remove or deprecate it:

```python
# Option 1: Remove entirely
# Delete the load_domain_sync_events() function

# Option 2: Mark deprecated
@deprecated("Use @sync_projection decorators instead of sync_events.py files")
def load_domain_sync_events(domain_name: str) -> tuple[Set[str], Dict[str, Dict[str, Any]]]:
    """DEPRECATED: Use decorator-based sync projection discovery"""
    return set(), {}
```

## Decorator Reference

### Basic Usage

```python
@sync_projection("EventType", priority=1, timeout=1.0)
async def on_event(self, envelope: EventEnvelope) -> None:
    """Handle event synchronously"""
    pass
```

### Parameters

- **event_type** (str): Event type to handle (e.g., "OrderSyncedFromBrokerEvent")
- **priority** (int): Execution priority (1=highest, 10=normal, 20=low)
- **timeout** (float): Max execution time in seconds (default: 1.0)

### Priority Guidelines

- **Priority 1**: Critical data integrity (order status, positions)
- **Priority 5**: Important updates (account balances)
- **Priority 10**: Standard projections (user data)
- **Priority 15**: Low priority (analytics, reporting)

## Auto-Discovery Mechanism

### How It Works

1. **Import Time**: When projector module is imported, decorators register events
2. **Registry Lookup**: `get_all_sync_events()` returns all registered event types
3. **Worker Check**: EventProcessorWorker calls `is_sync_event()` before processing
4. **Skip Logic**: If event is sync, worker skips it (already handled)

### Registration Flow

```python
# 1. Decorator applied at module import
@sync_projection("MyEvent")
async def on_my_event(...):
    pass

# 2. Decorator registers event in global registry
_SYNC_PROJECTION_HANDLERS["MyEvent"] = handler_info

# 3. Domain registry queries all sync events
sync_events = get_all_sync_events()  # Returns: {"MyEvent", "OtherEvent", ...}

# 4. Worker checks before processing
if domain_registry.is_sync_event("MyEvent"):
    log.debug("Skipping MyEvent - already handled by sync projection")
    return  # Skip async processing
```

## Testing Migration

### Verification Checklist

- [ ] All `sync_events.py` files deleted
- [ ] All domain factory functions use `get_all_sync_events()`
- [ ] No import errors when loading domain registry
- [ ] Server starts without errors
- [ ] EventProcessorWorker skips sync events correctly
- [ ] Sync projections execute within timeout limits

### Test Sync Event Discovery

```python
# In your test file
from app.infra.event_store.sync_decorators import get_sync_projection_events
from app.infra.worker_core.event_processor.domain_registry import DOMAIN_REGISTRY

def test_sync_events_auto_discovered():
    """Verify sync events are auto-discovered from decorators"""
    sync_events = get_all_sync_events()

    # Check expected sync events are registered
    assert "OrderSyncedFromBrokerEvent" in sync_events
    assert "PositionReconciledEvent" in sync_events

    # Verify domain registry knows about them
    assert DOMAIN_REGISTRY.is_sync_event("OrderSyncedFromBrokerEvent")
```

### Monitor Worker Logs

Look for these log messages after migration:

```
✓ GOOD:
[EventProcessorWorker] Skipping sync event: OrderSyncedFromBrokerEvent (already handled)
[EventProcessorWorker] Processing async event: OrderCompletedEvent

✗ BAD (indicates migration incomplete):
[EventProcessorWorker] ERROR: No domain could process event type 'OrderSyncedFromBrokerEvent'
```

## Common Issues

### Issue 1: Import Errors After Deleting Files

**Symptom**: `ModuleNotFoundError: No module named 'app.my_domain.sync_events'`

**Cause**: Code still tries to import deleted `sync_events.py`

**Fix**: Search codebase for `from app.*.sync_events import` and remove/update

### Issue 2: Events Processed Twice

**Symptom**: Same event processed by both sync projection and async worker

**Cause**: Worker doesn't know event is sync (decorator not imported)

**Fix**: Ensure projector module is imported in domain factory function:

```python
def order_projector_factory():
    # Import the full module to register decorators
    import app.order.projectors
    from app.order.projectors import OrderProjector
    # ...
```

### Issue 3: Empty Sync Events Set

**Symptom**: `get_all_sync_events()` returns empty set

**Cause**: Projector modules not imported yet when registry is created

**Fix**: Import projector modules in domain factory functions (see Issue 2)

### Issue 4: Sync Events Not Skipped by Worker

**Symptom**: Worker still processes sync events instead of skipping

**Cause**: Domain registration still uses old file-based loading

**Fix**: Replace `load_domain_sync_events()` with decorator pattern (Step 2)

## Performance Considerations

### Benefits

- **Faster Startup**: No file I/O for sync event config
- **Type Safety**: Decorators are checked at import time
- **Memory Efficiency**: Single registry, no duplicate config
- **Maintainability**: One place to change sync behavior

### Metrics to Monitor

```python
# Sync projection execution time
sync_projection_duration_ms: histogram(1-1000ms)

# Worker skip rate
worker_events_skipped_total: counter(by event_type)

# Async processing lag
async_projection_lag_ms: histogram(0-5000ms)
```

## Best Practices

### 1. Import Projector Modules in Factory Functions

```python
def create_order_domain() -> DomainRegistration:
    def order_projector_factory():
        # Import full module to trigger decorator registration
        import app.order.projectors
        from app.order.projectors import OrderProjector

        # Create projector instance
        return OrderProjector(...)

    # Now decorators are registered
    sync_events = get_all_sync_events()
    # ...
```

### 2. Keep Sync Projections Fast

```python
@sync_projection("MyEvent", timeout=1.0)  # Max 1 second
async def on_my_event(self, envelope: EventEnvelope):
    # GOOD: Simple database update
    await self.db.execute("UPDATE orders SET status = $1 WHERE id = $2", ...)

    # BAD: Heavy computation (use async worker instead)
    # await self.generate_report()  # DON'T DO THIS
```

### 3. Use Appropriate Priorities

```python
# Priority 1: Data integrity (must execute first)
@sync_projection("OrderFilled", priority=1)

# Priority 5: Important but not critical
@sync_projection("BalanceUpdated", priority=5)

# Priority 10: Standard updates
@sync_projection("UserProfileChanged", priority=10)
```

### 4. Document Sync Projections

```python
@sync_projection("OrderSyncedFromBrokerEvent", priority=1, timeout=1.0)
@monitor_projection
async def on_order_synced_from_broker(self, envelope: EventEnvelope) -> None:
    """
    Project OrderSyncedFromBrokerEvent → Update order from broker sync

    SYNC: This projection runs immediately to ensure order status is current

    Updates: status, filled_quantity, average_fill_price, broker timestamps
    Priority: 1 (critical for order lifecycle)
    Timeout: 1.0s (simple DB update)
    """
```

## Migration Checklist

### Pre-Migration
- [ ] Identify all `sync_events.py` files in codebase
- [ ] List all decorators using `@sync_projection`
- [ ] Verify decorator imports in projector modules
- [ ] Review current `load_domain_sync_events()` usage

### During Migration
- [ ] Add `get_sync_projection_events` import to domain registry
- [ ] Replace all `load_domain_sync_events()` calls
- [ ] Update all domain factory functions
- [ ] Delete all `sync_events.py` files
- [ ] Remove/deprecate `load_domain_sync_events()` function

### Post-Migration
- [ ] Run all tests (unit + integration)
- [ ] Start server and verify no import errors
- [ ] Check EventProcessorWorker logs for skipped events
- [ ] Monitor sync projection execution times
- [ ] Verify no duplicate event processing
- [ ] Update documentation and code comments

## Further Reading

- `docs/reference/infrastructure/sync_projections.md` - Sync projection patterns
- `docs/reference/domains/event_projectors.md` - Projector architecture
- `EVENT_AUTOREGISTRATION_EXAMPLE.md` - Event auto-registration guide

## Summary

**Before**: Manual `sync_events.py` files + decorators (duplicate config)
**After**: Single source of truth with `@sync_projection` decorators
**Result**: Less code, fewer errors, easier maintenance

The decorator-based pattern is the **recommended approach** for all new domains and existing domains should be migrated to this pattern.
