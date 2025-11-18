# Command Handler Implementation Guide

**TradeCore v0.5 - CQRS Write Side**
**Last Updated:** 2025-01-10
**Status:** Production Reference

---

## Table of Contents

1. [Overview](#overview)
2. [Purpose and When to Use](#purpose-and-when-to-use)
3. [Architecture](#architecture)
4. [Step-by-Step Implementation](#step-by-step-implementation)
5. [Code Examples from TradeCore](#code-examples-from-tradecore)
6. [Testing Strategies](#testing-strategies)
7. [Performance Tips](#performance-tips)
8. [Common Mistakes](#common-mistakes)

---

## Overview

Command handlers are the **write side** of TradeCore's CQRS architecture. They:
- Execute business logic via domain aggregates
- Emit domain events through event sourcing
- Coordinate with sagas for distributed transactions
- Ensure data consistency and concurrency control

### Key Principles

1. **One command, one handler** - Single Responsibility Principle
2. **Handlers orchestrate, aggregates contain logic** - Clean Architecture
3. **All state changes emit events** - Event Sourcing
4. **Handlers are stateless** - No instance state between calls
5. **Use BaseCommandHandler** - Provides event publishing infrastructure

---

## Purpose and When to Use

### When to Create a Command Handler

Create a command handler when you need to:
- ✅ **Mutate domain state** (create, update, delete)
- ✅ **Execute business logic** via aggregates
- ✅ **Emit domain events** for projectors and sagas
- ✅ **Coordinate distributed transactions** via sagas
- ✅ **Handle concurrency conflicts** with optimistic locking

### When NOT to Use Command Handlers

DON'T create command handlers for:
- ❌ **Read-only operations** - Use query handlers instead
- ❌ **Direct database writes** - Use aggregates and events
- ❌ **Infrastructure operations** - Use services
- ❌ **Reporting** - Use projectors and read models

---

## Architecture

### Command Flow

```
API Request
    ↓
Command (dataclass with validation)
    ↓
Command Bus (routes to handler)
    ↓
Command Handler (orchestration)
    ↓
Load Aggregate (from event store or read model)
    ↓
Execute Business Logic (aggregate method)
    ↓
Aggregate Emits Events (uncommitted)
    ↓
Handler Publishes Events (commit to event store + transport)
    ↓
Projectors Update Read Models (eventual consistency)
    ↓
Sagas React to Events (distributed orchestration)
```

### Handler Structure

```python
@command_handler(CreateOrderCommand)
class CreateOrderHandler(BaseCommandHandler):
    """
    Handle CreateOrderCommand

    1. Validate command
    2. Load/create aggregate
    3. Execute business logic
    4. Publish events
    """

    def __init__(self, deps: HandlerDependencies):
        # Initialize base with event infrastructure
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="order_events",  # Where events go
            event_store=deps.event_store
        )
        # Store additional dependencies
        self.query_bus = deps.query_bus
        self.command_bus = deps.command_bus

    async def handle(self, command: CreateOrderCommand) -> UUID:
        # 1. Create aggregate (new)
        aggregate = Order.create(...)

        # 2. Publish events (automatic from aggregate.uncommitted_events)
        await self.publish_and_commit_events(
            aggregate=aggregate,
            aggregate_type="order",
            expected_version=None,  # New aggregate
            saga_id=command.saga_id
        )

        return aggregate.id
```

---

## Step-by-Step Implementation

### Step 1: Define Command (commands.py)

Commands are **immutable data classes** with validation:

```python
from dataclasses import dataclass
from uuid import UUID
from decimal import Decimal
from typing import Optional

@dataclass
class CreateOrderCommand:
    """
    Create new order

    Commands use dataclasses (NOT Pydantic BaseModel).
    All fields should be immutable types.
    """
    user_id: UUID
    automation_id: UUID
    symbol: str
    side: str  # "buy" or "sell"
    quantity: Decimal
    order_type: str  # "market", "limit", "stop"

    # Optional fields
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None

    # Saga coordination
    saga_id: Optional[UUID] = None

    def __post_init__(self):
        """Validate command after initialization"""
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")

        if self.order_type == "limit" and not self.limit_price:
            raise ValueError("Limit orders require limit_price")
```

**Key Points:**
- Use `@dataclass` (NOT Pydantic)
- All fields immutable (no setters)
- Validate in `__post_init__`
- Include `saga_id` for distributed transactions

---

### Step 2: Create Handler Class (command_handlers/)

Handlers inherit from `BaseCommandHandler`:

```python
import logging
from uuid import UUID, uuid4
from typing import TYPE_CHECKING

from app.common.base.base_command_handler import BaseCommandHandler
from app.infra.cqrs.decorators import command_handler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("tradecore.order.command_handlers.lifecycle")

@command_handler(CreateOrderCommand)
class CreateOrderHandler(BaseCommandHandler):
    """
    Handle CreateOrderCommand

    Creates new order aggregate and emits OrderCreatedEvent.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        # Store dependencies
        self.event_bus = deps.event_bus
        self.event_store = deps.event_store
        self.query_bus = deps.query_bus

        # Initialize base handler
        super().__init__(
            event_bus=self.event_bus,
            transport_topic="order_events",
            event_store=self.event_store
        )

    async def handle(self, command: CreateOrderCommand) -> UUID:
        """
        Create new order

        Returns:
            order_id: UUID of created order
        """
        log.info(f"Creating order for {command.symbol}")

        # Business logic implementation...
```

**Key Points:**
- Use `@command_handler(CommandClass)` decorator
- Inherit from `BaseCommandHandler`
- Initialize base with `event_bus`, `transport_topic`, `event_store`
- Store additional dependencies (query_bus, command_bus, repos)

---

### Step 3: Load or Create Aggregate

**For NEW aggregates:**

```python
async def handle(self, command: CreateOrderCommand) -> UUID:
    """Create new order"""

    # Validate prerequisites via query bus
    automation = await self.query_bus.query(
        GetAutomationQuery(automation_id=command.automation_id)
    )

    if not automation.is_active:
        raise AutomationInactiveError("Automation must be active")

    # Create aggregate (calls factory method)
    order = Order.create(
        user_id=command.user_id,
        automation_id=command.automation_id,
        symbol=command.symbol,
        side=command.side,
        quantity=command.quantity,
        order_type=command.order_type,
        limit_price=command.limit_price
    )

    # Aggregate has uncommitted events now
    log.info(f"Order created: {order.id}")

    # Publish events
    await self.publish_and_commit_events(
        aggregate=order,
        aggregate_type="order",
        expected_version=None,  # New aggregate (no version)
        saga_id=command.saga_id
    )

    return order.id
```

**For EXISTING aggregates (update/delete):**

```python
async def handle(self, command: CancelOrderCommand) -> None:
    """Cancel existing order"""

    # Load aggregate from event store
    order = await self._load_aggregate(command.order_id)

    # Store ORIGINAL version BEFORE mutations
    original_version = order.version

    # Validate ownership
    if order.user_id != command.user_id:
        raise PermissionError("Not your order")

    # Execute business logic (emits events)
    order.cancel(reason=command.reason)

    # Publish events with concurrency control
    await self.publish_and_commit_events(
        aggregate=order,
        aggregate_type="order",
        expected_version=original_version,  # For optimistic locking
        saga_id=command.saga_id
    )

async def _load_aggregate(self, order_id: UUID) -> Order:
    """Load order from event store"""
    events = await self.event_store.get_events(
        aggregate_id=order_id,
        aggregate_type="order"
    )

    if not events:
        raise OrderNotFoundError(f"Order {order_id} not found")

    # Initialize aggregate
    order = Order(id=order_id, ...)  # Minimal initialization

    # Replay events to rebuild state
    from app.infra.event_bus.event_registry import EVENT_TYPE_TO_PYDANTIC_MODEL

    for envelope in events:
        event_class = EVENT_TYPE_TO_PYDANTIC_MODEL.get(envelope.event_type)
        if event_class:
            event = event_class(**envelope.event_data)
            order._apply(event)
            order.version = envelope.aggregate_version

    # Clear uncommitted events (just loaded from store)
    order.mark_events_committed()

    return order
```

---

### Step 4: Execute Business Logic

**IMPORTANT:** Business logic lives in **aggregates**, not handlers!

```python
# ❌ WRONG - Business logic in handler
async def handle(self, command: PlaceOrderCommand):
    order = await self._load_aggregate(command.order_id)

    # DON'T DO THIS IN HANDLER!
    if order.status != OrderStatus.PENDING:
        raise InvalidOrderStateError("Can only place pending orders")

    order.status = OrderStatus.PLACED  # Direct mutation - NO!
    order.placed_at = datetime.now(UTC)

# ✅ CORRECT - Business logic in aggregate
async def handle(self, command: PlaceOrderCommand):
    order = await self._load_aggregate(command.order_id)

    # Delegate to aggregate method
    order.place(
        broker_order_id=command.broker_order_id,
        placed_at=command.placed_at
    )

    # Aggregate method handles validation and emits events
```

**Aggregate Implementation:**

```python
# app/order/aggregate.py
class Order(Aggregate):
    def place(
        self,
        broker_order_id: str,
        placed_at: datetime
    ) -> None:
        """
        Place order with broker

        Business Rules:
        - Order must be in PENDING state
        - Must have valid broker_order_id
        """
        # Validate state
        if self.status != OrderStatus.PENDING:
            raise InvalidOrderStateError(
                f"Cannot place order in {self.status} state"
            )

        # Emit event (applies via _apply)
        event = OrderPlacedEvent(
            order_id=self.id,
            broker_order_id=broker_order_id,
            placed_at=placed_at
        )
        self.apply(event)

    def _on_order_placed_event(self, event: OrderPlacedEvent) -> None:
        """Apply event to state"""
        self.status = OrderStatus.PLACED
        self.broker_order_id = event.broker_order_id
        self.placed_at = event.placed_at
```

---

### Step 5: Handle Concurrency Conflicts

Use **optimistic locking** to prevent concurrent modifications:

```python
async def handle(self, command: UpdateOrderCommand) -> None:
    """Update order with retry on conflict"""

    max_retries = 3
    retry_delay = 0.1

    for attempt in range(max_retries):
        try:
            # Load aggregate
            order = await self._load_aggregate(command.order_id)
            original_version = order.version

            # Execute business logic
            order.update(
                limit_price=command.limit_price,
                stop_price=command.stop_price
            )

            # Publish with version check
            await self.publish_and_commit_events(
                aggregate=order,
                aggregate_type="order",
                expected_version=original_version,
                saga_id=command.saga_id
            )

            # Success - break retry loop
            return

        except ConcurrencyError as e:
            if attempt < max_retries - 1:
                log.warning(
                    f"Concurrency conflict on attempt {attempt + 1}: {e}"
                )
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                log.error(f"Failed after {max_retries} attempts")
                raise
```

---

### Step 6: Publish Events

Use `publish_and_commit_events` from `BaseCommandHandler`:

```python
await self.publish_and_commit_events(
    aggregate=order,
    aggregate_type="order",
    expected_version=original_version,  # For optimistic locking
    causation_id=uuid4(),  # Optional: link events
    saga_id=command.saga_id,  # Optional: saga coordination
    metadata={
        "command_type": "CancelOrderCommand",
        "reason": command.reason,
        "user_id": str(command.user_id)
    }
)
```

**What happens:**
1. Events saved to **KurrentDB** (event store) with version check
2. Events published to **Redpanda** (transport) for projectors/sagas
3. Saga context added to metadata
4. Aggregate version incremented
5. Uncommitted events cleared

---

## Code Examples from TradeCore

### Example 1: Simple Create Handler (Automation)

**File:** `/Users/silvermpx/PycharmProjects/TradeCore/app/automation/command_handlers/lifecycle_handlers.py`

```python
@command_handler(CreateAutomationCommand)
class CreateAutomationHandler(BaseCommandHandler):
    """
    Handle CreateAutomationCommand

    Creates new automation with derivatives support.
    Triggers AutomationCreatedEvent (SYNC Priority 2).
    """

    def __init__(self, deps: 'HandlerDependencies'):
        self.event_bus = deps.event_bus
        self.event_store = deps.event_store

        super().__init__(
            event_bus=self.event_bus,
            transport_topic="automation_events",
            event_store=self.event_store
        )

    async def handle(self, command: CreateAutomationCommand) -> Dict[str, Any]:
        """
        Create new automation.

        Returns:
            Dict with automation_id, webhook_url, webhook_token, status
        """
        log.info(f"Creating automation '{command.name}' for user {command.user_id}")

        # Create automation aggregate
        automation = Automation.create(
            user_id=command.user_id,
            name=command.name,
            symbol=command.symbol,
            position_sizing=command.position_sizing,
            account_ids=command.account_ids,
            asset_type=command.asset_type,
            option_details=command.option_details,
            future_details=command.future_details,
            side_preference=command.side_preference,
            stop_loss=command.stop_loss,
            take_profit=command.take_profit,
            order_preferences=command.order_preferences,
            auto_submit=command.auto_submit,
            metadata=command.metadata
        )

        # Save automation (triggers AutomationCreatedEvent)
        await self.publish_and_commit_events(
            aggregate=automation,
            aggregate_type="automation",
            expected_version=None
        )

        log.info(f"Automation created: {automation.id}")

        return {
            "automation_id": str(automation.id),
            "webhook_url": automation.webhook_config.url,
            "webhook_token": automation.webhook_config.token,
            "status": automation.status.value
        }
```

**Key Patterns:**
- Factory method (`Automation.create()`) returns aggregate
- No version (new aggregate)
- Returns structured response
- Simple, linear flow

---

### Example 2: Update Handler with Concurrency (Automation)

```python
@command_handler(UpdateAutomationCommand)
class UpdateAutomationHandler(BaseCommandHandler):
    """Handle automation updates"""

    def __init__(self, deps: 'HandlerDependencies'):
        self.event_bus = deps.event_bus
        self.event_store = deps.event_store

        super().__init__(
            event_bus=self.event_bus,
            transport_topic="automation_events",
            event_store=self.event_store
        )

    async def handle(self, command: UpdateAutomationCommand) -> Dict[str, Any]:
        """Update automation configuration"""
        log.info(f"Updating automation {command.automation_id}")

        # Load automation
        automation = await self._load_aggregate(command.automation_id)

        # Verify ownership
        if automation.user_id != command.user_id:
            raise PermissionError(
                f"User {command.user_id} does not own automation {command.automation_id}"
            )

        # Update configuration
        automation.update_config(
            name=command.name,
            position_sizing=command.position_sizing,
            stop_loss=command.stop_loss,
            take_profit=command.take_profit,
            order_preferences=command.order_preferences,
            side_preference=command.side_preference,
            auto_submit=command.auto_submit,
            asset_type=command.asset_type,
            option_details=command.option_details,
            future_details=command.future_details
        )

        # Save automation (triggers AutomationUpdatedEvent)
        await self.publish_and_commit_events(
            aggregate=automation,
            aggregate_type="automation"
        )

        log.info(f"Automation updated: {automation.id}")

        return {
            "automation_id": str(automation.id),
            "status": automation.status.value
        }
```

**Key Patterns:**
- Load aggregate from event store
- Authorization check before mutation
- Delegate logic to aggregate method
- Version automatically incremented

---

### Example 3: Complex Multi-Phase Handler (Broker Connection)

**File:** `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_connection/command_handlers/connection_handlers.py`

```python
@command_handler(InitiateBrokerConnectionCommand)
class InitiateBrokerConnectionHandler(BaseCommandHandler):
    """
    Handle InitiateBrokerConnectionCommand.

    Two-phase process:
    Phase 1: Create/update connection
    Phase 2: Handle authentication (OAuth/API Keys)
    """

    def __init__(self, deps: 'HandlerDependencies'):
        self.event_bus = deps.event_bus
        self.event_store = deps.event_store
        self.query_bus = deps.query_bus
        self.command_bus = deps.command_bus

        # Distributed lock for race conditions
        lock_config = DistributedLockConfig(
            namespace="broker_connection",
            ttl_seconds=60,
            max_wait_ms=30000,
            strategy="wait_with_timeout"
        )
        self.distributed_lock = DistributedLock(lock_config)

        super().__init__(
            event_bus=self.event_bus,
            transport_topic="broker_connection_events",
            event_store=self.event_store
        )

    async def handle(self, command: InitiateBrokerConnectionCommand) -> UUID:
        """
        Initiate broker connection.

        Returns:
            broker_connection_id
        """
        broker_key = f"{command.broker_id}:{command.environment or 'paper'}"
        lock_key = f"{command.user_id}:{command.broker_id}:{command.environment or 'paper'}"

        log.info(f"Initiating broker connection for {broker_key}")

        # Acquire distributed lock
        lock_info = await self.distributed_lock.acquire(
            resource_id=lock_key,
            ttl_seconds=60,
            timeout_ms=30000
        )

        try:
            # Phase 1: Create/Update Connection
            broker_connection_id = await self._phase1_create_connection(command)

            # Phase 2: Handle Authentication
            await self._phase2_handle_authentication(command, broker_connection_id)

            return broker_connection_id

        finally:
            # Release lock
            if lock_info:
                await self.distributed_lock.release(lock_key)

    async def _phase1_create_connection(self, command: InitiateBrokerConnectionCommand) -> UUID:
        """Phase 1: Create or update connection"""
        # Check for existing connection
        result = await self.query_bus.query(EnsureSingleConnectionQuery(
            user_id=command.user_id,
            broker_id=command.broker_id,
            environment=command.environment or "paper"
        ))

        existing_id = result.connection_id if result and result.exists else None

        if existing_id:
            # Load and update existing
            aggregate = await _load_and_prepare_aggregate(
                existing_id, command.user_id,
                self.query_bus, self.event_store
            )
            original_version = aggregate.version

            # Reset if disconnected
            if aggregate.state.status == BrokerConnectionStatusEnum.DISCONNECTED:
                aggregate.reset_connection_status(command.user_id)
        else:
            # Create new
            broker_connection_id = uuid4()
            aggregate = BrokerConnectionAggregate(broker_connection_id)

            aggregate.initiate(
                command.user_id,
                command.broker_id,
                command.environment or "paper",
                command.api_endpoint_override
            )
            original_version = None

        # Save with retry on conflict
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self.publish_and_commit_events(
                    aggregate=aggregate,
                    aggregate_type="broker_connection",
                    expected_version=original_version,
                    saga_id=command.saga_id,
                    metadata={
                        "command_type": "InitiateBrokerConnectionCommand",
                        "phase": "connection_created",
                        "attempt": attempt + 1
                    }
                )
                break  # Success
            except ConcurrencyError:
                if attempt < max_retries - 1:
                    # Reload and retry
                    aggregate = await _load_and_prepare_aggregate(...)
                    original_version = aggregate.version
                else:
                    raise

        return aggregate.id

    async def _phase2_handle_authentication(
        self,
        command: InitiateBrokerConnectionCommand,
        broker_connection_id: UUID
    ) -> None:
        """Phase 2: Handle authentication"""
        # Determine authentication method
        if command.broker_id.lower() == "virtual":
            await self._start_oauth_flow(broker_connection_id, command.user_id, command.saga_id)
        elif command.auth_method == 'api_key':
            await self._attempt_api_connection(broker_connection_id, command.user_id, ...)
        # ... more authentication logic
```

**Key Patterns:**
- Multi-phase orchestration
- Distributed locking for race conditions
- Retry logic with exponential backoff
- Query bus for reads, command bus for writes
- Saga coordination via `saga_id`

---

### Example 4: Batch Operation Handler (Broker Account)

**File:** `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_account/command_handlers/batch_handlers.py`

```python
@command_handler(RefreshAllAccountsCommand)
class RefreshAllAccountsHandler(BaseCommandHandler):
    """
    Handle batch refresh of multiple accounts.
    Orchestrates multiple sub-commands.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="broker_account_events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus
        self.command_bus = deps.command_bus

    async def handle(self, command: RefreshAllAccountsCommand) -> Dict[str, Any]:
        """Refresh all accounts for user or connection"""
        log.info(f"Handling RefreshAllAccounts for user {command.user_id}")

        # Get accounts via query bus
        if command.broker_connection_id:
            query = GetAccountsByConnectionQuery(
                broker_connection_id=command.broker_connection_id,
                include_deleted=False
            )
        else:
            query = GetAccountsByUserQuery(
                user_id=command.user_id,
                include_deleted=False
            )

        accounts = await self.query_bus.query(query)

        # Filter out recently synced (unless forced)
        if not command.force_refresh:
            accounts = [
                acc for acc in accounts
                if not acc.last_synced_at or
                (datetime.now(timezone.utc) - acc.last_synced_at).total_seconds() > 300
            ]

        log.info(f"Found {len(accounts)} accounts to refresh")

        results = {
            'total': len(accounts),
            'refreshed': 0,
            'failed': 0,
            'errors': []
        }

        # Refresh each account via command bus
        for account in accounts:
            try:
                refresh_command = RefreshAccountDataFromBrokerCommand(
                    account_aggregate_id=account.id,
                    user_id=command.user_id,
                    saga_id=command.saga_id
                )

                await self.command_bus.send(refresh_command)
                results['refreshed'] += 1

            except Exception as e:
                log.error(f"Failed to refresh account {account.id}: {e}")
                results['failed'] += 1
                results['errors'].append({
                    'account_id': str(account.id),
                    'error': str(e)
                })

        # Publish completion event
        if command.saga_id:
            await self.event_bus.publish_stream("broker_account_events", {
                "event_id": str(uuid4()),
                "event_type": "AllAccountsRefreshCompleted",
                "saga_id": str(command.saga_id),
                "user_id": str(command.user_id),
                "results": results,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        return results
```

**Key Patterns:**
- Query bus for reads
- Command bus for sub-commands
- Error aggregation for batch operations
- Saga completion event
- Structured result reporting

---

## Testing Strategies

### Unit Testing Command Handlers

```python
import pytest
from uuid import uuid4
from decimal import Decimal

@pytest.mark.asyncio
async def test_create_order_handler_success(mock_deps):
    """Test successful order creation"""
    # Arrange
    handler = CreateOrderHandler(mock_deps)
    command = CreateOrderCommand(
        user_id=uuid4(),
        automation_id=uuid4(),
        symbol="AAPL",
        side="buy",
        quantity=Decimal("100"),
        order_type="market"
    )

    # Act
    order_id = await handler.handle(command)

    # Assert
    assert order_id is not None

    # Verify event published
    published_events = mock_deps.event_bus.published_events
    assert len(published_events) == 1
    assert published_events[0].event_type == "OrderCreatedEvent"

@pytest.mark.asyncio
async def test_create_order_handler_validation_error(mock_deps):
    """Test order creation with invalid quantity"""
    handler = CreateOrderHandler(mock_deps)

    # Invalid quantity
    with pytest.raises(ValueError, match="Quantity must be positive"):
        command = CreateOrderCommand(
            user_id=uuid4(),
            automation_id=uuid4(),
            symbol="AAPL",
            side="buy",
            quantity=Decimal("-10"),  # Invalid!
            order_type="market"
        )

@pytest.mark.asyncio
async def test_update_order_handler_concurrency_error(mock_deps):
    """Test concurrency handling"""
    handler = UpdateOrderHandler(mock_deps)

    # Mock concurrency error on first attempt
    mock_deps.event_store.save_events = AsyncMock(
        side_effect=[
            ConcurrencyError("Version conflict"),  # First attempt fails
            None  # Second attempt succeeds
        ]
    )

    command = UpdateOrderCommand(
        order_id=uuid4(),
        user_id=uuid4(),
        limit_price=Decimal("150.00")
    )

    # Should retry and succeed
    await handler.handle(command)

    # Verify two attempts
    assert mock_deps.event_store.save_events.call_count == 2
```

### Integration Testing

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_order_lifecycle_integration(test_db, event_store, command_bus):
    """Test complete order lifecycle"""
    # Create order
    create_cmd = CreateOrderCommand(
        user_id=test_user_id,
        automation_id=test_automation_id,
        symbol="AAPL",
        side="buy",
        quantity=Decimal("100"),
        order_type="market"
    )

    order_id = await command_bus.send(create_cmd)

    # Wait for projection
    await asyncio.sleep(0.5)

    # Verify order exists in read model
    order = await test_db.fetchrow(
        "SELECT * FROM orders WHERE id = $1",
        order_id
    )
    assert order is not None
    assert order['status'] == 'pending'

    # Place order
    place_cmd = PlaceOrderCommand(
        order_id=order_id,
        user_id=test_user_id,
        broker_order_id="BROKER-123"
    )

    await command_bus.send(place_cmd)
    await asyncio.sleep(0.5)

    # Verify order placed
    order = await test_db.fetchrow(
        "SELECT * FROM orders WHERE id = $1",
        order_id
    )
    assert order['status'] == 'placed'
    assert order['broker_order_id'] == 'BROKER-123'
```

---

## Performance Tips

### 1. Minimize Aggregate Loading

```python
# ❌ BAD - Loads aggregate twice
async def handle(self, command: UpdateOrderCommand):
    order = await self._load_aggregate(command.order_id)
    original_version = order.version

    # ... business logic ...

    order = await self._load_aggregate(command.order_id)  # Wasteful!
    await self.publish_and_commit_events(...)

# ✅ GOOD - Load once
async def handle(self, command: UpdateOrderCommand):
    order = await self._load_aggregate(command.order_id)
    original_version = order.version

    # ... business logic ...

    await self.publish_and_commit_events(
        aggregate=order,
        expected_version=original_version
    )
```

### 2. Batch Event Publishing

```python
# ✅ GOOD - All events published in one batch
order.place(broker_order_id="BROKER-123")
order.add_fill(quantity=Decimal("50"), price=Decimal("150.00"))
order.add_fill(quantity=Decimal("50"), price=Decimal("150.50"))

# All uncommitted events published together
await self.publish_and_commit_events(aggregate=order, ...)
```

### 3. Use Query Bus for Reads

```python
# ❌ BAD - Direct repository access
async def handle(self, command: CreateOrderCommand):
    automation = await self.automation_repo.get_by_id(command.automation_id)

# ✅ GOOD - Query bus (cached, consistent)
async def handle(self, command: CreateOrderCommand):
    automation = await self.query_bus.query(
        GetAutomationQuery(automation_id=command.automation_id)
    )
```

### 4. Optimize Event Replay

```python
# ✅ GOOD - Only load events once
async def _load_aggregate(self, order_id: UUID) -> Order:
    events = await self.event_store.get_events(
        aggregate_id=order_id,
        aggregate_type="order"
    )

    # Use snapshots for aggregates with many events
    snapshot = await self.event_store.get_snapshot(
        aggregate_id=order_id,
        aggregate_type="order"
    )

    if snapshot:
        order = Order.from_snapshot(snapshot)
        # Only replay events after snapshot
        events = [e for e in events if e.aggregate_version > snapshot.version]
    else:
        order = Order(id=order_id)

    for envelope in events:
        event = self._deserialize_event(envelope)
        order._apply(event)

    return order
```

---

## Common Mistakes

### Mistake 1: Business Logic in Handler

```python
# ❌ WRONG - Logic in handler
async def handle(self, command: CancelOrderCommand):
    order = await self._load_aggregate(command.order_id)

    # Business logic in handler - NO!
    if order.status not in [OrderStatus.PENDING, OrderStatus.PLACED]:
        raise InvalidOrderStateError("Cannot cancel")

    order.status = OrderStatus.CANCELLED
    order.cancelled_at = datetime.now(UTC)

# ✅ CORRECT - Logic in aggregate
async def handle(self, command: CancelOrderCommand):
    order = await self._load_aggregate(command.order_id)

    # Delegate to aggregate
    order.cancel(reason=command.reason)

    await self.publish_and_commit_events(...)
```

### Mistake 2: Forgetting Version Check

```python
# ❌ WRONG - No version check
async def handle(self, command: UpdateOrderCommand):
    order = await self._load_aggregate(command.order_id)
    order.update(limit_price=command.limit_price)

    # No expected_version - concurrency issues!
    await self.publish_and_commit_events(
        aggregate=order,
        aggregate_type="order"
    )

# ✅ CORRECT - Use original version
async def handle(self, command: UpdateOrderCommand):
    order = await self._load_aggregate(command.order_id)
    original_version = order.version  # BEFORE mutation

    order.update(limit_price=command.limit_price)

    await self.publish_and_commit_events(
        aggregate=order,
        aggregate_type="order",
        expected_version=original_version  # Optimistic locking
    )
```

### Mistake 3: Direct Database Writes

```python
# ❌ WRONG - Direct database write
async def handle(self, command: DeleteOrderCommand):
    await self.db.execute(
        "DELETE FROM orders WHERE id = $1",
        command.order_id
    )

# ✅ CORRECT - Event sourcing
async def handle(self, command: DeleteOrderCommand):
    order = await self._load_aggregate(command.order_id)

    # Emit event
    order.delete()

    await self.publish_and_commit_events(
        aggregate=order,
        aggregate_type="order"
    )

    # Projector handles database deletion
```

### Mistake 4: Not Handling Saga Context

```python
# ❌ WRONG - Ignoring saga_id
async def handle(self, command: CreateOrderCommand):
    order = Order.create(...)

    await self.publish_and_commit_events(
        aggregate=order,
        aggregate_type="order"
        # Missing saga_id!
    )

# ✅ CORRECT - Pass saga context
async def handle(self, command: CreateOrderCommand):
    order = Order.create(...)

    await self.publish_and_commit_events(
        aggregate=order,
        aggregate_type="order",
        saga_id=command.saga_id  # For saga coordination
    )
```

### Mistake 5: Synchronous I/O

```python
# ❌ WRONG - Blocking call
async def handle(self, command: CreateOrderCommand):
    # Blocks event loop!
    automation = self.automation_repo.get_by_id_sync(command.automation_id)

# ✅ CORRECT - Async all the way
async def handle(self, command: CreateOrderCommand):
    automation = await self.query_bus.query(
        GetAutomationQuery(automation_id=command.automation_id)
    )
```

---

## Summary Checklist

When implementing a command handler:

- [ ] Define command as `@dataclass` with validation
- [ ] Create handler class with `@command_handler` decorator
- [ ] Inherit from `BaseCommandHandler`
- [ ] Initialize base with `event_bus`, `transport_topic`, `event_store`
- [ ] Load or create aggregate
- [ ] Store original version BEFORE mutations
- [ ] Delegate business logic to aggregate methods
- [ ] Handle concurrency with retry logic
- [ ] Publish events with `publish_and_commit_events`
- [ ] Include `saga_id` for saga coordination
- [ ] Write unit and integration tests
- [ ] Use query bus for reads, command bus for writes
- [ ] Keep handlers stateless (no instance variables)
- [ ] Log important operations
- [ ] Handle errors gracefully

---

## References

- **BaseCommandHandler**: `/Users/silvermpx/PycharmProjects/TradeCore/app/common/base/base_command_handler.py`
- **Automation Handlers**: `/Users/silvermpx/PycharmProjects/TradeCore/app/automation/command_handlers/lifecycle_handlers.py`
- **Broker Connection Handlers**: `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_connection/command_handlers/connection_handlers.py`
- **Batch Handlers**: `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_account/command_handlers/batch_handlers.py`
- **Event Store**: `/Users/silvermpx/PycharmProjects/TradeCore/app/infra/event_store/kurrentdb_event_store.py`
- **Command Bus**: `/Users/silvermpx/PycharmProjects/TradeCore/app/infra/cqrs/command_bus.py`

---

**Next Steps:**
- Read [Query Handler Guide](QUERY_HANDLER_GUIDE.md) for read side
- Read [Projector Guide](PROJECTOR_GUIDE.md) for event projections
- Review [CQRS Documentation](../cqrs.md) for architecture overview
