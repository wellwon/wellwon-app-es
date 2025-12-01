# TradeCore Domain Implementation Best Practices

**Date**: 2025-11-01 (Updated: 2025-11-22)
**Purpose**: Definitive guide for implementing CQRS/ES domains in TradeCore
**Status**: ✅ VALIDATED against all 8 production domains

**⚠️ CRITICAL UPDATES (2025-11-22)**:
- **Pydantic v2 Standard**: Commands/Queries MUST use Pydantic v2 with CQRS base classes
- **Commands**: Inherit from `Command` (NOT BaseModel, NOT dataclass)
- **Queries**: Inherit from `Query` (NOT BaseModel, NOT dataclass)
- **Handlers**: Inherit from `BaseCommandHandler` / `BaseQueryHandler`
- **Required Files**: ALL domains MUST have `exceptions.py` and `enums.py`

---

## 📌 CRITICAL RULES (MUST FOLLOW)

### 1. ❌ NEVER use `datetime.utcnow()`
**DEPRECATED in Python 3.12+**

❌ **WRONG**:
```python
from datetime import datetime

# In events.py
opened_at: datetime = Field(default_factory=datetime.utcnow)  # WRONG!

# In commands.py
timestamp: datetime = field(default_factory=datetime.utcnow)  # WRONG!

# In aggregate.py
self.created_at = datetime.utcnow()  # WRONG!
```

✅ **CORRECT**:
```python
from datetime import datetime, UTC  # Import UTC!

# In events.py (Pydantic)
opened_at: datetime = Field(default_factory=lambda: datetime.now(UTC))  # CORRECT!

# In commands.py (Pydantic v2 - inherits from Command)
timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))  # CORRECT!

# In value_objects.py (frozen dataclass)
last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))  # CORRECT!

# In aggregate.py (direct assignment)
self.created_at = datetime.now(UTC)  # CORRECT!
```

**Why**:
- `datetime.utcnow()` creates naive datetime (no timezone)
- `datetime.now(UTC)` creates timezone-aware datetime
- Pydantic and databases prefer timezone-aware datetimes

---

### 2. ✅ Commands/Queries MUST use Pydantic v2 with CQRS base classes
**NEW STANDARD (2025-11-22)**

❌ **WRONG** - Old patterns:
```python
# commands.py
from dataclasses import dataclass

@dataclass
class MyCommand:  # Wrong - no inheritance
    field: str

# OR

from pydantic import BaseModel

class MyCommand(BaseModel):  # Wrong - should inherit from Command
    field: str
```

✅ **CORRECT** - Pydantic v2 with CQRS:
```python
# commands.py
from pydantic import Field
from app.infra.cqrs.command_bus import Command

class MyCommand(Command):  # MUST inherit from Command
    """Command description"""
    # Required fields first
    field: str

    # Optional fields with defaults
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # saga_id inherited from Command base class

# queries.py
from app.infra.cqrs.query_bus import Query

class MyQuery(Query):  # MUST inherit from Query
    """Query description"""
    field: str
    # saga_id inherited from Query base class
```

**Why**:
- `Command` and `Query` are Pydantic v2 BaseModel with `saga_id` field
- Automatic validation at API boundaries
- Type safety and IDE support
- Consistent with FastAPI integration
- Eliminates CommandBus warnings

---

### 3. ✅ ALWAYS use snake_case for method names
**PEP 8 Convention**

❌ **WRONG**:
```python
# In aggregate.py
def _apply(self, event):
    handler_name = f"_on_{event.event_type}"  # Creates _on_PositionOpenedEvent

def _on_PositionOpenedEvent(self, event):  # PascalCase - WRONG!
    pass
```

✅ **CORRECT**:
```python
# In aggregate.py
def _apply(self, event: BaseEvent) -> None:
    """Apply event to aggregate state"""
    # Convert CamelCase → snake_case
    event_class_name = event.__class__.__name__
    snake_case_name = ''.join(['_' + c.lower() if c.isupper() else c for c in event_class_name]).lstrip('_')
    handler_name = f"_on_{snake_case_name}"
    handler = getattr(self, handler_name, None)
    if handler:
        handler(event)

def _on_position_opened_event(self, event: PositionOpenedEvent):  # snake_case - CORRECT!
    """Apply PositionOpenedEvent"""
    self.status = PositionStatus.OPEN
    self.opened_at = event.opened_at
```

**Pattern for Position aggregate** (Lines 1119-1137 in `position/aggregate.py`):
```python
def _apply(self, event: BaseEvent) -> None:
    """Apply event to aggregate state"""
    # Route to specific handler (convert CamelCase → snake_case)
    event_class_name = event.__class__.__name__
    # Convert EventName → event_name
    snake_case_name = ''.join(['_' + c.lower() if c.isupper() else c for c in event_class_name]).lstrip('_')
    handler_name = f"_on_{snake_case_name}"
    handler = getattr(self, handler_name, None)

    if not handler:
        return

    handler(event)

    # Add to uncommitted events
    if event not in self._uncommitted_events:
        self._uncommitted_events.append(event)
```

**Pattern for Automation aggregate** (Lines 733-748 in `automation/aggregate.py`):
```python
def apply(self, event):
    """Apply event to aggregate state"""
    # Route to specific apply method (convert CamelCase → snake_case)
    event_type = event.event_type
    # Convert EventName → event_name
    snake_case_name = ''.join(['_' + c.lower() if c.isupper() else c for c in event_type]).lstrip('_')
    method_name = f"_apply_{snake_case_name}"

    if hasattr(self, method_name):
        getattr(self, method_name)(event)
    else:
        raise ValueError(f"No apply method for event type: {event_type}")

    # Add to uncommitted events
    self.uncommitted_events.append(event)
    self.version += 1
```

**Event handler naming**:
```python
# Position domain pattern (_on_ prefix)
def _on_position_opened_event(self, event): pass
def _on_position_increased_event(self, event): pass  # Pyramiding
def _on_position_closed_event(self, event): pass

# Automation domain pattern (_apply_ prefix)
def _apply_automation_created_event(self, event): pass
def _apply_automation_activated_event(self, event): pass
def _apply_pyramiding_config_updated_event(self, event): pass
```

---

### 3. ✅ ALWAYS add `event_type` field to ALL events
**Required for Event Registry and Routing**

❌ **WRONG**:
```python
class PositionOpenedEvent(BaseEvent):
    """Position opened"""
    # Missing event_type field! - WRONG!
    position_id: UUID
    symbol: str
```

✅ **CORRECT**:
```python
class PositionOpenedEvent(BaseEvent):
    """Position opened"""
    event_type: Literal["PositionOpenedEvent"] = "PositionOpenedEvent"  # CORRECT!
    position_id: UUID
    symbol: str
    opened_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**Pattern**:
- Use `Literal` type hint with exact event class name
- Default value MUST match the Literal type
- Place immediately after docstring, before other fields

**All 13 Automation events** have `event_type` ✅
**All 12 Position events** have `event_type` ✅
**All 16 Order events** have `event_type` ✅

---

### 4. ✅ Use Pydantic BaseEvent (NOT @dataclass)
**Events are Pydantic models**

❌ **WRONG**:
```python
from dataclasses import dataclass

@dataclass  # WRONG for events!
class PositionOpenedEvent:
    position_id: UUID
    symbol: str
```

✅ **CORRECT**:
```python
from pydantic import Field
from app.common.base.base_model import BaseEvent

class PositionOpenedEvent(BaseEvent):  # Inherit from BaseEvent - CORRECT!
    """Position opened"""
    event_type: Literal["PositionOpenedEvent"] = "PositionOpenedEvent"
    position_id: UUID
    symbol: str
    opened_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**Why**:
- BaseEvent is a Pydantic BaseModel
- Provides validation
- JSON serialization

---

### 5. ✅ Handlers MUST inherit from Base classes
**NEW STANDARD (2025-11-22)**

❌ **WRONG**:
```python
# Command handler without inheritance
from app.infra.cqrs.command_bus import ICommandHandler

@command_handler(MyCommand)
class MyCommandHandler(ICommandHandler):  # Wrong - use BaseCommandHandler
    async def handle(self, command: MyCommand):
        pass
```

