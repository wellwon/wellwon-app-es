# Database Distribution Analysis: PostgreSQL vs ScyllaDB

**Date:** 2025-11-30
**Based on:** Discord Architecture, ScyllaDB Best Practices

---

## Executive Summary

After analyzing WellWon's tables against Discord's architecture and ScyllaDB best practices, the current distribution is **CORRECT**. Most tables should remain in PostgreSQL as they contain relational metadata requiring JOINs and ACID transactions.

**Key Principle from Discord:**
> ScyllaDB stores **messages only** (trillions of high-volume records).
> PostgreSQL stores **everything else** (users, channels, permissions, metadata).

---

## Industry Best Practices

### When to Use ScyllaDB
| Use Case | Reason |
|----------|--------|
| High-volume time-series data | Partition by time, TWCS compaction |
| Simple key-value access | No JOINs needed |
| Write-heavy workloads | Distributed writes |
| Immutable/append-only data | Messages, events, logs |

### When to Use PostgreSQL
| Use Case | Reason |
|----------|--------|
| Complex queries with JOINs | Relational model |
| ACID transactions | Authentication, payments |
| Full-text search | Built-in FTS |
| Small reference tables | Users, configs, templates |
| Data requiring integrity constraints | Foreign keys |

**Source:** [ScyllaDB Data Modeling Best Practices](https://docs.scylladb.com/stable/get-started/data-modeling/best-practices.html)

---

## Discord's Architecture Reference

```
┌─────────────────────────────────────────────────────────────────┐
│                    DISCORD DATA DISTRIBUTION                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ScyllaDB (72 nodes)              PostgreSQL                    │
│  ┌─────────────────────┐          ┌─────────────────────────┐  │
│  │                     │          │                         │  │
│  │  • Messages ONLY    │          │  • User accounts        │  │
│  │  • Trillions of     │          │  • Guilds (servers)     │  │
│  │    records          │          │  • Channels             │  │
│  │  • High throughput  │          │  • Permissions          │  │
│  │                     │          │  • All metadata         │  │
│  └─────────────────────┘          └─────────────────────────┘  │
│                                                                  │
│  Redis                            S3                            │
│  ┌─────────────────────┐          ┌─────────────────────────┐  │
│  │  • Presence         │          │  • Images               │  │
│  │  • Caching          │          │  • Videos               │  │
│  │  • Sessions         │          │  • Files                │  │
│  └─────────────────────┘          └─────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Source:** [How Discord Stores Trillions of Messages](https://discord.com/blog/how-discord-stores-trillions-of-messages)

---

## WellWon Table Analysis

### Tables That MUST Stay in PostgreSQL

| Table | Reason | Volume |
|-------|--------|--------|
| `user_accounts` | ACID for auth, JOINs everywhere | Low |
| `companies` | JOINs with users, business logic | Low |
| `user_companies` | Many-to-many relational | Low |
| `chats` | JOINs with users/companies, auth checks | Medium |
| `chat_participants` | Authorization, JOINs with users | Medium |
| `telegram_supergroups` | JOINs with companies | Low |
| `telegram_users` | Reference data, JOINs | Low |
| `message_templates` | CRUD, JOINs with users | Low |
| `news` | CMS content | Low |
| `currencies` | Reference data | Tiny |

### Event Sourcing Infrastructure (MUST Stay in PostgreSQL)

| Table | Reason |
|-------|--------|
| `event_outbox` | Transactional outbox pattern requires ACID |
| `processed_events` | Complex queries, aggregations |
| `projection_checkpoints` | Reference data |
| `dlq_events` | Recovery workflows, complex queries |
| `audit_logs` | Compliance, complex queries |
| `system_logs` | Debugging, complex queries |
| `schema_migrations` | Reference data |

### Tables Already Optimized

| Table | Current State | Status |
|-------|--------------|--------|
| `messages` | Search index only (ScyllaDB is primary) | ✅ CORRECT |
| `message_reads` | REMOVED (ScyllaDB `message_read_positions`) | ✅ CORRECT |

### Tables to Remove/Move

| Table | Current | Recommendation |
|-------|---------|----------------|
| `typing_indicators` | PostgreSQL fallback | **REMOVE** - Redis only |
| `telegram_group_members` | PostgreSQL | **KEEP** - needs JOINs for display |

---

## Detailed Recommendations

### 1. `messages` Table - KEEP AS IS ✅

**Current state:** Simplified search index pointing to ScyllaDB

```sql
-- PostgreSQL (search index)
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    chat_id UUID NOT NULL,
    sender_id UUID,
    scylla_message_id BIGINT NOT NULL,  -- Reference to ScyllaDB
    scylla_bucket INT,
    content TEXT,  -- For full-text search
    ...
);
```

**Why keep:**
- PostgreSQL has superior full-text search
- Enables JOINs: `SELECT m.*, u.username FROM messages m JOIN user_accounts u...`
- Chat list preview with user info

**Why NOT move to ScyllaDB:**
- ScyllaDB doesn't support JOINs
- Would need to denormalize user data into every message
- Full-text search would require external system (Elasticsearch)

### 2. `message_templates` - KEEP IN PostgreSQL ✅

**Analysis:**
- Small table (~100-1000 rows)
- CRUD operations, not high-volume
- Needs JOINs: `SELECT t.*, u.username as created_by_name FROM message_templates t JOIN user_accounts u...`
- Used in UI dropdowns

**Verdict:** Not a candidate for ScyllaDB

### 3. `chats` Table - KEEP IN PostgreSQL ✅

**Analysis:**
- Medium volume (~10k-100k rows)
- Needs JOINs for chat list:
  ```sql
  SELECT c.*,
         comp.name as company_name,
         u.username as creator_name
  FROM chats c
  LEFT JOIN companies comp ON c.company_id = comp.id
  LEFT JOIN user_accounts u ON c.created_by = u.id
  ```
- Authorization checks require participant lookups
- Used for complex queries (search, filter by company, etc.)

**Verdict:** Keep in PostgreSQL

**Note:** ScyllaDB `channel_metadata` is a **denormalized copy** for ScyllaDB-only queries (when fetching messages without needing JOINs)

### 4. `chat_participants` - KEEP IN PostgreSQL ✅

**Analysis:**
- Authorization: "Is user X in chat Y?"
- Needs JOINs for participant list with user details
- Unread tracking via `last_read_at`

**Verdict:** Keep in PostgreSQL for authorization and JOINs

### 5. `typing_indicators` - REMOVE FROM PostgreSQL ⚠️

**Analysis:**
- 10-second TTL ephemeral data
- Redis is the correct store
- PostgreSQL fallback adds complexity without benefit

**Recommendation:** Remove table, use Redis only

### 6. Telegram Tables - KEEP IN PostgreSQL ✅

| Table | Reason |
|-------|--------|
| `telegram_supergroups` | JOINs with companies, low volume |
| `telegram_group_members` | JOINs with users for display |
| `telegram_users` | Reference data, link to user_accounts |

**ScyllaDB already handles:**
- `telegram_sync_state` - Sync tracking per channel
- `telegram_message_mapping` - O(1) dedup lookup

---

## What ScyllaDB Already Has (Correct)

| Table | Purpose | Volume |
|-------|---------|--------|
| `messages` | Primary message storage | High |
| `telegram_message_mapping` | O(1) Telegram dedup | High |
| `message_reactions` | Individual reactions | High |
| `message_reaction_counts` | Aggregated counts | High |
| `pinned_messages` | Pinned per channel | Medium |
| `telegram_sync_state` | Sync tracking | Low |
| `channel_metadata` | Denormalized channel info | Low |
| `message_read_positions` | Read position tracking | High |

---

## Final Recommendation

### DO NOT MOVE to ScyllaDB:
- ❌ `chats` - Needs JOINs
- ❌ `chat_participants` - Authorization, JOINs
- ❌ `message_templates` - Small reference table
- ❌ `telegram_supergroups` - JOINs with companies
- ❌ `telegram_group_members` - JOINs with users
- ❌ `telegram_users` - Reference data

### REMOVE from PostgreSQL:
- ⚠️ `typing_indicators` - Use Redis only

### KEEP AS IS:
- ✅ `messages` (search index) - Correct
- ✅ All ScyllaDB tables - Correct
- ✅ All PostgreSQL metadata tables - Correct

---

## Summary

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    WELLWON DATA DISTRIBUTION (FINAL)                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ScyllaDB (High-Volume)               PostgreSQL (Metadata + Search)    │
│  ┌───────────────────────────┐        ┌─────────────────────────────┐  │
│  │ messages                  │        │ user_accounts               │  │
│  │ telegram_message_mapping  │        │ companies                   │  │
│  │ message_reactions         │        │ user_companies              │  │
│  │ message_reaction_counts   │        │ chats                       │  │
│  │ pinned_messages           │        │ chat_participants           │  │
│  │ telegram_sync_state       │        │ messages (search index)     │  │
│  │ channel_metadata          │        │ telegram_supergroups        │  │
│  │ message_read_positions    │        │ telegram_group_members      │  │
│  └───────────────────────────┘        │ telegram_users              │  │
│                                        │ message_templates           │  │
│  Redis (Ephemeral)                    │ news, currencies            │  │
│  ┌───────────────────────────┐        │ event_outbox, audit_logs    │  │
│  │ typing:{chat}:{user}      │        │ processed_events, dlq       │  │
│  │ presence:{user}           │        └─────────────────────────────┘  │
│  │ cache:*                   │                                         │
│  └───────────────────────────┘                                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Conclusion:** Current distribution is correct. Only change needed is removing `typing_indicators` from PostgreSQL (Redis-only).

---

## Sources

- [How Discord Stores Trillions of Messages](https://discord.com/blog/how-discord-stores-trillions-of-messages)
- [ScyllaDB Data Modeling Best Practices](https://docs.scylladb.com/stable/get-started/data-modeling/best-practices.html)
- [ScyllaDB vs PostgreSQL](https://www.scylladb.com/2024/01/16/migrating-from-postgres-to-scylladb/)
- [Discord Migrated to ScyllaDB - InfoQ](https://www.infoq.com/news/2023/06/discord-cassandra-scylladb/)
