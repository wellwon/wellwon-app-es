# Debugging Event Flow - TradeCore v0.5

**Last Updated**: 2025-11-10
**Purpose**: Guide to tracing events through TradeCore's CQRS/Event Sourcing architecture

---

## Table of Contents

1. [Event Flow Overview](#event-flow-overview)
2. [Debugging Tools](#debugging-tools)
3. [Tracing a Command](#tracing-a-command)
4. [Tracing an Event](#tracing-an-event)
5. [Debugging Sagas](#debugging-sagas)
6. [Using Redpanda Console](#using-redpanda-console)
7. [Log Patterns to Look For](#log-patterns-to-look-for)
8. [Common Investigation Scenarios](#common-investigation-scenarios)
9. [Performance Debugging](#performance-debugging)

---

## Event Flow Overview

### Complete CQRS Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. API REQUEST                                                  │
│    User clicks "Disconnect" → POST /broker-connections/{id}/disconnect
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. COMMAND HANDLER                                              │
│    • RequestBrokerDisconnectHandler receives command            │
│    • Validates request                                          │
│    • Queries account IDs (event enrichment - TRUE SAGA)         │
│    • Loads aggregate                                            │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. AGGREGATE                                                    │
│    • BrokerConnectionAggregate.request_disconnect()             │
│    • Validates business rules                                   │
│    • Creates BrokerDisconnected event                           │
│    • Applies event to state (status → DISCONNECTING)            │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. EVENT ENRICHMENT (TRUE SAGA)                                 │
│    • Handler enriches event with account IDs                    │
│    • event.linked_account_ids = [...]                           │
│    • event.virtual_account_ids = [...]                          │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. EVENT STORE                                                  │
│    • Event saved to event_outbox table                          │
│    • Status: 'pending'                                          │
│    • Outbox service publishes to Redpanda                       │
│    • Status: 'published'                                        │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. REDPANDA (Event Bus)                                         │
│    • Event published to topic: broker_connection.events         │
│    • Partitioned by aggregate_id                                │
│    • Multiple consumers subscribe                               │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
                    ┌────┴────┐
                    ↓         ↓
        ┌───────────────┐   ┌──────────────────┐
        │ 7a. PROJECTOR │   │ 7b. SAGA MANAGER │
        └───────────────┘   └──────────────────┘
                ↓                      ↓
    ┌─────────────────────┐  ┌─────────────────────────────┐
    │ Update read model   │  │ BrokerDisconnectionSaga     │
    │ (PostgreSQL)        │  │ • Validate event            │
    │                     │  │ • Delete accounts           │
    │ UPDATE broker_conn  │  │ • Delete VB accounts        │
    │ SET status =        │  │ • Delete automations        │
    │   'disconnected'    │  │ • Purge connection          │
    └─────────────────────┘  └─────────────────────────────┘
                                        ↓
                            ┌───────────────────────┐
                            │ 8. SAGA COMMANDS      │
                            │ • DeleteBrokerAccount │
                            │ • DeleteVirtualBroker │
                            │ • DeleteAutomation    │
                            │ (Each triggers own    │
                            │  aggregate + events)  │
                            └───────────────────────┘
```

---

## Debugging Tools

### 1. Application Logs

**Location**:
- Server logs: `docker logs tradecore-api-1`
- Worker logs: `docker logs tradecore-worker-1`
- Local logs: Console output (if running with `--reload`)

**Log Levels**:
```python
DEBUG    # Verbose (method calls, data dumps)
INFO     # Normal operations (events published, commands executed)
WARNING  # Recoverable issues (retries, circuit breaker)
ERROR    # Failures (validation errors, command failures)
```

**Useful Log Filters**:
```bash
# Filter by aggregate ID
docker logs tradecore-api-1 2>&1 | grep "conn_123"

# Filter by event type
docker logs tradecore-worker-1 2>&1 | grep "BrokerDisconnected"

# Filter by saga ID
docker logs tradecore-worker-1 2>&1 | grep "saga_abc123"

# Last 100 lines with live updates
docker logs -f --tail 100 tradecore-api-1
```

---

### 2. Redpanda Console

**Access**: http://localhost:8080

**Features**:
- Browse topics
- View events (messages)
- Search by partition key
- View consumer groups
- Monitor lag

**How to Use**:
1. Navigate to Topics
2. Select topic (e.g., `broker_connection.events`)
3. Click "Messages"
4. Filter by key (aggregate_id)
5. View event payload (JSON)

---

### 3. Database Queries

**Event Outbox** (Event Store):
```sql
-- View recent events for aggregate
SELECT event_id, event_type, status, published_at, created_at
FROM event_outbox
WHERE aggregate_id = 'your-aggregate-id'
ORDER BY created_at DESC
LIMIT 10;

-- View unpublished events (stuck events)
SELECT aggregate_id, event_type, status, created_at
FROM event_outbox
WHERE status = 'pending'
  AND created_at < NOW() - INTERVAL '5 minutes'
ORDER BY created_at ASC;

-- View events by type
SELECT aggregate_id, event_type, created_at
FROM event_outbox
WHERE event_type = 'BrokerDisconnected'
ORDER BY created_at DESC
LIMIT 20;

-- Full event history for aggregate
SELECT event_id, event_type, aggregate_version, status, published_at
FROM event_outbox
WHERE aggregate_id = 'your-aggregate-id'
ORDER BY aggregate_version ASC;
```

**Read Model**:
```sql
-- Check broker connection status
SELECT id, broker_id, environment, status, connected, deleted
FROM broker_connections
WHERE id = 'your-connection-id';

-- Check accounts for connection
SELECT id, broker_account_id, status, deleted
FROM broker_accounts
WHERE broker_connection_id = 'your-connection-id';

-- Check virtual accounts
SELECT id, broker_account_id, status, deleted
FROM virtual_accounts
WHERE broker_connection_id = 'your-connection-id';

-- Check aggregate version (for replay debugging)
SELECT id, aggregate_version
FROM broker_connections
WHERE id = 'your-connection-id';
```

---

### 4. Python Debugger (pdb)

**Add breakpoint in code**:
```python
import pdb; pdb.set_trace()
```

**Useful in**:
- Command handlers (trace command execution)
- Event handlers (trace event application)
- Saga steps (trace saga orchestration)

**Commands**:
- `n` - Next line
- `s` - Step into function
- `c` - Continue execution
- `p variable_name` - Print variable
- `l` - List code around current line
- `q` - Quit debugger

---

## Tracing a Command

### Step-by-Step Investigation

**Scenario**: User clicked "Disconnect" but connection not disconnected.

#### Step 1: Verify API Request Received

**Check server logs**:
```bash
docker logs tradecore-api-1 2>&1 | grep "POST /broker-connections"
```

**Expected**:
```
INFO: POST /broker-connections/{id}/disconnect - 200 OK
```

**If NOT found**: API request not received (check frontend, network)

---

#### Step 2: Verify Command Handler Executed

**Search for command handler logs**:
```bash
docker logs tradecore-api-1 2>&1 | grep "RequestBrokerDisconnectHandler"
```

**Expected**:
```
INFO: RequestBrokerDisconnectHandler: Processing disconnect for connection conn_123
INFO: RequestBrokerDisconnectHandler: Enriched with 2 broker account IDs
INFO: RequestBrokerDisconnectHandler: Enriched with 2 virtual account IDs
```

**If NOT found**:
- Command not routed to handler
- Check `command_bus.py` registration
- Check command class name matches handler

---

#### Step 3: Verify Event Created

**Check event outbox**:
```sql
SELECT event_id, event_type, status, created_at
FROM event_outbox
WHERE aggregate_id = 'conn_123'
  AND event_type = 'BrokerDisconnected'
ORDER BY created_at DESC
LIMIT 1;
```

**Expected**:
```
event_type: BrokerDisconnected
status: published
created_at: 2025-11-10 14:30:00
```

**If NOT found**:
- Aggregate didn't emit event (check aggregate method)
- Event not saved (check event store service)

**If status = 'pending'**:
- Event stuck in outbox (check outbox service logs)
- Redpanda unreachable (check docker-compose)

---

#### Step 4: Verify Event Published to Redpanda

**Check Redpanda Console**: http://localhost:8080
1. Topics → `broker_connection.events`
2. Messages
3. Filter by key: `conn_123`

**Expected**: Message with `BrokerDisconnected` event

**If NOT found**:
- Outbox service not running
- Redpanda connectivity issue
- Check worker logs for errors

---

## Tracing an Event

### Step-by-Step Investigation

**Scenario**: Event published but projection not updated.

#### Step 1: Verify Event in Redpanda

**Redpanda Console**: http://localhost:8080
- Topics → `broker_connection.events`
- Messages → Filter by aggregate_id

**Expected**: Event with correct payload

---

#### Step 2: Verify Consumer Subscribed

**Check worker logs**:
```bash
docker logs tradecore-worker-1 2>&1 | grep "Subscribed to topic"
```

**Expected**:
```
INFO: Subscribed to topic: broker_connection.events (consumer group: broker_connection_projectors)
```

**If NOT found**:
- Worker not running
- Consumer not configured
- Check `worker_consumer_groups.py`

---

#### Step 3: Verify Event Consumed

**Search worker logs for event**:
```bash
docker logs tradecore-worker-1 2>&1 | grep "BrokerDisconnected"
```

**Expected**:
```
INFO: Processing event: BrokerDisconnected (aggregate_id: conn_123)
```

**If NOT found**:
- Consumer lag (check Redpanda Console)
- Event filtered out (check consumer filter)
- Worker crashed (check logs for exceptions)

---

#### Step 4: Verify Projector Executed

**Search for projector logs**:
```bash
docker logs tradecore-worker-1 2>&1 | grep "project_broker_disconnected"
```

**Expected**:
```
INFO: Projector: project_broker_disconnected for aggregate conn_123
DEBUG: Executing SQL: UPDATE broker_connections SET status = 'disconnected' WHERE id = $1
```

**If NOT found**:
- Projector not registered (check `domain_registry.py`)
- Projector function name mismatch
- Event type doesn't match

---

#### Step 5: Verify Database Updated

**Query read model**:
```sql
SELECT id, status, updated_at
FROM broker_connections
WHERE id = 'conn_123';
```

**Expected**:
```
status: disconnected
updated_at: 2025-11-10 14:30:05
```

**If NOT updated**:
- Projector SQL failed (check logs for exceptions)
- Database constraint violation
- Transaction rolled back

---

## Debugging Sagas

### Saga Investigation Pattern

**Scenario**: BrokerDisconnectionSaga not deleting accounts.

#### Step 1: Verify Saga Triggered

**Search worker logs**:
```bash
docker logs tradecore-worker-1 2>&1 | grep "BrokerDisconnectionSaga"
```

**Expected**:
```
INFO: BrokerDisconnectionSaga started for connection conn_123 (saga_id: saga_abc123)
```

**If NOT found**:
- Saga not registered for event
- Check `saga_manager.py` event mapping
- Event type mismatch

---

#### Step 2: Verify Saga Validation Passed

**Search for validation logs**:
```bash
docker logs tradecore-worker-1 2>&1 | grep "TRUE SAGA validation"
```

**Expected**:
```
INFO: Saga saga_abc123: TRUE SAGA validation - broker=alpaca, user=user_456, linked_accounts=2, virtual_accounts=2
```

**Key Data**:
- `linked_accounts=2` - Should match actual account count
- `virtual_accounts=2` - Should match VB account count

**If counts = 0**:
- ❌ Event not enriched with account IDs
- Check command handler event enrichment
- See `DISCONNECT_SAGA_FIX_2025.md`

---

#### Step 3: Verify Saga Steps Executed

**Search for step logs**:
```bash
docker logs tradecore-worker-1 2>&1 | grep "saga_abc123"
```

**Expected sequence**:
```
INFO: Saga saga_abc123: Step 1/7 - _validate_disconnection - STARTED
INFO: Saga saga_abc123: Step 1/7 - _validate_disconnection - COMPLETED
INFO: Saga saga_abc123: Step 2/7 - _delete_broker_accounts - STARTED
INFO: Saga saga_abc123: TRUE SAGA - Deleting 2 broker accounts from event
INFO: Saga saga_abc123: Successfully deleted 2 broker accounts
INFO: Saga saga_abc123: Step 2/7 - _delete_broker_accounts - COMPLETED
INFO: Saga saga_abc123: Step 3/7 - _cleanup_virtual_broker_data - STARTED
INFO: Saga saga_abc123: TRUE SAGA - VB cleanup for 2 accounts from event
INFO: Saga saga_abc123: Successfully deleted 2 VB accounts
INFO: Saga saga_abc123: Step 3/7 - _cleanup_virtual_broker_data - COMPLETED
INFO: Saga saga_abc123: Step 7/7 - _purge_connection - STARTED
INFO: Saga saga_abc123: Connection purged successfully
INFO: Saga saga_abc123: Step 7/7 - _purge_connection - COMPLETED
INFO: Saga saga_abc123: COMPLETED SUCCESSFULLY
```

**If step FAILED**:
```
ERROR: Saga saga_abc123: Step 2/7 - _delete_broker_accounts - FAILED: ValidationError
ERROR: Saga saga_abc123: FAILED - Attempting compensation
```

- Check error message
- Check saga compensation logic
- Verify saga can rollback

---

#### Step 4: Verify Saga Commands Sent

**Search for command logs**:
```bash
docker logs tradecore-worker-1 2>&1 | grep "DeleteBrokerAccountCommand"
```

**Expected**:
```
INFO: CommandBus: Sending DeleteBrokerAccountCommand (account_id: acc_123)
INFO: CommandBus: Sending DeleteBrokerAccountCommand (account_id: acc_456)
```

**If NOT found**:
- Saga step didn't send commands
- Command bus not injected
- Check saga step implementation

---

#### Step 5: Verify Final State

**Query database**:
```sql
-- Should return 0 rows (all deleted)
SELECT id FROM broker_accounts
WHERE broker_connection_id = 'conn_123'
  AND deleted = FALSE;

-- Should return 0 rows (all deleted)
SELECT id FROM virtual_accounts
WHERE broker_connection_id = 'conn_123'
  AND deleted = FALSE;

-- Should return 0 rows (connection deleted)
SELECT id FROM broker_connections
WHERE id = 'conn_123';
```

**If accounts still exist**:
- Delete commands failed (check command handler logs)
- Saga validation aborted purge (check logs for "ABORTING PURGE")
- Saga compensated (rolled back)

---

## Using Redpanda Console

### Access

**URL**: http://localhost:8080

### Browse Topics

1. Click "Topics" in left sidebar
2. View all topics:
   - `broker_connection.events`
   - `broker_account.events`
   - `automation.events`
   - `position.events`
   - `order.events`

### View Messages

1. Click on topic name
2. Click "Messages" tab
3. Click "Fetch messages"
4. Filter by:
   - **Key** (aggregate_id): `conn_123`
   - **Offset**: Start from beginning or specific offset
   - **Partition**: All or specific partition

### Search Event Payload

1. View message
2. Click "Value" tab
3. JSON payload displayed:
```json
{
  "event_type": "BrokerDisconnected",
  "broker_connection_id": "conn_123",
  "user_id": "user_456",
  "broker_id": "alpaca",
  "environment": "paper",
  "linked_account_ids": ["acc_123", "acc_456"],
  "virtual_account_ids": ["vb_789", "vb_012"],
  "timestamp": "2025-11-10T14:30:00Z"
}
```

### Monitor Consumer Groups

1. Click "Consumer Groups"
2. View consumer group status:
   - `broker_connection_projectors`
   - `broker_account_projectors`
   - `saga_orchestrators`
3. Check **Lag** (should be 0 or very low)

**High lag** (> 100 messages):
- Consumer slow or stuck
- Worker overloaded
- Check worker logs for errors

---

## Log Patterns to Look For

### Success Patterns

**Command Execution**:
```
INFO: CommandBus: Sending CreateAutomationCommand
INFO: CreateAutomationHandler: Processing command for user user_123
INFO: CreateAutomationHandler: Automation created with ID auto_456
```

**Event Publishing**:
```
INFO: EventStore: Saving event AutomationCreatedEvent (aggregate_id: auto_456)
INFO: OutboxService: Publishing event event_789 to Redpanda
INFO: OutboxService: Event event_789 published successfully
```

**Projection**:
```
INFO: EventProcessor: Processing event AutomationCreatedEvent (aggregate_id: auto_456)
INFO: Projector: project_automation_created for aggregate auto_456
DEBUG: SQL: INSERT INTO automations (id, user_id, name, symbol) VALUES ($1, $2, $3, $4)
```

**Saga**:
```
INFO: SagaManager: Starting BrokerDisconnectionSaga for event BrokerDisconnected
INFO: Saga saga_abc123: Step 1/7 - COMPLETED
INFO: Saga saga_abc123: Step 2/7 - COMPLETED
...
INFO: Saga saga_abc123: COMPLETED SUCCESSFULLY
```

---

### Error Patterns

**Command Validation Failed**:
```
ERROR: CreateAutomationHandler: Validation failed: Broker account not found
WARNING: CommandBus: Command failed with validation error
```

**Event Publishing Failed**:
```
ERROR: OutboxService: Failed to publish event event_789: ConnectionRefused
ERROR: OutboxService: Redpanda unreachable, will retry
```

**Projection Failed**:
```
ERROR: Projector: project_automation_created failed: UniqueViolationError
ERROR: EventProcessor: Failed to process event AutomationCreatedEvent, will retry
```

**Saga Failed**:
```
ERROR: Saga saga_abc123: Step 2/7 - FAILED: ValidationError
ERROR: Saga saga_abc123: FAILED - Attempting compensation
INFO: Saga saga_abc123: Compensation step 1/2 - COMPLETED
INFO: Saga saga_abc123: COMPENSATED (rolled back)
```

---

### Investigation Patterns

**Slow Operations** (> 1s):
```
WARNING: CommandHandler took 3.5s to execute (threshold: 1.0s)
WARNING: High event latency detected: 2500ms for BrokerDisconnected
```

**Retry Attempts**:
```
INFO: CircuitBreaker: Retry attempt 1/3 for query GetBrokerAccountQuery
INFO: CircuitBreaker: Retry attempt 2/3 for query GetBrokerAccountQuery
WARNING: CircuitBreaker: All retries exhausted, opening circuit
```

**Race Conditions**:
```
WARNING: Saga saga_abc123: Connection reconnected during saga, aborting purge
INFO: Saga saga_abc123: ABORTED (safe to retry)
```

---

## Common Investigation Scenarios

### Scenario 1: Disconnect Not Working

**Steps**:
1. ✅ Check API logs for POST request
2. ✅ Check command handler enriched event with account IDs
3. ✅ Check event in `event_outbox` (status = 'published')
4. ✅ Check Redpanda Console for event
5. ✅ Check worker logs for saga trigger
6. ✅ Check saga validation (linked_accounts > 0)
7. ✅ Check saga steps completed
8. ✅ Check database accounts deleted

**See**: `DISCONNECT_SAGA_FIX_2025.md` for full fix documentation

---

### Scenario 2: Projection Not Updating

**Steps**:
1. ✅ Verify event published to Redpanda
2. ✅ Verify consumer subscribed to topic
3. ✅ Verify event consumed (worker logs)
4. ✅ Verify projector registered in domain_registry.py
5. ✅ Verify projector function name matches event type
6. ✅ Check projector logs for SQL errors
7. ✅ Query database manually to verify schema

---

### Scenario 3: Event Not Published

**Steps**:
1. ✅ Check event in `event_outbox` (status = 'pending' or 'failed')
2. ✅ Check outbox service logs for errors
3. ✅ Verify Redpanda running: `docker ps | grep redpanda`
4. ✅ Check Redpanda health: http://localhost:8080
5. ✅ Restart outbox service if needed
6. ✅ Check network connectivity

---

### Scenario 4: Saga Not Triggered

**Steps**:
1. ✅ Verify event published to Redpanda
2. ✅ Check saga_manager.py event mapping
3. ✅ Verify event type matches registration
4. ✅ Check worker logs for saga initialization
5. ✅ Verify saga consumer group subscribed
6. ✅ Check Redpanda Console consumer group lag

---

## Performance Debugging

### Identify Slow Operations

**Search logs for timing**:
```bash
docker logs tradecore-api-1 2>&1 | grep "took.*s"
```

**Expected output**:
```
WARNING: CommandHandler took 3.5s to execute (threshold: 1.0s)
WARNING: Query GetBrokerAccountQuery took 2.1s (threshold: 0.5s)
```

---

### Trace Event Latency

**Search for latency warnings**:
```bash
docker logs tradecore-worker-1 2>&1 | grep "latency"
```

**Expected**:
```
WARNING: High event latency detected: 2500ms for BrokerDisconnected
```

**Causes**:
- Worker lag (check consumer group lag)
- Redpanda slow (check Redpanda Console)
- Projector slow (check SQL query performance)

---

### Database Query Performance

**Enable query logging** in PostgreSQL:
```sql
-- Show slow queries
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

**Identify missing indexes**:
```sql
SELECT schemaname, tablename, attname, n_distinct
FROM pg_stats
WHERE schemaname = 'public'
  AND n_distinct > 0
  AND tablename IN ('broker_connections', 'broker_accounts', 'automations')
ORDER BY n_distinct DESC;
```

---

## Tools Summary

| Tool | Use Case | Access |
|------|----------|--------|
| **Application Logs** | Trace code execution | `docker logs tradecore-api-1` |
| **Redpanda Console** | Browse events, monitor lag | http://localhost:8080 |
| **PostgreSQL** | Query read models, event outbox | `psql` or database client |
| **Python Debugger (pdb)** | Step through code | Add breakpoint in code |
| **curl/httpx** | Test API endpoints | Command line |
| **pytest** | Test event flow | `pytest tests/integration/` |

---

## Summary Checklist

When debugging event flow issues:

- [ ] Check API logs for request received
- [ ] Check command handler logs for execution
- [ ] Verify event in `event_outbox` (status = 'published')
- [ ] Verify event in Redpanda Console
- [ ] Check worker logs for event consumed
- [ ] Verify projector registered and executed
- [ ] Verify saga triggered (if applicable)
- [ ] Check saga step logs for failures
- [ ] Query database for final state
- [ ] Check for error patterns in logs
- [ ] Monitor consumer group lag
- [ ] Verify event data completeness (TRUE SAGA)

---

**Related Documentation**:
- `/Users/silvermpx/PycharmProjects/TradeCore/DISCONNECT_SAGA_FIX_2025.md` - Saga debugging example
- `/Users/silvermpx/PycharmProjects/TradeCore/BROKER_DISCONNECTION_SAGA_REFACTOR_SUMMARY.md` - TRUE SAGA pattern
- `/Users/silvermpx/PycharmProjects/TradeCore/docs/reference/COMMON_PITFALLS.md` - Common bugs
