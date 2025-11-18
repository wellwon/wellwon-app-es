# Projector Implementation Guide

**TradeCore v0.5 - Event Projection & Read Models**
**Last Updated:** 2025-01-10
**Status:** Production Reference

---

## Table of Contents

1. [Overview](#overview)
2. [Purpose and When to Use](#purpose-and-when-to-use)
3. [Architecture](#architecture)
4. [SYNC vs ASYNC Projections](#sync-vs-async-projections)
5. [Step-by-Step Implementation](#step-by-step-implementation)
6. [Code Examples from TradeCore](#code-examples-from-tradecore)
7. [Testing Strategies](#testing-strategies)
8. [Performance Tips](#performance-tips)
9. [Common Mistakes](#common-mistakes)

---

## Overview

Projectors are the **event-to-read-model transformation layer** in TradeCore's CQRS architecture. They:
- Listen to domain events from the event bus
- Update read models (PostgreSQL tables)
- Maintain denormalized views for queries
- Support both SYNC (critical) and ASYNC (eventual) consistency
- Ensure idempotency (can replay events safely)

### Key Principles

1. **Projectors are event handlers** - React to domain events
2. **Update read models, not aggregates** - Write-side is event store
3. **Idempotent by design** - Safe to replay events
4. **SYNC for critical paths** - OAuth, real-time UI updates
5. **ASYNC for everything else** - Eventual consistency

---

## Purpose and When to Use

### When to Create a Projector

Create a projector when you need to:
- ✅ **Update read models** from domain events
- ✅ **Denormalize data** for query optimization
- ✅ **Maintain derived state** (e.g., balances, statistics)
- ✅ **Cross-domain views** (e.g., order with position data)
- ✅ **Event-driven cleanup** (e.g., delete cascade)

### When NOT to Use Projectors

DON'T create projectors for:
- ❌ **Business logic** - Use aggregates
- ❌ **Event sourcing writes** - Use command handlers
- ❌ **Saga orchestration** - Use saga managers
- ❌ **External API calls** - Use services

---

## Architecture

### Projection Flow

```
Domain Event Emitted
    ↓
Event Store (KurrentDB) - Permanent storage
    ↓
Event Bus (Redpanda) - Transport layer
    ↓
Event Processor Worker - Routes events
    ↓
Projector Method - Domain-specific handler
    ↓
Read Model Update (PostgreSQL) - Optimized for queries
    ↓
Query Handler - Reads updated data
```

### Projector Structure

```python
class BrokerConnectionProjector:
    """
    Projector for BrokerConnection domain events.

    Handles projection of connection lifecycle events to read models.
    """

    def __init__(
        self,
        read_repo: BrokerConnectionReadRepo,
        query_bus: Optional[IQueryBus] = None
    ):
        self.read_repo = read_repo
        self.query_bus = query_bus

    @sync_projection("BrokerConnectionEstablished", priority=1, timeout=2.0)
    @monitor_projection
    async def on_broker_connection_established(self, envelope: EventEnvelope) -> None:
        """
        SYNC projection for connection establishment.

        Priority 1: CRITICAL - OAuth callback polls this!
        Timeout: 2.0s - Must complete quickly
        """
        event_data = envelope.event_data
        broker_connection_id = envelope.aggregate_id

        await self.read_repo.update(
            broker_connection_id=broker_connection_id,
            updates={
                "connected": True,
                "last_connection_status": "CONNECTED",
                "last_connected_at": event_data['established_at']
            }
        )

    async def on_broker_disconnected(self, envelope: EventEnvelope) -> None:
        """
        ASYNC projection for disconnection.

        No @sync_projection decorator - eventual consistency OK.
        """
        event_data = envelope.event_data
        broker_connection_id = envelope.aggregate_id

        await self.read_repo.update(
            broker_connection_id=broker_connection_id,
            updates={
                "connected": False,
                "last_connection_status": "DISCONNECTED",
                "disconnected_at": event_data['disconnected_at']
            }
        )
```

---

## SYNC vs ASYNC Projections

### SYNC Projections

**Use SYNC when:**
- ⚡ **User is waiting** (OAuth callback, real-time UI)
- ⚡ **Critical path** (10s timeout in OAuth polling)
- ⚡ **Race conditions** (must complete before next operation)

**Configuration:** `app/*/sync_events.py`

```python
# app/broker_connection/sync_events.py
SYNC_EVENTS = {
    "BrokerConnectionInitiated",       # OAuth critical path
    "BrokerConnectionEstablished",     # OAuth callback polls this
    "BrokerTokensSuccessfullyStored",  # OAuth completed
    "BrokerConnectionReauthRequired"   # User action required
}

EVENT_CONFIG = {
    "BrokerConnectionEstablished": {
        "priority": 1,  # CRITICAL
        "timeout": 2.0,  # Must complete in 2 seconds
        "description": "OAuth callback queries this (10s timeout)"
    }
}
```

**Decorator:**

```python
@sync_projection("BrokerConnectionEstablished", priority=1, timeout=2.0)
@monitor_projection
async def on_broker_connection_established(self, envelope: EventEnvelope) -> None:
    """SYNC projection - blocks until complete"""
    # Update read model synchronously
    await self.read_repo.update(...)
```

### ASYNC Projections

**Use ASYNC for:**
- 📊 **Statistics and reports** (eventual consistency OK)
- 📝 **Audit logs** (not time-critical)
- 🔔 **Notifications** (best-effort delivery)
- 🧹 **Cleanup operations** (can be delayed)

**No decorator needed:**

```python
async def on_broker_disconnected(self, envelope: EventEnvelope) -> None:
    """ASYNC projection - eventual consistency"""
    # Processed by worker asynchronously
    await self.read_repo.update(...)
```

### Comparison

| Aspect | SYNC Projection | ASYNC Projection |
|--------|----------------|------------------|
| **Latency** | <2 seconds | 1-5 seconds |
| **Guarantee** | Blocks until complete | Eventual consistency |
| **Performance** | Slower (serialized) | Faster (parallel) |
| **Use Case** | OAuth, real-time UI | Reports, cleanup |
| **Decorator** | `@sync_projection` | None (default) |
| **Priority** | 1-3 (1=highest) | N/A |
| **Timeout** | 1.0-5.0 seconds | N/A |

---

## Step-by-Step Implementation

### Step 1: Define Domain Events (events.py)

Events use Pydantic `BaseEvent`:

```python
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field

from app.common.base.base_event import BaseEvent

class AutomationCreatedEvent(BaseEvent):
    """
    Automation created

    CRITICAL: Events use Pydantic BaseEvent (NOT @dataclass)
    Must have event_type field with Literal type.
    """
    event_type: Literal["AutomationCreatedEvent"] = "AutomationCreatedEvent"

    # Event data
    automation_id: UUID
    user_id: UUID
    name: str
    symbol: str
    status: str
    webhook_token: str
    webhook_url: str

    # Derivatives support
    asset_type: str
    option_underlying_symbol: Optional[str] = None
    option_strike_price: Optional[Decimal] = None

    # Timestamp
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**Key Points:**
- Inherit from `BaseEvent` (Pydantic)
- Include `event_type` with `Literal` type
- All fields should be JSON-serializable
- Use `datetime.now(UTC)` for timestamps

---

### Step 2: Create Projector Class (projectors.py)

```python
import logging
from typing import Optional, Dict, Any
from uuid import UUID

from app.infra.read_repos.automation_read_repo import AutomationReadRepo
from app.automation.read_models import AutomationReadModel
from app.infra.event_store.event_envelope import EventEnvelope
from app.infra.event_store.sync_decorators import sync_projection, monitor_projection

log = logging.getLogger("tradecore.automation.projectors")


class AutomationProjector:
    """
    Projector for Automation domain events.

    Projects domain events to read models in PostgreSQL.
    Supports both SYNC and ASYNC projections.
    """

    def __init__(
        self,
        read_repo: AutomationReadRepo,
        query_bus: Optional[IQueryBus] = None
    ):
        self.read_repo = read_repo
        self.query_bus = query_bus

    async def handle_event(self, event_dict: Dict[str, Any]) -> None:
        """
        Generic event handler for event processor compatibility.

        Routes events to appropriate projection methods.
        """
        event_type = event_dict.get("event_type")
        if not event_type:
            log.error(f"Event dict missing event_type: {event_dict}")
            return

        # Create EventEnvelope from dict
        envelope = EventEnvelope.from_partial_data(event_dict)

        # Find and execute projection method
        method_name = f"on_{self._to_snake_case(event_type)}"
        method = getattr(self, method_name, None)

        if method:
            await method(envelope)
        else:
            log.debug(f"No projection handler for {event_type}")

    def _to_snake_case(self, name: str) -> str:
        """Convert PascalCase to snake_case"""
        return ''.join(['_' + c.lower() if c.isupper() else c for c in name]).lstrip('_')
```

---

### Step 3: Implement Projection Methods

**SYNC Projection (Critical):**

```python
@sync_projection("AutomationCreatedEvent", priority=2, timeout=2.0)
@monitor_projection
async def on_automation_created_event(self, envelope: EventEnvelope) -> None:
    """
    Project AutomationCreatedEvent to automations table.

    SYNC Priority 2 - User waiting for automation to appear.
    Timeout: 2.0s
    """
    event_data = envelope.event_data
    automation_id = envelope.aggregate_id

    log.info(f"[SYNC] Projecting AutomationCreatedEvent for {automation_id}")

    await self.read_repo.create(
        automation_id=automation_id,
        user_id=event_data['user_id'],
        name=event_data['name'],
        symbol=event_data['symbol'],
        status='inactive',
        webhook_token=event_data['webhook_token'],
        webhook_url=event_data['webhook_url'],
        asset_type=event_data['asset_type'],
        # ... more fields
        created_at=event_data['occurred_at']
    )

    log.info(f"[SYNC] Automation {automation_id} created in read model")
```

**ASYNC Projection (Eventual Consistency):**

```python
async def on_automation_updated_event(self, envelope: EventEnvelope) -> None:
    """
    Project AutomationUpdatedEvent to automations table.

    ASYNC - eventual consistency OK.
    """
    event_data = envelope.event_data
    automation_id = envelope.aggregate_id

    log.info(f"[ASYNC] Projecting AutomationUpdatedEvent for {automation_id}")

    # Check if automation exists
    automation = await self.read_repo.get_by_id(automation_id)
    if not automation:
        log.warning(f"Automation {automation_id} not found for update")
        return

    # Update fields
    updates = {
        "name": event_data.get('name', automation.name),
        "position_sizing_type": event_data.get('position_sizing_type'),
        "stop_loss_type": event_data.get('stop_loss_type'),
        "take_profit_type": event_data.get('take_profit_type'),
        "updated_at": event_data['occurred_at']
    }

    await self.read_repo.update(automation_id, updates)

    log.info(f"[ASYNC] Automation {automation_id} updated in read model")
```

---

### Step 4: Handle Idempotency

Projections must be **idempotent** (safe to replay):

```python
async def on_automation_created_event(self, envelope: EventEnvelope) -> None:
    """Idempotent projection"""
    event_data = envelope.event_data
    automation_id = envelope.aggregate_id

    # Check if already exists (idempotency)
    existing = await self.read_repo.get_by_id(automation_id)
    if existing:
        log.debug(f"Automation {automation_id} already exists - skipping")
        return

    # Create new record
    await self.read_repo.create(...)
```

**Patterns for idempotency:**

1. **Check before insert:**
```python
if not await self.read_repo.exists(automation_id):
    await self.read_repo.create(...)
```

2. **Upsert (INSERT ON CONFLICT):**
```python
await self.db.execute(
    """
    INSERT INTO automations (id, name, ...)
    VALUES ($1, $2, ...)
    ON CONFLICT (id) DO UPDATE
    SET name = EXCLUDED.name, ...
    """,
    automation_id, name, ...
)
```

3. **Version tracking:**
```python
# Only apply if version is newer
if envelope.aggregate_version > automation.version:
    await self.read_repo.update(...)
```

---

### Step 5: Handle Cross-Domain Projections

Projectors can listen to events from other domains:

```python
from app.broker_account.events import BrokerAccountDeleted

async def on_broker_account_deleted(self, envelope: EventEnvelope) -> None:
    """
    Cross-domain projection: Remove automation when account deleted.

    Listens to BrokerAccount domain events.
    """
    event_data = envelope.event_data
    account_id = envelope.aggregate_id

    log.info(f"Removing automations for deleted account {account_id}")

    # Find automations using this account
    automations = await self.read_repo.find_by_account(account_id)

    for automation in automations:
        # Remove account from automation
        await self.db.execute(
            """
            DELETE FROM automation_broker_accounts
            WHERE automation_id = $1 AND account_id = $2
            """,
            automation.id, account_id
        )

    log.info(f"Cleaned up {len(automations)} automations for account {account_id}")
```

---

### Step 6: Register Projector

**In domain registry** (`app/infra/consumers/domain_registry.py`):

```python
from app.automation.projectors import AutomationProjector

DOMAIN_REGISTRY = {
    "automation": {
        "projector_class": AutomationProjector,
        "read_repo_attr": "automation_read_repo",
        "events": [
            "AutomationCreatedEvent",
            "AutomationUpdatedEvent",
            "AutomationActivatedEvent",
            "AutomationDeactivatedEvent",
            "AutomationSuspendedEvent",
            "AutomationDeletedEvent",
            # ... more events
        ]
    }
}
```

---

## Code Examples from TradeCore

### Example 1: Simple SYNC Projection (Automation)

**File:** `/Users/silvermpx/PycharmProjects/TradeCore/app/automation/projectors.py`

```python
async def project_automation_created(event: AutomationCreatedEvent, pg_client):
    """
    Project AutomationCreatedEvent to automations table

    SYNC Priority 1 - User waiting for automation to appear
    Timeout: 2.0s
    """
    await pg_client.execute(
        """
        INSERT INTO automations (
            id, user_id, name, symbol, status,
            webhook_token, webhook_url, webhook_allowed_ips, webhook_rate_limit,
            webhook_created_at,

            -- Derivatives (17 fields)
            asset_type,
            option_underlying_symbol, option_strike_price, option_expiration_date,
            option_type, option_action, option_contract_size, option_multiplier,
            future_underlying_symbol, future_contract_month, future_expiration_date,
            future_contract_size, future_tick_size, future_tick_value,
            future_multiplier, future_exchange, future_product_code,

            -- Position Sizing
            position_sizing_type, fixed_quantity, amount_per_position,
            risk_per_position, percent_of_equity, use_buying_power,

            -- Side Preference
            side_preference,

            -- Stop Loss
            stop_loss_type, stop_loss_price, stop_loss_dollar_amount,
            stop_loss_percentage, stop_loss_atr_multiplier, stop_loss_atr_period,
            stop_loss_trailing, stop_loss_trail_amount, stop_loss_trail_percentage,

            -- Take Profit
            take_profit_type, take_profit_price, take_profit_dollar_amount,
            take_profit_percentage, take_profit_risk_reward_ratio,

            -- Pyramiding (7 fields)
            pyramiding_enabled, max_pyramid_entries, pyramid_size_factor,
            min_profit_to_pyramid, min_spacing_percentage,
            move_stop_on_pyramid, breakeven_after_pyramid,

            -- Order Preferences
            entry_order_type, exit_order_type,

            -- Auto-submit
            auto_submit,

            -- Timestamps
            created_at, updated_at,

            -- Event Sourcing
            aggregate_version,

            -- Metadata
            metadata
        )
        VALUES (
            $1, $2, $3, $4, 'inactive',
            $5, $6, '{}', 60, $7,

            -- Derivatives
            $8,
            $9, $10, $11, $12, $13, $14, $15,
            $16, $17, $18, $19, $20, $21, $22, $23, $24,

            -- Position Sizing
            $25, $26, $27, $28, $29, $30,

            -- Side Preference
            $31,

            -- Stop Loss
            $32, $33, $34, $35, $36, $37, $38, $39, $40,

            -- Take Profit
            $41, $42, $43, $44, $45,

            -- Pyramiding
            $46, $47, $48, $49, $50, $51, $52,

            -- Order Preferences
            $53, $54,

            -- Auto-submit
            $55,

            -- Timestamps
            $56, $56,

            -- Event Sourcing
            1,

            -- Metadata
            $57
        )
        """,
        event.automation_id, event.user_id, event.name, event.symbol,
        event.webhook_token, event.webhook_url, event.occurred_at,

        # Derivatives
        event.asset_type.value,
        event.option_underlying_symbol, event.option_strike_price, event.option_expiration_date,
        event.option_type.value if event.option_type else None,
        event.option_action.value if event.option_action else None,
        event.option_contract_size, event.option_multiplier,
        event.future_underlying_symbol, event.future_contract_month, event.future_expiration_date,
        event.future_contract_size, event.future_tick_size, event.future_tick_value,
        event.future_multiplier, event.future_exchange, event.future_product_code,

        # Position Sizing
        event.position_sizing_type.value, event.fixed_quantity, event.amount_per_position,
        event.risk_per_position, event.percent_of_equity, event.use_buying_power,

        # Side Preference
        event.side_preference,

        # Stop Loss
        event.stop_loss_type.value if event.stop_loss_type else None,
        event.stop_loss_price, event.stop_loss_dollar_amount, event.stop_loss_percentage,
        event.stop_loss_atr_multiplier, event.stop_loss_atr_period,
        event.stop_loss_trailing, event.stop_loss_trail_amount, event.stop_loss_trail_percentage,

        # Take Profit
        event.take_profit_type.value if event.take_profit_type else None,
        event.take_profit_price, event.take_profit_dollar_amount, event.take_profit_percentage,
        event.take_profit_risk_reward_ratio,

        # Pyramiding (7 fields matching SQL schema)
        event.pyramiding_enabled,
        event.pyramiding_max_entries,
        event.pyramiding_size_factor,
        event.pyramiding_min_profit,
        event.pyramiding_min_spacing,
        event.pyramiding_move_stop,
        event.pyramiding_breakeven_after,

        # Order Preferences
        event.entry_order_type, event.exit_order_type,

        # Auto-submit
        event.auto_submit,

        # Timestamps
        event.occurred_at,

        # Metadata
        event.metadata
    )

    # Insert broker account relationships
    for account_id in event.account_ids:
        await pg_client.execute(
            """
            INSERT INTO automation_broker_accounts (automation_id, account_id, routing_order)
            VALUES ($1, $2, 0)
            ON CONFLICT (automation_id, account_id) DO NOTHING
            """,
            event.automation_id, account_id
        )
```

**Key Patterns:**
- Direct SQL execution via `pg_client`
- Comprehensive field mapping
- Junction table for relationships
- Idempotency with `ON CONFLICT DO NOTHING`

---

### Example 2: SYNC Projection with Decorator (Broker Connection)

**File:** `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_connection/projectors.py`

```python
@sync_projection("BrokerConnectionEstablished", priority=1, timeout=2.0)
@monitor_projection
async def on_broker_connection_established(self, envelope: EventEnvelope) -> None:
    """
    CRITICAL: Handle broker connection establishment.

    Priority 1: CRITICAL - OAuth callback polls this!
    Timeout: 2.0s - Must complete quickly
    """
    event_data = envelope.event_data
    broker_connection_id = envelope.aggregate_id

    log.info(f"[SYNC] Projecting BrokerConnectionEstablished for {broker_connection_id}")

    # Get existing projection
    proj = await self._get_projection_or_warn(broker_connection_id, "BrokerConnectionEstablished")
    if not proj:
        return

    # Update connection state
    updates = {
        "connected": True,
        "last_connection_status": "CONNECTED",
        "last_connected_at": event_data.get('established_at'),
        "last_status_reason": event_data.get('status_message', 'Connection established'),
        "updated_at": event_data.get('established_at')
    }

    # CRITICAL FIX: Cache-aware update for instant WSE notification
    await self.read_repo.update_with_cache_invalidation(
        broker_connection_id=broker_connection_id,
        updates=updates
    )

    log.info(f"[SYNC] Connection {broker_connection_id} marked as connected")
```

**Key Patterns:**
- `@sync_projection` decorator with priority and timeout
- `@monitor_projection` for metrics
- Helper method for safe projection lookup
- Cache invalidation for real-time updates

---

### Example 3: ASYNC Projection with Update (Broker Connection)

```python
async def on_broker_disconnected(self, envelope: EventEnvelope) -> None:
    """
    Handle broker disconnection.

    ASYNC - Eventual consistency OK.
    """
    event_data = envelope.event_data
    broker_connection_id = envelope.aggregate_id

    log.info(f"[ASYNC] Projecting BrokerDisconnected for {broker_connection_id}")

    # Get existing projection
    proj = await self.read_repo.get_by_id(broker_connection_id)
    if not proj:
        log.warning(f"Connection {broker_connection_id} not found for disconnection")
        return

    # Calculate grace period
    disconnected_at = event_data.get('disconnected_at')
    grace_period_ends_at = disconnected_at + timedelta(hours=self.grace_period_hours)

    # Update connection state
    updates = {
        "connected": False,
        "last_connection_status": "DISCONNECTED",
        "disconnected_at": disconnected_at,
        "grace_period_ends_at": grace_period_ends_at,
        "last_status_reason": event_data.get('reason', 'Connection lost'),
        "updated_at": disconnected_at
    }

    await self.read_repo.update(broker_connection_id, updates)

    log.info(
        f"[ASYNC] Connection {broker_connection_id} marked as disconnected, "
        f"grace period until {grace_period_ends_at}"
    )
```

**Key Patterns:**
- No `@sync_projection` decorator (ASYNC by default)
- Existence check before update
- Business logic for grace period calculation
- Detailed logging

---

### Example 4: Cross-Domain Projection (Automation)

```python
from app.broker_account.events import BrokerAccountDeleted, BrokerAccountsBatchDeleted

async def project_broker_account_deleted(event: BrokerAccountDeleted, pg_client):
    """
    Cross-domain projection: Remove automation when account deleted.

    Listens to BrokerAccount domain events.
    """
    account_id = event.account_id

    # Remove account from automations
    await pg_client.execute(
        """
        DELETE FROM automation_broker_accounts
        WHERE account_id = $1
        """,
        account_id
    )

    # Check if any automations now have no accounts
    orphaned = await pg_client.fetch(
        """
        SELECT a.id
        FROM automations a
        LEFT JOIN automation_broker_accounts aba ON a.id = aba.automation_id
        WHERE aba.automation_id IS NULL
        """,
    )

    # Deactivate orphaned automations
    for row in orphaned:
        await pg_client.execute(
            """
            UPDATE automations
            SET status = 'suspended',
                suspended_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            """,
            row['id']
        )

async def project_broker_accounts_batch_deleted(event: BrokerAccountsBatchDeleted, pg_client):
    """
    Cross-domain projection: Batch account deletion.

    Handles cleanup for multiple accounts at once.
    """
    account_ids = event.account_ids

    # Remove all accounts from automations
    await pg_client.execute(
        """
        DELETE FROM automation_broker_accounts
        WHERE account_id = ANY($1::uuid[])
        """,
        account_ids
    )

    # Deactivate orphaned automations (same as above)
    # ...
```

**Key Patterns:**
- Import events from other domains
- Cascade operations
- Orphan detection and cleanup
- Batch operations for efficiency

---

## Testing Strategies

### Unit Testing Projectors

```python
import pytest
from uuid import uuid4
from datetime import datetime, UTC

@pytest.mark.asyncio
async def test_automation_created_projection(mock_pg_client):
    """Test AutomationCreatedEvent projection"""
    # Arrange
    automation_id = uuid4()
    user_id = uuid4()

    event = AutomationCreatedEvent(
        automation_id=automation_id,
        user_id=user_id,
        name="Test Automation",
        symbol="AAPL",
        webhook_token="token123",
        webhook_url="https://webhook.url",
        asset_type=AssetType.STOCK,
        account_ids=[uuid4()],
        occurred_at=datetime.now(UTC)
    )

    # Act
    await project_automation_created(event, mock_pg_client)

    # Assert
    assert mock_pg_client.execute.call_count == 2  # INSERT automation + account relation
    insert_call = mock_pg_client.execute.call_args_list[0]
    assert "INSERT INTO automations" in insert_call[0][0]
    assert insert_call[0][1] == automation_id
    assert insert_call[0][2] == user_id

@pytest.mark.asyncio
async def test_automation_created_projection_idempotency(mock_pg_client):
    """Test projection is idempotent"""
    event = AutomationCreatedEvent(...)

    # First projection
    await project_automation_created(event, mock_pg_client)

    # Second projection (should handle duplicate)
    # ON CONFLICT DO NOTHING handles idempotency
    await project_automation_created(event, mock_pg_client)

    # Verify no errors raised
    assert True
```

### Integration Testing

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_automation_lifecycle_projection(test_db, event_bus):
    """Test complete automation lifecycle through projections"""
    automation_id = uuid4()
    user_id = uuid4()

    # Emit AutomationCreatedEvent
    created_event = AutomationCreatedEvent(
        automation_id=automation_id,
        user_id=user_id,
        name="Test",
        symbol="AAPL",
        # ... fields
    )
    await event_bus.publish("automation_events", created_event.model_dump())

    # Wait for projection
    await asyncio.sleep(0.5)

    # Verify in database
    automation = await test_db.fetchrow(
        "SELECT * FROM automations WHERE id = $1",
        automation_id
    )
    assert automation is not None
    assert automation['status'] == 'inactive'

    # Emit AutomationActivatedEvent
    activated_event = AutomationActivatedEvent(
        automation_id=automation_id,
        user_id=user_id,
        activated_at=datetime.now(UTC)
    )
    await event_bus.publish("automation_events", activated_event.model_dump())

    await asyncio.sleep(0.5)

    # Verify status updated
    automation = await test_db.fetchrow(
        "SELECT * FROM automations WHERE id = $1",
        automation_id
    )
    assert automation['status'] == 'active'
```

---

## Performance Tips

### 1. Use Batch Operations

```python
# ❌ BAD - Individual inserts
for account_id in event.account_ids:
    await pg_client.execute(
        "INSERT INTO automation_broker_accounts ...",
        automation_id, account_id
    )

# ✅ GOOD - Batch insert
account_values = [(automation_id, acc_id, 0) for acc_id in event.account_ids]
await pg_client.executemany(
    "INSERT INTO automation_broker_accounts (automation_id, account_id, routing_order) VALUES ($1, $2, $3)",
    account_values
)
```

### 2. Minimize Database Roundtrips

```python
# ✅ GOOD - Single UPDATE with multiple fields
await pg_client.execute(
    """
    UPDATE automations
    SET status = $2,
        activated_at = $3,
        updated_at = $4,
        aggregate_version = aggregate_version + 1
    WHERE id = $1
    """,
    automation_id, 'active', activated_at, updated_at
)
```

### 3. Use Indexes

```sql
-- Create indexes for projection queries
CREATE INDEX idx_automations_user_id ON automations(user_id);
CREATE INDEX idx_automation_accounts_automation_id ON automation_broker_accounts(automation_id);
CREATE INDEX idx_automation_accounts_account_id ON automation_broker_accounts(account_id);
```

### 4. Avoid N+1 in Cross-Domain Projections

```python
# ❌ BAD - N+1 queries
for account_id in deleted_account_ids:
    automations = await pg_client.fetch(
        "SELECT * FROM automation_broker_accounts WHERE account_id = $1",
        account_id
    )

# ✅ GOOD - Single query
automations = await pg_client.fetch(
    """
    SELECT DISTINCT automation_id
    FROM automation_broker_accounts
    WHERE account_id = ANY($1::uuid[])
    """,
    deleted_account_ids
)
```

### 5. Use Transactions for Multi-Step Projections

```python
async def on_automation_deleted(self, envelope: EventEnvelope) -> None:
    """Use transaction for cleanup"""
    automation_id = envelope.aggregate_id

    async with self.db.transaction():
        # Delete related records
        await self.db.execute(
            "DELETE FROM automation_broker_accounts WHERE automation_id = $1",
            automation_id
        )

        await self.db.execute(
            "DELETE FROM automation_signals WHERE automation_id = $1",
            automation_id
        )

        # Delete automation
        await self.db.execute(
            "DELETE FROM automations WHERE id = $1",
            automation_id
        )
```

---

## Common Mistakes

### Mistake 1: Not Handling Idempotency

```python
# ❌ WRONG - Will fail on replay
async def on_automation_created(self, envelope: EventEnvelope):
    # Crashes if already exists!
    await pg_client.execute(
        "INSERT INTO automations (id, ...) VALUES ($1, ...)",
        automation_id, ...
    )

# ✅ CORRECT - Idempotent
async def on_automation_created(self, envelope: EventEnvelope):
    # Check existence
    existing = await pg_client.fetchrow(
        "SELECT id FROM automations WHERE id = $1",
        automation_id
    )
    if existing:
        return  # Already projected

    await pg_client.execute(...)

# ✅ BETTER - Use ON CONFLICT
async def on_automation_created(self, envelope: EventEnvelope):
    await pg_client.execute(
        """
        INSERT INTO automations (id, ...)
        VALUES ($1, ...)
        ON CONFLICT (id) DO NOTHING
        """,
        automation_id, ...
    )
```

### Mistake 2: Business Logic in Projector

```python
# ❌ WRONG - Business logic in projector!
async def on_automation_activated(self, envelope: EventEnvelope):
    automation = await self.read_repo.get_by_id(automation_id)

    # Business validation - NO!
    if automation.status == 'suspended':
        raise InvalidStateError("Cannot activate suspended automation")

    await self.read_repo.update(...)

# ✅ CORRECT - Just project the event
async def on_automation_activated(self, envelope: EventEnvelope):
    # Event already validated by aggregate
    await self.read_repo.update(
        automation_id=automation_id,
        updates={
            "status": "active",
            "activated_at": event_data['activated_at']
        }
    )
```

### Mistake 3: Using Aggregates in Projectors

```python
# ❌ WRONG - Loading aggregate in projector!
async def on_automation_updated(self, envelope: EventEnvelope):
    # Slow! Replays all events!
    events = await self.event_store.get_events(...)
    automation = Automation.from_events(events)

    # Use read model instead!

# ✅ CORRECT - Use read model
async def on_automation_updated(self, envelope: EventEnvelope):
    # Fast read from projection
    automation = await self.read_repo.get_by_id(automation_id)
    await self.read_repo.update(...)
```

### Mistake 4: Not Handling Missing Projections

```python
# ❌ WRONG - Assumes projection exists
async def on_automation_updated(self, envelope: EventEnvelope):
    # Crashes if automation not found!
    await pg_client.execute(
        "UPDATE automations SET ... WHERE id = $1",
        automation_id
    )

# ✅ CORRECT - Check existence
async def on_automation_updated(self, envelope: EventEnvelope):
    automation = await self.read_repo.get_by_id(automation_id)
    if not automation:
        log.warning(f"Automation {automation_id} not found - may have been deleted")
        return

    await self.read_repo.update(...)
```

### Mistake 5: Forgetting to Register Events

```python
# ❌ WRONG - Event not in domain registry!
# Projector exists but never called

# ✅ CORRECT - Register in domain_registry.py
DOMAIN_REGISTRY = {
    "automation": {
        "projector_class": AutomationProjector,
        "events": [
            "AutomationCreatedEvent",
            "AutomationUpdatedEvent",
            "AutomationActivatedEvent",  # Must list ALL events!
        ]
    }
}
```

---

## Summary Checklist

When implementing a projector:

- [ ] Define events with `BaseEvent` (Pydantic)
- [ ] Create projector class with `__init__` accepting dependencies
- [ ] Implement projection methods (`on_event_name`)
- [ ] Use `@sync_projection` for critical paths
- [ ] Handle idempotency (check existence or use `ON CONFLICT`)
- [ ] Never include business logic (just project events)
- [ ] Don't load aggregates (use read models)
- [ ] Handle missing projections gracefully
- [ ] Use transactions for multi-step operations
- [ ] Register events in domain registry
- [ ] Write unit and integration tests
- [ ] Add indexes for query performance
- [ ] Use batch operations for efficiency
- [ ] Configure SYNC events in `sync_events.py`
- [ ] Monitor projection performance

---

## References

- **Automation Projectors**: `/Users/silvermpx/PycharmProjects/TradeCore/app/automation/projectors.py`
- **Broker Connection Projectors**: `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_connection/projectors.py`
- **SYNC Event Configuration**: `/Users/silvermpx/PycharmProjects/TradeCore/app/broker_connection/sync_events.py`
- **Domain Registry**: `/Users/silvermpx/PycharmProjects/TradeCore/app/infra/consumers/domain_registry.py`
- **Event Envelope**: `/Users/silvermpx/PycharmProjects/TradeCore/app/infra/event_store/event_envelope.py`
- **Sync Decorators**: `/Users/silvermpx/PycharmProjects/TradeCore/app/infra/event_store/sync_decorators.py`

---

**Next Steps:**
- Read [Command Handler Guide](COMMAND_HANDLER_GUIDE.md) for write side
- Read [Query Handler Guide](QUERY_HANDLER_GUIDE.md) for read side
- Review [CQRS Documentation](../cqrs.md) for architecture overview
- Study [Sync Projection Configuration](../SYNC_PROJECTION_OPTIMIZATION_COMPLETE_NOV2025.md)