✅ **CORRECT**:
```python
# Command handler with proper inheritance
from app.common.base.base_command_handler import BaseCommandHandler
from app.infra.cqrs.decorators import command_handler

@command_handler(MyCommand)
class MyCommandHandler(BaseCommandHandler):
    """Handle MyCommand"""

    def __init__(self, deps: HandlerDependencies):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="my_domain_events",
            event_store=deps.event_store
        )

    async def handle(self, command: MyCommand) -> Any:
        # Business logic here
        pass

# Query handler with proper inheritance
from app.common.base.base_query_handler import BaseQueryHandler

@query_handler(MyQuery)
class MyQueryHandler(BaseQueryHandler[MyQuery, ResultType]):
    """Handle MyQuery"""

    def __init__(self, deps: HandlerDependencies):
        super().__init__()
        self.db = deps.pg_client

    async def handle(self, query: MyQuery) -> ResultType:
        # Query logic here
        pass
```

**Why**:
- BaseCommandHandler provides `publish_and_commit_events()` helper
- BaseQueryHandler provides generic type safety
- Consistent error handling and logging
- Better testability

---

### 6. ✅ ALL domains MUST have exceptions.py and enums.py
**NEW REQUIREMENT (2025-11-22)**

**exceptions.py** - Domain-specific business errors:
```python
class {Domain}DomainError(Exception):
    """Base exception for {Domain} domain"""
    pass

class {Domain}NotFoundError({Domain}DomainError):
    """Specific domain error"""
    pass
```

**enums.py** - Domain-specific enumerations:
```python
from enum import Enum

class {Domain}Status(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
```

**Common vs Domain exceptions**:
- Domain exceptions.py = Business logic errors (Invalid state, business rule violations)
- Common exceptions = Infrastructure (BrokerAuthError, ResourceNotFoundError, PermissionError)

---

### 7. ✅ Use Pydantic BaseEvent (NOT @dataclass)
- Event registry integration

---

## 🚀 Event Auto-Registration Pattern (2025 Update)

### Overview

**Event Auto-Registration System** eliminates manual event registry maintenance using Python decorators.

**Key Benefits**:
- Zero manual registry updates
- Automatic duplicate detection
- Type-safe event registration
- Single source of truth
- 70% code reduction (713 → 212 lines in event_registry.py)

### Event Decorators

**Import**:
```python
from app.infra.event_bus.event_decorators import domain_event, saga_event, system_event
```

**Available Decorators**:

1. `@domain_event()` - Domain events (default priority: 10)
2. `@saga_event()` - Saga orchestration events (priority: 5)
3. `@system_event()` - Infrastructure events (priority: 15)
4. `@streaming_event()` - Real-time events (priority: 20)

### Usage Pattern

#### CORRECT Usage (Auto-Registration)

```python
from app.infra.event_bus.event_decorators import domain_event
from app.common.base.base_model import BaseEvent
from datetime import datetime, UTC
from typing import Literal
from uuid import UUID
from pydantic import Field

@domain_event(category="domain", description="User account created")
class UserAccountCreated(BaseEvent):
    """User account created event"""
    event_type: Literal["UserAccountCreated"] = "UserAccountCreated"
    user_id: UUID
    username: str
    email: str
    role: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

@domain_event(category="domain", description="Position opened")
class PositionOpenedEvent(BaseEvent):
    """Position opened event"""
    event_type: Literal["PositionOpenedEvent"] = "PositionOpenedEvent"
    position_id: UUID
    symbol: str
    quantity: Decimal
    price: Decimal
    opened_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

#### WRONG - Old Manual Registration (Deprecated)

```python
# events.py - OLD WAY (no decorator)
class UserAccountCreated(BaseEvent):
    event_type: Literal["UserAccountCreated"] = "UserAccountCreated"
    user_id: UUID
    username: str

# event_registry.py - Manual registration required (DEPRECATED)
EVENT_TYPE_TO_PYDANTIC_MODEL = {
    "UserAccountCreated": UserAccountCreated,  # Manual entry - NO LONGER NEEDED
    "PositionOpenedEvent": PositionOpenedEvent,
    # ... 189+ manual entries
}
```

### Decorator Parameters

```python
@domain_event(
    category="domain",           # Event category (domain/saga/system/streaming)
    description="Brief desc",    # Optional description for docs
    sync=False,                   # DEPRECATED - use @sync_projection instead
    priority=10                   # Event priority (lower = higher priority)
)
```

**Priority Values**:
- Saga events: 5 (highest priority)
- Domain events: 10 (default)
- System events: 15
- Streaming events: 20 (lowest priority)

### Migration from Manual Registration

**Before (Manual Registry)**:
```python
# app/user_account/events.py
class UserAccountCreated(BaseEvent):
    event_type: Literal["UserAccountCreated"] = "UserAccountCreated"
    # ... fields

# app/infra/event_bus/event_registry.py (713 lines)
EVENT_TYPE_TO_PYDANTIC_MODEL = {
    "UserAccountCreated": UserAccountCreated,
    "UserPasswordChanged": UserPasswordChanged,
    "UserAccountDeleted": UserAccountDeleted,
    # ... 189+ manual entries
}
```

**After (Auto-Registration)**:
```python
# app/user_account/events.py
from app.infra.event_bus.event_decorators import domain_event

@domain_event(category="domain", description="User account created")
class UserAccountCreated(BaseEvent):
    event_type: Literal["UserAccountCreated"] = "UserAccountCreated"
    # ... fields

@domain_event(category="domain", description="User password changed")
class UserPasswordChanged(BaseEvent):
    event_type: Literal["UserPasswordChanged"] = "UserPasswordChanged"
    # ... fields

# app/infra/event_bus/event_registry.py (212 lines - 70% reduction!)
# Manual registry only contains system events
# Domain events auto-register at import time
```

### Important Rules

1. **ALWAYS** use `@domain_event()` decorator for ALL domain events
2. **ALWAYS** keep `event_type: Literal["EventName"] = "EventName"` field
3. **NEVER** manually add domain events to event_registry.py
4. **NEVER** duplicate event definitions across domains
5. **ALWAYS** define events in their origin domain

### Duplicate Detection

The decorator system automatically detects duplicate event registrations:

**Example Error**:
```
WARNING: Event type 'UserAccountDeleted' already registered by <class UserAccountDeleted>.
         Overriding with <class UserAccountDeleted> from module app.common.events.saga_events
```

**Solution**: Remove duplicate definition, keep only in origin domain.

---

## 📊 SYNC vs ASYNC Projection Pattern (2025 Update)

### Overview

**Projection Types**:
- **SYNC**: Executed within command transaction (blocking, immediate consistency)
- **ASYNC**: Executed by worker after commit (non-blocking, eventual consistency)

**Performance Impact**:
- SYNC projections block write operations
- Over-synced systems can reduce throughput by 20-30%
- ASYNC projections enable horizontal scaling

### SYNC Projection Criteria

Use **SYNC** projections ONLY for:

1. **Critical business logic** - Data needed immediately by next command
2. **Authorization/Security** - Permission checks, access control
3. **Aggregate consistency** - Cross-aggregate invariants
4. **User-facing reads** - Data displayed immediately after write

Use **ASYNC** projections for:

1. **Analytics/Reporting** - Dashboards, metrics, statistics
2. **Audit/Logging** - Activity logs, history tracking
3. **Notifications** - Emails, alerts, webhooks
4. **Denormalized views** - Search indexes, cached aggregates
5. **Third-party integrations** - External system updates

### Pattern: @sync_projection Decorator

**The decorator is the SINGLE SOURCE OF TRUTH** - no separate config files needed.

#### CORRECT - Critical Projections (SYNC)

```python
from app.infra.event_store.sync_decorators import sync_projection, monitor_projection

class UserAccountProjector:
    """User account projector"""

    def __init__(self, user_read_repo: UserAccountReadRepo):
        self.user_read_repo = user_read_repo

    @sync_projection("UserAccountCreated")
    @monitor_projection
    async def on_user_created(self, envelope: EventEnvelope) -> None:
        """Project UserAccountCreated event

        SYNC: Required for immediate authentication after signup
        """
        event_data = envelope.event_data
        user_id = envelope.aggregate_id

        await UserAccountReadRepo.insert_user_account_projection(
            user_id=user_id,
            username=event_data['username'],
            email=event_data['email'],
            hashed_password=event_data['hashed_password'],
            role=event_data['role'],
        )

    @sync_projection("UserAccountDeleted", priority=1, timeout=3.0)
    async def on_user_deleted(self, envelope: EventEnvelope) -> None:
        """Project UserAccountDeleted event

        SYNC: Critical for security - prevent deleted user from accessing system
        """
        user_id = envelope.aggregate_id
        await UserAccountReadRepo.mark_user_inactive_projection(user_id)
        await self._clear_user_caches(user_id)  # Immediate cache invalidation

    @sync_projection("BrokerAccountCreated")
    async def on_broker_account_created(self, envelope: EventEnvelope) -> None:
        """Project BrokerAccountCreated event

        SYNC: Required for immediate trading after account creation
        """
        event_data = envelope.event_data
        await BrokerAccountReadRepo.insert_broker_account_projection(
            account_id=event_data['account_id'],
            user_id=event_data['user_id'],
            broker_name=event_data['broker_name'],
            status=event_data['status'],
        )
