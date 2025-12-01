# EventStore Stream Archival Pattern

## Problem

When using CQRS with Event Sourcing (KurrentDB/EventStoreDB), deleting entities from PostgreSQL (read model) without archiving the corresponding EventStore streams causes **foreign key violations** when old events are replayed.

### Symptoms

```
ERROR: insert or update on table "entities" violates foreign key constraint
DETAIL: Key (parent_id)=(uuid) is not present in table "parent_entities"
```

This happens because:
1. Entity deleted from PostgreSQL (read model)
2. EventStore still contains old events with references to deleted entity
3. On event replay/projection rebuild, old events reference non-existent entities

---

## Solution: Stream Archival Service

A **Server-side subscription service** that listens to deletion events and archives corresponding EventStore streams.

### Architecture

```
Command Handler (Write Side)
    │
    ├── emits EntityDeleted event → EventStore
    │                                    │
    │                                    ↓
    │                            publishes to topic
    │                                    │
    │                                    ↓
    │                     Stream Archival Service (subscription)
    │                                    │
    │                                    ↓
    │                          archive_stream() - soft delete
    │
    ↓
Worker (Read Side)
    │
    ↓
Projector → PostgreSQL (delete from read model)
```

### Why This Pattern?

**Industry Best Practice**: "Cleanup operations should be handled through event subscriptions, not command handlers"

Benefits:
- **Loose Coupling**: Command handlers don't know about archival
- **Single Responsibility**: Archival is separate concern
- **CQRS Compliance**: Write-side operation on EventStore
- **Decoupled**: Triggered by events, not embedded in commands

---

## Implementation

### 1. Add `archive_stream` Method to EventStore

```python
# app/infra/event_store/kurrentdb_event_store.py

async def archive_stream(
    self,
    aggregate_id: uuid.UUID,
    aggregate_type: str,
    reason: str = "Entity deleted from read model"
) -> bool:
    """
    Archive (soft-delete) an aggregate stream in KurrentDB.

    The stream is tombstoned but events are preserved for audit/compliance.
    """
    stream_name = f"{aggregate_type}-{aggregate_id}"

    if not self._initialized or not self._client:
        return False

    try:
        # KurrentDB soft-delete: deletes stream but keeps events
        await self._client.delete_stream(stream_name)

        log.info(f"Archived stream '{stream_name}': {reason}")

        # Also archive snapshot stream if exists
        snapshot_stream = f"snapshot-{aggregate_type}-{aggregate_id}"
        try:
            await self._client.delete_stream(snapshot_stream)
        except Exception:
            pass  # Snapshot may not exist

        # Invalidate version cache
        if self._cache_manager:
            cache_key = f"event_store:version:{stream_name}"
            await self._cache_manager.delete(cache_key)

        return True

    except StreamNotFoundError:
        return True  # Already deleted

    except Exception as e:
        log.error(f"Error archiving stream {stream_name}: {e}")
        return False
```

### 2. Create Stream Archival Service

```python
# app/infra/event_store/stream_archival_service.py

class StreamArchivalService:
    """
    Server-side subscription that archives EventStore streams
    when entities are deleted.
    """

    def __init__(self, event_bus, event_store):
        self._event_bus = event_bus
        self._event_store = event_store

        # Map deletion event types to aggregate types
        self._deletion_event_mapping = {
            "UserDeleted": "user",
            "OrderDeleted": "order",
            "ItemDeleted": "item",
            # Add your domain deletion events here
        }

    async def start(self) -> None:
        """Subscribe to deletion events from transport topics."""
        topics = [
            "transport.user-events",
            "transport.order-events",
            # Add your domain topics here
        ]

        for topic in topics:
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_event,
                group="stream-archival-service",
                consumer_id="archival-subscriber"
            )

    async def _handle_event(self, event_dict: Dict[str, Any]) -> None:
        """Archive stream when deletion event received."""
        event_type = event_dict.get("event_type", "")

        aggregate_type = self._deletion_event_mapping.get(event_type)
        if not aggregate_type:
            return  # Not a deletion event

        aggregate_id_str = event_dict.get("aggregate_id")
        if not aggregate_id_str:
            return

        try:
            aggregate_id = uuid.UUID(str(aggregate_id_str))

            await self._event_store.archive_stream(
                aggregate_id=aggregate_id,
                aggregate_type=aggregate_type,
                reason=f"Entity deleted via {event_type}"
            )

        except Exception as e:
            log.warning(f"Failed to archive stream: {e}")
```

