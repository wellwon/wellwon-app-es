# Chat Domain Architecture

## Overview

The Chat domain uses a **Discord-style architecture** optimized for high-volume messaging:

- **ScyllaDB** = PRIMARY for message content (trillions of messages)
- **PostgreSQL** = METADATA only (chat list, participants, last_message preview)

## Why No Sequence Tracking?

Chat domain has `enable_sequence_tracking=False` because:

### 1. Snowflake IDs Provide Ordering

Messages use 64-bit Snowflake IDs (Twitter/Discord pattern):

```
┌─────────────────────────────────────────────────────────────────┐
│ 41 bits: timestamp │ 10 bits: worker │ 12 bits: sequence       │
└─────────────────────────────────────────────────────────────────┘
```

- Chronologically sortable by ID alone
- No separate sequence counter needed
- Distributed generation without coordination

### 2. High Volume = Bottleneck Risk

Traditional sequence tracking requires:
- Central sequence counter (single point of failure)
- Redis lookup per message (latency overhead)
- Single-threaded processing (no parallelism)

At Discord scale (trillions of messages), this becomes a severe bottleneck.

### 3. Different Consistency Model

| Aspect | User/Company | Chat |
|--------|-------------|------|
| Volume | ~100 events/aggregate | Millions of messages |
| Ordering | Strict sequence | Snowflake (timestamp-based) |
| Consistency | Strong | Eventual |
| Idempotency | By sequence | By Snowflake ID |

## Message Flow

```
SendMessage API
      ↓
MessageSent Event → Kafka (transport.chat-events)
      ↓
Worker (no sequence check)
      ↓
┌─────────────────────────────────────────┐
│ ScyllaDB: INSERT message                │
│ (idempotent by Snowflake ID)            │
├─────────────────────────────────────────┤
│ PostgreSQL: UPDATE chat.last_message_*  │
│ (metadata preview only)                 │
└─────────────────────────────────────────┘
      ↓
WSE → Frontend (real-time update)
```

## Idempotency Without Sequence Tracking

Messages are idempotent via deterministic Snowflake ID:

```python
# projectors.py - MessageSent handler
message_uuid = uuid.UUID(event_data['message_id'])
deterministic_snowflake = int.from_bytes(message_uuid.bytes[:8], byteorder='big') & 0x7FFFFFFFFFFFFFFF
```

ScyllaDB's PRIMARY KEY prevents duplicates:
```sql
PRIMARY KEY ((channel_id, bucket), message_id)
```

## References

- [Discord: How Discord Stores Trillions of Messages](https://discord.com/blog/how-discord-stores-trillions-of-messages)
- [Sequence Tracking](../architecture/SEQUENCE_TRACKING.md)

## Files

- `app/chat/projectors.py` - Event projectors
- `app/infra/read_repos/message_scylla_repo.py` - ScyllaDB repository
- `app/infra/worker_core/event_processor/domain_registry.py:278` - Sequence tracking disabled
