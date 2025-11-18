# Saga Patterns Reference

**Status**: ✅ Reference Guide
**Last Updated**: 2025-11-10
**Applies To**: TradeCore v0.5+

---

## Table of Contents

1. [Overview](#overview)
2. [Common Saga Patterns](#common-saga-patterns)
3. [Pattern Catalog](#pattern-catalog)
4. [Implementation Examples](#implementation-examples)

---

## Overview

**Sagas** coordinate distributed transactions across multiple aggregates/domains. TradeCore implements TRUE SAGA pattern: Event-driven orchestration with NO query_bus dependency for core logic.

### TRUE SAGA Principles (2025 Refactor)

✅ **DO:**
- Use CommandBus for orchestration
- Extract data from enriched events (no queries)
- Use queries ONLY for safety validations (pre-delete checks)
- Implement compensation for reversible steps
- Publish completion/failure events

❌ **DON'T:**
- Query read models for core saga logic
- Use queries to get entity IDs (should be in event)
- Skip compensation (always implement, even if no-op)
- Block on SYNC projections (let workers handle)

---

## Common Saga Patterns

### 1. Connection Saga (Account Discovery)

**Use Case:** After broker connection, discover and link accounts

**Trigger Event:** `BrokerConnectionEstablished`

**Flow:**
```
BrokerConnectionEstablished
    ↓
BrokerConnectionSaga.start()
    ↓
Step 1: Verify connection exists (SYNC projection check)
    ↓
Step 2: Discover accounts (call broker API)
    ↓
Step 3: Link accounts (emit BrokerAccountLinked events)
    ↓
Step 4: Publish completion
    ↓
BrokerConnectionEstablishedSagaCompleted
```

**Key Features:**
- Idempotent (checks if accounts already exist)
- Virtual broker optimized (10x faster timeout)
- Compensation: Delete discovered accounts on failure

**Code:** `app/infra/saga/broker_connection_saga.py`

---

### 2. Disconnection Saga (Cleanup)

**Use Case:** Clean up all resources when broker disconnected

**Trigger Event:** `BrokerDisconnected`

**Flow:**
```
BrokerDisconnected (enriched with account_ids, automation_ids)
    ↓
BrokerDisconnectionSaga.start()
    ↓
Step 1: Validate disconnection (race condition check)
    ↓
Step 2: Clear broker cache
    ↓
Step 3: Delete broker accounts (from event data)
    ↓
Step 4: Cleanup virtual broker data (if virtual)
    ↓
Step 5: Validate accounts deleted (eventual consistency check)
    ↓
Step 6: Clear adapter resources
    ↓
Step 7: Final cache cleanup
    ↓
Step 8: Purge connection (re-validate before delete)
    ↓
BrokerDisconnectionCompleted
```

**Key Features:**
- TRUE SAGA: Account IDs from enriched event (NO queries for core logic)
- Distributed locking (prevent concurrent disconnects)
- Race condition prevention (re-validate before purge)
- Nuclear cleanup for critical errors (cache corruption, duplicate accounts)

**Code:** `app/infra/saga/broker_disconnection_saga.py`

---

### 3. Recovery Saga (Reconnection)

**Use Case:** Automatically recover failed broker connections

**Trigger Event:** `BrokerConnectionFailed` or `BrokerStreamingDisconnected`

**Flow:**
```
BrokerConnectionFailed
    ↓
ConnectionRecoverySaga.start()
    ↓
Step 1: Verify recoverable (check if requires user action)
    ↓
Step 2: Attempt health check
    ↓
Step 3: If failed → Attempt reconnection
    ↓
Step 4: Verify recovery succeeded
    ↓
Step 5: Publish recovery status
    ↓
BrokerConnectionRecovered / BrokerConnectionRecoveryFailed
```

**Key Features:**
- Max retry limit (3 attempts)
- Exponential backoff (2s, 4s, 8s)
- User action required check (invalid credentials)
- Compensation: Publish failure event for user alert

**Code:** `app/infra/saga/connection_recovery_saga.py`

---

### 4. User Deletion Saga (Cascade)

**Use Case:** Cascade delete all user resources across domains

**Trigger Event:** `UserAccountDeleted` (enriched with owned resource IDs)

**Flow:**
```
UserAccountDeleted (enriched with connection_ids, account_ids, automation_ids)
    ↓
UserDeletionSaga.start()
    ↓
Step 1: Extract resource IDs from event (TRUE SAGA)
    ↓
Step 2: Disconnect all brokers (triggers BrokerDisconnectionSaga for each)
    ↓
Step 3: Wait for cascade completion (BrokerDisconnectionSaga instances)
    ↓
Step 4: Cleanup virtual broker data + clear ALL caches
    ↓
Step 5: Publish user deleted event (SKIP - already published)
    ↓
Step 6: Complete deletion + trigger hard delete
    ↓
UserDeletionCompleted
```

**Key Features:**
- TRUE SAGA: NO queries (data from enriched event)
- Saga composition (delegates to BrokerDisconnectionSaga)
- Cache cleanup (VB cache, Redis cache, QueryBus cache)
- Virtual broker accounts deleted from VB database

**Code:** `app/infra/saga/user_deletion_saga.py`

---

### 5. Order Execution Saga (Trading)

**Use Case:** Place order with broker, handle fills, update positions

**Trigger Event:** `OrderPlacedEvent`

**Flow:**
```
OrderPlacedEvent
    ↓
OrderExecutionSaga.start()
    ↓
Step 1: Validate order (account, buying power, limits)
    ↓
Step 2: Submit order to broker
    ↓
Step 3: Wait for acknowledgment
    ↓
Step 4: Monitor for fills (streaming or polling)
    ↓
Step 5: Update position on fill
    ↓
Step 6: Calculate P&L
    ↓
OrderExecutionCompleted
```

**Compensation:**
- Cancel order if submission fails
- Rollback position if fill rejected

**Code:** `app/infra/saga/order_execution_saga.py`

---

### 6. Position Management Saga (Pyramiding)

**Use Case:** Manage complex position lifecycle (pyramiding, scaling)

**Trigger Event:** `PositionOpenedEvent`

**Flow:**
```
PositionOpenedEvent
    ↓
PositionManagementSaga.start()
    ↓
Step 1: Initialize position tracking
    ↓
Step 2: Monitor for add-on orders (pyramiding)
    ↓
Step 3: Update average price on fills
    ↓
Step 4: Monitor for stop loss / take profit
    ↓
Step 5: Close position on exit signal
    ↓
PositionManagementCompleted
```

**Code:** `app/infra/saga/position_management_saga.py`

---

## Pattern Catalog

### Pattern: Event-Driven Orchestration (TRUE SAGA)

**Problem:** Sagas querying read models creates coupling and eventual consistency issues.

**Solution:** Enrich events with all data saga needs. Saga extracts data from event, NO queries for core logic.

**Example:**

```python
# BAD: Query-driven saga
async def _get_accounts_to_delete(self, **context):
    broker_connection_id = context['broker_connection_id']

    # ❌ Query read model (creates coupling)
    accounts = await query_bus.query(
        GetAccountsByConnectionQuery(broker_connection_id)
    )

    return {'account_ids': [acc.id for acc in accounts]}

# GOOD: Event-driven saga (TRUE SAGA)
async def _get_accounts_to_delete(self, **context):
    # ✅ Extract from enriched event (NO queries!)
    linked_account_ids = context.get('linked_account_ids', [])
    virtual_account_ids = context.get('virtual_account_ids', [])

    return {
        'linked_account_ids': linked_account_ids,
        'virtual_account_ids': virtual_account_ids
    }
```

**Benefits:**
- Decoupled from read model
- No eventual consistency issues
- Faster (no DB queries)
- Easier to test (mock event data)

---

### Pattern: Idempotent Step

**Problem:** Saga retries cause duplicate operations (e.g., create account twice).

**Solution:** Check if operation already completed before executing.

**Example:**

```python
async def _discover_accounts(self, **context):
    """Idempotent account discovery"""

    # Check if accounts already exist
    existing_accounts = await query_bus.query(
        GetAccountsByConnectionQuery(broker_connection_id)
    )

    if existing_accounts:
        # Already discovered - return cached result
        return {
            'accounts_discovered': True,
            'already_existed': True,
            'account_ids': [str(acc.id) for acc in existing_accounts],
            'discovery_attempts': 0
        }

    # Proceed with discovery...
```

**Benefits:**
- Safe saga retry
- Faster retry (skip expensive operation)
- No compensation needed

---

### Pattern: Race Condition Prevention (Pre-Action Validation)

**Problem:** State changes between saga steps (user reconnects while disconnection saga runs).

**Solution:** Re-validate critical conditions RIGHT BEFORE irreversible actions.

**Example:**

```python
async def _purge_connection(self, **context):
    """Purge connection with race condition check"""

    # CRITICAL: Re-validate connection state RIGHT BEFORE purging
    connection_details = await query_bus.query(
        GetBrokerConnectionDetailsQuery(broker_connection_id)
    )

    if connection_details.status == BrokerConnectionStatusEnum.CONNECTED:
        # User reconnected! Abort purge to prevent data loss
        log.error("ABORTING - Connection is CONNECTED. User has reconnected.")
        return {'purged': False, 'reason': 'connection_reconnected', 'aborted': True}

    # Verify NO accounts exist
    accounts = await query_bus.query(GetAccountsByConnectionQuery(broker_connection_id))
    if accounts:
        # Accounts created AFTER deletion step! Abort purge
        log.error(f"ABORTING - Found {len(accounts)} accounts after deletion")
        return {'purged': False, 'reason': 'accounts_exist_after_deletion', 'aborted': True}

    # Safe to purge
    await command_bus.send(PurgeBrokerConnectionCommand(broker_connection_id))
```

**Benefits:**
- Prevents data loss in fast connect/disconnect/connect cycles
- TOCTOU (Time-Of-Check-Time-Of-Use) protection
- Graceful abort on race condition

---

### Pattern: Distributed Locking

**Problem:** Multiple saga instances try to process same entity concurrently.

**Solution:** Acquire distributed lock before saga execution.

**Example:**

```python
async def _validate_disconnection(self, **context):
    """Validate with distributed lock"""

    lock_key = f"broker:disconnect:lock:{broker_connection_id}"
    lock_value = f"{self.saga_id}:{datetime.now(timezone.utc).isoformat()}"

    # Acquire lock (5 min TTL)
    lock_acquired = await safe_set(lock_key, lock_value, ttl_seconds=300, nx=True)

    if not lock_acquired:
        # Another process is handling this
        log.warning("Lock not acquired. Another process may be disconnecting.")
        await asyncio.sleep(3.0)  # Wait and check status

    try:
        # Perform validation...
        return {'lock_acquired': lock_acquired}
    finally:
        # Release lock
        if lock_acquired:
            await safe_delete(lock_key)
```

**Benefits:**
- Prevents concurrent saga execution
- Graceful handling when lock unavailable
- Automatic cleanup with TTL

---

### Pattern: Saga Composition

**Problem:** Complex workflow spans multiple domains.

**Solution:** Parent saga delegates to child sagas.

**Example:**

```python
# Parent: UserDeletionSaga
async def _disconnect_all_brokers(self, **context):
    """Delegate to BrokerDisconnectionSaga for each connection"""

    # Send command that triggers child sagas
    result = await command_bus.send(DisconnectAllBrokersCommand(user_id))

    # This command emits BrokerDisconnected events
    # Each event triggers a BrokerDisconnectionSaga instance

    return {
        'brokers_disconnected': result['disconnected_count'],
        'child_sagas_triggered': result['disconnected_count']
    }

# Wait for child sagas to complete
async def _wait_for_cascade_completion(self, **context):
    """Allow time for child sagas to finish"""

    disconnected_count = context['disconnected_count']
    wait_time = min(5 + (disconnected_count * 2), 30)  # Max 30s

    await asyncio.sleep(wait_time)
```

**Benefits:**
- Separation of concerns (each saga has single responsibility)
- Reusable child sagas
- Parallel execution (child sagas run independently)

---

### Pattern: Eventual Consistency with Retry

**Problem:** Projection lag causes validation to fail (accounts not deleted yet).

**Solution:** Poll read model with exponential backoff until consistent.

**Example:**

```python
async def _validate_all_accounts_deleted(self, **context):
    """Poll until projections complete (eventual consistency)"""

    async def check_accounts_deleted() -> bool:
        # Wait for PostgreSQL commit propagation
        await asyncio.sleep(0.15)

        # Clear cache to get fresh data
        await cache_manager.clear_connection_cache(broker_connection_id)

        # Query read model
        accounts = await query_bus.query(GetAccountsByConnectionQuery(broker_connection_id))

        if accounts:
            # Still exist - trigger retry
            raise RuntimeError(f"Accounts still in read model: {len(accounts)}")

        return True  # All deleted

    # Retry with exponential backoff
    retry_config = RetryConfig(
        max_attempts=5,
        initial_delay_ms=500,
        max_delay_ms=2000,
        backoff_factor=1.5,
        jitter=True
    )

    await retry_async(check_accounts_deleted, retry_config=retry_config)
```

**Benefits:**
- Handles projection lag gracefully
- Exponential backoff prevents hammering DB
- Jitter prevents thundering herd

---

### Pattern: Nuclear Cleanup

**Problem:** Critical errors (duplicate accounts, cache corruption) require aggressive cleanup.

**Solution:** Detect critical errors and perform comprehensive cleanup.

**Example:**

```python
CRITICAL_DISCONNECT_REASONS = {
    'duplicate_accounts',
    'data_corruption',
    'cache_corruption',
    'sync_failure',
    'nuclear_cleanup',
}

async def _clear_broker_cache(self, **context):
    """Nuclear cleanup for critical errors"""

    disconnect_reason = context.get('disconnect_reason', '')

    if self._is_critical_disconnect_reason(disconnect_reason):
        # Nuclear option: Clear ALL user+broker caches
        log.warning(f"Critical disconnect: {disconnect_reason}. Performing nuclear cleanup.")

        cleared = await cache_manager.clear_all_user_broker_data(
            user_id=str(user_id),
            broker_id=broker_id
        )

        return {'cache_cleared': True, 'cleanup_type': 'nuclear', 'entries_cleared': cleared}
    else:
        # Standard cleanup
        # ...
```

**Benefits:**
- Recover from data corruption
- Comprehensive cleanup for edge cases
- Documented escalation path

---

## Implementation Examples

### Complete Saga Structure

```python
class MyDomainSaga(BaseSaga):
    """Template for implementing sagas"""

    def __init__(self, saga_id: Optional[uuid.UUID] = None):
        super().__init__(saga_id)
        # Instance variables for tracking state
        self._entity_id: Optional[uuid.UUID] = None
        self._operation_count: int = 0

    def get_saga_type(self) -> str:
        """Saga type name for metrics"""
        return "MyDomainSaga"

    def get_timeout(self) -> timedelta:
        """Saga timeout from config"""
        return saga_config.get_timeout_for_saga(self.get_saga_type())

    def define_steps(self) -> List[SagaStep]:
        """Define saga steps"""
        return [
            SagaStep(
                name="step_1",
                execute=self._step_1,
                compensate=self._compensate_step_1,
                timeout_seconds=30,
                retry_count=3,
                retry_delay_base=1.0
            ),
            SagaStep(
                name="step_2",
                execute=self._step_2,
                compensate=self._compensate_step_2,
                timeout_seconds=60,
                retry_count=2
            ),
            # More steps...
        ]

    # =========================================================================
    # Step Implementations
    # =========================================================================

    async def _step_1(self, **context) -> Dict[str, Any]:
        """Step 1: Description"""
        # Extract from context/event
        entity_id = context['entity_id']
        command_bus = context['command_bus']

        # Execute step logic
        result = await command_bus.send(SomeCommand(entity_id))

        # Return step result
        return {'step_1_completed': True, 'result': result}

    async def _step_2(self, **context) -> Dict[str, Any]:
        """Step 2: Description"""
        # Can access previous step results
        step_1_result = context.get('result')

        # Execute step logic
        # ...

        return {'step_2_completed': True}

    # =========================================================================
    # Compensation Methods
    # =========================================================================

    async def _compensate_step_1(self, **context) -> None:
        """Compensate for step 1 failure"""
        entity_id = context['entity_id']
        command_bus = context['command_bus']

        # Undo step 1 operations
        await command_bus.send(RevertSomeCommand(entity_id))

        log.warning(f"Saga {self.saga_id}: Compensated step 1")

    async def _compensate_step_2(self, **context) -> None:
        """Compensate for step 2 failure"""
        # Implement compensation or no-op if not needed
        pass
```

---

## Quick Reference

### Saga Checklist

**Before Implementing:**
```
□ Identify trigger event
□ Define all steps (execute + compensate)
□ Extract required data from event (NO queries for core logic)
□ Implement idempotency for retryable steps
□ Add race condition checks before irreversible actions
□ Configure timeouts (virtual: 10x faster than real)
□ Add distributed locking if needed
□ Implement compensation for reversible steps
□ Publish completion/failure events
```

**TRUE SAGA Requirements:**
```
□ Event contains ALL data saga needs (enrich event in handler)
□ Queries ONLY for safety validations (not core logic)
□ Use CommandBus for orchestration
□ Publish domain events for saga state changes
□ Handle compensation gracefully
□ Support saga retry (idempotent steps)
```

---

## References

- **Saga Manager**: `app/infra/saga/saga_manager.py`
- **Saga Config**: `app/config/saga_config.py`
- **Example Sagas**: `app/infra/saga/*.py`
- **TRUE SAGA Refactor**: `ALL_SAGAS_REFACTORED_COMPLETE_NOV2025.md`
- **Compensation Guide**: `docs/reference/COMPENSATION_GUIDE.md`

---

**Last Updated**: 2025-11-10
**Next Review**: 2026-01-10
