# Query Handler Implementation Guide

**TradeCore v0.5 - CQRS Read Side**
**Last Updated:** 2025-01-10
**Status:** Production Reference

---

## Table of Contents

1. [Overview](#overview)
2. [Purpose and When to Use](#purpose-and-when-to-use)
3. [Architecture](#architecture)
4. [BaseQueryHandler Pattern](#basequeryhandler-pattern)
5. [Step-by-Step Implementation](#step-by-step-implementation)
6. [Code Examples from TradeCore](#code-examples-from-tradecore)
7. [Testing Strategies](#testing-strategies)
8. [Performance Tips](#performance-tips)
9. [Common Mistakes](#common-mistakes)

---

## Overview

Query handlers are the **read side** of TradeCore's CQRS architecture. They:
- Fetch data from read models (PostgreSQL projections)
- Provide optimized views for different use cases
- Support pagination, filtering, and sorting
- Never mutate state (read-only operations)
- Can use caching for performance

### Key Principles

1. **Queries are READ-ONLY** - No state mutations, no events
2. **Use read models, not aggregates** - Optimized for querying
3. **BaseQueryHandler is OPTIONAL** - Lightweight pattern
4. **Authorization at query level** - Validate ownership
5. **Cache when appropriate** - Use `@cached_query_handler`

---

## Purpose and When to Use

### When to Create a Query Handler

Create a query handler when you need to:
- ✅ **Fetch data for display** (lists, details, dashboards)
- ✅ **Validate authorization** (user owns resource)
- ✅ **Support pagination/filtering** (large datasets)
- ✅ **Aggregate data** (statistics, reports)
- ✅ **Join multiple read models** (complex views)

### When NOT to Use Query Handlers

DON'T create query handlers for:
- ❌ **Mutating state** - Use command handlers
- ❌ **Complex business logic** - Use domain aggregates
- ❌ **Event sourcing** - Use event store directly
- ❌ **Infrastructure operations** - Use services

---

## Architecture

### Query Flow

```
API Request
    ↓
Query (dataclass/Pydantic with params)
    ↓
Query Bus (routes to handler)
    ↓
Query Handler (orchestration)
    ↓
Read Repository (PostgreSQL read models)
    ↓
Return DTO/Read Model
    ↓
API Response (JSON serialization)
```

### Query Types

TradeCore supports three query patterns:

| Pattern | Use Case | Example |
|---------|----------|---------|
| **Simple Query** | Single record by ID | `GetOrderQuery(order_id=...)` |
| **List Query** | Multiple records with filters | `GetOrdersByUserQuery(user_id=...)` |
| **Aggregate Query** | Statistics/summaries | `GetAccountStatisticsQuery(user_id=...)` |

---

## BaseQueryHandler Pattern

### Overview

`BaseQueryHandler` is a **lightweight, optional** base class introduced in TradeCore v0.5. It provides:
- ✅ Logging infrastructure
- ✅ Authorization helpers
- ✅ Error handling wrappers
- ✅ Performance tracking
- ✅ Safe attribute access

**Key Point:** Inheritance is OPTIONAL. Simple queries work fine without it.

### When to Use BaseQueryHandler

| Scenario | Use BaseQueryHandler? | Reason |
|----------|----------------------|--------|
| Simple repo query | Optional | Minimal benefit |
| Authorization needed | **Yes** | Use `validate_resource_ownership()` |
| Error handling | **Yes** | Use `handle_not_found()` |
| Performance tracking | **Yes** | Use `start_tracking()` |
| Complex logic | **Yes** | Use logging and helpers |

### Class Structure

```python
from app.common.base.base_query_handler import BaseQueryHandler

@query_handler(GetOrderQuery)
class GetOrderQueryHandler(BaseQueryHandler[GetOrderQuery, Optional[OrderReadModel]]):
    """
    Handler with BaseQueryHandler utilities

    Generic types:
    - TQuery: GetOrderQuery
    - TResult: Optional[OrderReadModel]
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()  # Initialize logging
        self.order_repo = deps.order_read_repo

    async def handle(self, query: GetOrderQuery) -> Optional[OrderReadModel]:
        """
        Handle query and return result

        Must implement this abstract method
        """
        order = await self.order_repo.get_by_id(query.order_id)

        # Use base class helpers
        order = self.handle_not_found(
            resource=order,
            resource_type="Order",
            resource_id=query.order_id,
            raise_exception=False  # Return None instead
        )

        if order:
            self.validate_resource_ownership(
                resource_user_id=order.user_id,
                requesting_user_id=query.user_id,
                resource_type="Order"
            )

        return order
```

### Available Utilities

**Authorization:**
- `validate_resource_ownership()` - Strict ownership check (raises exception)
- `validate_optional_resource_ownership()` - Flexible check (returns bool)

**Error Handling:**
- `handle_not_found()` - Resource not found handling
- `safe_getattr()` - Safe attribute access with transform

**Performance:**
- `start_tracking()` - Start execution timer
- `end_tracking()` - End timer and log duration
- `get_execution_time()` - Get current duration

**Logging:**
- `log_query_start()` - Log query start
- `log_query_result()` - Log query completion
- `self.log` - Instance logger

---

## Step-by-Step Implementation

### Step 1: Define Query (queries.py)

Queries use Pydantic `Query` base class for validation:

```python
from uuid import UUID
from typing import Optional
from pydantic import Field

from app.infra.cqrs.query_bus import Query

class GetOrderQuery(Query):
    """
    Get order by ID

    Queries use Pydantic Query base class.
    All fields validated automatically.
    """
    order_id: UUID
    user_id: UUID  # For authorization
    saga_id: Optional[UUID] = None  # For saga coordination

class GetOrdersByUserQuery(Query):
    """Get orders for user with pagination"""
    user_id: UUID
    status: Optional[str] = None  # Filter by status
    limit: int = Field(default=100, ge=1, le=1000)  # Pagination
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc")
```

**Key Points:**
- Use `Query` base class (from `app.infra.cqrs.query_bus`)
- Pydantic validation automatic
- Include `user_id` for authorization
- Support pagination with `limit/offset`

---

### Step 2: Create Handler Class (query_handlers/)

**Option A: Simple Handler (No BaseQueryHandler)**

```python
from typing import TYPE_CHECKING, Optional
from app.infra.cqrs.decorators import query_handler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

@query_handler(GetOrderQuery)
class GetOrderQueryHandler:
    """Simple query handler - no base class"""

    def __init__(self, deps: 'HandlerDependencies'):
        self.order_repo = deps.order_read_repo

    async def handle(self, query: GetOrderQuery) -> Optional[OrderReadModel]:
        """Get order by ID"""
        return await self.order_repo.get_by_id(
            order_id=query.order_id,
            user_id=query.user_id
        )
```

**Option B: Handler with BaseQueryHandler**

```python
from app.common.base.base_query_handler import BaseQueryHandler
from app.infra.cqrs.decorators import query_handler, readonly_query

@readonly_query(GetOrderQuery)  # Marks as read-only
class GetOrderQueryHandler(BaseQueryHandler[GetOrderQuery, Optional[OrderReadModel]]):
    """Handler with BaseQueryHandler utilities"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()  # Initialize logging
        self.order_repo = deps.order_read_repo

    async def handle(self, query: GetOrderQuery) -> Optional[OrderReadModel]:
        """Get order by ID with authorization"""
        # Fetch order
        order = await self.order_repo.get_by_id(query.order_id)

        # Handle not found
        order = self.handle_not_found(
            resource=order,
            resource_type="Order",
            resource_id=query.order_id,
            raise_exception=False  # Return None
        )

        if order:
            # Validate ownership
            self.validate_resource_ownership(
                resource_user_id=order.user_id,
                requesting_user_id=query.user_id,
                resource_type="Order",
                resource_id=query.order_id
            )

        return order
```

---

### Step 3: Implement Handle Method

**Simple Query:**

```python
async def handle(self, query: GetOrderQuery) -> Optional[OrderReadModel]:
    """Get single order"""
    return await self.order_repo.get_by_id(
        order_id=query.order_id,
        user_id=query.user_id
    )
```

**List Query with Pagination:**

```python
async def handle(self, query: GetOrdersByUserQuery) -> List[OrderReadModel]:
    """Get orders for user with pagination"""
    # Build filters
    filters = {"user_id": query.user_id}

    if query.status:
        filters["status"] = query.status

    # Fetch with pagination
    orders = await self.order_repo.get_many(
        filters=filters,
        limit=query.limit,
        offset=query.offset,
        sort_by=query.sort_by,
        sort_order=query.sort_order
    )

    return orders
```

**Aggregate Query:**

```python
async def handle(self, query: GetAccountStatisticsQuery) -> AccountStatistics:
    """Get account statistics"""
    # Fetch aggregated data
    stats = await self.account_repo.get_statistics(
        user_id=query.user_id,
        broker_id=query.broker_id
    )

    return AccountStatistics(
        total_accounts=stats.get('total_accounts', 0),
        total_balance=stats.get('total_balance', Decimal('0')),
        total_equity=stats.get('total_equity', Decimal('0')),
        active_accounts=stats.get('active_accounts', 0),
        disconnected_accounts=stats.get('disconnected_accounts', 0)
    )
```

---

### Step 4: Handle Authorization

**Pattern 1: Strict Ownership (Raises Exception)**

```python
async def handle(self, query: GetBrokerConnectionDetailsQuery) -> BrokerConnectionDetails:
    """Get connection details (strict authorization)"""
    conn = await self.conn_repo.get_by_id(query.broker_connection_id)

    # Raise exception if not found
    conn = self.handle_not_found(
        resource=conn,
        resource_type="Connection",
        resource_id=query.broker_connection_id
    )

    # Raise exception if not authorized
    if query.user_id:
        self.validate_resource_ownership(
            resource_user_id=conn.user_id,
            requesting_user_id=query.user_id,
            resource_type="connection"
        )

    return self._to_details(conn)
```

**Pattern 2: Optional Ownership (Returns None)**

```python
async def handle(self, query: GetAllUserBrokerConnectionsQuery) -> List[BrokerConnectionDetails]:
    """Get all connections (optional authorization)"""
    connections = await self.conn_repo.get_all_for_user(query.user_id)

    # Filter by ownership (if user_id provided)
    if query.user_id:
        connections = [
            conn for conn in connections
            if self.validate_optional_resource_ownership(
                resource_user_id=conn.user_id,
                requesting_user_id=query.user_id,
                resource_type="connection"
            )
        ]

    # Filter by broker if specified
    if query.broker_id:
        connections = [
            conn for conn in connections
            if conn.broker_id.lower() == query.broker_id.lower()
        ]

    return [self._to_details(conn) for conn in connections]
```

---

### Step 5: Return DTOs

Always return DTOs (Data Transfer Objects), not raw read models:

```python
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class BrokerConnectionDetails(BaseModel):
    """DTO for broker connection"""
    id: UUID
    user_id: UUID
    broker_id: str
    environment: str
    connected: bool
    api_endpoint: Optional[str]
    reauth_required: bool
    has_api_keys: bool
    has_oauth_tokens: bool
    token_expires_at: Optional[datetime]
    last_connection_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2

async def handle(self, query: GetBrokerConnectionDetailsQuery) -> BrokerConnectionDetails:
    """Return DTO, not raw read model"""
    conn = await self.conn_repo.get_by_id(query.broker_connection_id)

    # Convert to DTO
    return BrokerConnectionDetails(
        id=conn.id,
        user_id=conn.user_id,
        broker_id=conn.broker_id,
        environment=self.safe_getattr(
            obj=conn.environment,
            attr='value',
            default='paper'
        ),
        connected=conn.connected,
        api_endpoint=conn.api_endpoint,
        reauth_required=conn.reauth_required,
        has_api_keys=conn.has_api_keys,
        has_oauth_tokens=conn.has_oauth_tokens,
        token_expires_at=conn.token_expires_at,
        last_connection_status=self.safe_getattr(
            obj=conn.last_connection_status,
            attr='value',
            default='unknown'
        ),
        created_at=conn.created_at,
        updated_at=conn.updated_at
    )
```

---

## Code Examples from TradeCore

### Example 1: Simple Query Handler (No BaseQueryHandler)

**File:** `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_connection/query_handlers/connection_query_handlers.py`

```python
@query_handler(GetBrokerConnectionByUserBrokerEnvQuery)
class GetBrokerConnectionByUserBrokerEnvQueryHandler(BaseQueryHandler[GetBrokerConnectionByUserBrokerEnvQuery, Optional[BrokerConnectionDetails]]):
    """Handler for finding connection by parameters"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.conn_repo = deps.broker_conn_read_repo

    async def handle(self, query: GetBrokerConnectionByUserBrokerEnvQuery) -> BrokerConnectionDetails | None:
        """Find broker connection"""
        connections = await self.conn_repo.get_all_for_user(query.user_id)

        for conn in connections:
            if (conn.broker_id.lower() == query.broker_id.lower() and
                    conn.environment.lower() == query.environment.lower()):
                return BrokerConnectionDetails(
                    id=conn.id,
                    user_id=conn.user_id,
                    broker_id=conn.broker_id,
                    environment=conn.environment.value if hasattr(conn.environment, 'value') else conn.environment,
                    connected=conn.connected,
                    api_endpoint=conn.api_endpoint,
                    reauth_required=conn.reauth_required,
                    has_api_keys=conn.has_api_keys,
                    has_oauth_tokens=conn.has_oauth_tokens,
                    token_expires_at=conn.token_expires_at,
                    last_connection_status=conn.last_connection_status.value if hasattr(conn.last_connection_status,
                                                                                        'value') else conn.last_connection_status,
                    last_status_reason=conn.last_status_reason,
                    last_connected_at=conn.last_connected_at,
                    last_heartbeat_at=conn.last_heartbeat_at,
                    created_at=conn.created_at,
                    updated_at=conn.updated_at,
                    metadata=conn.metadata or {},
                    status=conn.last_connection_status,
                    connection_instance_id=conn.connection_instance_id,
                    disconnected_at=conn.disconnected_at,
                    grace_period_ends_at=conn.grace_period_ends_at
                )

        return None
```

**Key Patterns:**
- Inherits from `BaseQueryHandler`
- Generic types specified
- Returns `Optional[DTO]`
- Safe enum handling with `hasattr`

---

### Example 2: Handler with Authorization

```python
@readonly_query(GetBrokerConnectionDetailsQuery)
class GetBrokerConnectionDetailsQueryHandler(BaseQueryHandler[GetBrokerConnectionDetailsQuery, BrokerConnectionDetails]):
    """Handler for getting broker connection details"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.conn_repo = deps.broker_conn_read_repo

    async def handle(self, query: GetBrokerConnectionDetailsQuery) -> BrokerConnectionDetails:
        """Get connection details"""
        conn = await self.conn_repo.get_by_id(query.broker_connection_id)

        # Raise exception if not found
        conn = self.handle_not_found(
            resource=conn,
            resource_type="Connection",
            resource_id=query.broker_connection_id
        )

        # Validate ownership (raises exception if unauthorized)
        if query.user_id:
            self.validate_resource_ownership(
                resource_user_id=conn.user_id,
                requesting_user_id=query.user_id,
                resource_type="connection"
            )

        return BrokerConnectionDetails(
            id=conn.id,
            user_id=conn.user_id,
            broker_id=conn.broker_id,
            environment=conn.environment.value if hasattr(conn.environment, 'value') else conn.environment,
            connected=conn.connected,
            api_endpoint=conn.api_endpoint,
            reauth_required=conn.reauth_required,
            has_api_keys=conn.has_api_keys,
            has_oauth_tokens=conn.has_oauth_tokens,
            token_expires_at=conn.token_expires_at,
            last_connection_status=conn.last_connection_status.value if hasattr(conn.last_connection_status,
                                                                                'value') else conn.last_connection_status,
            last_status_reason=conn.last_status_reason,
            last_connected_at=conn.last_connected_at,
            last_heartbeat_at=conn.last_heartbeat_at,
            created_at=conn.created_at,
            updated_at=conn.updated_at,
            metadata=conn.metadata or {},
            status=conn.last_connection_status,
            connection_instance_id=conn.connection_instance_id,
            disconnected_at=conn.disconnected_at,
            grace_period_ends_at=conn.grace_period_ends_at
        )
```

**Key Patterns:**
- `@readonly_query` decorator
- `handle_not_found()` with `raise_exception=True`
- `validate_resource_ownership()` for strict auth
- DTO conversion with safe enum access

---

### Example 3: List Query with Filtering

**Query Definition:**

```python
class GetAllUserBrokerConnectionsQuery(Query):
    """
    Get all broker connections for a user.

    CRITICAL FIX (Nov 8, 2025): Changed include_disconnected default from True to False
    to prevent disconnected connections from appearing in UI after navigation.
    """
    user_id: UUID
    include_disconnected: bool = False  # FIXED: Changed from True
    broker_id: Optional[str] = None  # Filter by specific broker
```

**Handler Implementation:**

```python
@query_handler(GetAllUserBrokerConnectionsQuery)
class GetAllUserBrokerConnectionsQueryHandler(BaseQueryHandler[GetAllUserBrokerConnectionsQuery, List[BrokerConnectionDetails]]):
    """Handler for getting all user connections"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.conn_repo = deps.broker_conn_read_repo

    async def handle(self, query: GetAllUserBrokerConnectionsQuery) -> List[BrokerConnectionDetails]:
        """Get all connections for user"""
        # Fetch all connections
        connections = await self.conn_repo.get_all_for_user(query.user_id)

        # Filter disconnected (based on query parameter)
        if not query.include_disconnected:
            connections = [
                conn for conn in connections
                if conn.connected and not conn.disconnected_at
            ]

        # Filter by broker if specified
        if query.broker_id:
            connections = [
                conn for conn in connections
                if conn.broker_id.lower() == query.broker_id.lower()
            ]

        # Convert to DTOs
        return [self._to_details(conn) for conn in connections]

    def _to_details(self, conn) -> BrokerConnectionDetails:
        """Convert read model to DTO"""
        return BrokerConnectionDetails(
            id=conn.id,
            user_id=conn.user_id,
            broker_id=conn.broker_id,
            environment=self.safe_getattr(
                obj=conn.environment,
                attr='value',
                default='paper'
            ),
            connected=conn.connected,
            # ... more fields
        )
```

**Key Patterns:**
- List return type `List[BrokerConnectionDetails]`
- Multiple filtering steps
- Helper method for DTO conversion
- `safe_getattr()` for enum handling

---

### Example 4: Service Query Handler (Cross-Domain)

**Query Definition:**

```python
class GetBrokerHealthServiceQuery(Query):
    """Query to check broker health via service"""
    user_id: UUID
    broker_connection_id: UUID
```

**Handler Implementation:**

```python
@query_handler(GetBrokerHealthServiceQuery)
class GetBrokerHealthServiceQueryHandler:
    """Handler for broker health service operations"""

    def __init__(self, deps: 'HandlerDependencies'):
        self.broker_monitoring_service = deps.broker_monitoring_service

    async def handle(self, query: GetBrokerHealthServiceQuery) -> HealthCheckResult:
        """Check broker health via service"""
        # Delegate to service (cross-domain operation)
        result = await self.broker_monitoring_service.check_broker_health(
            user_id=query.user_id,
            broker_connection_id=query.broker_connection_id
        )

        return HealthCheckResult(
            is_healthy=result.is_healthy,
            reason=result.reason,
            connection_status=result.connection_status,
            last_heartbeat=result.last_heartbeat,
            details=result.details
        )
```

**Key Patterns:**
- Service delegation for cross-domain operations
- No BaseQueryHandler (simple forwarding)
- DTO transformation

---

## Testing Strategies

### Unit Testing Query Handlers

```python
import pytest
from uuid import uuid4

@pytest.mark.asyncio
async def test_get_order_query_handler_success(mock_deps):
    """Test successful order retrieval"""
    # Arrange
    handler = GetOrderQueryHandler(mock_deps)
    order_id = uuid4()
    user_id = uuid4()

    mock_order = OrderReadModel(
        id=order_id,
        user_id=user_id,
        symbol="AAPL",
        status="pending"
    )
    mock_deps.order_read_repo.get_by_id = AsyncMock(return_value=mock_order)

    query = GetOrderQuery(order_id=order_id, user_id=user_id)

    # Act
    result = await handler.handle(query)

    # Assert
    assert result is not None
    assert result.id == order_id
    assert result.user_id == user_id

@pytest.mark.asyncio
async def test_get_order_query_handler_not_found(mock_deps):
    """Test order not found"""
    handler = GetOrderQueryHandler(mock_deps)
    mock_deps.order_read_repo.get_by_id = AsyncMock(return_value=None)

    query = GetOrderQuery(order_id=uuid4(), user_id=uuid4())

    # Should return None (not raise exception)
    result = await handler.handle(query)
    assert result is None

@pytest.mark.asyncio
async def test_get_order_query_handler_authorization_error(mock_deps):
    """Test authorization failure"""
    handler = GetOrderQueryHandler(mock_deps)
    order_id = uuid4()
    owner_id = uuid4()
    attacker_id = uuid4()  # Different user!

    mock_order = OrderReadModel(
        id=order_id,
        user_id=owner_id,  # Owned by different user
        symbol="AAPL",
        status="pending"
    )
    mock_deps.order_read_repo.get_by_id = AsyncMock(return_value=mock_order)

    query = GetOrderQuery(order_id=order_id, user_id=attacker_id)

    # Should raise PermissionError
    with pytest.raises(PermissionError):
        await handler.handle(query)
```

### Integration Testing

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_orders_integration(test_db, query_bus):
    """Test order query with real database"""
    # Create test orders
    await test_db.execute(
        """
        INSERT INTO orders (id, user_id, symbol, status)
        VALUES ($1, $2, 'AAPL', 'pending'),
               ($2, $2, 'TSLA', 'filled')
        """,
        uuid4(), test_user_id
    )

    # Query orders
    query = GetOrdersByUserQuery(
        user_id=test_user_id,
        status="pending",
        limit=10
    )

    results = await query_bus.query(query)

    # Verify
    assert len(results) == 1
    assert results[0].symbol == "AAPL"
    assert results[0].status == "pending"
```

---

## Performance Tips

### 1. Use Caching for Hot Paths

```python
from app.infra.cqrs.decorators import cached_query_handler

@cached_query_handler(GetBrokerConnectionDetailsQuery, ttl_seconds=60)
class GetBrokerConnectionDetailsQueryHandler(BaseQueryHandler):
    """Handler with caching"""

    async def handle(self, query: GetBrokerConnectionDetailsQuery) -> BrokerConnectionDetails:
        # Result cached for 60 seconds
        conn = await self.conn_repo.get_by_id(query.broker_connection_id)
        return self._to_details(conn)
```

### 2. Optimize Database Queries

```python
# ❌ BAD - N+1 query problem
async def handle(self, query: GetOrdersWithAccountsQuery):
    orders = await self.order_repo.get_many(user_id=query.user_id)

    for order in orders:
        # N queries!
        order.account = await self.account_repo.get_by_id(order.account_id)

# ✅ GOOD - Single query with join
async def handle(self, query: GetOrdersWithAccountsQuery):
    # Single query with JOIN
    orders = await self.order_repo.get_many_with_accounts(
        user_id=query.user_id
    )
```

### 3. Use Pagination

```python
# ✅ GOOD - Always use pagination for lists
async def handle(self, query: GetOrdersByUserQuery) -> List[OrderReadModel]:
    return await self.order_repo.get_many(
        user_id=query.user_id,
        limit=query.limit,  # Max 1000
        offset=query.offset
    )
```

### 4. Index Read Models

```sql
-- Create indexes for common query patterns
CREATE INDEX idx_orders_user_id_status ON orders(user_id, status);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX idx_broker_connections_user_broker ON broker_connections(user_id, broker_id);
```

---

## Common Mistakes

### Mistake 1: Mutating State in Query Handler

```python
# ❌ WRONG - Mutating state!
async def handle(self, query: GetOrderQuery):
    order = await self.order_repo.get_by_id(query.order_id)

    # NO! Queries are READ-ONLY
    order.last_viewed_at = datetime.now(UTC)
    await self.order_repo.update(order)

    return order

# ✅ CORRECT - Read-only
async def handle(self, query: GetOrderQuery):
    order = await self.order_repo.get_by_id(query.order_id)
    return order
```

### Mistake 2: Not Validating Authorization

```python
# ❌ WRONG - No authorization check!
async def handle(self, query: GetOrderQuery):
    # Anyone can read any order!
    return await self.order_repo.get_by_id(query.order_id)

# ✅ CORRECT - Validate ownership
async def handle(self, query: GetOrderQuery):
    order = await self.order_repo.get_by_id(query.order_id)

    if order:
        self.validate_resource_ownership(
            resource_user_id=order.user_id,
            requesting_user_id=query.user_id,
            resource_type="Order"
        )

    return order
```

### Mistake 3: Returning Raw Read Models

```python
# ❌ WRONG - Exposing internal read model
async def handle(self, query: GetOrderQuery):
    # Returns internal read model!
    return await self.order_repo.get_by_id(query.order_id)

# ✅ CORRECT - Return DTO
async def handle(self, query: GetOrderQuery):
    order = await self.order_repo.get_by_id(query.order_id)

    # Convert to DTO
    return OrderDetails(
        id=order.id,
        symbol=order.symbol,
        status=order.status.value,  # Enum to string
        created_at=order.created_at
    )
```

### Mistake 4: No Pagination

```python
# ❌ WRONG - Returns all records (unbounded!)
async def handle(self, query: GetOrdersByUserQuery):
    # Could return 100,000 orders!
    return await self.order_repo.get_many(user_id=query.user_id)

# ✅ CORRECT - Always paginate
async def handle(self, query: GetOrdersByUserQuery):
    return await self.order_repo.get_many(
        user_id=query.user_id,
        limit=query.limit,  # Max 1000
        offset=query.offset
    )
```

### Mistake 5: Using Aggregates for Queries

```python
# ❌ WRONG - Loading aggregate for query!
async def handle(self, query: GetOrderQuery):
    # Loads all events and replays! Slow!
    events = await self.event_store.get_events(
        aggregate_id=query.order_id,
        aggregate_type="order"
    )

    order = Order(id=query.order_id)
    for event in events:
        order._apply(event)

    return order

# ✅ CORRECT - Use read model
async def handle(self, query: GetOrderQuery):
    # Fast read from projection
    return await self.order_repo.get_by_id(query.order_id)
```

---

## Summary Checklist

When implementing a query handler:

- [ ] Define query as Pydantic `Query` class
- [ ] Use `@query_handler` or `@readonly_query` decorator
- [ ] Inherit from `BaseQueryHandler` if using utilities
- [ ] Implement `async def handle()` method
- [ ] Validate authorization with `validate_resource_ownership()`
- [ ] Handle not found with `handle_not_found()`
- [ ] Return DTO, not raw read model
- [ ] Support pagination for lists (`limit/offset`)
- [ ] Use caching for hot paths (`@cached_query_handler`)
- [ ] Write unit and integration tests
- [ ] Never mutate state (read-only!)
- [ ] Optimize database queries (avoid N+1)
- [ ] Use indexes for common filters
- [ ] Log errors and performance issues

---

## References

- **BaseQueryHandler**: `/Users/silvermpx/PycharmProjects/TradeCore/app/common/base/base_query_handler.py`
- **Connection Query Handlers**: `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_connection/query_handlers/connection_query_handlers.py`
- **Query Definitions**: `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_connection/queries.py`
- **Query Bus**: `/Users/silvermpx/PycharmProjects/TradeCore/app/infra/cqrs/query_bus.py`
- **BaseQueryHandler Guide**: `/Users/silvermpx/PycharmProjects/TradeCore/docs/BASE_QUERY_HANDLER_GUIDE.md`

---

**Next Steps:**
- Read [Command Handler Guide](COMMAND_HANDLER_GUIDE.md) for write side
- Read [Projector Guide](PROJECTOR_GUIDE.md) for event projections
- Review [CQRS Documentation](../cqrs.md) for architecture overview
