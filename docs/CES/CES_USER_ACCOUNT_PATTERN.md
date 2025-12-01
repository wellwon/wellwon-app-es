# Compensating Event System (CES) - User Account Domain Pattern

## Quick Reference for Other Projects

This document provides a pattern reference for implementing the **Compensating Event System (CES)** in the User Account domain. Use this as a template for your other projects.

### What is CES?

**Compensating Event System** (term by Greg Young) - a pattern where PostgreSQL triggers detect external data modifications and generate **compensating events** to maintain system consistency.

| Component | Description |
|-----------|-------------|
| **Trigger** | PostgreSQL BEFORE/AFTER trigger detects change |
| **Compensating Event** | Event that records the external modification |
| **Outbox** | Transactional outbox ensures exactly-once delivery |
| **Sync Projector** | Handles event synchronously (security-critical) |

---

## CES Pattern Overview

When data is modified directly in PostgreSQL (bypassing your application), the **Compensating Event System** detects this and:

1. **Trigger** fires on UPDATE/DELETE
2. **Compensating Event** written to `event_outbox` table
3. **Outbox Processor** delivers to EventStore + EventBus
4. **Sync Projector** handles immediately:
   - Invalidates caches
   - Revokes tokens (security events)
   - Logs CRITICAL for audit

---

## Step 1: Define Events

**File:** `events.py`

```python
from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class UserRoleChangedExternally(BaseModel):
    """Compensating event for external role change via SQL."""
    event_type: Literal["UserRoleChangedExternally"] = "UserRoleChangedExternally"
    user_id: str
    username: str
    old_role: str
    new_role: str
    changed_at: datetime
    detected_by: Literal["EXTERNAL_SQL"] = "EXTERNAL_SQL"

class UserStatusChangedExternally(BaseModel):
    """Compensating event for external status change via SQL."""
    event_type: Literal["UserStatusChangedExternally"] = "UserStatusChangedExternally"
    user_id: str
    username: str
    old_status: bool
    new_status: bool
    changed_at: datetime
    detected_by: Literal["EXTERNAL_SQL"] = "EXTERNAL_SQL"

class UserAccountDeletedExternally(BaseModel):
    """Compensating event for external user deletion via SQL."""
    event_type: Literal["UserAccountDeletedExternally"] = "UserAccountDeletedExternally"
    user_id: str
    username: str
    email: str
    deleted_at: datetime
    detected_by: Literal["EXTERNAL_SQL"] = "EXTERNAL_SQL"
```

---

## Step 2: Create PostgreSQL Triggers

**File:** `migrations/add_user_external_change_triggers.sql`