```

#### CORRECT - Analytics/Monitoring (ASYNC)

```python
class PortfolioProjector:
    """Portfolio analytics projector"""

    def __init__(self, portfolio_repo: PortfolioReadRepo):
        self.portfolio_repo = portfolio_repo

    # NO @sync_projection decorator - ASYNC by default
    async def on_order_filled(self, envelope: EventEnvelope) -> None:
        """Project OrderFilledEvent

        ASYNC: Analytics/audit data - eventual consistency OK
        Performance: Does not block order processing
        """
        event_data = envelope.event_data
        await self.portfolio_repo.update_account_activity(
            account_id=event_data['account_id'],
            activity_type='order_filled',
            symbol=event_data['symbol'],
            amount=event_data['filled_amount'],
        )

    async def on_position_closed(self, envelope: EventEnvelope) -> None:
        """Project PositionClosedEvent

        ASYNC: Historical statistics - eventual consistency OK
        Performance: Does not block position closure
        """
        event_data = envelope.event_data
        await self.portfolio_repo.update_closed_positions_stats(
            user_id=event_data['user_id'],
            realized_pnl=event_data['realized_pnl'],
        )

class BrokerAccountProjector:
    """Broker account projector"""

    async def on_account_discovery_completed(self, envelope: EventEnvelope) -> None:
        """Project AccountDiscoveryCompleted event

        ASYNC: Saga completion logging - eventual consistency OK
        Performance: Does not block batch discovery operations
        """
        event_data = envelope.event_data
        log.info(f"Discovery completed: {event_data.get('discovered_count', 0)} accounts")
```

### WRONG - Over-Synced Projections

```python
# WRONG - Analytics blocking writes
class PortfolioProjector:

    @sync_projection("OrderFilledEvent")  # WRONG - analytics should be ASYNC
    async def on_order_filled(self, envelope: EventEnvelope) -> None:
        """Update account activities"""
        # This blocks every order fill for analytics!
        await self.portfolio_repo.update_account_activity(...)

    @sync_projection("BrokerConnectionHealthChecked")  # WRONG - audit log should be ASYNC
    async def on_health_checked(self, envelope: EventEnvelope) -> None:
        """Log health check"""
        # This blocks every health check for logging!
        log.info(f"Health check: {event_data}")
```

### Performance Metrics (TradeCore 2025-11-13 Update)

**Phase 1 - Before Optimization** (69 SYNC projections):
- Write throughput: ~500 commands/sec
- P95 latency: 150ms
- Portfolio writes: 200-300ms (analytics blocking)
- Batch operations: 2-3 seconds per account

**Phase 2 - After Portfolio/VB Optimization** (54 SYNC projections, 22% reduction):
- Write throughput: ~600 commands/sec (+20%)
- P95 latency: 110ms (-27%)
- Portfolio writes: 50-80ms (-67%)
- Batch operations: 1.5-2 seconds per account (-33%)

**Phase 3 - After Event Bus Audit (Nov 13, 2025)** (38 SYNC projections, 30% further reduction):
- **Critical Infrastructure Fixes**:
  - Fixed thread safety issues in event_decorators.py (race conditions eliminated)
  - Fixed thread safety issues in sync_decorators.py (handler registration safe)
  - Fixed memory leak in performance metrics (bounded at 1000 keys)
- **User Account Optimization**: 7 projections converted SYNC → ASYNC
  - UserPasswordChanged, UserPasswordReset, UserEmailVerified
  - UserBrokerAccountMappingSet, UserConnectedBroker(Added/Removed)
  - UserAuthenticationSucceeded/Failed
- **Performance Impact**: User domain ~29% fewer blocking operations
- **SYNC Ratio**: 55.7% → 39.2% (acceptable for trading platform)
- **Industry Benchmark**: 15-25% SYNC (trading platforms: 30-40% acceptable)

**Domains with High ASYNC Ratios**:
- Automation: 100% ASYNC (0 SYNC)
- Portfolio: 100% ASYNC (0 SYNC)
- User Account: 67% ASYNC (5 SYNC remain - auth/security critical)
- Broker Account: 60% ASYNC (5 SYNC - saga coordination)

**Domains Requiring High SYNC (Trading Critical)**:
- Order: 9 SYNC (real-money operations, zero-loss tolerance)
- Virtual Broker: 9 SYNC (state machine consistency)
- Broker Connection: 8 SYNC (OAuth flows, must be synchronous)
- Position: 2 SYNC (cross-domain validation)

**Audit Findings**:
See `docs/EVENT_BUS_AUTO_REGISTRATION_AUDIT_2025.md` for complete analysis.

### Decision Tree

```
Is this projection critical for the next command?
├─ YES → Is it user-facing or security-critical?
│  ├─ YES → Use @sync_projection
│  └─ NO → Consider ASYNC
└─ NO → Is it analytics, logging, or notification?
   └─ YES → Use ASYNC (no decorator)
```

### Migration: Removing Redundant sync_events.py

**Old System** (DEPRECATED - Removed 2025-11-13):
```python
# app/user_account/sync_events.py - DELETED
SYNC_EVENTS = [
    "UserAccountCreated",
    "UserAccountDeleted",
    "UserPasswordChanged",
]
```

**New System** (Current):
```python
# app/user_account/projectors.py
# The @sync_projection decorator IS the config

@sync_projection("UserAccountCreated")  # Automatically tracked
async def on_user_created(self, envelope: EventEnvelope) -> None:
    """SYNC: Required for immediate authentication"""
    pass

@sync_projection("UserAccountDeleted", priority=1)  # Automatically tracked
async def on_user_deleted(self, envelope: EventEnvelope) -> None:
    """SYNC: Critical for security"""
    pass

# ASYNC - no decorator needed
async def on_user_authentication_succeeded(self, envelope: EventEnvelope) -> None:
    """ASYNC: Last login timestamp - eventual consistency OK"""
    pass
```

**Result**:
- Deleted 8 redundant `sync_events.py` config files
- @sync_projection decorator is single source of truth
- No configuration drift between projectors and config files

---

## 🔄 Sync Projection Architecture (Complete Guide)

### Overview

Sync projections use decorators for automatic registration. EventProcessorWorker processes ALL events (both sync and async) using the same unified system.

**Key Components:**
1. `@sync_projection` decorator - Auto-registers handlers
2. `sync_decorators.py` - Decorator implementation and execution
3. `EventProcessorWorker` - Processes ALL events using sync decorators
4. `EventEnvelope` - Unified event format for projectors

### Architecture Flow

```
Event Published
    |
    v
EventBus (Redpanda)
    |
    v
EventProcessorWorker
    |
    v
DomainRegistry.get_all_sync_events()
    |
    v
EventProcessor.process_event()
    |
    v
execute_sync_projections(envelope, projector_instances)
    |
    v
@sync_projection decorated methods execute
```

### Core Components

#### 1. Sync Decorators (`app/infra/event_store/sync_decorators.py`)

**Registration:**
```python
_SYNC_PROJECTION_HANDLERS: Dict[str, List[ProjectionHandler]] = {}

@sync_projection(
    event_type: str,
    timeout: float = 2.0,
    priority: int = 10,
    description: Optional[str] = None
)
```

**Features:**
- Thread-safe registration
- Automatic event type tracking
- Priority-based execution (lower number = higher priority)
- Timeout protection
- Performance metrics

**Key Functions:**
```python
# Get all sync events (single source of truth)
def get_all_sync_events() -> Set[str]

# Execute sync projections for an event
async def execute_sync_projections(
    envelope: EventEnvelope,
    projector_instances: Dict[str, Any],
    timeout_override: Optional[float] = None
) -> Dict[str, Any]

