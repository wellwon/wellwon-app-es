# Unit Testing Guide - WellWon Platform

**Last Updated**: 2025-12-06
**Purpose**: Comprehensive guide to writing unit tests for TradeCore domains, handlers, and projectors

---

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Structure](#test-structure)
3. [Testing Aggregates](#testing-aggregates)
4. [Testing Command Handlers](#testing-command-handlers)
5. [Testing Projectors](#testing-projectors)
6. [Testing Sagas](#testing-sagas)
7. [Mocking Dependencies](#mocking-dependencies)
8. [Test Fixtures](#test-fixtures)
9. [Best Practices](#best-practices)
10. [Common Patterns](#common-patterns)

---

## Testing Philosophy

### Core Principles

**1. Test Behavior, Not Implementation**
- Focus on what the component does, not how it does it
- Test public interfaces, not private methods
- Verify business rules and invariants

**2. Event Sourcing Testing**
- Test replay equivalence (replaying events produces same state as commands)
- Verify events contain all necessary data
- Test aggregate state transitions

**3. Isolation**
- Unit tests should NOT require database, Redpanda, or external services
- Mock all external dependencies
- Fast execution (< 1ms per test)

**4. Coverage**
- Test happy paths
- Test edge cases and validations
- Test error conditions
- Test business rule violations

---

## Test Structure

### Directory Layout

```
tests/
├── unit/                           # Unit tests (fast, isolated)
│   ├── test_broker_connection_aggregate_replay.py
│   ├── test_virtual_broker_aggregate_replay.py
│   ├── test_position_validations.py
│   ├── test_order_validations.py
│   ├── services/
│   │   ├── test_market_data_service.py
│   │   └── test_market_data_direct_integration.py
│   └── broker_adapters/
│       ├── alpaca/
│       │   └── test_alpaca_critical_features.py
│       └── tradestation/
│           └── test_streaming_orders_positions.py
│
├── integration/                    # Integration tests (slower, real dependencies)
│   ├── test_wse_broker_connection.py
│   ├── test_wse_broker_account.py
│   └── test_market_data_integration.py
│
└── test_*.py                       # Domain flow tests (API + Database)
    ├── test_automation_cqrs_flow.py
    ├── test_position_domain.py
    └── test_order_position_saga_integration.py
```

### File Naming

- **Unit tests**: `test_{component}_unit.py` or `test_{domain}_{aspect}.py`
- **Integration tests**: `test_{feature}_integration.py`
- **Flow tests**: `test_{domain}_flow.py` or `test_{domain}_cqrs_flow.py`

### Test Method Naming

```python
# ✅ GOOD - Describes what is being tested
def test_open_position_broker_account_not_found():
def test_add_to_position_insufficient_buying_power():
def test_connection_lifecycle_replay():

# ❌ BAD - Generic or unclear
def test_position():
def test_handler():
def test_error():
```

---

## Testing Aggregates

### 1. Replay Equivalence Tests

**Critical for Event Sourcing**: Replaying events MUST produce identical state to executing commands.

**Pattern**: Execute commands → Capture events → Replay into fresh aggregate → Compare states

**Example** (`tests/unit/test_broker_connection_aggregate_replay.py`):

```python
import pytest
import uuid
from datetime import datetime, timezone
from app.broker_connection.aggregate import BrokerConnectionAggregate
from app.infra.broker_adapters.common.adapter_enums import BrokerConnectionStatusEnum


class TestBrokerConnectionReplayEquivalence:
    """Test that replaying events produces identical state"""

    def test_api_credentials_replay(self):
        """Verify replaying API credentials events produces same state"""
        user_id = uuid.uuid4()
        conn_id = uuid.uuid4()

        # Execute commands
        agg1 = BrokerConnectionAggregate(conn_id)
        agg1.initiate(user_id, "alpaca", "paper")
        agg1.store_api_credentials(user_id, "encrypted_key", "encrypted_secret")

        # Get events and state
        events = agg1.get_uncommitted_events()
        state1 = agg1.state.model_dump()

        # Replay into fresh aggregate
        agg2 = BrokerConnectionAggregate(conn_id)
        for event in events:
            agg2._apply(event)
            agg2.version += 1  # Increment version during replay

        state2 = agg2.state.model_dump()

        # States must be identical
        assert state1 == state2, f"States don't match:\nOriginal: {state1}\nReplayed: {state2}"
        assert agg1.version == agg2.version

    def test_full_lifecycle_with_failures_replay(self):
        """Test complete lifecycle with multiple failures and recovery"""
        user_id = uuid.uuid4()
        conn_id = uuid.uuid4()

        # Complex lifecycle: connect → fail → reauth → reconnect → health check → disconnect
        agg1 = BrokerConnectionAggregate(conn_id)
        agg1.initiate(user_id, "alpaca", "paper")
        agg1.store_api_credentials(user_id, "key", "secret")
        agg1.report_connection_failure(user_id, "Temporary network error", {})
        agg1.establish_connection(user_id)
        agg1.report_successful_health_check(user_id, "Healthy")
        agg1.report_health_check_failure(user_id, "Token expired", "error")
        agg1.request_reauth(user_id, "Re-authenticating")
        agg1.store_api_credentials(user_id, "new_key", "new_secret")
        agg1.establish_connection(user_id)
        agg1.request_disconnect(user_id, "User logout")

        # Get events and state
        events = agg1.get_uncommitted_events()
        state1 = agg1.state.model_dump()

        # Replay into fresh aggregate
        agg2 = BrokerConnectionAggregate(conn_id)
        for event in events:
            agg2._apply(event)
            agg2.version += 1

        state2 = agg2.state.model_dump()

        # States must be identical after complex lifecycle
        assert state1 == state2
        assert agg1.version == agg2.version
        assert len(events) == 10  # Should have 10 events in this flow
```

**Key Points**:
- ✅ Test both simple and complex flows
- ✅ Verify `version` increments correctly
- ✅ Use `model_dump()` for state comparison (handles datetime serialization)
- ✅ Test state transitions (e.g., `status` field changes)

---

### 2. Business Rule Tests

**Purpose**: Verify aggregate enforces business invariants

**Example** (Position domain):

```python
def test_position_cannot_close_with_insufficient_quantity(self):
    """Test that closing more than available quantity raises error"""
    position = Position.open(
        user_id=uuid4(),
        broker_account_id=uuid4(),
        order_id=uuid4(),
        symbol="AAPL",
        asset_type=AssetType.STOCK,
        side=PositionSide.LONG,
        quantity=Decimal("100"),
        entry_price=Decimal("150.00"),
        commission=Decimal("1.00"),
        account_equity_at_entry=Decimal("10000.00")
    )

    # Try to close more than available
    with pytest.raises(PositionValidationError) as exc_info:
        position.reduce_position(
            order_id=uuid4(),
            quantity=Decimal("150"),  # More than available!
            exit_price=Decimal("155.00"),
            commission=Decimal("1.00")
        )

    assert "insufficient quantity" in str(exc_info.value).lower()
```

**Key Points**:
- ✅ Test validation errors with `pytest.raises`
- ✅ Verify error messages are clear
- ✅ Test boundary conditions (zero, negative, exceeds limit)

---

### 3. State Transition Tests

**Example**:

```python
def test_connection_lifecycle_state_transitions(self):
    """Test connection state transitions through full lifecycle"""
    conn = BrokerConnectionAggregate(uuid4())
    user_id = uuid4()

    # Initial state
    assert conn.state.status == BrokerConnectionStatusEnum.PENDING

    # After initiation
    conn.initiate(user_id, "alpaca", "paper")
    assert conn.state.status == BrokerConnectionStatusEnum.PENDING

    # After credentials stored
    conn.store_api_credentials(user_id, "key", "secret")
    assert conn.state.status == BrokerConnectionStatusEnum.AUTHENTICATING

    # After connection established
    conn.establish_connection(user_id)
    assert conn.state.status == BrokerConnectionStatusEnum.CONNECTED

    # After disconnect requested
    conn.request_disconnect(user_id, "User logout")
    assert conn.state.status == BrokerConnectionStatusEnum.DISCONNECTING
```

---

## Testing Command Handlers

### 1. Handler Setup Pattern

**Use mocks for all dependencies**:

```python
import pytest
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.position.commands import OpenPositionCommand
from app.position.command_handlers.position_lifecycle_handlers import OpenPositionHandler
from app.position.exceptions import PositionValidationError
from app.broker_account.queries import BrokerAccountDetails


@pytest.fixture
def mock_handler_dependencies():
    """Mock handler dependencies for testing"""
    deps = MagicMock()
    deps.event_bus = AsyncMock()
    deps.event_store = AsyncMock()
    deps.query_bus = AsyncMock()
    deps.command_bus = AsyncMock()
    return deps


@pytest.fixture
def valid_open_position_command():
    """Valid OpenPositionCommand for testing"""
    return OpenPositionCommand(
        user_id=uuid4(),
        broker_account_id=uuid4(),
        order_id=uuid4(),
        symbol="AAPL",
        asset_type=AssetType.STOCK,
        side=PositionSide.LONG,
        quantity=Decimal("100"),
        entry_price=Decimal("150.00"),
        commission=Decimal("1.00"),
        account_equity_at_entry=Decimal("10000.00")
    )


@pytest.fixture
def mock_broker_account():
    """Mock broker account with valid status"""
    return BrokerAccountDetails(
        id=uuid4(),
        user_id=uuid4(),
        broker_connection_id=uuid4(),
        broker_id="alpaca",
        environment="paper",
        asset_type="stock",
        broker_account_id="test-account",
        account_name="Test Account",
        balance=Decimal("10000.00"),
        currency="USD",
        equity=Decimal("10000.00"),
        buying_power=Decimal("20000.00"),
        status="active"
    )
```

---

### 2. Validation Tests

**Test that handlers validate business rules BEFORE calling aggregate**:

```python
@pytest.mark.asyncio
async def test_open_position_broker_account_not_found(
    mock_handler_dependencies,
    valid_open_position_command
):
    """Test that OpenPosition raises error if broker account not found"""
    handler = OpenPositionHandler(mock_handler_dependencies)

    # Mock query bus to return None (account not found)
    mock_handler_dependencies.query_bus.query = AsyncMock(return_value=None)

    with pytest.raises(PositionValidationError) as exc_info:
        await handler.handle(valid_open_position_command)

    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_open_position_broker_account_inactive(
    mock_handler_dependencies,
    valid_open_position_command,
    mock_broker_account
):
    """Test that OpenPosition raises error if broker account is inactive"""
    handler = OpenPositionHandler(mock_handler_dependencies)

    # Set account status to inactive
    mock_broker_account.status = "suspended"

    # Mock query bus to return inactive account
    mock_handler_dependencies.query_bus.query = AsyncMock(return_value=mock_broker_account)

    with pytest.raises(PositionValidationError) as exc_info:
        await handler.handle(valid_open_position_command)

    assert "not active" in str(exc_info.value).lower()
```

---

### 3. Data Enrichment Tests

**Test that handlers enrich commands with queried data**:

```python
@pytest.mark.asyncio
async def test_open_position_account_equity_used(
    mock_handler_dependencies,
    valid_open_position_command,
    mock_broker_account
):
    """Test that OpenPosition uses account equity from broker account"""
    handler = OpenPositionHandler(mock_handler_dependencies)

    # Mock query bus to return account and no existing position
    query_results = [mock_broker_account, None]
    mock_handler_dependencies.query_bus.query = AsyncMock(side_effect=query_results)

    # Mock save_aggregate to capture the position
    saved_position = None
    async def capture_position(position):
        nonlocal saved_position
        saved_position = position

    handler.save_aggregate = AsyncMock(side_effect=capture_position)

    with patch('app.position.command_handlers.position_lifecycle_handlers.Position.open') as mock_open:
        mock_position = MagicMock()
        mock_position.position_id = uuid4()
        mock_open.return_value = mock_position

        await handler.handle(valid_open_position_command)

        # Verify Position.open was called with account equity
        call_kwargs = mock_open.call_args.kwargs
        assert call_kwargs['account_equity_at_entry'] == mock_broker_account.equity
```

---

## Testing Projectors

### 1. Event Projection Tests

**Pattern**: Create event → Call projector → Verify database operations

```python
@pytest.mark.asyncio
async def test_automation_created_projector():
    """Test AutomationCreatedEvent projector"""
    # Arrange
    mock_pg_client = AsyncMock()
    event = AutomationCreatedEvent(
        automation_id=uuid4(),
        user_id=uuid4(),
        name="Test Automation",
        symbol="AAPL",
        asset_type=AssetType.STOCK,
        side_preference=SidePreference.BOTH,
        entry_order_type=OrderType.MARKET,
        exit_order_type=OrderType.MARKET,
        position_sizing=PositionSizing(type="fixed", fixed_quantity=Decimal("10")),
        broker_account_ids=[uuid4()],
        timestamp=datetime.now(UTC)
    )

    # Act
    await project_automation_created(event, mock_pg_client)

    # Assert
    mock_pg_client.execute.assert_called_once()
    call_args = mock_pg_client.execute.call_args

    # Verify SQL
    assert "INSERT INTO automations" in call_args[0][0]

    # Verify parameters
    params = call_args[0][1:]
    assert params[0] == event.automation_id
    assert params[1] == event.user_id
    assert params[2] == event.name
    assert params[3] == event.symbol
```

**Key Points**:
- ✅ Mock `PGClient` with `AsyncMock`
- ✅ Verify SQL queries are correct
- ✅ Verify parameters match event data
- ✅ Test UPSERT logic (INSERT ... ON CONFLICT)

---

### 2. Projection Update Tests

**Test idempotency** (processing event multiple times produces same result):

```python
@pytest.mark.asyncio
async def test_automation_activated_projector_idempotent():
    """Test AutomationActivatedEvent projector is idempotent"""
    mock_pg_client = AsyncMock()
    event = AutomationActivatedEvent(
        automation_id=uuid4(),
        user_id=uuid4(),
        timestamp=datetime.now(UTC)
    )

    # Process event twice
    await project_automation_activated(event, mock_pg_client)
    await project_automation_activated(event, mock_pg_client)

    # Should execute twice (but produce same result due to UPSERT)
    assert mock_pg_client.execute.call_count == 2

    # Verify both calls had same parameters
    call1 = mock_pg_client.execute.call_args_list[0]
    call2 = mock_pg_client.execute.call_args_list[1]
    assert call1 == call2
```

---

## Testing Sagas

### Pattern: Mock All External Calls

```python
@pytest.mark.asyncio
async def test_broker_disconnection_saga_deletes_accounts():
    """Test BrokerDisconnectionSaga deletes all accounts"""
    # Arrange
    mock_command_bus = AsyncMock()
    mock_query_bus = AsyncMock()
    mock_event_bus = AsyncMock()

    saga = BrokerDisconnectionSaga(
        command_bus=mock_command_bus,
        query_bus=mock_query_bus,
        event_bus=mock_event_bus
    )

    # Create enriched event (TRUE SAGA pattern)
    event = BrokerDisconnected(
        broker_connection_id=uuid4(),
        user_id=uuid4(),
        broker_id="alpaca",
        environment="paper",
        reason="User requested",
        linked_account_ids=[uuid4(), uuid4()],  # 2 accounts
        virtual_account_ids=[],
        active_automation_ids=[]
    )

    context = {
        'broker_connection_id': event.broker_connection_id,
        'user_id': event.user_id,
        'broker_id': event.broker_id,
        'environment': event.environment,
        'linked_account_ids': event.linked_account_ids,
        'virtual_account_ids': event.virtual_account_ids
    }

    # Act
    await saga._delete_broker_accounts(context)

    # Assert
    # Should send 2 DeleteBrokerAccountCommand
    assert mock_command_bus.send.call_count == 2
    for call in mock_command_bus.send.call_args_list:
        command = call[0][0]
        assert isinstance(command, DeleteBrokerAccountCommand)
        assert command.account_aggregate_id in event.linked_account_ids
```

---

## Mocking Dependencies

### 1. Mock Event Bus

```python
@pytest.fixture
def mock_event_bus():
    """Mock EventBus for testing"""
    event_bus = AsyncMock()
    event_bus.publish = AsyncMock()
    event_bus.publish_batch = AsyncMock()
    return event_bus
```

### 2. Mock Command/Query Bus

```python
@pytest.fixture
def mock_command_bus():
    """Mock CommandBus for testing"""
    bus = AsyncMock()
    bus.send = AsyncMock()
    bus.dispatch = AsyncMock()
    return bus


@pytest.fixture
def mock_query_bus():
    """Mock QueryBus for testing"""
    bus = AsyncMock()
    bus.query = AsyncMock()
    return bus
```

### 3. Mock PGClient

```python
@pytest.fixture
def mock_pg_client():
    """Mock PostgreSQL client for testing"""
    client = AsyncMock()
    client.execute = AsyncMock()
    client.fetchrow = AsyncMock()
    client.fetch = AsyncMock()
    client.transaction = AsyncMock()
    return client
```

### 4. Mock Broker Adapter

```python
@pytest.fixture
def mock_alpaca_adapter():
    """Mock Alpaca adapter for testing"""
    adapter = AsyncMock()
    adapter.get_account = AsyncMock(return_value={
        'id': 'test-account',
        'equity': '10000.00',
        'cash': '5000.00',
        'buying_power': '20000.00'
    })
    adapter.place_order = AsyncMock(return_value={
        'id': 'order-123',
        'status': 'filled',
        'filled_qty': '100',
        'filled_avg_price': '150.00'
    })
    return adapter
```

### 5. Fake Adapters for Ports (Recommended)

Instead of using `AsyncMock`, use **Fake Adapters** that implement port interfaces. Fakes provide better behavior testing than mocks.

**See:** [PORTS_AND_ADAPTERS_GUIDE.md](./PORTS_AND_ADAPTERS_GUIDE.md) for full Ports & Adapters pattern.

**Location:** `tests/fakes/`

**Example: FakeTelegramAdapter**

```python
# tests/fakes/fake_telegram_adapter.py
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass

@dataclass
class CallRecord:
    """Record of a method call for verification."""
    method: str
    args: tuple
    kwargs: Dict[str, Any]
    result: Any = None

class FakeTelegramAdapter:
    """
    Fake adapter implementing TelegramMessagingPort + TelegramGroupsPort.

    Stores data in memory and tracks all method calls for verification.
    """

    def __init__(self):
        self.messages: List[Dict] = []
        self.topics: Dict[str, Dict] = {}
        self._calls: List[CallRecord] = []
        self._should_fail: Dict[str, str] = {}
        self._next_message_id = 1

    # === Test Setup Methods ===

    def configure_failure(self, method: str, error_message: str) -> None:
        """Configure a method to fail with an error."""
        self._should_fail[method] = error_message

    def clear(self) -> None:
        """Reset state between tests."""
        self.messages.clear()
        self.topics.clear()
        self._calls.clear()
        self._should_fail.clear()

    # === Test Verification Methods ===

    def was_called(self, method: str) -> bool:
        """Check if a method was called."""
        return any(c.method == method for c in self._calls)

    def get_call_count(self, method: str) -> int:
        """Get number of times a method was called."""
        return sum(1 for c in self._calls if c.method == method)

    def get_calls(self, method: str) -> List[CallRecord]:
        """Get all calls to a specific method."""
        return [c for c in self._calls if c.method == method]

    # === Port Implementation ===

    async def send_message(self, chat_id: int, text: str, **kwargs) -> Dict:
        """Send message - stores in memory."""
        self._calls.append(CallRecord("send_message", (chat_id, text), kwargs))

        if "send_message" in self._should_fail:
            raise Exception(self._should_fail["send_message"])

        msg_id = self._next_message_id
        self._next_message_id += 1
        self.messages.append({
            "message_id": msg_id, "chat_id": chat_id, "text": text
        })
        return {"success": True, "message_id": msg_id}

    async def leave_group(self, group_id: int) -> bool:
        """Leave group - returns True."""
        self._calls.append(CallRecord("leave_group", (group_id,), {}))

        if "leave_group" in self._should_fail:
            raise Exception(self._should_fail["leave_group"])

        return True
```

**Using Fake in Tests:**

```python
# tests/unit/customs/test_submit_handler.py
import pytest
from tests.fakes.fake_kontur_adapter import FakeKonturAdapter
from tests.fakes.fake_event_bus import FakeEventBus

@pytest.fixture
def fake_kontur():
    return FakeKonturAdapter()

@pytest.fixture
def fake_event_bus():
    return FakeEventBus()

@pytest.fixture
def handler(fake_kontur, fake_event_bus):
    deps = HandlerDependencies(
        event_bus=fake_event_bus,
        kontur_port=fake_kontur,  # Inject fake port
    )
    return SubmitToKonturHandler(deps)

class TestSubmitToKonturHandler:

    @pytest.mark.asyncio
    async def test_submit_creates_docflow(self, handler, fake_kontur):
        """Test successful docflow creation."""
        command = SubmitToKonturCommand(
            declaration_id=uuid4(),
            user_id=uuid4(),
        )

        result = await handler.handle(command)

        # Verify fake was called
        assert fake_kontur.was_called('create_docflow')
        assert fake_kontur.get_call_count('create_docflow') == 1

    @pytest.mark.asyncio
    async def test_submit_handles_failure(self, handler, fake_kontur):
        """Test handling of API failure."""
        fake_kontur.configure_failure('create_docflow', 'API Error')

        command = SubmitToKonturCommand(declaration_id=uuid4(), user_id=uuid4())

        with pytest.raises(KonturSubmissionError):
            await handler.handle(command)
```

**Available Fake Adapters in `tests/fakes/`:**

| Fake Adapter | Implements Port | Domain |
|--------------|-----------------|--------|
| `FakeKonturAdapter` | `KonturDeclarantPort` | Customs |
| `FakeTelegramAdapter` | `TelegramMessagingPort`, `TelegramGroupsPort` | Chat, Company |
| `FakeDaDataAdapter` | `CompanyEnrichmentPort` | Company |

**Fake vs Mock:**

| Aspect | Fake Adapter | AsyncMock |
|--------|--------------|-----------|
| Behavior | Real implementation in memory | Stub returns |
| State | Stores data, tracks calls | No state |
| Verification | Call history, stored data | Basic call checks |
| Complexity | More code, but reusable | Less code, per-test |
| Recommended | For ports with complex behavior | For simple stubs |

---

## Test Fixtures

### 1. Common Fixtures

Create `tests/conftest.py` for shared fixtures:

```python
import pytest
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def user_id():
    """Generate random user ID"""
    return uuid4()


@pytest.fixture
def broker_account_id():
    """Generate random broker account ID"""
    return uuid4()


@pytest.fixture
def default_position_size():
    """Default position size for testing"""
    return Decimal("100")


@pytest.fixture
def default_entry_price():
    """Default entry price for testing"""
    return Decimal("150.00")


@pytest.fixture
def mock_handler_dependencies():
    """Mock all handler dependencies"""
    deps = MagicMock()
    deps.event_bus = AsyncMock()
    deps.event_store = AsyncMock()
    deps.query_bus = AsyncMock()
    deps.command_bus = AsyncMock()
    deps.pg_client = AsyncMock()
    deps.redis_client = AsyncMock()
    return deps
```

### 2. Domain-Specific Fixtures

Create fixtures for each domain in test files:

```python
@pytest.fixture
def sample_position():
    """Sample position for testing"""
    return Position.open(
        user_id=uuid4(),
        broker_account_id=uuid4(),
        order_id=uuid4(),
        symbol="AAPL",
        asset_type=AssetType.STOCK,
        side=PositionSide.LONG,
        quantity=Decimal("100"),
        entry_price=Decimal("150.00"),
        commission=Decimal("1.00"),
        account_equity_at_entry=Decimal("10000.00")
    )
```

---

## Best Practices

### 1. Fast Tests

```python
# ✅ GOOD - No I/O, completes in < 1ms
def test_position_calculate_pnl():
    position = create_test_position()
    pnl = position.calculate_unrealized_pnl(Decimal("155.00"))
    assert pnl == Decimal("500.00")

# ❌ BAD - Requires database
def test_position_query():
    result = await pg_client.fetchrow("SELECT * FROM positions WHERE id = $1", position_id)
    assert result is not None
```

### 2. Deterministic Tests

```python
# ✅ GOOD - Always produces same result
def test_position_calculation():
    position = Position.open(..., quantity=Decimal("100"), entry_price=Decimal("150.00"))
    pnl = position.calculate_unrealized_pnl(Decimal("155.00"))
    assert pnl == Decimal("500.00")

# ❌ BAD - Non-deterministic (depends on current time)
def test_position_age():
    position = Position.open(..., opened_at=datetime.now(UTC))
    age = position.calculate_age()
    assert age < timedelta(seconds=1)  # Flaky!
```

### 3. Test One Thing

```python
# ✅ GOOD - Tests one specific validation
@pytest.mark.asyncio
async def test_open_position_broker_account_not_found():
    # Test only account not found scenario
    ...

# ❌ BAD - Tests multiple scenarios in one test
@pytest.mark.asyncio
async def test_open_position_all_validations():
    # Test account not found, account inactive, duplicate position, etc.
    # Hard to debug if it fails!
    ...
```

### 4. Clear Assertions

```python
# ✅ GOOD - Clear assertion message
assert position.status == PositionStatus.OPEN, \
    f"Expected position status OPEN, got {position.status}"

# ✅ GOOD - Use pytest.raises with message check
with pytest.raises(PositionValidationError) as exc_info:
    position.reduce_position(quantity=Decimal("150"))
assert "insufficient quantity" in str(exc_info.value).lower()

# ❌ BAD - No assertion message
assert position.status == PositionStatus.OPEN
```

---

## Common Patterns

### 1. Test Async Handlers

```python
@pytest.mark.asyncio
async def test_command_handler():
    handler = MyCommandHandler(mock_dependencies)
    command = MyCommand(...)
    result = await handler.handle(command)
    assert result is not None
```

### 2. Test Exception Handling

```python
@pytest.mark.asyncio
async def test_handler_error_handling():
    handler = MyCommandHandler(mock_dependencies)
    mock_dependencies.query_bus.query = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(MyDomainException) as exc_info:
        await handler.handle(command)

    assert "failed to query" in str(exc_info.value).lower()
```

### 3. Test Side Effects

```python
@pytest.mark.asyncio
async def test_handler_publishes_event():
    handler = MyCommandHandler(mock_dependencies)
    command = MyCommand(...)

    await handler.handle(command)

    # Verify event published
    mock_dependencies.event_bus.publish.assert_called_once()
    event = mock_dependencies.event_bus.publish.call_args[0][0]
    assert isinstance(event, MyDomainEvent)
    assert event.aggregate_id == command.aggregate_id
```

### 4. Test Data Transformation

```python
@pytest.mark.asyncio
async def test_projector_transforms_event_correctly():
    mock_pg_client = AsyncMock()
    event = MyEvent(field1="value1", field2=Decimal("123.45"))

    await my_projector(event, mock_pg_client)

    # Verify transformation
    call_args = mock_pg_client.execute.call_args[0]
    assert call_args[1] == event.field1  # String unchanged
    assert call_args[2] == str(event.field2)  # Decimal → str for database
```

---

## Running Tests

### Command Line

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_position_validations.py -v

# Run specific test
pytest tests/unit/test_position_validations.py::test_open_position_broker_account_not_found -v

# Run with coverage
pytest tests/unit/ --cov=app --cov-report=html

# Run tests matching pattern
pytest -k "validation" -v

# Run tests in parallel (faster)
pytest tests/unit/ -n auto
```

### PyCharm

1. Right-click test file → Run 'pytest in test_...'
2. Click green arrow next to test method
3. View coverage: Run → Run with Coverage

---

## Troubleshooting

### Common Issues

**1. Async test not running**
```python
# ❌ MISSING @pytest.mark.asyncio
async def test_my_handler():
    await handler.handle(command)

# ✅ CORRECT
@pytest.mark.asyncio
async def test_my_handler():
    await handler.handle(command)
```

**2. Mock not being called**
```python
# ❌ Mock not configured
mock_query_bus.query = MagicMock(return_value=None)  # Wrong for async!

# ✅ Use AsyncMock for async methods
mock_query_bus.query = AsyncMock(return_value=None)
```

**3. Event replay test fails**
```python
# ❌ Forgot to increment version during replay
for event in events:
    agg2._apply(event)
    # Missing version increment!

# ✅ Increment version after each event
for event in events:
    agg2._apply(event)
    agg2.version += 1
```

---

## Example Test Files

**See these files for examples**:
- `/Users/silvermpx/PycharmProjects/TradeCore/tests/unit/test_broker_connection_aggregate_replay.py`
- `/Users/silvermpx/PycharmProjects/TradeCore/tests/unit/test_position_validations.py`
- `/Users/silvermpx/PycharmProjects/TradeCore/tests/unit/test_order_validations.py`

---

## Summary Checklist

When writing unit tests:

- [ ] Test replay equivalence for aggregates
- [ ] Test business rule validations
- [ ] Mock all external dependencies (database, event bus, etc.)
- [ ] Use `@pytest.mark.asyncio` for async tests
- [ ] Use `AsyncMock` for async methods
- [ ] Test both happy path and error cases
- [ ] Verify event data contains all necessary fields
- [ ] Test idempotency of projectors
- [ ] Keep tests fast (< 1ms per test)
- [ ] Use clear assertion messages
- [ ] Test one thing per test method

---

**Next**: See [INTEGRATION_TESTING_GUIDE.md](INTEGRATION_TESTING_GUIDE.md) for integration testing patterns.
