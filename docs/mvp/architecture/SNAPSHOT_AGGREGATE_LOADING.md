# Snapshot-Aware Aggregate Loading

**Status:** Implemented
**Date:** 2025-12-02
**Affects:** All Event-Sourced Aggregates

---

## Overview

This document describes the proper pattern for loading aggregates from the event store when snapshots are enabled. The pattern ensures that aggregate state is correctly restored from snapshots before applying subsequent events.

## The Problem

### Symptom
```
UserNotParticipantError: User xxx is not a participant of chat yyy
```

Even though the user IS a participant (added before snapshot was created).

### Root Cause

The original `replay_from_events()` pattern had a critical flaw:

```python
# OLD PATTERN (BROKEN)
events = await self.event_store.get_events(aggregate_id, "Chat")
aggregate = ChatAggregate.replay_from_events(aggregate_id, events)
```

**What happens:**
1. `get_events()` finds snapshot at version 400
2. `get_events()` optimizes by returning only events AFTER snapshot (e.g., 95 events from version 401-495)
3. `replay_from_events()` creates **empty** aggregate (version=0)
4. `replay_from_events()` applies only the 95 events
5. **ParticipantAdded events from before version 400 are NEVER applied!**

### Why This Breaks

- Participants added before the snapshot → NOT in aggregate state
- Messages sent before snapshot → message count wrong
- Any state changes before snapshot → LOST

## The Solution

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Proper Aggregate Loading                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Load Snapshot (if exists)                                   │
│     └── Contains: participants, message_count, state at v400    │
│                                                                  │
│  2. Restore Aggregate from Snapshot                             │
│     └── aggregate.restore_from_snapshot(snapshot.state)         │
│     └── aggregate.version = snapshot.version (400)              │
│                                                                  │
│  3. Load Events AFTER Snapshot                                  │
│     └── Events from v401 to current                             │
│                                                                  │
│  4. Apply Events to Aggregate                                   │
│     └── Incremental updates on top of snapshot state            │
│                                                                  │
│  Result: Complete aggregate state at current version            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

#### 1. Event Store Method

New method `get_events_with_snapshot()` returns both snapshot and events:

```python
# app/infra/event_store/kurrentdb_event_store.py

async def get_events_with_snapshot(
    self,
    aggregate_id: uuid.UUID,
    aggregate_type: str,
    from_version: int = 0,
    to_version: Optional[int] = None,
) -> Tuple[Optional[AggregateSnapshot], List[EventEnvelope]]:
    """
    Get snapshot and events for aggregate.

    Returns:
        Tuple of (snapshot or None, list of events after snapshot)
    """
    snapshot = await self.get_latest_snapshot(aggregate_id, aggregate_type)
    events_from_version = from_version

    if snapshot and snapshot.version >= from_version:
        events_from_version = snapshot.version + 1

    events = await self._read_events_from_version(events_from_version)
    return (snapshot, events)
```

#### 2. Aggregate `replay_from_events()`

Updated to accept optional snapshot:

```python
# app/chat/aggregate.py (and all other aggregates)

@classmethod
def replay_from_events(
    cls,
    aggregate_id: uuid.UUID,
    events: List[BaseEvent],
    snapshot: Optional[Any] = None  # NEW PARAMETER
) -> 'ChatAggregate':
    """
    Reconstruct aggregate from snapshot + events.

    Args:
        aggregate_id: The aggregate ID
        events: Events to replay (AFTER snapshot if provided)
        snapshot: Optional AggregateSnapshot to restore from first
    """
    agg = cls(aggregate_id)

    # CRITICAL: Restore from snapshot FIRST
    if snapshot is not None:
        agg.restore_from_snapshot(snapshot.state)
        agg.version = snapshot.version

    # Then apply subsequent events
    for evt in events:
        if isinstance(evt, EventEnvelope):
            event_obj = evt.to_event_object()
            agg._apply(event_obj)
            if evt.aggregate_version:
                agg.version = evt.aggregate_version
            else:
                agg.version += 1
        else:
            agg._apply(evt)
            agg.version += 1

    agg.mark_events_committed()
    return agg
```

#### 3. BaseCommandHandler Helper

New `load_aggregate()` method centralizes the pattern:

```python
# app/common/base/base_command_handler.py

async def load_aggregate(
    self,
    aggregate_id: uuid.UUID,
    aggregate_type: str,
    aggregate_class: Type[T],
) -> T:
    """
    Load aggregate with proper snapshot support.

    This is the RECOMMENDED way to load aggregates in command handlers.

    Example:
        chat = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)
    """
    snapshot, events = await self.event_store.get_events_with_snapshot(
        aggregate_id, aggregate_type
    )
    return aggregate_class.replay_from_events(
        aggregate_id, events, snapshot=snapshot
    )
```