# Auto-register with event store
async def auto_register_sync_projections(
    event_store,
    projector_instances: Dict[str, Any]
) -> Dict[str, Any]
```

#### 2. EventProcessorWorker (`app/workers/event_processor_worker.py`)

**Initialization:**
```python
class EventProcessingWorker(BaseWorker):
    def __init__(self, config: Optional[WorkerConfig] = None):
        super().__init__(WorkerType.EVENT_PROCESSOR, config)

        # Collect all sync events from domain registry
        self.sync_events_registry: Set[str] = set()

    async def _setup_event_processing(self) -> None:
        # Initialize domains
        await self.domain_registry.initialize_all(...)

        # Collect sync events from decorators
        self.sync_events_registry = self.domain_registry.get_all_sync_events()

        # Create event processor with sync events
        self.event_processor = EventProcessor(
            domain_registry=self.domain_registry,
            event_bus=self.event_bus,
            sync_events_registry=self.sync_events_registry,
            skip_sync_events=False  # Workers process ALL events
        )
```

**Event Processing:**
```python
# In EventProcessor.process_event()
for domain in domains:
    # Check if projector uses sync decorators
    has_sync_decorators = False
    for attr_name in dir(domain.projector_instance):
        attr = getattr(domain.projector_instance, attr_name)
        if hasattr(attr, '_is_sync_projection'):
            has_sync_decorators = True
            break

    if has_sync_decorators:
        # Use sync projection decorators
        envelope = EventEnvelope.from_partial_data(event_dict)

        # Collect all projector instances (cross-domain support)
        projector_instances = {
            d.name: d.projector_instance
            for d in self.domain_registry.get_enabled_domains()
            if d.has_projector() and event_type in d.event_models
        }

        # Execute sync projections (NO transaction wrapper!)
        result = await execute_sync_projections(envelope, projector_instances)
```

**CRITICAL: No Transaction Wrapper**
```python
# WRONG - Breaks Virtual Broker projections
async with transaction():
    result = await execute_sync_projections(envelope, projector_instances)

# CORRECT - Let each projector manage its own transactions
result = await execute_sync_projections(envelope, projector_instances)
```

**Why no transaction?**
- Virtual Broker uses separate database (vb_db)
- transaction() context forces all operations to MAIN database
- Each projector manages its own transactions if needed

#### 3. EventEnvelope (`app/infra/event_store/event_envelope.py`)

**Unified Format:**
```python
@dataclass
class EventEnvelope:
    event_id: UUID
    event_type: str
    aggregate_id: UUID
    aggregate_type: str
    event_data: Dict[str, Any]
    sequence_number: int
    stored_at: datetime

    @classmethod
    def from_partial_data(cls, event_dict: Dict[str, Any]) -> 'EventEnvelope':
        """Create envelope from Redpanda event dict"""
        return cls(
            event_id=UUID(event_dict['event_id']),
            event_type=event_dict['event_type'],
            aggregate_id=UUID(event_dict.get('aggregate_id', event_dict['event_id'])),
            aggregate_type=event_dict.get('aggregate_type', 'Unknown'),
            event_data=event_dict,
            sequence_number=event_dict.get('sequence_number', 0),
            stored_at=parse_datetime(event_dict.get('stored_at'))
        )
```

### Projector Implementation Pattern

#### Complete Example

```python
# app/user_account/projectors.py
from app.infra.event_store.event_envelope import EventEnvelope
from app.infra.event_store.sync_decorators import sync_projection, monitor_projection
from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo

class UserAccountProjector:
    """Projector with sync decorators"""

    def __init__(self, user_read_repo: UserAccountReadRepo):
        self.user_read_repo = user_read_repo

    # SYNC projection - immediate consistency
    @sync_projection("UserAccountCreated")
    @monitor_projection  # Optional monitoring
    async def on_user_created(self, envelope: EventEnvelope) -> None:
        """Project UserAccountCreated event

        SYNC: Required for immediate authentication after signup
        """
        event_data = envelope.event_data
        user_id = envelope.aggregate_id

        await UserAccountReadRepo.insert_user_account_projection(
            user_id=user_id,
            username=event_data['username'],
            email=event_data.get('email', ''),
            hashed_password=event_data['hashed_password'],
            role=event_data['role']
        )

    # SYNC projection with priority
    @sync_projection("UserAccountDeleted", priority=1, timeout=3.0)
    async def on_user_deleted(self, envelope: EventEnvelope) -> None:
        """Project UserAccountDeleted event

        SYNC: Critical for security - prevent deleted user access
        Priority: 1 (highest)
        Timeout: 3.0s (longer for cleanup)
        """
        user_id = envelope.aggregate_id
        await UserAccountReadRepo.mark_user_deleted_projection(user_id)

    # ASYNC projection - no decorator
    async def on_user_login(self, envelope: EventEnvelope) -> None:
        """Project UserAuthenticationSucceeded event

        ASYNC: Last login timestamp - eventual consistency OK
        """
        user_id = envelope.aggregate_id
        await UserAccountReadRepo.update_last_login(user_id)
```

#### Virtual Broker Projector (Multi-Database)

```python
# app/virtual_broker/projectors.py
from app.infra.event_store.sync_decorators import sync_projection

class VirtualBrokerProjector:
    """Virtual Broker projector - uses separate database"""

    def __init__(self, vb_db: VirtualBrokerDatabase):
        self.vb_db = vb_db  # Separate database connection

    @sync_projection("VirtualBrokerAccountCreated")
    async def on_account_created(self, envelope: EventEnvelope) -> None:
        """Write to Virtual Broker database

        CRITICAL: No transaction() wrapper in EventProcessor!
        Manages its own transaction with vb_db.
        """
        # Use Virtual Broker database
        await self.vb_db.execute(
            "INSERT INTO vb_accounts (...) VALUES (...)",
            ...
        )
```

### Domain Registry Integration

```python
# app/infra/worker_core/event_processor/domain_registry.py

class DomainRegistry:
    def get_all_sync_events(self) -> Set[str]:
        """Get all sync events from @sync_projection decorators"""
        from app.infra.event_store.sync_decorators import get_all_sync_events
        return get_all_sync_events()

    def get_sync_events_by_domain(self) -> Dict[str, Set[str]]:
        """Get sync events grouped by domain"""
        result = {}
        for domain in self.get_enabled_domains():
            if domain.sync_events:
                result[domain.name] = domain.sync_events
        return result
```

### Monitoring and Metrics

**Sync Projection Metrics:**
```python
# Get metrics
from app.infra.event_store.sync_decorators import get_sync_projection_metrics

metrics = get_sync_projection_metrics()
# {
#   "total_event_types": 38,
#   "total_handlers": 54,
#   "domains": ["user_account", "broker_account", ...],
#   "performance": {
#     "UserAccountCreated": {
#       "avg_ms": 12.5,
#       "min_ms": 8.2,
#       "max_ms": 25.1,
#       "p95_ms": 18.3,
#       "samples": 100
#     }
#   },
#   "errors": {...}
# }
```

**EventProcessor Metrics:**
```python
# In EventProcessingWorker
projection_metrics = self.event_processor.get_projection_metrics()
# {
#   "sync_events_skipped": 0,  # Should be 0 for workers
#   "sync_event_warnings": {},
#   "recovery_triggers": 5,
#   "total_processed": 1234
# }
```

### Best Practices

1. **Use @sync_projection for critical operations:**
   - User authentication (login/logout)
   - Security operations (account deletion)
   - Real-money operations (order placement)
   - Cross-domain consistency (position updates)

2. **Use ASYNC (no decorator) for:**
   - Analytics and reporting
   - Audit logs
   - Notifications
   - Historical statistics

3. **Decorator Parameters:**
   ```python
   @sync_projection(
       "EventName",
       priority=10,     # 1-20, lower = higher priority
       timeout=2.0,     # Max execution time in seconds
       description="..."  # Auto-documentation
   )
   ```

4. **Cross-Domain Events:**
   - EventProcessor collects ALL projector instances
   - Multiple domains can handle the same event
   - Each domain's sync projections execute independently

5. **Performance Optimization:**
   - Keep sync projections under 100ms
   - Use database indexes
   - Avoid N+1 queries
   - Monitor timeout warnings

6. **Error Handling:**
   - Sync projections have automatic retry (via worker)
   - Failed projections go to DLQ
   - EventProcessor tracks errors per projection

### Common Patterns

#### Pattern 1: Static Repository Methods
```python
@sync_projection("UserAccountCreated")
async def on_user_created(self, envelope: EventEnvelope) -> None:
    # Use static method (no self.user_read_repo)
    await UserAccountReadRepo.insert_user_account_projection(
        user_id=envelope.aggregate_id,
        username=envelope.event_data['username']
    )
