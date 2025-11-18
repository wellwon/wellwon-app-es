# Event Design Patterns Reference Guide

**TradeCore v0.5** | Event Sourcing Best Practices

---

## Table of Contents

1. [Introduction](#introduction)
2. [Event Fundamentals](#event-fundamentals)
3. [Event Schema Design](#event-schema-design)
4. [Event Enrichment Patterns](#event-enrichment-patterns)
5. [Event Versioning](#event-versioning)
6. [Serialization Patterns](#serialization-patterns)
7. [Production Examples](#production-examples)
8. [Common Mistakes](#common-mistakes)
9. [Testing Events](#testing-events)
10. [Performance Optimization](#performance-optimization)

---

## Introduction

Events are **immutable records of state changes** in TradeCore's event-sourced architecture. They serve as:

- **Audit trail**: Complete history of what happened
- **State restoration**: Rebuild aggregates from events
- **Inter-service communication**: Saga triggers and projector updates
- **Analytics source**: Business intelligence and reporting

### Key Principles

1. **Events are Pydantic models** (NOT dataclasses)
2. **Events are immutable** (once created, never modified)
3. **Events are self-contained** (include all necessary data)
4. **Events use past tense** (describe what happened)
5. **Events must have `event_type` field** with Literal type hint

---

## Event Fundamentals

### BaseEvent Structure

All TradeCore events inherit from `BaseEvent`:

```python
from app.common.base.base_model import BaseEvent
from pydantic import Field
from typing import Literal, Dict, Any
from datetime import datetime, UTC
from uuid import UUID

class MyDomainEvent(BaseEvent):
    """
    [Past tense description of what happened]

    Triggers:
    - [What this event causes to happen]
    - [Saga activation conditions]
    - [Projector updates]
    """
    # ⚠️ CRITICAL: event_type field is REQUIRED
    event_type: Literal["MyDomainEvent"] = "MyDomainEvent"

    # Domain identifiers
    aggregate_id: UUID
    user_id: UUID

    # Domain-specific fields
    field1: str
    field2: Decimal

    # Timestamps (use UTC!)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Metadata (for correlation, tracing, etc.)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### Critical Requirements

#### ✅ 1. Events are Pydantic Models (NOT @dataclass)

```python
# ❌ WRONG - Events are NOT dataclasses
from dataclasses import dataclass

@dataclass
class PositionOpenedEvent:
    position_id: UUID
    quantity: Decimal

# ✅ CORRECT - Events are Pydantic models
from app.common.base.base_model import BaseEvent

class PositionOpenedEvent(BaseEvent):
    event_type: Literal["PositionOpenedEvent"] = "PositionOpenedEvent"
    position_id: UUID
    quantity: Decimal
```

**Why Pydantic?**
- Built-in validation
- JSON serialization
- Type coercion
- Schema generation

#### ✅ 2. event_type Field is REQUIRED

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

**Why event_type?**
- Event routing in event bus
- Saga trigger matching
- Projector dispatch
- Event store indexing

#### ✅ 3. Use datetime.now(UTC) for Timestamps

```python
# ❌ WRONG - datetime.utcnow() is DEPRECATED
from datetime import datetime
occurred_at: datetime = Field(default_factory=datetime.utcnow)

# ✅ CORRECT - Use datetime.now(UTC)
from datetime import datetime, UTC
occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**Why UTC?**
- Aware datetime (includes timezone)
- Pydantic validation compatible
- No ambiguity across timezones

---

## Event Schema Design

### Naming Conventions

#### Event Names: Past Tense

```python
# ✅ CORRECT - Past tense event names
class PositionOpenedEvent(BaseEvent): pass
class OrderFilledEvent(BaseEvent): pass
class AutomationActivatedEvent(BaseEvent): pass

# ❌ WRONG - Present/imperative tense
class OpenPositionEvent(BaseEvent): pass
class FillOrderEvent(BaseEvent): pass
class ActivateAutomationEvent(BaseEvent): pass
```

#### Event Class Names: Match event_type

```python
# ✅ CORRECT - Class name matches event_type
class PositionOpenedEvent(BaseEvent):
    event_type: Literal["PositionOpenedEvent"] = "PositionOpenedEvent"

# ❌ WRONG - Mismatch
class PositionOpenedEvent(BaseEvent):
    event_type: Literal["PositionCreated"] = "PositionCreated"  # Inconsistent!
```

### Field Organization

Organize event fields in logical groups:

```python
class PositionOpenedEvent(BaseEvent):
    """Position has been opened"""
    event_type: Literal["PositionOpenedEvent"] = "PositionOpenedEvent"

    # ========================================================================
    # IDENTIFIERS (always first)
    # ========================================================================
    position_id: UUID
    user_id: UUID
    account_id: UUID
    strategy_id: Optional[UUID] = None
    automation_id: Optional[UUID] = None

    # ========================================================================
    # ASSET DETAILS
    # ========================================================================
    symbol: str
    asset_type: AssetType
    side: PositionSide

    # ========================================================================
    # POSITION SIZING
    # ========================================================================
    quantity: Decimal
    entry_price: Decimal
    entry_value: Decimal
    commission: Decimal

    # ========================================================================
    # RISK MANAGEMENT
    # ========================================================================
    stop_loss_price: Optional[Decimal] = None
    stop_loss_type: Optional[StopLossType] = None
    take_profit_price: Optional[Decimal] = None
    risk_amount: Decimal

    # ========================================================================
    # PYRAMIDING CONFIG
    # ========================================================================
    pyramiding_enabled: bool
    max_pyramiding_allowed: int
    pyramiding_size_factor: Decimal

    # ========================================================================
    # METADATA
    # ========================================================================
    entry_reason: str
    market_condition: Optional[str] = None
    account_equity_at_entry: Decimal

    # ========================================================================
    # TIMESTAMPS
    # ========================================================================
    opened_at: datetime
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### Optional vs Required Fields

**Use Optional[] for truly optional data:**

```python
class WebhookSignalReceivedEvent(BaseEvent):
    """Webhook signal received from external source"""
    event_type: Literal["WebhookSignalReceivedEvent"] = "WebhookSignalReceivedEvent"

    # ✅ Required fields (no default)
    signal_id: UUID
    automation_id: UUID
    user_id: UUID
    action: SignalAction
    symbol: str

    # ✅ Optional fields (may not be present)
    quantity: Optional[Decimal] = None  # May be calculated by automation
    order_type: Optional[str] = None    # May use automation default
    price: Optional[Decimal] = None     # May be market order
    stop_loss: Optional[Decimal] = None # May not have stop loss
```

---

## Event Enrichment Patterns

### TRUE SAGA Pattern: Eliminate Queries in Sagas

**Problem:** Sagas should NOT query read models.

**Solution:** Enrich events with ALL data saga needs.

#### ❌ ANTI-PATTERN: Query in Saga

```python
class BrokerDisconnectSaga:
    """BAD: Saga queries read model"""

    async def handle_broker_disconnected(self, event: BrokerDisconnected):
        # ❌ ANTI-PATTERN: Saga querying read model
        accounts = await self.query_bus.query(
            GetLinkedAccountsQuery(broker_connection_id=event.broker_connection_id)
        )

        automations = await self.query_bus.query(
            GetAutomationsByConnectionQuery(broker_connection_id=event.broker_connection_id)
        )

        # Now use the data...
```

#### ✅ TRUE SAGA: Enriched Event

```python
class BrokerDisconnected(BaseEvent):
    """
    Broker connection disconnected.

    TRUE SAGA PATTERN: Event contains ALL data saga needs (NO queries required).
    """
    event_type: Literal["BrokerDisconnected"] = "BrokerDisconnected"

    broker_connection_id: UUID
    user_id: UUID
    broker_id: str
    environment: str

    # TRUE SAGA: All related entity IDs (saga doesn't need to query!)
    linked_account_ids: List[UUID] = Field(default_factory=list)
    virtual_account_ids: List[UUID] = Field(default_factory=list)
    active_automation_ids: List[UUID] = Field(default_factory=list)
```

**Command Handler enriches event:**

```python
@command_handler(DisconnectBrokerCommand)
async def handle_disconnect(cmd: DisconnectBrokerCommand, deps: HandlerDependencies):
    """Command handler queries and enriches event"""

    # Query related entities
    linked_accounts = await deps.query_bus.query(
        GetLinkedAccountsQuery(broker_connection_id=cmd.broker_connection_id)
    )
    active_automations = await deps.query_bus.query(
        GetAutomationsByConnectionQuery(broker_connection_id=cmd.broker_connection_id)
    )

    # Enrich event with queried data
    aggregate.request_disconnect(
        user_id=cmd.user_id,
        reason=cmd.reason,
        # TRUE SAGA: Pass enriched data to aggregate
        linked_account_ids=[acc.id for acc in linked_accounts],
        active_automation_ids=[auto.id for auto in active_automations]
    )
```

### Event Enrichment for Position Sizing

```python
class WebhookSignalReceivedEvent(BaseEvent):
    """
    Webhook signal received.

    TRUE SAGA REFACTORING (Nov 2025):
    - Enriched with account equity/buying_power to eliminate saga queries
    - AutomationExecutionSaga no longer queries GetAccountByIdQuery
    """
    event_type: Literal["WebhookSignalReceivedEvent"] = "WebhookSignalReceivedEvent"

    signal_id: UUID
    automation_id: UUID
    user_id: UUID
    action: SignalAction
    symbol: str

    # Account IDs for routing
    account_ids: List[UUID] = Field(default_factory=list)

    # TRUE SAGA: Account data (eliminate GetAccountByIdQuery in saga)
    account_equity: Optional[Decimal] = None      # For position sizing
    account_buying_power: Optional[Decimal] = None  # For risk checks
```

---

## Event Versioning

### Event Schema Evolution

Events are **immutable**, but schemas evolve. TradeCore uses **additive versioning**:

#### Version 1: Initial Schema

```python
class OrderPlacedEvent(BaseEvent):
    """Order placed (v1)"""
    event_type: Literal["OrderPlacedEvent"] = "OrderPlacedEvent"

    order_id: UUID
    user_id: UUID
    symbol: str
    quantity: Decimal
    side: OrderSide
```

#### Version 2: Add Optional Field

```python
class OrderPlacedEvent(BaseEvent):
    """Order placed (v2)"""
    event_type: Literal["OrderPlacedEvent"] = "OrderPlacedEvent"

    order_id: UUID
    user_id: UUID
    symbol: str
    quantity: Decimal
    side: OrderSide

    # ✅ NEW FIELD: Optional (backward compatible)
    time_in_force: Optional[TimeInForce] = None
```

#### Version 3: Add More Optional Fields

```python
class OrderPlacedEvent(BaseEvent):
    """Order placed (v3)"""
    event_type: Literal["OrderPlacedEvent"] = "OrderPlacedEvent"

    order_id: UUID
    user_id: UUID
    symbol: str
    quantity: Decimal
    side: OrderSide

    # v2 field
    time_in_force: Optional[TimeInForce] = None

    # ✅ NEW FIELDS: Optional (backward compatible)
    extended_hours: Optional[bool] = None
    client_order_id: Optional[str] = None
```

### Breaking Changes

If you MUST make a breaking change, create a new event:

```python
# Old event (keep for historical events)
class OrderPlacedEvent(BaseEvent):
    """Order placed (deprecated)"""
    event_type: Literal["OrderPlacedEvent"] = "OrderPlacedEvent"
    # ... old schema

# New event (use for new orders)
class OrderPlacedEventV2(BaseEvent):
    """Order placed (v2)"""
    event_type: Literal["OrderPlacedEventV2"] = "OrderPlacedEventV2"
    # ... new schema
```

---

## Serialization Patterns

### Value Object Flattening

**Problem:** Value objects don't serialize to JSON cleanly.

**Solution:** Flatten in events, reconstruct in aggregates.

#### Value Object Definition

```python
@dataclass(frozen=True)
class OptionDetails:
    """Option contract details - immutable value object"""
    underlying_symbol: str
    strike_price: Decimal
    expiration_date: datetime
    option_type: OptionType
    option_action: Optional[OptionAction] = None
    contract_size: int = 100
    multiplier: Decimal = Decimal("1")
```

#### Flattened in Event

```python
class AutomationCreatedEvent(BaseEvent):
    """
    Automation created with derivatives support.

    ⚠️ IMPORTANT: Derivative fields are FLATTENED for serialization
    """
    event_type: Literal["AutomationCreatedEvent"] = "AutomationCreatedEvent"

    automation_id: UUID
    user_id: UUID
    symbol: str

    # Asset type
    asset_type: AssetType = AssetType.STOCK

    # Option fields (7 flattened fields)
    option_underlying_symbol: Optional[str] = None
    option_strike_price: Optional[Decimal] = None
    option_expiration_date: Optional[datetime] = None
    option_type: Optional[OptionType] = None
    option_action: Optional[OptionAction] = None
    option_contract_size: Optional[int] = None
    option_multiplier: Optional[Decimal] = None
```

#### Reconstructed in Aggregate

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
```

### Enum Serialization

Pydantic handles enums automatically:

```python
from enum import Enum

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderPlacedEvent(BaseEvent):
    event_type: Literal["OrderPlacedEvent"] = "OrderPlacedEvent"

    # ✅ Pydantic serializes enums to string values
    side: OrderSide  # Serializes to "buy" or "sell"
```

### UUID Serialization

Pydantic handles UUIDs automatically:

```python
from uuid import UUID

class OrderPlacedEvent(BaseEvent):
    event_type: Literal["OrderPlacedEvent"] = "OrderPlacedEvent"

    # ✅ Pydantic serializes UUIDs to strings
    order_id: UUID  # Serializes to "123e4567-e89b-12d3-a456-426614174000"
    user_id: UUID
```

### Decimal Serialization

Pydantic handles Decimals automatically:

```python
from decimal import Decimal

class OrderPlacedEvent(BaseEvent):
    event_type: Literal["OrderPlacedEvent"] = "OrderPlacedEvent"

    # ✅ Pydantic serializes Decimals to strings (preserves precision)
    quantity: Decimal  # Serializes to "100.50"
    price: Decimal     # Serializes to "150.25"
```

---

## Production Examples

### Example 1: BrokerConnectionEvent with Validators

**Location:** `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_connection/events.py`

```python
class BrokerConnectionEvent(BaseEvent):
    """Base class for all broker connection events with proper serialization support"""

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v) if v else None,
            Enum: lambda v: v.value if v else None,
        }
    )

    @model_validator(mode='before')
    def convert_uuids_and_datetimes(cls, values):
        """Convert string UUIDs and datetime strings to proper types"""
        # Convert string UUIDs to UUID objects
        for field_name in ['broker_connection_id', 'user_id', 'event_id']:
            if field_name in values and isinstance(values[field_name], str):
                try:
                    values[field_name] = uuid.UUID(values[field_name])
                except (ValueError, TypeError):
                    pass

        # Convert datetime strings to datetime objects
        for field_name in ['timestamp', 'checked_at', 'expires_at']:
            if field_name in values and isinstance(values[field_name], str):
                try:
                    values[field_name] = datetime.fromisoformat(values[field_name].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass

        return values
```

### Example 2: Event with Field Validators

```python
class BrokerConnectionHealthUpdated(BaseEvent):
    """Broker connection health updated"""
    event_type: Literal["BrokerConnectionHealthUpdated"] = "BrokerConnectionHealthUpdated"

    broker_connection_id: UUID
    user_id: UUID
    broker_id: str
    environment: str
    new_status: Union[BrokerConnectionStatusEnum, str]
    reason: Optional[str] = None

    @field_validator('new_status', mode='before')
    def validate_status(cls, v):
        """Convert string to enum if needed"""
        if isinstance(v, str):
            try:
                return BrokerConnectionStatusEnum(v)
            except ValueError:
                # If it's not a valid enum value, keep it as string
                return v
        return v
```

### Example 3: Event with Enrichment

```python
class WebhookSignalReceivedEvent(BaseEvent):
    """
    Webhook signal received from external source.

    TRUE SAGA REFACTORING (Nov 2025):
    - Enriched with account equity/buying_power to eliminate saga queries
    """
    event_type: Literal["WebhookSignalReceivedEvent"] = "WebhookSignalReceivedEvent"

    # Signal identifiers
    signal_id: UUID
    automation_id: UUID
    user_id: UUID

    # Signal action
    action: SignalAction  # buy, sell, exit, cancel, add

    # Position sentiment after execution (TradersPost compatible)
    sentiment: Optional[SignalSentiment] = None  # bullish/long, bearish/short, flat

    # Signal symbol
    symbol: str

    # Broker accounts (for saga orchestration)
    account_ids: List[UUID] = Field(default_factory=list)

    # TRUE SAGA: Account data (eliminate GetAccountByIdQuery in saga)
    account_equity: Optional[Decimal] = None      # For position sizing
    account_buying_power: Optional[Decimal] = None  # For risk checks

    # Asset details (17 flattened derivative fields)
    asset_type: AssetType = AssetType.STOCK
    option_underlying_symbol: Optional[str] = None
    # ... all derivative fields

    # Signal quantities and prices
    quantity: Optional[Decimal] = None
    price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None

    # Raw signal JSON (for debugging)
    raw_signal_json: Dict[str, Any]

    # Source tracking
    source_ip: str

    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

---

## Common Mistakes

### ❌ Mistake 1: Using @dataclass for Events

```python
# ❌ WRONG - Events are NOT dataclasses
from dataclasses import dataclass

@dataclass
class PositionOpenedEvent:
    position_id: UUID

# ✅ CORRECT - Events are Pydantic models
from app.common.base.base_model import BaseEvent

class PositionOpenedEvent(BaseEvent):
    event_type: Literal["PositionOpenedEvent"] = "PositionOpenedEvent"
    position_id: UUID
```

### ❌ Mistake 2: Missing event_type Field

```python
# ❌ WRONG - Missing event_type field
class PositionOpenedEvent(BaseEvent):
    position_id: UUID

# ✅ CORRECT - Always include event_type
class PositionOpenedEvent(BaseEvent):
    event_type: Literal["PositionOpenedEvent"] = "PositionOpenedEvent"
    position_id: UUID
```

### ❌ Mistake 3: Mutable Collections

```python
# ❌ WRONG - Mutable default for list field
class AutomationCreatedEvent(BaseEvent):
    account_ids: List[UUID] = []  # BAD! Shared across instances

# ✅ CORRECT - Use Field(default_factory=list)
from pydantic import Field

class AutomationCreatedEvent(BaseEvent):
    account_ids: List[UUID] = Field(default_factory=list)
```

### ❌ Mistake 4: Modifying Events

```python
# ❌ WRONG - Events are immutable!
event = PositionOpenedEvent(...)
event.quantity = Decimal("200")  # NO! Don't modify events

# ✅ CORRECT - Create a new event
new_event = PositionOpenedEvent(
    position_id=event.position_id,
    quantity=Decimal("200"),  # New value
    # ... other fields
)
```

### ❌ Mistake 5: Using datetime.utcnow()

```python
# ❌ WRONG - datetime.utcnow() is deprecated
occurred_at: datetime = Field(default_factory=datetime.utcnow)

# ✅ CORRECT - Use datetime.now(UTC)
from datetime import datetime, UTC
occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

---

## Testing Events

### Unit Testing Event Creation

```python
import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, UTC

def test_position_opened_event_creation():
    """Test creating a position opened event"""
    # Arrange
    position_id = uuid4()
    user_id = uuid4()

    # Act
    event = PositionOpenedEvent(
        position_id=position_id,
        user_id=user_id,
        account_id=uuid4(),
        symbol="AAPL",
        asset_type=AssetType.STOCK,
        side=PositionSide.LONG,
        quantity=Decimal("100"),
        entry_price=Decimal("150.00"),
        entry_value=Decimal("15000.00"),
        commission=Decimal("1.00"),
        pyramiding_enabled=True,
        max_pyramiding_allowed=5,
        pyramiding_size_factor=Decimal("0.5"),
        opened_at=datetime.now(UTC)
    )

    # Assert
    assert event.event_type == "PositionOpenedEvent"
    assert event.position_id == position_id
    assert event.user_id == user_id
    assert event.quantity == Decimal("100")
    assert event.entry_price == Decimal("150.00")
    assert isinstance(event.occurred_at, datetime)


def test_event_serialization():
    """Test event serialization to JSON"""
    # Arrange
    event = PositionOpenedEvent(...)

    # Act
    json_data = event.model_dump(mode='json')

    # Assert
    assert isinstance(json_data['position_id'], str)  # UUID → string
    assert isinstance(json_data['quantity'], str)     # Decimal → string
    assert json_data['event_type'] == 'PositionOpenedEvent'


def test_event_deserialization():
    """Test event deserialization from JSON"""
    # Arrange
    json_data = {
        'event_type': 'PositionOpenedEvent',
        'position_id': str(uuid4()),
        'quantity': '100.00',
        # ... other fields
    }

    # Act
    event = PositionOpenedEvent(**json_data)

    # Assert
    assert isinstance(event.position_id, UUID)
    assert isinstance(event.quantity, Decimal)
    assert event.quantity == Decimal("100.00")
```

### Testing Event Enrichment

```python
async def test_event_enrichment():
    """Test command handler enriches event"""
    # Arrange
    cmd = DisconnectBrokerCommand(
        broker_connection_id=uuid4(),
        user_id=uuid4(),
        reason="User requested"
    )

    # Mock queries
    linked_accounts = [
        BrokerAccount(id=uuid4()),
        BrokerAccount(id=uuid4())
    ]

    query_bus_mock.query.side_effect = [linked_accounts, []]

    # Act
    await command_handler.handle(cmd, deps)

    # Assert
    event = aggregate.get_uncommitted_events()[0]
    assert isinstance(event, BrokerDisconnected)
    assert len(event.linked_account_ids) == 2
    assert event.linked_account_ids == [acc.id for acc in linked_accounts]
```

---

## Performance Optimization

### Event Size Optimization

**Keep events small for faster serialization:**

```python
# ❌ AVOID: Embedding large objects
class OrderPlacedEvent(BaseEvent):
    order_id: UUID
    full_order_book: List[Dict[str, Any]]  # Hundreds of KB!

# ✅ BETTER: Reference only
class OrderPlacedEvent(BaseEvent):
    order_id: UUID
    order_book_snapshot_id: UUID  # Reference to separate storage
```

### Batch Event Publishing

For sagas that emit many events:

```python
# ✅ Collect events and publish in batch
events = []
for i in range(100):
    event = OrderStatusUpdatedEvent(...)
    events.append(event)

# Publish batch
await event_bus.publish_batch(events)
```

### Event Compression

For large events, consider compression:

```python
import zlib
import json

def compress_event(event: BaseEvent) -> bytes:
    """Compress event for storage"""
    json_data = event.model_dump_json()
    return zlib.compress(json_data.encode('utf-8'))

def decompress_event(compressed: bytes, event_class: type) -> BaseEvent:
    """Decompress event from storage"""
    json_data = zlib.decompress(compressed).decode('utf-8')
    return event_class.model_validate_json(json_data)
```

---

## Summary

### Event Design Checklist

✅ **Structure:**
- [ ] Inherits from BaseEvent
- [ ] Has event_type field with Literal type hint
- [ ] Uses Pydantic (NOT @dataclass)
- [ ] Past tense naming
- [ ] Uses datetime.now(UTC) for timestamps

✅ **Fields:**
- [ ] Required fields have no default
- [ ] Optional fields use Optional[] and default
- [ ] Collections use Field(default_factory=list/dict)
- [ ] UUIDs, Decimals, Enums handled by Pydantic

✅ **Enrichment:**
- [ ] Includes all data saga needs
- [ ] No need for saga to query read models
- [ ] Enriched by command handler

✅ **Versioning:**
- [ ] New fields are Optional (backward compatible)
- [ ] Breaking changes = new event class
- [ ] Event store supports schema evolution

✅ **Testing:**
- [ ] Unit tests for event creation
- [ ] Serialization/deserialization tests
- [ ] Enrichment tests

---

**See Also:**
- [Aggregate Patterns](/Users/silvermpx/PycharmProjects/TradeCore/docs/reference/AGGREGATE_PATTERNS.md)
- [Value Objects Guide](/Users/silvermpx/PycharmProjects/TradeCore/docs/reference/VALUE_OBJECTS_GUIDE.md)
- [Domain Creation Template](/Users/silvermpx/PycharmProjects/TradeCore/docs/mvp/DOMAIN_CREATION_TEMPLATE.md)