## Usage Patterns

### Command Handler (Recommended)

```python
@command_handler(SendMessageCommand)
class SendMessageHandler(BaseCommandHandler):

    async def handle(self, command: SendMessageCommand) -> uuid.UUID:
        # Use the helper method - handles snapshots automatically
        chat = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        chat.send_message(
            message_id=command.message_id,
            sender_id=command.sender_id,
            content=command.content,
        )

        await self.publish_events(aggregate=chat, aggregate_id=command.chat_id, command=command)
        return command.message_id
```

### Special Cases (Need Bootstrap Check)

When you need to check if aggregate is new (e.g., migration support):

```python
async def handle(self, command: ProcessTelegramMessageCommand) -> uuid.UUID:
    # Use get_events_with_snapshot directly for bootstrap check
    snapshot, events = await self.event_store.get_events_with_snapshot(
        command.chat_id, "Chat"
    )
    chat = ChatAggregate.replay_from_events(command.chat_id, events, snapshot=snapshot)

    # Check if this is a NEW aggregate (no history at all)
    is_bootstrapped = snapshot is None and not events

    if is_bootstrapped:
        await self._bootstrap_from_read_model(chat, command.chat_id)
```

## Compatibility

### AggregateRepository

`AggregateRepository._load_aggregate_internal()` already handles snapshots correctly:

```python
async def _load_aggregate_internal(self, aggregate_id):
    aggregate = self.aggregate_class(aggregate_id)

    # Load and restore from snapshot
    if self.enable_snapshots:
        snapshot = await self.event_store.get_latest_snapshot(...)
        if snapshot:
            aggregate.restore_from_snapshot(snapshot.state)
            aggregate.version = snapshot.version

    # Load events after snapshot
    events = await self.event_store.get_events(
        aggregate_id, self.aggregate_type,
        from_version=start_version + 1
    )

    # Apply events with version from envelope
    for envelope in events:
        aggregate._apply(domain_event)
        aggregate.version = envelope.aggregate_version
```

### AggregateProvider

`DefaultAggregateProvider` also handles this correctly by manually setting version from envelope.

## Migration Guide

### Step 1: Update Event Store

Add `get_events_with_snapshot()` method to your event store implementation.

### Step 2: Update Aggregates

Add `snapshot` parameter to all `replay_from_events()` methods:

```python
@classmethod
def replay_from_events(
    cls,
    aggregate_id: uuid.UUID,
    events: List[BaseEvent],
    snapshot: Optional[Any] = None  # ADD THIS
) -> 'YourAggregate':
    agg = cls(aggregate_id)

    # ADD THIS BLOCK
    if snapshot is not None:
        agg.restore_from_snapshot(snapshot.state)
        agg.version = snapshot.version

    for evt in events:
        # ... existing code
```

### Step 3: Update BaseCommandHandler

Add `load_aggregate()` helper method.

### Step 4: Update Command Handlers

Replace old pattern:
```python
# OLD
events = await self.event_store.get_events(command.chat_id, "Chat")
chat = ChatAggregate.replay_from_events(command.chat_id, events)

# NEW
chat = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)
```

## Testing

### Verify Snapshot Loading

```python
async def test_aggregate_loads_from_snapshot():
    # Create aggregate with participant
    chat = ChatAggregate(chat_id)
    chat.create_chat(name="Test", chat_type="group", created_by=user_id)
    chat.add_participant(user_id=user_id, role="admin", added_by=user_id)

    # Save events and create snapshot
    await event_store.append_events(chat.id, "Chat", chat.get_uncommitted_events())
    await event_store.save_snapshot(chat.id, "Chat", chat.version, chat.create_snapshot())

    # Add more events after snapshot
    chat.send_message(...)
    await event_store.append_events(...)

    # Load aggregate - should have participant from snapshot
    loaded = await handler.load_aggregate(chat.id, "Chat", ChatAggregate)

    assert loaded.is_participant(user_id)  # MUST pass
    assert loaded.version == expected_version
```

## References

- [Snapshots in Event Sourcing - Kurrent.io](https://www.kurrent.io/blog/snapshots-in-event-sourcing)
- [Event Sourcing: Snapshotting - Domain Centric](https://domaincentric.net/blog/event-sourcing-snapshotting)
- [Event Sourcing Pattern - Microsoft Azure](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