```

#### Pattern 2: Instance Repository Methods
```python
@sync_projection("OrderPlaced")
async def on_order_placed(self, envelope: EventEnvelope) -> None:
    # Use instance method
    await self.order_read_repo.insert_order(
        order_id=envelope.aggregate_id,
        symbol=envelope.event_data['symbol']
    )
```

#### Pattern 3: Cross-Domain Projection
```python
# In broker_account/projectors.py
@sync_projection("BrokerDisconnected")  # From broker_connection domain
async def on_broker_disconnected(self, envelope: EventEnvelope) -> None:
    """Handle disconnection in broker_account domain"""
    broker_id = envelope.event_data['broker_connection_id']
    await self.broker_account_read_repo.mark_accounts_offline(broker_id)
```

### Testing Sync Projections

```python
import pytest
from app.infra.event_store.event_envelope import EventEnvelope
from app.infra.event_store.sync_decorators import execute_sync_projections

@pytest.mark.asyncio
async def test_sync_projection():
    # Create test envelope
    envelope = EventEnvelope.from_partial_data({
        'event_id': str(uuid.uuid4()),
        'event_type': 'UserAccountCreated',
        'aggregate_id': str(uuid.uuid4()),
        'username': 'testuser',
        'email': 'test@example.com'
    })

    # Create projector instance
    projector = UserAccountProjector(user_read_repo)

    # Execute sync projections
    result = await execute_sync_projections(
        envelope,
        {'user_account': projector}
    )

    # Verify
    assert result['handlers_executed'] == 1
    assert result['success'] is True
```

### Migration from sync_events.py

**Old System (DEPRECATED):**
```python
# app/user_account/sync_events.py
SYNC_EVENTS = [
    "UserAccountCreated",
    "UserAccountDeleted"
]

# app/user_account/projectors.py
async def on_user_created(self, event_dict: Dict[str, Any]) -> None:
    pass
```

**New System (CURRENT):**
```python
# NO sync_events.py file needed!

# app/user_account/projectors.py
@sync_projection("UserAccountCreated")  # Decorator is config
async def on_user_created(self, envelope: EventEnvelope) -> None:
    pass
```

**Migration Steps:**
1. Delete `sync_events.py` file
2. Add `@sync_projection` decorators to projector methods
3. Change signature from `event_dict` to `envelope: EventEnvelope`
4. Access data via `envelope.event_data` instead of `event_dict`
5. Test with EventProcessorWorker

---

## 🏗️ Domain Architecture Patterns

### Aggregate Event Sourcing Pattern

**1. Event Application Flow**

```python
class Position:
    """Position Aggregate Root"""

    def __init__(self, position_id: UUID):
        self.position_id = position_id
        self._version = 0
        self._uncommitted_events = []
        # ... state fields

    # PUBLIC METHOD - Call from outside
    def apply(self, event: Any):
        """Apply event and record (public alias)"""
        self._apply_and_record(event)

    # PRIVATE METHOD - Apply and record
    def _apply_and_record(self, event: Any):
        """Apply event to state and record as uncommitted"""
        self._apply(event)
        self._uncommitted_events.append(event)
        self._version += 1

    # PRIVATE METHOD - Route to handler
    def _apply(self, event: BaseEvent) -> None:
        """Route event to specific handler"""
        event_class_name = event.__class__.__name__
        snake_case_name = ''.join(['_' + c.lower() if c.isupper() else c for c in event_class_name]).lstrip('_')
        handler_name = f"_on_{snake_case_name}"
        handler = getattr(self, handler_name, None)
        if handler:
            handler(event)

    # EVENT HANDLERS - Update state
    def _on_position_opened_event(self, event: PositionOpenedEvent):
        """Apply PositionOpenedEvent"""
        self.status = PositionStatus.OPEN
        self.symbol = event.symbol
        self.opened_at = event.opened_at
        # ... update all state from event
```

**2. Business Methods Pattern**

```python
class Position:
    """Position Aggregate Root"""

    # FACTORY METHOD
    @staticmethod
    def open(
        position_id: UUID,
        user_id: UUID,
        symbol: str,
        # ... other params
    ) -> 'Position':
        """Factory method to create new position"""
        position = Position(position_id)

        # Create event
        event = PositionOpenedEvent(
            aggregate_id=str(position_id),
            position_id=position_id,
            user_id=user_id,
            symbol=symbol,
            opened_at=datetime.now(UTC),  # Use UTC!
        )

        # Apply event
        position.apply(event)

        return position

    # BUSINESS METHOD
    def add_to_position(
        self,
        order_id: UUID,
        quantity: Decimal,
        price: Decimal,
        # ... other params
    ) -> None:
        """Add to position (pyramiding)"""

        # VALIDATION FIRST
        if self.status != PositionStatus.OPEN:
            raise InvalidPositionStateError()

        if not self.pyramiding_enabled:
            raise PyramidingNotEnabledError()

        # VALIDATE PYRAMID RULES
        validation_result = self._validate_pyramid_entry(quantity, price, account_equity)
        if not validation_result.is_valid:
            # Emit validation failed event
            event = PyramidValidationFailedEvent(
                aggregate_id=str(self.position_id),
                position_id=self.position_id,
                reasons=validation_result.failure_reasons,
                rejected_at=datetime.now(UTC),
            )
            self.apply(event)
            raise PyramidValidationError(validation_result.failure_reasons)

        # CALCULATE NEW STATE
        new_quantity = self.quantity + quantity
        new_avg_price = self._calculate_weighted_average_price(quantity, price)

        # CREATE AND APPLY EVENT
        event = PositionIncreasedEvent(
            aggregate_id=str(self.position_id),
            position_id=self.position_id,
            entry_id=uuid4(),
            entry_sequence=len(self.entries) + 1,
            quantity=quantity,
            price=price,
            new_quantity=new_quantity,
            new_average_price=new_avg_price,
            pyramided_at=datetime.now(UTC),
        )
        self.apply(event)
```

---

### Value Objects Pattern

**Immutable frozen dataclasses**

```python
from dataclasses import dataclass, field
from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional

@dataclass(frozen=True)  # Immutable!
class PositionEntry:
    """
    Position Entry Value Object

    Represents a single pyramid entry into a position.
    Immutable once created.
    """
    entry_id: UUID
    entry_sequence: int  # 1, 2, 3...
    order_id: UUID
    quantity: Decimal
    price: Decimal
    entry_date: datetime
    entry_reason: str
    market_condition: Optional[str] = None
    commission: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")

    def __post_init__(self):
        """Validation after initialization"""
        if self.quantity <= 0:
            raise ValueError("Entry quantity must be positive")
        if self.price <= 0:
            raise ValueError("Entry price must be positive")
        if self.entry_sequence < 1:
            raise ValueError("Entry sequence must be >= 1")


@dataclass(frozen=True)
class PyramidingConfig:
    """
    Pyramiding Configuration Value Object

    Controls pyramiding strategy behavior.
    """
    enabled: bool = True
    max_entries: int = 5  # Max pyramid levels
    size_factor: Decimal = Decimal("0.5")  # 50% size reduction per entry
    min_profit_to_pyramid: Decimal = Decimal("0.02")  # 2% minimum profit
    min_spacing_percentage: Decimal = Decimal("0.03")  # 3% minimum spacing
    move_stop_on_pyramid: bool = True  # Adjust stop loss
    breakeven_after_entry: int = 2  # Move to breakeven after entry N

    def __post_init__(self):
        """Validation"""
        if not (1 <= self.max_entries <= 10):
            raise ValueError("Max entries must be 1-10")
        if not (Decimal("0") <= self.size_factor <= Decimal("1")):
            raise ValueError("Size factor must be 0-1")
        if self.breakeven_after_entry > self.max_entries:
            raise ValueError("Breakeven entry must be <= max entries")

    @property
    def is_enabled(self) -> bool:
        """Check if pyramiding is enabled"""
        return self.enabled and self.max_entries > 1

    def calculate_next_size(self, current_size: Decimal) -> Decimal:
        """Calculate next pyramid entry size"""
        return current_size * self.size_factor