```sql
-- =============================================================================
-- EXTERNAL CHANGE DETECTION TRIGGERS FOR USER ACCOUNTS
-- =============================================================================

-- Outbox table (if not exists)
CREATE TABLE IF NOT EXISTS event_outbox (
    id SERIAL PRIMARY KEY,
    event_id UUID NOT NULL DEFAULT gen_random_uuid(),
    aggregate_id UUID NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_version INTEGER DEFAULT 1,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL,
    topic VARCHAR(200) NOT NULL,
    partition_key TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    priority INTEGER DEFAULT 10,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_outbox_status_created ON event_outbox(status, created_at);
CREATE INDEX IF NOT EXISTS idx_outbox_topic ON event_outbox(topic);

-- =============================================================================
-- TRIGGER 1: User Role Changed Externally
-- =============================================================================
CREATE OR REPLACE FUNCTION notify_user_role_changed()
RETURNS TRIGGER AS $
BEGIN
    -- Only trigger if role actually changed
    IF OLD.role IS DISTINCT FROM NEW.role THEN
        INSERT INTO event_outbox (
            event_id, aggregate_id, aggregate_type, aggregate_version,
            event_type, event_data, topic, partition_key, status, priority, metadata, created_at
        ) VALUES (
            gen_random_uuid(),
            OLD.id,
            'UserAccount',
            COALESCE(NEW.aggregate_version, 1),
            'UserRoleChangedExternally',
            jsonb_build_object(
                'event_type', 'UserRoleChangedExternally',
                'user_id', OLD.id::text,
                'username', OLD.username,
                'old_role', OLD.role,
                'new_role', NEW.role,
                'changed_at', NOW()::text,
                'detected_by', 'EXTERNAL_SQL',
                'compensating_event', true
            ),
            'transport.user-account-events',
            OLD.id::text,
            'pending',
            5,  -- High priority for security events
            jsonb_build_object('write_to_eventstore', true, 'compensating_event', true),
            NOW()
        );

        -- Notify outbox processor
        PERFORM pg_notify('outbox_events', OLD.id::text);
    END IF;

    RETURN NEW;
END;
$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_role_changed ON user_accounts;
CREATE TRIGGER trg_user_role_changed
    AFTER UPDATE OF role ON user_accounts
    FOR EACH ROW
    WHEN (pg_trigger_depth() = 0)
    EXECUTE FUNCTION notify_user_role_changed();

-- =============================================================================
-- TRIGGER 2: User Status Changed Externally (is_active)
-- =============================================================================
CREATE OR REPLACE FUNCTION notify_user_status_changed()
RETURNS TRIGGER AS $
BEGIN
    IF OLD.is_active IS DISTINCT FROM NEW.is_active THEN
        INSERT INTO event_outbox (
            event_id, aggregate_id, aggregate_type, aggregate_version,
            event_type, event_data, topic, partition_key, status, priority, metadata, created_at
        ) VALUES (
            gen_random_uuid(),
            OLD.id,
            'UserAccount',
            COALESCE(NEW.aggregate_version, 1),
            'UserStatusChangedExternally',
            jsonb_build_object(
                'event_type', 'UserStatusChangedExternally',
                'user_id', OLD.id::text,
                'username', OLD.username,
                'old_status', OLD.is_active,
                'new_status', NEW.is_active,
                'changed_at', NOW()::text,
                'detected_by', 'EXTERNAL_SQL',
                'compensating_event', true
            ),
            'transport.user-account-events',
            OLD.id::text,
            'pending',
            5,  -- High priority for security events
            jsonb_build_object('write_to_eventstore', true, 'compensating_event', true),
            NOW()
        );

        PERFORM pg_notify('outbox_events', OLD.id::text);
    END IF;

    RETURN NEW;
END;
$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_status_changed ON user_accounts;
CREATE TRIGGER trg_user_status_changed
    AFTER UPDATE OF is_active ON user_accounts
    FOR EACH ROW
    WHEN (pg_trigger_depth() = 0)
    EXECUTE FUNCTION notify_user_status_changed();

-- =============================================================================
-- TRIGGER 3: User Account Deleted Externally
-- =============================================================================
CREATE OR REPLACE FUNCTION notify_user_deleted()
RETURNS TRIGGER AS $
BEGIN
    INSERT INTO event_outbox (
        event_id, aggregate_id, aggregate_type, aggregate_version,
        event_type, event_data, topic, partition_key, status, priority, metadata, created_at
    ) VALUES (
        gen_random_uuid(),
        OLD.id,
        'UserAccount',
        COALESCE(OLD.aggregate_version, 1),
        'UserAccountDeletedExternally',
        jsonb_build_object(
            'event_type', 'UserAccountDeletedExternally',
            'user_id', OLD.id::text,
            'username', OLD.username,
            'email', OLD.email,
            'deleted_at', NOW()::text,
            'detected_by', 'EXTERNAL_SQL',
            'compensating_event', true
        ),
        'transport.user-account-events',
        OLD.id::text,
        'pending',
        1,  -- CRITICAL priority
        jsonb_build_object('write_to_eventstore', true, 'compensating_event', true),
        NOW()
    );

    PERFORM pg_notify('outbox_events', OLD.id::text);

    RETURN OLD;
END;
$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_deleted ON user_accounts;
CREATE TRIGGER trg_user_deleted
    BEFORE DELETE ON user_accounts
    FOR EACH ROW
    WHEN (pg_trigger_depth() = 0)
    EXECUTE FUNCTION notify_user_deleted();

-- =============================================================================
-- MONITORING FUNCTION
-- =============================================================================
CREATE OR REPLACE FUNCTION get_user_external_change_stats()
RETURNS TABLE(
    event_type TEXT,
    total_count BIGINT,
    pending_count BIGINT,
    last_24h BIGINT
) AS $
BEGIN
    RETURN QUERY
    SELECT
        eo.event_type,
        COUNT(*) AS total_count,
        COUNT(*) FILTER (WHERE eo.status = 'pending') AS pending_count,
        COUNT(*) FILTER (WHERE eo.created_at > NOW() - INTERVAL '24 hours') AS last_24h
    FROM event_outbox eo
    WHERE eo.event_type IN (
        'UserRoleChangedExternally',
        'UserStatusChangedExternally',
        'UserAccountDeletedExternally'
    )
    GROUP BY eo.event_type
    ORDER BY total_count DESC;
END;
$ LANGUAGE plpgsql;
```

