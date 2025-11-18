# Integration Testing Guide - TradeCore v0.5

**Last Updated**: 2025-11-10
**Purpose**: Guide to writing integration tests that verify end-to-end flows with real dependencies

---

## Table of Contents

1. [Integration Testing Philosophy](#integration-testing-philosophy)
2. [Test Environment Setup](#test-environment-setup)
3. [Testing Event Flow](#testing-event-flow)
4. [Testing Sagas](#testing-sagas)
5. [Testing API Endpoints](#testing-api-endpoints)
6. [Testing WebSocket Streaming (WSE)](#testing-websocket-streaming-wse)
7. [Testing Database Operations](#testing-database-operations)
8. [Testing Redpanda Integration](#testing-redpanda-integration)
9. [Best Practices](#best-practices)
10. [Common Patterns](#common-patterns)

---

## Integration Testing Philosophy

### What are Integration Tests?

**Integration tests** verify that multiple components work together correctly with real (or realistic) dependencies:
- Real PostgreSQL database
- Real Redpanda (or mock Kafka)
- Real WebSocket connections
- Real HTTP API calls

### Unit vs Integration Tests

| Aspect | Unit Tests | Integration Tests |
|--------|-----------|-------------------|
| **Speed** | < 1ms per test | 100ms - 5s per test |
| **Dependencies** | All mocked | Real or realistic |
| **Scope** | Single component | Multiple components |
| **Purpose** | Test logic | Test integration |
| **Reliability** | Very reliable | Can be flaky |
| **Execution** | Always run | Run before merge |

### When to Write Integration Tests

✅ **Write integration tests for**:
- CQRS flow (Command → Event → Projection)
- Saga orchestration (multi-step workflows)
- API endpoint behavior
- WebSocket message delivery
- Event bus publishing/consuming
- Database schema validation

❌ **Don't write integration tests for**:
- Simple validation logic (use unit tests)
- Single aggregate behavior (use unit tests)
- Error message formatting (use unit tests)

---

## Test Environment Setup

### 1. Test Database

**Use separate test database**:

```python
# tests/conftest.py
import pytest
import asyncpg
import os

TEST_POSTGRES_DSN = os.getenv(
    "TEST_POSTGRES_DSN",
    "postgresql://tradecore:password@localhost:5432/tradecore_test"
)


@pytest.fixture(scope="session")
async def test_db():
    """Create test database connection pool"""
    pool = await asyncpg.create_pool(TEST_POSTGRES_DSN, min_size=2, max_size=10)
    yield pool
    await pool.close()


@pytest.fixture
async def pg_client(test_db):
    """Get database connection for test"""
    async with test_db.acquire() as conn:
        # Start transaction
        async with conn.transaction():
            yield conn
            # Rollback after test (automatic cleanup)
```

**Key Points**:
- ✅ Use transaction rollback for cleanup (faster than DELETE)
- ✅ Separate database for tests (don't pollute production data)
- ✅ Session-scoped pool, function-scoped connections

---

### 2. Test API Client

**Use httpx for async HTTP calls**:

```python
import pytest
import httpx

API_BASE_URL = "http://localhost:5001"


@pytest.fixture
async def api_client():
    """Create async HTTP client for API testing"""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
async def authenticated_client(api_client):
    """Create authenticated API client"""
    # Login to get JWT token
    response = await api_client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "testpassword"
    })
    token = response.json()["access_token"]

    # Add auth header to all requests
    api_client.headers["Authorization"] = f"Bearer {token}"
    return api_client
```

---

### 3. WebSocket Client

**Mock WebSocket for WSE testing**:

```python
import pytest
import json
from typing import List, Dict, Any


class MockWebSocket:
    """Mock WebSocket for testing"""

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []
        self.state = "CONNECTED"

    async def send_text(self, data: str):
        """Mock send_text"""
        self.sent_messages.append(json.loads(data))

    async def send_bytes(self, data: bytes):
        """Mock send_bytes"""
        # Handle compressed messages (C: prefix)
        if data.startswith(b'C:'):
            self.sent_messages.append({
                "_compressed": True,
                "_size": len(data)
            })
        else:
            self.sent_messages.append(json.loads(data.decode('utf-8')))

    def get_messages_by_type(self, event_type: str) -> List[Dict]:
        """Get all messages matching event type"""
        return [msg for msg in self.sent_messages if msg.get("t") == event_type]


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket for testing"""
    return MockWebSocket()
```

---

## Testing Event Flow

### Pattern: Command → Event → Projection

**Test complete CQRS flow** (`tests/test_automation_cqrs_flow.py`):

```python
import asyncio
import httpx
import asyncpg


class AutomationCQRSTest:
    """Test Automation domain CQRS flow"""

    def __init__(self):
        self.token = None
        self.automation_id = None
        self.pg_conn = None

    async def setup(self):
        """Setup test environment"""
        # Load JWT token
        with open('/tmp/token.txt', 'r') as f:
            self.token = f.read().strip()

        # Connect to PostgreSQL
        self.pg_conn = await asyncpg.connect(POSTGRES_DSN)

    async def test_create_automation(self):
        """
        TEST: Create Automation via API

        Validates:
        - CreateAutomationCommand processed
        - AutomationCreatedEvent emitted (SYNC priority 2)
        - Read model projection created
        - Broker account junction table updated
        """
        # 1. Send API request (Command)
        payload = {
            "name": "Test AAPL CQRS",
            "symbol": "AAPL",
            "assetType": "stock",
            "brokerAccountIds": [TEST_BROKER_ACCOUNT_ID],
            "positionSizing": {
                "type": "fixed",
                "fixedQuantity": "10"
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/automations",
                json=payload,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=30.0
            )

        assert response.status_code == 201
        data = response.json()
        self.automation_id = data.get("automationId")

        # 2. Wait for projection (eventual consistency)
        await asyncio.sleep(2)

        # 3. Verify read model (Projection)
        query = """
            SELECT id, name, symbol, status, position_sizing_type,
                   fixed_quantity, aggregate_version
            FROM automations
            WHERE id = $1
        """

        row = await self.pg_conn.fetchrow(query, uuid.UUID(self.automation_id))

        assert row is not None
        assert row['name'] == "Test AAPL CQRS"
        assert row['symbol'] == "AAPL"
        assert row['status'] == "inactive"
        assert row['position_sizing_type'] == "fixed"
        assert row['fixed_quantity'] == Decimal("10")

        # 4. Verify event stored
        query = """
            SELECT event_id, event_type, status, published_at
            FROM event_outbox
            WHERE aggregate_id = $1
              AND event_type = 'AutomationCreatedEvent'
            ORDER BY created_at DESC
            LIMIT 1
        """

        event_row = await self.pg_conn.fetchrow(query, uuid.UUID(self.automation_id))

        assert event_row is not None
        assert event_row['status'] == 'published'
```

**Key Points**:
- ✅ Test full flow: API → Command → Event → Projection
- ✅ Wait for eventual consistency (asyncio.sleep)
- ✅ Verify read model matches command data
- ✅ Verify event stored and published

---

## Testing Sagas

### Pattern: Event → Saga → Multiple Commands

**Test saga orchestration**:

```python
@pytest.mark.asyncio
async def test_broker_disconnection_saga_full_flow(pg_client, api_client):
    """
    Test BrokerDisconnectionSaga deletes all accounts and connection

    Flow:
    1. User creates broker connection
    2. Broker accounts created
    3. User requests disconnect
    4. BrokerDisconnected event triggers saga
    5. Saga deletes all accounts
    6. Saga deletes connection
    """
    # 1. Create broker connection
    response = await api_client.post("/broker-connections", json={
        "broker_id": "alpaca",
        "environment": "paper",
        "api_key": "test_key",
        "api_secret": "test_secret"
    })
    assert response.status_code == 201
    connection_id = response.json()["connection_id"]

    # 2. Wait for accounts to be discovered
    await asyncio.sleep(5)

    # 3. Verify accounts exist
    accounts = await pg_client.fetch(
        "SELECT id FROM broker_accounts WHERE broker_connection_id = $1",
        uuid.UUID(connection_id)
    )
    assert len(accounts) > 0
    account_count = len(accounts)

    # 4. Request disconnect (triggers saga)
    response = await api_client.post(
        f"/broker-connections/{connection_id}/disconnect",
        json={"reason": "Test disconnect"}
    )
    assert response.status_code == 200

    # 5. Wait for saga to complete (eventual consistency)
    await asyncio.sleep(10)

    # 6. Verify accounts deleted
    accounts_after = await pg_client.fetch(
        "SELECT id FROM broker_accounts WHERE broker_connection_id = $1 AND deleted = FALSE",
        uuid.UUID(connection_id)
    )
    assert len(accounts_after) == 0, f"Expected 0 accounts, found {len(accounts_after)}"

    # 7. Verify connection deleted
    connection = await pg_client.fetchrow(
        "SELECT id FROM broker_connections WHERE id = $1",
        uuid.UUID(connection_id)
    )
    assert connection is None, "Connection should be deleted"

    # 8. Verify saga completion event
    saga_events = await pg_client.fetch(
        """
        SELECT event_type, status
        FROM event_outbox
        WHERE aggregate_id = $1
        ORDER BY created_at DESC
        LIMIT 5
        """,
        uuid.UUID(connection_id)
    )

    event_types = [e['event_type'] for e in saga_events]
    assert 'BrokerDisconnected' in event_types
```

**Key Points**:
- ✅ Test complete saga lifecycle
- ✅ Verify all side effects (deletions, state changes)
- ✅ Verify saga completion
- ✅ Use realistic timing (await asyncio.sleep for eventual consistency)

---

## Testing API Endpoints

### Pattern: Request → Response → Database

**Test CRUD operations**:

```python
@pytest.mark.asyncio
async def test_create_automation_endpoint(authenticated_client, pg_client):
    """Test POST /automations endpoint"""
    # 1. Send request
    payload = {
        "name": "Test Strategy",
        "symbol": "AAPL",
        "assetType": "stock",
        "brokerAccountIds": [str(TEST_BROKER_ACCOUNT_ID)],
        "positionSizing": {"type": "fixed", "fixedQuantity": "100"}
    }

    response = await authenticated_client.post("/automations", json=payload)

    # 2. Verify response
    assert response.status_code == 201
    data = response.json()
    assert "automationId" in data
    automation_id = data["automationId"]

    # 3. Verify database
    await asyncio.sleep(1)  # Wait for projection
    row = await pg_client.fetchrow(
        "SELECT name, symbol FROM automations WHERE id = $1",
        uuid.UUID(automation_id)
    )
    assert row is not None
    assert row['name'] == "Test Strategy"
    assert row['symbol'] == "AAPL"


@pytest.mark.asyncio
async def test_get_automation_endpoint(authenticated_client, pg_client):
    """Test GET /automations/{id} endpoint"""
    # 1. Create automation directly in database
    automation_id = uuid4()
    await pg_client.execute(
        """
        INSERT INTO automations (id, user_id, name, symbol, status, asset_type)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        automation_id, TEST_USER_ID, "Test", "AAPL", "active", "stock"
    )

    # 2. Query via API
    response = await authenticated_client.get(f"/automations/{automation_id}")

    # 3. Verify response
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == str(automation_id)
    assert data['name'] == "Test"
    assert data['symbol'] == "AAPL"
    assert data['status'] == "active"


@pytest.mark.asyncio
async def test_update_automation_endpoint(authenticated_client, pg_client):
    """Test PUT /automations/{id} endpoint"""
    # 1. Create automation
    automation_id = uuid4()
    await pg_client.execute(
        """
        INSERT INTO automations (id, user_id, name, symbol, status, asset_type, fixed_quantity)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        automation_id, TEST_USER_ID, "Test", "AAPL", "active", "stock", Decimal("10")
    )

    # 2. Update via API
    response = await authenticated_client.put(
        f"/automations/{automation_id}",
        json={"positionSizing": {"type": "fixed", "fixedQuantity": "20"}}
    )

    assert response.status_code == 200

    # 3. Verify database updated
    await asyncio.sleep(1)  # Wait for projection
    row = await pg_client.fetchrow(
        "SELECT fixed_quantity FROM automations WHERE id = $1",
        automation_id
    )
    assert row['fixed_quantity'] == Decimal("20")
```

---

## Testing WebSocket Streaming (WSE)

### Pattern: Event → WSE → WebSocket Message

**Test event transformation and delivery** (`tests/integration/test_wse_broker_connection.py`):

```python
@pytest.mark.asyncio
async def test_connection_created_transformation():
    """Test BrokerConnectionCreated event transformation"""
    # Arrange
    event = {
        "event_type": "BrokerConnectionCreated",
        "broker_connection_id": "conn_123",
        "broker_id": "alpaca",
        "environment": "paper",
        "user_id": "user_456",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    metadata = {
        "aggregate_id": "conn_123",
        "aggregate_type": "BrokerConnection",
        "version": 1,
        "timestamp": event["timestamp"]
    }

    # Act
    result = await EventTransformer.transform_event(event, metadata)

    # Assert
    assert result is not None
    assert result["t"] == "broker_connection_created"
    assert result["p"]["id"] == "conn_123"
    assert result["p"]["broker_id"] == "alpaca"
    assert result["p"]["environment"] == "paper"
    assert "event_version" in result
    assert "latency_ms" in result
    assert result["v"] == 2  # Protocol version


@pytest.mark.asyncio
async def test_full_connection_lifecycle_wse(mock_websocket):
    """Test complete broker connection lifecycle through WSE"""
    # This test simulates the full flow:
    # 1. Connection created
    # 2. Connection established
    # 3. Connection disconnected
    # 4. Connection deleted

    events = [
        {
            "event_type": "BrokerConnectionCreated",
            "broker_connection_id": "conn_123",
            "broker_id": "alpaca",
            "environment": "paper",
        },
        {
            "event_type": "BrokerConnectionEstablished",
            "broker_connection_id": "conn_123",
            "status": "connected",
        },
        {
            "event_type": "BrokerConnectionDisconnected",
            "broker_connection_id": "conn_123",
            "status": "disconnected",
        },
        {
            "event_type": "BrokerConnectionDeleted",
            "broker_connection_id": "conn_123",
        }
    ]

    results = []
    for event in events:
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        metadata = {"timestamp": event["timestamp"]}
        result = await EventTransformer.transform_event(event, metadata)
        results.append(result)

    # Assert sequence
    assert results[0]["t"] == "broker_connection_created"
    assert results[1]["t"] == "broker_connection_update"
    assert results[1]["p"]["status"] == "connected"
    assert results[2]["t"] == "broker_connection_update"
    assert results[2]["p"]["status"] == "disconnected"
    assert results[3]["t"] == "broker_connection_deleted"
```

**Key Points**:
- ✅ Test event transformation (domain event → WSE message)
- ✅ Test complete lifecycle flows
- ✅ Verify message format (type, payload, version, latency)
- ✅ Test observability fields (trace_id, latency_ms)

---

## Testing Database Operations

### Pattern: Execute → Query → Verify

**Test database schema and constraints**:

```python
@pytest.mark.asyncio
async def test_automation_table_schema(pg_client):
    """Test automations table has correct schema"""
    # Query table structure
    columns = await pg_client.fetch(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'automations'
        ORDER BY ordinal_position
        """
    )

    column_map = {col['column_name']: col for col in columns}

    # Verify required columns exist
    assert 'id' in column_map
    assert column_map['id']['data_type'] == 'uuid'
    assert column_map['id']['is_nullable'] == 'NO'

    assert 'user_id' in column_map
    assert column_map['user_id']['data_type'] == 'uuid'
    assert column_map['user_id']['is_nullable'] == 'NO'

    assert 'symbol' in column_map
    assert column_map['symbol']['data_type'] == 'character varying'


@pytest.mark.asyncio
async def test_automation_foreign_key_constraints(pg_client):
    """Test foreign key constraints are enforced"""
    # Try to insert automation with invalid user_id
    invalid_user_id = uuid4()

    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await pg_client.execute(
            """
            INSERT INTO automations (id, user_id, name, symbol, status, asset_type)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            uuid4(), invalid_user_id, "Test", "AAPL", "active", "stock"
        )


@pytest.mark.asyncio
async def test_automation_unique_constraints(pg_client):
    """Test unique constraints are enforced"""
    # Insert first automation
    automation_id = uuid4()
    await pg_client.execute(
        """
        INSERT INTO automations (id, user_id, name, symbol, status, asset_type)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        automation_id, TEST_USER_ID, "Test", "AAPL", "active", "stock"
    )

    # Try to insert duplicate ID
    with pytest.raises(asyncpg.UniqueViolationError):
        await pg_client.execute(
            """
            INSERT INTO automations (id, user_id, name, symbol, status, asset_type)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            automation_id, TEST_USER_ID, "Test2", "TSLA", "active", "stock"
        )
```

---

## Testing Redpanda Integration

### Pattern: Publish → Consume → Verify

**Test event publishing and consumption**:

```python
@pytest.mark.asyncio
async def test_event_published_to_redpanda(event_bus, pg_client):
    """Test that domain events are published to Redpanda"""
    # 1. Create command
    command = CreateAutomationCommand(
        user_id=TEST_USER_ID,
        name="Test",
        symbol="AAPL",
        asset_type=AssetType.STOCK,
        # ...
    )

    # 2. Execute command
    await command_bus.send(command)

    # 3. Wait for event to be published
    await asyncio.sleep(1)

    # 4. Verify event in outbox
    events = await pg_client.fetch(
        """
        SELECT event_type, status, published_at
        FROM event_outbox
        WHERE aggregate_type = 'Automation'
        ORDER BY created_at DESC
        LIMIT 1
        """
    )

    assert len(events) > 0
    assert events[0]['event_type'] == 'AutomationCreatedEvent'
    assert events[0]['status'] == 'published'
    assert events[0]['published_at'] is not None


@pytest.mark.asyncio
async def test_event_consumed_by_projector(event_bus, pg_client):
    """Test that published events are consumed and projected"""
    # 1. Publish event
    event = AutomationCreatedEvent(
        automation_id=uuid4(),
        user_id=TEST_USER_ID,
        name="Test",
        symbol="AAPL",
        # ...
    )

    await event_bus.publish(event)

    # 2. Wait for consumer to process
    await asyncio.sleep(2)

    # 3. Verify projection created
    row = await pg_client.fetchrow(
        "SELECT name, symbol FROM automations WHERE id = $1",
        event.automation_id
    )

    assert row is not None
    assert row['name'] == "Test"
    assert row['symbol'] == "AAPL"
```

---

## Best Practices

### 1. Cleanup After Tests

```python
@pytest.fixture
async def test_automation(pg_client):
    """Create test automation, cleanup after test"""
    automation_id = uuid4()

    # Setup
    await pg_client.execute(
        """
        INSERT INTO automations (id, user_id, name, symbol, status, asset_type)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        automation_id, TEST_USER_ID, "Test", "AAPL", "active", "stock"
    )

    yield automation_id

    # Cleanup
    await pg_client.execute("DELETE FROM automations WHERE id = $1", automation_id)
```

### 2. Use Realistic Timing

```python
# ✅ GOOD - Wait for eventual consistency
await asyncio.sleep(2)  # Projection typically takes 1-2 seconds

# ❌ BAD - Too short, test will be flaky
await asyncio.sleep(0.1)

# ❌ BAD - Too long, test suite slow
await asyncio.sleep(30)
```

### 3. Test Idempotency

```python
@pytest.mark.asyncio
async def test_projection_idempotent(pg_client):
    """Test that processing event twice produces same result"""
    event = AutomationCreatedEvent(...)

    # Process event twice
    await project_automation_created(event, pg_client)
    await project_automation_created(event, pg_client)

    # Should only have one row (UPSERT behavior)
    count = await pg_client.fetchval(
        "SELECT COUNT(*) FROM automations WHERE id = $1",
        event.automation_id
    )
    assert count == 1
```

### 4. Test Concurrent Operations

```python
@pytest.mark.asyncio
async def test_concurrent_position_updates(pg_client, command_bus):
    """Test that concurrent updates don't cause race conditions"""
    position_id = uuid4()

    # Create position
    # ...

    # Update concurrently
    tasks = [
        command_bus.send(UpdatePositionCommand(...)),
        command_bus.send(UpdatePositionCommand(...)),
        command_bus.send(UpdatePositionCommand(...))
    ]

    await asyncio.gather(*tasks)

    # Verify final state is consistent
    position = await pg_client.fetchrow(
        "SELECT * FROM positions WHERE id = $1",
        position_id
    )
    # Verify aggregate version incremented correctly
    # Verify no data loss
```

---

## Common Patterns

### 1. Wait for Eventual Consistency

```python
async def wait_for_projection(pg_client, automation_id, max_wait=5):
    """Wait for automation to appear in read model"""
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < max_wait:
        row = await pg_client.fetchrow(
            "SELECT id FROM automations WHERE id = $1",
            automation_id
        )
        if row is not None:
            return True
        await asyncio.sleep(0.1)
    return False

# Usage
automation_id = await create_automation()
assert await wait_for_projection(pg_client, automation_id)
```

### 2. Verify Event Sequence

```python
@pytest.mark.asyncio
async def test_event_sequence(pg_client):
    """Verify events published in correct order"""
    # Execute operations
    await create_automation()
    await activate_automation()
    await deactivate_automation()

    # Verify event sequence
    events = await pg_client.fetch(
        """
        SELECT event_type
        FROM event_outbox
        WHERE aggregate_id = $1
        ORDER BY created_at ASC
        """,
        automation_id
    )

    event_types = [e['event_type'] for e in events]
    assert event_types == [
        'AutomationCreatedEvent',
        'AutomationActivatedEvent',
        'AutomationDeactivatedEvent'
    ]
```

### 3. Test Error Recovery

```python
@pytest.mark.asyncio
async def test_saga_compensates_on_failure(pg_client):
    """Test saga compensates when step fails"""
    # 1. Trigger saga
    # 2. Simulate failure in middle step
    # 3. Verify compensation executed
    # 4. Verify system state rolled back
```

---

## Running Integration Tests

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run with real Redpanda (requires docker-compose)
docker-compose -f docker/docker-compose.redpanda.yml up -d
pytest tests/integration/ -v

# Run specific integration test
pytest tests/integration/test_wse_broker_connection.py -v

# Run with slower timeout (for debugging)
pytest tests/integration/ -v --timeout=60
```

---

## Summary Checklist

When writing integration tests:

- [ ] Test complete CQRS flow (Command → Event → Projection)
- [ ] Wait for eventual consistency (realistic timing)
- [ ] Verify database state after operations
- [ ] Test saga orchestration (multi-step workflows)
- [ ] Test API endpoints with real HTTP calls
- [ ] Test WebSocket message delivery (WSE)
- [ ] Clean up test data after each test
- [ ] Test error scenarios and recovery
- [ ] Test idempotency of operations
- [ ] Use realistic test data (not "test", "foo", "bar")

---

**Next**: See [COMMON_PITFALLS.md](COMMON_PITFALLS.md) for bugs we've fixed and how to avoid them.