```

**Usage in Aggregate**:
```python
class Position:
    """Position Aggregate Root"""

    def __init__(self, position_id: UUID):
        # ...
        self.entries: List[PositionEntry] = []  # List of VOs
        self.pyramiding_config: Optional[PyramidingConfig] = None  # VO

    def _on_position_opened_event(self, event: PositionOpenedEvent):
        """Apply PositionOpenedEvent"""
        # Reconstruct PositionEntry VO
        entry = PositionEntry(
            entry_id=event.entry_id,
            entry_sequence=1,
            order_id=event.order_id,
            quantity=event.quantity,
            price=event.price,
            entry_date=event.opened_at,
            entry_reason=event.entry_reason,
            commission=event.commission,
        )
        self.entries.append(entry)

        # Reconstruct PyramidingConfig VO
        if event.pyramiding_enabled:
            self.pyramiding_config = PyramidingConfig(
                enabled=event.pyramiding_enabled,
                max_entries=event.pyramiding_max_entries,
                size_factor=event.pyramiding_size_factor,
                min_profit_to_pyramid=event.pyramiding_min_profit,
                min_spacing_percentage=event.pyramiding_min_spacing,
                move_stop_on_pyramid=event.pyramiding_move_stop,
                breakeven_after_entry=event.pyramiding_breakeven_after,
            )
```

---

### Event Flattening Pattern (Derivatives Support)

**Commands use VALUE OBJECTS → Events FLATTEN → Apply methods RECONSTRUCT**

```python
# 1. COMMAND uses Value Objects
@dataclass
class CreateAutomationCommand:
    """Create automation"""
    user_id: UUID
    name: str
    symbol: str
    asset_type: AssetType

    # Value Objects (NOT flattened)
    option_details: Optional[OptionDetails] = None  # VO
    future_details: Optional[FutureDetails] = None  # VO
    pyramiding_config: Optional[PyramidingConfig] = None  # VO
    position_sizing: Optional[PositionSizingConfig] = None  # VO


# 2. HANDLER extracts and flattens for event
class AutomationLifecycleHandlers:

    async def handle_create_automation(self, cmd: CreateAutomationCommand):
        """Create automation"""

        # Call factory method (which creates event)
        automation = Automation.create(
            automation_id=uuid4(),
            user_id=cmd.user_id,
            name=cmd.name,
            symbol=cmd.symbol,
            asset_type=cmd.asset_type,
            option_details=cmd.option_details,  # Pass VO
            future_details=cmd.future_details,  # Pass VO
            pyramiding_config=cmd.pyramiding_config,  # Pass VO
        )

        # Save aggregate
        await self.save_aggregate(automation, "Automation")


# 3. AGGREGATE factory method flattens VOs for event
class Automation:

    @staticmethod
    def create(
        automation_id: UUID,
        user_id: UUID,
        name: str,
        symbol: str,
        asset_type: AssetType,
        option_details: Optional[OptionDetails] = None,  # VO
        future_details: Optional[FutureDetails] = None,  # VO
        pyramiding_config: Optional[PyramidingConfig] = None,  # VO
    ) -> 'Automation':
        """Factory method"""

        automation = Automation(automation_id)

        # FLATTEN VALUE OBJECTS for event
        event = AutomationCreatedEvent(
            aggregate_id=str(automation_id),
            automation_id=automation_id,
            user_id=user_id,
            name=name,
            symbol=symbol,
            asset_type=asset_type,

            # FLATTEN OptionDetails (7 fields)
            option_underlying_symbol=option_details.underlying_symbol if option_details else None,
            option_strike_price=option_details.strike_price if option_details else None,
            option_expiration_date=option_details.expiration_date if option_details else None,
            option_type=option_details.option_type if option_details else None,
            option_action=option_details.option_action if option_details else None,
            option_contract_size=option_details.contract_size if option_details else None,
            option_multiplier=option_details.multiplier if option_details else None,

            # FLATTEN FutureDetails (9 fields)
            future_underlying_symbol=future_details.underlying_symbol if future_details else None,
            # ... (9 fields total)

            # FLATTEN PyramidingConfig (7 fields)
            pyramiding_enabled=pyramiding_config.enabled if pyramiding_config else False,
            pyramiding_max_entries=pyramiding_config.max_entries if pyramiding_config else 5,
            pyramiding_size_factor=pyramiding_config.size_factor if pyramiding_config else Decimal("0.5"),
            # ... (7 fields total)

            occurred_at=datetime.now(UTC),
        )

        automation.apply(event)
        return automation


# 4. EVENT has flattened fields (17 for derivatives + 7 for pyramiding)
class AutomationCreatedEvent(BaseEvent):
    """Automation created with derivatives and pyramiding support"""
    event_type: Literal["AutomationCreatedEvent"] = "AutomationCreatedEvent"

    automation_id: UUID
    user_id: UUID
    name: str
    symbol: str
    asset_type: AssetType

    # FLATTENED Option Details (7 fields)
    option_underlying_symbol: Optional[str] = None
    option_strike_price: Optional[Decimal] = None
    option_expiration_date: Optional[datetime] = None
    option_type: Optional[OptionType] = None
    option_action: Optional[OptionAction] = None
    option_contract_size: Optional[int] = None
    option_multiplier: Optional[Decimal] = None

    # FLATTENED Future Details (9 fields)
    future_underlying_symbol: Optional[str] = None
    # ... (9 fields total)

    # FLATTENED Pyramiding Config (7 fields)
    pyramiding_enabled: bool = False
    pyramiding_max_entries: int = 5
    pyramiding_size_factor: Decimal = Decimal("0.5")
    pyramiding_min_profit: Decimal = Decimal("0.02")
    pyramiding_min_spacing: Decimal = Decimal("0.03")
    pyramiding_move_stop: bool = True
    pyramiding_breakeven_after: int = 2

    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# 5. APPLY METHOD reconstructs Value Objects
class Automation:

    def _apply_automation_created_event(self, event: AutomationCreatedEvent):
        """Apply creation event - reconstruct value objects from flattened data"""

        self.automation_id = event.automation_id
        self.user_id = event.user_id
        self.name = event.name
        self.symbol = event.symbol
        self.asset_type = event.asset_type

        # RECONSTRUCT OptionDetails VO from 7 flattened fields
        if event.option_underlying_symbol:
            self.option_details = OptionDetails(
                underlying_symbol=event.option_underlying_symbol,
                strike_price=event.option_strike_price,
                expiration_date=event.option_expiration_date,
                option_type=event.option_type,
                option_action=event.option_action,
                contract_size=event.option_contract_size or 100,
                multiplier=event.option_multiplier or Decimal("1"),
            )
        else:
            self.option_details = None

        # RECONSTRUCT FutureDetails VO from 9 flattened fields
        if event.future_underlying_symbol:
            self.future_details = FutureDetails(
                underlying_symbol=event.future_underlying_symbol,
                # ... (9 fields total)
            )
        else:
            self.future_details = None

        # RECONSTRUCT PyramidingConfig VO from 7 flattened fields
        self.pyramiding_config = PyramidingConfig(
            enabled=event.pyramiding_enabled,
            max_entries=event.pyramiding_max_entries,
            size_factor=event.pyramiding_size_factor,
            min_profit_to_pyramid=event.pyramiding_min_profit,
            min_spacing_percentage=event.pyramiding_min_spacing,
            move_stop_on_pyramid=event.pyramiding_move_stop,
            breakeven_after_entry=event.pyramiding_breakeven_after,
        )

        self.created_at = event.occurred_at