---

## Step 3: Add Projector Handlers

**File:** `projectors.py`

```python
import logging
import uuid
from app.infra.event_store.event_envelope import EventEnvelope
from app.infra.event_store.sync_decorators import sync_projection, monitor_projection

log = logging.getLogger("your_app.user_account.projectors")


class UserAccountProjector:
    """Projector for User Account domain events."""

    def __init__(self, user_read_repo, jwt_manager=None):
        self.user_read_repo = user_read_repo
        self.jwt_manager = jwt_manager

    # =========================================================================
    # External Change Detection Handlers
    # =========================================================================

    @sync_projection("UserRoleChangedExternally", priority=1, timeout=2.0)
    @monitor_projection
    async def on_user_role_changed_externally(self, envelope: EventEnvelope) -> None:
        """
        Handle UserRoleChangedExternally event.

        SECURITY-CRITICAL: Revoke all sessions to force re-login with new permissions.
        """
        event_data = envelope.event_data
        user_id = uuid.UUID(event_data['user_id'])
        old_role = event_data['old_role']
        new_role = event_data['new_role']

        log.critical(
            f"[EXTERNAL CHANGE] User role changed via SQL! "
            f"user_id={user_id}, {old_role} -> {new_role}, invalidating all sessions"
        )

        # Revoke all refresh tokens
        if self.jwt_manager:
            try:
                await self.jwt_manager.revoke_all_refresh_tokens(str(user_id))
                log.info(f"Revoked all tokens for user {user_id}")
            except Exception as e:
                log.error(f"Failed to revoke tokens for user {user_id}: {e}")

        # Clear cache
        await self._clear_user_caches(user_id)

    @sync_projection("UserStatusChangedExternally", priority=1, timeout=2.0)
    @monitor_projection
    async def on_user_status_changed_externally(self, envelope: EventEnvelope) -> None:
        """
        Handle UserStatusChangedExternally event.

        SECURITY-CRITICAL: Force logout if user deactivated.
        """
        event_data = envelope.event_data
        user_id = uuid.UUID(event_data['user_id'])
        new_status = event_data['new_status']

        log.critical(
            f"[EXTERNAL CHANGE] User status changed via SQL! "
            f"user_id={user_id}, active={new_status}"
        )

        if not new_status:  # User deactivated
            if self.jwt_manager:
                try:
                    await self.jwt_manager.revoke_all_refresh_tokens(str(user_id))
                    log.info(f"User {user_id} deactivated - all sessions revoked")
                except Exception as e:
                    log.error(f"Failed to revoke tokens: {e}")

        # Clear cache
        await self._clear_user_caches(user_id)

    @sync_projection("UserAccountDeletedExternally", priority=1, timeout=3.0)
    @monitor_projection
    async def on_user_account_deleted_externally(self, envelope: EventEnvelope) -> None:
        """
        Handle UserAccountDeletedExternally event.

        CATASTROPHIC: User deleted via SQL. Revoke tokens + clear caches.
        """
        event_data = envelope.event_data
        user_id = event_data.get('user_id')
        username = event_data.get('username')

        log.critical(
            f"[CATASTROPHIC] User account deleted via SQL! "
            f"user_id={user_id}, username={username} "
            f"- IMMEDIATE ADMIN INVESTIGATION REQUIRED"
        )

        # Revoke all tokens
        if self.jwt_manager:
            try:
                await self.jwt_manager.revoke_all_refresh_tokens(str(user_id))
                log.info(f"Revoked all tokens for deleted user {user_id}")
            except Exception as e:
                log.error(f"Failed to revoke tokens for deleted user {user_id}: {e}")

        # Clear all caches
        try:
            await self._clear_user_caches(uuid.UUID(user_id))
        except Exception as e:
            log.error(f"Failed to clear caches for deleted user {user_id}: {e}")

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _clear_user_caches(self, user_id: uuid.UUID) -> None:
        """Clear all user-related caches."""
        cache_keys = [
            f"user:profile:{user_id}",
            f"user:auth:{user_id}",
            f"user:sessions:{user_id}",
            f"user:permissions:{user_id}",
        ]

        for key in cache_keys:
            try:
                await self.user_read_repo.cache_manager.delete(key)
            except Exception as e:
                log.warning(f"Failed to clear cache key {key}: {e}")

        log.info(f"Cache invalidation completed for user {user_id}")
```

