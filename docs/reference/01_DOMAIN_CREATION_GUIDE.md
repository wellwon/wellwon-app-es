# Domain Creation Guide

**WellWon Platform v1.0 - Complete Step-by-Step Reference**

**Last Updated:** 2025-12-01

This is the authoritative guide for creating new domains in WellWon. Follow this guide exactly to ensure consistency with existing architecture and best practices.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Folder Structure](#folder-structure)
4. [Step-by-Step Creation](#step-by-step-creation)
5. [Code Examples](#code-examples)
6. [Good vs Bad Examples](#good-vs-bad-examples)
7. [Testing Your Domain](#testing-your-domain)
8. [Checklist](#checklist)
9. [Common Pitfalls](#common-pitfalls)

---

## Overview

### What is a Domain?

In WellWon, a **domain** is a **bounded context** following Domain-Driven Design (DDD) principles. Each domain:

- **Encapsulates** a specific business capability (e.g., broker accounts, automation, positions)
- **Owns** its data and business logic
- **Communicates** with other domains via events (event-driven architecture)
- **Follows** CQRS (Command Query Responsibility Segregation) and Event Sourcing patterns

### Bounded Context Principles

1. **Single Responsibility**: One domain, one purpose (e.g., `broker_account` only manages broker accounts)
2. **Loose Coupling**: Domains communicate via events, not direct calls
3. **High Cohesion**: All related logic stays within the domain
4. **Aggregate Root**: One aggregate per domain managing state transitions
5. **Event-First Thinking**: All state changes emit events

### Architecture Pattern

```
Command → CommandHandler → Aggregate → Event → Projector → ReadModel
   ↓                           ↓                    ↓
QueryBus                   EventStore           PostgreSQL
```

---

## Prerequisites

Before creating a domain, ensure you understand:

1. **CQRS**: Command/Query separation, CommandBus, QueryBus
2. **Event Sourcing**: Events as source of truth, event store, projections
3. **Aggregates**: State management, business rules, event emission
4. **Pydantic vs Dataclasses**: Events use Pydantic, Value Objects use dataclasses
5. **Async Python**: All I/O operations must be async

**Required Reading:**
- `/docs/reference/PROJECTION_DECORATORS.md` - Projection decorator patterns
- `/docs/mvp/architecture/PROJECTION_ARCHITECTURE.md` - Full architecture overview

---

## Folder Structure

### Complete Domain Directory Structure

```
app/{domain_name}/
├── __init__.py                    # Package initialization
├── aggregate.py                   # Aggregate root (state + business logic)
├── commands.py                    # Command definitions (write operations)
├── events.py                      # Domain events (Pydantic BaseEvent)
├── value_objects.py              # Immutable value objects (frozen dataclasses)
├── enums.py                      # Domain-specific enumerations
├── exceptions.py                 # Custom domain exceptions
├── projectors.py                 # Event projectors (@sync_projection/@async_projection)
├── read_models.py                # Read model schemas (Pydantic)
├── queries.py                    # Query definitions (read operations)
├── command_handlers/             # Modular command handlers
│   ├── __init__.py
│   ├── lifecycle_handlers.py    # Creation, deletion handlers
│   ├── {feature}_handlers.py    # Feature-specific handlers
│   └── ...
└── query_handlers/               # Query handlers (read operations)
    ├── __init__.py
    ├── {feature}_query_handlers.py
    └── ...
```

### File Descriptions

| File | Purpose | Pattern | Required | Example |
|------|---------|---------|----------|---------|
| `aggregate.py` | Aggregate root with state and business logic | Event sourcing aggregate | ✅ YES | `broker_account` |
| `events.py` | Domain events (Pydantic BaseEvent with @domain_event) | Event definitions | ✅ YES | `broker_account` |
| `commands.py` | Write operations (inherit from Command) | Pydantic v2 | ✅ YES | `broker_account` |
| `queries.py` | Read operations (inherit from Query) | Pydantic v2 | ✅ YES | `broker_account` |
| `exceptions.py` | Domain-specific business errors | Exception classes | ✅ YES | `automation` |
| `enums.py` | Domain-specific enumerations | Python str Enum | ✅ YES | `automation` |
| `projectors.py` | Event handlers updating read models | @sync_projection | ✅ YES | `broker_account` |
| `read_models.py` | Read-side database schemas | Pydantic v2 | ✅ YES | `broker_account` |
| `value_objects.py` | Immutable domain objects | @dataclass frozen | Optional | `automation` |
| `command_handlers/` | Command handler classes | BaseCommandHandler | ✅ YES | `broker_account` |
| `query_handlers/` | Query handler classes | BaseQueryHandler | ✅ YES | `broker_account` |

**⚠️ 2025-12-01 BREAKING CHANGES**:
- `commands.py` - NOW inherits from `Command` (Pydantic v2), NOT @dataclass
- `queries.py` - NOW inherits from `Query` (Pydantic v2), NOT @dataclass
- `exceptions.py` - NOW REQUIRED for all domains
- `enums.py` - NOW REQUIRED for all domains
- `sync_events.py` - **REMOVED** (use `@sync_projection`/`@async_projection` decorators in projectors.py)

---

## Step-by-Step Creation

### Step 1: Define Aggregates and State

**File:** `aggregate.py`

The aggregate is the **heart** of your domain. It:
- Manages state
- Enforces business rules
- Emits events on state changes

#### 1.1 Define Aggregate State (Pydantic BaseModel)

```python
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal

class BrokerAccountAggregateState(BaseModel):
    """Internal state of the AccountAggregate."""
    # Identifiers
    user_id: Optional[UUID] = None
    broker_connection_id: Optional[UUID] = None
    broker_id: Optional[str] = None
    broker_account_id: Optional[str] = None

    # Details
    account_name: Optional[str] = None
    currency: str = "USD"

    # Financials
    balance: Decimal = Decimal("0.0")
    equity: Optional[Decimal] = None

    # Flags
    is_deleted: bool = False

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

**Why Pydantic for State?**
- Automatic validation
- JSON serialization (for snapshots)
- Type safety
- Easy to extend

#### 1.2 Define Aggregate Root

```python
from typing import List
from app.common.base.base_model import BaseEvent

class AccountAggregate:
    """
    Aggregate root for broker accounts.

    Responsibilities:
    - Validate business rules
    - Emit domain events
    - Manage account lifecycle
    """

    def __init__(self, aggregate_id: UUID):
        self.id: UUID = aggregate_id
        self.version: int = 0
        self.state: BrokerAccountAggregateState = BrokerAccountAggregateState()
        self._uncommitted_events: List[BaseEvent] = []

    def _apply_and_record(self, event: BaseEvent) -> None:
        """Apply event to state and record for persistence"""
        self._apply(event)  # Mutate state
        self._uncommitted_events.append(event)
        self.version += 1

    def get_uncommitted_events(self) -> List[BaseEvent]:
        return self._uncommitted_events

    def mark_events_committed(self) -> None:
        self._uncommitted_events = []
```

#### 1.3 Add Command Methods (Business Logic)

```python
def link_new_broker_account(
    self,
    user_id: UUID,
    broker_connection_id: UUID,
    broker_id: str,
    broker_account_id: str,
    account_name: Optional[str],
    balance: Decimal,
    currency: str,
    linked_at: datetime
):
    """
    Link a new broker account.

    Business Rules:
    - Cannot link if already linked
    - Balance must be non-negative
    - Required fields must be present
    """
    # Validate business rules
    if self.version > 0 and self.state.broker_account_id != broker_account_id:
        raise InvalidOperationError("Mismatch in broker account ID during linking.")

    if balance < 0:
        raise InvalidOperationError("Balance cannot be negative.")

    # Create and apply event
    event = BrokerAccountLinked(
        account_aggregate_id=self.id,
        user_id=user_id,
        broker_connection_id=broker_connection_id,
        broker_id=broker_id,
        broker_account_id=broker_account_id,
        account_name=account_name,
        initial_balance=balance,
        currency=currency,
        linked_at=linked_at
    )

    self._apply_and_record(event)
```

#### 1.4 Add Event Handlers (State Mutation)

**⚠️ CRITICAL: Use snake_case for method names**

```python
def _apply(self, event: BaseEvent) -> None:
    """
    Route event to handler (dynamic dispatch).

    Converts PascalCase event class name to snake_case method name.
    Example: BrokerAccountLinked → _on_broker_account_linked
    """
    event_class_name = event.__class__.__name__
    snake_case_name = ''.join([
        '_' + c.lower() if c.isupper() else c
        for c in event_class_name
    ]).lstrip('_')
    handler_name = f"_on_{snake_case_name}"
    handler = getattr(self, handler_name, None)
    if handler:
        handler(event)

def _on_broker_account_linked(self, event: BrokerAccountLinked) -> None:
    """Apply BrokerAccountLinked event to state"""
    self.state.user_id = event.user_id
    self.state.broker_connection_id = event.broker_connection_id
    self.state.broker_id = event.broker_id
    self.state.broker_account_id = event.broker_account_id
    self.state.account_name = event.account_name
    self.state.balance = event.initial_balance
    self.state.currency = event.currency
    self.state.created_at = event.linked_at
```

---

### Step 2: Create Events

**File:** `events.py`

**⚠️ CRITICAL RULES:**
1. Events MUST inherit from `BaseEvent` (Pydantic model)
2. Events MUST have `event_type: Literal["EventName"] = "EventName"`
3. Events are **NOT** @dataclass
4. Use `datetime.now(UTC)` NOT `datetime.utcnow()`

#### 2.1 Import Required Modules

```python
from typing import Optional, Literal, Dict, Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.common.base.base_model import BaseEvent
```

#### 2.2 Define Events

```python
class BrokerAccountLinked(BaseEvent):
    """
    Event when a broker account is linked to the system.

    Triggers:
    - Account creation in read model
    - Account discovery saga completion
    - Initial balance projection
    """
    event_type: Literal["BrokerAccountLinked"] = "BrokerAccountLinked"

    # Identifiers
    account_aggregate_id: UUID
    user_id: UUID
    broker_connection_id: UUID
    broker_id: str
    broker_account_id: str

    # Details
    account_name: Optional[str] = None
    initial_balance: Decimal
    currency: str
    initial_equity: Optional[Decimal] = None
    initial_buying_power: Optional[Decimal] = None

    # Metadata
    linked_at: datetime


class AccountDataFromBrokerUpdated(BaseEvent):
    """Event when account data is refreshed from broker"""
    event_type: Literal["AccountDataFromBrokerUpdated"] = "AccountDataFromBrokerUpdated"

    account_aggregate_id: UUID
    balance: Decimal
    equity: Optional[Decimal] = None
    buying_power: Optional[Decimal] = None
    status_from_broker: Optional[str] = None
    metadata_from_broker: Optional[Dict[str, Any]] = None
    refreshed_at: datetime
```

**Event Naming Conventions:**
- Past tense (e.g., `AccountLinked`, not `LinkAccount`)
- Clear, descriptive names (e.g., `AccountDataFromBrokerUpdated` vs `AccountUpdated`)
- Include context when needed (e.g., `UserAccountMarkedDeleted` vs `Deleted`)

---

### Step 3: Create Value Objects

**File:** `value_objects.py`

Value objects are **immutable** domain concepts. They:
- Use `@dataclass(frozen=True)` for immutability
- Encapsulate related data
- Include validation logic
- Are reusable across the domain

#### 3.1 Define Value Objects

```python
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
from datetime import datetime

from app.automation.enums import OptionType, OptionAction

@dataclass(frozen=True)
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
    multiplier: Decimal = Decimal("1") # Price multiplier

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
        strike_int = int(self.strike_price * 1000)
        return f"{self.underlying_symbol}{exp_str}{option_char}{strike_int:08d}"


@dataclass(frozen=True)
class PositionSizingConfig:
    """Configuration for position sizing"""
    sizing_type: str  # "FIXED", "PERCENT", "RISK_BASED"
    fixed_quantity: Optional[Decimal] = None
    amount_per_position: Optional[Decimal] = None
    risk_per_position: Optional[Decimal] = None
    percent_of_equity: Optional[Decimal] = None
    use_buying_power: bool = False

    def __post_init__(self):
        """Validate configuration based on sizing type"""
        if self.sizing_type == "FIXED" and self.fixed_quantity is None:
            raise ValueError("fixed_quantity required for FIXED sizing")
        if self.sizing_type == "PERCENT" and self.percent_of_equity is None:
            raise ValueError("percent_of_equity required for PERCENT sizing")
```

**Why Frozen Dataclasses?**
- Immutability prevents accidental state changes
- Thread-safe
- Hashable (can be used in sets/dicts)
- Clear intent (value object, not entity)

---

### Step 4: Create Commands

**File:** `commands.py`

Commands represent **write operations** (intent to change state).

#### 4.1 Import Required Modules

```python
from uuid import UUID
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from pydantic import Field

from app.infra.cqrs.command_bus import Command
```

#### 4.2 Define Commands

```python
class LinkDiscoveredBrokerAccountCommand(Command):
    """
    Command to link or update a discovered broker account.

    Triggers creation or update of the AccountAggregate.
    """
    user_id: UUID
    broker_connection_id: UUID

    broker_id_from_adapter: str
    broker_account_id_from_adapter: str

    account_name_from_adapter: Optional[str] = None
    balance_from_adapter: Decimal
    currency_from_adapter: str
    equity_from_adapter: Optional[Decimal] = None
    buying_power_from_adapter: Optional[Decimal] = None
    status_from_adapter: Optional[str] = None
    metadata_from_broker: Optional[Dict[str, Any]] = None

    discovered_at: datetime

    # Saga support
    saga_id: Optional[UUID] = Field(None, description="ID of orchestrating saga")


class RefreshAccountDataFromBrokerCommand(Command):
    """Command to refresh account data from the broker"""
    account_aggregate_id: UUID
    user_id: UUID
    saga_id: Optional[UUID] = None


class DeleteBrokerAccountCommand(Command):
    """Command to delete a broker account (hard delete)"""
    account_id: UUID
    user_id: UUID
    reason: str
    saga_id: Optional[UUID] = None
```

**Command Naming:**
- Imperative verbs (e.g., `LinkAccount`, `RefreshData`, `Delete`)
- Clear intent (what will happen)
- Include context (e.g., `LinkDiscoveredBrokerAccountCommand` vs `LinkAccountCommand`)

---

### Step 5: Implement Command Handlers

**File:** `command_handlers/lifecycle_handlers.py`

Command handlers:
- Validate commands
- Load aggregates
- Execute business logic
- Save events

#### 5.1 Create Handler Class

```python
import logging
from typing import TYPE_CHECKING
from uuid import UUID
from datetime import datetime, UTC

from app.broker_account.commands import LinkDiscoveredBrokerAccountCommand
from app.broker_account.aggregate import AccountAggregate
from app.broker_account.queries import GetAccountByDetailsQuery
from app.common.base.base_command_handler import BaseCommandHandler
from app.infra.cqrs.decorators import command_handler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.broker_account.lifecycle_handlers")


@command_handler(LinkDiscoveredBrokerAccountCommand)
class LinkDiscoveredBrokerAccountHandler(BaseCommandHandler):
    """
    Handler for linking discovered broker accounts.

    DOCUMENTED EXCEPTION: Uses QueryBus to find existing aggregate by external ID.
    This is necessary because:
    - Adapter discovers accounts by broker_account_id (external identifier)
    - We need to find the aggregate ID from external identifier
    - Alternative: Caller enriches command with aggregate_id after query

    For most handlers, use pure Event Sourcing (load_aggregate, version check).
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="broker_account_events",
            event_store=deps.event_store
        )
        # EXCEPTION: Query needed to find aggregate by external ID
        self.query_bus = deps.query_bus
        self.aggregate_repository = deps.aggregate_repository

    async def handle(self, command: LinkDiscoveredBrokerAccountCommand) -> UUID:
        """Link or update discovered broker account"""
        log.info(f"Linking broker account: {command.broker_account_id_from_adapter}")

        # EXCEPTION: Find aggregate by external broker_account_id
        # (can't use load_aggregate because we don't have our internal aggregate_id)
        existing_account = await self.query_bus.query(GetAccountByDetailsQuery(
            user_id=command.user_id,
            broker_id=command.broker_id_from_adapter,
            broker_account_id=command.broker_account_id_from_adapter
        ))

        # Load or create aggregate
        if existing_account:
            account_id = existing_account.id
            aggregate = await self.aggregate_repository.load(
                AccountAggregate,
                account_id
            )
            log.info(f"Updating existing account: {account_id}")
        else:
            account_id = UUID()
            aggregate = AccountAggregate(account_id)
            log.info(f"Creating new account: {account_id}")

        # Execute business logic
        aggregate.link_new_broker_account(
            user_id=command.user_id,
            broker_connection_id=command.broker_connection_id,
            broker_id=command.broker_id_from_adapter,
            broker_account_id=command.broker_account_id_from_adapter,
            account_name=command.account_name_from_adapter,
            balance=command.balance_from_adapter,
            currency=command.currency_from_adapter,
            equity=command.equity_from_adapter,
            buying_power=command.buying_power_from_adapter,
            status_from_broker=command.status_from_adapter,
            metadata_from_broker=command.metadata_from_broker,
            linked_at=datetime.now(UTC)
        )

        # Save aggregate (persists events)
        await self.aggregate_repository.save(aggregate)

        log.info(f"Broker account linked successfully: {account_id}")
        return account_id
```

**Handler Best Practices:**
1. Use `@command_handler` decorator for registration
2. Inject dependencies via `HandlerDependencies`
3. **NEVER use QueryBus for reads** - load aggregate from Event Store instead
4. Let aggregate validate business rules (aggregate.version == 0 means not found)
5. Log key operations for debugging

**CRITICAL: Pure CQRS Pattern**
```python
# ✅ CORRECT - Load from Event Store
aggregate = await self.load_aggregate(command.entity_id, "EntityType", EntityAggregate)
if aggregate.version == 0:
    raise ValueError("Entity not found")

# ❌ WRONG - Query in command handler
entity = await self.query_bus.query(GetEntityByIdQuery(id=command.entity_id))
```

**Documented Exceptions (use sparingly):**
- **Authentication handlers**: Must lookup by email/username to find aggregate ID
- **Password/Security handlers**: Must validate credentials via query
- **Saga enrichment handlers**: Must query data to enrich event for saga

---

### Step 6: Create Projectors

**File:** `projectors.py`

Projectors update **read models** (PostgreSQL/ScyllaDB) when events occur.

**CRITICAL:** Use explicit `@sync_projection` or `@async_projection` decorators for ALL projection methods.

#### 6.1 Dual-Decorator Pattern (2025 Best Practice)

```python
import logging
from app.infra.event_store.event_envelope import EventEnvelope
from app.infra.cqrs.projector_decorators import (
    sync_projection,
    async_projection,
    monitor_projection
)

log = logging.getLogger("wellwon.company.projectors")


class CompanyProjector:
    """
    Projector for Company domain read models.

    SYNC vs ASYNC Decision:
    - @sync_projection: User expects immediate feedback (saga dependencies, UI critical)
    - @async_projection: Eventual consistency OK (background updates, metrics)
    """

    def __init__(self, company_read_repo: CompanyReadRepo):
        self.company_read_repo = company_read_repo

    # =========================================================================
    # SYNC Projections - Execute on SERVER before HTTP response
    # =========================================================================

    @sync_projection("CompanyCreated", priority=1, timeout=2.0)
    @monitor_projection  # Optional: detailed logging
    async def on_company_created(self, envelope: EventEnvelope) -> None:
        """
        SYNC: Saga creates chat immediately after company - must exist in read model.
        """
        event_data = envelope.event_data
        company_id = envelope.aggregate_id

        await self.company_read_repo.insert_company(
            company_id=company_id,
            name=event_data['name'],
            company_type=event_data.get('company_type', 'company'),
            created_by=event_data['created_by'],
            created_at=envelope.stored_at,
        )
        log.info(f"Projected CompanyCreated: {company_id}")

    # =========================================================================
    # ASYNC Projections - Execute on WORKER via Kafka
    # =========================================================================

    @async_projection("CompanyUpdated")
    async def on_company_updated(self, envelope: EventEnvelope) -> None:
        """
        ASYNC: Company update is not time-critical. UI uses optimistic update.
        """
        event_data = envelope.event_data
        company_id = envelope.aggregate_id

        await self.company_read_repo.update_company(
            company_id=company_id,
            name=event_data.get('name'),
            updated_at=envelope.stored_at,
        )

    @async_projection("CompanyDeleted")
    @monitor_projection
    async def on_company_deleted(self, envelope: EventEnvelope) -> None:
        """
        ASYNC: UI uses optimistic update, eventual consistency acceptable.
        """
        company_id = envelope.aggregate_id

        try:
            await self.company_read_repo.delete_company(
                company_id=company_id,
                updated_at=envelope.stored_at,
            )
        except Exception as e:
            log.error(f"CompanyDeleted projection FAILED: {company_id}, error={e}")
            raise  # Re-raise for Worker retry
```

#### 6.2 SYNC vs ASYNC Decision Matrix

| Criteria | @sync_projection | @async_projection |
|----------|-----------------|-------------------|
| User expects immediate feedback | YES | NO |
| Saga depends on read model | YES | NO |
| Critical for next operation | YES | NO |
| UI uses optimistic update | NO | YES |
| Background analytics | NO | YES |
| Audit logging | NO | YES |

#### 6.3 Idempotency Pattern (REQUIRED)

```python
# CORRECT: Idempotent with ON CONFLICT
await pg.execute("""
    INSERT INTO companies (id, name, created_at)
    VALUES ($1, $2, $3)
    ON CONFLICT (id) DO NOTHING
""", company_id, name, created_at)

# WRONG: Not idempotent - fails on replay
await pg.execute("""
    INSERT INTO companies (id, name, created_at)
    VALUES ($1, $2, $3)
""", company_id, name, created_at)
```

**Projector Best Practices:**
1. **ALWAYS use explicit decorators** - `@sync_projection` or `@async_projection`
2. **Idempotent handlers** - use `ON CONFLICT DO NOTHING/UPDATE`
3. **Import from correct location** - `app.infra.cqrs.projector_decorators`
4. **Re-raise exceptions in ASYNC** - enables Worker retry mechanism
5. **Use `@monitor_projection`** for critical operations
6. **Short timeouts for SYNC** - default 2.0s, max 5.0s

---

### Step 7: Register Domain in Domain Registry

**File:** `app/infra/worker_core/event_processor/domain_registry.py`

**⚠️ NOTE:** `sync_events.py` is **DEPRECATED** as of 2025-12-01. Sync/async configuration is now handled via `@sync_projection` and `@async_projection` decorators directly on projector methods.

Register your new domain in the domain registry for Worker event processing.

#### 7.1 Create Domain Factory Function

```python
# In domain_registry.py

def create_shipment_domain() -> DomainRegistration:
    """Factory function for shipment domain configuration"""

    # Import projector module FIRST to trigger decorator registration
    import app.shipment.projectors

    from app.shipment.events import (
        ShipmentCreated,
        ShipmentUpdated,
        ShipmentStatusChanged,
        ShipmentDelivered,
    )

    def shipment_projector_factory():
        from app.shipment.projectors import ShipmentProjector
        from app.infra.read_repos.shipment_read_repo import ShipmentReadRepo

        read_repo = ShipmentReadRepo()
        return ShipmentProjector(read_repo)

    return DomainRegistration(
        name="shipment",
        topics=["transport.shipment-events"],
        projector_factory=shipment_projector_factory,
        event_models={
            "ShipmentCreated": ShipmentCreated,
            "ShipmentUpdated": ShipmentUpdated,
            "ShipmentStatusChanged": ShipmentStatusChanged,
            "ShipmentDelivered": ShipmentDelivered,
        },
        projection_config={
            "aggregate_type": "Shipment",
            "transport_topic": "transport.shipment-events"
        },
        enable_sequence_tracking=True
    )
```

#### 7.2 Register in Domain Registry Creation

```python
def create_domain_registry() -> DomainRegistry:
    """Create and populate the domain registry"""
    global _domain_registry

    if _domain_registry is None:
        registry = DomainRegistry()

        # Register existing domains
        registry.register(create_user_account_domain())
        registry.register(create_company_domain())
        registry.register(create_chat_domain())

        # Register your new domain
        registry.register(create_shipment_domain())  # ADD THIS

        log.info(f"Domain registry created with {len(registry._domains)} domains")
        _domain_registry = registry

    return _domain_registry
```

#### 7.3 Add Topic Configuration

In `app/config/eventbus_transport_config.py`:

```python
# Add to _init_default_topics()
"transport.shipment-events": TopicConfig(
    name="transport.shipment-events",
    type=TopicType.STREAM,
    partitions=9,
    retention_ms=604800000,  # 7 days
    consumer_group="event-processor-workers"
),
```

**Domain Registration Checklist:**
1. ✅ Import projector module in factory (triggers decorator registration)
2. ✅ Define all event models in `event_models` dict
3. ✅ Create `projector_factory` function
4. ✅ Add TopicConfig for your transport topic
5. ✅ Consumer group should be `event-processor-workers`

### Step 8: Create Queries and Query Handlers

**File:** `queries.py`

```python
from uuid import UUID
from typing import Optional
from pydantic import Field

from app.infra.cqrs.query_bus import Query


class GetAccountsByUserQuery(Query):
    """Query to get all accounts for a user"""
    user_id: UUID
    include_deleted: bool = False
    saga_id: Optional[UUID] = None


class GetAccountByIdQuery(Query):
    """Query to get account by ID"""
    account_id: UUID
    user_id: Optional[UUID] = None  # For ownership validation
    saga_id: Optional[UUID] = None


class GetAccountByDetailsQuery(Query):
    """Query to find account by specific details"""
    user_id: UUID
    broker_id: Optional[str] = None
    broker_account_id: Optional[str] = None
    saga_id: Optional[UUID] = None
```

**File:** `query_handlers/account_query_handlers.py`

```python
import logging
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID

from app.broker_account.queries import GetAccountsByUserQuery, GetAccountByIdQuery
from app.broker_account.read_models import BrokerAccountReadModel
from app.infra.cqrs.decorators import query_handler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.broker_account.query_handlers.account")


@query_handler(GetAccountsByUserQuery)
class GetAccountsByUserHandler:
    """Handler for GetAccountsByUserQuery"""

    def __init__(self, deps: 'HandlerDependencies'):
        self.account_read_repo = deps.account_read_repo

    async def handle(self, query: GetAccountsByUserQuery) -> List[BrokerAccountReadModel]:
        """Get all accounts for a user"""
        return await self.account_read_repo.get_by_user(
            user_id=query.user_id,
            include_deleted=query.include_deleted
        )


@query_handler(GetAccountByIdQuery)
class GetAccountByIdHandler:
    """Handler for GetAccountByIdQuery"""

    def __init__(self, deps: 'HandlerDependencies'):
        self.account_read_repo = deps.account_read_repo

    async def handle(self, query: GetAccountByIdQuery) -> Optional[BrokerAccountReadModel]:
        """Get account by ID"""
        account = await self.account_read_repo.get_by_id(query.account_id)

        # Validate ownership if user_id provided
        if query.user_id and account and account.user_id != query.user_id:
            log.warning(f"User {query.user_id} attempted to access account {query.account_id}")
            return None

        return account
```

---

### Step 9: Database Migrations

Create database schema for read models.

**File:** `alembic/versions/{timestamp}_create_{domain_name}_tables.py`

```python
"""Create {domain_name} tables

Revision ID: {revision_id}
Revises: {previous_revision}
Create Date: {timestamp}
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = '{revision_id}'
down_revision = '{previous_revision}'
branch_labels = None
depends_on = None


def upgrade():
    # Create main table
    op.create_table(
        '{domain_name}s',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),

        # Event sourcing metadata
        sa.Column('aggregate_version', sa.Integer, default=1, nullable=False),
        sa.Column('last_event_sequence', sa.BigInteger, nullable=True),
        sa.Column('last_saga_id', UUID(as_uuid=True), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),

        # Indexes
        sa.Index('idx_{domain_name}s_user_id', 'user_id'),
        sa.Index('idx_{domain_name}s_status', 'status'),

        # Foreign keys
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )

    # Trigger for updated_at
    op.execute("""
        CREATE TRIGGER {domain_name}s_updated_at
        BEFORE UPDATE ON {domain_name}s
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    op.drop_table('{domain_name}s')
```

**Run migration:**
```bash
alembic revision --autogenerate -m "Create {domain_name} tables"
alembic upgrade head
```

---

## Code Examples

### Example 1: Simple Domain (Broker Account)

**Complexity:** Low
**Lines:** ~1,200 total
**Events:** 10
**SYNC Rate:** 28% (7 SYNC / 25 total)

**Key Features:**
- Simple aggregate (account state)
- Basic CRUD operations
- Cross-domain queries (Order/Position validate account)
- Saga integration (discovery, deletion)

**Location:** `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_account/`

### Example 2: Medium Domain (Broker Connection)

**Complexity:** Medium
**Lines:** ~2,500 total
**Events:** 15
**SYNC Rate:** 40% (6 SYNC / 15 total)

**Key Features:**
- OAuth2 integration
- Connection lifecycle (establishment, disconnection)
- Saga orchestration (BrokerDisconnectionSaga)
- Credential encryption

**Location:** `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_connection/`

### Example 3: Complex Domain (Automation)

**Complexity:** High
**Lines:** ~4,300 total
**Events:** 13
**SYNC Rate:** 75% (10 SYNC / 13 total)

**Key Features:**
- State machines (INACTIVE → ACTIVE → SUSPENDED)
- Derivatives support (options, futures)
- Webhook signal processing
- Pyramiding configuration
- Value objects (17 derivative fields)

**Location:** `/Users/silvermpx/PycharmProjects/TradeCore/app/automation/`

---

## Good vs Bad Examples

### Good Example: Event Definition

```python
# ✅ CORRECT
from app.common.base.base_model import BaseEvent
from typing import Literal
from datetime import datetime, UTC
from uuid import UUID

class BrokerAccountLinked(BaseEvent):
    """Event when broker account is linked"""
    event_type: Literal["BrokerAccountLinked"] = "BrokerAccountLinked"
    account_aggregate_id: UUID
    user_id: UUID
    linked_at: datetime
```

### Bad Example: Event Definition

```python
# ❌ WRONG
from dataclasses import dataclass  # Events are NOT dataclasses!
from datetime import datetime

@dataclass  # ❌ NO! Events are Pydantic BaseEvent
class BrokerAccountLinked:
    account_id: str  # ❌ NO! Use UUID
    linked_at: datetime = datetime.utcnow()  # ❌ DEPRECATED! Use datetime.now(UTC)
```

### Good Example: Aggregate Method Names

```python
# ✅ CORRECT - snake_case
class AccountAggregate:
    def _on_broker_account_linked(self, event):  # ✅ snake_case
        self.state.balance = event.initial_balance

    def _on_account_data_updated(self, event):  # ✅ snake_case
        self.state.balance = event.balance
```

### Bad Example: Aggregate Method Names

```python
# ❌ WRONG - PascalCase
class AccountAggregate:
    def _on_BrokerAccountLinked(self, event):  # ❌ PascalCase!
        self.state.balance = event.initial_balance

    def _OnAccountDataUpdated(self, event):  # ❌ PascalCase!
        self.state.balance = event.balance
```

### Good Example: Value Objects

```python
# ✅ CORRECT - Frozen dataclass
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)  # ✅ Immutable
class PositionSizingConfig:
    sizing_type: str
    fixed_quantity: Decimal

    def __post_init__(self):
        if self.fixed_quantity <= 0:
            raise ValueError("Quantity must be positive")
```

### Bad Example: Value Objects

```python
# ❌ WRONG - Mutable dataclass
from dataclasses import dataclass

@dataclass  # ❌ NOT frozen! Can be mutated
class PositionSizingConfig:
    sizing_type: str
    fixed_quantity: float  # ❌ Use Decimal for money!
```

### Good Example: Command Handler

```python
# ✅ CORRECT - Pure Event Sourcing
@command_handler(UpdateAccountCommand)
class UpdateAccountHandler(BaseCommandHandler):
    """Pure Event Sourcing handler - NO QueryBus!"""

    def __init__(self, deps: HandlerDependencies):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="broker_account_events",
            event_store=deps.event_store
        )
        # NO query_bus! Pure handlers don't need it

    async def handle(self, command: UpdateAccountCommand) -> UUID:
        # ✅ Load aggregate from Event Store
        aggregate = await self.load_aggregate(
            command.account_id, "BrokerAccount", AccountAggregate
        )

        # ✅ Check existence via version
        if aggregate.version == 0:
            raise ValueError(f"Account {command.account_id} not found")

        # ✅ Business logic in aggregate
        aggregate.update_settings(...)

        # ✅ Publish events
        await self.publish_events(
            aggregate=aggregate,
            aggregate_id=command.account_id,
            command=command
        )
        return command.account_id
```

### Bad Example: Command Handler

```python
# ❌ WRONG - QueryBus in command handler
class UpdateAccountHandler:
    def __init__(self, deps):
        self.query_bus = deps.query_bus  # ❌ DON'T DO THIS!

    async def handle(self, command):
        # ❌ Query in command handler (eventual consistency race condition!)
        existing = await self.query_bus.query(GetAccountQuery(...))

        # ❌ Checking via query instead of aggregate version
        if not existing:
            raise ValueError("Account not found")

        # ❌ Direct database insert (not event sourcing)
        await self.db.execute("INSERT INTO accounts ...")
```

---

## Testing Your Domain

### Unit Tests

**File:** `tests/unit/{domain_name}/test_aggregate.py`

```python
import pytest
from uuid import uuid4
from datetime import datetime, UTC
from decimal import Decimal

from app.broker_account.aggregate import AccountAggregate
from app.broker_account.events import BrokerAccountLinked


class TestAccountAggregate:
    """Unit tests for AccountAggregate"""

    def test_link_new_broker_account(self):
        """Test linking a new broker account"""
        # Arrange
        aggregate = AccountAggregate(uuid4())
        user_id = uuid4()
        broker_connection_id = uuid4()

        # Act
        aggregate.link_new_broker_account(
            user_id=user_id,
            broker_connection_id=broker_connection_id,
            broker_id="alpaca",
            broker_account_id="ABC123",
            account_name="My Trading Account",
            balance=Decimal("10000.00"),
            currency="USD",
            linked_at=datetime.now(UTC)
        )

        # Assert
        assert aggregate.version == 1
        assert len(aggregate.get_uncommitted_events()) == 1

        event = aggregate.get_uncommitted_events()[0]
        assert isinstance(event, BrokerAccountLinked)
        assert event.user_id == user_id
        assert event.broker_id == "alpaca"
        assert event.initial_balance == Decimal("10000.00")

        # State updated correctly
        assert aggregate.state.user_id == user_id
        assert aggregate.state.balance == Decimal("10000.00")

    def test_cannot_link_negative_balance(self):
        """Test that negative balance is rejected"""
        # Arrange
        aggregate = AccountAggregate(uuid4())

        # Act & Assert
        with pytest.raises(InvalidOperationError):
            aggregate.link_new_broker_account(
                user_id=uuid4(),
                broker_connection_id=uuid4(),
                broker_id="alpaca",
                broker_account_id="ABC123",
                account_name="Test",
                balance=Decimal("-1000.00"),  # ❌ Negative!
                currency="USD",
                linked_at=datetime.now(UTC)
            )
```

### Integration Tests

**File:** `tests/integration/{domain_name}/test_command_flow.py`

```python
import pytest
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, UTC

from app.broker_account.commands import LinkDiscoveredBrokerAccountCommand
from app.broker_account.queries import GetAccountByIdQuery


@pytest.mark.asyncio
async def test_link_account_command_flow(
    command_bus,
    query_bus,
    event_store
):
    """Test full command → event → projection flow"""
    # Arrange
    user_id = uuid4()
    broker_connection_id = uuid4()

    command = LinkDiscoveredBrokerAccountCommand(
        user_id=user_id,
        broker_connection_id=broker_connection_id,
        broker_id_from_adapter="alpaca",
        broker_account_id_from_adapter="ABC123",
        account_name_from_adapter="Test Account",
        balance_from_adapter=Decimal("10000.00"),
        currency_from_adapter="USD",
        discovered_at=datetime.now(UTC)
    )

    # Act - Dispatch command
    account_id = await command_bus.dispatch(command)

    # Wait for projection (eventual consistency)
    await asyncio.sleep(0.5)

    # Assert - Query read model
    account = await query_bus.query(GetAccountByIdQuery(account_id=account_id))

    assert account is not None
    assert account.user_id == user_id
    assert account.broker_id == "alpaca"
    assert account.balance == Decimal("10000.00")

    # Assert - Events persisted
    events = await event_store.load_events(account_id)
    assert len(events) == 1
    assert events[0].event_type == "BrokerAccountLinked"
```

---

## Checklist

Use this checklist to ensure your domain is complete:

### Required Files
- [ ] `__init__.py` - Package initialization
- [ ] `aggregate.py` - Aggregate root with state and business logic
- [ ] `events.py` - Domain events (Pydantic BaseEvent)
- [ ] `commands.py` - Command definitions
- [ ] `projectors.py` - Event projectors with `@sync_projection`/`@async_projection`
- [ ] `read_models.py` - Read model schemas
- [ ] `queries.py` - Query definitions
- [ ] `exceptions.py` - Domain-specific exceptions
- [ ] `command_handlers/` - Command handler implementations
- [ ] `query_handlers/` - Query handler implementations

### Optional Files (Domain-Specific)
- [ ] `value_objects.py` - Immutable value objects (if needed)
- [ ] `enums.py` - Domain enumerations (if needed)
- [ ] `exceptions.py` - Custom exceptions (if needed)

### Code Quality
- [ ] Events inherit from `BaseEvent` (NOT @dataclass)
- [ ] Events have `event_type: Literal["EventName"] = "EventName"`
- [ ] Use `datetime.now(UTC)` NOT `datetime.utcnow()`
- [ ] Method names use `snake_case` NOT `PascalCase`
- [ ] Value objects use `@dataclass(frozen=True)`
- [ ] Business logic in aggregates, NOT handlers
- [ ] All I/O operations are async
- [ ] **Command handlers use load_aggregate() - NO QueryBus!**
- [ ] QueryBus used in query handlers and routers (READ side only)
- [ ] Use CommandBus for writes (CQRS compliance)

### Registration
- [ ] Domain registered in `domain_registry.py`
- [ ] Events registered in event models dict
- [ ] Projector factory configured
- [ ] TopicConfig added in `eventbus_transport_config.py`
- [ ] Consumer group set to `event-processor-workers`

### Database
- [ ] Alembic migration created
- [ ] Table schema matches read model
- [ ] Indexes on foreign keys and frequently queried columns
- [ ] Timestamps with triggers (`updated_at`, `deleted_at`)
- [ ] Event sourcing metadata (`aggregate_version`, `last_event_sequence`)

### Testing
- [ ] Unit tests for aggregate
- [ ] Unit tests for value objects
- [ ] Integration tests for command flow
- [ ] Integration tests for query flow
- [ ] Test edge cases and business rule violations

### Documentation
- [ ] Docstrings on all classes and methods
- [ ] Event descriptions (what triggers, what happens)
- [ ] Command descriptions (intent, parameters)
- [ ] README for domain (if complex)

---

## Common Pitfalls

### 1. Using @dataclass for Events

**Problem:**
```python
@dataclass  # ❌ WRONG!
class MyEvent:
    field: str
```

**Solution:**
```python
class MyEvent(BaseEvent):  # ✅ CORRECT
    event_type: Literal["MyEvent"] = "MyEvent"
    field: str
```

### 2. Using datetime.utcnow()

**Problem:**
```python
created_at: datetime = datetime.utcnow()  # ❌ DEPRECATED!
```

**Solution:**
```python
from datetime import datetime, UTC
created_at: datetime = datetime.now(UTC)  # ✅ CORRECT
```

### 3. PascalCase Method Names

**Problem:**
```python
def _on_MyEvent(self, event):  # ❌ WRONG!
    pass
```

**Solution:**
```python
def _on_my_event(self, event):  # ✅ CORRECT
    pass
```

### 4. Business Logic in Handlers

**Problem:**
```python
async def handle(self, command):
    # ❌ Business logic in handler!
    if command.balance < 0:
        raise ValueError("Negative balance")

    await self.db.execute("INSERT ...")
```

**Solution:**
```python
async def handle(self, command):
    # ✅ Business logic in aggregate
    aggregate = AccountAggregate(uuid4())
    aggregate.create_account(balance=command.balance)  # Validates here!
    await self.aggregate_repository.save(aggregate)
```

### 5. Direct Database Access in Command Handler

**Problem:**
```python
async def handle(self, command):
    # ❌ Direct database access!
    result = await self.db.execute("SELECT * FROM accounts WHERE ...")
```

**Solution:**
```python
async def handle(self, command):
    # ✅ Load aggregate from Event Store
    aggregate = await self.load_aggregate(
        command.account_id, "BrokerAccount", AccountAggregate
    )

    # ✅ Check existence via version
    if aggregate.version == 0:
        raise ValueError("Account not found")
```

**Note:** QueryBus is for the READ side (query handlers, routers), NOT for command handlers!

### 6. Too Many SYNC Events

**Problem:**
```python
SYNC_EVENTS = {
    "AccountCreated",
    "AccountUpdated",
    "AccountBalanceChanged",  # ❌ High frequency!
    "AccountEquityChanged",   # ❌ High frequency!
    "AccountMetricsCalculated",  # ❌ Background operation!
    # ... 20 more events
}
```

**Solution:**
```python
SYNC_EVENTS = {
    # Only cross-domain validation and critical state
    "AccountCreated",
    "AccountDeleted",
    "AccountActivated",
}

ASYNC_EVENTS = {
    # High-frequency and background operations
    "AccountBalanceChanged",
    "AccountEquityChanged",
    "AccountMetricsCalculated",
}
```

### 7. Missing event_type Field

**Problem:**
```python
class MyEvent(BaseEvent):
    # ❌ Missing event_type!
    field: str
```

**Solution:**
```python
class MyEvent(BaseEvent):
    event_type: Literal["MyEvent"] = "MyEvent"  # ✅ Required!
    field: str
```

### 8. Mutable Value Objects

**Problem:**
```python
@dataclass  # ❌ Not frozen!
class Config:
    value: str
```

**Solution:**
```python
@dataclass(frozen=True)  # ✅ Immutable
class Config:
    value: str
```

---

## Next Steps

After creating your domain:

1. **Test thoroughly** - Unit tests, integration tests, edge cases
2. **Monitor performance** - Check SYNC event ratio (aim for 20-30%)
3. **Document** - Add docstrings, README if complex
4. **Review** - Have another developer review your domain
5. **Deploy** - Test in staging before production

**Recommended Reading:**
- `/docs/reference/PROJECTION_DECORATORS.md` - Projection decorator patterns
- `/docs/mvp/architecture/PROJECTION_ARCHITECTURE.md` - Full architecture overview
- `/docs/mvp/domains/` - Example domain documentation (User Account, Company, Chat)

---

## Support

If you encounter issues:

1. Check exemplar domains for reference:
   - **Simple:** `app/user_account/` (23 projections)
   - **Medium:** `app/company/` (14 projections)
   - **Complex:** `app/chat/` (16 projections with ScyllaDB)

2. Review existing patterns in codebase

3. Check logs for errors:
   ```bash
   tail -f logs/wellwon.log
   ```

4. Use debugging tools:
   - Redpanda Console: http://localhost:8080
   - API Docs: http://localhost:5002/docs

---

**Version:** 2.0
**Last Updated:** December 1, 2025
**Author:** WellWon Team
**Status:** Production Ready