```

**Why this pattern**:
- **Commands**: Developer-friendly (use VOs)
- **Events**: Serialization-friendly (flat structure)
- **Aggregate**: Reconstruction (rebuild VOs from events)
- **Projectors**: Can access flat fields directly

---

### SQL Aggregate Functions Pattern

**When using GROUP BY with aggregate functions**

❌ **WRONG**:
```python
# This query will fail: user_id not in GROUP BY or aggregate function
query = """
    SELECT
        user_id,  -- ERROR: not in GROUP BY!
        COUNT(*) as total_positions,
        SUM(unrealized_pnl) as total_pnl
    FROM positions
    WHERE user_id = $1
"""
```

✅ **CORRECT** (Option 1 - Use parameter):
```python
query = """
    SELECT
        $1 as user_id,  -- Use parameter directly
        COUNT(*) as total_positions,
        SUM(unrealized_pnl) as total_pnl
    FROM positions
    WHERE user_id = $1
"""
```

✅ **CORRECT** (Option 2 - Use GROUP BY):
```python
query = """
    SELECT
        user_id,
        COUNT(*) as total_positions,
        SUM(unrealized_pnl) as total_pnl
    FROM positions
    WHERE user_id = $1
    GROUP BY user_id  -- Add GROUP BY
"""
```

**Position read repo example** (Fixed in `app/infra/read_repos/position_read_repo.py:265-289`):
```python
async def get_portfolio_summary(
    self,
    user_id: UUID,
    broker_account_id: Optional[UUID] = None
) -> PortfolioSummaryReadModel:
    """Get portfolio summary for a user/account"""

    conditions = ["user_id = $1"]
    params = [user_id]

    if broker_account_id:
        conditions.append("broker_account_id = $2")
        params.append(broker_account_id)

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            $1 as user_id,  -- ✅ Use parameter directly
            COALESCE(MAX(broker_account_id), {'$2' if broker_account_id else 'NULL'}) as broker_account_id,
            COUNT(*) as total_positions,
            COUNT(*) FILTER (WHERE status = 'open') as open_positions,
            COALESCE(SUM(unrealized_pnl) FILTER (WHERE status = 'open'), 0) as total_unrealized_pnl,
            COALESCE(SUM(realized_pnl), 0) as total_realized_pnl
        FROM positions
        WHERE {where_clause}
    """

    row = await pg_db_proxy.fetchrow(query, *params)
    return PortfolioSummaryReadModel(**dict(row))
```

---

### BaseQueryHandler Pattern ⭐ UPDATED (2025-11-08)

**All query handlers MUST extend BaseQueryHandler for consistency**

#### Overview

BaseQueryHandler provides standardized patterns for:
- ✅ **Error handling** - `handle_not_found()` helper
- ✅ **Authorization** - `validate_resource_ownership()` helper
- ✅ **Logging** - Instance-level `self.log` (not module-level)
- ✅ **Type safety** - Generic type parameters `[TQuery, TResult]`
- ⭐ **Read-Only Marker** - `@readonly_query` decorator (industry standard)

#### ❌ OLD PATTERN (Function-based)

```python
import logging

log = logging.getLogger("tradecore.position.handlers")  # Module-level

@query_handler(GetPositionQuery)
async def handle_get_position(
    query: GetPositionQuery,
    deps: HandlerDependencies
) -> Optional[PositionReadModel]:
    """Get position by ID"""
    position = await deps.position_read_repo.get_by_id(query.position_id)

    # ❌ Manual error handling
    if not position:
        log.error(f"Position {query.position_id} not found")
        raise PositionNotFoundError(query.position_id)

    # ❌ Manual authorization
    if query.user_id and position.user_id != query.user_id:
        log.error(f"User {query.user_id} not authorized for position {query.position_id}")
        raise UnauthorizedError()

    return position
```

#### ✅ NEW PATTERN (Class-based with BaseQueryHandler)

```python
from app.common.base.base_query_handler import BaseQueryHandler
from app.infra.cqrs.decorators import query_handler

@query_handler(GetPositionQuery)
class GetPositionQueryHandler(BaseQueryHandler[GetPositionQuery, Optional[PositionReadModel]]):
    """
    ✅ CLASS-BASED handler extending BaseQueryHandler

    Type parameters:
    - TQuery: GetPositionQuery
    - TResult: Optional[PositionReadModel]
    """

    def __init__(self, deps: HandlerDependencies):
        super().__init__()  # ✅ Initialize base class
        self.position_repo = deps.position_read_repo

    async def handle(self, query: GetPositionQuery) -> Optional[PositionReadModel]:
        """Handle GetPositionQuery - INSTANCE METHOD"""
        self.log.info(f"Fetching position {query.position_id}")  # ✅ self.log

        position = await self.position_repo.get_by_id(query.position_id)

        # ✅ Use helper method for error handling
        position = self.handle_not_found(
            resource=position,
            resource_type="Position",
            resource_id=query.position_id
        )

        # ✅ Use helper method for authorization
        if query.user_id:
            self.validate_resource_ownership(
                resource_user_id=position.user_id,
                requesting_user_id=query.user_id,
                resource_type="position"
            )

        return position
```

#### Migration Pattern

**Step 1: Change imports**

```python
# ❌ OLD
import logging
log = logging.getLogger("...")

# ✅ NEW
from app.common.base.base_query_handler import BaseQueryHandler
from app.infra.cqrs.decorators import query_handler
# Note: Remove module-level log
```

**Step 2: Convert function to class**

```python
# ❌ OLD
@query_handler(MyQuery)
async def handle_my_query(query, deps):
    pass

# ✅ NEW
@query_handler(MyQuery)
class MyQueryHandler(BaseQueryHandler[MyQuery, MyResultType]):
    def __init__(self, deps):
        super().__init__()
        self.my_repo = deps.my_read_repo

    async def handle(self, query: MyQuery) -> MyResultType:
        pass
```

**Step 3: Replace `log` with `self.log`**

```python
# ❌ OLD
log.info("Fetching position")
log.error(f"Position not found: {id}")

# ✅ NEW
self.log.info("Fetching position")
self.log.error(f"Position not found: {id}")
```

**Step 4: Use helper methods**

```python
# ❌ OLD - Manual error handling
if not resource:
    log.error(f"Resource {id} not found")
    raise ResourceNotFoundError(id)

# ✅ NEW - Use helper
resource = self.handle_not_found(
    resource=resource,
    resource_type="Position",
    resource_id=id
)

# ❌ OLD - Manual authorization
if resource.user_id != query.user_id:
    raise UnauthorizedError()

# ✅ NEW - Use helper
self.validate_resource_ownership(
    resource_user_id=resource.user_id,
    requesting_user_id=query.user_id,
    resource_type="position"
)
```

#### Important Rules

1. ✅ **ALWAYS** call `super().__init__()` in constructor
2. ✅ **ALWAYS** use `self.log` (never module-level `log`)
3. ✅ **ALWAYS** specify generic types: `BaseQueryHandler[TQuery, TResult]`
4. ✅ **ALWAYS** make `handle()` an instance method
5. ✅ **PREFER** helper methods (`handle_not_found`, `validate_resource_ownership`)
6. ✅ **KEEP** business logic in aggregates (handlers are thin orchestrators)

#### Cached Query Handlers

For frequently accessed data, use `@cached_query_handler`:

```python
from app.infra.cqrs.decorators import cached_query_handler

@cached_query_handler(GetAccountByIdQuery, ttl=30)
class GetAccountByIdQueryHandler(BaseQueryHandler[GetAccountByIdQuery, BrokerAccountDetails]):
    """Cached query with 30-second TTL"""

    def __init__(self, deps: HandlerDependencies):
        super().__init__()
        self.account_repo = deps.account_read_repo

    async def handle(self, query: GetAccountByIdQuery) -> BrokerAccountDetails:
        acc = await self.account_repo.get_by_id(query.account_id)

        acc = self.handle_not_found(
            resource=acc,
            resource_type="Account",
            resource_id=query.account_id
        )

        if query.user_id:
            self.validate_resource_ownership(
                resource_user_id=acc.user_id,
                requesting_user_id=query.user_id,
                resource_type="account"
            )

        return acc
```

**Important**: Import `cached_query_handler` from decorators, NOT from BaseQueryHandler!

```python
# ✅ CORRECT
from app.infra.cqrs.decorators import query_handler, cached_query_handler
from app.common.base.base_query_handler import BaseQueryHandler

# ❌ WRONG
from app.common.base.base_query_handler import BaseQueryHandler, cached_query_handler
```

#### Migration Statistics (Completed 2025-11-04)

**✅ Fully Migrated Domains:**
- Position: 14/14 handlers (100%)
- User Account: 44/44 handlers (100%)
- Automation: 8/9 handlers (88%)
- Order: 10/12 handlers (83%)

**⚙️ Partially Migrated:**
- Broker Account: 13/31 handlers (41%)
- Broker Connection: 22/70 handlers (31%)
- Virtual Broker: 0/36 handlers
- Portfolio: 0/4 handlers

**Total: 112/222 handlers migrated** across 30 files

#### Examples from Production Code

**Position Domain** (`app/position/query_handlers/position_query_handlers.py`):
```python
@query_handler(GetPositionQuery)
class GetPositionQueryHandler(BaseQueryHandler[GetPositionQuery, Optional[PositionReadModel]]):
    """Get position by ID with authorization"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.position_repo = deps.position_read_repo

    async def handle(self, query: GetPositionQuery) -> Optional[PositionReadModel]:
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

**User Account Domain** (`app/user_account/query_handlers/profile_query_handlers.py`):
```python
@cached_query_handler(GetUserProfileQuery, ttl=60)
class GetUserProfileQueryHandler(BaseQueryHandler[GetUserProfileQuery, Optional[UserProfile]]):
    """Get user profile with 60s cache"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetUserProfileQuery) -> Optional[UserProfile]:
        self.log.info(f"Fetching user profile for {query.user_id}")

        user = await self.user_repo.get_by_id(query.user_id)

        user = self.handle_not_found(
            resource=user,
            resource_type="User",
            resource_id=query.user_id
        )

        return user.to_profile()
```

