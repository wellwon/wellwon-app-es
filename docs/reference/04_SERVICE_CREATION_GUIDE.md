# Application Service Creation Guide

**TradeCore v0.6.0**
**Last Updated**: 2025-01-10
**Audience**: Backend developers implementing new services

---

## Table of Contents

1. [What is an Application Service?](#what-is-an-application-service)
2. [Service vs Domain Logic](#service-vs-domain-logic)
3. [Step-by-Step Service Creation](#step-by-step-service-creation)
4. [Service Patterns](#service-patterns)
5. [Broker Streaming Architecture (2025)](#broker-streaming-architecture-2025)
6. [Code Examples](#code-examples)
7. [Testing Services](#testing-services)
8. [Common Mistakes](#common-mistakes)
9. [Best Practices](#best-practices)

---

## What is an Application Service?

**Application Services** are the **orchestration layer** between the API and domain layers in TradeCore's Clean Architecture.

### Architecture Position

```
┌──────────────────────────────────────────┐
│  API Layer (FastAPI Routers)            │
│  - HTTP request/response handling        │
│  - Input validation (Pydantic)           │
│  - Authentication/Authorization          │
└──────────────────┬───────────────────────┘
                   │
                   ↓
┌──────────────────────────────────────────┐
│  Application Services (THIS LAYER)       │ ← WE ARE HERE
│  - Orchestration & coordination          │
│  - Cross-domain workflows                │
│  - CQRS dispatching                      │
│  - No business logic!                    │
└──────────────────┬───────────────────────┘
                   │
                   ↓
┌──────────────────────────────────────────┐
│  Domain Layer (Aggregates)               │
│  - Business rules & validation           │
│  - Domain events                         │
│  - Aggregate state management            │
└──────────────────────────────────────────┘
```

### Key Characteristics

**Services DO:**
- Coordinate multiple domain operations
- Dispatch commands via CommandBus
- Query data via QueryBus
- Manage infrastructure (OAuth, WebSockets, file uploads)
- Handle cross-cutting concerns (logging, monitoring)

**Services DON'T:**
- Contain business rules (that's domain logic!)
- Validate business invariants (aggregates do that)
- Manipulate domain state directly (use commands)
- Make decisions about domain state transitions

---

## Service vs Domain Logic

### Decision Matrix

| Concern | Domain Logic | Service Logic |
|---------|-------------|---------------|
| Order price validation | ✅ Aggregate | ❌ Not service |
| Position P&L calculation | ✅ Aggregate | ❌ Not service |
| OAuth token exchange | ❌ Not domain | ✅ Service |
| Multi-step account setup | ❌ Not domain | ✅ Service (Saga) |
| Broker WebSocket lifecycle | ❌ Not domain | ✅ Service |
| Market data normalization | ❌ Not domain | ✅ Handler |
| Send 3 commands in sequence | ❌ Not domain | ✅ Service |

### Example: Wrong vs Right

**❌ WRONG - Business logic in service:**
```python
# app/services/order_service.py
class OrderService:
    async def place_order(self, order_data: dict):
        # ❌ BAD: Validating business rules in service
        if order_data['price'] < 0:
            raise ValueError("Price must be positive")

        # ❌ BAD: Calculating values in service
        commission = order_data['quantity'] * 0.005

        # ❌ BAD: Directly manipulating state
        order = Order(**order_data)
        order.status = "pending"
        await self.db.save(order)
```

**✅ RIGHT - Business logic in domain:**
```python
# app/services/order_service.py
class OrderService:
    async def place_order(self, order_data: dict):
        # ✅ CORRECT: Service only orchestrates
        command = PlaceOrderCommand(**order_data)
        await self.command_bus.send(command)

# app/order/aggregate.py
class OrderAggregate:
    def place_order(self, price, quantity, broker_id):
        # ✅ CORRECT: Business logic in aggregate
        if price <= 0:
            raise InvalidPriceError("Price must be positive")

        commission = self._calculate_commission(quantity, broker_id)

        # Emit domain event
        self.apply(OrderPlacedEvent(
            order_id=self.id,
            price=price,
            quantity=quantity,
            commission=commission
        ))
```

---

## Step-by-Step Service Creation

### Step 1: Identify Service Responsibility

**Ask yourself:**
1. Does this coordinate multiple domains? → Service
2. Does this handle infrastructure concerns? → Service
3. Is this a single domain operation? → Use CommandBus directly from API
4. Does this require business validation? → Domain logic, not service

**Example scenarios:**
- OAuth token exchange → `BrokerAuthenticationService`
- Broker WebSocket lifecycle → `StreamingLifecycleManager`
- Market data normalization → `MarketDataHandler`
- Saga orchestration → `SagaService`

### Step 2: Create Service Class

**Location**: `app/services/{service_name}.py`

**Template:**
```python
# app/services/my_service.py
import logging
from typing import Optional, Any, Dict
from uuid import UUID

# Import CQRS dependencies
from app.infra.cqrs.command_bus import CommandBus
from app.infra.cqrs.query_bus import QueryBus

log = logging.getLogger("tradecore.services.my_service")


class MyService:
    """
    Service for [describe responsibility].

    Responsibilities:
    - [What it does]
    - [What it coordinates]
    - [What it orchestrates]

    Architecture:
    [How it fits into the system]
    """

    def __init__(
        self,
        command_bus: CommandBus,
        query_bus: QueryBus,
        # Add other infrastructure dependencies
    ):
        self.command_bus = command_bus
        self.query_bus = query_bus

        # Initialize state
        self._initialized = False
        self._running = False

        log.info("MyService initialized")

    async def initialize(self) -> None:
        """Initialize service (called during startup)"""
        if self._initialized:
            return

        log.info("Initializing MyService...")

        # Setup infrastructure
        # Register callbacks
        # Start background tasks

        self._initialized = True
        self._running = True

        log.info("MyService initialized successfully")

    async def shutdown(self) -> None:
        """Shutdown service gracefully"""
        if not self._running:
            return

        log.info("Shutting down MyService...")

        # Cleanup resources
        # Stop background tasks

        self._running = False

        log.info("MyService shutdown complete")
```

### Step 3: Inject Dependencies

**In `app/core/startup/services.py`:**

```python
# Create service instances
my_service = MyService(
    command_bus=command_bus,
    query_bus=query_bus,
    # Other dependencies
)

# Initialize during startup
await my_service.initialize()

# Store in app state for access
app.state.my_service = my_service
```

### Step 4: Implement Public Methods

**Service methods should:**
- Be async (most operations are I/O bound)
- Take primitive types or value objects as parameters
- Return typed results (Pydantic models, dicts, primitives)
- Log important operations
- Handle errors gracefully

```python
async def perform_operation(
    self,
    user_id: UUID,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Perform operation description.

    Args:
        user_id: User identifier
        data: Operation data

    Returns:
        Result dictionary

    Raises:
        ValueError: If data is invalid
        ServiceError: If operation fails
    """
    try:
        log.info(f"Performing operation for user {user_id}")

        # Validate input
        if not data:
            raise ValueError("Data is required")

        # Orchestrate domain operations
        result = await self._orchestrate_workflow(user_id, data)

        log.info(f"Operation completed successfully")
        return result

    except Exception as e:
        log.error(f"Operation failed: {e}", exc_info=True)
        raise
```

### Step 5: Use CommandBus for Write Operations

**ALWAYS use CommandBus to modify state:**

```python
async def create_resource(self, user_id: UUID, data: dict):
    """Create new resource via domain command."""

    # Build command from input
    from app.my_domain.commands import CreateResourceCommand

    command = CreateResourceCommand(
        user_id=user_id,
        name=data['name'],
        description=data.get('description')
    )

    # Send via CommandBus (CQRS)
    result = await self.command_bus.send(command)

    log.info(f"Resource created: {result}")
    return result
```

### Step 6: Use QueryBus for Read Operations

**ALWAYS use QueryBus to read data:**

```python
async def get_resource(self, resource_id: UUID) -> Optional[dict]:
    """Retrieve resource via query."""

    from app.my_domain.queries import GetResourceQuery

    query = GetResourceQuery(resource_id=resource_id)

    # Query via QueryBus (CQRS)
    resource = await self.query_bus.query(query)

    if not resource:
        log.warning(f"Resource not found: {resource_id}")
        return None

    return resource
```

### Step 7: Add Error Handling and Logging

**Always handle errors appropriately:**

```python
from app.common.exceptions.exceptions import ServiceError

async def risky_operation(self, user_id: UUID):
    """Operation that may fail."""
    try:
        log.info(f"Starting risky operation for {user_id}")

        # Perform operation
        result = await self._do_something()

        log.info(f"Risky operation succeeded")
        return result

    except ConnectionError as e:
        # Infrastructure error - log and retry
        log.warning(f"Connection error: {e}, retrying...")
        await asyncio.sleep(1)
        return await self.risky_operation(user_id)

    except ValueError as e:
        # Invalid input - log and raise
        log.error(f"Invalid input: {e}")
        raise ServiceError(f"Invalid operation parameters: {e}")

    except Exception as e:
        # Unexpected error - log with full trace and raise
        log.error(f"Unexpected error in risky_operation: {e}", exc_info=True)
        raise ServiceError(f"Operation failed: {e}")
```

### Step 8: Register Service in DI Container

**In `app/core/startup/services.py`:**

```python
async def initialize_services(app: FastAPI):
    """Initialize all application services."""

    # Get infrastructure dependencies
    command_bus = app.state.command_bus
    query_bus = app.state.query_bus

    # Create service instance
    my_service = MyService(
        command_bus=command_bus,
        query_bus=query_bus
    )

    # Initialize
    await my_service.initialize()

    # Store in app state
    app.state.my_service = my_service

    log.info("MyService registered")
```

---

## Service Patterns

### Pattern 1: Facade Pattern (Coordination)

**Use case**: Provide unified interface to complex subsystem

**Example**: `StreamingService` (coordinates lifecycle, market data, trading data)

```python
class StreamingService:
    """
    Unified facade for all streaming operations.

    Coordinates:
    - StreamingLifecycleManager (connection lifecycle)
    - MarketDataHandler (market data processing)
    - TradingDataHandler (trading data processing)

    Design Pattern: Facade (Gang of Four)
    """

    def __init__(
        self,
        lifecycle_manager: StreamingLifecycleManager,
        market_data_handler: MarketDataHandler,
        trading_data_handler: TradingDataHandler
    ):
        self.lifecycle_manager = lifecycle_manager
        self.market_data_handler = market_data_handler
        self.trading_data_handler = trading_data_handler

        # Wire dependencies (circular dependency injection)
        self.lifecycle_manager.set_market_data_handler(self.market_data_handler)
        self.lifecycle_manager.set_trading_data_handler(self.trading_data_handler)

    async def startup(self) -> None:
        """Start all streaming components."""
        await self.lifecycle_manager.setup_event_listeners()
        # Market/trading handlers are stateless

    async def shutdown(self) -> None:
        """Shutdown all streaming components."""
        await self.lifecycle_manager.shutdown()
        await self.market_data_handler.shutdown()
        await self.trading_data_handler.shutdown()

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive streaming status."""
        return {
            "lifecycle": self.lifecycle_manager.get_status(),
            "market_data": self.market_data_handler.get_stats(),
            "trading_data": self.trading_data_handler.get_stats()
        }
```

### Pattern 2: Handler Pattern (Data Processing)

**Use case**: Process incoming data streams and distribute to multiple channels

**Example**: `MarketDataHandler` (normalizes broker data, distributes to WSE/Cache/CommandBus)

```python
class MarketDataHandler:
    """
    Platform-level Market Data Handler.

    Responsibilities:
    1. Subscribe DIRECTLY to broker adapters
    2. Receive real-time callbacks from adapters
    3. Normalize broker-specific data to common format
    4. Distribute to multiple channels:
       - WSEMarketDataPublisher (Frontend WebSocket)
       - CommandBus (Position valuation commands)
       - CacheManager (Redis caching)
       - Callbacks (VirtualBroker, Automation)

    Architecture:
    Broker Adapter → MarketDataHandler (DIRECT) → Multi-channel distribution
    """

    def __init__(
        self,
        wse_market_data_publisher: WSEMarketDataPublisher,
        command_bus: CommandBus,
        adapter_manager: AdapterManager,
        cache_manager: CacheManager
    ):
        self.wse_publisher = wse_market_data_publisher
        self.command_bus = command_bus
        self.adapter_manager = adapter_manager
        self.cache_manager = cache_manager

        # Subscription tracking
        self._subscriptions: Dict[str, Set[tuple[UUID, UUID]]] = defaultdict(set)

        # Callback registry
        self._quote_callbacks: List[Callable] = []

    async def subscribe_to_broker_data(
        self,
        user_id: UUID,
        broker_connection_id: UUID,
        broker_id: str,
        symbols: List[str]
    ) -> Dict[str, Any]:
        """
        Subscribe directly to broker adapter for market data.

        This method registers MarketDataHandler as the direct callback target.
        """
        adapter = await self.adapter_manager.get_adapter(
            user_id=user_id,
            broker_connection_id=broker_connection_id
        )

        # Create callback with context
        async def quote_callback(quote):
            await self._on_quote_from_adapter(
                quote=quote,
                user_id=user_id,
                broker_id=broker_id
            )

        # Subscribe to broker (DIRECT)
        result = await adapter.subscribe_quotes(
            user_id=str(user_id),
            symbols=symbols,
            callback=quote_callback
        )

        return result

    async def _on_quote_from_adapter(
        self,
        quote: Dict[str, Any],
        user_id: UUID,
        broker_id: str
    ):
        """
        Direct callback from adapter for quote updates.
        NO INDIRECTION - data flows directly from adapter to handler.
        """
        symbol = quote.get("symbol")

        # Normalize quote data
        normalized = self._normalize_quote(symbol, quote)

        # Distribute to multiple channels
        await self._distribute_quote(user_id, broker_id, symbol, normalized)

    async def _distribute_quote(
        self,
        user_id: UUID,
        broker_id: str,
        symbol: str,
        quote: Dict[str, Any]
    ):
        """Distribute quote to all channels."""
        # 1. Publish to WSE (Frontend)
        if self.wse_publisher:
            await self.wse_publisher.publish_quote_update(
                user_id=user_id,
                broker_id=broker_id,
                symbol=symbol,
                quote_data=quote
            )

        # 2. Send command to Position domain
        if self.command_bus:
            from app.position.commands import UpdatePositionValuationCommand
            await self.command_bus.send(
                UpdatePositionValuationCommand(
                    user_id=user_id,
                    symbol=symbol,
                    market_price=Decimal(str(quote.get("last", 0)))
                )
            )

        # 3. Cache in Redis
        if self.cache_manager:
            await self._cache_quote(symbol, quote)

        # 4. Notify registered callbacks
        for callback in self._quote_callbacks:
            await callback(quote)
```

### Pattern 3: Coordinator Pattern (Workflow Orchestration)

**Use case**: Orchestrate multi-step workflows across domains

**Example**: `SagaService` (orchestrates distributed transactions)

```python
class SagaService:
    """
    Saga orchestration service.

    Responsibilities:
    - Trigger sagas based on domain events
    - Track saga execution state
    - Handle saga compensation (rollback)
    - Prevent duplicate saga execution

    Architecture:
    Event → SagaService → SagaManager → Saga → CommandBus → Domains
    """

    def __init__(
        self,
        event_bus: EventBus,
        command_bus: CommandBus,
        query_bus: QueryBus,
        saga_manager: SagaManager
    ):
        self.event_bus = event_bus
        self.command_bus = command_bus
        self.query_bus = query_bus
        self.saga_manager = saga_manager

        # Saga trigger configurations
        self._trigger_configs: Dict[str, List[SagaTriggerConfig]] = {}

        # Duplicate detection
        self._active_sagas: Dict[str, Set[str]] = defaultdict(set)

    async def initialize(self):
        """Initialize saga service."""
        # Register saga types
        self._register_sagas()

        # Configure triggers
        self._configure_triggers()

        # Setup event consumers
        await self._setup_event_consumers()

    def _register_sagas(self):
        """Register all saga types."""
        from app.infra.saga.user_deletion_saga import UserDeletionSaga
        from app.infra.saga.broker_connection_saga import BrokerConnectionSaga

        saga_types = [
            UserDeletionSaga,
            BrokerConnectionSaga
        ]

        for saga_type in saga_types:
            self.saga_manager.register_saga(saga_type)

    def _configure_triggers(self):
        """Configure saga triggers."""
        self._trigger_configs["transport.user-account-events"] = [
            SagaTriggerConfig(
                event_types=["UserAccountDeleted"],
                saga_class=UserDeletionSaga,
                context_builder=lambda event: {
                    'user_id': event['user_id'],
                    'reason': event.get('reason', 'user_deletion')
                },
                dedupe_key_builder=lambda event: f"user_deletion:{event['user_id']}",
                dedupe_window_seconds=600
            )
        ]

    async def _handle_event(self, event_dict: Dict[str, Any]):
        """Handle event and trigger sagas if needed."""
        event_type = event_dict.get("event_type")

        # Find matching saga triggers
        for topic, configs in self._trigger_configs.items():
            for config in configs:
                if event_type in config.event_types:
                    await self._trigger_saga(config, event_dict)

    async def _trigger_saga(
        self,
        config: SagaTriggerConfig,
        event: Dict[str, Any]
    ):
        """Trigger saga execution."""
        # Check for duplicates
        dedupe_key = config.dedupe_key_builder(event) if config.dedupe_key_builder else None
        if dedupe_key and dedupe_key in self._active_sagas:
            log.warning(f"Saga already running: {dedupe_key}")
            return

        # Build saga context
        context = config.context_builder(event)

        # Track active saga
        if dedupe_key:
            self._active_sagas[dedupe_key].add(event.get('event_id'))

        try:
            # Execute saga via SagaManager
            await self.saga_manager.start_saga(
                saga_class=config.saga_class,
                saga_id=str(uuid4()),
                context=context
            )
        finally:
            # Cleanup tracking
            if dedupe_key:
                self._active_sagas[dedupe_key].discard(event.get('event_id'))
```

### Pattern 4: Background Service Pattern (Monitoring)

**Use case**: Continuous background monitoring and periodic tasks

**Example**: `DataIntegrityMonitor` (checks consistency, triggers recovery)

```python
class DataIntegrityMonitor:
    """
    Background service for data integrity monitoring.

    Responsibilities:
    - Periodic consistency checks
    - Gap detection between event store and read models
    - Trigger projection rebuilds
    - Alert on data corruption
    """

    def __init__(
        self,
        query_bus: QueryBus,
        event_store: EventStore,
        projection_rebuilder: ProjectionRebuilderService
    ):
        self.query_bus = query_bus
        self.event_store = event_store
        self.projection_rebuilder = projection_rebuilder

        # Background task
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start background monitoring."""
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        log.info("Data integrity monitor started")

    async def stop(self):
        """Stop background monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        log.info("Data integrity monitor stopped")

    async def _monitor_loop(self):
        """Background monitoring loop."""
        while self._running:
            try:
                # Check consistency
                issues = await self._check_consistency()

                # Trigger recovery if needed
                for issue in issues:
                    await self._handle_issue(issue)

                # Wait before next check
                await asyncio.sleep(300)  # 5 minutes

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Monitor error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Backoff on error

    async def _check_consistency(self) -> List[Dict[str, Any]]:
        """Check data consistency."""
        issues = []

        # Check each domain
        for domain in ["user_account", "broker_account", "order", "position"]:
            # Compare event count vs projection count
            event_count = await self.event_store.count_events(
                stream_name=f"{domain}-*"
            )
            projection_count = await self.query_bus.query(
                GetEntityCountQuery(domain=domain)
            )

            if abs(event_count - projection_count) > 10:
                issues.append({
                    "domain": domain,
                    "type": "count_mismatch",
                    "event_count": event_count,
                    "projection_count": projection_count
                })

        return issues

    async def _handle_issue(self, issue: Dict[str, Any]):
        """Handle detected issue."""
        domain = issue["domain"]
        issue_type = issue["type"]

        log.warning(f"Data integrity issue detected: {issue}")

        if issue_type == "count_mismatch":
            # Trigger projection rebuild
            await self.projection_rebuilder.rebuild_domain(domain)
```

---

## Broker Streaming Architecture (2025)

### Why We Refactored (Critical Understanding)

**Problem with Old Architecture** (pre-v0.6.0):
```
❌ Streaming services were routing data (mixing concerns)
❌ Lifecycle manager was mixed with data processing
❌ Not aligned with CQRS/ES/DDD best practices
❌ Unclear separation between REST API and streaming
```

**Solution (2025 Refactor)**:
```
✅ Handlers (not services) process streams
✅ Lifecycle manager only manages connections
✅ Facade pattern provides unified entry point
✅ Clean Architecture: Infrastructure → Application → Domain
✅ Broker-agnostic: Normalize broker data to commands
✅ Industry standard: Bloomberg, Alpaca, Interactive Brokers pattern
```

### Separation of Concerns

**OLD (Wrong)**:
```
REST API market data → app/infra/market_data/broker_providers/
Broker streaming market data → (Mixed with lifecycle!)
```

**NEW (Correct)**:
```
REST API market data → app/infra/market_data/broker_providers/ (synchronous HTTP)
Broker streaming market data → market_data_handler.py (real-time WebSocket/Chunked)
Broker streaming trading data → trading_data_handler.py (real-time WebSocket/Chunked)
Connection lifecycle → lifecycle_manager.py (health, reconnection)
Health monitoring → app/services/adapter_monitoring/ (observability)
```

### Direct Subscription Pattern

**Key insight**: Services register callbacks directly with broker adapters (no intermediary routing).

**Data flow**:
```
Broker WebSocket → Handler callback (DIRECT) → Multi-channel distribution
```

**Example**:
```python
# MarketDataHandler subscribes directly to adapter
adapter = await adapter_manager.get_adapter(user_id, broker_connection_id)

# Create callback with context
async def quote_callback(quote):
    await self._on_quote_from_adapter(quote=quote, user_id=user_id)

# Register callback directly
await adapter.subscribe_quotes(
    user_id=str(user_id),
    symbols=["AAPL", "TSLA"],
    callback=quote_callback  # DIRECT callback!
)
```

### Module Structure

```
app/services/broker_streaming/
├── __init__.py                  # Module exports
├── streaming_service.py         # Facade coordinator (entry point)
├── lifecycle_manager.py         # Connection lifecycle only
├── market_data_handler.py       # Market data streaming handler
└── trading_data_handler.py      # Trading data streaming handler
```

### Component Responsibilities

**1. StreamingService (Facade)**
- Unified entry point for all streaming operations
- Coordinates lifecycle, market data, trading data
- Gang of Four Facade pattern

```python
streaming_service = StreamingService(
    lifecycle_manager=lifecycle_manager,
    market_data_handler=market_data_handler,
    trading_data_handler=trading_data_handler
)

# Single entry point
await streaming_service.startup()
```

**2. StreamingLifecycleManager (Connection Management)**
- Establish/teardown WebSocket and HTTP Chunked connections
- Monitor connection health and trigger reconnection
- Manage subscription state (symbols, channels)
- **Does NOT route data** (handlers receive data directly from adapters)

```python
# Initiates subscriptions (delegates to handlers)
await lifecycle_manager.subscribe_to_market_data(
    user_id=user_id,
    broker_connection_id=broker_connection_id,
    broker_id="alpaca"
)
# Data flows: Adapter → MarketDataHandler (NOT through lifecycle manager!)
```

**3. MarketDataHandler (Market Data Processing)**
- Subscribe directly to broker adapters
- Receive real-time callbacks
- Normalize broker-specific data
- Distribute to multiple channels (WSE, CommandBus, Cache)
- Manage platform-wide subscriptions

```python
# Handler receives data directly from adapter
async def _on_quote_from_adapter(self, quote: Dict, user_id: UUID):
    # Normalize
    normalized = self._normalize_quote(quote)

    # Distribute to channels
    await self.wse_publisher.publish_quote_update(...)  # Frontend
    await self.command_bus.send(UpdatePositionValuationCommand(...))  # Domain
    await self.cache_manager.set_json(...)  # Cache
    for callback in self._callbacks:
        await callback(normalized)  # VirtualBroker, Automation
```

**4. TradingDataHandler (Trading Data Processing)**
- Process real-time trading events (fills, orders, balance)
- Normalize broker-specific data to commands
- Send commands to domains via CommandBus
- Periodic balance sync (REST fallback for Alpaca)

```python
# Handler normalizes broker data to commands
async def process_fill_event(self, fill: Dict, user_id: UUID):
    # Extract data
    price = Decimal(str(fill.get("price")))
    qty = Decimal(str(fill.get("qty")))

    # Incremental balance update
    self._local_balance[user_id]["cash"] -= price * qty

    # Send command to domain
    from app.broker_account.commands import UpdateAccountBalanceCommand
    await self.command_bus.send(
        UpdateAccountBalanceCommand(
            account_id=account_id,
            user_id=user_id,
            balance=self._local_balance[user_id]["cash"]
        )
    )
```

### Industry Best Practices

**1. Separate market data from trading data** (Bloomberg pattern)
- Market data: Quotes, trades, bars (high frequency)
- Trading data: Fills, orders, balance (critical accuracy)

**2. Separate connection lifecycle from data processing** (Alpaca pattern)
- Lifecycle: Connect, disconnect, reconnect, health
- Data: Normalize, distribute, cache

**3. Facade pattern for unified entry point** (Gang of Four)
- Simple interface to complex subsystem
- Coordinates multiple components

**4. Direct subscription with callbacks** (Interactive Brokers pattern)
- Adapter calls handler directly (low latency)
- No routing layers (reduces complexity)

### Integration with CQRS/ES/DDD

**CQRS Compliance**:
- Handlers send **commands** to CommandBus (write side)
- Handlers query **read models** via QueryBus (read side)
- No direct database access from handlers

**Event Sourcing Compliance**:
- Commands trigger domain events in aggregates
- Events stored in event store (immutable audit trail)
- Projectors update read models

**DDD Compliance**:
- Business logic in aggregates (not handlers)
- Handlers are **application layer** (orchestration only)
- Domain models isolated from infrastructure

### Usage Example

**Complete flow**:
```python
# 1. Initialize streaming components
lifecycle_manager = StreamingLifecycleManager(...)
market_data_handler = MarketDataHandler(...)
trading_data_handler = TradingDataHandler(...)

# 2. Create facade
streaming_service = StreamingService(
    lifecycle_manager=lifecycle_manager,
    market_data_handler=market_data_handler,
    trading_data_handler=trading_data_handler
)

# 3. Start streaming
await streaming_service.startup()

# 4. Data flows automatically:
# Alpaca WebSocket → MarketDataHandler → [WSE, CommandBus, Cache]
# Alpaca WebSocket → TradingDataHandler → CommandBus → Domain
```

---

## Code Examples

### Example 1: Simple Service (Authentication)

```python
# app/services/broker_auth_service.py
import logging
from typing import Optional, Tuple
from uuid import UUID

from app.infra.broker_adapters.adapter_manager import AdapterManager
from app.infra.broker_adapters.common.adapter_models import AuthInfo
from app.security.encryption import encrypt_data, decrypt_data

log = logging.getLogger("tradecore.services.broker_auth")


class BrokerAuthenticationService:
    """
    Handles ALL broker-specific authentication and credential management.

    Responsibilities:
    - OAuth token exchange
    - Credential encryption/decryption
    - Token refresh
    - Session management

    Storage hierarchy:
    1. Redis (CacheManager) - Fast access cache
    2. SQL Database - Persistent encrypted storage
    3. In-memory - Emergency fallback
    """

    def __init__(self, adapter_manager: AdapterManager):
        self._adapter_manager = adapter_manager
        self._cache_manager: Optional[CacheManager] = None

    async def initialize(self):
        """Initialize the service."""
        from app.infra.persistence.cache_manager import get_cache_manager
        self._cache_manager = get_cache_manager()
        log.info("BrokerAuthenticationService initialized")

    async def exchange_oauth_code_for_tokens(
        self,
        user_id: UUID,
        broker_id: str,
        broker_connection_id: UUID,
        code: str,
        redirect_uri: str
    ) -> Tuple[str, Optional[str], Optional[int]]:
        """
        Exchange OAuth authorization code for tokens.

        Returns:
            Tuple of (access_token, refresh_token, expires_in)
        """
        try:
            # Execute OAuth code exchange through AdapterManager
            result = await self._adapter_manager.execute_operation(
                user_id,
                broker_connection_id,
                "exchange_oauth_code_for_tokens",
                code=code,
                redirect_uri=redirect_uri
            )

            # Store tokens
            await self._store_oauth_tokens(str(user_id), broker_id, result)

            log.info(f"OAuth code exchanged for user {user_id}")
            return result

        except Exception as e:
            log.error(f"Error exchanging OAuth code: {e}", exc_info=True)
            raise

    async def _store_oauth_tokens(
        self,
        user_id: str,
        broker_id: str,
        tokens: Tuple[str, Optional[str], Optional[int]]
    ):
        """Store OAuth tokens in cache."""
        access_token, refresh_token, expires_in = tokens

        if self._cache_manager:
            cache_key = f"broker:{broker_id}:oauth:tokens:{user_id}"
            token_data = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": expires_in
            }
            await self._cache_manager.set_json(cache_key, token_data, ttl=expires_in)
```

### Example 2: Handler Service (Data Processing)

```python
# app/services/broker_streaming/trading_data_handler.py
import logging
from typing import Dict, Any
from uuid import UUID
from decimal import Decimal
from datetime import datetime, UTC

from app.infra.cqrs.command_bus import CommandBus

log = logging.getLogger("tradecore.streaming.trading_data")


class TradingDataHandler:
    """
    Real-time Trading Data Handler.

    Responsibilities:
    1. Process real-time trading events from broker adapters
    2. Normalize broker-specific data to generic commands
    3. Send commands to domains via CommandBus
    """

    def __init__(self, command_bus: CommandBus):
        self.command_bus = command_bus
        self._running = False

    async def start(self):
        """Start the handler."""
        self._running = True
        log.info("TradingDataHandler started")

    async def process_fill_event(
        self,
        fill_event: Dict[str, Any],
        user_id: UUID,
        account_id: UUID,
        broker_id: str
    ):
        """
        Process fill event from broker WebSocket.

        Architecture:
        1. Extract fill data (normalize broker format)
        2. Update local balance state
        3. Send UpdateAccountBalanceCommand → Domain
        """
        if not self._running:
            log.warning("Handler not running, ignoring fill event")
            return

        try:
            # Extract fill data (broker-agnostic)
            price = Decimal(str(fill_event.get("price", 0)))
            qty = Decimal(str(fill_event.get("qty", 0)))
            side = fill_event.get("order", {}).get("side")

            log.info(f"Processing fill: {side} {qty} @ ${price}")

            # Calculate trade value
            trade_value = price * qty

            # Send command to domain (CQRS)
            from app.broker_account.commands import UpdateAccountBalanceCommand

            await self.command_bus.send(
                UpdateAccountBalanceCommand(
                    account_id=account_id,
                    user_id=user_id,
                    balance=None,  # Domain will calculate
                    timestamp=datetime.now(UTC)
                )
            )

            log.info(f"Fill processed successfully")

        except Exception as e:
            log.error(f"Error processing fill: {e}", exc_info=True)
```

### Example 3: Facade Service (Coordination)

```python
# app/services/broker_streaming/streaming_service.py
import logging
from typing import Dict, Any

log = logging.getLogger("tradecore.streaming.service")


class StreamingService:
    """
    Unified facade for all streaming operations.

    Coordinates:
    - StreamingLifecycleManager (connection lifecycle)
    - MarketDataHandler (market data processing)
    - TradingDataHandler (trading data processing)

    Design Pattern: Facade (Gang of Four)
    """

    def __init__(
        self,
        lifecycle_manager: StreamingLifecycleManager,
        market_data_handler: MarketDataHandler,
        trading_data_handler: TradingDataHandler
    ):
        self.lifecycle_manager = lifecycle_manager
        self.market_data_handler = market_data_handler
        self.trading_data_handler = trading_data_handler

        # Wire dependencies (circular dependency injection)
        self.lifecycle_manager.set_market_data_handler(self.market_data_handler)
        self.lifecycle_manager.set_trading_data_handler(self.trading_data_handler)

        log.info("StreamingService initialized (facade pattern)")

    async def startup(self) -> None:
        """Start all streaming components."""
        log.info("Starting streaming services...")

        # Setup lifecycle event listeners
        await self.lifecycle_manager.setup_event_listeners()
        log.info("✓ Lifecycle manager started")

        # Handlers are stateless - no startup needed
        log.info("✓ Market data handler ready")
        log.info("✓ Trading data handler ready")

        log.info("All streaming services started successfully")

    async def shutdown(self) -> None:
        """Shutdown all streaming components."""
        log.info("Shutting down streaming services...")

        await self.lifecycle_manager.shutdown()
        log.info("✓ Lifecycle manager shutdown")

        if hasattr(self.market_data_handler, 'shutdown'):
            await self.market_data_handler.shutdown()
        log.info("✓ Market data handler shutdown")

        if hasattr(self.trading_data_handler, 'shutdown'):
            await self.trading_data_handler.shutdown()
        log.info("✓ Trading data handler shutdown")

        log.info("All streaming services shutdown successfully")

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive streaming status."""
        return {
            "lifecycle": self.lifecycle_manager.get_status(),
            "market_data": self.market_data_handler.get_stats() if hasattr(self.market_data_handler, 'get_stats') else {},
            "trading_data": self.trading_data_handler.get_stats() if hasattr(self.trading_data_handler, 'get_stats') else {}
        }
```

---

## Testing Services

### Unit Testing Pattern

```python
# tests/unit/services/test_my_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.my_service import MyService


@pytest.fixture
def mock_command_bus():
    """Mock CommandBus."""
    mock = AsyncMock()
    mock.send = AsyncMock(return_value={"success": True})
    return mock


@pytest.fixture
def mock_query_bus():
    """Mock QueryBus."""
    mock = AsyncMock()
    mock.query = AsyncMock(return_value=[])
    return mock


@pytest.fixture
async def service(mock_command_bus, mock_query_bus):
    """Create service instance."""
    service = MyService(
        command_bus=mock_command_bus,
        query_bus=mock_query_bus
    )
    await service.initialize()
    yield service
    await service.shutdown()


@pytest.mark.asyncio
async def test_service_operation(service, mock_command_bus):
    """Test service operation."""
    user_id = uuid4()
    data = {"name": "test"}

    # Execute operation
    result = await service.perform_operation(user_id, data)

    # Verify command was sent
    assert mock_command_bus.send.called
    assert result is not None


@pytest.mark.asyncio
async def test_service_error_handling(service):
    """Test service error handling."""
    user_id = uuid4()
    invalid_data = {}  # Invalid input

    # Should raise ValueError
    with pytest.raises(ValueError):
        await service.perform_operation(user_id, invalid_data)
```

### Integration Testing Pattern

```python
# tests/integration/test_my_service_integration.py
import pytest
from uuid import uuid4

from app.services.my_service import MyService
from app.infra.cqrs.command_bus import CommandBus
from app.infra.cqrs.query_bus import QueryBus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_service_with_real_buses(
    command_bus: CommandBus,
    query_bus: QueryBus
):
    """Test service with real CQRS buses."""
    # Create service
    service = MyService(
        command_bus=command_bus,
        query_bus=query_bus
    )
    await service.initialize()

    try:
        # Execute operation
        user_id = uuid4()
        result = await service.perform_operation(
            user_id,
            {"name": "integration_test"}
        )

        # Verify result
        assert result is not None
        assert result.get("success") is True

        # Verify state via query
        query_result = await service.get_resource(user_id)
        assert query_result is not None

    finally:
        await service.shutdown()
```

---

## Common Mistakes

### Mistake 1: Business Logic in Service

**❌ WRONG:**
```python
class OrderService:
    async def place_order(self, order_data: dict):
        # ❌ Business validation in service
        if order_data['price'] < 0:
            raise ValueError("Price must be positive")

        # ❌ Business calculation in service
        commission = order_data['quantity'] * 0.005

        # ❌ Direct state manipulation
        order = Order(**order_data)
        order.commission = commission
        await self.db.save(order)
```

**✅ CORRECT:**
```python
class OrderService:
    async def place_order(self, order_data: dict):
        # ✅ Service only orchestrates
        command = PlaceOrderCommand(**order_data)
        return await self.command_bus.send(command)

# Business logic belongs in aggregate
class OrderAggregate:
    def place_order(self, price, quantity):
        # ✅ Validation in aggregate
        if price <= 0:
            raise InvalidPriceError()

        # ✅ Calculation in aggregate
        commission = self._calculate_commission(quantity)

        # ✅ Emit event
        self.apply(OrderPlacedEvent(...))
```

### Mistake 2: Direct Database Access

**❌ WRONG:**
```python
class MyService:
    async def get_user(self, user_id: UUID):
        # ❌ Direct database access from service
        async with self.pg_client.connection() as conn:
            result = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id
            )
        return result
```

**✅ CORRECT:**
```python
class MyService:
    async def get_user(self, user_id: UUID):
        # ✅ Use QueryBus (CQRS)
        from app.user_account.queries import GetUserQuery
        return await self.query_bus.query(
            GetUserQuery(user_id=user_id)
        )
```

### Mistake 3: Synchronous Code in Async Service

**❌ WRONG:**
```python
class MyService:
    async def process_data(self, data: list):
        results = []
        for item in data:
            # ❌ Blocking synchronous operation
            result = self._sync_process(item)
            results.append(result)
        return results
```

**✅ CORRECT:**
```python
class MyService:
    async def process_data(self, data: list):
        # ✅ Concurrent async operations
        tasks = [self._async_process(item) for item in data]
        results = await asyncio.gather(*tasks)
        return results
```

### Mistake 4: Not Handling Errors

**❌ WRONG:**
```python
class MyService:
    async def risky_operation(self, user_id: UUID):
        # ❌ No error handling - exceptions bubble up
        result = await self.external_api.call()
        return result
```

**✅ CORRECT:**
```python
class MyService:
    async def risky_operation(self, user_id: UUID):
        try:
            result = await self.external_api.call()
            return result
        except ConnectionError as e:
            # ✅ Handle transient errors
            log.warning(f"Connection error, retrying: {e}")
            await asyncio.sleep(1)
            return await self.risky_operation(user_id)
        except ValueError as e:
            # ✅ Handle invalid input
            log.error(f"Invalid input: {e}")
            raise ServiceError(f"Operation failed: {e}")
        except Exception as e:
            # ✅ Handle unexpected errors
            log.error(f"Unexpected error: {e}", exc_info=True)
            raise
```

### Mistake 5: Circular Service Dependencies

**❌ WRONG:**
```python
# service_a.py
class ServiceA:
    def __init__(self, service_b: ServiceB):
        self.service_b = service_b  # ❌ Circular dependency

# service_b.py
class ServiceB:
    def __init__(self, service_a: ServiceA):
        self.service_a = service_a  # ❌ Circular dependency
```

**✅ CORRECT:**
```python
# Use events for decoupling
class ServiceA:
    async def do_something(self):
        # ✅ Emit event instead of calling ServiceB
        await self.event_bus.publish(SomethingHappenedEvent(...))

class ServiceB:
    async def setup_listeners(self):
        # ✅ Subscribe to events
        await self.event_bus.subscribe(
            "events.something",
            self._handle_something
        )
```

---

## Best Practices

### 1. Service Naming

**Follow conventions:**
- `{Purpose}Service` for general services (`OrderService`, `UserService`)
- `{Purpose}Handler` for data processing (`MarketDataHandler`, `TradingDataHandler`)
- `{Purpose}Manager` for lifecycle management (`StreamingLifecycleManager`)
- `{Purpose}Monitor` for background monitoring (`DataIntegrityMonitor`)

### 2. Dependency Injection

**Always inject dependencies in constructor:**
```python
class MyService:
    def __init__(
        self,
        command_bus: CommandBus,
        query_bus: QueryBus,
        # Other dependencies
    ):
        # Store dependencies
        self.command_bus = command_bus
        self.query_bus = query_bus
```

**Never create dependencies inside service:**
```python
# ❌ WRONG
class MyService:
    def __init__(self):
        self.command_bus = CommandBus()  # DON'T DO THIS!

# ✅ CORRECT
class MyService:
    def __init__(self, command_bus: CommandBus):
        self.command_bus = command_bus  # Injected!
```

### 3. Initialization Pattern

**Use separate `initialize()` method:**
```python
class MyService:
    def __init__(self, dependencies):
        # Store dependencies only
        self._dependencies = dependencies
        self._initialized = False

    async def initialize(self):
        # Async initialization
        if self._initialized:
            return

        # Setup resources
        await self._setup_connections()
        await self._setup_listeners()

        self._initialized = True
```

### 4. Graceful Shutdown

**Always implement cleanup:**
```python
class MyService:
    async def shutdown(self):
        """Gracefully shutdown service."""
        if not self._running:
            return

        log.info("Shutting down MyService...")

        # Stop background tasks
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Close connections
        await self._close_connections()

        self._running = False
        log.info("MyService shutdown complete")
```

### 5. Logging Best Practices

**Use structured logging:**
```python
# ✅ CORRECT: Include context
log.info(
    f"Processing order: order_id={order_id}, "
    f"user_id={user_id}, symbol={symbol}"
)

# ✅ CORRECT: Log exceptions with traceback
try:
    result = await self.do_something()
except Exception as e:
    log.error(f"Operation failed: {e}", exc_info=True)
    raise

# ❌ WRONG: No context
log.info("Processing order")

# ❌ WRONG: No traceback
try:
    result = await self.do_something()
except Exception as e:
    log.error(f"Error: {e}")  # Missing exc_info=True!
```

### 6. Return Types

**Use typed return values:**
```python
# ✅ CORRECT: Explicit types
async def get_user(self, user_id: UUID) -> Optional[UserModel]:
    result = await self.query_bus.query(GetUserQuery(user_id))
    return result

# ✅ CORRECT: Pydantic models
async def create_order(self, data: OrderCreateData) -> OrderResult:
    command = PlaceOrderCommand(**data.dict())
    result = await self.command_bus.send(command)
    return OrderResult(**result)

# ❌ WRONG: No types
async def get_user(self, user_id):
    return await self.query_bus.query(GetUserQuery(user_id))
```

### 7. Error Handling Strategy

**Use domain-specific exceptions:**
```python
from app.common.exceptions.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError
)

class MyService:
    async def get_resource(self, resource_id: UUID):
        try:
            resource = await self.query_bus.query(GetResourceQuery(resource_id))

            if not resource:
                # ✅ Domain-specific exception
                raise NotFoundError(f"Resource not found: {resource_id}")

            return resource

        except NotFoundError:
            # Re-raise domain exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ServiceError(f"Failed to get resource: {e}")
```

### 8. Concurrency Considerations

**Use locks for critical sections:**
```python
import asyncio

class MyService:
    def __init__(self):
        self._lock = asyncio.Lock()

    async def critical_operation(self, user_id: UUID):
        # ✅ Protect critical section
        async with self._lock:
            # Only one concurrent execution
            result = await self._do_critical_thing(user_id)
            return result
```

### 9. Testing Guidelines

**Make services testable:**
```python
class MyService:
    def __init__(
        self,
        command_bus: CommandBus,
        query_bus: QueryBus,
        # ✅ All dependencies injectable
    ):
        self.command_bus = command_bus
        self.query_bus = query_bus

    # ✅ Public methods are testable
    async def public_operation(self, data):
        return await self._internal_operation(data)

    # ✅ Internal methods can be tested via public API
    async def _internal_operation(self, data):
        # Implementation
        pass
```

### 10. Documentation

**Document service responsibilities:**
```python
class MyService:
    """
    Service for [clear description].

    Responsibilities:
    - [What it does]
    - [What it coordinates]
    - [What it manages]

    Architecture:
    - Fits into [layer]
    - Depends on [services/infrastructure]
    - Used by [API/other services]

    Example:
        >>> service = MyService(command_bus, query_bus)
        >>> await service.initialize()
        >>> result = await service.do_something()
    """
```

---

## Summary

**Key Takeaways:**

1. **Services orchestrate, domains decide** - Keep business logic in aggregates
2. **Use CQRS** - Always use CommandBus/QueryBus, never direct database access
3. **Separate concerns** - Lifecycle ≠ Data processing ≠ Business logic
4. **Follow patterns** - Facade, Handler, Coordinator, Background Service
5. **Industry standards** - Learn from Bloomberg, Alpaca, Interactive Brokers
6. **Test everything** - Unit tests (mocks) + Integration tests (real dependencies)
7. **Document thoroughly** - Explain WHY, not just WHAT

**Next Steps:**
- Read exemplar services (`broker_auth_service.py`, `broker_streaming/`)
- Study domain guides (`DOMAIN_CREATION_TEMPLATE.md`)
- Review CQRS architecture (`docs/cqrs.md`)
- Implement your own service following this guide!

---

**Related Documentation:**
- `/docs/mvp/DOMAIN_CREATION_TEMPLATE.md` - Domain creation guide
- `/docs/cqrs.md` - CQRS architecture reference
- `/docs/mvp/DOMAIN_IMPLEMENTATION_BEST_PRACTICES.md` - Best practices
- `/app/services/broker_streaming/` - Streaming architecture (2025 refactor)

**Version**: 0.6.0
**Last Updated**: 2025-01-10
