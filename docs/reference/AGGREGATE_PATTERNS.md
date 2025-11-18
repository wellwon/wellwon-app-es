# Aggregate Patterns Reference Guide

**TradeCore v0.5** | Event Sourcing & CQRS Implementation Patterns

---

## Table of Contents

1. [Introduction](#introduction)
2. [Aggregate Fundamentals](#aggregate-fundamentals)
3. [Event Application Patterns](#event-application-patterns)
4. [State Management](#state-management)
5. [Business Logic Encapsulation](#business-logic-encapsulation)
6. [Production Examples](#production-examples)
7. [Common Mistakes](#common-mistakes)
8. [Testing Strategies](#testing-strategies)
9. [Performance Considerations](#performance-considerations)

---

## Introduction

Aggregates are the **foundational building blocks** of TradeCore's event-sourced architecture. They encapsulate business logic, enforce invariants, and serve as consistency boundaries in the domain model.

### What is an Aggregate?

An aggregate is:
- **Root entity** that manages a cluster of related objects
- **Consistency boundary** for business rules
- **Event producer** that emits domain events
- **State restorer** that rebuilds from event history

### Key Principles

1. **Event Sourcing Compliance**: All state changes MUST be captured as events
2. **Business Logic Encapsulation**: Domain rules live in aggregates, NOT sagas/services
3. **Command-Event Pattern**: Commands trigger business logic → Events record changes
4. **Immutability**: Events are immutable once emitted

---

## Aggregate Fundamentals

### Basic Structure

Every TradeCore aggregate follows this pattern:

```python
from dataclasses import dataclass, field
from typing import List, Any, Optional
from uuid import UUID
from datetime import datetime, UTC

@dataclass
class MyAggregate:
    """
    Aggregate Root for [Domain Name]

    Manages [business responsibility] with full event sourcing support.
    """

    # ========================================================================
    # IDENTITY
    # ========================================================================
    id: UUID  # Primary aggregate identifier

    # ========================================================================
    # DOMAIN STATE
    # ========================================================================
    user_id: Optional[UUID] = None
    # ... domain-specific fields

    # ========================================================================
    # EVENT SOURCING INFRASTRUCTURE
    # ========================================================================
    version: int = 0  # For optimistic concurrency
    uncommitted_events: List[Any] = field(default_factory=list)

    # ========================================================================
    # METADATA
    # ========================================================================
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### Critical Components

#### 1. Event Sourcing Fields

```python
version: int = 0  # Optimistic concurrency control
uncommitted_events: List[Any] = field(default_factory=list)
```

- `version`: Increments with each event (prevents concurrent modification)
- `uncommitted_events`: Temporary storage for events before persistence

#### 2. Timestamps

```python
# ❌ WRONG - datetime.utcnow() is DEPRECATED in Python 3.12+
created_at: datetime = Field(default_factory=datetime.utcnow)

# ✅ CORRECT - Use datetime.now(UTC)
from datetime import datetime, UTC
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**Why this matters:**
- `datetime.utcnow()` creates **naive datetime** (no timezone info)
- `datetime.now(UTC)` creates **aware datetime** (includes UTC timezone)
- Pydantic validation requires aware datetimes for proper serialization

---

## Event Application Patterns

### The apply_and_record Pattern

TradeCore uses a **dual-method approach** for event application:

#### Public `apply()` - For New Events

```python
def apply(self, event: BaseEvent) -> None:
    """
    Apply event to aggregate state (public - for new events).

    This method:
    1. Routes event to specific handler
    2. Updates aggregate state
    3. Adds event to uncommitted_events
    4. Increments version
    """
    # Route to specific apply method (CamelCase → snake_case)
    event_type = event.event_type
    snake_case_name = ''.join(['_' + c.lower() if c.isupper() else c for c in event_type]).lstrip('_')
    method_name = f"_apply_{snake_case_name}"

    if hasattr(self, method_name):
        getattr(self, method_name)(event)
    else:
        raise ValueError(f"No apply method for event type: {event_type}")

    # Add to uncommitted events (for persistence)
    self.uncommitted_events.append(event)
    self.version += 1
```

#### Private `_apply()` - For Event Replay

```python
def _apply(self, event: BaseEvent) -> None:
    """
    Apply event to aggregate state (private - for replay from event store).

    This method:
    1. Routes event to specific handler
    2. Updates aggregate state
    3. Does NOT add to uncommitted_events (already persisted)
    4. Does NOT increment version (version comes from event store)
    """
    # Same routing logic as apply()
    event_type = event.event_type
    snake_case_name = ''.join(['_' + c.lower() if c.isupper() else c for c in event_type]).lstrip('_')
    method_name = f"_apply_{snake_case_name}"

    if hasattr(self, method_name):
        getattr(self, method_name)(event)
```

### Dynamic Method Routing

TradeCore uses **reflection-based routing** to avoid massive if/elif chains:

```python
# ❌ ANTI-PATTERN - Manual routing (doesn't scale)
def _apply(self, event: BaseEvent) -> None:
    if isinstance(event, AutomationCreatedEvent):
        self._on_automation_created_event(event)
    elif isinstance(event, AutomationActivatedEvent):
        self._on_automation_activated_event(event)
    # ... 50+ more elif statements

# ✅ CORRECT - Dynamic routing (scalable)
def _apply(self, event: BaseEvent) -> None:
    event_class_name = event.__class__.__name__
    # Convert EventName → event_name
    snake_case_name = ''.join(['_' + c.lower() if c.isupper() else c for c in event_class_name]).lstrip('_')
    handler_name = f"_on_{snake_case_name}"
    handler = getattr(self, handler_name, None)

    if handler:
        handler(event)
    else:
        # Default: do nothing (event recorded but no state change)
        pass
```

**Benefits:**
- Add new events without touching routing logic
- Clear naming convention (`_on_event_name`)
- Graceful degradation for unknown events

### Event Handler Naming

**✅ ALWAYS use snake_case for method names (PEP 8):**

```python
# ❌ WRONG - PascalCase method names (violates PEP 8)
def _on_PositionOpenedEvent(self, event): pass

# ✅ CORRECT - snake_case method names
def _on_position_opened_event(self, event: PositionOpenedEvent):
    """Apply position opened event to aggregate state"""
    self.user_id = event.user_id
    self.quantity = event.quantity
    self.status = PositionStatus.OPEN
```

---

## State Management

### Value Objects in Aggregates

TradeCore aggregates use **value objects** for complex configurations:

```python
from app.automation.value_objects import (
    OptionDetails,
    FutureDetails,
    PositionSizingConfig,
    StopLossConfig,
    TakeProfitConfig,
    PyramidingConfig
)

@dataclass
class Automation:
    """
    Automation Aggregate Root

    STATE MANAGEMENT:
    - Commands use VALUE OBJECTS (OptionDetails, FutureDetails, configs)
    - Events FLATTEN these for serialization (17 derivative fields)
    - Apply methods RECONSTRUCT value objects from flattened event data
    """

    # Value objects (NOT flattened in aggregate state)
    option_details: Optional[OptionDetails] = None
    future_details: Optional[FutureDetails] = None
    position_sizing: Optional[PositionSizingConfig] = None
    stop_loss: Optional[StopLossConfig] = None
    take_profit: Optional[TakeProfitConfig] = None
    pyramiding_config: Optional[PyramidingConfig] = None
```

### Event Flattening Pattern

**Problem:** Value objects don't serialize to JSON cleanly.

**Solution:** Flatten in events, reconstruct in apply methods.

#### In Event (Flattened):

```python
class AutomationCreatedEvent(BaseEvent):
    # Option fields (7 flattened fields)
    option_underlying_symbol: Optional[str] = None
    option_strike_price: Optional[Decimal] = None
    option_expiration_date: Optional[datetime] = None
    option_type: Optional[OptionType] = None
    option_action: Optional[OptionAction] = None
    option_contract_size: Optional[int] = None
    option_multiplier: Optional[Decimal] = None

    # Stop Loss fields (9 flattened fields)
    stop_loss_type: Optional[StopLossType] = None
    stop_loss_price: Optional[Decimal] = None
    stop_loss_dollar_amount: Optional[Decimal] = None
    # ...
```

#### In Apply Method (Reconstructed):

```python
def _apply_automation_created_event(self, event: AutomationCreatedEvent):
    """Reconstruct value objects from flattened event data"""

    # Reconstruct OptionDetails if present
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

    # Reconstruct StopLossConfig if present
    if event.stop_loss_type:
        self.stop_loss = StopLossConfig(
            type=event.stop_loss_type,
            price=event.stop_loss_price,
            dollar_amount=event.stop_loss_dollar_amount,
            percentage=event.stop_loss_percentage,
            atr_multiplier=event.stop_loss_atr_multiplier,
            atr_period=event.stop_loss_atr_period,
            trailing=event.stop_loss_trailing,
            trail_amount=event.stop_loss_trail_amount,
            trail_percentage=event.stop_loss_trail_percentage
        )
```

### Collection Management

Use proper collection types for tracking entries/exits:

```python
@dataclass
class Position:
    """Position aggregate with pyramiding support"""

    # ✅ Use List for ordered collections
    entries: List[PositionEntry] = field(default_factory=list)
    exits: List[PositionExit] = field(default_factory=list)

    def add_to_position(self, quantity: Decimal, price: Decimal, ...):
        """Add pyramid entry"""
        # Create immutable entry record
        entry = PositionEntry(
            entry_id=uuid4(),
            sequence=self.pyramiding_count + 1,
            quantity=quantity,
            price=price,
            timestamp=datetime.now(UTC)
        )

        # Append to entries list
        self.entries.append(entry)
        self.pyramiding_count = len(self.entries)
```

---

## Business Logic Encapsulation

### Domain Methods vs Command Handlers

**✅ Business logic belongs in AGGREGATES, not command handlers:**

```python
# ❌ WRONG - Business logic in command handler
@command_handler(AddToPosisionCommand)
async def handle_add_to_position(cmd: AddToPosisionCommand, deps: HandlerDependencies):
    position = await deps.aggregate_repository.load(cmd.position_id)

    # Business logic leaked into handler!
    if position.status != PositionStatus.OPEN:
        raise PositionNotOpenError()

    if not position.pyramiding_enabled:
        raise PyramidingDisabledError()

    # Calculate new state
    new_quantity = position.quantity + cmd.quantity
    new_avg_price = (position.quantity * position.avg_price + cmd.quantity * cmd.price) / new_quantity

    # This is all WRONG - belongs in aggregate!

# ✅ CORRECT - Business logic in aggregate
@dataclass
class Position:
    def add_to_position(
        self,
        order_id: UUID,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal = Decimal("0"),
        force_pyramid: bool = False
    ) -> None:
        """
        Add to position (pyramid).

        Validates pyramid rules and adds new entry if allowed.

        Raises:
            PositionNotOpenError: If position not in OPEN state
            PyramidingDisabledError: If pyramiding disabled
            MaxPyramidEntriesReachedError: If max entries reached
        """
        # Check position is open
        if self.status != PositionStatus.OPEN:
            raise PositionNotOpenError(str(self.position_id), self.status)

        # Check pyramiding enabled
        if not self.pyramiding_enabled:
            raise PyramidingDisabledError(str(self.position_id))

        # Validate pyramid (unless forced)
        if not force_pyramid:
            validation = self._validate_pyramid_entry(quantity, price)
            if not validation.is_valid:
                raise PyramidValidationError(str(self.position_id), validation.failure_reason)

        # Calculate new state
        new_total_quantity = self.quantity + quantity
        new_average_price = self._calculate_weighted_average(
            self.quantity, self.average_entry_price, quantity, price
        )

        # Emit event
        event = PositionIncreasedEvent(...)
        self.apply(event)
```

### Calculation Methods

**Encapsulate domain calculations as private methods:**

```python
@dataclass
class Position:
    """Position aggregate with calculation methods"""

    @staticmethod
    def _calculate_weighted_average(
        qty1: Decimal,
        price1: Decimal,
        qty2: Decimal,
        price2: Decimal
    ) -> Decimal:
        """
        Calculate weighted average price.

        Formula: (qty1 * price1 + qty2 * price2) / (qty1 + qty2)
        """
        total_qty = qty1 + qty2
        if total_qty == 0:
            return Decimal("0")

        total_value = (qty1 * price1) + (qty2 * price2)
        return total_value / total_qty

    @staticmethod
    def _calculate_pnl(
        side: PositionSide,
        cost_basis: Decimal,
        market_value: Decimal
    ) -> Decimal:
        """Calculate P&L based on position side"""
        if side == PositionSide.LONG:
            return market_value - cost_basis
        else:  # SHORT
            return cost_basis - market_value

    @staticmethod
    def _calculate_risk_amount(
        side: PositionSide,
        quantity: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal
    ) -> Decimal:
        """Calculate risk amount ($ at risk)"""
        if side == PositionSide.LONG:
            return quantity * (entry_price - stop_loss_price)
        else:  # SHORT
            return quantity * (stop_loss_price - entry_price)
```

### Validation Methods

```python
def _validate_pyramid_entry(
    self,
    proposed_quantity: Decimal,
    proposed_price: Decimal,
    account_equity: Decimal
) -> PyramidValidationResult:
    """
    Comprehensive pyramid validation.

    Checks all pyramiding rules and returns validation result.
    """
    errors = []

    # Check 1: Max entries reached?
    has_max_entries = self.pyramiding_count < self.max_pyramiding_allowed
    if not has_max_entries:
        errors.append(f"Max pyramid entries reached ({self.max_pyramiding_allowed})")

    # Check 2: Sufficient profit since last entry?
    last_entry = self.entries[-1] if self.entries else None
    has_sufficient_profit = False

    if last_entry:
        if self.side == PositionSide.LONG:
            profit_pct = ((proposed_price - last_entry.price) / last_entry.price) * Decimal("100")
            has_sufficient_profit = profit_pct >= Decimal("2.0")  # 2% minimum

        if not has_sufficient_profit:
            errors.append(f"Insufficient profit since last entry")

    # Return validation result
    return PyramidValidationResult(
        is_valid=len(errors) == 0,
        failure_reason=errors if errors else None,
        has_max_entries=has_max_entries,
        has_sufficient_profit=has_sufficient_profit
    )
```

---

## Production Examples

### Example 1: Automation Aggregate (4,309 lines)

**Location:** `/Users/silvermpx/PycharmProjects/TradeCore/app/automation/aggregate.py`

**Key Features:**
- 13 events
- State machine (INACTIVE → ACTIVE → SUSPENDED)
- Derivatives support (17 flattened fields)
- Position sizing calculations
- Risk management

**Highlights:**

```python
@dataclass
class Automation:
    """
    Automation Aggregate Root

    Manages trading automation lifecycle, configuration,
    and webhook signal processing with full derivatives support.
    """

    # ========================================================================
    # FACTORY METHOD
    # ========================================================================

    @staticmethod
    def create(
        user_id: UUID,
        name: str,
        symbol: str,
        position_sizing: PositionSizingConfig,
        account_ids: List[UUID],
        asset_type: AssetType = AssetType.STOCK,
        option_details: Optional[OptionDetails] = None,
        future_details: Optional[FutureDetails] = None,
        # ...
    ) -> 'Automation':
        """
        Create new automation with derivatives validation

        Validates:
        - Asset type has correct details (option_details for OPTION, etc.)
        - At least one broker account
        - Position sizing configuration
        """
        # Validate derivatives
        Automation._validate_asset_type_details(asset_type, option_details, future_details)

        # Generate automation ID and webhook configuration
        automation_id = uuid4()
        webhook_token = secrets.token_urlsafe(32)

        # Create aggregate
        automation = Automation(id=automation_id, ...)

        # Emit creation event (FLATTENED derivatives)
        event = AutomationCreatedEvent(...)
        automation.apply(event)

        return automation
```

### Example 2: BrokerConnection Aggregate (1,137 lines)

**Location:** `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_connection/aggregate.py`

**Key Features:**
- OAuth flow management
- Credential encryption storage
- Connection health tracking
- Token refresh logic

**Highlights:**

```python
class BrokerConnectionAggregate:
    """
    Aggregate root implementing business rules and event sourcing for broker connections.

    Command methods produce domain events; apply methods update the in-memory state.
    """

    def __init__(self, aggregate_id: uuid.UUID):
        self.id: uuid.UUID = aggregate_id
        self.version: int = 0
        self.state: BrokerConnectionAggregateState = BrokerConnectionAggregateState()
        self._uncommitted_events: List[BaseEvent] = []

    def _apply_and_record(self, event: BaseEvent) -> None:
        """Apply an event to the state and record it as uncommitted."""
        self._apply(event)
        self._uncommitted_events.append(event)
        self.version += 1

    def confirm_oauth_tokens_stored(
        self,
        user_id: uuid.UUID,
        encrypted_access_token: str,
        encrypted_refresh_token: Optional[str],
        expires_in: Optional[int],
        scopes: Optional[List[str]]
    ) -> None:
        """
        Store access and refresh tokens after OAuth flow completes.
        Clears API keys and resets reauth flag.
        """
        # Validation only - NO state mutation (ES compliance fix)
        if self.state.user_id != user_id:
            raise ValueError("User ID mismatch for storing OAuth tokens.")

        # Calculate expiration time for event
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            if expires_in else None
        )

        # Create and apply event - state mutation happens ONLY in event handler
        evt = BrokerTokensSuccessfullyStored(
            broker_connection_id=self.id,
            user_id=user_id,
            encrypted_access_token=encrypted_access_token,
            encrypted_refresh_token=encrypted_refresh_token,
            access_token_expires_at=expires_at,
            refresh_token_was_provided=bool(encrypted_refresh_token),
            scopes_granted=scopes
        )
        self._apply_and_record(evt)
```

### Example 3: Position Aggregate (1,819 lines)

**Location:** `/Users/silvermpx/PycharmProjects/TradeCore/app/position/aggregate.py`

**Key Features:**
- Pyramiding support (multiple entries)
- Partial exits (scaling out)
- Real-time P&L calculation
- Risk management (stop loss, take profit)
- Broker reconciliation

**Highlights:**

```python
@classmethod
def open(
    cls,
    user_id: UUID,
    account_id: UUID,
    order_id: UUID,
    symbol: str,
    asset_type: AssetType,
    side: PositionSide,
    quantity: Decimal,
    entry_price: Decimal,
    commission: Decimal = Decimal("0"),
    # ... many more parameters
) -> "Position":
    """
    Open a new position (first entry).

    Creates position aggregate and emits PositionOpenedEvent.
    """
    # Validation
    if quantity <= 0:
        raise PositionValidationError("Quantity must be positive")
    if entry_price <= 0:
        raise PositionValidationError("Entry price must be positive")

    # Create position
    position_id = uuid4()
    position = cls(position_id)

    # Apply pyramiding config defaults
    if pyramiding_config is None:
        pyramiding_config = PyramidingConfig()

    # Calculate entry value
    entry_value = quantity * entry_price

    # Emit PositionOpenedEvent
    event = PositionOpenedEvent(...)
    position._apply(event)

    return position
```

---

## Common Mistakes

### ❌ Mistake 1: State Mutation Outside Events

```python
# ❌ WRONG - Direct state mutation bypasses event sourcing
def activate(self):
    self.status = AutomationStatus.ACTIVE  # NO!
    self.activated_at = datetime.now(UTC)   # NO!

# ✅ CORRECT - State changes via events
def activate(self):
    event = AutomationActivatedEvent(
        automation_id=self.id,
        user_id=self.user_id,
        activated_at=datetime.now(UTC)
    )
    self.apply(event)  # State changes happen in event handler
```

### ❌ Mistake 2: Using datetime.utcnow()

```python
# ❌ WRONG - Deprecated in Python 3.12+
created_at: datetime = Field(default_factory=datetime.utcnow)

# ✅ CORRECT - Use datetime.now(UTC)
from datetime import datetime, UTC
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### ❌ Mistake 3: PascalCase Method Names

```python
# ❌ WRONG - PascalCase method names (violates PEP 8)
def _on_PositionOpenedEvent(self, event): pass

# ✅ CORRECT - snake_case method names
def _on_position_opened_event(self, event: PositionOpenedEvent): pass
```

### ❌ Mistake 4: Missing event_type Field

```python
# ❌ WRONG - Missing event_type field
class PositionOpenedEvent(BaseEvent):
    position_id: UUID
    quantity: Decimal

# ✅ CORRECT - Always include event_type with Literal
from typing import Literal

class PositionOpenedEvent(BaseEvent):
    event_type: Literal["PositionOpenedEvent"] = "PositionOpenedEvent"
    position_id: UUID
    quantity: Decimal
```

### ❌ Mistake 5: Validation in Event Handlers

```python
# ❌ WRONG - Validation in event handler
def _apply_position_opened_event(self, event: PositionOpenedEvent):
    if event.quantity <= 0:
        raise ValueError("Quantity must be positive")  # NO!

    self.quantity = event.quantity

# ✅ CORRECT - Validation in command method
def open_position(self, quantity: Decimal, price: Decimal):
    # Validate BEFORE creating event
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    # Create and apply event
    event = PositionOpenedEvent(...)
    self.apply(event)
```

---

## Testing Strategies

### Unit Testing Aggregates

```python
import pytest
from decimal import Decimal
from uuid import uuid4

def test_position_open():
    """Test opening a new position"""
    # Arrange
    user_id = uuid4()
    account_id = uuid4()
    order_id = uuid4()

    # Act
    position = Position.open(
        user_id=user_id,
        account_id=account_id,
        order_id=order_id,
        symbol="AAPL",
        asset_type=AssetType.STOCK,
        side=PositionSide.LONG,
        quantity=Decimal("100"),
        entry_price=Decimal("150.00")
    )

    # Assert
    assert position.status == PositionStatus.OPEN
    assert position.quantity == Decimal("100")
    assert position.average_entry_price == Decimal("150.00")
    assert len(position.get_uncommitted_events()) == 1
    assert isinstance(position.get_uncommitted_events()[0], PositionOpenedEvent)


def test_pyramid_validation_failure():
    """Test pyramid entry rejected when max entries reached"""
    # Arrange
    position = Position.open(...)

    # Fill max entries
    for i in range(5):
        position.add_to_position(
            order_id=uuid4(),
            quantity=Decimal("50"),
            price=Decimal(f"{150 + i * 5}.00"),
            force_pyramid=True  # Skip validation to fill slots
        )

    # Act & Assert
    with pytest.raises(MaxPyramidEntriesReachedError):
        position.add_to_position(
            order_id=uuid4(),
            quantity=Decimal("25"),
            price=Decimal("175.00")
        )


def test_event_replay():
    """Test rebuilding aggregate from event history"""
    # Arrange
    events = [
        PositionOpenedEvent(...),
        PositionIncreasedEvent(...),
        PositionPnLUpdatedEvent(...)
    ]

    # Act
    position = Position(uuid4())
    for event in events:
        position._apply(event)  # Use _apply for replay

    # Assert
    assert position.version == 0  # Version not incremented during replay
    assert position.quantity == Decimal("150")  # State from events
    assert len(position.get_uncommitted_events()) == 0  # No uncommitted events
```

### Integration Testing

```python
async def test_position_command_flow():
    """Test complete command → aggregate → event flow"""
    # Arrange
    command = OpenPositionCommand(
        user_id=uuid4(),
        account_id=uuid4(),
        symbol="AAPL",
        side=PositionSide.LONG,
        quantity=Decimal("100"),
        entry_price=Decimal("150.00")
    )

    # Act
    result = await command_bus.dispatch(command)

    # Assert
    assert result.success
    position_id = result.aggregate_id

    # Verify aggregate state
    position = await aggregate_repository.load(position_id)
    assert position.status == PositionStatus.OPEN

    # Verify event published
    events = await event_store.load_stream(f"position-{position_id}")
    assert len(events) == 1
    assert events[0].event_type == "PositionOpenedEvent"
```

---

## Performance Considerations

### Snapshot Strategy

For aggregates with many events (>100), use snapshots:

```python
def create_snapshot(self) -> Dict[str, Any]:
    """Create a snapshot of current state for event store optimization"""
    return {
        "user_id": str(self.state.user_id) if self.state.user_id else None,
        "broker_id": self.state.broker_id,
        "status": self.state.status.value if self.state.status else None,
        # ... all state fields
        "version": self.version
    }

def restore_from_snapshot(self, snapshot_data: Dict[str, Any]) -> None:
    """Restore aggregate state from a snapshot"""
    self.state.user_id = uuid.UUID(snapshot_data["user_id"]) if snapshot_data.get("user_id") else None
    self.state.broker_id = snapshot_data.get("broker_id")
    self.state.status = BrokerConnectionStatusEnum(snapshot_data["status"])
    # ... restore all state fields
```

### Event Store Strategy

TradeCore uses **10-year retention** with **snapshots every 50 events**:

- Events: 10 years (immutable audit trail)
- Snapshots: Latest + last 10 (performance optimization)
- Replay: From latest snapshot + subsequent events

### Memory Management

For large aggregates (Position with 100+ entries):

```python
@dataclass
class Position:
    """Position aggregate with memory-efficient collections"""

    # Use efficient data structures
    entries: List[PositionEntry] = field(default_factory=list)  # O(1) append

    # Cache expensive calculations
    _cached_pnl: Optional[Decimal] = None
    _cache_price: Optional[Decimal] = None

    @property
    def unrealized_pnl(self) -> Decimal:
        """Cached P&L calculation"""
        if self._cached_pnl is None or self._cache_price != self.current_price:
            self._cached_pnl = self._calculate_unrealized_pnl()
            self._cache_price = self.current_price
        return self._cached_pnl
```

---

## Summary

### Aggregate Design Checklist

✅ **Structure:**
- [ ] Uses @dataclass for aggregate root
- [ ] Includes `id`, `version`, `uncommitted_events` fields
- [ ] Uses `datetime.now(UTC)` for timestamps
- [ ] Uses snake_case for all method names

✅ **Event Sourcing:**
- [ ] All state changes via events
- [ ] Public `apply()` for new events
- [ ] Private `_apply()` for replay
- [ ] Dynamic event routing (no if/elif chains)

✅ **Business Logic:**
- [ ] Domain rules in aggregate (not sagas/services)
- [ ] Calculation methods are private (`_calculate_*`)
- [ ] Validation before creating events
- [ ] Immutable value objects for complex data

✅ **Testing:**
- [ ] Unit tests for each command method
- [ ] Unit tests for event replay
- [ ] Integration tests for command flow
- [ ] Performance tests for large event histories

---

**See Also:**
- [Event Design Patterns](/Users/silvermpx/PycharmProjects/TradeCore/docs/reference/EVENT_DESIGN_PATTERNS.md)
- [Value Objects Guide](/Users/silvermpx/PycharmProjects/TradeCore/docs/reference/VALUE_OBJECTS_GUIDE.md)
- [Domain Creation Template](/Users/silvermpx/PycharmProjects/TradeCore/docs/mvp/DOMAIN_CREATION_TEMPLATE.md)
