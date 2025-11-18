# True Saga Pattern Implementation Guide

**TradeCore v0.5 - Event-Driven Orchestration**

## Table of Contents

1. [What is True Saga Pattern](#what-is-true-saga-pattern)
2. [Architecture Principles](#architecture-principles)
3. [Event Enrichment Pattern](#event-enrichment-pattern)
4. [Step-by-Step Creation](#step-by-step-creation)
5. [Context Builder Critical Pattern](#context-builder-critical-pattern)
6. [Compensation Patterns](#compensation-patterns)
7. [Performance Optimization](#performance-optimization)
8. [Monitoring & Metrics](#monitoring--metrics)
9. [Troubleshooting](#troubleshooting)

---

## What is True Saga Pattern

### Definition

**True Saga Pattern** is an event-driven orchestration pattern where:

- ✅ **All data comes from enriched events** (NO queries in saga logic)
- ✅ **Command Bus orchestration** (sagas dispatch commands to domains)
- ✅ **Event enrichment by handlers** (handlers query data → enrich events → saga uses event data)
- ✅ **Compensation logic** (rollback on failures)
- ✅ **Distributed transactions** (across multiple domains)

### Why It Exists

**Problem with Traditional Sagas:**
```python
# ❌ ANTI-PATTERN: Query-based saga (violates CQRS/ES)
async def _cleanup_virtual_broker(self, **context):
    broker_connection_id = context['broker_connection_id']

    # BAD: Saga queries read model directly
    accounts = await self.query_bus.query(
        GetVirtualAccountsByConnectionQuery(connection_id=broker_connection_id)
    )

    # BAD: Saga loops through query results
    for account in accounts:
        await self.command_bus.send(DeleteAccountCommand(account_id=account.id))
```

**Issues:**
- Saga depends on read model consistency
- Eventual consistency causes race conditions
- Violates event-driven architecture (saga shouldn't query)
- Not idempotent (retries may see different data)

**True Saga Solution:**
```python
# ✅ TRUE SAGA: Event-driven saga (CQRS/ES compliant)
async def _cleanup_virtual_broker(self, **context):
    # Data already in event (handler enriched it!)
    virtual_account_ids = context['virtual_account_ids']  # From BrokerDisconnected event
    broker_connection_id = context['broker_connection_id']

    # TRUE SAGA: Use event data, no queries!
    delete_command = DeleteVirtualBrokerAccounts(
        user_id=context['user_id'],
        broker_connection_id=broker_connection_id,
        account_ids=virtual_account_ids,  # From enriched event
        saga_id=self.saga_id
    )

    await command_bus.send(delete_command)
```

---

## Architecture Principles

### 1. Event-Driven Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMMAND HANDLER (Write Side)                  │
│              Business Logic + Event Enrichment                   │
├─────────────────────────────────────────────────────────────────┤
│  API Request → Command → Handler → Aggregate                     │
│                                      ↓                           │
│  Handler Queries Data (query_bus) → Enrich Event                │
│                                      ↓                           │
│                              Domain Event (ENRICHED)             │
│                                      ↓                           │
│                           Event Store (Redpanda)                 │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                         SAGA SERVICE                             │
│                  (Event-Driven Orchestration)                    │
├─────────────────────────────────────────────────────────────────┤
│  Event Trigger → Context Builder → Saga Steps                   │
│                                      ↓                           │
│  Step 1: Extract data from enriched event (NO queries!)         │
│  Step 2: Send commands to domains (orchestration)               │
│  Step 3: Publish completion events                              │
└─────────────────────────────────────────────────────────────────┘
```

### 2. No Queries in Saga Logic

**Rule:** Sagas ONLY query for **safety validations**, never for core logic.

**Examples:**

✅ **Allowed (Safety Validation):**
```python
# Check if connection still exists (race condition prevention)
connection = await query_bus.query(GetBrokerConnectionDetailsQuery(...))
if connection.connected:
    log.error("ABORT - User reconnected!")
    return {'skip_remaining_steps': True}  # Safety abort
```

❌ **Forbidden (Core Logic):**
```python
# WRONG: Querying to get list of accounts to delete
accounts = await query_bus.query(GetAccountsByConnectionQuery(...))
for account in accounts:  # WRONG: Loop through query results
    await command_bus.send(DeleteAccountCommand(account.id))
```

### 3. Command Bus Orchestration

Sagas orchestrate domains using **CommandBus**, never direct DB access:

```python
# ✅ CORRECT: Send command to domain
await command_bus.send(DeleteBrokerAccountCommand(
    account_aggregate_id=account_id,
    user_id=user_id,
    saga_id=self.saga_id
))

# ❌ WRONG: Direct database access
await pg_client.execute("DELETE FROM broker_accounts WHERE id = $1", account_id)
```

---

## Event Enrichment Pattern

### How It Works

**Step 1: Handler Enriches Event**

```python
# app/broker_connection/command_handlers/disconnect_handlers.py
@command_handler(DisconnectBrokerCommand)
async def handle_disconnect_broker(command: DisconnectBrokerCommand, deps: HandlerDependencies):
    """Handler queries data and enriches event"""

    # 1. Load aggregate
    aggregate = await deps.aggregate_repository.load(command.broker_connection_id)

    # 2. QUERY: Get linked accounts (handler can query!)
    linked_accounts = await deps.query_bus.query(
        GetAccountsByConnectionQuery(broker_connection_id=command.broker_connection_id)
    )

    # 3. QUERY: Get virtual accounts
    virtual_accounts = await deps.query_bus.query(
        GetVirtualAccountsByConnectionQuery(connection_id=command.broker_connection_id)
    )

    # 4. QUERY: Get active automations
    automations = await deps.query_bus.query(
        GetActiveAutomationsByConnectionQuery(connection_id=command.broker_connection_id)
    )

    # 5. Aggregate emits ENRICHED event
    aggregate.disconnect(
        reason=command.reason,
        linked_account_ids=[acc.id for acc in linked_accounts],  # ENRICHED
        virtual_account_ids=[acc.id for acc in virtual_accounts],  # ENRICHED
        active_automation_ids=[auto.id for auto in automations]  # ENRICHED
    )

    await deps.aggregate_repository.save(aggregate)
```

**Step 2: Aggregate Emits Enriched Event**

```python
# app/broker_connection/aggregate.py
def disconnect(
    self,
    reason: str,
    linked_account_ids: List[UUID],
    virtual_account_ids: List[UUID],
    active_automation_ids: List[UUID]
):
    """Emit enriched disconnection event"""
    event = BrokerDisconnected(
        broker_connection_id=self.id,
        user_id=self.user_id,
        broker_id=self.broker_id,
        environment=self.environment,
        reason=reason,
        # ENRICHED: All account IDs from handler queries
        linked_account_ids=[str(id) for id in linked_account_ids],
        virtual_account_ids=[str(id) for id in virtual_account_ids],
        active_automation_ids=[str(id) for id in active_automation_ids],
        disconnected_at=datetime.now(UTC)
    )
    self.apply(event)
```

**Step 3: Saga Uses Enriched Event Data**

```python
# app/infra/saga/broker_disconnection_saga.py
async def _delete_broker_accounts(self, **context) -> Dict[str, Any]:
    """TRUE SAGA: Delete accounts using IDs from enriched event"""

    # NO QUERIES! Data from event context
    linked_account_ids = context['linked_account_ids']  # From BrokerDisconnected event
    virtual_account_ids = context['virtual_account_ids']  # From BrokerDisconnected event

    # Loop through event data (not query results!)
    for account_id in linked_account_ids:
        await command_bus.send(DeleteBrokerAccountCommand(
            account_aggregate_id=account_id,
            user_id=context['user_id'],
            saga_id=self.saga_id
        ))
```

---

## Step-by-Step Creation

### Step 1: Design Saga Steps and Compensation

**Example: User Deletion Saga**

```python
Steps:
1. get_user_resources        (Extract from enriched event)    → No compensation
2. disconnect_all_brokers    (Disconnect brokers)            → Compensate: Reconnect
3. wait_for_cascade          (Wait for cleanup)              → No compensation
4. cleanup_virtual_data      (Delete VB data)                → No compensation
5. publish_completion        (Publish event)                  → No compensation
```

**Design Questions:**
- What can fail? → Needs compensation
- What's idempotent? → No compensation needed
- What's a read-only check? → No compensation needed

### Step 2: Ensure Handler Enriches Events

**CRITICAL:** Handler must enrich event with ALL data saga needs.

```python
# ✅ CORRECT: Handler enriches event
@command_handler(DeleteUserAccountCommand)
async def handle_delete_user(command: DeleteUserAccountCommand, deps: HandlerDependencies):
    aggregate = await deps.aggregate_repository.load(command.user_id)

    # QUERY: Get all owned resources (handler can query!)
    connections = await deps.query_bus.query(GetConnectionsByUserQuery(user_id=command.user_id))
    accounts = await deps.query_bus.query(GetAccountsByUserQuery(user_id=command.user_id))
    automations = await deps.query_bus.query(GetAutomationsByUserQuery(user_id=command.user_id))

    # Emit ENRICHED event
    aggregate.delete(
        reason=command.reason,
        owned_connection_ids=[conn.id for conn in connections],  # ENRICHED
        owned_account_ids=[acc.id for acc in accounts],          # ENRICHED
        owned_automation_ids=[auto.id for auto in automations]   # ENRICHED
    )

    await deps.aggregate_repository.save(aggregate)
```

### Step 3: Implement Saga Class with BaseSaga

```python
# app/infra/saga/user_deletion_saga.py
from app.infra.saga.saga_manager import BaseSaga, SagaStep

class UserDeletionSaga(BaseSaga):
    """TRUE SAGA: Event-driven user deletion orchestration"""

    def get_saga_type(self) -> str:
        return "UserDeletionSaga"

    def get_timeout(self) -> timedelta:
        return saga_config.get_timeout_for_saga(self.get_saga_type(), is_virtual=False)

    def define_steps(self) -> List[SagaStep]:
        return [
            SagaStep(
                name="get_user_resources",
                execute=self._get_user_resources,
                compensate=self._noop_compensate,
                timeout_seconds=30,
                retry_count=2
            ),
            SagaStep(
                name="disconnect_all_brokers",
                execute=self._disconnect_all_brokers,
                compensate=self._compensate_broker_disconnection,
                timeout_seconds=60,
                retry_count=2
            ),
            # ... more steps
        ]
```

### Step 4: Define Saga Steps (Execute + Compensate)

```python
async def _get_user_resources(self, **context) -> Dict[str, Any]:
    """
    Step 1: Extract resource IDs from enriched UserAccountDeleted event.
    TRUE SAGA: NO query_bus calls - all data from event!
    """
    user_id = uuid.UUID(context['user_id'])

    # Extract enriched data from event
    owned_connection_ids = context.get('owned_connection_ids', [])
    owned_account_ids = context.get('owned_account_ids', [])
    owned_automation_ids = context.get('owned_automation_ids', [])
    has_virtual_broker = context.get('has_virtual_broker', False)

    log.info(
        f"Saga {self.saga_id}: TRUE SAGA - extracted from event: "
        f"{len(owned_connection_ids)} connections, {len(owned_account_ids)} accounts"
    )

    return {
        'owned_connection_ids': owned_connection_ids,
        'owned_account_ids': owned_account_ids,
        'owned_automation_ids': owned_automation_ids,
        'has_virtual_broker': has_virtual_broker,
        'data_source': 'enriched_event'  # Mark as TRUE SAGA
    }

async def _disconnect_all_brokers(self, **context) -> Dict[str, Any]:
    """Step 2: Disconnect all brokers using CommandBus"""
    user_id = uuid.UUID(context['user_id'])
    command_bus: 'CommandBus' = context['command_bus']

    # Use domain command (TRUE SAGA orchestration)
    command = DisconnectAllBrokersCommand(
        user_id=user_id,
        reason="user_deletion",
        saga_id=self.saga_id
    )

    result = await command_bus.send(command)

    return {
        'brokers_disconnected': True,
        'disconnected_count': result.get('disconnected_count', 0)
    }

async def _compensate_broker_disconnection(self, **context) -> None:
    """Compensate: Publish manual intervention event"""
    event_bus: EventBus = context['event_bus']

    await event_bus.publish("saga.compensation", {
        "event_id": str(uuid.uuid4()),
        "event_type": "BrokerDisconnectionCompensationRequired",
        "saga_id": str(self.saga_id),
        "user_id": str(context['user_id']),
        "reason": "Broker disconnection failed during user deletion",
        "requires_manual_intervention": True
    })
```

### Step 5: Add Saga Trigger in saga_service.py

```python
# app/services/saga_service.py
def _configure_triggers(self):
    self._trigger_configs["transport.user-account-events"] = [
        SagaTriggerConfig(
            event_types=["UserAccountDeleted", "UserDeleted"],
            saga_class=UserDeletionSaga,
            context_builder=lambda event: {
                'user_id': event['user_id'],
                'reason': event.get('reason', 'user_deletion'),
                # CRITICAL: Extract enriched data from event
                'owned_connection_ids': event.get('owned_connection_ids', []),
                'owned_account_ids': event.get('owned_account_ids', []),
                'owned_automation_ids': event.get('owned_automation_ids', []),
                'has_virtual_broker': event.get('has_virtual_broker', False),
                # CQRS metadata
                'correlation_id': event.get('correlation_id', event.get('event_id')),
                'causation_id': event.get('event_id'),
                'original_event_type': event.get('event_type')
            },
            dedupe_key_builder=lambda event: f"user_deletion:{event['user_id']}",
            dedupe_window_seconds=600,
            description="Triggers user deletion saga"
        )
    ]
```

### Step 6: Configure Context Builder (CRITICAL!)

**CRITICAL PATTERN:** Context builder MUST extract ALL enriched fields from event.

**🐛 Real Bug We Found (Nov 2025):**

```python
# ❌ BUG: Missing enriched fields in context_builder
context_builder=lambda event: {
    'broker_connection_id': event.get('aggregate_id'),
    'user_id': event.get('user_id'),
    'broker_id': event.get('broker_id'),
    'reason': event.get('reason'),
    # 🐛 MISSING: linked_account_ids, virtual_account_ids!
}

# Result: Saga has empty lists, deletes nothing!
```

**✅ FIX: Extract ALL enriched fields:**

```python
# ✅ CORRECT: Extract ALL enriched fields from event
context_builder=lambda event: {
    'broker_connection_id': event.get('aggregate_id') or event.get('broker_connection_id'),
    'user_id': event.get('user_id'),
    'broker_id': event.get('broker_id'),
    'reason': event.get('reason'),
    # CRITICAL: Extract enriched account IDs
    'linked_account_ids': event.get('linked_account_ids', []),
    'virtual_account_ids': event.get('virtual_account_ids', []),
    'active_automation_ids': event.get('active_automation_ids', []),
    # Metadata
    'correlation_id': event.get('correlation_id', event.get('event_id')),
    'causation_id': event.get('event_id')
}
```

### Step 7: Add Timeout Configuration

```python
# app/config/saga_config.py
class SagaConfig:
    def get_timeout_for_saga(self, saga_type: str, is_virtual: bool = False) -> timedelta:
        """Get timeout based on saga type and broker type"""
        base_timeouts = {
            "BrokerConnectionSaga": 120 if is_virtual else 300,
            "BrokerDisconnectionSaga": 180 if is_virtual else 300,
            "UserDeletionSaga": 600,  # 10 minutes
            "ConnectionRecoverySaga": 120,
        }

        timeout_seconds = base_timeouts.get(saga_type, self.default_timeout_seconds)
        return timedelta(seconds=timeout_seconds)

saga_config = SagaConfig()
```

### Step 8: Test Compensation Logic

```python
# tests/integration/test_saga_compensation.py
async def test_broker_disconnection_saga_compensation():
    """Test compensation rollback on failure"""

    # 1. Setup: Create connection and accounts
    connection_id = await setup_broker_connection(user_id, "alpaca")
    account_ids = await setup_broker_accounts(connection_id, count=3)

    # 2. Inject failure in step 3 (after accounts deleted)
    with patch_saga_step_failure("clear_adapter_resources"):
        # 3. Trigger disconnection
        await command_bus.send(DisconnectBrokerCommand(
            broker_connection_id=connection_id,
            user_id=user_id,
            reason="test_compensation"
        ))

        # 4. Wait for saga to fail and compensate
        await wait_for_saga_compensation(timeout=60)

    # 5. Verify compensation published manual intervention event
    events = await get_published_events("saga.compensation")
    assert len(events) == 1
    assert events[0]['event_type'] == "BrokerAccountDeletionCompensationRequired"
    assert events[0]['requires_manual_intervention'] is True
```

---

## Context Builder Critical Pattern

### The Bug We Fixed (BrokerDisconnectionSaga)

**Symptom:** Saga deleting 0 accounts despite handler enriching event with account IDs.

**Root Cause:** Context builder missing enriched fields.

**Timeline:**
1. Handler enriches `BrokerDisconnected` event with `linked_account_ids`, `virtual_account_ids`
2. Event published to Kafka with enriched data
3. **🐛 SagaService context_builder** missing these fields
4. Saga receives `context['linked_account_ids']` = `[]` (empty!)
5. Saga deletes 0 accounts

**Fix:**

```python
# BEFORE (BUG):
SagaTriggerConfig(
    event_types=["BrokerDisconnected"],
    saga_class=BrokerDisconnectionSaga,
    context_builder=lambda event: {
        'broker_connection_id': event.get('aggregate_id'),
        'user_id': event.get('user_id'),
        'broker_id': event.get('broker_id'),
        'reason': event.get('reason')
        # 🐛 MISSING: linked_account_ids, virtual_account_ids
    }
)

# AFTER (FIXED):
SagaTriggerConfig(
    event_types=["BrokerDisconnected"],
    saga_class=BrokerDisconnectionSaga,
    context_builder=lambda event: {
        'broker_connection_id': event.get('aggregate_id') or event.get('broker_connection_id'),
        'user_id': event.get('user_id'),
        'broker_id': event.get('broker_id'),
        'reason': event.get('reason'),
        # ✅ FIXED: Extract enriched account IDs from event
        'linked_account_ids': event.get('linked_account_ids', []),
        'virtual_account_ids': event.get('virtual_account_ids', []),
        'active_automation_ids': event.get('active_automation_ids', [])
    }
)
```

### Checklist: Context Builder Must Extract

- ✅ All aggregate IDs (user_id, broker_connection_id, account_id, etc.)
- ✅ All enriched lists (linked_account_ids, virtual_account_ids, etc.)
- ✅ Business data (reason, broker_id, environment, etc.)
- ✅ CQRS metadata (correlation_id, causation_id, original_event_type)
- ✅ Timing metadata (event_timestamp, event_version, aggregate_version)

### How to Verify Context Builder is Complete

**1. Check Handler Enrichment:**

```python
# Find handler that emits the event
grep -A 20 "BrokerDisconnected(" app/broker_connection/
```

**2. List Enriched Fields:**

```python
# app/broker_connection/events.py
class BrokerDisconnected(BaseEvent):
    event_type: Literal["BrokerDisconnected"] = "BrokerDisconnected"
    broker_connection_id: UUID
    user_id: UUID
    broker_id: str
    environment: str
    reason: str
    linked_account_ids: List[str] = []       # ENRICHED
    virtual_account_ids: List[str] = []      # ENRICHED
    active_automation_ids: List[str] = []    # ENRICHED
    disconnected_at: datetime
```

**3. Verify Context Builder Extracts ALL Fields:**

```python
# app/services/saga_service.py
context_builder=lambda event: {
    # Check: Does context_builder extract EVERY field from event?
    'broker_connection_id': event.get('aggregate_id'),  # ✅
    'user_id': event.get('user_id'),                    # ✅
    'broker_id': event.get('broker_id'),                # ✅
    'environment': event.get('environment'),            # ✅
    'reason': event.get('reason'),                      # ✅
    'linked_account_ids': event.get('linked_account_ids', []),      # ✅
    'virtual_account_ids': event.get('virtual_account_ids', []),    # ✅
    'active_automation_ids': event.get('active_automation_ids', []) # ✅
}
```

**4. Debug: Log Context in Saga:**

```python
async def _validate_disconnection(self, **context) -> Dict[str, Any]:
    log.info(f"Saga context keys: {list(context.keys())}")
    log.info(f"linked_account_ids: {context.get('linked_account_ids', [])}")
    log.info(f"virtual_account_ids: {context.get('virtual_account_ids', [])}")

    # If these are empty, context_builder is missing fields!
```

---

## Compensation Patterns

### Pattern 1: No-Op Compensation (Read-Only Steps)

```python
async def _verify_connection(self, **context) -> Dict[str, Any]:
    """Read-only verification step"""
    # Check connection health (no state changes)
    result = await command_bus.send(CheckBrokerConnectionHealthCommand(...))
    return {'connection_healthy': result.is_healthy}

async def _noop_compensate(self, **context) -> None:
    """No compensation needed for read-only step"""
    pass
```

### Pattern 2: Event-Based Compensation (Publish Manual Intervention)

```python
async def _delete_broker_accounts(self, **context) -> Dict[str, Any]:
    """Delete accounts"""
    for account_id in context['linked_account_ids']:
        await command_bus.send(DeleteBrokerAccountCommand(account_id=account_id))

    return {'accounts_deleted': len(context['linked_account_ids'])}

async def _compensate_account_deletion(self, **context) -> None:
    """Compensation: Publish manual intervention event"""
    event_bus: EventBus = context['event_bus']

    await event_bus.publish("saga.compensation", {
        "event_id": str(uuid.uuid4()),
        "event_type": "AccountDeletionCompensationRequired",
        "saga_id": str(self.saga_id),
        "broker_connection_id": str(context['broker_connection_id']),
        "account_ids": context['linked_account_ids'],
        "requires_manual_intervention": True,
        "reason": "Account deletion failed, partial completion"
    })
```

### Pattern 3: Command-Based Compensation (Actual Rollback)

```python
async def _disconnect_all_brokers(self, **context) -> Dict[str, Any]:
    """Disconnect brokers"""
    result = await command_bus.send(DisconnectAllBrokersCommand(
        user_id=context['user_id'],
        reason="user_deletion"
    ))

    return {
        'disconnected_brokers': result.get('disconnected_brokers', [])
    }

async def _compensate_broker_disconnection(self, **context) -> None:
    """Compensation: Reconnect brokers"""
    command_bus: CommandBus = context['command_bus']

    for broker_info in context.get('disconnected_brokers', []):
        try:
            await command_bus.send(ReconnectBrokerCommand(
                broker_connection_id=broker_info['connection_id'],
                user_id=context['user_id']
            ))
            log.info(f"Reconnected broker {broker_info['connection_id']}")
        except Exception as e:
            log.error(f"Failed to reconnect broker: {e}")
```

### Pattern 4: Idempotent Compensation (Safe Retry)

```python
async def _purge_connection(self, **context) -> Dict[str, Any]:
    """Final deletion step"""
    await command_bus.send(PurgeBrokerConnectionCommand(
        broker_connection_id=context['broker_connection_id'],
        force=True
    ))

    return {'purged': True}

async def _noop_compensate(self, **context) -> None:
    """No compensation - purge is final and idempotent"""
    # If purge fails, saga marked as failed
    # Manual intervention required (cannot undo deletion)
    pass
```

---

## Performance Optimization

### 1. Fast-Track Virtual Brokers

**BrokerConnectionSaga Optimization (Nov 2025):**

```python
# BEFORE: 15 attempts × 2s delay = 30s worst case
max_attempts = 15
wait_time = 2.0 * (attempt + 1)  # 2s, 4s, 6s... 30s

# AFTER: 5 attempts × 0.5s delay = ~5s worst case
max_attempts = 5  # SYNC projection = 2s timeout
wait_time = 0.5 * (attempt + 1)  # 0.5s, 1.0s, 1.5s, 2.0s, 2.5s
```

**Result:** 83% faster (30s → 5s) for virtual broker connection saga.

### 2. SYNC Projection Strategy

**Problem:** Saga waiting for async projection to complete (eventual consistency).

**Solution:** Mark critical projections as SYNC (immediate DB write in handler transaction).

```python
# app/broker_connection/sync_events.py
SYNC_EVENTS = {
    "BrokerConnectionEstablished",  # SYNC: Saga needs connection record immediately
    "BrokerAccountLinked"           # SYNC: Saga verifies account creation
}
```

**Result:** Saga can proceed immediately without polling read model.

### 3. Reduce Retry Delays

```python
# app/config/saga_config.py
class SagaConfig:
    default_retry_delay_seconds: float = 0.5  # Reduced from 2.0s
    virtual_broker_speed_factor: float = 0.5  # 2x faster for virtual brokers
```

### 4. Skip Redundant Steps

```python
async def _wait_for_projection_sync(self, **context) -> Dict[str, Any]:
    if not self._is_virtual_broker():
        return {'wait_skipped': True}  # Skip wait for real brokers

    # Only virtual brokers wait for orphan deletion
    await asyncio.sleep(0.5)
    return {'projection_sync_complete': True}
```

---

## Monitoring & Metrics

### 1. Saga Lifecycle Events

**Published by SagaManager:**

```python
# saga.events topic
{
    "event_type": "SagaStarted",
    "saga_id": "uuid",
    "saga_type": "BrokerConnectionSaga",
    "timeout_minutes": 5,
    "initial_context": {...}
}

{
    "event_type": "SagaCompleted",
    "saga_id": "uuid",
    "total_duration_ms": 1234,
    "steps_executed": 5,
    "step_timings": {
        "verify_connection": 0.5,
        "discover_accounts": 1.2
    }
}

{
    "event_type": "SagaCompensationStarted",
    "saga_id": "uuid",
    "reason": "Step discover_accounts failed",
    "failed_step": "discover_accounts",
    "steps_to_compensate": ["verify_connection"]
}
```

### 2. Prometheus Metrics

```python
# app/infra/metrics/saga_metrics.py
saga_execution_time = Histogram(
    'saga_execution_seconds',
    'Saga execution time',
    ['saga_type', 'status']
)

saga_step_execution_time = Histogram(
    'saga_step_execution_seconds',
    'Saga step execution time',
    ['saga_type', 'step_name', 'status']
)

saga_compensation_count = Counter(
    'saga_compensations_total',
    'Number of saga compensations',
    ['saga_type', 'step_name']
)
```

### 3. Distributed Locking Metrics

```python
# Track aggregate conflicts
saga_conflict_count = Counter(
    'saga_conflicts_total',
    'Number of saga conflicts detected',
    ['saga_type', 'conflict_key']
)

saga_pending_queue_size = Gauge(
    'saga_pending_queue_size',
    'Number of sagas in pending queue',
    ['conflict_key']
)
```

### 4. Query Saga Status

```bash
# Get saga status
curl http://localhost:5001/api/sagas/{saga_id}/status

{
    "saga_id": "uuid",
    "saga_type": "BrokerConnectionSaga",
    "status": "IN_PROGRESS",
    "progress": "3/5",
    "started_at": "2025-11-10T12:00:00Z",
    "current_step": "discover_accounts",
    "step_timings": {
        "verify_connection": 0.5,
        "discover_accounts": 1.2
    }
}
```

---

## Troubleshooting

### Issue 1: Saga Not Triggering

**Symptoms:**
- Event published to Kafka
- Saga never starts
- No "SagaStarted" event

**Diagnosis:**

```python
# 1. Check saga trigger configuration
curl http://localhost:5001/api/sagas/triggers

# 2. Check event consumer is running
curl http://localhost:5001/health/worker

# 3. Check Kafka consumer lag
docker exec redpanda rpk group describe saga-triggers-default

# 4. Check pre_trigger_check
# If configured, saga may be skipped by pre-trigger validation
```

**Common Causes:**
- Event type mismatch (check `event_types` in `SagaTriggerConfig`)
- Pre-trigger check returning `False` (check `pre_trigger_check` lambda)
- Event consumer not started (check `_setup_event_consumers()`)
- Kafka consumer lag (check Redpanda)

### Issue 2: Saga Deleting 0 Accounts

**Symptoms:**
- Saga executes successfully
- Saga reports `accounts_deleted: 0`
- Handler enriched event with account IDs

**Diagnosis:**

```python
# 1. Check event enrichment (handler)
# Search for event emission in handler
grep -A 20 "BrokerDisconnected(" app/broker_connection/

# 2. Check context_builder extracts fields
# app/services/saga_service.py
# Verify context_builder has ALL enriched fields

# 3. Add logging to saga
log.info(f"Context keys: {list(context.keys())}")
log.info(f"linked_account_ids: {context.get('linked_account_ids', [])}")

# 4. Check Kafka event payload
docker exec redpanda rpk topic consume transport.broker-connection-events --num 1
```

**Fix:** Update `context_builder` to extract missing fields (see [Context Builder Critical Pattern](#context-builder-critical-pattern)).

### Issue 3: Saga Timeout

**Symptoms:**
- Saga times out after 2 minutes
- Step stuck waiting for projection
- "SagaTimedOut" event published

**Diagnosis:**

```python
# 1. Check saga timeout configuration
saga_config.get_timeout_for_saga("BrokerConnectionSaga", is_virtual=False)

# 2. Check step timeout
# Step may be stuck waiting for async projection
# Check if projection is SYNC or ASYNC

# 3. Check retry delays
# Excessive retry delays can exceed saga timeout
```

**Fix:**

```python
# Option 1: Mark projection as SYNC (fastest)
SYNC_EVENTS = {"BrokerConnectionEstablished"}

# Option 2: Reduce retry delays
saga_config.default_retry_delay_seconds = 0.5

# Option 3: Increase saga timeout
def get_timeout_for_saga(self, saga_type: str, is_virtual: bool = False) -> timedelta:
    return timedelta(seconds=600)  # 10 minutes
```

### Issue 4: Compensation Not Running

**Symptoms:**
- Saga step fails
- Saga status = "FAILED"
- Compensation functions not called

**Diagnosis:**

```python
# 1. Check if compensation is defined
# Verify step has compensate function (not _noop_compensate)

# 2. Check SagaStatus
# Compensation only runs if saga transitions to COMPENSATING

# 3. Check compensation errors
curl http://localhost:5001/api/sagas/{saga_id}/status

# 4. Check saga.compensation events
curl http://localhost:5001/api/events?topic=saga.compensation
```

**Common Causes:**
- Compensation function raises exception (logged in saga state)
- Compensation skipped if status is TIMED_OUT (not FAILED)
- No-op compensation (`_noop_compensate`) doesn't do anything

### Issue 5: Race Condition (Concurrent Sagas)

**Symptoms:**
- Two sagas triggered for same aggregate
- Data corruption
- Foreign key violations

**Diagnosis:**

```python
# 1. Check conflict_key_builder
SagaTriggerConfig(
    conflict_key_builder=lambda event: f"broker_connection:{event['broker_connection_id']}",
    allow_concurrent=False  # Must be False!
)

# 2. Check distributed lock
# Saga should acquire lock before starting
curl http://localhost:5001/api/locks?key=saga:start:broker_connection:*

# 3. Check pending saga queue
curl http://localhost:5001/api/sagas/pending
```

**Fix:**

```python
# Ensure conflict_key_builder is set
SagaTriggerConfig(
    conflict_key_builder=lambda event: f"broker_connection:{event['broker_connection_id']}",
    allow_concurrent=False,
    auto_retry_on_conflict=True,  # Retry after lock released
    max_retry_attempts=5
)
```

---

## Exemplar Sagas (Production-Ready)

### 1. BrokerConnectionSaga
- **File:** `app/infra/saga/broker_connection_saga.py`
- **Triggers:** `BrokerConnectionEstablished`
- **Steps:** 5 (verify, discover, wait, publish)
- **Optimizations:** Fast-track virtual brokers (83% faster)
- **Lines:** 883

### 2. BrokerDisconnectionSaga
- **File:** `app/infra/saga/broker_disconnection_saga.py`
- **Triggers:** `BrokerDisconnected`
- **Steps:** 9 (validate, cache clear, delete accounts, cleanup VB, validate, clear adapter, final cache, purge, publish)
- **TRUE SAGA:** Uses enriched event data (NO queries for core logic)
- **Lines:** 1,336

### 3. UserDeletionSaga
- **File:** `app/infra/saga/user_deletion_saga.py`
- **Triggers:** `UserAccountDeleted`
- **Steps:** 6 (get resources, disconnect brokers, wait, cleanup VB, publish, complete)
- **TRUE SAGA:** Event-driven (NO queries)
- **Lines:** 523

### 4. ConnectionRecoverySaga
- **File:** `app/infra/saga/connection_recovery_saga.py`
- **Triggers:** `BrokerConnectionFailed`
- **Steps:** 5 (verify, health check, reconnect, verify recovery, publish)
- **Compensation:** Rollback reconnection on failure
- **Lines:** 481

---

## Quick Reference: True Saga Checklist

- [ ] **Handler enriches event** with ALL data saga needs
- [ ] **Context builder** extracts ALL enriched fields from event
- [ ] **Saga uses event data** (NO queries for core logic)
- [ ] **Saga sends commands** (NOT direct DB access)
- [ ] **Compensation defined** for state-changing steps
- [ ] **Timeout configured** (saga-specific or default)
- [ ] **Conflict key configured** if aggregate must be single-threaded
- [ ] **Event trigger registered** in `saga_service.py`
- [ ] **Saga registered** in `_register_sagas()`
- [ ] **Metrics added** (Prometheus + lifecycle events)
- [ ] **Tests written** (unit + integration + compensation)

---

## Further Reading

- **CQRS Architecture:** `docs/cqrs.md`
- **Event Sourcing:** `docs/redpanda_comprehensive_architecture_v06.md`
- **Domain Creation:** `docs/mvp/DOMAIN_CREATION_TEMPLATE.md`
- **Saga Config:** `app/config/saga_config.py`
- **Saga Manager:** `app/infra/saga/saga_manager.py`
- **Saga Service:** `app/services/saga_service.py`

---

**Document Version:** 1.0
**Last Updated:** November 10, 2025
**Status:** Production-Ready ✅
