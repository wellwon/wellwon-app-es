# Snapshot Loading Fix Guide

**Version:** 1.0
**Date:** 2025-12-02
**Author:** WellWon Team

---

## Executive Summary

This guide documents a critical fix for Event Sourcing systems that use snapshots for aggregate loading optimization. The fix ensures that aggregate state is properly restored from snapshots before applying subsequent events.

**Without this fix:** Aggregates lose state that existed before the snapshot was created.

---

## Problem Analysis

### The Bug

When loading an aggregate, the event store's `get_events()` method uses snapshots to optimize reading:

```python
# Inside get_events()
snapshot = await self.get_latest_snapshot(aggregate_id, aggregate_type)
if snapshot and snapshot.version >= from_version:
    from_version = snapshot.version + 1  # Skip events before snapshot
```

This optimization is correct - we don't need to read events that are already captured in the snapshot.

**BUT** the snapshot data is never returned to the caller!

The caller then does:
```python
events = await event_store.get_events(aggregate_id, "Type")  # Only post-snapshot events!
aggregate = Aggregate.replay_from_events(aggregate_id, events)  # Creates EMPTY aggregate!
```

### Visual Explanation

```
Event Stream: [E1, E2, ... E400] [SNAPSHOT @ v400] [E401, E402, ... E495]
                                       │
                    ┌──────────────────┘
                    │
                    v
              Contains:
              - participants: {user1, user2, user3}
              - message_count: 1500
              - name: "My Chat"
              - telegram_chat_id: 12345

get_events() returns: [E401, E402, ... E495]  (95 events)

replay_from_events() without snapshot:
  1. Creates empty aggregate (version=0, no participants)
  2. Applies E401-E495
  3. Result: MISSING user1, user2, user3!

replay_from_events() WITH snapshot:
  1. Creates aggregate from snapshot (version=400, has user1, user2, user3)
  2. Applies E401-E495
  3. Result: CORRECT state with all participants
```

### Symptoms of This Bug

1. **UserNotParticipantError** when user is definitely a participant
2. **Wrong message counts** after loading aggregate
3. **Missing telegram_chat_id** even though chat is linked
4. **Optimistic concurrency conflicts** (expected version 1 but found 401)
5. **Any aggregate state from before snapshot is lost**

---

## Solution Implementation

### File 1: Event Store

**File:** `app/infra/event_store/kurrentdb_event_store.py`

Add new method after `get_events()`:

```python
async def get_events_with_snapshot(
    self,
    aggregate_id: uuid.UUID,
    aggregate_type: str,
    from_version: int = 0,
    to_version: Optional[int] = None,
) -> Tuple[Optional['AggregateSnapshot'], List[EventEnvelope]]:
    """
    Get snapshot and events for aggregate from KurrentDB.

    This is the proper way to load aggregates - returns both the snapshot
    (if exists) and events that occurred after the snapshot. The caller
    should restore from snapshot first, then apply the events.

    Args:
        aggregate_id: Aggregate UUID
        aggregate_type: Aggregate type
        from_version: Start version (inclusive, 1-based)
        to_version: End version (inclusive, 1-based, None = all)

    Returns:
        Tuple of (snapshot or None, list of events after snapshot)
    """
    if not self._initialized or not self._client:
        raise EventStoreError("KurrentDB not initialized")

    # Load snapshot first
    snapshot = await self.get_latest_snapshot(aggregate_id, aggregate_type)
    events_from_version = from_version

    if snapshot and snapshot.version >= from_version:
        events_from_version = snapshot.version + 1
        log.debug(
            f"Found snapshot at version {snapshot.version} for "
            f"{aggregate_type}-{aggregate_id}, reading events from {events_from_version}"
        )

    stream_name = self._get_stream_name(aggregate_id, aggregate_type)
    from_revision = events_from_version - 1 if events_from_version > 0 else 0

    log.info(
        f"get_events_with_snapshot: stream='{stream_name}' "
        f"snapshot_version={snapshot.version if snapshot else None} "
        f"reading_from={events_from_version}"
    )

    try:
        events_generator = await self._client.read_stream(
            stream_name=stream_name,
            stream_position=from_revision
        )

        envelopes = []
        async for recorded_event in events_generator:
            event_data = json.loads(recorded_event.data.decode('utf-8'))
            envelope = EventEnvelope.from_dict(event_data)
            envelope.aggregate_version = recorded_event.stream_position + 1

            if to_version and envelope.aggregate_version > to_version:
                break

            envelopes.append(envelope)

        log.info(
            f"get_events_with_snapshot: loaded snapshot={'yes' if snapshot else 'no'} "
            f"+ {len(envelopes)} events for {aggregate_type}-{aggregate_id}"
        )
        return (snapshot, envelopes)

    except StreamNotFoundError:
        log.info(f"Stream '{stream_name}' not found - returning (None, [])")
        return (None, [])

    except StreamIsDeletedError:
        log.warning(f"Stream '{stream_name}' was deleted - returning (None, [])")
        return (None, [])

    except Exception as e:
        log.error(f"Error in get_events_with_snapshot: {type(e).__name__}: {e}")
        raise EventStoreError(f"Failed to get events with snapshot: {e}") from e
```

