# WellWon ScyllaDB Schema

High-volume message storage following Discord's architecture for storing trillions of messages.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATA DISTRIBUTION                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ScyllaDB (High-Volume, Time-Series)          PostgreSQL (ACID, Metadata)   │
│  ┌─────────────────────────────────┐          ┌───────────────────────────┐ │
│  │ - Message content               │          │ - Chat metadata           │ │
│  │ - Message reactions             │          │ - Participants            │ │
│  │ - Pinned messages               │  <--->   │ - Unread tracking         │ │
│  │ - Telegram sync state           │          │ - Message templates       │ │
│  │ - Channel metadata (denorm)     │          │ - Search index            │ │
│  └─────────────────────────────────┘          └───────────────────────────┘ │
│                                                                              │
│  Redis (Ephemeral)                                                           │
│  ┌─────────────────────────────────┐                                         │
│  │ - Typing indicators (10s TTL)   │                                         │
│  │ - User presence                 │                                         │
│  │ - Real-time counters            │                                         │
│  └─────────────────────────────────┘                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Schema Files

| File | Description |
|------|-------------|
| `schema.scylla` | **Main schema** - Complete production-ready schema |
| `migrations/001_initial_schema.cql` | Initial migration (same as main schema) |
| `migrations/README.md` | Migration documentation and conventions |

**Quality Report:** See [SCYLLADB_IMPLEMENTATION_QUALITY_REPORT.md](/docs/SCYLLADB_IMPLEMENTATION_QUALITY_REPORT.md) for full validation against industry standards.

## Tables

### Core Tables

| Table | Partition Key | Purpose |
|-------|--------------|---------|
| `messages` | `(channel_id, bucket)` | Main message storage |
| `telegram_message_mapping` | `(telegram_message_id, telegram_chat_id)` | Fast Telegram dedup lookup |
| `message_reactions` | `(channel_id, message_id)` | Individual reactions |
| `message_reaction_counts` | `(channel_id, message_id)` | Reaction counts (counter) |
| `pinned_messages` | `channel_id` | Pinned messages per channel |
| `telegram_sync_state` | `channel_id` | Telegram sync tracking |
| `channel_metadata` | `channel_id` | Denormalized channel info |
| `message_read_positions` | `(channel_id, user_id)` | Read position tracking |

### ScyllaDB 5.x/6.x Tablets Compatibility

**Tablets are DISABLED** in our keyspace (`tablets = {'enabled': false}`).

ScyllaDB 5.x+ enables tablets by default, but they are NOT compatible with:
- Counter tables (we use `message_reaction_counts`)
- Secondary indexes (we use `idx_telegram_sync_chat`)
- Materialized Views (removed from schema)
- Lightweight Transactions (LWT)

