# SYNC vs ASYNC Events: Decision Guide

**Status**: ✅ Reference Guide
**Last Updated**: 2025-11-10
**Applies To**: TradeCore v0.5+

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Decision Tree](#quick-decision-tree)
3. [SYNC Events (Immediate Consistency)](#sync-events-immediate-consistency)
4. [ASYNC Events (Eventual Consistency)](#async-events-eventual-consistency)
5. [Event Configuration Patterns](#event-configuration-patterns)
6. [Performance Implications](#performance-implications)
7. [Domain Examples](#domain-examples)
8. [Common Pitfalls](#common-pitfalls)

---

## Overview

TradeCore uses a **hybrid event projection strategy**: Most events are processed asynchronously (eventual consistency), but critical events require synchronous projection (immediate consistency).

**Key Principle**: Only make events SYNC if there's a **concrete technical reason** (cross-domain queries, race conditions, user expectations).

### Architecture

```
┌──────────────────────────────────────────────────────┐
│ Command → Aggregate → Event → EventStore            │
└──────────────────────────────────────────────────────┘
                       ↓
      ┌────────────────┴────────────────┐
      ↓                                  ↓
┌─────────────────┐            ┌─────────────────┐
│ SYNC Projection │            │ ASYNC Projection│
│ (< 2s timeout)  │            │ (No timeout)    │
│ Blocks response │            │ Non-blocking    │
└─────────────────┘            └─────────────────┘
```

**SYNC Events:**
- Projection completes BEFORE command handler returns
- Default 2s timeout per event
- Used for ~10-20% of events (critical only)
- Higher latency per command (~500ms-2s)

**ASYNC Events:**
- Projection runs in background workers
- No blocking, no timeout
- Used for ~80-90% of events
- Lowest latency per command (~5-50ms)

---

## Quick Decision Tree

```
START: "Should this event be SYNC?"
    ↓
    Is this event queried by another domain IMMEDIATELY after creation?
    (e.g., Order domain queries BrokerAccount status during order placement)
    │
    ├─ YES → SYNC (Priority 1: Cross-domain validation)
    │
    └─ NO → Continue ↓

    Will a race condition occur if projection is delayed by 100-500ms?
    (e.g., User activates automation, webhook arrives 50ms later)
    │
    ├─ YES → SYNC (Priority 1: Race condition prevention)
    │
    └─ NO → Continue ↓

    Does user expect IMMEDIATE UI feedback on this action?
    (e.g., Create automation, expect immediate webhook URL display)
    │
    ├─ YES → SYNC (Priority 2: User expectation)
    │
    └─ NO → Continue ↓

    Is this event ONLY queried by sagas for coordination?
    │
    ├─ YES → ASYNC (Saga coordination events are ALWAYS async)
    │
    └─ NO → Continue ↓

    Is this event high-frequency (>10/sec) or a notification?
    │
    ├─ YES → ASYNC (Performance optimization)
    │
    └─ NO → ASYNC (Default: eventual consistency is fine)
```

---

## SYNC Events (Immediate Consistency)

### When to Use SYNC

**Priority 1 - CRITICAL (Must be SYNC):**

1. **Cross-domain validation queries**
   - Example: `BrokerAccountLinked` - Order domain queries account status during order placement
   - Pattern: Domain B queries Domain A's read model immediately after Domain A emits event

2. **Race condition prevention**
   - Example: `AutomationActivatedEvent` - Webhook may arrive 50ms after activation
   - Pattern: External system queries state immediately after state change

3. **OAuth callback dependencies**
   - Example: `BrokerConnectionInitiated` - OAuth callback queries connection existence (10s polling)
   - Pattern: External callback loops until state change visible

**Priority 2 - HIGH (Should be SYNC):**

4. **User-initiated state changes (immediate UI feedback)**
   - Example: `DefaultAccountSet` - User expects immediate UI update
   - Pattern: User clicks action, expects instant visual confirmation

5. **Hard deletion events**
   - Example: `BrokerAccountDeleted` - Prevent orphaned foreign key references
   - Pattern: Deletion must cascade before related operations occur

### SYNC Event Characteristics

```python
SYNC_EVENTS = {
    "BrokerAccountLinked",      # Cross-domain: Order validates account
    "AutomationActivatedEvent",  # Race condition: Webhook may arrive immediately
    "BrokerConnectionInitiated", # OAuth callback: 10s polling dependency
}

EVENT_CONFIG = {
    "BrokerAccountLinked": {
        "priority": 1,              # CRITICAL
        "timeout": 2.0,             # Default 2s (sufficient for PG + cache)
        "description": "Cross-domain: Order validates account exists"
    },
    "AutomationActivatedEvent": {
        "priority": 1,              # CRITICAL
        "timeout": 2.0,
        "description": "Race condition: Must be active before webhook arrives"
    },
}
```

### SYNC Event Timeout Guidelines

| Event Type | Timeout | Rationale |
|------------|---------|-----------|
| Simple INSERT | 1.0s | Single DB write + cache update |
| Simple UPDATE | 1.0s | Single DB write + cache update |
| Complex state change | 2.0s | Multiple DB operations + cache invalidation |
| OAuth critical path | 2.0s | External system polling dependency |
| Cross-domain validation | 2.0s | Foreign key validation + index update |

**Rule of Thumb**: Default 2s timeout covers 99.9% of projection operations. Only reduce to 1s for trivial projections (single INSERT).

---

## ASYNC Events (Eventual Consistency)

### When to Use ASYNC

**Always ASYNC:**

1. **Saga coordination events**
   - Example: `AccountDiscoveryStarted`, `AccountDiscoveryCompleted`
   - Reason: Sagas are event-driven (no query_bus dependency since 2025 refactor)

2. **High-frequency updates**
   - Example: `AccountBalanceUpdated` (every trade), `QuoteReceived` (every 100ms)
   - Reason: Would block command response for ~2s per update

3. **Notification events**
   - Example: `OrderFillNotification`, `SignalRejectedEvent`
   - Reason: User doesn't query immediately; eventual delivery is fine

4. **Background operations**
   - Example: `MetricsCalculated`, `CacheWarmed`
   - Reason: No user-facing impact; eventual consistency acceptable

5. **Audit trail events**
   - Example: `WebhookSignalReceivedEvent`, `ConnectionHealthChecked`
   - Reason: Historical logging; no immediate query dependency

### ASYNC Event Characteristics

```python
ASYNC_EVENTS = {
    # Saga coordination (TRUE SAGA pattern)
    "AccountDiscoveryStarted",      # Saga trigger - no query_bus
    "AccountDiscoveryCompleted",    # Saga notification - eventual OK

    # High-frequency updates
    "AccountBalanceUpdated",        # Every trade - eventual OK
    "AccountEquityUpdated",         # Every quote - eventual OK

    # Notifications
    "SignalProcessedEvent",         # Confirmation - eventual OK
    "SignalRejectedEvent",          # Error notification - eventual OK

    # Background operations
    "AccountMetricsCalculated",     # Analytics - eventual OK
    "ConnectionHealthUpdated",      # Monitoring - eventual OK
}
```

### ASYNC Event Benefits

- **Performance**: No blocking (command returns in ~5-50ms)
- **Scalability**: Workers process events in parallel
- **Resilience**: Event replay on worker failure
- **Decoupling**: Domains don't wait for projections

---

## Event Configuration Patterns

### Complete Event Configuration

```python
# app/broker_account/sync_events.py

from typing import Set, Dict, Any

# =========================================================================
# SYNC EVENTS
# =========================================================================

SYNC_EVENTS: Set[str] = {
    # === PRIORITY 1 - CRITICAL (Cross-domain validation) ===
    "BrokerAccountLinked",      # Order/Position validate account exists
    "BrokerAccountUnlinked",    # Cross-domain: Cleanup references

    # === PRIORITY 2 - HIGH (User preferences) ===
    "DefaultAccountSet",        # User queries immediately

    # === PRIORITY 1 - CRITICAL (Hard deletion) ===
    "BrokerAccountDeleted",     # Single account hard delete
}

# =========================================================================
# EVENT CONFIG (Detailed settings)
# =========================================================================

EVENT_CONFIG: Dict[str, Dict[str, Any]] = {
    "BrokerAccountLinked": {
        "priority": 1,
        "timeout": 2.0,
        "description": "Cross-domain: Order/Position validate account",
        "queries_depend_on_this": ["GetBrokerAccountByIdQuery", "ValidateAccountStatusQuery"]
    },
    "DefaultAccountSet": {
        "priority": 2,
        "timeout": 1.0,
        "description": "User queries immediately",
        "ui_blocking": True
    },
    "BrokerAccountDeleted": {
        "priority": 1,
        "timeout": 3.0,  # Longer: CASCADE deletion + cache cleanup
        "description": "Single broker account hard deleted",
        "cascade_operations": ["foreign_key_cleanup", "cache_invalidation"]
    },
}

# =========================================================================
# ASYNC EVENTS
# =========================================================================

ASYNC_EVENTS: Set[str] = {
    # High-frequency updates (eventual consistency OK)
    "AccountBalanceUpdated",      # Every trade/quote
    "AccountEquityUpdated",       # Every quote
    "AccountBuyingPowerUpdated",  # Every quote

    # Saga coordination events (TRUE SAGA pattern)
    "AccountDiscoveryStarted",    # Saga trigger - no query_bus
    "AccountDiscoveryCompleted",  # Saga notification - eventual OK

    # Background operations
    "AccountMetricsCalculated",   # Analytics
    "AccountReconciliationCompleted",  # Background sync
}

# =========================================================================
# CRITICAL SEQUENCES (Document event ordering requirements)
# =========================================================================

CRITICAL_SEQUENCES = [
    # Account linking flow (SYNC required for cross-domain)
    ["BrokerAccountLinked", "Order domain queries account", "ValidateAccountForOrder"],

    # Deletion flow (SYNC required for foreign key integrity)
    ["BrokerAccountDeleted", "Cleanup orphaned orders", "Cleanup orphaned positions"],
]

# =========================================================================
# Auto-registration with decorator system
# =========================================================================

def register_domain_events():
    """Register this domain's sync events with the decorator system"""
    try:
        from app.infra.event_store.sync_decorators import register_domain_sync_events
        register_domain_sync_events("broker_account", SYNC_EVENTS)
    except ImportError:
        pass  # Decorator system not available yet

# Auto-register on import
register_domain_events()
```

### Priority Levels Explained

```python
PRIORITY_LEVELS = {
    1: "CRITICAL - Cross-domain validation, hard deletion, race conditions",
    2: "HIGH - User preferences, immediate UI feedback",
    3: "NORMAL - Important state changes (rarely used)",
}
```

**Priority 1** = Must complete or system breaks (foreign key violations, race conditions)
**Priority 2** = User expects immediate feedback (UI/UX requirement)
**Priority 3** = Nice to have (rarely used; most events are either Priority 1 or ASYNC)

---

## Performance Implications

### Latency Comparison

| Operation | SYNC Projection | ASYNC Projection |
|-----------|----------------|------------------|
| Command execution | 5-50ms | 5-50ms |
| Event emission | 10-20ms | 10-20ms |
| Projection wait | **500ms-2s** (blocking) | 0ms (non-blocking) |
| **Total latency** | **515ms-2.07s** | **15-70ms** |

**Example: Place Order Command**

```python
# SYNC projection (total ~1.5s):
Command: CreateOrderCommand                     # 20ms
  → Aggregate: Order.place_order()              # 10ms
  → Event: OrderPlacedEvent                     # 10ms
  → EventStore: Write to KurrentDB              # 30ms
  → SYNC Projection: Update read model          # 1.2s (BLOCKS!)
  → Cache: Invalidate query cache               # 50ms
  → Response: Return to user                    # 10ms
Total: ~1.5s

# ASYNC projection (total ~70ms):
Command: CreateOrderCommand                     # 20ms
  → Aggregate: Order.place_order()              # 10ms
  → Event: OrderPlacedEvent                     # 10ms
  → EventStore: Write to KurrentDB              # 30ms
  → Response: Return to user immediately        # 10ms
Total: ~70ms
(Worker processes projection in background: +1.2s eventual)
```

### Throughput Impact

**SYNC Events:**
- Max throughput: ~500-1000 commands/sec (limited by projection blocking)
- Database connections: Higher usage (each command holds connection for projection)
- User experience: Slower responses (1-2s per command)

**ASYNC Events:**
- Max throughput: ~5,000-10,000 commands/sec (limited by EventStore only)
- Database connections: Lower usage (workers pool connections)
- User experience: Fast responses (10-100ms per command)

### Database Impact

**SYNC Projection:**
```python
# Command handler connection holds for ENTIRE projection
async def handle_command(command):
    async with pg_pool.acquire() as conn:  # Connection acquired
        aggregate = await load_aggregate(conn)
        aggregate.apply_command(command)
        event = aggregate.pop_uncommitted_events()

        await event_store.append(event)

        # SYNC projection (connection still held!)
        await sync_projection(event, conn)  # 500ms-2s wait

        await conn.commit()  # Connection finally released
    # Total connection hold time: 500ms-2s
```

**ASYNC Projection:**
```python
# Command handler releases connection immediately
async def handle_command(command):
    async with pg_pool.acquire() as conn:  # Connection acquired
        aggregate = await load_aggregate(conn)
        aggregate.apply_command(command)
        event = aggregate.pop_uncommitted_events()

        await event_store.append(event)
        await conn.commit()
    # Connection released (~50ms hold time)

# Worker processes projection later (separate connection)
async def worker_projection(event):
    async with pg_pool.acquire() as conn:
        await project_event(event, conn)
    # Separate connection, no blocking
```

---

## Domain Examples

### Example 1: Broker Connection Domain (4 SYNC events)

**SYNC Events (Critical Only):**

```python
SYNC_EVENTS = {
    # OAuth flow (10s polling dependency)
    "BrokerConnectionInitiated",       # Must exist before OAuth callback
    "BrokerConnectionEstablished",     # OAuth callback queries this
    "BrokerTokensSuccessfullyStored",  # OAuth completed

    # Real-time UI (user action required)
    "BrokerConnectionReauthRequired",  # User must re-authenticate NOW
}
```

**Why SYNC?**
- `BrokerConnectionInitiated`: OAuth callback polls for 10s waiting for this record to exist
- `BrokerConnectionEstablished`: OAuth callback queries connection status immediately
- `BrokerTokensSuccessfullyStored`: Triggers connection flow; must be visible before account discovery
- `BrokerConnectionReauthRequired`: User expects immediate alert (session invalid)

**ASYNC Events (Majority):**

```python
ASYNC_EVENTS = {
    # Moved from SYNC (47 events freed up!)
    "BrokerDisconnected",              # Saga trigger (event-driven, no query)
    "BrokerConnectionPurged",          # Saga cleanup (eventual OK)
    "BrokerConnectionHealthUpdated",   # Monitoring data (eventual OK)
    "BrokerApiCredentialsStored",      # Background credential storage
    # ... 43 more events
}
```

**Impact:** 72% reduction in SYNC events (from 51 to 4)

---

### Example 2: Automation Domain (6 SYNC events, 75% SYNC rate)

**SYNC Events (Race Condition Prevention):**

```python
SYNC_EVENTS = {
    # Lifecycle (race condition with webhooks)
    "AutomationCreatedEvent",      # Webhook URL must be queryable immediately
    "AutomationActivatedEvent",    # MUST prevent race with incoming signals
    "AutomationDeactivatedEvent",  # MUST stop signals immediately (risk mgmt)
    "AutomationSuspendedEvent",    # Emergency stop (risk mgmt)

    # Risk management (safety critical)
    "RiskLimitExceededEvent",      # Critical alert must be visible NOW

    # Cross-domain
    "BrokerAccountDeleted",        # Unbind automation from deleted account
}
```

**Race Condition Scenario (Why SYNC is Critical):**

```
WITHOUT SYNC (BAD):
1. User clicks "Activate" → Command → Event → EventStore
2. ASYNC projection starts (50-500ms delay)
3. TradingView webhook arrives 50ms later           ← Race!
4. Webhook handler queries automation status → INACTIVE (projection not done)
5. Signal REJECTED incorrectly ❌

WITH SYNC (GOOD):
1. User clicks "Activate" → Command → Event → EventStore
2. SYNC projection completes (< 2s) → status = ACTIVE
3. Returns to user (automation shows ACTIVE)
4. TradingView webhook arrives
5. Webhook handler queries automation status → ACTIVE ✅
6. Signal PROCESSED correctly ✅
```

**ASYNC Events:**

```python
ASYNC_EVENTS = {
    # Signal processing (audit trail, eventual OK)
    "WebhookSignalReceivedEvent",   # Audit trail
    "SignalProcessedEvent",         # Confirmation
    "SignalRejectedEvent",          # Error notification

    # Configuration changes (eventual OK)
    "AutomationUpdatedEvent",       # Config changes
}
```

**Impact:** High SYNC rate (6/10 = 60%) justified by race condition prevention

---

### Example 3: Broker Account Domain (7 SYNC events, 72% reduction)

**SYNC Events (Cross-domain Validation):**

```python
SYNC_EVENTS = {
    # Cross-domain queries (Order/Position domains validate accounts)
    "BrokerAccountLinked",          # Order validates account exists
    "BrokerAccountUnlinked",        # Cleanup references

    # Account state (Order validation)
    "AccountStatusChanged",         # Order validation depends on status
    "BrokerAccountActivated",       # Cross-domain validation
    "BrokerAccountDeactivated",     # Cross-domain validation

    # User preferences
    "DefaultAccountSet",            # User queries immediately

    # Hard deletion
    "BrokerAccountDeleted",         # Single account hard delete
}
```

**ASYNC Events (Saga Coordination - Moved from SYNC):**

```python
ASYNC_EVENTS = {
    # Saga coordination events (TRUE SAGA refactor - NO queries!)
    "AccountDiscoveryStarted",         # Saga trigger
    "AccountsDiscovered",              # Saga notification
    "AccountDiscoveryCompleted",       # Saga notification
    "BrokerAccountsDeleted",           # Saga notification
    "BrokerAccountsCleanupOrchestrated",  # Saga coordination

    # High-frequency updates
    "AccountBalanceUpdated",           # Every trade
    "AccountEquityUpdated",            # Every quote

    # ... 18 total ASYNC events
}
```

**Refactor Impact:**
- **Before**: 25 SYNC events (sagas queried read models)
- **After**: 7 SYNC events (sagas use event data only)
- **Reduction**: 72% (18 events freed up!)

---

## Common Pitfalls

### ❌ Pitfall 1: Making Everything SYNC "To Be Safe"

**Problem:**
```python
# BAD: Every event is SYNC
SYNC_EVENTS = {
    "UserCreated",
    "UserUpdated",
    "UserLoggedIn",
    "UserLoggedOut",
    "UserPasswordChanged",
    "UserEmailChanged",
    # ... 50 more events
}
```

**Why Bad:**
- Blocks command responses (1-2s per command)
- Holds database connections longer
- Reduces system throughput by 5-10x
- User experience suffers (slow responses)

**Fix:**
```python
# GOOD: Only critical events SYNC
SYNC_EVENTS = {
    "UserCreated",          # Auth system queries immediately
    "UserEmailChanged",     # Login depends on email (cross-domain)
}

ASYNC_EVENTS = {
    "UserLoggedIn",         # Audit trail only
    "UserLoggedOut",        # Audit trail only
    "UserPasswordChanged",  # Background notification
    # ... rest are ASYNC
}
```

---

### ❌ Pitfall 2: Making Saga Coordination Events SYNC

**Problem:**
```python
# BAD: Saga events as SYNC
SYNC_EVENTS = {
    "AccountDiscoveryStarted",     # Saga coordination
    "AccountDiscoveryCompleted",   # Saga notification
    "SagaCompletedEvent",          # Saga lifecycle
}
```

**Why Bad:**
- Sagas should be event-driven (not query-driven)
- Blocking projection for saga coordination is unnecessary
- Violates TRUE SAGA pattern (sagas don't query read models)

**Fix:**
```python
# GOOD: Saga events are ASYNC (TRUE SAGA pattern)
ASYNC_EVENTS = {
    "AccountDiscoveryStarted",     # Saga trigger - no query_bus
    "AccountDiscoveryCompleted",   # Saga notification - eventual OK
    "SagaCompletedEvent",          # Saga lifecycle - eventual OK
}
```

**Rationale:** Sagas receive event data directly (no queries), so projection timing doesn't matter.

---

### ❌ Pitfall 3: Confusing "Important" with "SYNC Required"

**Problem:**
```python
# BAD: Making event SYNC because it "seems important"
SYNC_EVENTS = {
    "OrderFilled",          # "Important event!"
    "TradeExecuted",        # "Must be accurate!"
    "PositionClosed",       # "Financial data!"
}
```

**Why Bad:**
- "Important" ≠ "requires immediate consistency"
- Events can be critical but still use eventual consistency
- High-frequency events (OrderFilled) should NEVER be SYNC

**Fix:**
```python
# GOOD: Check if event is actually queried immediately
ASYNC_EVENTS = {
    "OrderFilled",          # User views orders page later (eventual OK)
    "TradeExecuted",        # Historical data (eventual OK)
    "PositionClosed",       # P&L calculation happens async (eventual OK)
}

SYNC_EVENTS = {
    # Only if cross-domain query happens immediately:
    "BrokerAccountLinked",  # Order command queries account status NOW
}
```

**Decision Test:** Ask "Will another domain query this within 100ms?" If NO → ASYNC.

---

### ❌ Pitfall 4: Using 10s+ Timeouts for SYNC Events

**Problem:**
```python
# BAD: Long timeout for SYNC event
EVENT_CONFIG = {
    "BrokerAccountLinked": {
        "priority": 1,
        "timeout": 30.0,  # 30 seconds! 😱
        "description": "Cross-domain validation"
    },
}
```

**Why Bad:**
- Blocks command response for 30s (terrible UX)
- Indicates projection is doing too much work
- Masks underlying performance issues

**Fix:**
```python
# GOOD: 2s timeout (forces efficient projection)
EVENT_CONFIG = {
    "BrokerAccountLinked": {
        "priority": 1,
        "timeout": 2.0,  # 2 seconds max
        "description": "Cross-domain validation"
    },
}
```

**Rule:** If projection takes >2s, optimize the projection (add indexes, batch operations, use cache).

---

### ❌ Pitfall 5: Not Documenting WHY Event is SYNC

**Problem:**
```python
# BAD: No context for future developers
SYNC_EVENTS = {
    "BrokerAccountLinked",
    "AutomationActivatedEvent",
    "BrokerConnectionInitiated",
}
```

**Why Bad:**
- Future developers might move to ASYNC (breaking system)
- No understanding of race conditions or dependencies
- Technical debt accumulates

**Fix:**
```python
# GOOD: Document rationale with examples
EVENT_CONFIG = {
    "BrokerAccountLinked": {
        "priority": 1,
        "timeout": 2.0,
        "description": "Cross-domain: Order/Position validate account exists",
        "rationale": "Order placement commands query broker_accounts table immediately",
        "queries_depend_on_this": [
            "GetBrokerAccountByIdQuery (Order domain)",
            "ValidateAccountStatusQuery (Position domain)"
        ],
        "moved_to_async_will_cause": "Orders fail with 'Account not found' error"
    },

    "AutomationActivatedEvent": {
        "priority": 1,
        "timeout": 2.0,
        "description": "Race condition: Webhook may arrive 50ms after activation",
        "rationale": "TradingView webhook can arrive before projection completes",
        "race_condition_scenario": """
            1. User activates automation
            2. Webhook arrives 50ms later
            3. Webhook handler queries automation.active status
            4. If ASYNC: status still False → signal rejected incorrectly
        """,
        "moved_to_async_will_cause": "Signals rejected immediately after activation"
    },
}
```

---

## Best Practices Summary

### ✅ DO:

1. **Default to ASYNC** - Only use SYNC when there's a concrete technical reason
2. **Document rationale** - Explain WHY event is SYNC with examples
3. **Use 2s timeout** - Forces efficient projections
4. **Measure SYNC rate** - Aim for <20% SYNC events per domain
5. **Review quarterly** - Can any SYNC events be moved to ASYNC?

### ❌ DON'T:

1. **Make saga events SYNC** - Sagas should be event-driven (TRUE SAGA pattern)
2. **Make high-frequency events SYNC** - Blocks system throughput
3. **Confuse "important" with "SYNC"** - Important events can use eventual consistency
4. **Use >2s timeouts** - Indicates projection needs optimization
5. **Make events SYNC "just in case"** - Measure performance impact first

---

## Migration Checklist

Moving event from SYNC → ASYNC:

```
□ Verify no cross-domain queries depend on immediate consistency
□ Check for race conditions (external webhooks, polling, etc.)
□ Confirm sagas don't query this event (should use event data directly)
□ Test with 500ms projection delay in staging
□ Monitor error rates after deployment
□ Update EVENT_CONFIG documentation
```

Moving event from ASYNC → SYNC:

```
□ Document concrete technical reason (cross-domain query, race condition)
□ Add EVENT_CONFIG entry with rationale
□ Optimize projection (add indexes, batch operations)
□ Measure projection time (< 2s required)
□ Test command latency impact
□ Monitor database connection pool usage
□ Update domain metrics (SYNC percentage)
```

---

## References

- **Saga Refactoring (2025)**: `ALL_SAGAS_REFACTORED_COMPLETE_NOV2025.md`
- **Sync Projection Analysis**: `SYNC_PROJECTION_OPTIMIZATION_COMPLETE_NOV2025.md`
- **Performance Guide**: `docs/reference/PERFORMANCE_OPTIMIZATION_GUIDE.md`
- **Event Sourcing**: `docs/cqrs.md`

---

**Next Steps:**
- Review your domain's `sync_events.py` file
- Challenge each SYNC event: "Can this be ASYNC?"
- Measure SYNC percentage (target: <20%)
- Optimize projections (target: <500ms per event)