### 3. Register in Server Startup

```python
# app/core/startup/distributed.py (or your startup module)

async def initialize_event_store(app):
    # ... EventStore initialization ...

    # Initialize Stream Archival Service
    from app.infra.event_store.stream_archival_service import (
        StreamArchivalService
    )

    archival_service = StreamArchivalService(
        event_bus=app.state.event_bus,
        event_store=app.state.event_store
    )
    await archival_service.start()

    app.state.archival_service = archival_service
```

---

## Configuration

### Adding New Domains

To support archival for a new domain:

1. **Add deletion event mapping**:
```python
self._deletion_event_mapping = {
    "MyEntityDeleted": "my_entity",
    "MyEntityHardDeleted": "my_entity",
}
```

2. **Subscribe to domain topic**:
```python
topics = [
    "transport.my-entity-events",
]
```

### Deletion Event Naming Convention

| Event Type | Purpose |
|------------|---------|
| `EntityDeleted` | Standard deletion (soft delete stream) |
| `EntityHardDeleted` | Permanent deletion |
| `EntityPurged` | Full purge after cascade completion |

---

## Graceful Handling for Stale Events

Add validation in projectors to skip stale events (defense in depth):

```python
# In your projector
async def on_entity_created(self, envelope: EventEnvelope) -> None:
    parent_id = event_data.get("parent_id")

    # Check if parent exists (prevent FK violation)
    parent_exists = await pg_db.fetchval(
        "SELECT EXISTS(SELECT 1 FROM parent_entities WHERE id = $1)",
        parent_id
    )

    if not parent_exists:
        log.warning(
            f"SKIPPING stale event: parent_id {parent_id} not found. "
            f"This occurs after database reset without clearing EventStore."
        )
        return  # Skip instead of crash
```

---

## Best Practices

### DO

- Archive streams via subscription service (decoupled)
- Use soft delete for reversibility
- Add graceful handling in projectors
- Keep EventStore and PostgreSQL in sync

### DON'T

- Archive in command handlers (coupling)
- Archive in workers/projectors (CQRS violation)
- Hard delete without audit requirements
- Directly delete from PostgreSQL without archiving streams

---

## Troubleshooting

### Events still appear after archival

This is expected - soft delete marks stream for scavenging but events may persist until next scavenge run.

### Foreign key violations persist

1. Check archival service is running and subscribed
2. Verify deletion event is mapped in `_deletion_event_mapping`
3. Check topic name matches subscription
4. Clear EventStore completely for fresh start (dev only)

### Clear EventStore (Development Only)

```bash
# Stop EventStore
docker stop kurrentdb-node

# Remove volume
docker volume rm kurrentdb-data

# Restart with fresh data
docker run -d --name kurrentdb-node \
  -p 2113:2113 \
  -v kurrentdb-data:/var/lib/kurrentdb \
  docker.kurrent.io/kurrent-latest/kurrentdb:latest \
  --insecure --run-projections=All
```

---

## References

- [Kurrent Blog: Stream Archival](https://www.kurrent.io/blog/keep-your-streams-short-temporal-modelling-for-fast-reads-and-optimal-data-retention)
- [Carnage's Tech Talk: Events Are Forever](https://carnage.github.io/2018/10/events-are-forever)
- [Microsoft: Event Sourcing Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
