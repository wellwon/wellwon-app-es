# ScyllaDB Developer Guide

**Version:** 1.0.0
**Last Updated:** 2025-11-30

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Data Modeling](#2-data-modeling)
3. [Client Usage](#3-client-usage)
4. [Repository Pattern](#4-repository-pattern)
5. [Snowflake IDs](#5-snowflake-ids)
6. [Best Practices](#6-best-practices)
7. [Anti-Patterns to Avoid](#7-anti-patterns-to-avoid)
8. [Testing](#8-testing)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Introduction

ScyllaDB is a high-performance NoSQL database compatible with Apache Cassandra. WellWon uses it for high-volume message storage following Discord's architecture.

### When to Use ScyllaDB

| Use Case | Database |
|----------|----------|
| High-volume writes (messages) | ScyllaDB |
| Time-series data | ScyllaDB |
| Simple key-value access | ScyllaDB |
| Complex JOINs | PostgreSQL |
| Full-text search | PostgreSQL |
| ACID transactions | PostgreSQL |
| Reference data (users, companies) | PostgreSQL |

---

## 2. Data Modeling

### Partition Key Design

The partition key determines data distribution across nodes. Design for:

1. **Even distribution** - Avoid hot partitions
2. **Bounded size** - < 100MB per partition
3. **Query alignment** - Support primary access patterns

**WellWon Pattern:**

```sql
PRIMARY KEY ((channel_id, bucket), message_id)
```

- `(channel_id, bucket)` = Partition key (composite)
- `message_id` = Clustering key

### Bucket Strategy

Buckets prevent unbounded partition growth:

```python
def calculate_message_bucket(snowflake_id: int) -> int:
    """Calculate 10-day bucket from Snowflake ID."""
    EPOCH = 1704067200000  # 2024-01-01 UTC
    BUCKET_SIZE_MS = 10 * 24 * 60 * 60 * 1000  # 10 days

    timestamp_ms = (snowflake_id >> 22) + EPOCH
    return int(timestamp_ms // BUCKET_SIZE_MS)
```

### Clustering Order

```sql
WITH CLUSTERING ORDER BY (message_id DESC)
```

- `DESC` for "newest first" queries (most common)
- Enables efficient range scans within partition

---

## 3. Client Usage

### Getting the Client

```python
from app.infra.persistence.scylladb import get_scylla_client

async def my_function():
    client = get_scylla_client()

    # Execute query
    result = await client.execute(
        "SELECT * FROM messages WHERE channel_id = ? AND bucket = ?",
        (channel_id, bucket)
    )
```

### Prepared Statements

The client automatically caches prepared statements (LRU, max 1000):

```python
# First call prepares and caches
result = await client.execute(query, params)

# Subsequent calls use cached prepared statement
result = await client.execute(query, params)
```

### Consistency Levels

```python
from cassandra import ConsistencyLevel

# Read with LOCAL_ONE (fast)
result = await client.execute(
    query,
    params,
    consistency_level=ConsistencyLevel.LOCAL_ONE
)

# Write with LOCAL_QUORUM (durable)
await client.execute(
    query,
    params,
    consistency_level=ConsistencyLevel.LOCAL_QUORUM
)
```

---

## 4. Repository Pattern

### MessageScyllaRepo

```python
from app.infra.read_repos.message_scylla_repo import (
    MessageScyllaRepo,
    MessageData,
)

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

# Get single message
message = await repo.get_message(
    channel_id=chat_id,
    message_id=snowflake_id,
)

# Find by Telegram ID (O(1) via mapping table)
message = await repo.get_message_by_telegram_id(
    channel_id=chat_id,
    telegram_message_id=123456,
    telegram_chat_id=telegram_chat_id,
)

# Soft delete
await repo.delete_message(
    channel_id=chat_id,
    message_id=snowflake_id,
)
```

### MessageData Model

```python
class MessageData(BaseModel):
    channel_id: uuid.UUID
    message_id: Optional[int] = None  # Snowflake ID (auto-generated)
    bucket: Optional[int] = None      # Auto-calculated
    sender_id: Optional[uuid.UUID] = None
    content: Optional[str] = None
    message_type: str = "text"
    reply_to_id: Optional[int] = None

    # File attachments
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    voice_duration: Optional[int] = None

    # Telegram integration
    telegram_message_id: Optional[int] = None
    telegram_chat_id: Optional[int] = None
    telegram_user_id: Optional[int] = None
    telegram_user_data: Optional[str] = None  # JSON

    # Source tracking
    source: str = "web"  # web, telegram, api

    # Status
    is_edited: bool = False
    is_deleted: bool = False
```

---

## 5. Snowflake IDs

### Structure

```
┌─────────────────────────────────────────────────────────────┐
│  42 bits timestamp  │  10 bits worker  │  12 bits sequence  │
└─────────────────────────────────────────────────────────────┘
```

### Generation

```python
from app.infra.persistence.scylladb import generate_snowflake_id

# Generate new ID
message_id = generate_snowflake_id()

# Extract timestamp
def extract_timestamp(snowflake_id: int) -> datetime:
    EPOCH = 1704067200000  # 2024-01-01 UTC
    timestamp_ms = (snowflake_id >> 22) + EPOCH
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
```

### Benefits

1. **Time-ordered** - Chronologically sortable
2. **Globally unique** - No coordination needed
3. **Compact** - 64-bit integer (bigint)
4. **High throughput** - ~4M IDs/second/worker

---

## 6. Best Practices

### DO

```python
# Use prepared statements (automatic via client)
await client.execute(query, params)

# Specify partition key in queries
await client.execute(
    "SELECT * FROM messages WHERE channel_id = ? AND bucket = ?",
    (channel_id, bucket)
)

# Use appropriate consistency levels
# Reads: LOCAL_ONE (fast)
# Writes: LOCAL_QUORUM (durable)

# Batch related writes
from cassandra.query import BatchStatement
batch = BatchStatement()
batch.add(insert_message_query, message_params)
batch.add(insert_mapping_query, mapping_params)
await client.execute(batch)
```

### DON'T

```python
# Don't use ALLOW FILTERING
# BAD:
"SELECT * FROM messages WHERE content LIKE '%search%' ALLOW FILTERING"

# Don't create secondary indexes on high-cardinality columns
# BAD:
"CREATE INDEX ON messages (telegram_message_id)"

# Don't use SELECT *
# BAD:
"SELECT * FROM messages"
# GOOD:
"SELECT channel_id, message_id, content, sender_id FROM messages"

# Don't ignore partition key
# BAD:
"SELECT * FROM messages WHERE message_id = ?"
# GOOD:
"SELECT * FROM messages WHERE channel_id = ? AND bucket = ? AND message_id = ?"
```

---

## 7. Anti-Patterns to Avoid

### 1. Unbounded Partitions

```sql
-- BAD: Partition grows forever
PRIMARY KEY (channel_id, message_id)

-- GOOD: Bounded by time bucket
PRIMARY KEY ((channel_id, bucket), message_id)
```

### 2. Secondary Indexes on High-Cardinality

```sql
-- BAD: Full table scan
CREATE INDEX ON messages (telegram_message_id);

-- GOOD: Dedicated lookup table
CREATE TABLE telegram_message_mapping (
    telegram_message_id bigint,
    telegram_chat_id bigint,
    channel_id uuid,
    bucket int,
    message_id bigint,
    PRIMARY KEY ((telegram_message_id, telegram_chat_id))
);
```

### 3. Re-preparing Statements

```python
# BAD: Prepares every time
for msg in messages:
    stmt = await session.prepare(query)
    await session.execute(stmt, params)

# GOOD: Use client's LRU cache (automatic)
for msg in messages:
    await client.execute(query, params)
```

### 4. ALLOW FILTERING

```sql
-- BAD: Sequential scan
SELECT * FROM messages WHERE content = 'hello' ALLOW FILTERING;

-- GOOD: Query by partition key, filter in application
SELECT * FROM messages WHERE channel_id = ? AND bucket = ?
-- Then filter in Python
```

---

## 8. Testing

### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_scylla_client():
    client = MagicMock()
    client.execute = AsyncMock(return_value=[])
    return client

async def test_insert_message(mock_scylla_client):
    repo = MessageScyllaRepo(client=mock_scylla_client)

    message = MessageData(
        channel_id=uuid.uuid4(),
        content="Test",
        sender_id=uuid.uuid4(),
    )

    result = await repo.insert_message(message)

    assert result is not None
    mock_scylla_client.execute.assert_called()
```

### Integration Tests

```python
@pytest.mark.integration
async def test_message_roundtrip():
    repo = MessageScyllaRepo()

    # Insert
    message = MessageData(
        channel_id=test_channel_id,
        content="Integration test message",
        sender_id=test_user_id,
    )
    message_id = await repo.insert_message(message)

    # Retrieve
    retrieved = await repo.get_message(
        channel_id=test_channel_id,
        message_id=message_id,
    )

    assert retrieved.content == "Integration test message"

    # Cleanup
    await repo.delete_message(
        channel_id=test_channel_id,
        message_id=message_id,
    )
```

---

## 9. Troubleshooting

### Connection Issues

```python
# Check connectivity
from app.infra.persistence.scylladb import check_connection_health

health = await check_connection_health(client)
print(health)  # {'status': 'healthy', 'latency_ms': 2.5}
```

### Slow Queries

1. Check if query uses partition key
2. Verify no ALLOW FILTERING
3. Check prepared statement cache hit rate
4. Review consistency level

### Tombstone Warnings

If seeing tombstone warnings:

1. Check `gc_grace_seconds` (should be 86400 for TWCS)
2. Verify TWCS compaction is running
3. Avoid frequent deletes (use soft deletes)

### Hot Partitions

Monitor partition size:

```sql
SELECT partition_key, estimated_partition_size_in_mb
FROM system.size_estimates
WHERE keyspace_name = 'wellwon_scylla' AND table_name = 'messages';
```

If partitions exceed 100MB, reduce bucket size.

---

## References

- [ScyllaDB Documentation](https://docs.scylladb.com/)
- [ScyllaDB University](https://university.scylladb.com/)
- [Discord Architecture Blog](https://discord.com/blog/how-discord-stores-trillions-of-messages)
- [ScyllaDB Python Driver](https://python-driver.docs.scylladb.com/)