**Required imports:**
```python
from typing import Tuple  # Add if not present
```

---

### File 2: Aggregate Classes

**Files:**
- `app/chat/aggregate.py`
- `app/user_account/aggregate.py`
- `app/company/aggregate.py`
- (any other aggregate files)

Update `replay_from_events()` method:

```python
@classmethod
def replay_from_events(
    cls,
    aggregate_id: uuid.UUID,
    events: List[BaseEvent],
    snapshot: Optional[Any] = None  # NEW PARAMETER
) -> 'YourAggregate':
    """
    Reconstruct aggregate from event history.

    Handles both BaseEvent objects and EventEnvelope objects (from KurrentDB).
    EventEnvelopes are converted to domain events using the event registry.

    Args:
        aggregate_id: The aggregate ID
        events: Events to replay (should be events AFTER snapshot if snapshot provided)
        snapshot: Optional AggregateSnapshot to restore from first
    """
    from app.infra.event_store.event_envelope import EventEnvelope
    from app.your_domain.events import YOUR_EVENT_TYPES

    agg = cls(aggregate_id)

    # CRITICAL: Restore from snapshot first if provided
    if snapshot is not None:
        agg.restore_from_snapshot(snapshot.state)
        agg.version = snapshot.version
        log.debug(f"Restored {cls.__name__} {aggregate_id} from snapshot at version {snapshot.version}")

    for evt in events:
        # Handle EventEnvelope from KurrentDB
        if isinstance(evt, EventEnvelope):
            # Try to convert envelope to domain event object
            event_obj = evt.to_event_object()
            if event_obj is None:
                # Fallback: use event types registry
                event_class = YOUR_EVENT_TYPES.get(evt.event_type)
                if event_class:
                    try:
                        event_obj = event_class(**evt.event_data)
                    except Exception as e:
                        log.warning(f"Failed to deserialize {evt.event_type}: {e}")
                        continue
                else:
                    log.warning(f"Unknown event type in replay: {evt.event_type}")
                    continue
            agg._apply(event_obj)
            # Use version from envelope (handles snapshot case correctly)
            if evt.aggregate_version:
                agg.version = evt.aggregate_version
            else:
                agg.version += 1
        else:
            # Direct BaseEvent object
            agg._apply(evt)
            agg.version += 1

    agg.mark_events_committed()
    return agg
```

**Required imports (add to aggregate file if missing):**
```python
from typing import Optional, Any
```

---

### File 3: Base Command Handler

**File:** `app/common/base/base_command_handler.py`

Add imports:
```python
from typing import Type, TypeVar

T = TypeVar('T', bound='AggregateProtocol')
```

Add method to `BaseCommandHandler` class:

