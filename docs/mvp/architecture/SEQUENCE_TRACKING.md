# Sequence Tracking in WellWon

## Overview

Sequence Tracking ensures **ordered, exactly-once event processing** for domain aggregates. It prevents duplicate processing and detects out-of-order events.

## How It Works

```
Event (seq=N) → Sequence Tracker → Check Redis → Process or Skip
                                        ↓
                              Redis: last_seq for aggregate
```

1. Each event has a `sequence_number` or `aggregate_version`
2. Redis stores the last processed sequence per aggregate
3. Before processing, tracker checks:
   - `seq <= last` → DuplicateEventError (skip)
   - `seq > last + 1` → OutOfOrderEventError (queue for retry)
   - `seq == last + 1` → OK, process and update Redis

## Configuration

Sequence tracking is configured per domain in `domain_registry.py`:

```python
DomainRegistration(
    name="user_account",
    enable_sequence_tracking=True,  # Enabled for bounded aggregates
    ...
)
```

## Domain Configuration

| Domain | Sequence Tracking | Reason |
|--------|------------------|--------|
| `user_account` | ✅ Enabled | Bounded aggregate, strict ordering needed |
| `company` | ✅ Enabled | Bounded aggregate, strict ordering needed |
| `chat` | ❌ Disabled | High-volume, uses Snowflake IDs for ordering |

## When to Enable

**Enable for:**
- Bounded aggregates with limited events (UserAccount, Company, Order)
- Domains requiring strict ACID consistency
- Aggregates where event order affects business logic

**Disable for:**
- High-volume streams (messages, logs, metrics)
- Domains using alternative ordering (Snowflake IDs, timestamps)
- Eventually consistent domains

## Implementation

**Files:**
- `app/infra/event_store/sequence_tracker.py` - Core tracker
- `app/infra/worker_core/event_processor/event_processor.py:780-812` - Integration
- `app/infra/worker_core/event_processor/domain_registry.py` - Configuration

## Related

- [Chat Domain Architecture](../domains/CHAT_ARCHITECTURE.md)
- [Event Processing](./EVENT_PROCESSING.md)