#### When NOT to Migrate

Simple query handlers that don't need error handling or authorization can remain function-based:

```python
# ✅ OK to keep as function (no error handling needed)
@query_handler(ListBrokersQuery)
async def handle_list_brokers(
    query: ListBrokersQuery,
    deps: HandlerDependencies
) -> List[str]:
    """List available brokers - no auth needed"""
    return ["alpaca", "tradestation", "virtual"]
```

However, for consistency, migrating ALL handlers is recommended.

---

## ✅ Validated Patterns from Production Domains

### Automation Domain ✅ (4,309 lines, EXCELLENT)

**Event Sourcing**:
- ✅ Dynamic snake_case conversion in `apply()` method
- ✅ All 13 events have `event_type` fields
- ✅ All datetimes use `datetime.now(UTC)`
- ✅ All event handlers use snake_case (`_apply_automation_created_event`)

**Pyramiding Integration**:
- ✅ PyramidingConfig value object (7 fields)
- ✅ PyramidingConfigUpdatedEvent (ASYNC)
- ✅ UpdatePyramidingConfigCommand + Handler
- ✅ Flattening pattern in AutomationCreatedEvent

**Code Quality**:
- ✅ 0 instances of datetime.utcnow
- ✅ 0 instances of PascalCase methods
- ✅ 75% SYNC rate (9/12 projectors)
- ✅ 17 custom exceptions

### Position Domain ✅ (1,408 lines aggregate, EXCELLENT)

**Event Sourcing**:
- ✅ Dynamic snake_case conversion in `_apply()` method
- ✅ All 12 events have `event_type` fields
- ✅ All datetimes use `datetime.now(UTC)` (after fixes)
- ✅ All event handlers use snake_case (`_on_position_opened_event`)

**Pyramiding Implementation**:
- ✅ Comprehensive validation (`_validate_pyramid_entry()`)
- ✅ PositionEntry VO (17 fields)
- ✅ PyramidingConfig VO (7 fields)
- ✅ AddToPositionCommand + Handler
- ✅ PositionIncreasedEvent + PyramidValidationFailedEvent
- ✅ Weighted average price calculation
- ✅ Stop loss auto-adjustment
- ✅ position_entries table tracking

**Code Quality**:
- ✅ 0 instances of datetime.utcnow (after fixes)
- ✅ 0 instances of PascalCase methods
- ✅ 34 custom exceptions
- ✅ Side-aware calculations (LONG/SHORT)

### Order Domain ✅ (Validated)

**Event Sourcing**:
- ✅ All 16 events have `event_type` fields (after fixes)
- ✅ All datetimes use `datetime.now(UTC)`
- ✅ Dynamic CamelCase→snake_case conversion
- ✅ All event handlers use snake_case (`_apply_order_placed_event`)

**Derivatives Support**:
- ✅ OptionDetails VO (8 fields)
- ✅ FutureDetails VO (9 fields)
- ✅ Flattening in OrderPlacedEvent (17 derivatives fields)

---

## 📚 File Organization Examples

### Position Domain Structure ✅

```
app/position/
├── aggregate.py                              # 1,408 lines
├── events.py                                  # 506 lines (12 events) - ALL decorated with @domain_event()
├── commands.py                                # 390 lines (15 commands)
├── value_objects.py                           # 472 lines (13 VOs)
├── enums.py                                   # 200 lines (10 enums)
├── projectors.py                              # 614 lines (8 projectors) - Uses @sync_projection
├── read_models.py                             # 280 lines (7 read models)
├── queries.py                                 # 223 lines (14 queries)
├── exceptions.py                              # 403 lines (34 exceptions)
├── command_handlers/
│   ├── position_lifecycle_handlers.py        # 3 handlers
│   ├── pyramiding_handlers.py                # 2 handlers
│   ├── price_update_handlers.py              # 2 handlers
│   ├── risk_management_handlers.py           # 2 handlers
│   └── reconciliation_handlers.py            # 2 handlers
└── query_handlers/
    └── position_query_handlers.py            # Query handlers
```

**Note**: `sync_events.py` removed in 2025-11-13 refactor - @sync_projection decorator is single source of truth

### Automation Domain Structure ✅

```
app/automation/
├── aggregate.py                              # 955 lines
├── events.py                                  # 495 lines (13 events) - ALL decorated with @domain_event()
├── commands.py                                # 324 lines (16 commands)
├── value_objects.py                           # 322 lines (8 VOs)
├── enums.py                                   # 108 lines (11 enums)
├── projectors.py                              # 667 lines (12 projectors) - Uses @sync_projection
├── read_models.py                             # 239 lines (4 read models)
├── queries.py                                 # 50 lines (5 queries)
├── exceptions.py                              # 170 lines (17 exceptions)
├── command_handlers/
│   ├── lifecycle_handlers.py                 # 6 handlers
│   ├── signal_handlers.py                    # 1 handler
│   └── pyramiding_handlers.py                # 1 handler
└── query_handlers/
    └── automation_query_handlers.py          # 5 handlers
```

**Note**: `sync_events.py` removed in 2025-11-13 refactor - @sync_projection decorator is single source of truth

---

## 🎯 Summary

### ❌ NEVER DO:
1. ❌ `datetime.utcnow()` - Use `datetime.now(UTC)` instead
2. ❌ PascalCase method names - Use `snake_case` instead
3. ❌ Events without `event_type` field
4. ❌ `@dataclass` for events - Use Pydantic `BaseEvent` instead
5. ❌ SELECT columns without GROUP BY when using aggregate functions
6. ❌ Manually add domain events to event_registry.py - Use `@domain_event()` decorator
7. ❌ Create separate sync_events.py config files - Use `@sync_projection` decorator
8. ❌ Over-sync projections - Reserve SYNC for critical business logic only
9. ❌ Duplicate event definitions across domains - Define in origin domain only

### ✅ ALWAYS DO:
1. ✅ `from datetime import datetime, UTC`
2. ✅ `datetime.now(UTC)` for all datetime generation
3. ✅ `event_type: Literal["EventName"] = "EventName"` in ALL events
4. ✅ `snake_case` for ALL methods (`_on_event_name`, not `_on_EventName`)
5. ✅ Dynamic CamelCase→snake_case conversion in `_apply()` method
6. ✅ Frozen dataclasses for value objects (`@dataclass(frozen=True)`)
7. ✅ Event flattening for derivatives (17 fields) and pyramiding (7 fields)
8. ✅ Value object reconstruction in apply methods
9. ✅ Comprehensive validation in aggregates
10. ✅ Custom domain exceptions (inherit from base exceptions)
11. ✅ **NEW**: Use `@domain_event()` decorator for ALL domain events (auto-registration)
12. ✅ **NEW**: Use `@sync_projection` ONLY for critical projections (security, authorization, user-facing)
13. ✅ **NEW**: Use ASYNC projections (no decorator) for analytics, logging, notifications
14. ✅ **NEW**: Document projection consistency requirements in docstrings

### 📊 Code Quality Metrics:
- **Automation Domain**: ✅ A+ (0 violations)
- **Position Domain**: ✅ A+ (0 violations after fixes)
- **Order Domain**: ✅ A+ (0 violations after fixes)

### 🚀 2025-11-13 Event Bus Refactor:
- **Event Registration**: 189 events migrated to @domain_event() decorator
- **Code Reduction**: event_registry.py reduced from 713 → 212 lines (70%)
- **SYNC Optimization**: Reduced from 69 → 54 SYNC projections (22% reduction)
- **Performance Gain**: +20% throughput, -27% latency
- **Files Deleted**: 8 redundant sync_events.py config files removed
- **Decorator is Single Source of Truth**: @sync_projection replaces separate config

### 📚 Key References:
- **Event Auto-Registration**: See "Event Auto-Registration Pattern" section above
- **SYNC Optimization**: See "SYNC vs ASYNC Projection Pattern" section above
- **Full Refactor Details**: `/docs/EVENT_BUS_AUTO_REGISTRATION_2025.md`
- **Migration Guide**: Included in auto-registration section

---

**Last Updated**: 2025-11-13
**Validated Against**: Automation, Position, Order, User, BrokerAccount, BrokerConnection, VirtualBroker, Portfolio domains
**Status**: ✅ Production-ready patterns with 2025 event bus optimizations