```python
async def load_aggregate(
    self,
    aggregate_id: uuid.UUID,
    aggregate_type: str,
    aggregate_class: Type[T],
) -> T:
    """
    Load an aggregate from the event store with proper snapshot support.

    This is the recommended way to load aggregates in command handlers.
    It properly handles:
    - Loading snapshot (if exists)
    - Loading events after snapshot
    - Restoring aggregate state from snapshot first
    - Applying subsequent events

    Args:
        aggregate_id: The aggregate's UUID
        aggregate_type: Type name (e.g., "Chat", "User", "Company")
        aggregate_class: The aggregate class (must have replay_from_events classmethod)

    Returns:
        Reconstructed aggregate instance

    Example:
        chat = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)
    """
    if not self.event_store:
        raise RuntimeError("Event store not configured - cannot load aggregate")

    snapshot, events = await self.event_store.get_events_with_snapshot(
        aggregate_id, aggregate_type
    )

    return aggregate_class.replay_from_events(
        aggregate_id, events, snapshot=snapshot
    )
```

---

### File 4: Command Handlers

**All files in:** `app/*/command_handlers/*.py`

Replace old pattern:

```python
# OLD (BROKEN)
events = await self.event_store.get_events(command.chat_id, "Chat")
chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

# NEW (CORRECT)
chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)
```

**For handlers that need bootstrap check (migration support):**

```python
# When you need to know if aggregate is new (no snapshot AND no events)
snapshot, events = await self.event_store.get_events_with_snapshot(
    command.chat_id, "Chat"
)
chat_aggregate = ChatAggregate.replay_from_events(
    command.chat_id, events, snapshot=snapshot
)

# Check if this is a completely new aggregate
is_new_aggregate = snapshot is None and not events
```

---

## Verification Checklist

After implementing the fix, verify:

### 1. Event Store
- [ ] `get_events_with_snapshot()` method exists
- [ ] Returns `Tuple[Optional[AggregateSnapshot], List[EventEnvelope]]`
- [ ] Loads snapshot correctly
- [ ] Returns events from correct version (after snapshot)

### 2. Aggregates
- [ ] All aggregates have `snapshot` parameter in `replay_from_events()`
- [ ] Snapshot is restored BEFORE applying events
- [ ] Version is set from snapshot first, then from envelopes

### 3. Base Command Handler
- [ ] `load_aggregate()` helper method exists
- [ ] Uses `get_events_with_snapshot()`
- [ ] Passes snapshot to `replay_from_events()`

### 4. Command Handlers
- [ ] All handlers use `load_aggregate()` or `get_events_with_snapshot()`
- [ ] No handlers use old `get_events()` + `replay_from_events()` pattern
- [ ] Special cases (bootstrap) use explicit snapshot check

---

## Troubleshooting

### "User is not a participant" Error

**Cause:** Participant was added before snapshot, not being restored.

**Fix:** Ensure `replay_from_events()` restores from snapshot first.

**Debug:**
```python
log.info(f"Loaded aggregate: version={agg.version}, participants={list(agg.state.participants.keys())}")
```

### Optimistic Concurrency Conflict

**Cause:** Aggregate version not being set correctly from snapshot.

**Symptoms:**
```
Expected version 1 but found 401
```

**Fix:** Ensure `agg.version = snapshot.version` is called when restoring.

**Debug:**
```python
log.info(f"After snapshot restore: version={agg.version}")
log.info(f"After event replay: version={agg.version}")
```

### Missing State After Load

**Cause:** `restore_from_snapshot()` not implementing all fields.

**Fix:** Verify `restore_from_snapshot()` restores ALL aggregate state:
- participants
- metadata
- telegram_chat_id
- telegram_topic_id
- message_count
- etc.

---

## Related Documentation

- `docs/mvp/architecture/SNAPSHOT_AGGREGATE_LOADING.md` - High-level overview
- `docs/mvp/architecture/SEQUENCE_TRACKING.md` - Event ordering
- `docs/mvp/domains/CHAT_ARCHITECTURE.md` - Chat domain specifics

---

## Changelog

### 2025-12-02
- Initial implementation
- Fixed snapshot loading for all aggregates
- Added `load_aggregate()` helper to BaseCommandHandler
- Updated all command handlers