See [ScyllaDB Tablets Documentation](https://docs.scylladb.com/stable/architecture/tablets.html) for details.

**Note:** Materialized View `messages_by_author` was removed - use application-level filtering instead.

## Key Design Decisions

### 1. Discord-Style Partitioning

```sql
PRIMARY KEY ((channel_id, bucket), message_id)
```

- **Partition Key:** `(channel_id, bucket)` prevents unbounded partition growth
- **Bucket:** 10-day time window calculated from Snowflake ID
- **Clustering Key:** `message_id DESC` for time-ordered retrieval

### 2. Snowflake IDs

64-bit time-ordered, globally unique identifiers:

```
┌─────────────────────────────────────────────────────────────┐
│  42 bits timestamp  │  10 bits worker  │  12 bits sequence  │
│    (~139 years)     │   (1024 workers) │  (4096/ms/worker)  │
└─────────────────────────────────────────────────────────────┘
```

- **Epoch:** 2024-01-01 00:00:00 UTC
- **Benefits:** Time-ordered, no coordination, compact (bigint)

### 3. TWCS Compaction

```sql
compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_size': 10,
    'compaction_window_unit': 'DAYS'
}
```

Optimal for time-series data with immutable writes.

### 4. Telegram Message Mapping (No ALLOW FILTERING)

Instead of secondary index:
```sql
-- BAD: Secondary index causes full table scan
CREATE INDEX ON messages (telegram_message_id);

-- GOOD: Dedicated mapping table for O(1) lookup
CREATE TABLE telegram_message_mapping (
    telegram_message_id bigint,
    telegram_chat_id bigint,
    channel_id uuid,
    ...
    PRIMARY KEY ((telegram_message_id, telegram_chat_id))
);
```

## Setup Instructions

### Development (Single Node)

```bash
# Start ScyllaDB
docker run -d --name scylladb \
    -p 9042:9042 -p 19042:19042 \
    -v scylla-data:/var/lib/scylla \
    scylladb/scylla:5.4 \
    --smp 2 \
    --memory 2G \
    --developer-mode 1

# Wait for startup (~30s)
docker logs -f scylladb

# Apply schema
docker exec -i scylladb-node cqlsh < database/scylla/schema.scylla

# Verify
docker exec -it scylladb cqlsh -e "DESCRIBE KEYSPACE wellwon_scylla;"
```

### Production (3+ Nodes)

1. Update keyspace replication:
```sql
CREATE KEYSPACE wellwon_scylla
WITH replication = {
    'class': 'NetworkTopologyStrategy',
    'datacenter1': 3
};
```

2. Apply schema to cluster

### Environment Variables

```bash
# Enable ScyllaDB
SCYLLA_ENABLED=true

# Connection
SCYLLA_CONTACT_POINTS=node1.example.com,node2.example.com,node3.example.com
SCYLLA_PORT=9042
SCYLLA_KEYSPACE=wellwon_scylla

# Authentication (optional)
SCYLLA_USERNAME=wellwon
SCYLLA_PASSWORD=secure_password
```

## Python Client Usage

```python
from app.infra.persistence.scylladb import (
    get_scylla_client,
    generate_snowflake_id,
    calculate_message_bucket,
)
from app.infra.read_repos.message_scylla_repo import MessageScyllaRepo, MessageData

# Get repository
repo = MessageScyllaRepo()

# Insert message
message = MessageData(
    channel_id=chat_id,
    content="Hello, World!",
    sender_id=user_id,
    message_type="text",
    source="web",
)
snowflake_id = await repo.insert_message(message)

# Get messages with pagination
messages = await repo.get_messages(
    channel_id=chat_id,
    limit=50,
    before_id=last_message_id,
)

# Find by Telegram ID (uses mapping table - O(1))
msg = await repo.get_message_by_telegram_id(
    channel_id=chat_id,
    telegram_message_id=123456,
    telegram_chat_id=telegram_chat_id,  # For O(1) lookup
)
```

## Performance Characteristics

| Operation | Complexity | Notes |
|-----------|------------|-------|
| Insert message | O(1) | Single partition write |
| Get message by ID | O(1) | Direct partition + clustering key |
| Get messages (pagination) | O(log n) | Clustering key range |
| Get by Telegram ID | O(1) | Via mapping table |
| Add reaction | O(1) | Partition write + counter increment |

## Consistency Levels

| Operation | Level | Latency |
|-----------|-------|---------|
| Writes | LOCAL_QUORUM | ~5ms |
| Reads | LOCAL_ONE | ~1ms |

## Monitoring

### Health Checks

```python
from app.infra.persistence.scylladb import (
    check_connection_health,
    check_cluster_health,
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

### Metrics

- Query count
- Error count
- Prepared statement cache size (LRU, max 1000)
- Circuit breaker state
- Average latency

## JetBrains/DataGrip Connection

ScyllaDB uses the Cassandra CQL protocol:
1. Add new data source -> **Apache Cassandra**
2. Host: `localhost`
3. Port: `9042`
4. Keyspace: `wellwon_scylla`

## Internal Documentation

| Document | Location | Description |
|----------|----------|-------------|
| **MVP Guide** | `docs/mvp/infrastructure/SCYLLADB.md` | Production setup and architecture |
| **Developer Guide** | `docs/reference/infrastructure/SCYLLADB_GUIDE.md` | Client usage and best practices |
| **Quality Report** | `docs/SCYLLADB_IMPLEMENTATION_QUALITY_REPORT.md` | Validation against best practices |
| **Infrastructure Report** | `docs/SCYLLADB_INFRASTRUCTURE_REPORT.md` | Detailed implementation analysis |
| **Data Distribution** | `docs/DATABASE_DISTRIBUTION_ANALYSIS.md` | PostgreSQL vs ScyllaDB decisions |

## External References

- [Discord: How We Store Trillions of Messages](https://discord.com/blog/how-discord-stores-trillions-of-messages)
- [ScyllaDB Data Modeling Best Practices](https://docs.scylladb.com/stable/get-started/data-modeling/best-practices.html)
- [ScyllaDB TWCS Compaction](https://university.scylladb.com/courses/scylla-operations/lessons/compaction-strategies/topic/time-window-compaction-strategy-twcs/)
- [ScyllaDB Secondary Indexes vs MVs](https://university.scylladb.com/courses/data-modeling/lessons/materialized-views-secondary-indexes-and-filtering/)