---

## Step 4: @sync_projection Decorator

**File:** `sync_decorators.py`

```python
from functools import wraps
from typing import Callable, Any
import logging
import time

log = logging.getLogger(__name__)


class ProjectionMetadata:
    """Metadata for sync projection."""
    def __init__(self, event_type: str, priority: int, timeout: float):
        self.event_type = event_type
        self.priority = priority
        self.timeout = timeout


def sync_projection(event_type: str, priority: int = 10, timeout: float = 5.0):
    """
    Decorator for synchronous projections.

    Args:
        event_type: Event type this handler processes
        priority: 1-20 (lower = higher priority). Security events = 1-5
        timeout: Max execution time in seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start = time.monotonic()
            try:
                result = await func(*args, **kwargs)
                duration = time.monotonic() - start
                log.debug(f"[SYNC] {event_type} completed in {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.monotonic() - start
                log.error(f"[SYNC] {event_type} failed after {duration:.3f}s: {e}")
                raise

        # Mark as sync projection
        wrapper._is_sync_projection = True
        wrapper._projection_metadata = ProjectionMetadata(event_type, priority, timeout)
        return wrapper

    return decorator


def monitor_projection(func: Callable) -> Callable:
    """Optional: Add monitoring/metrics to projection."""
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Add your metrics here (Prometheus, etc.)
        return await func(*args, **kwargs)
    return wrapper
```

---

## Step 5: Register Events in Event Registry

**File:** `event_registry.py`

```python
EVENT_REGISTRY = {
    # ... existing events ...

    # External Change Detection Events
    "UserRoleChangedExternally": {
        "topic": "transport.user-account-events",
        "category": "external_change",
        "priority": 5,
        "sync": True,
        "description": "Compensating event for external role change"
    },
    "UserStatusChangedExternally": {
        "topic": "transport.user-account-events",
        "category": "external_change",
        "priority": 5,
        "sync": True,
        "description": "Compensating event for external status change"
    },
    "UserAccountDeletedExternally": {
        "topic": "transport.user-account-events",
        "category": "external_change",
        "priority": 1,
        "sync": True,
        "description": "Compensating event for external user deletion"
    },
}
```

---

## CES Architecture

```
SQL UPDATE/DELETE (external, bypassing application)
       │
       ▼
┌──────────────────┐
│ PostgreSQL       │
│ BEFORE/AFTER     │
│ Trigger          │
│ (pg_trigger_     │
│  depth() = 0)    │ ◄── Only fires for external changes!
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ event_outbox     │
│ (compensating    │
│  event +         │
│  metadata:       │
│  write_to_       │
│  eventstore=true)│
└────────┬─────────┘
         │
         ▼ pg_notify('outbox_events')
┌──────────────────┐
│ Outbox Processor │
│ (async worker)   │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
EventStore  EventBus
(10yr)     (Kafka/Redpanda)
    │         │
    │         ▼
    │  ┌──────────────────┐
    │  │ @sync_projection │  ◄── CRITICAL: Blocks until complete!
    │  │ @monitor_        │
    │  │  projection      │
    │  │ Projector        │
    │  └────────┬─────────┘
    │           │
    │           ▼
    │    ┌────────────────┐
    │    │ 1. Revoke ALL  │
    │    │    tokens      │
    │    │ 2. Clear ALL   │
    │    │    caches      │
    │    │ 3. Log         │
    │    │    CRITICAL    │
    │    └────────────────┘
    │
    ▼
10-year audit trail (compliance)
```

