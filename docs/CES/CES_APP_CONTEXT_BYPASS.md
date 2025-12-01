# CES (Compensating Event System) App Context Bypass

## Overview

This document describes a critical issue with CES triggers firing on normal application operations and provides a comprehensive fix guide for any project using this architecture.

---

## Table of Contents

1. [Problem Description](#problem-description)
2. [Root Cause Analysis](#root-cause-analysis)
3. [Solution Architecture](#solution-architecture)
4. [Implementation Guide](#implementation-guide)
5. [Usage Examples](#usage-examples)
6. [Testing & Verification](#testing--verification)
7. [Troubleshooting](#troubleshooting)

---

## Problem Description

### What is CES?

The Compensating Event System (CES) uses PostgreSQL triggers to detect **external data changes** - modifications made directly to the database outside of the application (e.g., via psql, pgAdmin, or other SQL clients). When such changes are detected, CES generates domain events to notify the system and trigger compensating actions.

### The Issue

CES triggers fire on **ALL** updates to monitored fields, including legitimate application operations. This causes:

1. **Duplicate Events**: Normal application operations generate both the intended domain event AND a `*ChangedExternally` CES event
2. **Incorrect Event Attribution**: Application changes are incorrectly labeled as "EXTERNAL_SQL"
3. **Unnecessary Processing**: The system processes compensating logic for changes that don't need compensation
4. **User Confusion**: Logs show "external change detected" for normal user actions

### Example Scenario

**User Account Domain:**

1. User clicks "Deactivate Account" in the UI
2. Application processes `DeactivateUserCommand`
3. Command handler updates `user_accounts.is_active = false`
4. CES trigger fires and generates `UserStatusChangedExternally` event
5. System incorrectly thinks someone modified the database directly

**Expected Behavior:**
- Only `UserDeactivated` event should be generated (from command handler)
- `UserStatusChangedExternally` should NOT fire for application operations

---

## Root Cause Analysis

### Current Trigger Logic (Before Fix)

```sql
CREATE OR REPLACE FUNCTION notify_user_status_changed()
RETURNS TRIGGER AS $$
BEGIN
    -- Fires on ANY update to is_active, regardless of source
    IF OLD.is_active IS DISTINCT FROM NEW.is_active THEN
        INSERT INTO event_outbox (...) VALUES (...);
        PERFORM pg_notify('outbox_events', NEW.id::text);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

**Problem**: The trigger cannot distinguish between:
- Application code updating `is_active` via SQLAlchemy/asyncpg
- DBA running `UPDATE user_accounts SET is_active = false WHERE id = '...'` in psql

### Why This Happens

PostgreSQL triggers execute at the database level and have no awareness of the application context. From the database's perspective, all UPDATE statements are identical regardless of their origin.

---

## Solution Architecture

### Approach: Session-Level Configuration Variable

PostgreSQL supports session-level configuration variables that can be set by the application and read by triggers. We use this mechanism to signal "this change is from the application."

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     APPLICATION FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Application starts transaction                              │
│  2. SET LOCAL wellwon.app_context = 'true'                   │
│  3. Execute UPDATE user_accounts SET is_active = false...       │
│  4. Trigger checks: current_setting('wellwon.app_context')   │
│  5. Setting = 'true' → Skip CES event generation               │
│  6. Transaction commits, SET LOCAL automatically resets         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     EXTERNAL SQL FLOW                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. DBA connects via psql                                       │
│  2. Runs: UPDATE user_accounts SET is_active = false...         │
│  3. Trigger checks: current_setting('wellwon.app_context')   │
│  4. Setting = '' (not set) → Generate CES event                │
│  5. UserStatusChangedExternally published to event bus         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **`SET LOCAL`**: Scoped to current transaction only, automatically resets on commit/rollback
2. **`current_setting(..., true)`**: The `true` parameter returns empty string if setting doesn't exist (no error)
3. **Custom namespace**: `wellwon.app_context` uses application-specific prefix to avoid conflicts

---

## Implementation Guide

### Step 1: Update PostgreSQL Trigger Functions

For each CES trigger that monitors sensitive fields, add the app context check at the beginning:

```sql
CREATE OR REPLACE FUNCTION notify_user_status_changed()
RETURNS TRIGGER AS $$
BEGIN
    -- Skip if change is from application (not external SQL)
    -- Application sets: SET LOCAL wellwon.app_context = 'true'
    IF current_setting('wellwon.app_context', true) = 'true' THEN
        RETURN NEW;
    END IF;

    -- Original trigger logic continues here
    IF OLD.is_active IS DISTINCT FROM NEW.is_active THEN
        INSERT INTO event_outbox (
            event_id, aggregate_id, aggregate_type, aggregate_version,
            event_type, event_data, topic, partition_key, status, priority, metadata, created_at
        ) VALUES (
            gen_random_uuid(), NEW.id, 'UserAccount', 1,
            'UserStatusChangedExternally',
            jsonb_build_object(
                'event_type', 'UserStatusChangedExternally',
                'user_id', NEW.id::text,
                'old_status', OLD.is_active,
                'new_status', NEW.is_active,
                'changed_at', to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
                'changed_by', 'EXTERNAL_SQL',
                'detection_method', 'trigger',
                'severity', 'HIGH'
            ),
            'transport.user-account-events',
            NEW.id::text, 'pending', 10,
            jsonb_build_object(
                'write_to_eventstore', true,
                'compensating_event', true,
                'changed_by', 'EXTERNAL_SQL',
                'severity', 'HIGH'
            ),
            NOW()
        );

        PERFORM pg_notify('outbox_events', NEW.id::text);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### Step 2: Add Helper Functions to Database Client

Add these functions to your PostgreSQL client module (e.g., `pg_client.py`):

```python
from contextlib import asynccontextmanager
from typing import Any, Optional

@asynccontextmanager
async def with_app_context(database: str = "main"):
    """
    Context manager that sets app_context to bypass CES triggers.

    CES triggers detect external SQL changes. When the application makes
    changes through normal code paths, we set this context to skip
    trigger execution.

    Usage:
        async with with_app_context():
            await db.execute("UPDATE user_accounts SET is_active = $1 WHERE id = $2", False, user_id)
    """
    async with acquire_connection(database) as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL wellwon.app_context = 'true'")
            yield conn
            # Transaction commits here, SET LOCAL automatically resets


async def execute_with_app_context(
    query: str,
    *args: Any,
    database: str = "main",
    timeout: Optional[float] = None
) -> str:
    """
    Execute a query with app_context set to bypass CES triggers.

    Use this for any UPDATE/INSERT/DELETE that modifies fields monitored
    by CES triggers (e.g., is_active, status, role, etc.)
    """
    async with with_app_context(database) as conn:
        return await conn.execute(query, *args, timeout=timeout)
```

### Step 3: Add to Database Proxy Class

Make the helpers accessible via your database proxy:

```python
class _DBProxy:
    """Proxy for database operations"""
    fetch = staticmethod(fetch)
    fetchrow = staticmethod(fetchrow)
    fetchval = staticmethod(fetchval)
    execute = staticmethod(execute)
    transaction = staticmethod(transaction)
    # CES trigger bypass helpers
    with_app_context = staticmethod(with_app_context)
    execute_with_app_context = staticmethod(execute_with_app_context)

db = _DBProxy()
```

### Step 4: Update Repository Methods

Identify all repository methods that update CES-monitored fields and update them to use `execute_with_app_context`:

```python
# app/infra/read_repos/user_account_read_repo.py

from app.infra.persistence.pg_client import db as pg_db_proxy, execute_with_app_context

class UserAccountReadRepo:

    async def update_user_status(
        self,
        user_id: UUID,
        is_active: bool,
        reason: Optional[str] = None
    ) -> None:
        """
        Update user active status.
        Uses execute_with_app_context to bypass CES trigger.
        """
        sql = """
            UPDATE user_accounts
            SET is_active = $2,
                status_reason = $3,
                updated_at = NOW()
            WHERE id = $1
        """

        # Use execute_with_app_context to bypass CES trigger
        await execute_with_app_context(sql, user_id, is_active, reason)

        # Invalidate and refresh cache
        await self.invalidate_user_cache(user_id)

    async def update_user_role(
        self,
        user_id: UUID,
        new_role: str
    ) -> None:
        """
        Update user role.
        Uses execute_with_app_context to bypass CES trigger.
        """
        sql = "UPDATE user_accounts SET role = $2, updated_at = NOW() WHERE id = $1"

        # Use execute_with_app_context to bypass CES trigger
        await execute_with_app_context(sql, user_id, new_role)

        await self.invalidate_user_cache(user_id)

    async def update_specific_fields(
        self,
        user_id: UUID,
        updates: Dict[str, Any]
    ) -> None:
        """
        Update specific fields of a user account.
        Automatically detects if CES-monitored fields are being updated.
        """
        if not updates:
            return

        updates["updated_at"] = datetime.now(timezone.utc)

        set_clauses = ", ".join([f"{field} = ${i + 2}" for i, field in enumerate(updates.keys())])
        sql = f"UPDATE user_accounts SET {set_clauses} WHERE id = $1"
        params = [user_id] + list(updates.values())

        # CES-monitored fields for user_accounts table
        ces_monitored_fields = {"is_active", "role", "status"}

        # Use execute_with_app_context if updating any CES-monitored field
        if ces_monitored_fields & set(updates.keys()):
            await execute_with_app_context(sql, *params)
        else:
            await pg_db_proxy.execute(sql, *params)

        await self.invalidate_user_cache(user_id)
```

### Step 5: Update Migration Files

Ensure your migration files include the app context check for all CES triggers:

```sql
-- migrations/007_add_ces_triggers.sql

-- User status change trigger
CREATE OR REPLACE FUNCTION notify_user_status_changed()
RETURNS TRIGGER AS $$
BEGIN
    -- Skip if change is from application (not external SQL)
    IF current_setting('wellwon.app_context', true) = 'true' THEN
        RETURN NEW;
    END IF;

    IF OLD.is_active IS DISTINCT FROM NEW.is_active THEN
        -- ... insert into event_outbox ...
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- User role change trigger
CREATE OR REPLACE FUNCTION notify_user_role_changed()
RETURNS TRIGGER AS $$
BEGIN
    -- Skip if change is from application (not external SQL)
    IF current_setting('wellwon.app_context', true) = 'true' THEN
        RETURN NEW;
    END IF;

    IF OLD.role IS DISTINCT FROM NEW.role THEN
        -- ... insert into event_outbox ...
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

## Usage Examples

### Example 1: Simple Status Update

```python
# In command handler or service
async def deactivate_user(user_id: UUID, reason: str):
    # This will NOT trigger UserStatusChangedExternally
    await user_repo.update_user_status(user_id, is_active=False, reason=reason)

    # The domain event is published by the aggregate/command handler
    await event_bus.publish("transport.user-events", UserDeactivated(...))
```

### Example 2: Batch Updates

```python
async def deactivate_inactive_users(user_ids: List[UUID]):
    """Batch deactivate users without triggering CES events."""

    id_list = ','.join([f"'{str(uid)}'" for uid in user_ids])

    sql = f"""
        UPDATE user_accounts
        SET is_active = false,
            status_reason = 'Bulk deactivation',
            updated_at = NOW()
        WHERE id IN ({id_list})
    """

    # Use execute_with_app_context for batch operation
    await execute_with_app_context(sql)
```

### Example 3: Complex Transaction with Multiple Updates

```python
async def transfer_user_ownership(old_user_id: UUID, new_user_id: UUID):
    """Transfer ownership with multiple updates in single transaction."""

    async with with_app_context() as conn:
        # Deactivate old user
        await conn.execute(
            "UPDATE user_accounts SET is_active = false WHERE id = $1",
            old_user_id
        )

        # Update new user role
        await conn.execute(
            "UPDATE user_accounts SET role = 'admin' WHERE id = $1",
            new_user_id
        )

        # Transfer resources
        await conn.execute(
            "UPDATE resources SET owner_id = $2 WHERE owner_id = $1",
            old_user_id, new_user_id
        )
    # All changes committed, app_context automatically reset
```

### Example 4: Conditional App Context

```python
async def update_user_fields(user_id: UUID, updates: Dict[str, Any]):
    """Update user fields, using app_context only when necessary."""

    ces_fields = {"is_active", "role", "status"}
    needs_app_context = bool(ces_fields & set(updates.keys()))

    sql = build_update_sql("user_accounts", updates)
    params = [user_id] + list(updates.values())

    if needs_app_context:
        await execute_with_app_context(sql, *params)
    else:
        await db.execute(sql, *params)
```

---

## Testing & Verification

### Test 1: Verify Trigger Has App Context Check

```sql
-- Check trigger function source
SELECT prosrc
FROM pg_proc
WHERE proname = 'notify_user_status_changed';

-- Should contain:
-- IF current_setting('wellwon.app_context', true) = 'true' THEN
--     RETURN NEW;
-- END IF;
```

### Test 2: Verify App Context Bypass Works

```sql
-- Test 1: Without app_context (should generate CES event)
BEGIN;
UPDATE user_accounts SET is_active = false WHERE id = 'test-user-id';
SELECT COUNT(*) FROM event_outbox WHERE event_type = 'UserStatusChangedExternally';
-- Expected: 1
ROLLBACK;

-- Test 2: With app_context (should NOT generate CES event)
BEGIN;
SET LOCAL wellwon.app_context = 'true';
UPDATE user_accounts SET is_active = false WHERE id = 'test-user-id';
SELECT COUNT(*) FROM event_outbox WHERE event_type = 'UserStatusChangedExternally';
-- Expected: 0
ROLLBACK;
```

### Test 3: Python Integration Test

```python
import pytest
from app.infra.persistence.pg_client import db, execute_with_app_context

@pytest.mark.asyncio
async def test_app_context_bypasses_ces_trigger():
    """Verify execute_with_app_context bypasses CES triggers."""

    # Get initial event count
    initial_count = await db.fetchval(
        "SELECT COUNT(*) FROM event_outbox WHERE event_type = 'UserStatusChangedExternally'"
    )

    # Update using execute_with_app_context
    await execute_with_app_context(
        "UPDATE user_accounts SET is_active = false WHERE id = $1",
        test_user_id
    )

    # Verify no new CES event was created
    final_count = await db.fetchval(
        "SELECT COUNT(*) FROM event_outbox WHERE event_type = 'UserStatusChangedExternally'"
    )

    assert final_count == initial_count, "CES event should not be generated for app operations"

    # Cleanup
    await execute_with_app_context(
        "UPDATE user_accounts SET is_active = true WHERE id = $1",
        test_user_id
    )
```

### Test 4: Verify External SQL Still Triggers CES

```python
@pytest.mark.asyncio
async def test_external_sql_triggers_ces():
    """Verify direct SQL (without app_context) triggers CES."""

    initial_count = await db.fetchval(
        "SELECT COUNT(*) FROM event_outbox WHERE event_type = 'UserStatusChangedExternally'"
    )

    # Update WITHOUT app_context (simulating external SQL)
    await db.execute(
        "UPDATE user_accounts SET is_active = false WHERE id = $1",
        test_user_id
    )

    final_count = await db.fetchval(
        "SELECT COUNT(*) FROM event_outbox WHERE event_type = 'UserStatusChangedExternally'"
    )

    assert final_count == initial_count + 1, "CES event should be generated for external SQL"
```

---

## Troubleshooting

### Issue: CES Events Still Being Generated

**Symptoms:**
- `*ChangedExternally` events appear in logs for normal operations
- Duplicate events in event store

**Solutions:**

1. **Verify trigger has app_context check:**
   ```sql
   SELECT prosrc FROM pg_proc WHERE proname = 'notify_user_status_changed';
   ```

2. **Verify repository is using execute_with_app_context:**
   ```python
   # Check your repository method
   async def update_status(...):
       await execute_with_app_context(sql, *params)  # Correct
       # NOT: await db.execute(sql, *params)  # Wrong
   ```

3. **Check for direct db.execute calls:**
   ```bash
   grep -r "db.execute.*is_active" app/
   grep -r "db.execute.*role" app/
   ```

### Issue: App Context Not Being Set

**Symptoms:**
- All updates trigger CES events
- `current_setting` returns empty string

**Solutions:**

1. **Verify SET LOCAL is inside transaction:**
   ```python
   # Correct - SET LOCAL inside transaction
   async with conn.transaction():
       await conn.execute("SET LOCAL wellwon.app_context = 'true'")
       await conn.execute(update_sql, *params)

   # Wrong - SET LOCAL outside transaction (resets immediately)
   await conn.execute("SET LOCAL wellwon.app_context = 'true'")
   await conn.execute(update_sql, *params)
   ```

2. **Use the helper functions:**
   ```python
   # Use the provided helpers instead of manual SET LOCAL
   await execute_with_app_context(sql, *params)
   ```

### Issue: App Context Persisting Across Requests

**Symptoms:**
- CES never triggers, even for actual external SQL
- App context seems "stuck"

**Solutions:**

1. **Use SET LOCAL, not SET:**
   ```sql
   -- Correct: Scoped to transaction
   SET LOCAL wellwon.app_context = 'true';

   -- Wrong: Persists for entire session
   SET wellwon.app_context = 'true';
   ```

2. **Ensure transactions are committed/rolled back:**
   ```python
   async with conn.transaction():
       # ... operations ...
   # Transaction ends here, SET LOCAL automatically resets
   ```

### Issue: Trigger Function Not Found

**Symptoms:**
- Error: function notify_user_status_changed() does not exist

**Solutions:**

1. **Run the migration:**
   ```bash
   psql -d yourdb -f migrations/007_add_ces_triggers.sql
   ```

2. **Create function manually:**
   ```sql
   CREATE OR REPLACE FUNCTION notify_user_status_changed() ...
   ```

---

## Checklist for New CES Triggers

When adding a new CES trigger to your system:

- [ ] Add app_context check as first statement in trigger function
- [ ] Update migration file with the new trigger
- [ ] Identify all repository methods that update the monitored field(s)
- [ ] Update repository methods to use `execute_with_app_context`
- [ ] Add tests for both app operations and external SQL
- [ ] Document which fields are CES-monitored for that table
- [ ] Update this documentation with new trigger details

---

## Reference: CES-Monitored Fields by Table

| Table | Field | Trigger Function | CES Event |
|-------|-------|------------------|-----------|
| user_accounts | is_active | notify_user_status_changed | UserStatusChangedExternally |
| user_accounts | role | notify_user_role_changed | UserRoleChangedExternally |
| broker_connections | connected | notify_broker_connection_status_changed | BrokerConnectionStatusChangedExternally |
| orders | (DELETE) | notify_order_deleted | OrderDeletedExternally |
| positions | (DELETE) | notify_position_deleted | PositionDeletedExternally |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-25 | Initial documentation |

---

## See Also

- [Event Sourcing Architecture](./EVENT_SOURCING.md)
- [CQRS Pattern](./CQRS.md)
- [Domain Event Registration](./EVENT_AUTOREGISTRATION_EXAMPLE.md)
