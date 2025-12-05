# Sequence Tracking Reference Guide

## Purpose

Sequence Tracking ensures **ordered, exactly-once event processing** in event-sourced systems. It solves two problems:

1. **Duplicate Prevention** - Events replayed from Kafka/EventStore aren't processed twice
2. **Order Guarantee** - Events are processed in correct sequence per aggregate

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Event Processor                             │
│                                                                  │
│  Event → ┌──────────────────┐ → Process → ┌──────────────────┐  │
│          │ Sequence Tracker │             │ Update Redis     │  │
│          └────────┬─────────┘             └──────────────────┘  │
│                   │                                              │
│          ┌────────▼─────────┐                                   │
│          │ Redis            │                                   │
│          │ key: domain_Event│                                   │
│          │ val: last_seq    │                                   │
│          └──────────────────┘                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### EventSequenceTracker

Location: `app/infra/event_store/sequence_tracker.py`

```python
class EventSequenceTracker:
    async def check_and_update_sequence(
        self,
        aggregate_id: UUID,
        projection_name: str,
        event_sequence: int,
        event_id: UUID,
        allow_replay: bool = False
    ) -> bool:
        """
        Returns True if event should be processed.
        Raises DuplicateEventError or OutOfOrderEventError.
        """
```

### Integration in Event Processor

Location: `app/infra/worker_core/event_processor/event_processor.py:780-812`

```python
if self.sequence_tracker and domain.enable_sequence_tracking:
    aggregate_id = uuid.UUID(event_dict.get("aggregate_id", str(event_uuid)))
    sequence = event_dict.get("sequence_number") or event_dict.get("aggregate_version", 1)

    try:
        should_process = await self.sequence_tracker.check_and_update_sequence(
            aggregate_id=aggregate_id,
            projection_name=f"{domain.name}_{event_type}",
            event_sequence=sequence,
            event_id=event_uuid,
            allow_replay=False
        )

        if not should_process:
            continue

    except OutOfOrderEventError as e:
        log.warning(f"Out of order event: {e}")
        await self._queue_pending_event(event_dict, domain.name)
        continue

    except DuplicateEventError as e:
        log.warning(f"Duplicate event skipped: {e}")
        continue
```

## Domain Configuration

Location: `app/infra/worker_core/event_processor/domain_registry.py`

```python
DomainRegistration(
    name="user_account",
    topics=[USER_ACCOUNT_EVENTS_TOPIC],
    projector_factory=user_projector_factory,
    event_models={...},
    enable_sequence_tracking=True,  # ← Enable/disable here
)
```

### Current Configuration

| Domain | `enable_sequence_tracking` | Rationale |
|--------|---------------------------|-----------|
| `user_account` | `True` | Bounded aggregate, ~100 events max |
| `company` | `True` | Bounded aggregate, strict ordering |
| `chat` | `False` | High-volume, Snowflake IDs for ordering |

## When to Disable Sequence Tracking

Disable when:

1. **High-volume streams** - Millions of events, central counter = bottleneck
2. **Alternative ordering** - Snowflake IDs, vector clocks, Lamport timestamps
3. **Eventual consistency OK** - Chat messages, logs, metrics
4. **Events lack sequence fields** - Legacy events without `aggregate_version`

### Industry References

> "Sequence numbers are going to fail unless you have a central deterministic sequence creator (which will be a non-scalable, single point of failure)."
> — [Stack Overflow: Global sequence counter in event store](https://stackoverflow.com/questions/2948523/in-cqrs-event-sourced-do-you-need-a-global-sequence-counter-in-the-event-stor)

> "Every ID we use is a Snowflake, making it chronologically sortable."
> — [Discord: How Discord Stores Trillions of Messages](https://discord.com/blog/how-discord-stores-trillions-of-messages)

> "In general it is bad idea to enforce global order. Aggregates are meant to form ACID-semantics boundaries."
> — [Domain Centric: Deduplication strategies](https://domaincentric.net/blog/event-sourcing-projection-patterns-deduplication-strategies)

## Redis Key Structure

```
event_sequence:{projection_name}:{aggregate_id}
```

Example:
```
event_sequence:user_account_UserAccountCreated:550e8400-e29b-41d4-a716-446655440000 = 5
```

TTL: 24 hours (configurable via `ttl_seconds`)

## Troubleshooting

### Events Silently Skipped

**Symptom:** Events not processed, no errors in logs

**Cause:** `DuplicateEventError` logged at WARNING (was DEBUG before fix)

**Check:** Look for `"Duplicate event skipped"` in logs

**Fix:** Either:
- Clear Redis sequence data: `redis-cli KEYS "event_sequence:*" | xargs redis-cli DEL`
- Disable sequence tracking for domain
- Add proper `sequence_number` to events

### Events Missing `sequence_number`

**Symptom:** All events have `sequence=1` (default)

**Cause:** Events don't include `sequence_number` or `aggregate_version`

**Code:** `event_processor.py:782`
```python
sequence = event_dict.get("sequence_number") or event_dict.get("aggregate_version", 1)
```

**Fix:** Either add sequence to events or disable tracking for domain

## Related Documentation

- [Chat Domain Architecture](../../mvp/domains/CHAT_ARCHITECTURE.md)
- [Event Processing](./EVENT_PROCESSING_GUIDE.md)
- [Martin Fowler: Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)