---

## Testing

```sql
-- Test role change detection
UPDATE user_accounts SET role = 'admin' WHERE username = 'testuser';

-- Verify outbox entry created
SELECT * FROM event_outbox
WHERE event_type = 'UserRoleChangedExternally'
ORDER BY created_at DESC LIMIT 1;

-- Test status change detection
UPDATE user_accounts SET is_active = false WHERE username = 'testuser';

-- Test deletion detection
DELETE FROM user_accounts WHERE username = 'testuser';

-- Check stats
SELECT * FROM get_user_external_change_stats();
```

---

## Key Points - CES Implementation Checklist

### 1. Triggers Must Use `pg_trigger_depth() = 0`

```sql
CREATE TRIGGER trg_user_role_changed
    AFTER UPDATE OF role ON user_accounts
    FOR EACH ROW
    WHEN (pg_trigger_depth() = 0)  -- CRITICAL: Only external changes!
    EXECUTE FUNCTION notify_user_role_changed();
```

Without this, application-initiated changes would also fire triggers (double events).

### 2. @sync_projection is MANDATORY for Security Events

```python
# WRONG - async projection, security risk!
async def on_user_role_changed_externally(self, envelope):
    ...

# CORRECT - sync projection, blocks until complete
@sync_projection("UserRoleChangedExternally", priority=1, timeout=2.0)
@monitor_projection
async def on_user_role_changed_externally(self, envelope):
    ...
```

**Priority guide:**
- **1-5**: Security-critical (role, status, deletion)
- **6-10**: Important (account data)
- **11-20**: Normal (orders, positions)

### 3. Outbox Metadata Must Include `write_to_eventstore`

```sql
INSERT INTO event_outbox (..., metadata) VALUES (
    ...,
    jsonb_build_object(
        'write_to_eventstore', true,   -- REQUIRED for audit trail
        'compensating_event', true      -- Marks as CES event
    )
);
```

### 4. No DataSyncSaga for *DeletedExternally Events

When data is deleted externally, there's nothing to recover:
- User deleted -> tokens revoked, caches cleared, DONE
- Account deleted -> cache cleared, DONE
- Connection deleted -> cache cleared, user must reconnect via OAuth

### 5. All Handlers Must Clear Caches

```python
async def on_user_account_deleted_externally(self, envelope):
    ...
    # MANDATORY: Clear all related caches
    await self._clear_user_caches(uuid.UUID(user_id))
```

### 6. Use CRITICAL Log Level for Audit

```python
log.critical(
    f"[EXTERNAL CHANGE] User role changed via SQL! "
    f"user_id={user_id}, {old_role} -> {new_role}"
)
```

This ensures:
- Logs are captured by monitoring systems
- Easy to search/filter in log aggregators
- Compliance audit trail

---

## CES vs CDC Comparison

| Feature | CES (Our Pattern) | CDC (Debezium) |
|---------|-------------------|----------------|
| **Mechanism** | PostgreSQL triggers | WAL log parsing |
| **Scope** | Selected tables/columns | All changes |
| **Filtering** | `pg_trigger_depth() = 0` | Post-processing |
| **Latency** | ~10ms (pg_notify) | ~100ms (polling) |
| **Complexity** | Simple (SQL only) | Complex (Kafka Connect) |
| **Use Case** | Security events | Full replication |

---

## Related Documentation

- `EXTERNAL_CHANGE_DETECTION_INTEGRATION_GUIDE.md` - Full integration guide
- `database/migrations/007_add_deletion_triggers.sql` - All trigger implementations

---

## References

- **Greg Young** - "Compensating Events" in Event Sourcing
- **Martin Fowler** - "Transactional Outbox Pattern"
- **Confluent** - "Outbox Pattern for Reliable Microservices"
