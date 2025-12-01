# External Change Detection & Compensating Event Pattern

## Integration Guide for Event-Sourced Systems

**Version:** 1.0
**Date:** November 2025
**Pattern:** Compensating Event + Transactional Outbox
**Validated by:** Greg Young, Martin Fowler, Confluent, Debezium

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Architecture Overview](#2-architecture-overview)
3. [Pattern Validation (Industry Sources)](#3-pattern-validation-industry-sources)
4. [Implementation Guide](#4-implementation-guide)
5. [SQL Triggers](#5-sql-triggers)
6. [Outbox Table Schema](#6-outbox-table-schema)
7. [Outbox Processor](#7-outbox-processor)
8. [Event Definitions](#8-event-definitions)
9. [Projector Handlers](#9-projector-handlers)
10. [Testing & Validation](#10-testing--validation)
11. [Monitoring & Alerting](#11-monitoring--alerting)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Problem Statement

### The Bypass Problem

In event-sourced systems, all state changes should flow through aggregates:

```
Normal Flow:
Command -> Aggregate -> Domain Event -> EventStore -> Projector -> Read Model
```

**Problem:** External actors (DBAs, scripts, migrations) can bypass aggregates:

```
Bypass Flow:
SQL UPDATE/DELETE -> Database (Read Model) -> ??? (EventStore never sees it)
```

**Consequences:**
- EventStore missing events (incomplete audit trail)
- Projection rebuild produces wrong state
- No WebSocket notifications to frontend
- Compliance violations (10-year audit requirement)

### Real-World Scenarios

| Scenario | Impact |
|----------|--------|
| DBA deletes user via SQL | User data gone, no audit trail |
| Script changes user role | Sessions not invalidated, security risk |
| Migration deletes old orders | Historical data lost for EventStore replay |
| Manual broker disconnect | WebSocket not notified, UI shows stale state |

---

## 2. Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL CHANGE DETECTION                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────────┐   │
│  │ External     │    │ PostgreSQL   │    │ event_outbox table           │   │
│  │ SQL Change   │───>│ TRIGGER      │───>│ (Transactional Outbox)       │   │
│  │ (DBA/Script) │    │ AFTER DELETE │    │                              │   │
│  └──────────────┘    │ AFTER UPDATE │    └──────────────┬───────────────┘   │
│                      └──────────────┘                   │                   │
│                                                         │ LISTEN/NOTIFY     │
│                                                         │ (instant)         │
│                                                         ▼                   │
│                                           ┌─────────────────────────────┐   │
│                                           │ OutboxProcessor             │   │
│                                           │ (polls or listens)          │   │
│                                           └──────────────┬──────────────┘   │
│                                                          │                  │
│                              ┌────────────────────────────┴────────────┐    │
│                              │                                         │    │
│                              ▼                                         ▼    │
│                   ┌──────────────────┐                    ┌─────────────────┐
│                   │ EventStore       │                    │ EventBus        │
│                   │ (KurrentDB)      │                    │ (Redpanda/Kafka)│
│                   │                  │                    │                 │
│                   │ - 10 year retain │                    │ - 7 day retain  │
│                   │ - Audit trail    │                    │ - Real-time     │
│                   │ - Replay/rebuild │                    │ - Kafka ecosys  │
│                   └────────┬─────────┘                    └────────┬────────┘
│                            │                                       │        │
│                            │ Catch-up Subscription                 │        │
│                            ▼                                       ▼        │
│                   ┌──────────────────┐                    ┌─────────────────┐
│                   │ Projector        │                    │ Worker          │
│                   │ (rebuild mode)   │                    │ (real-time)     │
│                   └────────┬─────────┘                    └────────┬────────┘
│                            │                                       │        │
│                            └───────────────────┬───────────────────┘        │
│                                                │                            │
│                                                ▼                            │
│                                    ┌───────────────────────┐                │
│                                    │ WebSocket Engine      │                │
│                                    │ (notify frontend)     │                │
│                                    └───────────────────────┘                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Event Flow Comparison

| Scenario | Event Type | Source | EventStore | EventBus | Recovery |
|----------|-----------|--------|------------|----------|----------|
| User clicks Disconnect | `BrokerDisconnected` | Aggregate | Yes | Yes | N/A |
| DBA deletes connection | `BrokerConnectionDeletedExternally` | Trigger | Yes | Yes | OAuth re-auth |
| Script changes role | `UserRoleChangedExternally` | Trigger | Yes | Yes | Session invalidation |
| Migration deletes order | `OrderDeletedExternally` | Trigger | Yes | Yes | Refetch from broker |

### Dual Destination Pattern

```
                    ┌─────────────────────────────────────────┐
                    │           OutboxProcessor               │
                    │                                         │
                    │  if (compensating_event):               │
                    │      await write_to_eventstore()  ──────┼──> EventStore (REQUIRED)
                    │                                         │    - Source of Truth
                    │  await publish_to_eventbus()      ──────┼──> EventBus (REQUIRED)
                    │                                         │    - Real-time transport
                    └─────────────────────────────────────────┘
```

**Why dual destination?**

| Destination | Purpose | Retention | Use Case |
|-------------|---------|-----------|----------|
| EventStore (KurrentDB) | Source of Truth | 10 years | Audit, compliance, projection rebuild |
| EventBus (Redpanda) | Transport | 7 days | Real-time processing, Kafka ecosystem |

---

## 3. Pattern Validation (Industry Sources)

### Greg Young (Event Sourcing Creator)

**Source:** [Kurrent.io - Event Sourcing and CQRS](https://www.kurrent.io/blog/event-sourcing-and-cqrs)

> "The only way to update an entity or undo a change is to add a **compensating event** to the event store."

> "Write a new fact that supersedes the old fact."

**KurrentDB Outbox Pattern:**
> "The stream is the outbox, out of the box. Like a database table, the stream provides atomic, durable, and immediately consistent operations."

**Source:** [Kurrent Docs - Outbox Pattern](https://docs.kurrent.io/dev-center/use-cases/outbox/introduction)

### Martin Fowler

**Source:** [martinfowler.com - Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)

> "The event store becomes the **principal source of truth**, and the system state is purely derived from it."

> "You can't update application state before writing to the event log because then you have a working state that is ahead of the event log state."

### Confluent (Kafka Creators)

**Source:** [Confluent - Dual Write Problem](https://www.confluent.io/blog/dual-write-problem/)

> "Kafka alone cannot ensure reliable data exchange. You might need to use the **transactional outbox**."

> "The transactional outbox pattern solves the dual-write problem - ensuring consistency between a local database and a message broker."

### Debezium (Red Hat)

**Source:** [Debezium - Outbox Pattern](https://debezium.io/blog/2019/02/19/reliable-microservices-data-exchange-with-the-outbox-pattern/)

> "Log-based Change Data Capture (CDC) is a great fit for capturing new entries in the outbox table."

> "The primary goal of the Outbox Pattern is to ensure that updates to the application state and publishing of the respective domain event is done within a **single transaction**."

### Microservices.io (Chris Richardson)

**Source:** [microservices.io - Transactional Outbox](https://microservices.io/patterns/data/transactional-outbox.html)

> "To atomically update the database and send messages to a message broker, the transactional outbox is the **simplest solution** that can be implemented, and it should be your **first choice**."

### Microsoft Azure

**Source:** [Microsoft - Event Sourcing Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)

> "The existing data in an event sourcing store isn't updated. Instead, **new entries are added** that transition the state of entities to the new values."

> "The requirement to use compensating events to cancel changes can provide a **history of changes that were reversed**."

---

## 4. Implementation Guide

### Prerequisites

1. PostgreSQL 12+ (for LISTEN/NOTIFY, triggers)
2. Event Store (KurrentDB/EventStoreDB or similar)
3. Message Broker (Redpanda/Kafka)
4. Async Python 3.10+ (asyncpg, aiokafka)

### Implementation Steps

```
Step 1: Create event_outbox table
         │
         ▼
Step 2: Create PostgreSQL triggers for each table
         │
         ▼
Step 3: Implement OutboxProcessor service
         │
         ▼
Step 4: Define compensating event classes
         │
         ▼
Step 5: Implement projector handlers
         │
         ▼
Step 6: Configure LISTEN/NOTIFY for instant processing
         │
         ▼
Step 7: Set up monitoring and alerting
```

---

## 5. SQL Triggers

### Trigger Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Table: orders   │     │ Table: users    │     │ Table: conns    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
    AFTER DELETE            AFTER UPDATE             AFTER DELETE
    AFTER UPDATE            (role, status)           AFTER UPDATE
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      event_outbox table                          │
│  (event_type, event_data, topic, status, metadata)              │
└─────────────────────────────────────────────────────────────────┘
         │
         │ pg_notify('outbox_events', event_id)
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OutboxProcessor                             │
│  LISTEN 'outbox_events' -> instant processing                   │
└─────────────────────────────────────────────────────────────────┘
```

### Generic Trigger Template

```sql
-- =============================================================================
-- GENERIC TRIGGER TEMPLATE FOR EXTERNAL CHANGE DETECTION
-- Pattern: Compensating Event via Transactional Outbox
-- =============================================================================

CREATE OR REPLACE FUNCTION notify_{table}_deleted()
RETURNS TRIGGER AS $$
DECLARE
    v_next_version INTEGER;
BEGIN
    -- Get next aggregate version (for ordering)
    SELECT COALESCE(MAX(aggregate_version), 0) + 1 INTO v_next_version
    FROM event_outbox
    WHERE aggregate_id = OLD.id AND aggregate_type = '{AggregateType}';

    -- Insert compensating event into outbox
    INSERT INTO event_outbox (
        event_id,
        aggregate_id,
        aggregate_type,
        aggregate_version,
        event_type,
        event_data,
        topic,
        partition_key,
        status,
        priority,
        metadata,
        created_at
    ) VALUES (
        gen_random_uuid(),
        OLD.id,
        '{AggregateType}',
        v_next_version,
        '{AggregateType}DeletedExternally',
        jsonb_build_object(
            'event_type', '{AggregateType}DeletedExternally',
            '{id_field}', OLD.id::text,
            'user_id', OLD.user_id::text,
            -- Add other relevant fields from OLD record
            'deleted_at', NOW()::text,
            'deleted_by', 'EXTERNAL_SQL',
            'detection_method', 'trigger',
            'recovery_action', '{recovery_action}',
            'original_data', row_to_json(OLD)::jsonb
        ),
        '{transport_topic}',
        OLD.{partition_key}::text,
        'pending',
        {priority},  -- 5 for saga, 10 for domain
        jsonb_build_object(
            'write_to_eventstore', true,
            'detection_method', 'trigger',
            'changed_by', 'EXTERNAL_SQL',
            'severity', '{severity}',
            'compensating_event', true
        ),
        NOW()
    );

    -- Instant notification via LISTEN/NOTIFY
    PERFORM pg_notify('outbox_events', OLD.id::text);

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS after_{table}_delete ON {table};
CREATE TRIGGER after_{table}_delete
AFTER DELETE ON {table}
FOR EACH ROW
EXECUTE FUNCTION notify_{table}_deleted();
```

### Concrete Examples

#### Example 1: Order Deletion

```sql
CREATE OR REPLACE FUNCTION notify_order_deleted()
RETURNS TRIGGER AS $$
DECLARE
    v_next_version INTEGER;
    v_broker_connection_id UUID;
BEGIN
    -- Get broker_connection_id from account
    SELECT broker_connection_id INTO v_broker_connection_id
    FROM broker_accounts
    WHERE id = OLD.account_id;

    SELECT COALESCE(MAX(aggregate_version), 0) + 1 INTO v_next_version
    FROM event_outbox
    WHERE aggregate_id = OLD.id AND aggregate_type = 'Order';

    INSERT INTO event_outbox (
        event_id, aggregate_id, aggregate_type, aggregate_version,
        event_type, event_data, topic, partition_key, status, priority,
        metadata, created_at
    ) VALUES (
        gen_random_uuid(),
        OLD.id,
        'Order',
        v_next_version,
        'OrderDeletedExternally',
        jsonb_build_object(
            'event_type', 'OrderDeletedExternally',
            'order_id', OLD.id::text,
            'user_id', OLD.user_id::text,
            'account_id', OLD.account_id::text,
            'broker_connection_id', v_broker_connection_id::text,
            'symbol', OLD.symbol,
            'side', OLD.side,
            'quantity', OLD.quantity::text,
            'order_type', OLD.order_type,
            'status', OLD.status,
            'broker_order_id', OLD.broker_order_id,
            'deleted_at', NOW()::text,
            'deleted_by', 'EXTERNAL_SQL',
            'detection_method', 'trigger',
            'recovery_action', 'refetch_from_broker',
            'original_data', row_to_json(OLD)::jsonb
        ),
        'transport.order-events',
        OLD.account_id::text,
        'pending',
        10,  -- Domain priority
        jsonb_build_object(
            'write_to_eventstore', true,
            'compensating_event', true,
            'changed_by', 'EXTERNAL_SQL',
            'severity', 'HIGH'
        ),
        NOW()
    );

    PERFORM pg_notify('outbox_events', OLD.id::text);
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS after_order_delete ON orders;
CREATE TRIGGER after_order_delete
AFTER DELETE ON orders
FOR EACH ROW
EXECUTE FUNCTION notify_order_deleted();
```

#### Example 2: User Role Change

```sql
CREATE OR REPLACE FUNCTION notify_user_role_changed()
RETURNS TRIGGER AS $$
BEGIN
    -- Only trigger if role actually changed
    IF OLD.role IS DISTINCT FROM NEW.role THEN
        INSERT INTO event_outbox (
            event_id, aggregate_id, aggregate_type, aggregate_version,
            event_type, event_data, topic, partition_key, status, priority,
            metadata, created_at
        ) VALUES (
            gen_random_uuid(),
            NEW.id,
            'UserAccount',
            1,
            'UserRoleChangedExternally',
            jsonb_build_object(
                'event_type', 'UserRoleChangedExternally',
                'user_id', NEW.id::text,
                'username', NEW.username,
                'old_role', OLD.role,
                'new_role', NEW.role,
                'changed_at', NOW()::text,
                'changed_by', 'EXTERNAL_SQL',
                'detection_method', 'trigger',
                'action_required', 'Invalidate all user sessions',
                'severity', 'HIGH'
            ),
            'transport.user-account-events',
            NEW.id::text,
            'pending',
            10,
            jsonb_build_object(
                'write_to_eventstore', true,
                'compensating_event', true,
                'changed_by', 'EXTERNAL_SQL',
                'severity', 'CRITICAL',
                'security_impact', true
            ),
            NOW()
        );

        PERFORM pg_notify('outbox_events', NEW.id::text);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS after_user_role_update ON user_accounts;
CREATE TRIGGER after_user_role_update
AFTER UPDATE OF role ON user_accounts
FOR EACH ROW
EXECUTE FUNCTION notify_user_role_changed();
```

#### Example 3: Broker Connection Deletion (Non-Recoverable)

```sql
CREATE OR REPLACE FUNCTION notify_broker_connection_deleted()
RETURNS TRIGGER AS $$
DECLARE
    v_next_version INTEGER;
BEGIN
    SELECT COALESCE(MAX(aggregate_version), 0) + 1 INTO v_next_version
    FROM event_outbox
    WHERE aggregate_id = OLD.id AND aggregate_type = 'BrokerConnection';

    INSERT INTO event_outbox (
        event_id, aggregate_id, aggregate_type, aggregate_version,
        event_type, event_data, topic, partition_key, status, priority,
        metadata, created_at
    ) VALUES (
        gen_random_uuid(),
        OLD.id,
        'BrokerConnection',
        v_next_version,
        'BrokerConnectionDeletedExternally',
        jsonb_build_object(
            'event_type', 'BrokerConnectionDeletedExternally',
            'connection_id', OLD.id::text,
            'user_id', OLD.user_id::text,
            'broker_id', OLD.broker_id,
            'environment', OLD.environment,
            'deleted_at', NOW()::text,
            'deleted_by', 'EXTERNAL_SQL',
            'detection_method', 'trigger',
            'recovery_method', 'none',  -- Non-recoverable!
            'alert_user', true,
            'severity', 'HIGH',
            'action_required', 'User must reconnect via OAuth',
            'original_data', row_to_json(OLD)::jsonb
        ),
        'saga.external-changes',  -- Saga topic for coordination
        OLD.user_id::text,
        'pending',
        5,  -- Saga priority (higher than domain)
        jsonb_build_object(
            'write_to_eventstore', true,
            'compensating_event', true,
            'changed_by', 'EXTERNAL_SQL',
            'severity', 'CRITICAL',
            'saga_coordination', true
        ),
        NOW()
    );

    PERFORM pg_notify('outbox_events', OLD.id::text);
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS after_broker_connection_delete ON broker_connections;
CREATE TRIGGER after_broker_connection_delete
AFTER DELETE ON broker_connections
FOR EACH ROW
EXECUTE FUNCTION notify_broker_connection_deleted();
```

---

## 6. Outbox Table Schema

```sql
-- =============================================================================
-- EVENT OUTBOX TABLE
-- Pattern: Transactional Outbox (Chris Richardson, Confluent)
-- =============================================================================

CREATE TABLE IF NOT EXISTS event_outbox (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event identification
    event_id UUID NOT NULL UNIQUE,
    aggregate_id UUID NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_version INTEGER DEFAULT 1,
    event_type VARCHAR(100) NOT NULL,

    -- Event payload
    event_data JSONB NOT NULL,

    -- Transport routing
    topic VARCHAR(255) NOT NULL,
    partition_key VARCHAR(255),

    -- Processing state
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'published', 'failed', 'dead_letter')),
    priority INTEGER DEFAULT 10,
    publish_attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    last_attempt_at TIMESTAMPTZ,

    -- Error tracking
    last_error TEXT,
    last_error_at TIMESTAMPTZ,

    -- Correlation (for saga/distributed tracing)
    correlation_id UUID,
    causation_id UUID,
    saga_id UUID,

    -- Metadata (for routing decisions)
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for efficient polling
CREATE INDEX IF NOT EXISTS idx_outbox_pending
ON event_outbox (status, created_at)
WHERE status IN ('pending', 'failed');

CREATE INDEX IF NOT EXISTS idx_outbox_aggregate
ON event_outbox (aggregate_id, aggregate_version);

CREATE INDEX IF NOT EXISTS idx_outbox_event_type
ON event_outbox (event_type);

CREATE INDEX IF NOT EXISTS idx_outbox_topic
ON event_outbox (topic)
WHERE status = 'pending';

-- Optimized function for getting pending events (pre-compiled query plan)
CREATE OR REPLACE FUNCTION get_pending_outbox_events(
    p_max_attempts INT,
    p_cutoff_time TIMESTAMPTZ,
    p_created_after TIMESTAMPTZ,
    p_limit INT
)
RETURNS TABLE (
    id UUID,
    event_id UUID,
    aggregate_id UUID,
    aggregate_type VARCHAR,
    event_type VARCHAR,
    event_data JSONB,
    topic VARCHAR,
    partition_key VARCHAR,
    status VARCHAR,
    publish_attempts INT,
    last_attempt_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    last_error TEXT,
    correlation_id UUID,
    causation_id UUID,
    saga_id UUID,
    metadata JSONB,
    aggregate_version INT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        o.id, o.event_id, o.aggregate_id, o.aggregate_type, o.event_type,
        o.event_data, o.topic, o.partition_key, o.status, o.publish_attempts,
        o.last_attempt_at, o.published_at, o.last_error, o.correlation_id,
        o.causation_id, o.saga_id, o.metadata, o.aggregate_version, o.created_at
    FROM event_outbox o
    WHERE o.status IN ('pending', 'failed')
      AND o.publish_attempts < p_max_attempts
      AND (o.last_attempt_at IS NULL OR o.last_attempt_at < p_cutoff_time)
      AND o.created_at > p_created_after
    ORDER BY o.aggregate_id, o.aggregate_version, o.created_at, o.id
    LIMIT p_limit
    FOR UPDATE SKIP LOCKED;
END;
$$ LANGUAGE plpgsql;
```

---

## 7. Outbox Processor

### Python Implementation

```python
# outbox_processor.py
# Pattern: Transactional Outbox with LISTEN/NOTIFY

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import asyncpg

log = logging.getLogger("outbox.processor")


class OutboxStatus(Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class OutboxEntry:
    """Represents an entry in the event outbox"""
    id: str
    event_id: str
    aggregate_id: str
    aggregate_type: str
    event_type: str
    event_data: Dict[str, Any]
    topic: str
    partition_key: Optional[str]
    status: OutboxStatus
    publish_attempts: int
    metadata: Optional[Dict[str, Any]]
    aggregate_version: Optional[int]
    created_at: datetime


class OutboxProcessor:
    """
    Processes events from the outbox table and publishes to EventStore + EventBus.

    Pattern: Transactional Outbox with LISTEN/NOTIFY for near-zero latency.

    Sources:
    - Confluent: https://www.confluent.io/blog/dual-write-problem/
    - Debezium: https://debezium.io/blog/2019/02/19/reliable-microservices-data-exchange-with-the-outbox-pattern/
    - microservices.io: https://microservices.io/patterns/data/transactional-outbox.html
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        event_store,  # Your EventStore implementation
        event_bus,    # Your EventBus implementation (Kafka/Redpanda)
        batch_size: int = 100,
        poll_interval_seconds: float = 0.1,
        max_retry_attempts: int = 3,
    ):
        self.db_pool = db_pool
        self.event_store = event_store
        self.event_bus = event_bus
        self.batch_size = batch_size
        self.poll_interval = poll_interval_seconds
        self.max_retry_attempts = max_retry_attempts

        self._running = False
        self._notify_event = asyncio.Event()
        self._listen_connection: Optional[asyncpg.Connection] = None

    async def start(self):
        """Start the outbox processor with LISTEN/NOTIFY"""
        self._running = True

        # Start LISTEN task for instant notifications
        asyncio.create_task(self._listen_for_notifications())

        # Start main processing loop
        asyncio.create_task(self._processing_loop())

        log.info("OutboxProcessor started with LISTEN/NOTIFY support")

    async def stop(self):
        """Stop the outbox processor"""
        self._running = False
        if self._listen_connection:
            await self._listen_connection.close()
        log.info("OutboxProcessor stopped")

    async def _listen_for_notifications(self):
        """
        Listen for PostgreSQL NOTIFY events.

        Best Practice: Dedicated connection for LISTEN to get instant notifications.
        This provides CDC-like latency WITHOUT external dependencies (Debezium).
        """
        notification_queue = asyncio.Queue()

        def callback(connection, pid, channel, payload):
            notification_queue.put_nowait(payload)

        try:
            self._listen_connection = await self.db_pool.acquire()
            await self._listen_connection.add_listener('outbox_events', callback)
            log.info("PostgreSQL LISTEN started on channel 'outbox_events'")

            while self._running:
                try:
                    await asyncio.wait_for(notification_queue.get(), timeout=5.0)
                    self._notify_event.set()
                except asyncio.TimeoutError:
                    pass

        except Exception as e:
            log.error(f"LISTEN error: {e}")
        finally:
            if self._listen_connection:
                await self._listen_connection.remove_listener('outbox_events', callback)
                await self.db_pool.release(self._listen_connection)

    async def _processing_loop(self):
        """Main processing loop - combines NOTIFY events with fallback polling"""
        while self._running:
            try:
                # Wait for NOTIFY or timeout
                try:
                    await asyncio.wait_for(
                        self._notify_event.wait(),
                        timeout=self.poll_interval
                    )
                    self._notify_event.clear()
                except asyncio.TimeoutError:
                    pass

                # Process pending events
                entries = await self._get_pending_events()

                for entry in entries:
                    await self._process_entry(entry)

            except Exception as e:
                log.error(f"Processing loop error: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _get_pending_events(self) -> list[OutboxEntry]:
        """Get pending events from outbox table"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        created_after = datetime.now(timezone.utc) - timedelta(hours=24)

        rows = await self.db_pool.fetch(
            """
            SELECT * FROM get_pending_outbox_events($1, $2, $3, $4)
            """,
            self.max_retry_attempts,
            cutoff_time,
            created_after,
            self.batch_size
        )

        return [
            OutboxEntry(
                id=str(row['id']),
                event_id=str(row['event_id']),
                aggregate_id=str(row['aggregate_id']),
                aggregate_type=row['aggregate_type'],
                event_type=row['event_type'],
                event_data=json.loads(row['event_data']) if isinstance(row['event_data'], str) else row['event_data'],
                topic=row['topic'],
                partition_key=row['partition_key'],
                status=OutboxStatus(row['status']),
                publish_attempts=row['publish_attempts'],
                metadata=json.loads(row['metadata']) if row['metadata'] else None,
                aggregate_version=row['aggregate_version'],
                created_at=row['created_at']
            )
            for row in rows
        ]

    async def _process_entry(self, entry: OutboxEntry):
        """
        Process a single outbox entry.

        DUAL DESTINATION PATTERN:
        1. EventStore - Source of Truth (required for compensating events)
        2. EventBus - Real-time transport
        """
        try:
            # Check if this is a compensating event (requires EventStore write)
            is_compensating = entry.metadata and entry.metadata.get('compensating_event', False)
            should_write_eventstore = entry.metadata and (
                entry.metadata.get('write_to_eventstore', False) or is_compensating
            )

            # 1. Write to EventStore first (for compensating events)
            if should_write_eventstore:
                await self._write_to_eventstore(entry)

            # 2. Publish to EventBus (transport)
            await self._publish_to_eventbus(entry)

            # 3. Mark as published
            await self._mark_published(entry.id)

            log.info(
                f"Processed outbox entry: {entry.event_type} "
                f"(eventstore={should_write_eventstore}, topic={entry.topic})"
            )

        except Exception as e:
            log.error(f"Failed to process entry {entry.event_id}: {e}")
            await self._mark_failed(entry.id, str(e))

    async def _write_to_eventstore(self, entry: OutboxEntry):
        """
        Write compensating event to EventStore.

        PATTERN: Compensating Event (Greg Young)
        - External changes bypass aggregates
        - Compensating events record the FACT
        - Preserves audit trail for projection rebuild

        Source: Greg Young - "Write a new fact that supersedes the old fact"
        """
        envelope = {
            'event_id': entry.event_id,
            'aggregate_id': entry.aggregate_id,
            'aggregate_type': entry.aggregate_type,
            'event_type': entry.event_type,
            'event_data': entry.event_data,
            'aggregate_version': entry.aggregate_version or 0,
            'timestamp': entry.created_at.isoformat(),
            'metadata': {
                'source': 'external_trigger',
                'compensating_event': True,
                'changed_by': entry.metadata.get('changed_by', 'EXTERNAL'),
                'severity': entry.metadata.get('severity', 'MEDIUM'),
                **entry.metadata
            }
        }

        await self.event_store.append_events(
            aggregate_id=entry.aggregate_id,
            aggregate_type=entry.aggregate_type,
            events=[envelope],
            expected_version=None  # No version check for compensating events
        )

        log.info(f"Compensating event written to EventStore: {entry.event_type}")

    async def _publish_to_eventbus(self, entry: OutboxEntry):
        """Publish event to EventBus (Kafka/Redpanda) for real-time transport"""
        transport_event = {
            'event_id': entry.event_id,
            'event_type': entry.event_type,
            'aggregate_id': entry.aggregate_id,
            'aggregate_type': entry.aggregate_type,
            'timestamp': entry.created_at.isoformat(),
            **entry.event_data
        }

        await self.event_bus.publish(
            topic=entry.topic,
            event=transport_event,
            key=entry.partition_key
        )

    async def _mark_published(self, outbox_id: str):
        """Mark entry as successfully published"""
        await self.db_pool.execute(
            """
            UPDATE event_outbox
            SET status = 'published',
                published_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            """,
            outbox_id
        )

    async def _mark_failed(self, outbox_id: str, error: str):
        """Mark entry as failed"""
        await self.db_pool.execute(
            """
            UPDATE event_outbox
            SET status = CASE
                    WHEN publish_attempts + 1 >= max_attempts THEN 'dead_letter'
                    ELSE 'failed'
                END,
                publish_attempts = publish_attempts + 1,
                last_attempt_at = NOW(),
                last_error = $2,
                last_error_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            """,
            outbox_id,
            error[:1000]
        )
```

---

## 8. Event Definitions

### Base Event Class

```python
# events/base.py
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime, timezone
import uuid


class BaseEvent(BaseModel):
    """Base class for all domain events"""
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1

    model_config = {"from_attributes": True}
```

### Compensating Event Classes

```python
# events/external_change_events.py
from typing import Literal, Optional
from datetime import datetime
import uuid
from .base import BaseEvent


class OrderDeletedExternally(BaseEvent):
    """
    Order deleted via external SQL operation (bypassing aggregate).

    Emitted by: PostgreSQL trigger (AFTER DELETE on orders)
    Purpose: Detect external deletions, enable recovery from broker
    Recovery: Refetch order from broker API
    """
    event_type: Literal["OrderDeletedExternally"] = "OrderDeletedExternally"

    # Identifiers
    order_id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    broker_connection_id: Optional[uuid.UUID] = None

    # Order details (preserved for audit)
    symbol: str
    side: str
    quantity: str
    order_type: str
    status: str
    broker_order_id: Optional[str] = None

    # Detection metadata
    deleted_at: datetime
    deleted_by: str = "EXTERNAL_SQL"
    detection_method: str = "trigger"

    # Recovery
    recovery_action: str = "refetch_from_broker"
    severity: str = "HIGH"


class UserRoleChangedExternally(BaseEvent):
    """
    User role changed via external SQL operation.

    Emitted by: PostgreSQL trigger (AFTER UPDATE on user_accounts.role)
    Purpose: Detect external role changes, invalidate sessions
    Action: Force logout (invalidate all refresh tokens + sessions)
    """
    event_type: Literal["UserRoleChangedExternally"] = "UserRoleChangedExternally"

    # Identifiers
    user_id: uuid.UUID
    username: str

    # Role change
    old_role: str
    new_role: str

    # Detection metadata
    changed_at: datetime
    changed_by: str = "EXTERNAL_SQL"
    detection_method: str = "trigger"

    # Action required
    action_required: str = "Invalidate all user sessions"
    severity: str = "HIGH"


class BrokerConnectionDeletedExternally(BaseEvent):
    """
    Broker connection deleted via external SQL operation.

    Emitted by: PostgreSQL trigger (AFTER DELETE on broker_connections)
    Purpose: Detect external deletions (NON-RECOVERABLE)
    Recovery: User must reconnect via OAuth
    """
    event_type: Literal["BrokerConnectionDeletedExternally"] = "BrokerConnectionDeletedExternally"

    # Identifiers
    connection_id: uuid.UUID
    user_id: uuid.UUID
    broker_id: str
    environment: str

    # Detection metadata
    deleted_at: datetime
    deleted_by: str = "EXTERNAL_SQL"
    detection_method: str = "trigger"

    # Recovery
    recovery_method: str = "none"  # NON-RECOVERABLE
    alert_user: bool = True
    severity: str = "HIGH"
    action_required: str = "User must reconnect via OAuth"
```

---

## 9. Projector Handlers

### Projector Implementation

```python
# projectors/external_change_projector.py
import logging
from typing import Dict, Any
import uuid

log = logging.getLogger("projector.external_changes")


class ExternalChangeProjector:
    """
    Handles compensating events from external SQL changes.

    Pattern: Sync Projection for security-critical events
    """

    def __init__(self, cache_manager, jwt_manager, websocket_engine):
        self.cache_manager = cache_manager
        self.jwt_manager = jwt_manager
        self.websocket_engine = websocket_engine

    async def on_user_role_changed_externally(self, event_data: Dict[str, Any]):
        """
        Handle UserRoleChangedExternally event.

        CRITICAL: Invalidate all user sessions after external role change.
        This ensures user must re-login to apply new permissions.
        """
        user_id = uuid.UUID(event_data['user_id'])
        old_role = event_data['old_role']
        new_role = event_data['new_role']

        log.critical(
            f"[EXTERNAL CHANGE] User role changed via SQL! "
            f"user_id={user_id}, {old_role} -> {new_role}"
        )

        # 1. Revoke all refresh tokens (force logout)
        await self.jwt_manager.revoke_all_refresh_tokens(str(user_id))
        log.info(f"Revoked all refresh tokens for user {user_id}")

        # 2. Clear user cache
        await self.cache_manager.delete(f"user:profile:{user_id}")
        await self.cache_manager.delete(f"user:sessions:{user_id}")
        log.info(f"Cleared cache for user {user_id}")

        # 3. Notify frontend via WebSocket
        await self.websocket_engine.broadcast_to_user(
            user_id=str(user_id),
            event={
                "type": "USER_ROLE_CHANGED",
                "payload": {
                    "old_role": old_role,
                    "new_role": new_role,
                    "action": "SESSION_INVALIDATED"
                }
            }
        )

    async def on_broker_connection_deleted_externally(self, event_data: Dict[str, Any]):
        """
        Handle BrokerConnectionDeletedExternally event.

        NON-RECOVERABLE: OAuth tokens are lost, user must reconnect.
        """
        connection_id = event_data['connection_id']
        user_id = event_data['user_id']
        broker_id = event_data['broker_id']

        log.critical(
            f"[EXTERNAL CHANGE] Broker connection deleted via SQL! "
            f"connection_id={connection_id}, broker={broker_id} "
            f"- NON-RECOVERABLE, user must reconnect via OAuth"
        )

        # 1. Stop any active streaming
        # await self.streaming_manager.stop_connection(connection_id)

        # 2. Clear connection cache
        await self.cache_manager.delete(f"connection:{connection_id}")
        await self.cache_manager.delete(f"user:connections:{user_id}")

        # 3. Notify frontend
        await self.websocket_engine.broadcast_to_user(
            user_id=user_id,
            event={
                "type": "BROKER_CONNECTION_DELETED",
                "payload": {
                    "connection_id": connection_id,
                    "broker_id": broker_id,
                    "recovery_method": "none",
                    "action_required": "Please reconnect via OAuth"
                }
            }
        )

    async def on_order_deleted_externally(self, event_data: Dict[str, Any]):
        """
        Handle OrderDeletedExternally event.

        RECOVERABLE: Can refetch order from broker API.
        """
        order_id = event_data['order_id']
        user_id = event_data['user_id']
        account_id = event_data['account_id']

        log.warning(
            f"[EXTERNAL CHANGE] Order deleted via SQL! "
            f"order_id={order_id} - triggering refetch from broker"
        )

        # 1. Clear order cache
        await self.cache_manager.delete(f"order:{order_id}")
        await self.cache_manager.delete(f"account:orders:{account_id}")

        # 2. Trigger recovery (refetch from broker)
        # await self.recovery_service.schedule_order_refetch(
        #     account_id=account_id,
        #     broker_order_id=event_data.get('broker_order_id')
        # )

        # 3. Notify frontend
        await self.websocket_engine.broadcast_to_user(
            user_id=user_id,
            event={
                "type": "ORDER_DELETED_EXTERNALLY",
                "payload": {
                    "order_id": order_id,
                    "recovery_action": "refetch_from_broker"
                }
            }
        )
```

---

## 10. Testing & Validation

### Unit Tests

```python
# tests/test_external_change_detection.py
import pytest
import asyncio
from datetime import datetime, timezone
import uuid


class TestExternalChangeDetection:
    """Test external change detection via triggers"""

    @pytest.fixture
    async def db_connection(self, db_pool):
        async with db_pool.acquire() as conn:
            yield conn

    async def test_order_deletion_trigger_creates_outbox_entry(self, db_connection):
        """Test that deleting an order creates compensating event in outbox"""
        # Arrange: Create test order
        order_id = uuid.uuid4()
        await db_connection.execute(
            """
            INSERT INTO orders (id, user_id, account_id, symbol, side, quantity, order_type, status)
            VALUES ($1, $2, $3, 'AAPL', 'buy', 100, 'market', 'open')
            """,
            order_id, uuid.uuid4(), uuid.uuid4()
        )

        # Act: Delete order (simulating external SQL)
        await db_connection.execute("DELETE FROM orders WHERE id = $1", order_id)

        # Assert: Check outbox has compensating event
        outbox_entry = await db_connection.fetchrow(
            """
            SELECT * FROM event_outbox
            WHERE aggregate_id = $1 AND event_type = 'OrderDeletedExternally'
            """,
            order_id
        )

        assert outbox_entry is not None
        assert outbox_entry['status'] == 'pending'
        assert outbox_entry['event_data']['deleted_by'] == 'EXTERNAL_SQL'
        assert outbox_entry['metadata']['compensating_event'] == True

    async def test_user_role_change_trigger_creates_outbox_entry(self, db_connection):
        """Test that changing user role creates compensating event"""
        # Arrange: Create test user
        user_id = uuid.uuid4()
        await db_connection.execute(
            """
            INSERT INTO user_accounts (id, username, email, role, hashed_password, hashed_secret)
            VALUES ($1, 'testuser', 'test@example.com', 'user', 'hash', 'secret')
            """,
            user_id
        )

        # Act: Change role (simulating external SQL)
        await db_connection.execute(
            "UPDATE user_accounts SET role = 'admin' WHERE id = $1",
            user_id
        )

        # Assert: Check outbox
        outbox_entry = await db_connection.fetchrow(
            """
            SELECT * FROM event_outbox
            WHERE aggregate_id = $1 AND event_type = 'UserRoleChangedExternally'
            """,
            user_id
        )

        assert outbox_entry is not None
        assert outbox_entry['event_data']['old_role'] == 'user'
        assert outbox_entry['event_data']['new_role'] == 'admin'
        assert outbox_entry['metadata']['security_impact'] == True

    async def test_outbox_processor_writes_to_eventstore(self, outbox_processor, event_store):
        """Test that OutboxProcessor writes compensating events to EventStore"""
        # Arrange: Create outbox entry with compensating_event flag
        entry = OutboxEntry(
            id=str(uuid.uuid4()),
            event_id=str(uuid.uuid4()),
            aggregate_id=str(uuid.uuid4()),
            aggregate_type='Order',
            event_type='OrderDeletedExternally',
            event_data={'order_id': str(uuid.uuid4()), 'deleted_by': 'EXTERNAL_SQL'},
            topic='transport.order-events',
            partition_key=None,
            status=OutboxStatus.PENDING,
            publish_attempts=0,
            metadata={'compensating_event': True, 'write_to_eventstore': True},
            aggregate_version=1,
            created_at=datetime.now(timezone.utc)
        )

        # Act: Process entry
        await outbox_processor._process_entry(entry)

        # Assert: Event written to EventStore
        events = await event_store.read_stream(
            f"Order-{entry.aggregate_id}"
        )

        assert len(events) == 1
        assert events[0].event_type == 'OrderDeletedExternally'
        assert events[0].metadata['compensating_event'] == True
```

### Integration Tests

```python
# tests/integration/test_full_flow.py
import pytest
import asyncio


class TestFullExternalChangeFlow:
    """End-to-end tests for external change detection"""

    async def test_full_flow_order_deletion(
        self,
        db_pool,
        outbox_processor,
        event_store,
        websocket_client
    ):
        """
        Test complete flow:
        1. Delete order via SQL
        2. Trigger creates outbox entry
        3. OutboxProcessor writes to EventStore
        4. OutboxProcessor publishes to EventBus
        5. Projector handles event
        6. WebSocket notifies frontend
        """
        # Arrange
        order_id = uuid.uuid4()
        user_id = uuid.uuid4()

        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO orders (...) VALUES (...)",
                order_id, user_id, ...
            )

        # Subscribe to WebSocket
        ws_messages = []
        async def ws_handler(msg):
            ws_messages.append(msg)

        await websocket_client.subscribe(user_id, ws_handler)

        # Act: Delete order (external SQL)
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM orders WHERE id = $1", order_id)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Assert: EventStore has compensating event
        events = await event_store.read_stream(f"Order-{order_id}")
        assert any(e.event_type == 'OrderDeletedExternally' for e in events)

        # Assert: WebSocket received notification
        assert any(
            msg['type'] == 'ORDER_DELETED_EXTERNALLY'
            for msg in ws_messages
        )
```

---

## 11. Monitoring & Alerting

### SQL Monitoring View

```sql
-- View for monitoring trigger-generated events
CREATE OR REPLACE VIEW trigger_generated_events AS
SELECT
    event_id,
    aggregate_type,
    event_type,
    event_data->>'deleted_by' as source,
    event_data->>'severity' as severity,
    status,
    priority,
    publish_attempts,
    created_at,
    published_at,
    EXTRACT(EPOCH FROM (COALESCE(published_at, NOW()) - created_at)) as latency_seconds
FROM event_outbox
WHERE event_type LIKE '%Externally'
ORDER BY created_at DESC
LIMIT 1000;

-- Statistics function
CREATE OR REPLACE FUNCTION get_external_change_stats()
RETURNS TABLE(
    event_type TEXT,
    count BIGINT,
    avg_latency_ms NUMERIC,
    max_latency_ms NUMERIC,
    pending_count BIGINT,
    failed_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.event_type::TEXT,
        COUNT(*),
        ROUND(AVG(EXTRACT(EPOCH FROM (COALESCE(e.published_at, NOW()) - e.created_at)) * 1000), 2),
        ROUND(MAX(EXTRACT(EPOCH FROM (COALESCE(e.published_at, NOW()) - e.created_at)) * 1000), 2),
        COUNT(*) FILTER (WHERE e.status = 'pending'),
        COUNT(*) FILTER (WHERE e.status IN ('failed', 'dead_letter'))
    FROM event_outbox e
    WHERE e.event_type LIKE '%Externally'
      AND e.created_at > NOW() - INTERVAL '1 day'
    GROUP BY e.event_type
    ORDER BY count DESC;
END;
$$ LANGUAGE plpgsql;
```

### Prometheus Metrics

```python
# metrics/external_change_metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Counters
external_changes_total = Counter(
    'external_changes_total',
    'Total external changes detected',
    ['event_type', 'aggregate_type', 'severity']
)

external_changes_published = Counter(
    'external_changes_published_total',
    'External changes successfully published',
    ['event_type', 'destination']  # destination: eventstore, eventbus
)

external_changes_failed = Counter(
    'external_changes_failed_total',
    'External changes failed to publish',
    ['event_type', 'error_type']
)

# Histograms
external_change_latency = Histogram(
    'external_change_processing_seconds',
    'Time from trigger to publish',
    ['event_type'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Gauges
outbox_pending_count = Gauge(
    'outbox_pending_count',
    'Number of pending events in outbox',
    ['event_type']
)
```

### Alerting Rules (Prometheus)

```yaml
# alerting_rules.yml
groups:
  - name: external_change_detection
    rules:
      - alert: ExternalChangeDetected
        expr: increase(external_changes_total[5m]) > 0
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "External SQL change detected"
          description: "{{ $labels.event_type }} detected via SQL trigger"

      - alert: ExternalChangeHighLatency
        expr: histogram_quantile(0.95, rate(external_change_processing_seconds_bucket[5m])) > 1.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency in external change processing"
          description: "95th percentile latency > 1s"

      - alert: OutboxBacklog
        expr: outbox_pending_count > 100
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Outbox backlog growing"
          description: "{{ $value }} events pending in outbox"

      - alert: CriticalExternalChange
        expr: increase(external_changes_total{severity="CRITICAL"}[1m]) > 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "CRITICAL external change detected"
          description: "{{ $labels.event_type }} - immediate investigation required"
```

---

## 12. Troubleshooting

### Common Issues

#### Issue 1: Events not appearing in outbox

**Symptoms:** SQL DELETE/UPDATE executed but no entry in `event_outbox`

**Diagnosis:**
```sql
-- Check if trigger exists
SELECT tgname, tgrelid::regclass, tgenabled
FROM pg_trigger
WHERE tgname LIKE 'after_%';

-- Check trigger function exists
SELECT proname FROM pg_proc WHERE proname LIKE 'notify_%';
```

**Solution:**
```sql
-- Re-create trigger
DROP TRIGGER IF EXISTS after_order_delete ON orders;
CREATE TRIGGER after_order_delete
AFTER DELETE ON orders
FOR EACH ROW
EXECUTE FUNCTION notify_order_deleted();
```

#### Issue 2: Events stuck in pending status

**Symptoms:** Events in outbox with `status = 'pending'` for extended time

**Diagnosis:**
```sql
SELECT
    event_type,
    COUNT(*) as pending_count,
    MIN(created_at) as oldest_pending,
    MAX(publish_attempts) as max_attempts
FROM event_outbox
WHERE status = 'pending'
GROUP BY event_type;
```

**Solution:**
- Check OutboxProcessor is running
- Check EventBus connectivity
- Check for poison pills (non-transient errors)

#### Issue 3: Events not written to EventStore

**Symptoms:** Events published to EventBus but missing from EventStore

**Diagnosis:**
```python
# Check if compensating_event flag is set
SELECT metadata->>'compensating_event'
FROM event_outbox
WHERE event_type = 'OrderDeletedExternally';
```

**Solution:**
- Ensure trigger sets `'compensating_event': true` in metadata
- Check EventStore connectivity
- Review OutboxProcessor logs

#### Issue 4: Duplicate events

**Symptoms:** Same event appears multiple times

**Diagnosis:**
```sql
SELECT event_id, COUNT(*)
FROM event_outbox
GROUP BY event_id
HAVING COUNT(*) > 1;
```

**Solution:**
- Use `ON CONFLICT (event_id) DO NOTHING` in trigger
- Ensure idempotent consumers

### Debug Queries

```sql
-- Recent external changes
SELECT * FROM trigger_generated_events LIMIT 20;

-- Statistics
SELECT * FROM get_external_change_stats();

-- Failed events
SELECT event_id, event_type, last_error, publish_attempts
FROM event_outbox
WHERE status IN ('failed', 'dead_letter')
ORDER BY created_at DESC
LIMIT 20;

-- Processing latency
SELECT
    event_type,
    AVG(EXTRACT(EPOCH FROM (published_at - created_at))) as avg_latency_sec
FROM event_outbox
WHERE status = 'published'
  AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY event_type;
```

---

## Summary

### Key Takeaways

1. **EventStore = Source of Truth** (Martin Fowler, Greg Young)
2. **Compensating Events** for external changes (Greg Young)
3. **Transactional Outbox** for dual-write protection (Confluent, Debezium)
4. **LISTEN/NOTIFY** for CDC-like latency without Debezium
5. **Dual Destination** (EventStore + EventBus) for completeness

### Implementation Checklist

- [ ] Create `event_outbox` table with proper indexes
- [ ] Implement PostgreSQL triggers for each monitored table
- [ ] Implement OutboxProcessor with LISTEN/NOTIFY
- [ ] Define compensating event classes
- [ ] Implement projector handlers
- [ ] Configure monitoring and alerting
- [ ] Write integration tests
- [ ] Document recovery procedures

### References

1. [Greg Young - Event Sourcing and CQRS](https://www.kurrent.io/blog/event-sourcing-and-cqrs)
2. [Kurrent Docs - Outbox Pattern](https://docs.kurrent.io/dev-center/use-cases/outbox/introduction)
3. [Martin Fowler - Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)
4. [Confluent - Dual Write Problem](https://www.confluent.io/blog/dual-write-problem/)
5. [Debezium - Outbox Pattern](https://debezium.io/blog/2019/02/19/reliable-microservices-data-exchange-with-the-outbox-pattern/)
6. [microservices.io - Transactional Outbox](https://microservices.io/patterns/data/transactional-outbox.html)
7. [Microsoft - Event Sourcing Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
8. [Event-Driven.io - Outbox Patterns Explained](https://event-driven.io/en/outbox_inbox_patterns_and_delivery_guarantees_explained/)
