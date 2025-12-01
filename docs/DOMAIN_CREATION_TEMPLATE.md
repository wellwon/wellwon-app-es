# Domain Creation Template & Checklist

**Date**: 2025-10-30 (Updated: 2025-11-22)
**Purpose**: Step-by-step guide for creating new domains in TradeCore

**⚠️ CRITICAL UPDATES (2025-11-22)**:
- **Pydantic v2 Migration**: ALL Commands/Queries use Pydantic v2 with CQRS base classes
- **Commands**: MUST inherit from `Command` (app.infra.cqrs.command_bus)
- **Queries**: MUST inherit from `Query` (app.infra.cqrs.query_bus)
- **Handlers**: MUST inherit from `BaseCommandHandler` / `BaseQueryHandler`
- **Standard Structure**: ALL domains MUST have `exceptions.py` and `enums.py`

**Previous Updates (2025-11-13)**:
- **Event Auto-Registration**: Use `@domain_event()` decorator (NO manual registry)
- **SYNC Decorators Only**: Use `@sync_projection` decorator (NO sync_events.py files)
- **Code Reduction**: 70% reduction in event_registry.py boilerplate
- **Performance**: SYNC optimization reduced projections from 69 → 54

**Previous Updates (2025-11-01)**:
- Fixed PGClient reference (use `db` proxy instead)
- Fixed AggregateRepository pattern (use EventStore + publish_events_standalone)
- Added Custom Domain Exceptions requirement
- Added proper GROUP BY clause patterns
- Updated Router CQRS patterns (NO direct repository access)
- Added CRYPTO asset type support (5th asset type - treated like STOCK)

---

## 📋 Quick Checklist

Use this checklist when creating a new domain:

- [ ] Step 1: Create domain file structure
- [ ] Step 2: Define domain events with @domain_event() decorator
- [ ] Step 2.5: **ANALYZE** which events need sync vs async projections
- [ ] Step 3: Implement aggregate
- [ ] Step 4: Create commands & handlers
- [ ] Step 5: Create queries & handlers
- [ ] Step 6: Create projectors with @sync_projection decorator
- [ ] Step 7: Create read models
- [ ] Step 8: Register in domain_registry.py
- [ ] Step 9: Update handler_dependencies.py
- [ ] Step 10: Update CQRS registration
- [ ] Step 11: Add WSE integration (if needed)
- [ ] Step 12: Create API router
- [ ] Step 13: Create database schema
- [ ] Step 14: Write tests

---

## 🚀 Step-by-Step Guide

### Step 1: Create Domain File Structure

Create directory: `app/{domain}/`

**Required files:**
```bash
app/{domain}/
├── __init__.py              # Empty or with exports
├── aggregate.py             # Domain aggregate with state
├── commands.py              # Commands (Pydantic v2, inherit from Command)
├── queries.py               # Queries (Pydantic v2, inherit from Query)
├── events.py                # Events (Pydantic BaseEvent with @domain_event)
├── exceptions.py            # Domain exceptions (REQUIRED)
├── enums.py                 # Domain enums (REQUIRED)
├── projectors.py            # Event projectors with @sync_projection
├── read_models.py           # Read model schemas (Pydantic v2)
├── value_objects.py         # Value objects (frozen dataclasses, optional)
├── command_handlers/        # Command handlers (inherit BaseCommandHandler)
│   ├── lifecycle_handlers.py
│   └── [category]_handlers.py
└── query_handlers/          # Query handlers (inherit BaseQueryHandler)
    └── [category]_query_handlers.py
```

