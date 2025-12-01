# ScyllaDB - Message Storage Infrastructure

**Version:** 1.0.0
**Last Updated:** 2025-11-30
**Status:** Production Ready

---

## Overview

WellWon uses ScyllaDB for high-volume message storage, following Discord's proven architecture for storing trillions of messages. ScyllaDB handles message content while PostgreSQL manages metadata and search.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA DISTRIBUTION                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ScyllaDB (wellwon_scylla)           PostgreSQL (wellwon)               │
│  ┌───────────────────────────┐       ┌─────────────────────────────┐   │
│  │ messages (PRIMARY)        │       │ messages (SEARCH INDEX)     │   │
│  │ telegram_message_mapping  │       │ message_templates           │   │
│  │ message_reactions         │ <---> │ chats                       │   │
│  │ message_reaction_counts   │       │ chat_participants           │   │
│  │ pinned_messages           │       │ user_accounts               │   │
│  │ telegram_sync_state       │       │ companies                   │   │
│  │ channel_metadata          │       │ ...metadata tables          │   │
│  │ message_read_positions    │       │                             │   │
│  └───────────────────────────┘       └─────────────────────────────┘   │
│                                                                          │
│  Redis (Ephemeral)                                                       │
│  ┌───────────────────────────┐                                          │
│  │ typing:{chat}:{user}      │                                          │
│  │ presence:{user}           │                                          │
│  └───────────────────────────┘                                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Discord-Style Partitioning

```sql
PRIMARY KEY ((channel_id, bucket), message_id)
```

- **Partition Key:** `(channel_id, bucket)` prevents unbounded partition growth
- **Bucket:** 10-day time window calculated from Snowflake ID
- **Clustering:** `message_id DESC` for "newest first" queries

### 2. Snowflake IDs

64-bit time-ordered, globally unique message identifiers:

```
┌─────────────────────────────────────────────────────────────┐
│  42 bits timestamp  │  10 bits worker  │  12 bits sequence  │
│    (~139 years)     │   (1024 workers) │  (4096/ms/worker)  │
└─────────────────────────────────────────────────────────────┘
```

- **Epoch:** 2024-01-01 00:00:00 UTC
- **Benefits:** Time-ordered, no coordination needed, compact storage

### 3. Telegram Deduplication

Dedicated mapping table instead of secondary index (anti-pattern avoided):

```sql
CREATE TABLE telegram_message_mapping (
    telegram_message_id bigint,
    telegram_chat_id bigint,
    channel_id uuid,
    bucket int,
    message_id bigint,
    PRIMARY KEY ((telegram_message_id, telegram_chat_id))
);
```

## Tables

| Table | Partition Key | Purpose |
|-------|--------------|---------|
| `messages` | `(channel_id, bucket)` | Primary message storage |
| `telegram_message_mapping` | `(telegram_message_id, telegram_chat_id)` | O(1) Telegram dedup |
| `message_reactions` | `(channel_id, message_id)` | Individual reactions |
| `message_reaction_counts` | `(channel_id, message_id)` | Reaction counts (counter) |
| `pinned_messages` | `channel_id` | Pinned messages |
| `telegram_sync_state` | `channel_id` | Telegram sync tracking |
| `channel_metadata` | `channel_id` | Denormalized channel info |
| `message_read_positions` | `(channel_id, user_id)` | Read position tracking |

## Performance Characteristics

| Operation | Complexity | Latency |
|-----------|------------|---------|
| Insert message | O(1) | ~5ms |
| Get message by ID | O(1) | ~1ms |
| Get messages (pagination) | O(log n) | ~2ms |
| Get by Telegram ID | O(1) | ~1ms |
| Add reaction | O(1) | ~3ms |

## Configuration

### Environment Variables

```bash
# Enable ScyllaDB
SCYLLA_ENABLED=true

# Connection
SCYLLA_CONTACT_POINTS=node1.example.com,node2.example.com
SCYLLA_PORT=9042
SCYLLA_KEYSPACE=wellwon_scylla

# Authentication (optional)
SCYLLA_USERNAME=wellwon
SCYLLA_PASSWORD=secure_password
```

### Development Setup

```bash
# Start ScyllaDB container
docker run -d --name scylladb \
    -p 9042:9042 -p 19042:19042 \
    -v scylla-data:/var/lib/scylla \
    scylladb/scylla:5.4 \
    --smp 2 --memory 2G --developer-mode 1

# Wait for startup (~30s)
docker logs -f scylladb

# Apply schema
docker exec -i scylladb cqlsh < database/scylla/wellwon_scylla.cql

# Verify
docker exec -it scylladb cqlsh -e "DESCRIBE KEYSPACE wellwon_scylla;"
```

### Production Setup

Update replication factor to 3:

```sql
CREATE KEYSPACE wellwon_scylla
WITH replication = {
    'class': 'NetworkTopologyStrategy',
    'datacenter1': 3
};
```

## Compaction Strategy

TimeWindowCompactionStrategy (TWCS) optimized for time-series data:

```sql
compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_size': 10,
    'compaction_window_unit': 'DAYS'
}
```

- **gc_grace_seconds:** 86400 (1 day) - reduced for immutable data
- **Bucket alignment:** 10-day windows match compaction windows

## Consistency Levels

| Operation | Level | Rationale |
|-----------|-------|-----------|
| Writes | LOCAL_QUORUM | Durability guarantee |
| Reads | LOCAL_ONE | Speed, eventual consistency acceptable |

## Health Checks

```python
from app.infra.persistence.scylladb import (
    readiness_probe,
    liveness_probe,
)

# Kubernetes probes
@app.get("/health/ready")
async def readiness():
    return await readiness_probe(get_scylla_client())

@app.get("/health/live")
async def liveness():
    return await liveness_probe(get_scylla_client())
```

## Files

| File | Description |
|------|-------------|
| `database/scylla/wellwon_scylla.cql` | Main schema |
| `database/scylla/migrations/` | Migration files |
| `app/config/scylla_config.py` | Configuration |
| `app/infra/persistence/scylladb/client.py` | Client implementation |
| `app/infra/persistence/scylladb/health.py` | Health checks |
| `app/infra/read_repos/message_scylla_repo.py` | Repository |

## References

- [Discord: How We Store Trillions of Messages](https://discord.com/blog/how-discord-stores-trillions-of-messages)
- [ScyllaDB Data Modeling Best Practices](https://docs.scylladb.com/stable/get-started/data-modeling/best-practices.html)
- [ScyllaDB TWCS Compaction](https://university.scylladb.com/courses/scylla-operations/lessons/compaction-strategies/topic/time-window-compaction-strategy-twcs/)
