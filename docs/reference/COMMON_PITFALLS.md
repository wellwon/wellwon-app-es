# Common Pitfalls and How to Avoid Them - TradeCore v0.5

**Last Updated**: 2025-11-10
**Purpose**: Document actual bugs we've fixed, their root causes, and how to prevent them

---

## Table of Contents

1. [Critical Code Quality Issues](#critical-code-quality-issues)
2. [Saga Architecture Issues](#saga-architecture-issues)
3. [Event Sourcing Issues](#event-sourcing-issues)
4. [Database and Query Issues](#database-and-query-issues)
5. [WebSocket and Streaming Issues](#websocket-and-streaming-issues)
6. [Testing and Debugging Issues](#testing-and-debugging-issues)

---

## Critical Code Quality Issues

### 1. ❌ Using `datetime.utcnow()` (DEPRECATED)

**Problem**: Python 3.12+ deprecated `datetime.utcnow()` in favor of timezone-aware datetimes.

**Symptom**:
```python
DeprecationWarning: datetime.utcnow() is deprecated and will be removed in a future version.
Use datetime.now(UTC) instead.
```

**Root Cause**:
```python
# ❌ WRONG - Deprecated!
from datetime import datetime
opened_at: datetime = Field(default_factory=datetime.utcnow)
```

**Fix**:
```python
# ✅ CORRECT - Timezone-aware
from datetime import datetime, UTC
opened_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**Prevention**:
- ✅ Always import `UTC` from datetime
- ✅ Always use `datetime.now(UTC)` instead of `datetime.utcnow()`
- ✅ Use `lambda:` wrapper in Pydantic `Field(default_factory=...)`
- ✅ Add linter rule to catch `datetime.utcnow()`

**Files to Check**:
- All Pydantic models with datetime fields
- All event classes
- All aggregate state classes

**Search Command**:
```bash
grep -r "datetime.utcnow" app/
```

---

### 2. ❌ Using PascalCase for Method Names (PEP 8 Violation)

**Problem**: Python convention (PEP 8) requires `snake_case` for method names, NOT `PascalCase`.

**Symptom**:
```python
AttributeError: 'Position' object has no attribute '_on_PositionOpenedEvent'
```

**Root Cause**:
```python
# ❌ WRONG - PascalCase method name
def _on_PositionOpenedEvent(self, event: PositionOpenedEvent):
    self.state.status = PositionStatus.OPEN
```

**Why This Breaks**:
Aggregates use dynamic method name resolution with `snake_case` conversion:

```python
def _apply(self, event: BaseEvent) -> None:
    """Route event to handler (convert CamelCase → snake_case)"""
    event_class_name = event.__class__.__name__  # "PositionOpenedEvent"
    # Convert to snake_case: "position_opened_event"
    snake_case_name = ''.join(['_' + c.lower() if c.isupper() else c for c in event_class_name]).lstrip('_')
    handler_name = f"_on_{snake_case_name}"  # "_on_position_opened_event"
    handler = getattr(self, handler_name, None)  # ❌ Fails if method is PascalCase!
    if handler:
        handler(event)
```

**Fix**:
```python
# ✅ CORRECT - snake_case method name
def _on_position_opened_event(self, event: PositionOpenedEvent):
    self.state.status = PositionStatus.OPEN
```

**Prevention**:
- ✅ Always use `snake_case` for ALL method names
- ✅ Event handlers MUST be: `_on_{event_name_in_snake_case}`
- ✅ Add linter rule to enforce naming convention
- ✅ Test aggregate event replay to catch mismatches

**Search Command**:
```bash
grep -r "def _on_[A-Z]" app/  # Find PascalCase event handlers
```

---

### 3. ❌ Using `@dataclass` for Events (Wrong!)

**Problem**: Events MUST inherit from `BaseEvent` (Pydantic), NOT use `@dataclass`.

**Symptom**:
```python
TypeError: Event serialization failed
ValidationError: field required
```

**Root Cause**:
```python
# ❌ WRONG - @dataclass for events
@dataclass
class PositionOpenedEvent:
    position_id: UUID
    symbol: str
    # Missing event_type field!
    # Missing Pydantic validation!
```

**Fix**:
```python
# ✅ CORRECT - Inherit from BaseEvent
from app.common.base.base_event import BaseEvent
from typing import Literal

class PositionOpenedEvent(BaseEvent):
    """Position opened"""
    event_type: Literal["PositionOpenedEvent"] = "PositionOpenedEvent"  # Required!
    position_id: UUID
    symbol: str
    quantity: Decimal
    entry_price: Decimal
```

**Why BaseEvent is Required**:
- ✅ Pydantic validation (automatic type checking)
- ✅ JSON serialization (for Redpanda)
- ✅ Event registry integration
- ✅ Metadata fields (timestamp, aggregate_id, version)
- ✅ Replay support (event sourcing)

**Prevention**:
- ✅ ALL events inherit from `BaseEvent`
- ✅ ALL events have `event_type: Literal["EventName"] = "EventName"`
- ✅ Use `@dataclass(frozen=True)` for Value Objects only
- ✅ Never use `@dataclass` for events

**Search Command**:
```bash
grep -r "@dataclass" app/*/events.py  # Find potential violations
```

---

### 4. ❌ Missing `event_type` Field in Events

**Problem**: Events without explicit `event_type` field fail serialization and routing.

**Symptom**:
```python
KeyError: 'event_type'
EventRoutingError: Cannot determine event type
```

**Root Cause**:
```python
# ❌ WRONG - Missing event_type
class PositionOpenedEvent(BaseEvent):
    position_id: UUID
    symbol: str
    # Missing event_type!
```

**Fix**:
```python
# ✅ CORRECT - Explicit event_type with Literal type hint
from typing import Literal

class PositionOpenedEvent(BaseEvent):
    event_type: Literal["PositionOpenedEvent"] = "PositionOpenedEvent"
    position_id: UUID
    symbol: str
```

**Why This is Critical**:
- Event bus uses `event_type` to route events to correct handlers
- Event store uses `event_type` for indexing and querying
- Projectors filter events by `event_type`
- WSE transforms events based on `event_type`

**Prevention**:
- ✅ ALL events MUST have `event_type: Literal["EventName"] = "EventName"`
- ✅ Use Literal type hint (enforces string literal)
- ✅ Event name MUST match class name
- ✅ Add unit test to verify event_type exists

**Test Pattern**:
```python
def test_event_has_event_type():
    """Verify all events have event_type field"""
    event = PositionOpenedEvent(
        position_id=uuid4(),
        symbol="AAPL",
        # ...
    )
    assert hasattr(event, 'event_type')
    assert event.event_type == "PositionOpenedEvent"
```

---

## Saga Architecture Issues

### 5. ❌ Queries in Sagas (Process Manager Anti-Pattern)

**Problem**: Sagas querying read models for core logic violates TRUE SAGA pattern.

**Symptom**:
- Saga fails if projections lag (eventual consistency issues)
- Saga depends on read model state (tight coupling)
- Poor performance (multiple queries per saga execution)

**Root Cause**:
```python
# ❌ WRONG - Process Manager pattern (queries in saga)
async def _delete_broker_accounts(self, context: dict):
    # Query to get account IDs
    query = GetAccountsByConnectionQuery(
        broker_connection_id=context['broker_connection_id']
    )
    accounts = await self.query_bus.query(query)

    # Delete accounts
    for account in accounts:
        await self.command_bus.send(DeleteBrokerAccountCommand(
            account_aggregate_id=account.id
        ))
```

**Fix** (TRUE SAGA Pattern):
```python
# ✅ CORRECT - TRUE SAGA pattern (data from event)
async def _delete_broker_accounts(self, context: dict):
    # TRUE SAGA: Data from enriched event (NO queries!)
    linked_account_ids = context.get('linked_account_ids', [])

    # Delete accounts using IDs from event
    for account_id in linked_account_ids:
        await self.command_bus.send(DeleteBrokerAccountCommand(
            account_aggregate_id=account_id
        ))
```

**Event Enrichment** (Command Handler):
```python
# Enrich event with account IDs BEFORE publishing
async def handle_disconnect_command(command: RequestBrokerDisconnectCommand):
    # Query account IDs to enrich event
    accounts = await query_bus.query(GetAccountsByConnectionQuery(
        broker_connection_id=command.broker_connection_id
    ))
    linked_account_ids = [str(acc.id) for acc in accounts]

    # Create event via aggregate
    aggregate.request_disconnect(command.user_id, command.reason)

    # Enrich event with queried data
    disconnect_event = aggregate.get_uncommitted_events()[-1]
    disconnect_event.linked_account_ids = [UUID(aid) for aid in linked_account_ids]

    # Save and publish enriched event
    await aggregate_repository.save(aggregate)
```

**Why This Matters**:
- ✅ Saga independent of read model consistency
- ✅ Saga works even if projections lag
- ✅ Event contains definitive source of truth
- ✅ 92% performance improvement (fewer queries)

**Prevention**:
- ✅ Enrich events with ALL data saga needs (in command handler)
- ✅ Use queries in sagas ONLY for safety validations (not core logic)
- ✅ Mark queries as "SAFETY VALIDATION" in comments
- ✅ Event should be complete (no missing data)

**See Full Documentation**:
- `/Users/silvermpx/PycharmProjects/TradeCore/BROKER_DISCONNECTION_SAGA_REFACTOR_SUMMARY.md`
- `/Users/silvermpx/PycharmProjects/TradeCore/DISCONNECT_SAGA_FIX_2025.md`

---

### 6. ❌ Missing Context Data in Saga

**Problem**: Saga context missing required fields causes AttributeError.

**Symptom**:
```python
KeyError: 'user_id'
AttributeError: 'NoneType' object has no attribute 'broker_id'
```

**Root Cause**:
```python
# ❌ WRONG - Context builder missing fields
def build_context(event: BrokerDisconnected) -> dict:
    return {
        'broker_connection_id': event.broker_connection_id,
        # Missing user_id!
        # Missing broker_id!
        # Missing environment!
    }
```

**Fix**:
```python
# ✅ CORRECT - Complete context with all required fields
def build_context(event: BrokerDisconnected) -> dict:
    return {
        'broker_connection_id': event.broker_connection_id,
        'user_id': event.user_id,
        'broker_id': event.broker_id,
        'environment': event.environment,
        'reason': event.reason,
        'linked_account_ids': event.linked_account_ids,
        'virtual_account_ids': event.virtual_account_ids,
        'active_automation_ids': event.active_automation_ids
    }
```

**Prevention**:
- ✅ Context builder extracts ALL fields from event
- ✅ Verify event has all required fields BEFORE saga starts
- ✅ Use type hints for context dict
- ✅ Add unit test to verify context structure

**Test Pattern**:
```python
def test_saga_context_has_all_fields():
    """Verify saga context contains all required fields"""
    event = BrokerDisconnected(...)
    context = build_disconnection_context(event)

    required_fields = [
        'broker_connection_id',
        'user_id',
        'broker_id',
        'environment',
        'linked_account_ids'
    ]

    for field in required_fields:
        assert field in context, f"Missing field: {field}"
```

---

## Event Sourcing Issues

### 7. ❌ Business Logic in Services (Not in Aggregates)

**Problem**: Business logic in services violates Domain-Driven Design.

**Symptom**:
- Logic duplicated across services
- Hard to test (requires mocking services)
- Events don't capture full business context

**Root Cause**:
```python
# ❌ WRONG - Business logic in service
class PositionService:
    async def close_position(self, position_id: UUID, exit_price: Decimal):
        # Business logic in service!
        position = await self.repo.load(position_id)
        pnl = (exit_price - position.entry_price) * position.quantity
        commission = exit_price * position.quantity * Decimal("0.001")
        total_pnl = pnl - commission

        # Manually update state
        position.status = PositionStatus.CLOSED
        position.exit_price = exit_price
        position.realized_pnl = total_pnl

        await self.repo.save(position)
```

**Fix**:
```python
# ✅ CORRECT - Business logic in aggregate
class Position(Aggregate):
    def close_position(self, order_id: UUID, exit_price: Decimal, commission: Decimal):
        """Close position and realize P&L"""
        # Business logic in aggregate!
        if self.state.status == PositionStatus.CLOSED:
            raise PositionAlreadyClosedError()

        realized_pnl = self._calculate_realized_pnl(exit_price, commission)

        # Emit event (event sourcing)
        event = PositionClosedEvent(
            position_id=self.id,
            order_id=order_id,
            exit_price=exit_price,
            commission=commission,
            realized_pnl=realized_pnl,
            closed_at=datetime.now(UTC)
        )
        self.apply(event)

    def _on_position_closed_event(self, event: PositionClosedEvent):
        """Update state from event (replay-safe)"""
        self.state.status = PositionStatus.CLOSED
        self.state.exit_price = event.exit_price
        self.state.realized_pnl = event.realized_pnl
        self.state.closed_at = event.closed_at
```

**Why This Matters**:
- ✅ Business rules enforced consistently (aggregate validates)
- ✅ Event contains full context (replay produces same result)
- ✅ Easy to test (no service dependencies)
- ✅ Audit trail (events show business decisions)

**Prevention**:
- ✅ ALL business logic in aggregates (NOT services)
- ✅ Services orchestrate ONLY (call aggregate methods)
- ✅ Events contain ALL data needed for replay
- ✅ Test replay equivalence (command → events → state)

---

### 8. ❌ Aggregate State Not Updated by Events

**Problem**: Manually updating state instead of applying events breaks event sourcing.

**Symptom**:
- Replay produces different state than original
- Events don't contain full data
- State changes not audited

**Root Cause**:
```python
# ❌ WRONG - Directly mutating state
def close_position(self, exit_price: Decimal):
    # Direct mutation (NOT event sourcing!)
    self.state.status = PositionStatus.CLOSED
    self.state.exit_price = exit_price
    # No event emitted!
```

**Fix**:
```python
# ✅ CORRECT - Emit event, then apply
def close_position(self, order_id: UUID, exit_price: Decimal, commission: Decimal):
    # Emit event
    event = PositionClosedEvent(
        position_id=self.id,
        order_id=order_id,
        exit_price=exit_price,
        commission=commission,
        closed_at=datetime.now(UTC)
    )
    self.apply(event)  # This updates state via _on_position_closed_event

def _on_position_closed_event(self, event: PositionClosedEvent):
    """Apply event to state (replay-safe)"""
    self.state.status = PositionStatus.CLOSED
    self.state.exit_price = event.exit_price
```

**Pattern**:
1. Business method emits event
2. `apply(event)` calls `_on_{event_name_in_snake_case}`
3. Event handler updates state
4. State changes ONLY via event handlers

**Prevention**:
- ✅ NEVER mutate `self.state` directly in business methods
- ✅ ALWAYS emit event, then apply
- ✅ Test replay equivalence (catches violations)

---

## Database and Query Issues

### 9. ❌ SQL Aggregate Functions Without GROUP BY

**Problem**: Using COUNT, SUM, AVG without GROUP BY or proper context causes errors.

**Symptom**:
```python
asyncpg.PostgresSyntaxError: column "id" must appear in the GROUP BY clause
```

**Root Cause**:
```python
# ❌ WRONG - Aggregate function with non-grouped columns
SELECT id, symbol, COUNT(*) as total
FROM positions
WHERE user_id = $1
-- Missing GROUP BY!
```

**Fix Option 1** (Add GROUP BY):
```python
# ✅ CORRECT - Proper GROUP BY
SELECT symbol, COUNT(*) as total
FROM positions
WHERE user_id = $1
GROUP BY symbol
```

**Fix Option 2** (Remove non-aggregated columns):
```python
# ✅ CORRECT - Only aggregated result
SELECT COUNT(*) as total
FROM positions
WHERE user_id = $1
```

**Fix Option 3** (Use window function):
```python
# ✅ CORRECT - Window function for per-row aggregate
SELECT id, symbol,
       COUNT(*) OVER (PARTITION BY symbol) as symbol_count
FROM positions
WHERE user_id = $1
```

**Prevention**:
- ✅ When using COUNT/SUM/AVG, either:
  - Group by all non-aggregated columns (GROUP BY)
  - Or select ONLY aggregated columns
- ✅ Test queries in psql before adding to code
- ✅ Use query linter (pgFormatter, sqlfluff)

---

### 10. ❌ Not Handling NULL in Database Queries

**Problem**: Assuming columns are NOT NULL when they can be NULL.

**Symptom**:
```python
TypeError: unsupported operand type(s) for +: 'NoneType' and 'Decimal'
```

**Root Cause**:
```python
# ❌ WRONG - Assumes equity is NOT NULL
account = await pg_client.fetchrow("SELECT * FROM broker_accounts WHERE id = $1", account_id)
total_equity = account['equity'] + account['balance']  # Fails if equity is NULL!
```

**Fix**:
```python
# ✅ CORRECT - Handle NULL values
account = await pg_client.fetchrow("SELECT * FROM broker_accounts WHERE id = $1", account_id)
equity = account['equity'] or Decimal("0")
balance = account['balance'] or Decimal("0")
total_equity = equity + balance
```

**Prevention**:
- ✅ Use `COALESCE(column, default_value)` in SQL
- ✅ Check for None in Python before arithmetic
- ✅ Define NOT NULL constraints in schema where appropriate
- ✅ Use Pydantic models with Optional[] for nullable fields

---

## WebSocket and Streaming Issues

### 11. ❌ Circuit Breaker `get_state_sync` AttributeError

**Problem**: Calling sync method on async circuit breaker.

**Symptom**:
```python
AttributeError: 'CircuitBreaker' object has no attribute 'get_state_sync'
```

**Root Cause**:
```python
# ❌ WRONG - Calling sync method on async circuit breaker
if circuit_breaker.get_state_sync() == CircuitBreakerState.OPEN:
    # ...
```

**Fix**:
```python
# ✅ CORRECT - Use async method
if await circuit_breaker.get_state() == CircuitBreakerState.OPEN:
    # ...

# OR - Use sync circuit breaker if in sync context
if circuit_breaker.state == CircuitBreakerState.OPEN:
    # ...
```

**Prevention**:
- ✅ Always use `await` with async methods
- ✅ Check circuit breaker class (sync vs async)
- ✅ Use IDE type hints to catch sync/async mismatches

---

### 12. ❌ Blocking Operations in Async Context

**Problem**: Using blocking I/O in async functions.

**Symptom**:
- Event loop blocked
- Timeouts
- Poor performance

**Root Cause**:
```python
# ❌ WRONG - Blocking I/O in async function
async def fetch_data():
    response = requests.get("https://api.example.com")  # Blocks event loop!
    return response.json()
```

**Fix**:
```python
# ✅ CORRECT - Use async HTTP client
async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com")
        return response.json()
```

**Prevention**:
- ✅ Use async libraries (httpx, asyncpg, aioredis)
- ✅ Never use requests, psycopg2, redis-py in async code
- ✅ If blocking I/O required, use `asyncio.to_thread()`

---

## Testing and Debugging Issues

### 13. ❌ Tests Failing Due to Missing `@pytest.mark.asyncio`

**Problem**: Async test functions not marked with `@pytest.mark.asyncio`.

**Symptom**:
```python
RuntimeWarning: coroutine 'test_my_handler' was never awaited
```

**Root Cause**:
```python
# ❌ WRONG - Missing decorator
async def test_my_handler():
    result = await handler.handle(command)
    assert result is not None
```

**Fix**:
```python
# ✅ CORRECT - Add decorator
@pytest.mark.asyncio
async def test_my_handler():
    result = await handler.handle(command)
    assert result is not None
```

**Prevention**:
- ✅ ALL async test functions need `@pytest.mark.asyncio`
- ✅ Add pytest plugin: `pytest-asyncio`
- ✅ Configure pytest.ini: `asyncio_mode = auto`

---

### 14. ❌ Using `MagicMock` for Async Methods

**Problem**: Using `MagicMock` instead of `AsyncMock` for async methods.

**Symptom**:
```python
TypeError: object MagicMock can't be used in 'await' expression
```

**Root Cause**:
```python
# ❌ WRONG - MagicMock for async method
mock_query_bus = MagicMock()
mock_query_bus.query = MagicMock(return_value=None)

# Fails when called with await
result = await mock_query_bus.query(...)  # TypeError!
```

**Fix**:
```python
# ✅ CORRECT - Use AsyncMock
from unittest.mock import AsyncMock

mock_query_bus = AsyncMock()
mock_query_bus.query = AsyncMock(return_value=None)

# Works correctly
result = await mock_query_bus.query(...)
```

**Prevention**:
- ✅ Use `AsyncMock` for ALL async methods
- ✅ Use `MagicMock` for sync methods only
- ✅ Test mocks before using in tests

---

## Summary Checklist

### Before Committing Code

- [ ] No `datetime.utcnow()` (use `datetime.now(UTC)`)
- [ ] All method names are `snake_case` (NOT `PascalCase`)
- [ ] Events inherit from `BaseEvent` (NOT `@dataclass`)
- [ ] All events have `event_type: Literal["EventName"] = "EventName"`
- [ ] Business logic in aggregates (NOT services)
- [ ] Saga events enriched with all data (TRUE SAGA pattern)
- [ ] No queries in sagas for core logic (only safety validations)
- [ ] SQL queries handle NULL values
- [ ] No blocking I/O in async functions
- [ ] Async tests have `@pytest.mark.asyncio`
- [ ] Async mocks use `AsyncMock`

### Code Review Checklist

- [ ] Replay equivalence test exists for aggregates
- [ ] Events contain all data for replay
- [ ] Saga context has all required fields
- [ ] No direct state mutation (only via events)
- [ ] SQL aggregate functions have GROUP BY
- [ ] Circuit breaker calls use correct sync/async method

---

**Next**: See [DEBUGGING_EVENT_FLOW.md](DEBUGGING_EVENT_FLOW.md) for debugging event flow through the system.