**⚠️ 2025-11-22 PYDANTIC V2 REQUIREMENTS**:
- **commands.py**: ALL commands inherit from `Command` (Pydantic v2)
- **queries.py**: ALL queries inherit from `Query` (Pydantic v2)
- **command_handlers/**: ALL handlers inherit from `BaseCommandHandler`
- **query_handlers/**: ALL handlers inherit from `BaseQueryHandler`
- **exceptions.py**: REQUIRED - domain-specific business errors
- **enums.py**: REQUIRED - domain-specific enumerations

**⚠️ 2025-11-13 EVENT REQUIREMENTS**:
- **events.py**: ALL events MUST use `@domain_event()` decorator (auto-registration)
- **projectors.py**: Use `@sync_projection` decorator for SYNC projections
- **NO sync_events.py**: REMOVED - decorator is single source of truth

---

### Step 2: Define Domain Events with @domain_event() Decorator

**File**: `app/{domain}/events.py`

**⚠️ CRITICAL**: All events MUST use `@domain_event()` decorator for automatic registration.

**Import Required Decorators:**
```python
from app.infra.event_bus.event_decorators import domain_event
from app.common.base.base_model import BaseEvent
from typing import Literal
from datetime import datetime, UTC
from uuid import UUID
from decimal import Decimal
from pydantic import Field
```

**Event Definition Pattern:**
```python
@domain_event(category="domain", description="Brief description")
class MyDomainEvent(BaseEvent):
    """Detailed docstring explaining what this event represents"""
    event_type: Literal["MyDomainEvent"] = "MyDomainEvent"

    # Aggregate identifier (REQUIRED)
    my_entity_id: UUID

    # Event data fields
    field1: str
    field2: Decimal
    field3: Optional[str] = None

    # Timestamp (REQUIRED)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**Complete Example:**
```python
from app.infra.event_bus.event_decorators import domain_event
from app.common.base.base_model import BaseEvent
from typing import Literal, Optional
from datetime import datetime, UTC
from uuid import UUID
from decimal import Decimal
from pydantic import Field

# =============================================================================
# Lifecycle Events
# =============================================================================

@domain_event(category="domain", description="Order placed by user")
class OrderPlacedEvent(BaseEvent):
    """Order has been placed and is pending broker submission"""
    event_type: Literal["OrderPlacedEvent"] = "OrderPlacedEvent"

    order_id: UUID
    user_id: UUID
    account_id: UUID
    symbol: str
    side: str  # "buy" or "sell"
    quantity: Decimal
    order_type: str  # "market", "limit", "stop"
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None

    placed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

@domain_event(category="domain", description="Order acknowledged by broker")
class OrderAcknowledgedEvent(BaseEvent):
    """Broker has acknowledged order receipt"""
    event_type: Literal["OrderAcknowledgedEvent"] = "OrderAcknowledgedEvent"

    order_id: UUID
    broker_order_id: str  # External broker ID
    acknowledged_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

# =============================================================================
# Execution Events
# =============================================================================

@domain_event(category="domain", description="Order filled by broker")
class OrderFilledEvent(BaseEvent):
    """Order has been filled (partially or completely)"""
    event_type: Literal["OrderFilledEvent"] = "OrderFilledEvent"

    order_id: UUID
    filled_quantity: Decimal
    filled_price: Decimal
    commission: Decimal
    filled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**Decorator Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `category` | str | "domain" | Event category (domain/saga/system/streaming) |
| `description` | str | None | Brief description for documentation |
| `priority` | int | 10 | Event priority (5=saga, 10=domain, 15=system, 20=streaming) |

**Event Naming Convention:**
- Use PascalCase with "Event" suffix: `OrderPlacedEvent`, `UserCreatedEvent`
- Use past tense: "Created", "Updated", "Deleted", not "Create", "Update", "Delete"
- Be specific: "OrderFilledEvent" not "OrderEvent"

**IMPORTANT RULES:**
1. **ALWAYS** add `@domain_event()` decorator to ALL events
2. **ALWAYS** include `event_type: Literal["EventName"] = "EventName"` field
3. **ALWAYS** use `datetime.now(UTC)` for timestamps (NOT `datetime.utcnow()`)
4. **NEVER** manually add events to `event_registry.py` (auto-registered!)
5. **NEVER** duplicate event definitions across domains

---

### Step 2.5: Decision Guide - Sync vs Async Projections ⭐⭐⭐

**CRITICAL**: Understanding when to use sync vs async projections is fundamental to your domain design.

> ⚠️ **ВАЖНО**: Это руководство, а не жёсткие правила. **Для каждого нового домена** нужно индивидуально анализировать:
> - Какие события требуют немедленной видимости?
> - Какие операции выполняются сразу после команды?
> - Какие данные критичны для других доменов?
>
> **Перед имплементацией домена** - обсудите и задокументируйте решения о sync/async для каждого события!

#### 🎯 The Rule

**Use `@sync_projection` IF any of these are true:**

1. ✅ **User expects immediate visibility** - User created/updated something and will query it right away
2. ✅ **Critical for correctness** - Other systems/domains depend on this data being immediately available
3. ✅ **State transitions** - Entity moved to new state (pending → submitted → filled)
4. ✅ **Financial operations** - Money/positions/orders changed
5. ✅ **Authorization/Security** - Permissions, access control updates

**Use Async Projector (NO decorator) IF:**

1. ⏰ **Analytics/Metrics** - Non-critical aggregations, statistics
2. ⏰ **Audit logs** - Historical tracking (not queried immediately)
3. ⏰ **Derived data** - Calculated values that don't affect core operations
4. ⏰ **Notifications** - Emails, alerts (eventual consistency OK)
5. ⏰ **Reporting** - Data warehouse, business intelligence

---

#### 📊 Comparison Table

| Characteristic | Sync Projection | Async Projection |
|----------------|-----------------|------------------|
| **Decorator** | `@sync_projection(...)` | No decorator (or `@projector(...)`) |
| **Execution** | **BLOCKS** command handler | Runs in background |
| **Consistency** | **Immediate** (read-after-write) | **Eventual** (seconds/minutes) |
| **Timeout** | 1-5 seconds | No timeout |
| **Use for** | Critical data | Analytics, logs |
| **Example** | OrderPlaced, UserCreated | MetricsCalculated, AuditLogged |

---

#### 💡 Real Examples from Order Domain

**✅ Sync Projections** (`app/order/projectors.py` with `@sync_projection` decorators):

```python
from app.infra.event_store.sync_decorators import sync_projection
from app.infra.event_store.event_envelope import EventEnvelope

class OrderProjector:
    """Order projector using @sync_projection decorators"""

    @sync_projection("OrderPlacedEvent", priority=1, timeout=2.0)
    async def on_order_placed(self, envelope: EventEnvelope) -> None:
        """SYNC: User creates order and immediately queries it"""
        pass

    @sync_projection("OrderAcknowledgedEvent", priority=1, timeout=1.0)
    async def on_order_acknowledged(self, envelope: EventEnvelope) -> None:
        """SYNC: Broker acknowledged - user checks status"""
        pass

    @sync_projection("OrderFilledEvent", priority=2, timeout=2.0)
    async def on_order_filled(self, envelope: EventEnvelope) -> None:
        """SYNC: Order filled - affects positions/buying power"""
        pass

    @sync_projection("OrderCompletedEvent", priority=1, timeout=1.0)
    async def on_order_completed(self, envelope: EventEnvelope) -> None:
        """SYNC: Order completed - user sees final status"""
        pass

    @sync_projection("OrderCancelledEvent", priority=1, timeout=1.0)
    async def on_order_cancelled(self, envelope: EventEnvelope) -> None:
        """SYNC: User cancelled order - must see status change"""
        pass

    @sync_projection("OrderRejectedEvent", priority=1, timeout=1.0)
    async def on_order_rejected(self, envelope: EventEnvelope) -> None:
        """SYNC: Broker rejected - user needs error message"""
        pass
```

**Why Sync?**
- User placed order → **immediately queries** order status
- Frontend shows "Order Placed" → **must be in database**
- Other domains query order → **must exist** (Position domain needs it)

**⏰ Async Projections** (NO decorator - processed by EventProcessorWorker):

```python
class OrderProjector:
    """Async projections - no @sync_projection decorator"""

    # NO decorator = ASYNC
    async def on_order_execution_time_calculated(self, envelope: EventEnvelope) -> None:
        """ASYNC: Metrics - not queried immediately"""
        pass

    async def on_order_audit_log_created(self, envelope: EventEnvelope) -> None:
        """ASYNC: Audit trail - eventual consistency OK"""
        pass

    async def on_order_performance_metrics_updated(self, envelope: EventEnvelope) -> None:
        """ASYNC: Analytics - can wait"""
        pass

    async def on_order_notification_sent(self, envelope: EventEnvelope) -> None:
        """ASYNC: Email/alert - not queried"""
        pass
```

**Why Async?**
- Not queried immediately after creation
- Don't affect core operations
- Can tolerate seconds/minutes of delay

---

#### 🔍 Decision Tree

```
Does user query this data immediately after command?
├─ YES → Do other systems depend on it?
│         ├─ YES → Use @sync_projection ✅
│         └─ NO  → Use @sync_projection ✅ (user needs it)
│
└─ NO  → Is it critical for correctness?
          ├─ YES → Use @sync_projection ✅
          └─ NO  → Use Async Projection ⏰
```

---

#### ⚡ Performance Trade-offs

**Sync Projection:**
- ➕ **Immediate consistency** - No "order not found" errors
- ➕ **Better UX** - User sees changes instantly
- ➕ **Simpler logic** - No retry/polling needed
- ➖ **Slower commands** - Command handler waits for projection
- ➖ **Timeout risk** - If projection fails, command fails

**Async Projection:**
- ➕ **Faster commands** - Handler returns immediately
- ➕ **No timeout risk** - Projections retry in background
- ➕ **Better throughput** - More commands/second
- ➖ **Eventual consistency** - User might not see data immediately
- ➖ **Complex error handling** - Projection errors don't fail command

---

#### 📝 How to Implement

**Sync Projection** (for critical events only):

```python
# In app/{domain}/projectors.py
from app.infra.event_store.sync_decorators import sync_projection, monitor_projection
from app.infra.event_store.event_envelope import EventEnvelope

class MyDomainProjector:
    """Domain projector"""

    def __init__(self, my_repo: MyReadRepo):
        self.my_repo = my_repo

    @sync_projection("OrderPlacedEvent", priority=1, timeout=2.0)
    @monitor_projection
    async def on_order_placed(self, envelope: EventEnvelope) -> None:
        """Project OrderPlacedEvent

        SYNC: User queries order immediately after placement
        Performance: Blocks command handler until complete
        """
        event_data = envelope.event_data
        order_id = envelope.aggregate_id

        # This BLOCKS command handler until complete
        await self.my_repo.insert_order(
            order_id=order_id,
            user_id=event_data['user_id'],
            symbol=event_data['symbol'],
            status='placed'
        )
```

**Async Projection** (for analytics/logging):

```python
# In app/{domain}/projectors.py
# NO @sync_projection decorator - ASYNC by default

class MyDomainProjector:
    """Domain projector"""

    def __init__(self, my_repo: MyReadRepo):
        self.my_repo = my_repo

    async def on_metrics_calculated(self, envelope: EventEnvelope) -> None:
        """Project OrderMetricsCalculated

        ASYNC: Analytics data - eventual consistency OK
        Performance: Does not block command handler
        """
        event_data = envelope.event_data

        # This runs in background (eventual consistency)
        await self.my_repo.update_metrics(
            order_id=event_data['order_id'],
            execution_time=event_data['execution_time']
        )
```

**@sync_projection Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `event_type` | str | Required | Event type string (must match event_type field) |
| `priority` | int | 10 | Execution priority (1=highest, 5=lowest) |
| `timeout` | float | 5.0 | Max seconds to wait for projection |

**Priority Guidelines:**
- **1 (Highest)**: Critical security/authorization events
- **2 (High)**: User-facing state transitions
- **3 (Normal)**: Standard business logic
- **5 (Low)**: Metadata updates

**Timeout Guidelines:**
- **1.0s**: Simple INSERT/UPDATE
- **2.0s**: Complex operations with multiple tables
- **3.0s**: Cascading operations (deletions with cleanup)
- **5.0s**: Batch processing (avoid if possible!)

---

#### 🎓 Best Practices

1. **Start with ASYNC** - Default to async projections, only add @sync_projection when critical
2. **Measure Impact** - Monitor command latency (should be <100ms for most operations)
3. **Document Decisions** - Add docstring explaining WHY projection is SYNC or ASYNC
4. **Test Read-After-Write** - Test immediate queries for SYNC projections
5. **Keep Timeouts Short** - 1-2s for simple operations, avoid >3s timeouts
6. **Reserve SYNC for Critical** - Security, authorization, user-facing state only

**Example Documentation:**
```python
@sync_projection("UserAccountDeleted", priority=1, timeout=3.0)
async def on_user_deleted(self, envelope: EventEnvelope) -> None:
    """Project UserAccountDeleted event

    SYNC: Critical for security - prevent deleted user from accessing system
    Performance: Blocks delete command ~50-100ms (includes cache invalidation)
    """
    pass

async def on_user_authentication_succeeded(self, envelope: EventEnvelope) -> None:
    """Project UserAuthenticationSucceeded event

    ASYNC: Last login timestamp update - eventual consistency OK
    Performance: Does not block authentication flow
    """
    pass
```

---

#### 🚨 Common Mistakes

❌ **Making everything async**
- "It's faster!" but users get "not found" errors
- Example: User creates order → queries it → 404 error

❌ **Making everything sync**
- "It's simpler!" but command handler times out
- Example: Analytics blocking every write operation

❌ **Forgetting @sync_projection decorator**
- Projection runs async even though you intended sync
- System shows eventual consistency delays

❌ **Wrong timeout values**
- Too short (0.5s) → projections fail randomly
- Too long (10s) → command handler hangs, poor UX

❌ **Not documenting WHY**
- Next developer doesn't know if SYNC is critical
- Leads to incorrect optimizations

✅ **Correct Approach**:
- **Critical user-facing events** → @sync_projection
- **Analytics/metrics/logging** → Async (no decorator)
- **Document reasoning** in projection docstring
- **Test read-after-write** scenarios for SYNC projections
- **Monitor performance** and optimize based on metrics

---

### Step 3: Implement Aggregate

**File**: `app/{domain}/aggregate.py`

```python
"""
{Domain} Aggregate

Represents the {domain} entity with its state and business logic.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from app.common.base.base_aggregate import BaseAggregate
from app.{domain}.events import (
    {EventName1},
    {EventName2},
    # Import all events
)
from app.{domain}.enums import {EnumName}


@dataclass
class {Domain}Aggregate(BaseAggregate):
    """
    {Domain} aggregate root.

    Enforces business rules for {domain} operations.
    """

    # === STATE FIELDS ===
    {domain}_id: str
    status: {EnumName}
    field1: str
    field2: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # === BUSINESS LOGIC METHODS ===

    def method1(self, param1: str) -> None:
        """
        Business logic for action 1.

        Raises:
            ValueError: If business rule violated
        """
        # Validate business rules
        if not self._validate_rule1(param1):
            raise ValueError(f"Business rule violated: {param1}")

        # Apply event
        event = {EventName1}(
            aggregate_id=self.{domain}_id,
            field1=param1,
            timestamp=datetime.now()
        )
        self.apply(event)

    # === EVENT HANDLERS (State Updates) ===

    def apply_{event_name1}(self, event: {EventName1}) -> None:
        """Apply {EventName1} to update aggregate state"""
        self.field1 = event.field1
        self.updated_at = event.timestamp

    # Add apply method for EVERY event

    # === VALIDATION HELPERS ===

    def _validate_rule1(self, param: str) -> bool:
        """Validate business rule 1"""
        return len(param) > 0
```

**Best Practices:**
- Separate state fields from business logic
- All state changes through events (via `self.apply()`)
- Validation before emitting events
- Add `apply_{event_name}` method for each event
- Use clear method names describing business actions

---

### Step 4: Create Commands & Handlers

**File**: `app/{domain}/commands.py`

**⚠️ CRITICAL (2025-11-22)**: Commands MUST use Pydantic v2 and inherit from `Command`

```python
"""
{Domain} Commands

Commands represent user intentions and trigger state changes.

Converted to Pydantic v2 for proper validation and serialization.
"""

from typing import Optional, Dict, Any
from decimal import Decimal
from uuid import UUID

from pydantic import Field
from app.infra.cqrs.command_bus import Command  # REQUIRED


class {CommandName1}(Command):  # MUST inherit from Command
    """
    Command to {action description}.

    Args:
        {domain}_id: ID of the {domain}
        param1: Description
    """
    # Required fields (no defaults) - MUST come first
    {domain}_id: UUID
    param1: str

    # Optional fields (with defaults) - MUST come after
    param2: Optional[str] = None
    user_id: Optional[UUID] = None  # For authorization

    # Metadata (inherited saga_id from Command base class)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

**File**: `app/{domain}/command_handlers/{category}_handlers.py` ⭐ NEW STRUCTURE

**⚠️ CRITICAL**: Handlers are CLASS-BASED, extending BaseCommandHandler!

```python
"""
{Domain} Command Handlers

⚠️ CRITICAL: CLASS-BASED handlers extending BaseCommandHandler
"""

import logging
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from app.common.base.base_command_handler import BaseCommandHandler  # ⭐ NEW!
from app.infra.cqrs.decorators import command_handler
from app.

{domain}.commands
import

{CommandName1}
from app.

{domain}.aggregate
import

{Domain}
Aggregate

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("tradecore.{domain}.handlers")


@command_handler({CommandName1})
class {CommandName1}Handler(BaseCommandHandler):  # ⭐ EXTENDS BaseCommandHandler!
    """
    ⚠️ CORRECTED: CLASS-BASED Handler

    Handle {CommandName1}.

    Steps:
    1. Load aggregate (or create)
    2. Execute business logic
    3. Save using BaseCommandHandler.publish_and_commit_events()
    """

    def __init__(self, deps: 'HandlerDependencies'):
        # Store dependencies
        self.event_bus = deps.event_bus
        self.event_store = deps.event_store
        self.query_bus = deps.query_bus
        self.command_bus = deps.command_bus

        # ✅ Initialize base class
        super().__init__(
            event_bus=self.event_bus,
            transport_topic="{domain}_events",  # Your domain's event topic
            event_store=self.event_store
        )

    async def handle(self, command: {CommandName1}) -> UUID:
        """
        Handle command - INSTANCE METHOD

        Returns: {domain}_id or relevant ID
        """
        log.info(f"Handling {CommandName1} for {domain}_id={command.{domain}_id}")

        # Load or create aggregate
        if command.{domain}_id:
            # Load existing
            aggregate = await self._load_aggregate(command.
            {domain}
            _id)
            else:
            # Create new
            aggregate = {Domain}
            Aggregate.create(
                {domain}
            _id = uuid4(),
            field1 = command.param1,
            # ... initialization params
            )

            # Execute business logic (aggregate method)
            aggregate.method1(command.param1)

            # ✅ Save using BaseCommandHandler method
            # This handles:
            # - Event Store persistence
            # - Outbox pattern (exactly-once)
            # - Event Bus publishing
            # - Version management
            await self.publish_and_commit_events(
                aggregate=aggregate,
                aggregate_type="{Domain}",
                expected_version=None,  # None for new, aggregate.version for existing
                saga_id=command.metadata.get("saga_id") if hasattr(command, 'metadata') else None
            )

            log.info(f"{CommandName1} completed for {domain}_id={aggregate.{domain}_id}")
            return aggregate.
            {domain}
            _id

        async def _load_aggregate(self, {domain}_id: UUID) -> {Domain}Aggregate:

        """Helper: Load aggregate from event store"""
        aggregate = {Domain}
        Aggregate({domain}
        _id)

        # Load events
        events = await self.event_store.get_events(
            aggregate_id={domain}
        _id,
        aggregate_type = "{Domain}"
        )

        if not events:
            raise ValueError(f"{Domain} {domain}_id} not found")

        # Replay events
        from app.infra.event_bus.event_registry import EVENT_TYPE_TO_PYDANTIC_MODEL

        for envelope in events:
            event_class = EVENT_TYPE_TO_PYDANTIC_MODEL.get(envelope.event_type)
            if event_class:
                domain_event = event_class(**envelope.event_data)
                aggregate._apply(domain_event)
                aggregate._version = envelope.aggregate_version

        aggregate.mark_events_committed()
        return aggregate
```

**❌ WRONG PATTERN** (old documentation):
```python
# ❌ This is NOT correct!
@command_handler(MyCommand)
async def handle_my_command(command, deps):  # ❌ Function-based!
    # ❌ No BaseCommandHandler inheritance
    await deps.event_store.save_aggregate(aggregate)  # ❌ Wrong!
```

**✅ CORRECT PATTERN** (from Order Domain):
```python
# ✅ Class-based with BaseCommandHandler
@command_handler(PlaceOrderCommand)
class PlaceOrderHandler(BaseCommandHandler):
    def __init__(self, deps): ...
    async def handle(self, command): ...
    async def _load_aggregate(self, id): ...
```

---

### Step 5: Create Queries & Handlers ⭐ UPDATED (2025-11-22)

**File**: `app/{domain}/queries.py`

**⚠️ CRITICAL (2025-11-22)**: Queries MUST use Pydantic v2 and inherit from `Query`

```python
"""
{Domain} Queries

Queries fetch data from read models (no state changes).

Converted to Pydantic v2 for proper validation and serialization.
"""

from typing import Optional
from uuid import UUID

from app.infra.cqrs.query_bus import Query  # REQUIRED


class Get{Domain}Query(Query):  # MUST inherit from Query
    """Query to get {domain} by ID"""
    {domain}_id: UUID
    user_id: Optional[UUID] = None  # For authorization


class List{Domain}sQuery(Query):  # MUST inherit from Query
    """Query to list {domain}s with filtering"""
    user_id: UUID
    status: Optional[str] = None
    limit: int = 100
    offset: int = 0
```

**File**: `app/{domain}/query_handlers/{domain}_query_handlers.py` ⭐ NEW STRUCTURE

**⚠️ CRITICAL**: Query handlers are CLASS-BASED, extending BaseQueryHandler!

```python
"""
{Domain} Query Handlers

⚠️ CRITICAL: CLASS-BASED handlers extending BaseQueryHandler
"""

import logging
from typing import Optional, TYPE_CHECKING

from app.common.base.base_query_handler import BaseQueryHandler  # ⭐ NEW!
from app.infra.cqrs.decorators import query_handler, cached_query_handler
from app.{domain}.queries import Get{Domain}Query, List{Domain}sQuery
from app.{domain}.read_models import {Domain}ReadModel

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies


# === Get by ID Handler ===

@query_handler(Get{Domain}Query)
class Get{Domain}QueryHandler(BaseQueryHandler[Get{Domain}Query, Optional[{Domain}ReadModel]]):
    """
    ⚠️ UPDATED: CLASS-BASED Handler extending BaseQueryHandler

    Handle Get{Domain}Query with error handling and authorization.

    Type parameters:
    - TQuery: Get{Domain}Query
    - TResult: Optional[{Domain}ReadModel]
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()  # ✅ Initialize base class
        self.read_repo = deps.{domain}_read_repo

    async def handle(self, query: Get{Domain}Query) -> Optional[{Domain}ReadModel]:
        """
        Handle query - INSTANCE METHOD

        Returns: {Domain}ReadModel or raises NotFoundError
        """
        self.log.info(f"Fetching {domain} {query.{domain}_id}")

        # Fetch from repository
        {domain} = await self.read_repo.get_by_id(query.{domain}_id)

        # ✅ Use helper method for error handling
        {domain} = self.handle_not_found(
            resource={domain},
            resource_type="{Domain}",
            resource_id=query.{domain}_id
        )

        # ✅ Use helper method for authorization
        if query.user_id:
            self.validate_resource_ownership(
                resource_user_id={domain}.user_id,
                requesting_user_id=query.user_id,
                resource_type="{domain}"
            )

        return {domain}


# === List Handler (without BaseQueryHandler - simple query) ===

@query_handler(List{Domain}sQuery)
async def handle_list_{domain}s(
    query: List{Domain}sQuery,
    deps: 'HandlerDependencies'
) -> list[{Domain}ReadModel]:
    """
    Handle List{Domain}sQuery

    Simple list queries without error handling can remain function-based,
    but class-based is recommended for consistency.
    """
    read_repo = deps.{domain}_read_repo
    return await read_repo.list_by_user(
        user_id=query.user_id,
        status=query.status,
        limit=query.limit,
        offset=query.offset
    )


# === Cached Query Example ===

@cached_query_handler(Get{Domain}SummaryQuery, ttl=30)
class Get{Domain}SummaryQueryHandler(BaseQueryHandler[Get{Domain}SummaryQuery, {Domain}Summary]):
    """
    Cached query with 30-second TTL

    Use for frequently accessed data that changes infrequently.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.read_repo = deps.{domain}_read_repo

    async def handle(self, query: Get{Domain}SummaryQuery) -> {Domain}Summary:
        self.log.info(f"Fetching {domain} summary for user {query.user_id}")
        return await self.read_repo.get_summary(query.user_id)
```

**❌ WRONG PATTERN** (old documentation):
```python
# ❌ This is NOT correct!
@query_handler(MyQuery)
async def handle_my_query(query, deps):  # ❌ Function-based!
    read_repo = deps.my_read_repo
    return await read_repo.get(query.id)
```

**✅ CORRECT PATTERN** (from Position Domain):
```python
# ✅ Class-based with BaseQueryHandler
@query_handler(GetPositionQuery)
class GetPositionQueryHandler(BaseQueryHandler[GetPositionQuery, Optional[PositionReadModel]]):
    def __init__(self, deps):
        super().__init__()
        self.position_repo = deps.position_read_repo

    async def handle(self, query):
        position = await self.position_repo.get_by_id(query.position_id)

        position = self.handle_not_found(
            resource=position,
            resource_type="Position",
            resource_id=query.position_id
        )

        if query.user_id:
            self.validate_resource_ownership(
                resource_user_id=position.user_id,
                requesting_user_id=query.user_id,
                resource_type="position"
            )

        return position
```

**Key Changes from Old Pattern:**
1. ✅ **Class-based** instead of function-based
2. ✅ **Extends BaseQueryHandler** with generic types
3. ✅ **super().__init__()** call required
4. ✅ **self.log** instead of module-level log
5. ✅ **Helper methods** for error handling and authorization

**When to use BaseQueryHandler:**
- ✅ Queries that need error handling (resource not found)
- ✅ Queries that need authorization (validate user access)
- ✅ Queries that need consistent logging
- ✅ Recommended for ALL query handlers for consistency

**When function-based is OK:**
- Simple list queries without authorization
- System queries (health checks, metrics)
- BUT: class-based is still recommended for consistency

---

### Step 5.5: Create Domain Exceptions & Enums ⭐ NEW (2025-11-22)

**⚠️ REQUIRED**: All domains MUST have `exceptions.py` and `enums.py`

#### **File**: `app/{domain}/exceptions.py`

```python
"""
{Domain} Domain Exceptions

Domain-specific exceptions for {Domain} business logic.
Infrastructure exceptions (auth, not found, etc.) are in app.common.exceptions
"""


class {Domain}DomainError(Exception):
    """Base exception for {Domain} domain"""
    pass


class {Domain}NotFoundError({Domain}DomainError):
    """{Domain} not found"""

    def __init__(self, {domain}_id: str):
        self.{domain}_id = {domain}_id
        super().__init__(f"{Domain} not found: {{domain}_id}")


class Invalid{Domain}StateError({Domain}DomainError):
    """Invalid {domain} state transition"""

    def __init__(self, {domain}_id: str, current_state: str, attempted_transition: str):
        self.{domain}_id = {domain}_id
        self.current_state = current_state
        self.attempted_transition = attempted_transition
        super().__init__(
            f"Invalid state transition for {domain} {{domain}_id}: "
            f"cannot {attempted_transition} from state {current_state}"
        )
```

**Key Points**:
- Domain exceptions = Business logic errors
- Infrastructure exceptions (BrokerAuthError, ResourceNotFoundError, etc.) → use from `app.common.exceptions`
- Inherit from domain base exception for consistency

#### **File**: `app/{domain}/enums.py`

```python
"""
{Domain} Domain Enums

Enumerations for the {Domain} domain.
"""

from enum import Enum


class {Domain}Status(str, Enum):
    """{Domain} status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    DELETED = "deleted"


class {Domain}Type(str, Enum):
    """{Domain} type enumeration"""
    TYPE_A = "type_a"
    TYPE_B = "type_b"
```

**Key Points**:
- Use `str, Enum` for string-based enums (JSON serialization)
- Uppercase constant names (ACTIVE, PENDING, etc.)
- Lowercase values ("active", "pending", etc.)

**Examples from production domains**:
- `app/order/enums.py` - OrderState, OrderType, TimeInForce
- `app/position/enums.py` - PositionStatus, PositionSide, AssetType
- `app/virtual_broker/enums.py` - VirtualAccountStatus, VirtualOrderType
- `app/automation/enums.py` - AutomationStatus, SignalAction

---

### Step 6: Create Projectors

**File**: `app/{domain}/projectors.py`

```python
"""
{Domain} Projectors

Updates read models based on domain events.
"""

import logging
from typing import Dict, Any

from app.infra.read_repos.{domain}_read_repo import {Domain}ReadRepository
from app.infra.event_store.event_envelope import EventEnvelope
from app.infra.event_store.sync_decorators import sync_projection, monitor_projection

log = logging.getLogger("tradecore.{domain}.projectors")


class {Domain}Projector:
    """
    Projector for {Domain} domain events.

    Updates PostgreSQL read model based on events.
    """

    def __init__(self, read_repo: {Domain}ReadRepository):
        self.read_repo = read_repo
        log.info("{Domain}Projector initialized")

    async def handle_event(self, event_dict: Dict[str, Any]) -> None:
        """
        Generic event handler for worker compatibility.
        Routes events to appropriate sync projection methods.
        """
        event_type = event_dict.get("event_type")
        if not event_type:
            log.error(f"Event dict missing event_type: {event_dict}")
            return

        # Create EventEnvelope
        try:
            envelope = EventEnvelope.from_partial_data(event_dict)
        except Exception as e:
            log.error(f"Failed to create EventEnvelope: {e}", exc_info=True)
            return

        # Find sync projection method
        method_name = None
        for attr_name in dir(self):
            if attr_name.startswith('_'):
                continue
            attr = getattr(self, attr_name)
            if hasattr(attr, '_is_sync_projection'):
                if attr._projection_metadata.event_type == event_type:
                    method_name = attr_name
                    break

        if method_name:
            try:
                method = getattr(self, method_name)
                await method(envelope)
            except Exception as e:
                log.error(f"Error in {method_name}: {e}", exc_info=True)
                raise

    # === SYNC PROJECTIONS ===

    @sync_projection("{EventName1}", priority=1, timeout=2.0)
    @monitor_projection
    async def on_{event_name1}(self, envelope: EventEnvelope) -> None:
        """
        Project {EventName1} → Insert/Update {domain} in read model
        """
        event_data = envelope.event_data
        {domain}_id = event_data['{domain}_id']

        log.info(f"[SYNC] Projecting {EventName1}: {domain}_id={domain}_id}")

        # Update read model
        await self.read_repo.upsert({
            '{domain}_id': {domain}_id,
            'field1': event_data['field1'],
            # Map all necessary fields
        })

        log.info(f"✓ {EventName1} projection complete")

    # Add @sync_projection method for EVERY sync event
```

---

### Step 7: Create Read Models

**File**: `app/{domain}/read_models.py`

```python
"""
{Domain} Read Models

Schemas for querying {domain} data.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from decimal import Decimal


@dataclass
class {Domain}ReadModel:
    """
    Read model for {domain}.

    Optimized for queries, not domain logic.
    """
    {domain}_id: str
    status: str
    field1: str
    field2: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Add all fields needed for queries

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            '{domain}Id': self.{domain}_id,
            'status': self.status,
            'field1': self.field1,
            # Map all fields (use camelCase for frontend)
        }
```

---

### Step 8: Register in domain_registry.py

**File**: `app/infra/consumers/domain_registry.py`

**⚠️ 2025-11-13 UPDATE**: NO sync_events.py imports needed!
- Events auto-register with `@domain_event()` decorator
- SYNC projections auto-register with `@sync_projection` decorator
- Domain registry reads from decorator registries

**Step 8a: Create factory function**

```python
def create_{domain}_domain() -> DomainRegistration:
    """Factory function for {domain} domain configuration"""

    # Import events (triggers @domain_event() registration)
    from app.{domain}.events import {EventName1}, {EventName2}

    def {domain}_projector_factory(**kwargs):
        from app.{domain}.projectors import {Domain}Projector
        from app.infra.read_repos.{domain}_read_repo import {Domain}ReadRepository

        read_repo = {Domain}ReadRepository()
        return {Domain}Projector(read_repo)

    from app.infra.consumers.worker_config import {DOMAIN}_EVENTS_TOPIC

    return DomainRegistration(
        name="{domain}",
        topics=[{DOMAIN}_EVENTS_TOPIC],
        projector_factory={domain}_projector_factory,
        event_models={
            "{EventName1}": {EventName1},
            "{EventName2}": {EventName2},
            # Add all events
        },
        projection_config={
            "aggregate_type": "{Domain}",
            "transport_topic": {DOMAIN}_EVENTS_TOPIC
        },
        # NO sync_events parameter - decorator handles it!
        enable_sequence_tracking=True
    )
```

**Step 8b: Register in create_domain_registry()**

```python
def create_domain_registry() -> DomainRegistry:
    registry = DomainRegistry()

    # ... existing registrations
    registry.register(create_{domain}_domain())  # ADD THIS

    return registry
```

**IMPORTANT**:
- NO `load_domain_sync_events()` calls needed
- NO `sync_events` / `sync_event_config` parameters in DomainRegistration
- System automatically discovers SYNC events from `@sync_projection` decorators

---

### Step 9: Update handler_dependencies.py

**File**: `app/infra/cqrs/handler_dependencies.py`

```python
# In TYPE_CHECKING section:
if TYPE_CHECKING:
    from app.infra.read_repos.{domain}_read_repo import {Domain}ReadRepository

# In HandlerDependencies dataclass:
@dataclass
class HandlerDependencies:
    # ... existing fields
    {domain}_read_repo: Optional['{Domain}ReadRepository'] = None
```

---

### Step 10: Update CQRS Registration

**File**: `app/core/startup/cqrs.py`

**Step 11a: Import handlers**

```python
def _import_all_handler_modules():
    # ... existing imports
    import app.{domain}.handlers  # ADD THIS
```

**Step 11b: Initialize read repo**

```python
async def register_cqrs_handlers():
    # ... existing registrations

    # {Domain} read repo
    from app.infra.read_repos.{domain}_read_repo import {Domain}ReadRepository
    {domain}_read_repo = {Domain}ReadRepository(pg_client)

    # Update deps
    deps.{domain}_read_repo = {domain}_read_repo
```

---

### Step 11: Add WSE Integration (if real-time updates needed)

**File**: `app/infra/reactive_bus/reactive_core.py`

```python
INTERNAL_TO_WS_EVENT_TYPE_MAP = {
    # ... existing mappings

    # {Domain} events
    '{EventName1}': '{domain}_update',
    '{EventName2}': '{domain}_update',
    '{EventName3}': '{domain}_remove',
}
```

**File**: `app/infra/reactive_bus/wse_notifier_service.py`

```python
# Add subscription method
async def _subscribe_to_{domain}_events(self) -> None:
    """Subscribe to {domain} domain events"""
    topic = "domain.{domain}-events"

    sub_id = await self._event_bus.subscribe(
        topic,
        self._handle_{domain}_event
    )
    self._subscriptions[topic] = sub_id

# Add handler method
async def _handle_{domain}_event(self, event: Dict[str, Any]) -> None:
    """Handle {domain} domain event"""
    # Similar to other event handlers

# Add transformer method
def _transform_{domain}_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
    """Transform {domain} event to WSE format"""
    return {
        "{domain}_id": event.get("aggregate_id"),
        "field1": event.get("field1"),
        # Transform all fields
    }

# Call subscription in start()
async def start(self):
    # ... existing code
    asyncio.create_task(self._subscribe_to_{domain}_events())
```

---

### Step 12: Create API Router

**File**: `app/api/routers/{domain}_router.py`

```python
"""
{Domain} API Router
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.api.models.{domain}_models import (
    {Domain}CreateRequest,
    {Domain}Response
)
from app.infra.cqrs.command_bus import CommandBus
from app.infra.cqrs.query_bus import QueryBus
from app.{domain}.commands import {CommandName1}
from app.{domain}.queries import Get{Domain}Query

# ⚠️ IMPORTANT: Do NOT include prefix here - it's added in app/core/routes.py
# ❌ WRONG: router = APIRouter(prefix="/api/{domain}s")
# ❌ WRONG: router = APIRouter(prefix="/{domain}s")
# ✅ CORRECT: router = APIRouter()
router = APIRouter()


@router.post("/", response_model={Domain}Response)
async def create_{domain}(
    request: {Domain}CreateRequest,
    command_bus: CommandBus = Depends(),
    query_bus: QueryBus = Depends()
):
    """Create new {domain}"""

    # Send command
    command = {CommandName1}(
        {domain}_id=generate_id(),
        param1=request.param1
    )
    await command_bus.send(command)

    # Query result
    query = Get{Domain}Query({domain}_id=command.{domain}_id)
    result = await query_bus.query(query)

    return {Domain}Response.from_read_model(result)


@router.get("/{domain_id}", response_model={Domain}Response)
async def get_{domain}(
    {domain}_id: str,
    query_bus: QueryBus = Depends()
):
    """Get {domain} by ID"""
    query = Get{Domain}Query({domain}_id={domain}_id)
    result = await query_bus.query(query)

    if not result:
        raise HTTPException(404, f"{Domain} not found")

    return {Domain}Response.from_read_model(result)
```

**Register in** `app/core/routes.py`:

```python
from app.api.routers.{domain}_router import router as {domain}_router

def register_core_routers(app: FastAPI):
    """Register core application routers"""
    # ... existing routers
    app.include_router({domain}_router, prefix="/{domain}s", tags=["{Domain}s"])
    # ⚠️ PREFIX is added HERE, not in the router file!
```

**Pattern Explanation:**
- ✅ Router file (`{domain}_router.py`): `router = APIRouter()` - NO prefix
- ✅ Routes registration (`app/core/routes.py`): `app.include_router({domain}_router, prefix="/{domain}s")` - prefix HERE
- ❌ NEVER put `/api/` in prefix - FastAPI handles this automatically

---

### Step 13: Create Database Schema

**File**: `app/database/schemas/{domain}_schema.sql`

```sql
-- {Domain} Read Model Table

CREATE TABLE IF NOT EXISTS {domain}s (
    {domain}_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL,
    field1 TEXT NOT NULL,
    field2 TEXT,

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,

    -- Indexes
    CONSTRAINT {domain}s_user_id_idx
);

CREATE INDEX IF NOT EXISTS {domain}s_user_id_idx ON {domain}s(user_id);
CREATE INDEX IF NOT EXISTS {domain}s_status_idx ON {domain}s(status);
```

**Create Read Repository**:

**File**: `app/infra/read_repos/{domain}_read_repo.py`

```python
"""
{Domain} Read Repository
"""

from typing import Optional, List
from uuid import UUID

from app.{domain}.read_models import {Domain}ReadModel
from app.infra.persistence.pg_client import PGClient


class {Domain}ReadRepository:
    """Repository for {domain} read model"""

    def __init__(self, pg_client: Optional[PGClient] = None):
        from app.infra.persistence.pg_client import db
        self.pg = pg_client or db

    async def get_by_id(self, {domain}_id: str) -> Optional[{Domain}ReadModel]:
        """Get {domain} by ID"""
        query = "SELECT * FROM {domain}s WHERE {domain}_id = $1"
        row = await self.pg.fetchrow(query, UUID({domain}_id))

        if not row:
            return None

        return {Domain}ReadModel(
            {domain}_id=str(row['{domain}_id']),
            status=row['status'],
            field1=row['field1'],
            # Map all fields
        )

    async def upsert(self, data: dict) -> None:
        """Insert or update {domain}"""
        query = """
        INSERT INTO {domain}s (
            {domain}_id, user_id, status, field1, created_at, updated_at
        ) VALUES ($1, $2, $3, $4, NOW(), NOW())
        ON CONFLICT ({domain}_id)
        DO UPDATE SET
            status = EXCLUDED.status,
            field1 = EXCLUDED.field1,
            updated_at = NOW()
        """

        await self.pg.execute(
            query,
            UUID(data['{domain}_id']),
            UUID(data['user_id']),
            data['status'],
            data['field1']
        )
```

---

### Step 14: Write Tests

**File**: `tests/unit/{domain}/test_{domain}_aggregate.py`

```python
"""
Tests for {Domain} aggregate
"""

import pytest
from app.{domain}.aggregate import {Domain}Aggregate
from app.{domain}.events import {EventName1}


def test_{domain}_creation():
    """Test {domain} aggregate creation"""
    aggregate = {Domain}Aggregate({domain}_id="test-123")
    assert aggregate.{domain}_id == "test-123"


def test_method1_emits_event():
    """Test method1 emits correct event"""
    aggregate = {Domain}Aggregate({domain}_id="test-123")

    aggregate.method1("value1")

    assert len(aggregate.uncommitted_events) == 1
    event = aggregate.uncommitted_events[0]
    assert isinstance(event, {EventName1})
    assert event.field1 == "value1"
```

**File**: `tests/integration/{domain}/test_{domain}_handlers.py`

```python
"""
Integration tests for {domain} handlers
"""

import pytest
from app.{domain}.commands import {CommandName1}
from app.{domain}.queries import Get{Domain}Query


@pytest.mark.asyncio
async def test_create_{domain}(command_bus, query_bus):
    """Test {domain} creation end-to-end"""

    # Send command
    command = {CommandName1}(
        {domain}_id="test-123",
        param1="value1"
    )
    await command_bus.send(command)

    # Query result
    query = Get{Domain}Query({domain}_id="test-123")
    result = await query_bus.query(query)

    assert result is not None
    assert result.{domain}_id == "test-123"
    assert result.field1 == "value1"
```

---

## 🎯 Derivatives Support (Options & Futures) ⭐ NEW!

**Added**: November 1, 2025
**Status**: Required for trading-related domains (ORDER, POSITION, AUTOMATION, PORTFOLIO)

### When to Add Derivatives Support

Add derivatives support to your domain if it handles:

- ✅ **Orders** - Placing/managing derivative orders
- ✅ **Positions** - Tracking derivative positions
- ✅ **Automations/Strategies** - Trading derivatives via automation
- ✅ **Portfolio** - Calculating P&L for derivatives
- ❌ **Accounts** - No need (account balance doesn't care about asset type)
- ❌ **Connections** - No need (connection doesn't care what you trade)
- ❌ **Users** - No need (user management independent of assets)

**Rule of Thumb**: If your domain processes trades, positions, or P&L, add derivatives support.

---

### Pattern Overview

The derivatives support pattern includes:

1. **Asset Type Enum** - Distinguishes stocks/options/futures
2. **Value Objects** - OptionDetails and FutureDetails (immutable)
3. **Database Columns** - 17 additional columns for derivative specifications
4. **Event Fields** - Flattened derivative fields in events
5. **Command Fields** - Value objects in commands, flattened for infrastructure
6. **API Models** - camelCase derivative fields matching TradersPost format
7. **Validation** - Asset type consistency validation

**Reference Implementation**: `app/order/` (Order Domain) - fully implemented

---

### Step 1: Add Enumerations

**File**: `app/{domain}/enums.py`

```python
from enum import Enum

class AssetType(str, Enum):
    """Asset type enumeration for multi-asset support"""
    STOCK = "stock"
    OPTION = "option"
    FUTURE = "future"
    FUTURE_OPTION = "future_option"  # Options on futures
    CRYPTO = "crypto"  # Cryptocurrency (spot trading) ⭐ Added 2025-11-01

class OptionType(str, Enum):
    """Option contract type"""
    CALL = "call"
    PUT = "put"

class OptionAction(str, Enum):
    """Option trading action"""
    BUY_TO_OPEN = "buy_to_open"      # Open long position
    BUY_TO_CLOSE = "buy_to_close"    # Close short position
    SELL_TO_OPEN = "sell_to_open"    # Open short position
    SELL_TO_CLOSE = "sell_to_close"  # Close long position
```

**Why these enums?**
- `AssetType` - Determines which value object to use
- `OptionType` - Required for all option contracts
- `OptionAction` - Trading direction for options (different from simple buy/sell)

---

### Step 2: Create Value Objects

**File**: `app/{domain}/value_objects.py`

```python
"""
{Domain} Value Objects

Immutable value objects for domain entities.
"""

from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
from datetime import datetime

from app.{domain}.enums import OptionType, OptionAction


@dataclass(frozen=True)  # ✅ IMMUTABLE
class OptionDetails:
    """
    Option contract details - immutable value object

    Used for OPTION and FUTURE_OPTION asset types.
    Frozen=True ensures immutability after creation.
    """
    underlying_symbol: str              # e.g., "AAPL"
    strike_price: Decimal              # Strike/exercise price
    expiration_date: datetime          # Contract expiration
    option_type: OptionType            # CALL or PUT
    option_action: Optional[OptionAction] = None  # Trading action
    contract_size: int = 100           # Usually 100 shares per contract
    multiplier: Decimal = Decimal("1") # Price multiplier (usually 1 or 100)

    def __post_init__(self):
        """Validate option details"""
        if self.strike_price <= 0:
            raise ValueError(f"Strike price must be positive, got {self.strike_price}")
        if self.contract_size <= 0:
            raise ValueError(f"Contract size must be positive, got {self.contract_size}")
        if self.expiration_date.date() < datetime.now().date():
            raise ValueError("Expiration date is in the past")

    @property
    def symbol_representation(self) -> str:
        """
        Generate OCC (Options Clearing Corporation) format symbol.

        Format: {SYMBOL}{YYMMDD}{C/P}{STRIKE*1000:08d}
        Example: AAPL250117C00150000 (AAPL $150 Call expiring Jan 17, 2025)
        """
        exp_str = self.expiration_date.strftime("%y%m%d")
        option_char = "C" if self.option_type == OptionType.CALL else "P"
        strike_int = int(self.strike_price * 1000)  # Convert to cents
        return f"{self.underlying_symbol}{exp_str}{option_char}{strike_int:08d}"


@dataclass(frozen=True)  # ✅ IMMUTABLE
class FutureDetails:
    """
    Futures contract details - immutable value object

    Used for FUTURE and FUTURE_OPTION asset types.
    Includes contract specifications and exchange info.
    """
    underlying_symbol: str             # e.g., "ES" (E-mini S&P 500)
    contract_month: str                # e.g., "202503" (March 2025)
    expiration_date: datetime          # Contract expiration
    contract_size: Decimal             # Size of one contract (e.g., 50 for ES)
    tick_size: Decimal                 # Minimum price increment
    tick_value: Decimal                # Dollar value of one tick
    multiplier: Decimal = Decimal("1") # Price multiplier
    exchange: Optional[str] = None     # e.g., "CME", "CBOT"
    product_code: Optional[str] = None # Exchange-specific code

    def __post_init__(self):
        """Validate future details"""
        if self.contract_size <= 0:
            raise ValueError(f"Contract size must be positive, got {self.contract_size}")
        if self.tick_size <= 0:
            raise ValueError(f"Tick size must be positive, got {self.tick_size}")
        if self.tick_value <= 0:
            raise ValueError(f"Tick value must be positive, got {self.tick_value}")
```

**Key Points:**
- `frozen=True` - Immutability prevents accidental modification
- `__post_init__` - Validation ensures data integrity
- `symbol_representation` - Helper method for OCC format
- Both value objects follow same pattern for consistency

---

### Step 3: Update Aggregate

**File**: `app/{domain}/aggregate.py`

```python
from app.{domain}.value_objects import OptionDetails, FutureDetails
from app.{domain}.enums import AssetType

class {Domain}Aggregate:
    def __init__(self, {domain}_id: UUID):
        # ... existing fields

        # ✅ NEW: Derivatives support
        self.asset_type: AssetType = AssetType.STOCK
        self.option_details: Optional[OptionDetails] = None
        self.future_details: Optional[FutureDetails] = None

    @classmethod
    def create(
        cls,
        # ... existing params
        asset_type: AssetType = AssetType.STOCK,
        option_details: Optional[OptionDetails] = None,
        future_details: Optional[FutureDetails] = None,
    ) -> "{Domain}Aggregate":
        """Create new aggregate with optional derivatives"""
        aggregate_id = uuid4()
        aggregate = cls(aggregate_id)

        # ✅ Validate consistency
        cls._validate_asset_type_details(asset_type, option_details, future_details)

        # Emit creation event (with flattened derivatives)
        event = {Domain}CreatedEvent(
            {domain}_id=aggregate_id,
            # ... existing fields
            # ✅ Flatten value objects for serialization
            asset_type=asset_type,
            option_underlying_symbol=option_details.underlying_symbol if option_details else None,
            option_strike_price=option_details.strike_price if option_details else None,
            option_expiration_date=option_details.expiration_date if option_details else None,
            option_type=option_details.option_type if option_details else None,
            option_action=option_details.option_action if option_details else None,
            option_contract_size=option_details.contract_size if option_details else None,
            option_multiplier=option_details.multiplier if option_details else None,
            future_underlying_symbol=future_details.underlying_symbol if future_details else None,
            future_contract_month=future_details.contract_month if future_details else None,
            future_expiration_date=future_details.expiration_date if future_details else None,
            future_contract_size=future_details.contract_size if future_details else None,
            future_tick_size=future_details.tick_size if future_details else None,
            future_tick_value=future_details.tick_value if future_details else None,
            future_multiplier=future_details.multiplier if future_details else None,
            future_exchange=future_details.exchange if future_details else None,
            future_product_code=future_details.product_code if future_details else None,
        )
        aggregate.apply(event)
        return aggregate

    @staticmethod
    def _validate_asset_type_details(
        asset_type: AssetType,
        option_details: Optional[OptionDetails],
        future_details: Optional[FutureDetails]
    ):
        """
        Validate consistency between asset_type and details.

        Rules:
        - STOCK: no option/future details
        - CRYPTO: no option/future details (treated like stocks) ⭐ Added 2025-11-01
        - OPTION: requires option_details, no future_details
        - FUTURE: requires future_details, no option_details
        - FUTURE_OPTION: requires both option_details and future_details
        """
        if asset_type == AssetType.STOCK:
            if option_details or future_details:
                raise ValueError("STOCK entities cannot have option or future details")

        elif asset_type == AssetType.CRYPTO:
            if option_details or future_details:
                raise ValueError("CRYPTO entities cannot have option or future details")

        elif asset_type == AssetType.OPTION:
            if not option_details:
                raise ValueError("OPTION entities require option_details")
            if future_details:
                raise ValueError("OPTION entities cannot have future_details")

        elif asset_type == AssetType.FUTURE:
            if not future_details:
                raise ValueError("FUTURE entities require future_details")
            if option_details:
                raise ValueError("FUTURE entities cannot have option_details")

        elif asset_type == AssetType.FUTURE_OPTION:
            if not option_details or not future_details:
                raise ValueError("FUTURE_OPTION entities require both option and future details")

    def _apply_{domain}_created_event(self, event: {Domain}CreatedEvent):
        """Apply creation event - reconstructs value objects from flattened data"""
        # ... existing field assignments

        # ✅ Reconstruct value objects from flattened event data
        self.asset_type = event.asset_type

        if event.option_underlying_symbol:
            self.option_details = OptionDetails(
                underlying_symbol=event.option_underlying_symbol,
                strike_price=event.option_strike_price,
                expiration_date=event.option_expiration_date,
                option_type=event.option_type,
                option_action=event.option_action,
                contract_size=event.option_contract_size or 100,
                multiplier=event.option_multiplier or Decimal("1")
            )

        if event.future_underlying_symbol:
            self.future_details = FutureDetails(
                underlying_symbol=event.future_underlying_symbol,
                contract_month=event.future_contract_month,
                expiration_date=event.future_expiration_date,
                contract_size=event.future_contract_size,
                tick_size=event.future_tick_size,
                tick_value=event.future_tick_value,
                multiplier=event.future_multiplier or Decimal("1"),
                exchange=event.future_exchange,
                product_code=event.future_product_code
            )
```

**Why flatten in events?**
- Events must be serializable to JSON
- Value objects (frozen dataclasses) don't serialize well
- Flattening = easier Redpanda/event store persistence
- Reconstruction in `_apply` methods maintains domain logic

---

### Step 4: Update Events

**File**: `app/{domain}/events.py`

```python
class {Domain}CreatedEvent(BaseEvent):
    """
    {Domain} created event with derivatives support

    ⚠️ IMPORTANT: Derivative fields are FLATTENED for serialization
    """
    event_type: Literal["{Domain}CreatedEvent"] = "{Domain}CreatedEvent"
    {domain}_id: UUID
    # ... existing fields

    # ✅ NEW: Derivatives support (17 flattened fields)
    asset_type: AssetType = AssetType.STOCK

    # Option fields (7)
    option_underlying_symbol: Optional[str] = None
    option_strike_price: Optional[Decimal] = None
    option_expiration_date: Optional[datetime] = None
    option_type: Optional[OptionType] = None
    option_action: Optional[OptionAction] = None
    option_contract_size: Optional[int] = None
    option_multiplier: Optional[Decimal] = None

    # Future fields (10)
    future_underlying_symbol: Optional[str] = None
    future_contract_month: Optional[str] = None
    future_expiration_date: Optional[datetime] = None
    future_contract_size: Optional[Decimal] = None
    future_tick_size: Optional[Decimal] = None
    future_tick_value: Optional[Decimal] = None
    future_multiplier: Optional[Decimal] = None
    future_exchange: Optional[str] = None
    future_product_code: Optional[str] = None

    occurred_at: datetime = Field(default_factory=lambda: datetime.now())
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

**Total: 17 derivative fields** (1 asset_type + 7 option + 10 future - 1 overlap = 17 unique)

---

### Step 4: Update Commands

**File**: `app/{domain}/commands.py`

```python
@dataclass
class Create{Domain}Command:
    """Create new {domain} with optional derivatives"""
    {domain}_id: UUID
    # ... existing fields

    # ✅ NEW: Derivatives support (value objects, not flattened)
    asset_type: AssetType = AssetType.STOCK
    option_details: Optional[OptionDetails] = None
    future_details: Optional[FutureDetails] = None

    metadata: Dict = field(default_factory=dict)
```

**Note**: Commands use value objects (not flattened) because they're domain models, not serialization models.

---

### Step 5: Update Database Schema

**File**: `app/database/schemas/{domain}_schema.sql`

```sql
CREATE TABLE IF NOT EXISTS {domain}s (
    {domain}_id UUID PRIMARY KEY,
    -- ... existing columns

    -- ✅ NEW: Derivatives support (17 columns)
    asset_type VARCHAR(20) DEFAULT 'stock' NOT NULL,

    -- Option fields (7)
    option_underlying_symbol VARCHAR(20),
    option_strike_price DECIMAL(20, 8),
    option_expiration_date TIMESTAMP WITH TIME ZONE,
    option_type VARCHAR(10),  -- 'call' or 'put'
    option_action VARCHAR(20),  -- 'buy_to_open', 'sell_to_close', etc.
    option_contract_size INTEGER DEFAULT 100,
    option_multiplier DECIMAL(10, 4) DEFAULT 1,

    -- Future fields (9)
    future_underlying_symbol VARCHAR(20),
    future_contract_month VARCHAR(10),  -- e.g., '202503'
    future_expiration_date TIMESTAMP WITH TIME ZONE,
    future_contract_size DECIMAL(20, 8),
    future_tick_size DECIMAL(20, 8),
    future_tick_value DECIMAL(20, 8),
    future_multiplier DECIMAL(10, 4) DEFAULT 1,
    future_exchange VARCHAR(20),
    future_product_code VARCHAR(20),

    -- ... rest of schema
);

-- ✅ Add check constraint for asset_type (⭐ Updated 2025-11-01: Added 'crypto')
ALTER TABLE {domain}s ADD CONSTRAINT {domain}s_asset_type_check
    CHECK (asset_type IN ('stock', 'option', 'future', 'future_option', 'crypto'));

-- ✅ Add check constraint for option_type
ALTER TABLE {domain}s ADD CONSTRAINT {domain}s_option_type_check
    CHECK (option_type IS NULL OR option_type IN ('call', 'put'));

-- ✅ Add check constraint for option_action
ALTER TABLE {domain}s ADD CONSTRAINT {domain}s_option_action_check
    CHECK (option_action IS NULL OR option_action IN ('buy_to_open', 'buy_to_close', 'sell_to_open', 'sell_to_close'));

-- ✅ Add indexes for derivative queries
CREATE INDEX IF NOT EXISTS {domain}s_asset_type_idx ON {domain}s(asset_type);
CREATE INDEX IF NOT EXISTS {domain}s_option_underlying_idx ON {domain}s(option_underlying_symbol) WHERE option_underlying_symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS {domain}s_future_underlying_idx ON {domain}s(future_underlying_symbol) WHERE future_underlying_symbol IS NOT NULL;
```

**Best Practices:**
- All derivative columns Optional (NULL allowed) for backward compatibility
- Defaults: `asset_type = 'stock'`, contract sizes = 100, multipliers = 1
- Check constraints ensure data integrity
- Partial indexes for derivatives (WHERE NOT NULL) save space

---

### Step 6: Update Projectors

**File**: `app/{domain}/projectors.py`

```python
@sync_projection("{Domain}CreatedEvent", priority=1, timeout=2.0)
@monitor_projection
async def on_{domain}_created(self, envelope: EventEnvelope) -> None:
    """Project {Domain}CreatedEvent → Insert into read model with derivatives"""
    event_data = envelope.event_data
    {domain}_id = uuid.UUID(event_data['{domain}_id'])

    log.info(f"[SYNC] Projecting {Domain}CreatedEvent: {domain}_id={domain}_id}")

    await pg_db_proxy.execute(
        """
        INSERT INTO {domain}s (
            {domain}_id,
            -- ... existing fields
            -- ✅ NEW: Derivative fields (17 columns)
            asset_type,
            option_underlying_symbol, option_strike_price, option_expiration_date,
            option_type, option_action, option_contract_size, option_multiplier,
            future_underlying_symbol, future_contract_month, future_expiration_date,
            future_contract_size, future_tick_size, future_tick_value,
            future_multiplier, future_exchange, future_product_code,
            created_at, updated_at
        ) VALUES (
            $1, -- {domain}_id
            -- ... existing values
            -- ✅ NEW: Derivative values
            $N, $N+1, $N+2, $N+3, $N+4, $N+5, $N+6, $N+7,
            $N+8, $N+9, $N+10, $N+11, $N+12, $N+13, $N+14, $N+15, $N+16,
            $N+17, $N+18
        )
        """,
        {domain}_id,
        # ... existing values
        # ✅ NEW: Insert derivative values
        event_data.get('asset_type', 'stock'),
        event_data.get('option_underlying_symbol'),
        Decimal(str(event_data['option_strike_price'])) if event_data.get('option_strike_price') else None,
        event_data.get('option_expiration_date'),
        event_data.get('option_type'),
        event_data.get('option_action'),
        event_data.get('option_contract_size'),
        Decimal(str(event_data['option_multiplier'])) if event_data.get('option_multiplier') else None,
        event_data.get('future_underlying_symbol'),
        event_data.get('future_contract_month'),
        event_data.get('future_expiration_date'),
        Decimal(str(event_data['future_contract_size'])) if event_data.get('future_contract_size') else None,
        Decimal(str(event_data['future_tick_size'])) if event_data.get('future_tick_size') else None,
        Decimal(str(event_data['future_tick_value'])) if event_data.get('future_tick_value') else None,
        Decimal(str(event_data['future_multiplier'])) if event_data.get('future_multiplier') else None,
        event_data.get('future_exchange'),
        event_data.get('future_product_code'),
        envelope.stored_at,
        envelope.stored_at
    )

    log.info(f"✓ {Domain} {domain}_id} inserted with asset_type={event_data.get('asset_type', 'stock')}")
```

**Key Points:**
- Use `.get()` for all derivative fields (may be None)
- Convert Decimal strings: `Decimal(str(value))` for numeric fields
- Pass datetime objects directly (asyncpg handles them)

---

### Step 7: Update Read Models

**File**: `app/{domain}/read_models.py`

```python
@dataclass
class {Domain}ReadModel:
    """Read model for {domain} with derivatives support"""
    {domain}_id: UUID
    # ... existing fields

    # ✅ NEW: Derivatives support
    asset_type: str = "stock"

    # Option fields
    option_underlying_symbol: Optional[str] = None
    option_strike_price: Optional[Decimal] = None
    option_expiration_date: Optional[datetime] = None
    option_type: Optional[str] = None
    option_action: Optional[str] = None
    option_contract_size: Optional[int] = None
    option_multiplier: Optional[Decimal] = None

    # Future fields
    future_underlying_symbol: Optional[str] = None
    future_contract_month: Optional[str] = None
    future_expiration_date: Optional[datetime] = None
    future_contract_size: Optional[Decimal] = None
    future_tick_size: Optional[Decimal] = None
    future_tick_value: Optional[Decimal] = None
    future_multiplier: Optional[Decimal] = None
    future_exchange: Optional[str] = None
    future_product_code: Optional[str] = None

    created_at: datetime
    updated_at: Optional[datetime] = None
```

---

### Step 8: Update API Models

**File**: `app/api/models/{domain}_api_models.py`

```python
class Create{Domain}Request(BaseModel):
    """API request for creating {domain} with derivatives"""
    {domain}Id: Optional[UUID] = Field(None, description="{Domain} ID")
    # ... existing fields

    # ✅ NEW: Derivatives support (camelCase for frontend compatibility)
    assetType: str = Field("stock", description="Asset type: stock, option, future, future_option, crypto")

    # Option fields
    optionUnderlyingSymbol: Optional[str] = Field(None, description="Option underlying symbol")
    optionStrikePrice: Optional[Decimal] = Field(None, description="Option strike price")
    optionExpirationDate: Optional[datetime] = Field(None, description="Option expiration date")
    optionType: Optional[str] = Field(None, description="Option type: call or put")
    optionAction: Optional[str] = Field(None, description="Option action: buy_to_open, sell_to_close, etc.")
    optionContractSize: Optional[int] = Field(None, description="Option contract size (default 100)")
    optionMultiplier: Optional[Decimal] = Field(None, description="Option price multiplier (default 1)")

    # Future fields
    futureUnderlyingSymbol: Optional[str] = Field(None, description="Future underlying symbol")
    futureContractMonth: Optional[str] = Field(None, description="Future contract month (e.g., 202503)")
    futureExpirationDate: Optional[datetime] = Field(None, description="Future expiration date")
    futureContractSize: Optional[Decimal] = Field(None, description="Future contract size")
    futureTickSize: Optional[Decimal] = Field(None, description="Future minimum tick size")
    futureTickValue: Optional[Decimal] = Field(None, description="Future dollar value per tick")
    futureMultiplier: Optional[Decimal] = Field(None, description="Future price multiplier")
    futureExchange: Optional[str] = Field(None, description="Future exchange (e.g., CME)")
    futureProductCode: Optional[str] = Field(None, description="Future product code")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class {Domain}Response(BaseModel):
    """API response for {domain} with derivatives"""
    {domain}Id: UUID
    # ... existing fields

    # ✅ NEW: Derivatives support (camelCase)
    assetType: str

    # Option fields
    optionUnderlyingSymbol: Optional[str] = None
    optionStrikePrice: Optional[Decimal] = None
    optionExpirationDate: Optional[datetime] = None
    optionType: Optional[str] = None
    optionAction: Optional[str] = None
    optionContractSize: Optional[int] = None
    optionMultiplier: Optional[Decimal] = None

    # Future fields
    futureUnderlyingSymbol: Optional[str] = None
    futureContractMonth: Optional[str] = None
    futureExpirationDate: Optional[datetime] = None
    futureContractSize: Optional[Decimal] = None
    futureTickSize: Optional[Decimal] = None
    futureTickValue: Optional[Decimal] = None
    futureMultiplier: Optional[Decimal] = None
    futureExchange: Optional[str] = None
    futureProductCode: Optional[str] = None

    createdAt: datetime
    updatedAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
```

**Why camelCase?**
- Frontend compatibility (JavaScript/TypeScript convention)
- TradersPost webhook format uses camelCase
- Consistency across API layer

---

### Step 9: Update API Router

**File**: `app/api/routers/{domain}_router.py`

```python
@router.post("/", response_model={Domain}Response)
async def create_{domain}(
    request: Create{Domain}Request,
    command_bus: CommandBus = Depends()
):
    """Create {domain} with optional derivatives support"""

    # ✅ Build value objects from request
    option_details = None
    if request.optionUnderlyingSymbol:
        option_details = OptionDetails(
            underlying_symbol=request.optionUnderlyingSymbol,
            strike_price=request.optionStrikePrice,
            expiration_date=request.optionExpirationDate,
            option_type=OptionType(request.optionType),
            option_action=OptionAction(request.optionAction) if request.optionAction else None,
            contract_size=request.optionContractSize or 100,
            multiplier=request.optionMultiplier or Decimal("1")
        )

    future_details = None
    if request.futureUnderlyingSymbol:
        future_details = FutureDetails(
            underlying_symbol=request.futureUnderlyingSymbol,
            contract_month=request.futureContractMonth,
            expiration_date=request.futureExpirationDate,
            contract_size=request.futureContractSize,
            tick_size=request.futureTickSize,
            tick_value=request.futureTickValue,
            multiplier=request.futureMultiplier or Decimal("1"),
            exchange=request.futureExchange,
            product_code=request.futureProductCode
        )

    # ✅ Create command with value objects
    command = Create{Domain}Command(
        {domain}_id=request.{domain}Id or uuid4(),
        # ... existing fields
        asset_type=AssetType(request.assetType),
        option_details=option_details,
        future_details=future_details,
        metadata=request.metadata
    )

    await command_bus.send(command)

    # Query and return
    # ... (existing query logic)
```

---

### Step 10: Update Read Repository

**File**: `app/infra/read_repos/{domain}_read_repo.py`

Update all SELECT queries to include derivative columns:

```python
async def get_by_id(self, {domain}_id: UUID) -> Optional[{Domain}ReadModel]:
    """Get {domain} by ID with derivatives"""
    query = """
        SELECT
            {domain}_id, status, field1,
            -- ✅ Include all 17 derivative columns
            asset_type,
            option_underlying_symbol, option_strike_price, option_expiration_date,
            option_type, option_action, option_contract_size, option_multiplier,
            future_underlying_symbol, future_contract_month, future_expiration_date,
            future_contract_size, future_tick_size, future_tick_value,
            future_multiplier, future_exchange, future_product_code,
            created_at, updated_at
        FROM {domain}s
        WHERE {domain}_id = $1
    """

    row = await pg_db_proxy.fetchrow(query, {domain}_id)
    if not row:
        return None

    return {Domain}ReadModel(**dict(row))
```

---

### Derivatives Support Checklist

When adding derivatives to your domain:

- [ ] Added `AssetType`, `OptionType`, `OptionAction` enums to `enums.py`
- [ ] Created `OptionDetails` and `FutureDetails` value objects in `value_objects.py`
- [ ] Added `asset_type`, `option_details`, `future_details` fields to aggregate
- [ ] Implemented `_validate_asset_type_details()` static method
- [ ] Updated `create()` method to accept derivatives and flatten in event
- [ ] Updated `_apply` methods to reconstruct value objects from flattened data
- [ ] Added 17 flattened fields to all relevant events
- [ ] Added value object fields to all relevant commands
- [ ] Added 17 columns to database schema with constraints
- [ ] Added asset_type index and partial indexes for derivatives
- [ ] Updated projectors to insert/update all 17 derivative columns
- [ ] Added 17 fields to read models
- [ ] Added camelCase derivative fields to API request/response models
- [ ] Updated API router to build value objects from camelCase fields
- [ ] Updated all read repository SELECT queries to include derivatives
- [ ] Tested stock orders (default, no derivatives)
- [ ] Tested option orders (option_details present)
- [ ] Tested future orders (future_details present)
- [ ] Tested future option orders (both details present)
- [ ] Verified validation rejects invalid combinations

---

### Reference Implementation

**Complete example**: `app/order/` (Order Domain)

Files to reference:
- `app/order/enums.py` - AssetType, OptionType, OptionAction
- `app/order/value_objects.py` - OptionDetails, FutureDetails with OCC format
- `app/order/aggregate.py` - Validation and flattening pattern
- `app/order/events.py` - 17 flattened fields in OrderPlacedEvent
- `app/order/projectors.py` - Inserting 17 columns
- `app/database/tradecore.sql` - 17 columns with constraints
- `app/api/models/order_api_models.py` - camelCase API models
- `app/api/routers/order_router.py` - Building value objects from request

**Documentation**: `docs/mvp/04-domains/order-domain-spec.md` (lines 28-137, derivatives section)

---

### TradersPost Compatibility

The derivatives implementation is fully compatible with TradersPost webhook format:

```json
{
  "symbol": "AAPL250117C00150000",
  "assetType": "option",
  "optionUnderlyingSymbol": "AAPL",
  "optionStrikePrice": 150.00,
  "optionExpirationDate": "2025-01-17T00:00:00Z",
  "optionType": "call",
  "optionAction": "buy_to_open",
  "optionContractSize": 100,
  "optionMultiplier": 1
}
```

TradersPost already sends these fields - your domain just needs to process them!

---

## ✅ Final Verification Checklist

Before considering the domain complete:

- [ ] **Decision documented**: Which events are sync vs async (with reasoning)
- [ ] All sync projections have `@sync_projection` decorators
- [ ] NO `sync_events.py` file (deprecated - removed)
- [ ] Projector methods use `EventEnvelope` signature
- [ ] Domain registered in domain_registry.py
- [ ] HandlerDependencies includes read repo
- [ ] CQRS startup registers read repo
- [ ] WSE integration complete (if needed)
- [ ] API router created and registered
- [ ] Database schema created
- [ ] Read repository implemented
- [ ] Unit tests written
- [ ] Integration tests written
- [ ] Documentation updated

---

## 📚 Reference Examples

**Well-structured domains to reference:**

1. **Order Domain** (`app/order/`)
   - Complete trading event lifecycle
   - Complex state machine with `@sync_projection` decorators
   - Position affecting events

2. **Broker Account Domain** (`app/broker_account/`)
   - `@sync_projection` decorators for critical events
   - Cross-domain events
   - Cascading operations

3. **Broker Connection Domain** (`app/broker_connection/`)
   - OAuth flow events with sync projections
   - Connection lifecycle
   - Health monitoring

---

## 🚨 Common Mistakes to Avoid

1. ❌ **Not analyzing sync/async requirements**
   - **CRITICAL**: Don't copy-paste from other domains blindly!
   - Analyze YOUR domain's specific needs
   - Document WHY each event is sync or async

2. ❌ **Creating sync_events.py file (DEPRECATED)**
   - DO NOT create sync_events.py - it's been removed!
   - Use `@sync_projection` decorator instead
   - Decorator is the single source of truth

3. ❌ **Using Dict[str, Any] instead of EventEnvelope**
   - Projector methods MUST use `EventEnvelope` parameter
   - NOT `event_dict: Dict[str, Any]`

4. ❌ **Forgetting HandlerDependencies**
   - Add read repo to dataclass

5. ❌ **Missing WSE integration**
   - If events need real-time updates, integrate with WSE

6. ❌ **Not testing end-to-end**
   - Write integration tests
   - Verify events → projections → queries
   - Test both sync and async projection paths

---

## 💰 CRYPTO Asset Type Support (Added 2025-11-01)

### Overview

**CRYPTO** is the 5th supported asset type (after STOCK, OPTION, FUTURE, FUTURE_OPTION).

**Key Insight**: CRYPTO is treated **like STOCK** - no additional derivative fields needed!

### Why CRYPTO is Simple

Unlike options (7 fields) and futures (9 fields), **crypto requires ZERO additional fields**:

```python
# ✅ CRYPTO order - simple like stock
PlaceOrderCommand(
    symbol="BTC/USD",           # Symbol format with slash
    asset_type=AssetType.CRYPTO,
    quantity=Decimal("0.001"),  # Fractional quantities supported
    # NO option_details
    # NO future_details
)
```

### Implementation Checklist

When adding CRYPTO support to your domain:

- [ ] **Enum**: Add `CRYPTO = "crypto"` to AssetType enum
- [ ] **Validation**: Add CRYPTO case (like STOCK - no derivative details)
- [ ] **Database**: Update asset_type constraint to include `'crypto'`
- [ ] **NO new fields** needed (treat like STOCK)
- [ ] **NO new value objects** needed (no CryptoDetails)

### Validation Pattern

```python
@staticmethod
def _validate_asset_type_details(
    asset_type: AssetType,
    option_details: Optional[OptionDetails],
    future_details: Optional[FutureDetails]
):
    if asset_type == AssetType.STOCK:
        if option_details or future_details:
            raise ValueError("STOCK cannot have derivative details")

    elif asset_type == AssetType.CRYPTO:
        if option_details or future_details:
            raise ValueError("CRYPTO cannot have derivative details")

    # ... rest of validation
```

### Database Constraint

```sql
ALTER TABLE {domain}s ADD CONSTRAINT {domain}s_asset_type_check
    CHECK (asset_type IN ('stock', 'option', 'future', 'future_option', 'crypto'));
```

### Symbol Format

**Alpaca Format** (with forward slash):
- `BTC/USD`
- `ETH/USDT`
- `DOGE/USD`

**TradeStation Format** (standard):
- Same as Alpaca

### Broker Support

| Broker | Crypto Support | Notes |
|--------|----------------|-------|
| Alpaca | ✅ 20+ coins, 56 pairs | Fractional qty, 24/7 trading |
| TradeStation | ✅ TSCrypto + XRP Futures | Spot + futures |
| TradersPost | ✅ Reference standard | Treats crypto like stocks |
| Binance | 🔮 Future | Compatible with current design |
| Bybit | 🔮 Future | Compatible with current design |

### Features

- ✅ **Fractional Quantities**: Up to 8 decimal places (0.00000001)
- ✅ **24/7 Trading**: No market hours restrictions
- ✅ **No Margin**: Crypto cannot be bought on margin or sold short (Alpaca)
- ✅ **Multiple Quote Currencies**: USD, USDT, USDC, BTC

### API Example

```python
# API Request (camelCase)
{
  "symbol": "BTC/USD",
  "assetType": "crypto",  # ✅ Include crypto
  "quantity": 0.001,
  "orderType": "market"
  # NO option fields
  # NO future fields
}
```

### Migration SQL (if updating existing DB)

```sql
-- Drop old constraint
ALTER TABLE {domain}s DROP CONSTRAINT IF EXISTS {domain}s_asset_type_check;

-- Add new constraint with crypto
ALTER TABLE {domain}s ADD CONSTRAINT {domain}s_asset_type_check
    CHECK (asset_type IN ('stock', 'option', 'future', 'future_option', 'crypto'));
```

---

## 🎯 Time Estimates

**For a typical domain:**

- File structure creation: 30 minutes
- **Sync/Async analysis & decision**: 1-2 hours ⭐ (discuss with team!)
- Events & Aggregate: 2-3 hours
- Commands & Handlers: 2-4 hours
- Queries & Handlers: 1-2 hours
- Projectors with `@sync_projection` decorators: 2-3 hours
- Read Models & Repository: 1-2 hours
- Domain Registry: 30 minutes
- CQRS Integration: 30 minutes
- WSE Integration: 1-2 hours (if needed)
- API Router: 1-2 hours
- Database Schema: 1 hour
- Tests: 2-4 hours
- Documentation: 1 hour

**Total: 15-26 hours** for complete domain implementation (includes sync/async analysis)

**Note**: sync_events.py removed - saves 1 hour per domain!

---

**Good luck with your new domain! Follow this template and you'll have a clean, consistent domain structure.** 🚀
