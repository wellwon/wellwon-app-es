# Value Objects Guide

**TradeCore v0.5** | Immutable Domain Models Reference

---

## Table of Contents

1. [Introduction](#introduction)
2. [Value Object Fundamentals](#value-object-fundamentals)
3. [Design Patterns](#design-patterns)
4. [Production Examples](#production-examples)
5. [When to Use Value Objects](#when-to-use-value-objects)
6. [Validation Strategies](#validation-strategies)
7. [Common Mistakes](#common-mistakes)
8. [Testing Value Objects](#testing-value-objects)
9. [Performance Considerations](#performance-considerations)

---

## Introduction

Value Objects are **immutable objects defined by their attributes** rather than identity. They represent concepts from your domain that have no conceptual identity but are defined by their properties.

### Key Characteristics

1. **Immutability**: Once created, cannot be changed
2. **Equality by Value**: Two instances with same values are equal
3. **Self-Validating**: Validate invariants in `__post_init__`
4. **Side-Effect Free**: No mutable state or external dependencies

### Why Use Value Objects?

- **Type Safety**: Prevent primitive obsession
- **Encapsulation**: Business rules in one place
- **Immutability**: Thread-safe, predictable behavior
- **Domain Language**: Express concepts from ubiquitous language

---

## Value Object Fundamentals

### Basic Structure

TradeCore value objects use **frozen dataclasses**:

```python
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime

@dataclass(frozen=True)
class Money:
    """
    Value object representing a monetary amount.

    Immutable: frozen=True prevents modification after creation.
    """
    amount: Decimal
    currency: str = "USD"

    def __post_init__(self):
        """Validate invariants"""
        if self.amount < 0:
            raise ValueError(f"Amount cannot be negative: {self.amount}")
        if not self.currency or len(self.currency) != 3:
            raise ValueError(f"Invalid currency code: {self.currency}")

    def __str__(self) -> str:
        """Human-readable representation"""
        return f"{self.currency} {self.amount:.2f}"

    def add(self, other: 'Money') -> 'Money':
        """Add two money amounts (returns new instance)"""
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(amount=self.amount + other.amount, currency=self.currency)
```

### Critical Requirements

#### ✅ 1. Always Use frozen=True

```python
# ❌ WRONG - Mutable dataclass
@dataclass
class Money:
    amount: Decimal

money = Money(Decimal("100"))
money.amount = Decimal("200")  # Mutation allowed!

# ✅ CORRECT - Immutable (frozen)
@dataclass(frozen=True)
class Money:
    amount: Decimal

money = Money(Decimal("100"))
money.amount = Decimal("200")  # FrozenInstanceError!
```

#### ✅ 2. Validate in __post_init__

```python
@dataclass(frozen=True)
class Quantity:
    """Value object for trade quantity"""
    value: Decimal

    def __post_init__(self):
        """Validate quantity invariants"""
        if self.value <= 0:
            raise ValueError(f"Quantity must be positive, got {self.value}")

        if self.value > Decimal("1000000"):
            raise ValueError(f"Quantity exceeds maximum: {self.value}")
```

#### ✅ 3. Equality by Value (Automatic)

```python
@dataclass(frozen=True)
class StrikePrice:
    value: Decimal

# Automatic value equality
price1 = StrikePrice(Decimal("150.00"))
price2 = StrikePrice(Decimal("150.00"))
assert price1 == price2  # True (value equality)
assert price1 is not price2  # Different instances
```

---

## Design Patterns

### Pattern 1: Configuration Value Objects

Encapsulate complex configuration as value objects:

```python
@dataclass(frozen=True)
class PyramidingConfig:
    """
    Pyramiding (Position Scaling) Configuration

    Controls how automations can add to existing positions.
    """
    # Core Settings
    enabled: bool = False
    max_entries: int = 5

    # Size Reduction (50% rule default)
    size_factor: Decimal = Decimal("0.5")  # Each entry is 50% of previous

    # Profit Requirements
    min_profit_to_pyramid: Decimal = Decimal("0.02")  # 2% minimum profit

    # Spacing Requirements
    min_spacing_percentage: Decimal = Decimal("0.03")  # 3% minimum spacing

    # Risk Management
    move_stop_on_pyramid: bool = True  # Move stop loss when pyramiding
    breakeven_after_entry: int = 2  # Move to breakeven after 2nd entry

    def __post_init__(self):
        """Validate pyramiding configuration"""
        if self.enabled:
            # Validate max entries
            if self.max_entries < 1 or self.max_entries > 10:
                raise ValueError("max_entries must be between 1 and 10")

            # Validate size factor (must be between 0.1 and 1.0)
            if self.size_factor <= Decimal("0") or self.size_factor > Decimal("1"):
                raise ValueError("size_factor must be between 0 and 1")

            # Validate profit requirement
            if self.min_profit_to_pyramid < Decimal("0"):
                raise ValueError("min_profit_to_pyramid must be non-negative")

    @property
    def is_enabled(self) -> bool:
        """Check if pyramiding is enabled"""
        return self.enabled

    def calculate_next_size(self, current_size: Decimal) -> Decimal:
        """Calculate next pyramid entry size based on size_factor"""
        return current_size * self.size_factor
```

### Pattern 2: Derivatives Value Objects

Represent financial instruments:

```python
@dataclass(frozen=True)
class OptionDetails:
    """
    Option contract details - immutable value object

    Used for OPTION and FUTURE_OPTION asset types.
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
        strike_int = int(self.strike_price * 1000)  # Convert to cents
        return f"{self.underlying_symbol}{exp_str}{option_char}{strike_int:08d}"

    @property
    def notional_value(self) -> Decimal:
        """Calculate notional value of contract"""
        return self.strike_price * Decimal(self.contract_size) * self.multiplier


@dataclass(frozen=True)
class FutureDetails:
    """
    Futures contract details - immutable value object

    Used for FUTURE and FUTURE_OPTION asset types.
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

    @property
    def point_value(self) -> Decimal:
        """Calculate dollar value of one point move"""
        return (Decimal("1") / self.tick_size) * self.tick_value
```

### Pattern 3: Position Tracking Value Objects

Track entries and exits immutably:

```python
@dataclass(frozen=True)
class PositionEntry:
    """
    Individual pyramid entry - immutable record.

    This is the FOUNDATION of pyramiding tracking.
    """
    # Identity
    entry_id: UUID
    order_id: UUID
    sequence: int  # 1, 2, 3... (pyramid level)

    # Entry Details
    quantity: Decimal
    price: Decimal
    value: Decimal  # quantity * price
    commission: Decimal

    # Timing
    timestamp: datetime
    market_condition: Optional[str] = None

    # Risk at Entry
    stop_loss_at_entry: Optional[Decimal] = None
    account_equity_at_entry: Decimal = Decimal("0")
    risk_percentage: Decimal = Decimal("0")

    # Metadata
    entry_reason: str = "INITIAL"
    automation_id: Optional[UUID] = None
    signal_id: Optional[UUID] = None

    def __post_init__(self):
        """Validate entry data"""
        if self.sequence < 1:
            raise ValueError("Entry sequence must be >= 1")
        if self.quantity <= 0:
            raise ValueError("Entry quantity must be positive")
        if self.price <= 0:
            raise ValueError("Entry price must be positive")

    @property
    def cost_basis(self) -> Decimal:
        """Calculate cost basis including commission"""
        return self.value + self.commission


@dataclass(frozen=True)
class PositionExit:
    """
    Partial or full position exit - immutable record.
    """
    # Identity
    exit_id: UUID
    order_id: UUID
    sequence: int

    # Exit Details
    quantity: Decimal
    price: Decimal
    value: Decimal
    commission: Decimal

    # P&L Calculation
    cost_basis: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    pnl_percentage: Decimal

    # Timing
    timestamp: datetime
    holding_period: timedelta

    # Metadata
    exit_reason: str = "MANUAL"
    triggered_by: Optional[str] = None

    def __post_init__(self):
        """Validate exit data"""
        if self.sequence < 1:
            raise ValueError("Exit sequence must be >= 1")
        if self.quantity <= 0:
            raise ValueError("Exit quantity must be positive")
        if self.price <= 0:
            raise ValueError("Exit price must be positive")
```

### Pattern 4: Risk Management Value Objects

```python
@dataclass(frozen=True)
class StopLossConfig:
    """
    Stop loss configuration - immutable value object
    """
    stop_loss_type: StopLossType
    price: Optional[Decimal] = None  # For FIXED type

    # Trailing Stop
    trailing_distance: Optional[Decimal] = None  # $ distance from price
    trailing_percentage: Optional[Decimal] = None  # % distance from price

    # Percentage Stop
    percentage: Optional[Decimal] = None  # % from entry price

    # ATR Stop
    atr_multiplier: Optional[Decimal] = None
    atr_period: int = 14

    # Auto-adjustment
    move_with_pyramids: bool = True

    def __post_init__(self):
        """Validate stop loss config based on type"""
        if self.stop_loss_type == StopLossType.FIXED:
            if self.price is None or self.price <= 0:
                raise ValueError("FIXED stop loss requires positive price")

        elif self.stop_loss_type == StopLossType.TRAILING:
            if self.trailing_distance is None and self.trailing_percentage is None:
                raise ValueError("TRAILING stop loss requires distance or percentage")

        elif self.stop_loss_type == StopLossType.PERCENTAGE:
            if self.percentage is None or self.percentage <= 0:
                raise ValueError("PERCENTAGE stop loss requires positive percentage")

        elif self.stop_loss_type == StopLossType.ATR:
            if self.atr_multiplier is None or self.atr_multiplier <= 0:
                raise ValueError("ATR stop loss requires positive multiplier")

    def calculate_stop_price(
        self,
        entry_price: Decimal,
        side: str,
        current_atr: Optional[Decimal] = None
    ) -> Decimal:
        """Calculate stop loss price based on configuration"""
        if self.stop_loss_type == StopLossType.FIXED:
            return self.price

        elif self.stop_loss_type == StopLossType.PERCENTAGE:
            distance = entry_price * (self.percentage / Decimal("100"))
            return entry_price - distance if side == "LONG" else entry_price + distance

        elif self.stop_loss_type == StopLossType.ATR:
            if current_atr is None:
                raise ValueError("ATR stop loss requires current ATR value")
            distance = current_atr * self.atr_multiplier
            return entry_price - distance if side == "LONG" else entry_price + distance

        elif self.stop_loss_type == StopLossType.TRAILING:
            if self.trailing_distance:
                return entry_price - self.trailing_distance if side == "LONG" else entry_price + self.trailing_distance
            elif self.trailing_percentage:
                distance = entry_price * (self.trailing_percentage / Decimal("100"))
                return entry_price - distance if side == "LONG" else entry_price + distance

        return entry_price
```

### Pattern 5: Validation Result Value Objects

```python
@dataclass(frozen=True)
class PyramidValidationResult:
    """
    Result of pyramid validation check - immutable value object.
    """
    is_valid: bool
    failure_reason: Optional[str] = None

    # Detailed validation checks
    has_max_entries: bool = False
    has_sufficient_profit: bool = False
    has_sufficient_spacing: bool = False
    has_sufficient_capital: bool = False
    within_risk_limits: bool = False
    trend_is_valid: bool = False

    # Calculated values
    current_profit_pct: Decimal = Decimal("0")
    spacing_pct: Decimal = Decimal("0")
    calculated_quantity: Decimal = Decimal("0")
    total_risk_pct: Decimal = Decimal("0")

    @property
    def error_summary(self) -> str:
        """Generate human-readable error summary"""
        if self.is_valid:
            return "Validation passed"

        errors = []
        if not self.has_max_entries:
            errors.append("Max pyramid entries reached")
        if not self.has_sufficient_profit:
            errors.append(f"Insufficient profit ({self.current_profit_pct:.2f}%)")
        if not self.has_sufficient_spacing:
            errors.append(f"Insufficient spacing ({self.spacing_pct:.2f}%)")

        return "; ".join(errors)


@dataclass(frozen=True)
class ReconciliationResult:
    """
    Result of broker reconciliation - immutable value object.
    """
    position_id: UUID
    account_id: UUID
    timestamp: datetime
    status: ReconciliationStatus
    is_synced: bool

    # Quantities
    domain_quantity: Decimal
    broker_quantity: Optional[Decimal]
    quantity_difference: Decimal = Decimal("0")

    # Prices
    domain_average_price: Decimal
    broker_average_price: Optional[Decimal]
    price_difference: Decimal = Decimal("0")
    price_difference_pct: Decimal = Decimal("0")

    # Discrepancies
    discrepancies: Dict[str, str] = field(default_factory=dict)
    requires_manual_review: bool = False
    suggested_action: Optional[str] = None
    auto_resolved: bool = False

    @property
    def has_quantity_discrepancy(self) -> bool:
        """Check if quantity discrepancy exists"""
        return abs(self.quantity_difference) >= Decimal("0.01")

    @property
    def has_price_discrepancy(self) -> bool:
        """Check if price discrepancy exists"""
        return abs(self.price_difference_pct) >= Decimal("0.1")

    @property
    def needs_attention(self) -> bool:
        """Check if result needs manual attention"""
        return not self.is_synced and self.requires_manual_review
```

---

## Production Examples

### Example 1: Automation Value Objects

**Location:** `/Users/silvermpx/PycharmProjects/TradeCore/app/automation/value_objects.py`

**All Configuration as Value Objects:**

```python
@dataclass(frozen=True)
class PositionSizingConfig:
    """Position sizing configuration (TradersPost compatible)"""
    type: PositionSizingType
    fixed_quantity: Optional[Decimal] = None
    amount_per_position: Optional[Decimal] = None
    risk_per_position: Optional[Decimal] = None
    percent_of_equity: Optional[Decimal] = None
    use_buying_power: bool = False


@dataclass(frozen=True)
class OrderTypePreference:
    """Order type preferences for entry and exit"""
    entry_order_type: OrderType = OrderType.MARKET
    exit_order_type: OrderType = OrderType.MARKET
    stop_loss_order_type: OrderType = OrderType.STOP
    take_profit_order_type: OrderType = OrderType.LIMIT
    limit_offset_percentage: Optional[Decimal] = None
    limit_offset_amount: Optional[Decimal] = None


@dataclass(frozen=True)
class WebhookConfig:
    """Webhook configuration and security"""
    token: str
    url: str
    allowed_ips: List[str]
    rate_limit: int = 60
    created_at: datetime = datetime.now()
    rotated_at: Optional[datetime] = None
```

### Example 2: Position Value Objects

**Location:** `/Users/silvermpx/PycharmProjects/TradeCore/app/position/value_objects.py`

**Comprehensive Tracking:**

```python
@dataclass(frozen=True)
class PnLSnapshot:
    """
    Point-in-time P&L record - immutable value object.

    Stored for analytics and charting.
    """
    # Required fields (no defaults) - MUST come first
    timestamp: datetime
    market_price: Decimal
    unrealized_pnl: Decimal
    quantity: Decimal
    average_entry_price: Decimal
    pyramiding_count: int

    # Optional fields (with defaults) - MUST come after
    unrealized_pnl_per_entry: Dict[str, Decimal] = field(default_factory=dict)
    realized_pnl: Decimal = Decimal("0")
    total_pnl: Decimal = Decimal("0")
    pnl_percentage: Decimal = Decimal("0")

    def __post_init__(self):
        """Validate snapshot data"""
        if self.quantity < 0:
            raise ValueError("Quantity cannot be negative")
        if self.average_entry_price <= 0:
            raise ValueError("Average entry price must be positive")
        if self.pyramiding_count < 1:
            raise ValueError("Pyramiding count must be >= 1")


@dataclass(frozen=True)
class BrokerPositionData:
    """Position data received from broker - immutable value object."""
    broker: str
    broker_position_id: Optional[str]
    symbol: str
    quantity: Decimal
    average_price: Decimal
    current_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    unrealized_pnl_pct: Optional[Decimal] = None
    cost_basis: Optional[Decimal] = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))
    raw_data: Dict[str, any] = field(default_factory=dict)
```

---

## When to Use Value Objects

### Use Value Objects When:

✅ **Concept has no identity**
- Money, quantity, price, percentage
- Configuration settings
- Measurements, coordinates

✅ **Immutability makes sense**
- Once created, shouldn't change
- Want to prevent side effects

✅ **Equality by value is natural**
- $100 USD == $100 USD (regardless of instance)
- OptionDetails(strike=150) == OptionDetails(strike=150)

✅ **Business rules need encapsulation**
- Validation logic
- Calculation methods
- Domain invariants

### Use Entities When:

❌ **Identity matters**
- User, Order, Position
- Track lifecycle over time

❌ **Mutability is essential**
- State transitions (status changes)
- Collection management (add/remove)

❌ **Unique across instances**
- User(id=1) != User(id=2) even if all other fields identical

---

## Validation Strategies

### Strategy 1: Constructor Validation

```python
@dataclass(frozen=True)
class Percentage:
    """Value object for percentage values"""
    value: Decimal

    def __post_init__(self):
        """Validate percentage is within valid range"""
        if self.value < 0 or self.value > 100:
            raise ValueError(f"Percentage must be 0-100, got {self.value}")

    @classmethod
    def from_decimal(cls, value: Decimal) -> 'Percentage':
        """Create from decimal (0.5 → 50%)"""
        return cls(value * Decimal("100"))

    def to_decimal(self) -> Decimal:
        """Convert to decimal (50% → 0.5)"""
        return self.value / Decimal("100")
```

### Strategy 2: Multi-Field Validation

```python
@dataclass(frozen=True)
class DateRange:
    """Value object for date ranges"""
    start_date: datetime
    end_date: datetime

    def __post_init__(self):
        """Validate date range invariants"""
        if self.end_date < self.start_date:
            raise ValueError(f"End date {self.end_date} is before start date {self.start_date}")

        max_duration = timedelta(days=365)
        if (self.end_date - self.start_date) > max_duration:
            raise ValueError(f"Date range exceeds maximum duration of {max_duration.days} days")

    @property
    def duration(self) -> timedelta:
        """Calculate duration of range"""
        return self.end_date - self.start_date

    def contains(self, date: datetime) -> bool:
        """Check if date is within range"""
        return self.start_date <= date <= self.end_date
```

### Strategy 3: Business Rule Validation

```python
@dataclass(frozen=True)
class OrderPrice:
    """Value object for order pricing with market rules"""
    price: Decimal
    order_type: str
    tick_size: Decimal = Decimal("0.01")

    def __post_init__(self):
        """Validate price follows market rules"""
        # Must be positive
        if self.price <= 0:
            raise ValueError(f"Price must be positive, got {self.price}")

        # Must align with tick size
        remainder = self.price % self.tick_size
        if remainder != 0:
            raise ValueError(
                f"Price {self.price} does not align with tick size {self.tick_size}. "
                f"Remainder: {remainder}"
            )

        # Limit orders have price constraints
        if self.order_type == "LIMIT":
            if self.price > Decimal("1000000"):
                raise ValueError(f"Limit price {self.price} exceeds maximum")

    @classmethod
    def from_market_quote(cls, quote: Decimal, order_type: str, tick_size: Decimal) -> 'OrderPrice':
        """Create from market quote, rounding to tick size"""
        # Round to nearest tick
        rounded = round(quote / tick_size) * tick_size
        return cls(price=rounded, order_type=order_type, tick_size=tick_size)
```

---

## Common Mistakes

### ❌ Mistake 1: Forgetting frozen=True

```python
# ❌ WRONG - Not frozen (mutable)
@dataclass
class Money:
    amount: Decimal

money = Money(Decimal("100"))
money.amount = Decimal("200")  # Mutation allowed!

# ✅ CORRECT - Frozen (immutable)
@dataclass(frozen=True)
class Money:
    amount: Decimal

money = Money(Decimal("100"))
# money.amount = Decimal("200")  # FrozenInstanceError!
```

### ❌ Mistake 2: Mutable Default Arguments

```python
# ❌ WRONG - Mutable default (shared across instances!)
@dataclass(frozen=True)
class Portfolio:
    positions: List[Position] = []  # BAD!

# ✅ CORRECT - Use field(default_factory=...)
from dataclasses import field

@dataclass(frozen=True)
class Portfolio:
    positions: List[Position] = field(default_factory=list)
```

### ❌ Mistake 3: Missing Validation

```python
# ❌ WRONG - No validation
@dataclass(frozen=True)
class Quantity:
    value: Decimal

# Can create invalid instances!
qty = Quantity(Decimal("-100"))  # Negative quantity!

# ✅ CORRECT - Validate in __post_init__
@dataclass(frozen=True)
class Quantity:
    value: Decimal

    def __post_init__(self):
        if self.value <= 0:
            raise ValueError(f"Quantity must be positive, got {self.value}")
```

### ❌ Mistake 4: Mixing Value Objects and Entities

```python
# ❌ WRONG - Value object with identity
@dataclass(frozen=True)
class User:  # Should be entity!
    id: UUID
    name: str
    email: str

# Users with same name/email are NOT the same user!

# ✅ CORRECT - Entity (NOT value object)
@dataclass
class User:  # Mutable entity
    id: UUID
    name: str
    email: str
```

### ❌ Mistake 5: Using object_setattr Workaround

```python
# ❌ WRONG - Breaking immutability with workaround
@dataclass(frozen=True)
class Money:
    amount: Decimal

    def double(self):
        object.__setattr__(self, 'amount', self.amount * 2)  # BAD!

# ✅ CORRECT - Return new instance
@dataclass(frozen=True)
class Money:
    amount: Decimal

    def double(self) -> 'Money':
        return Money(amount=self.amount * 2)  # New instance
```

---

## Testing Value Objects

### Unit Testing Value Objects

```python
import pytest
from decimal import Decimal

def test_money_creation():
    """Test creating valid money instance"""
    money = Money(amount=Decimal("100.50"), currency="USD")
    assert money.amount == Decimal("100.50")
    assert money.currency == "USD"


def test_money_validation():
    """Test money validation"""
    # Negative amount
    with pytest.raises(ValueError, match="Amount cannot be negative"):
        Money(amount=Decimal("-100"), currency="USD")

    # Invalid currency
    with pytest.raises(ValueError, match="Invalid currency code"):
        Money(amount=Decimal("100"), currency="US")  # Only 2 chars


def test_money_immutability():
    """Test money is immutable"""
    money = Money(amount=Decimal("100"), currency="USD")

    with pytest.raises(Exception):  # FrozenInstanceError
        money.amount = Decimal("200")


def test_money_equality():
    """Test money equality by value"""
    money1 = Money(amount=Decimal("100"), currency="USD")
    money2 = Money(amount=Decimal("100"), currency="USD")
    money3 = Money(amount=Decimal("200"), currency="USD")

    assert money1 == money2  # Same values
    assert money1 is not money2  # Different instances
    assert money1 != money3  # Different values


def test_money_operations():
    """Test money arithmetic operations"""
    money1 = Money(amount=Decimal("100"), currency="USD")
    money2 = Money(amount=Decimal("50"), currency="USD")

    result = money1.add(money2)
    assert result.amount == Decimal("150")
    assert result.currency == "USD"

    # Original instances unchanged
    assert money1.amount == Decimal("100")
    assert money2.amount == Decimal("50")


def test_option_details_symbol_representation():
    """Test option symbol generation"""
    option = OptionDetails(
        underlying_symbol="AAPL",
        strike_price=Decimal("150.00"),
        expiration_date=datetime(2025, 1, 17),
        option_type=OptionType.CALL
    )

    assert option.symbol_representation == "AAPL250117C00150000"
```

---

## Performance Considerations

### Memory Optimization

Frozen dataclasses are memory-efficient:

```python
# ✅ Frozen dataclass uses __slots__ automatically (Python 3.10+)
@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

# Smaller memory footprint than regular class
```

### Caching Expensive Calculations

```python
@dataclass(frozen=True)
class ComplexCalculation:
    """Value object with expensive calculation"""
    value1: Decimal
    value2: Decimal
    _cached_result: Optional[Decimal] = field(default=None, init=False, repr=False)

    @property
    def result(self) -> Decimal:
        """Cached expensive calculation"""
        if self._cached_result is None:
            # Expensive calculation
            object.__setattr__(self, '_cached_result', self._calculate())
        return self._cached_result

    def _calculate(self) -> Decimal:
        """Perform expensive calculation"""
        # ... complex logic
        return self.value1 * self.value2
```

### Value Object Pools

For frequently created value objects, consider pooling:

```python
class MoneyPool:
    """Pool of commonly used Money instances"""
    _pool: Dict[Tuple[str, str], Money] = {}

    @classmethod
    def get(cls, amount: Decimal, currency: str) -> Money:
        """Get or create Money instance"""
        key = (str(amount), currency)
        if key not in cls._pool:
            cls._pool[key] = Money(amount=amount, currency=currency)
        return cls._pool[key]


# Usage
money1 = MoneyPool.get(Decimal("100"), "USD")
money2 = MoneyPool.get(Decimal("100"), "USD")
assert money1 is money2  # Same instance!
```

---

## Summary

### Value Object Design Checklist

✅ **Structure:**
- [ ] Uses @dataclass(frozen=True)
- [ ] Validates in __post_init__
- [ ] Uses field(default_factory=...) for collections
- [ ] No mutable state

✅ **Validation:**
- [ ] Validates all invariants at creation
- [ ] Raises clear exceptions for violations
- [ ] Documents validation rules

✅ **Operations:**
- [ ] Methods return new instances (no mutation)
- [ ] Equality by value (automatic with dataclass)
- [ ] Computed properties for derived values

✅ **Testing:**
- [ ] Tests valid creation
- [ ] Tests validation failures
- [ ] Tests immutability
- [ ] Tests equality
- [ ] Tests operations

✅ **Documentation:**
- [ ] Clear docstring explaining concept
- [ ] Documents validation rules
- [ ] Examples of usage

---

**See Also:**
- [Aggregate Patterns](/Users/silvermpx/PycharmProjects/TradeCore/docs/reference/AGGREGATE_PATTERNS.md)
- [Event Design Patterns](/Users/silvermpx/PycharmProjects/TradeCore/docs/reference/EVENT_DESIGN_PATTERNS.md)
- [Domain Creation Template](/Users/silvermpx/PycharmProjects/TradeCore/docs/mvp/DOMAIN_CREATION_TEMPLATE.md)
