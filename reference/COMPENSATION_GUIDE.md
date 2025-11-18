# Saga Compensation Guide

**Status**: ✅ Reference Guide
**Last Updated**: 2025-11-10
**Applies To**: TradeCore v0.5+

---

## Table of Contents

1. [Overview](#overview)
2. [When Compensation is Needed](#when-compensation-is-needed)
3. [When Compensation is NOT Needed](#when-compensation-is-not-needed)
4. [Compensation Strategies](#compensation-strategies)
5. [Implementation Patterns](#implementation-patterns)
6. [Rollback Patterns](#rollback-patterns)
7. [Testing Compensation](#testing-compensation)

---

## Overview

**Compensation** is the process of undoing saga steps when a later step fails. Unlike database transactions (which automatically rollback on error), sagas require **explicit compensation logic** for each step.

### Key Concepts

**Forward Recovery (Retry):**
- Attempt to complete the operation (preferred)
- Used for transient failures (network, timeouts)
- Example: Retry API call 3 times before failing

**Backward Recovery (Compensation):**
- Undo completed steps when saga fails
- Used for semantic rollback (business logic)
- Example: Cancel order if position update fails

**Pivot Transaction:**
- The point of no return in a saga
- After this step, only forward recovery allowed
- Example: Charging customer's credit card

---

## When Compensation is Needed

### ✅ Implement Compensation For:

#### 1. State Changes in External Systems

**Example: Order Submission**

```python
async def _submit_order_to_broker(self, **context):
    """Submit order - REQUIRES compensation"""
    broker_order_id = await broker_api.submit_order(order_data)
    return {'broker_order_id': broker_order_id}

async def _compensate_order_submission(self, **context):
    """Compensation: Cancel order if later step fails"""
    broker_order_id = context.get('broker_order_id')
    if broker_order_id:
        try:
            await broker_api.cancel_order(broker_order_id)
            log.info(f"Canceled order {broker_order_id} (saga compensation)")
        except Exception as e:
            log.error(f"Failed to cancel order: {e}")
            # Publish compensation failure for manual intervention
            await event_bus.publish("saga.compensation.failed", {...})
```

**Why:** Order was submitted to broker. If position update fails, must cancel order to prevent orphaned trade.

---

#### 2. Resource Allocation

**Example: Reserve Buying Power**

```python
async def _reserve_buying_power(self, **context):
    """Reserve funds - REQUIRES compensation"""
    amount = context['order_value']
    await account.reserve_buying_power(amount)
    return {'reserved_amount': amount}

async def _compensate_buying_power_reservation(self, **context):
    """Compensation: Release reserved funds"""
    amount = context.get('reserved_amount')
    if amount:
        await account.release_buying_power(amount)
        log.info(f"Released {amount} buying power (saga compensation)")
```

**Why:** Funds were locked. Must release if order submission fails.

---

#### 3. Cross-Domain State Changes

**Example: Create Position + Update Portfolio**

```python
async def _create_position(self, **context):
    """Create position - REQUIRES compensation"""
    position_id = await command_bus.send(OpenPositionCommand(...))
    return {'position_id': position_id}

async def _compensate_position_creation(self, **context):
    """Compensation: Close position"""
    position_id = context.get('position_id')
    if position_id:
        await command_bus.send(ClosePositionCommand(
            position_id=position_id,
            reason="saga_compensation"
        ))
        log.info(f"Closed position {position_id} (saga compensation)")
```

**Why:** Position exists in Position domain. If portfolio update fails, must close position to maintain consistency.

---

#### 4. Account/Entity Creation

**Example: Link Broker Accounts**

```python
async def _link_broker_accounts(self, **context):
    """Link accounts - REQUIRES compensation"""
    account_ids = []
    for account_info in context['discovered_accounts']:
        account_id = await command_bus.send(LinkBrokerAccountCommand(...))
        account_ids.append(account_id)

    return {'account_ids': account_ids}

async def _compensate_account_linking(self, **context):
    """Compensation: Delete linked accounts"""
    account_ids = context.get('account_ids', [])

    for account_id in account_ids:
        try:
            await command_bus.send(DeleteBrokerAccountCommand(
                account_id=account_id,
                reason="saga_compensation"
            ))
            log.info(f"Deleted account {account_id} (saga compensation)")
        except Exception as e:
            log.error(f"Failed to delete account {account_id}: {e}")
```

**Why:** Accounts were created. If later step fails (e.g., streaming setup), must delete accounts.

---

## When Compensation is NOT Needed

### ❌ Skip Compensation (No-op) For:

#### 1. Read-Only Operations (Queries, Validation)

```python
async def _verify_connection_exists(self, **context):
    """Read-only - NO compensation needed"""
    connection = await query_bus.query(GetBrokerConnectionDetailsQuery(...))
    return {'connection_exists': connection is not None}

async def _noop_compensate(self, **context) -> None:
    """No-op compensation for read-only step"""
    pass  # Nothing to undo
```

**Why:** No state change occurred. Nothing to undo.

---

#### 2. Idempotent Operations

```python
async def _publish_event(self, **context):
    """Publish event - NO compensation needed (idempotent)"""
    await event_bus.publish(SomeEvent(...))
    return {'event_published': True}

async def _noop_compensate(self, **context) -> None:
    """No compensation for idempotent event publishing"""
    pass  # Event publishing is idempotent (replay safe)
```

**Why:** Event publishing is idempotent. Re-publishing same event has no side effects (event deduplication).

---

#### 3. After Pivot Transaction

```python
async def _charge_customer(self, **context):
    """PIVOT: Charge customer - NO compensation after this"""
    charge_id = await payment_api.charge(amount)
    return {'charge_id': charge_id, 'pivot': True}

async def _ship_product(self, **context):
    """After pivot - NO compensation (only forward recovery)"""
    tracking_number = await shipping_api.ship(order_id)
    return {'tracking_number': tracking_number}

async def _noop_compensate(self, **context) -> None:
    """No compensation after pivot - forward recovery only"""
    pass
```

**Why:** After charging customer, can't rollback (refund is a new transaction). Must complete saga or retry later.

---

#### 4. Cache Operations

```python
async def _clear_cache(self, **context):
    """Cache clear - NO compensation needed"""
    await cache_manager.delete_pattern(f"user:{user_id}*")
    return {'cache_cleared': True}

async def _noop_compensate(self, **context) -> None:
    """No compensation for cache operations"""
    pass  # Cache will be repopulated on next query
```

**Why:** Cache is transient. Clearing cache has no business impact (just performance).

---

#### 5. Wait/Delay Steps

```python
async def _wait_for_event_propagation(self, **context):
    """Wait step - NO compensation needed"""
    await asyncio.sleep(2.0)
    return {'wait_complete': True}

async def _noop_compensate(self, **context) -> None:
    """No compensation for wait steps"""
    pass  # Time already passed, can't undo
```

**Why:** Waiting is passive. No state change to undo.

---

## Compensation Strategies

### Strategy 1: Direct Reversal (Symmetric Compensation)

**Pattern:** Undo operation with symmetric opposite action

```python
# Step: Reserve funds
async def _reserve_funds(self, **context):
    await account.reserve(amount)
    return {'reserved': amount}

# Compensation: Release funds (symmetric opposite)
async def _compensate_reserve_funds(self, **context):
    amount = context['reserved']
    await account.release(amount)
```

**Use For:**
- Resource allocation (reserve/release)
- Locks (acquire/release)
- State toggles (enable/disable)

---

### Strategy 2: Logical Deletion (Soft Delete)

**Pattern:** Mark entity as deleted instead of physical removal

```python
# Step: Create entity
async def _create_entity(self, **context):
    entity_id = await command_bus.send(CreateEntityCommand(...))
    return {'entity_id': entity_id}

# Compensation: Mark as deleted (soft delete)
async def _compensate_entity_creation(self, **context):
    entity_id = context['entity_id']
    await command_bus.send(MarkEntityDeletedCommand(
        entity_id=entity_id,
        reason="saga_compensation"
    ))
```

**Use For:**
- Entities with foreign key references
- Audit trail preservation
- Soft delete domains

---

### Strategy 3: Cancellation (API Call Reversal)

**Pattern:** Call API to cancel/revert operation

```python
# Step: Submit order
async def _submit_order(self, **context):
    order_id = await broker_api.place_order(order_data)
    return {'broker_order_id': order_id}

# Compensation: Cancel order
async def _compensate_order_submission(self, **context):
    order_id = context['broker_order_id']
    await broker_api.cancel_order(order_id)
```

**Use For:**
- External API calls (orders, reservations)
- Payment processing (before settlement)
- Booking systems

---

### Strategy 4: Counter-Transaction (New Transaction to Reverse)

**Pattern:** Create new transaction that reverses effect

```python
# Step: Charge customer
async def _charge_customer(self, **context):
    charge_id = await payment_api.charge(amount)
    return {'charge_id': charge_id}

# Compensation: Issue refund (counter-transaction)
async def _compensate_charge(self, **context):
    charge_id = context['charge_id']
    refund_id = await payment_api.refund(charge_id)
    log.warning(f"Refunded {charge_id} (saga compensation)")
```

**Use For:**
- Financial transactions (after settlement)
- Irreversible operations
- Audit trail required

---

### Strategy 5: Manual Intervention

**Pattern:** Publish event for human review

```python
# Step: Complex operation
async def _complex_operation(self, **context):
    result = await perform_complex_operation()
    return {'operation_result': result}

# Compensation: Flag for manual review
async def _compensate_complex_operation(self, **context):
    await event_bus.publish("saga.compensation.manual_intervention_required", {
        "saga_id": str(self.saga_id),
        "step": "complex_operation",
        "context": context,
        "reason": "Cannot automatically compensate complex operation",
        "requires_manual_review": True
    })

    log.error(f"Saga {self.saga_id}: Manual intervention required for compensation")
```

**Use For:**
- Operations that cannot be automatically reversed
- Complex state changes spanning multiple systems
- Critical business operations requiring human judgment

---

## Implementation Patterns

### Pattern 1: Track Compensation Data in Context

```python
async def _step_with_compensation_data(self, **context):
    """Store data needed for compensation"""

    # Perform operation
    entity_id = await create_entity()
    broker_order_id = await submit_order()

    # Return compensation data
    return {
        'step_completed': True,
        'entity_id': entity_id,           # Needed for deletion
        'broker_order_id': broker_order_id,  # Needed for cancellation
        'created_at': datetime.now(UTC)   # Audit info
    }

async def _compensate(self, **context):
    """Use compensation data"""
    entity_id = context.get('entity_id')
    broker_order_id = context.get('broker_order_id')

    if entity_id:
        await delete_entity(entity_id)

    if broker_order_id:
        await cancel_order(broker_order_id)
```

---

### Pattern 2: Best-Effort Compensation

```python
async def _compensate_with_fallback(self, **context):
    """Try compensation, log failure if can't"""

    entity_ids = context.get('entity_ids', [])

    for entity_id in entity_ids:
        try:
            await delete_entity(entity_id)
            log.info(f"Compensated {entity_id}")
        except EntityNotFoundError:
            # Already deleted - compensation is idempotent
            log.info(f"Entity {entity_id} already deleted (idempotent compensation)")
        except Exception as e:
            # Log failure but don't raise (best-effort)
            log.error(f"Failed to compensate {entity_id}: {e}")

            # Publish compensation failure for monitoring
            await event_bus.publish("saga.compensation.failed", {
                "saga_id": str(self.saga_id),
                "entity_id": str(entity_id),
                "error": str(e)
            })
```

**Why:** Compensation should be best-effort. Don't fail saga if compensation fails (already in failure state).

---

### Pattern 3: Conditional Compensation

```python
async def _conditional_compensate(self, **context):
    """Only compensate if conditions met"""

    # Check if compensation is needed
    if context.get('already_existed'):
        # Entity already existed - don't delete
        log.info("Skipping compensation - entity already existed")
        return

    if context.get('pivot_reached'):
        # After pivot - no compensation
        log.info("Skipping compensation - past pivot point")
        return

    # Perform compensation
    entity_id = context['entity_id']
    await delete_entity(entity_id)
```

---

### Pattern 4: Compensation with Retry

```python
async def _compensate_with_retry(self, **context):
    """Retry compensation on transient failures"""

    entity_id = context['entity_id']

    retry_config = RetryConfig(
        max_attempts=3,
        initial_delay_ms=500,
        backoff_factor=2.0,
        retry_condition=lambda e: isinstance(e, (TimeoutError, ConnectionError))
    )

    try:
        await retry_async(
            lambda: delete_entity(entity_id),
            retry_config=retry_config,
            context=f"Compensation for {entity_id}"
        )
        log.info(f"Compensated {entity_id} successfully")
    except Exception as e:
        log.error(f"Failed to compensate after retries: {e}")
        # Publish for manual intervention
        await event_bus.publish("saga.compensation.failed", {...})
```

---

## Rollback Patterns

### Full Rollback (All Steps)

```python
# Saga fails at step 3 → Compensates steps 2, 1 (reverse order)

Steps:
1. Reserve funds ✅
2. Submit order ✅
3. Update position ❌ FAILED

Compensation (reverse order):
2. Cancel order ✅
1. Release funds ✅
```

**Implementation:**

```python
class SagaManager:
    async def execute_saga(self, saga: BaseSaga):
        completed_steps = []

        try:
            for step in saga.steps:
                result = await self._execute_step(step)
                completed_steps.append((step, result))

        except Exception as e:
            # Rollback in REVERSE order
            for step, result in reversed(completed_steps):
                try:
                    await step.compensate(**result)
                except Exception as comp_error:
                    log.error(f"Compensation failed: {comp_error}")
            raise
```

---

### Partial Rollback (Selective Compensation)

```python
# Only compensate certain steps based on failure type

async def _compensate_step(self, **context):
    """Selective compensation based on failure"""

    failure_type = context.get('failure_type')

    if failure_type == 'validation_error':
        # No compensation needed - validation only
        return

    if failure_type == 'timeout':
        # Retry instead of compensate
        raise RetryableError("Timeout - retry saga")

    if failure_type == 'broker_api_error':
        # Compensate broker operations only
        await self._compensate_broker_operations(context)

    # Default: Full compensation
    await self._compensate_all_operations(context)
```

---

### Forward-Only (No Rollback After Pivot)

```python
# After pivot, only forward recovery allowed

class OrderExecutionSaga(BaseSaga):
    def define_steps(self):
        return [
            SagaStep("validate_order", ...),        # Can rollback
            SagaStep("reserve_funds", ...),         # Can rollback
            SagaStep("submit_order", ...),          # Can rollback

            # PIVOT POINT: Customer charged
            SagaStep("charge_customer", ...),       # CANNOT rollback (refund is new transaction)

            # After pivot: Only retry, no rollback
            SagaStep("fulfill_order", ...),         # Retry until success
            SagaStep("send_confirmation", ...),     # Retry until success
        ]
```

---

## Testing Compensation

### Unit Test Template

```python
@pytest.mark.asyncio
async def test_saga_compensation():
    """Test saga compensation on failure"""

    # Setup
    saga = MySaga()
    context = {
        'command_bus': mock_command_bus,
        'query_bus': mock_query_bus,
        'event_bus': mock_event_bus,
        'entity_id': uuid.uuid4()
    }

    # Mock step 1 success, step 2 failure
    mock_command_bus.send.side_effect = [
        {'entity_created': True, 'entity_id': context['entity_id']},  # Step 1 success
        Exception("Step 2 failed")  # Step 2 failure
    ]

    # Execute saga (should fail and compensate)
    with pytest.raises(Exception):
        await saga.execute(**context)

    # Assert compensation was called
    assert mock_command_bus.send.call_count == 3  # Step 1, Step 2 (failed), Compensation
    delete_call = mock_command_bus.send.call_args_list[-1]
    assert isinstance(delete_call[0][0], DeleteEntityCommand)
    assert delete_call[0][0].entity_id == context['entity_id']
```

---

### Integration Test (Full Workflow)

```python
@pytest.mark.asyncio
async def test_saga_compensation_integration():
    """Test compensation in full workflow"""

    # Create real entities
    connection_id = await create_broker_connection()
    saga = BrokerConnectionSaga()

    # Mock broker API to fail on account discovery
    with patch('app.infra.broker_adapters.AlpacaAdapter.get_accounts') as mock_api:
        mock_api.side_effect = BrokerAPIError("Account discovery failed")

        # Execute saga (should fail)
        with pytest.raises(BrokerAPIError):
            await saga.execute(broker_connection_id=connection_id)

    # Assert compensation: Connection was purged
    connection = await query_bus.query(GetBrokerConnectionDetailsQuery(connection_id))
    assert connection is None  # Deleted by compensation

    # Assert no orphaned accounts
    accounts = await query_bus.query(GetAccountsByConnectionQuery(connection_id))
    assert len(accounts) == 0
```

---

## Quick Reference

### Compensation Checklist

```
□ Identify reversible steps (need compensation)
□ Identify irreversible steps (no compensation)
□ Implement compensation for each reversible step
□ Store compensation data in step result
□ Handle compensation failures gracefully (best-effort)
□ Publish compensation failure events for monitoring
□ Test compensation with unit tests
□ Test compensation in integration tests
□ Document compensation strategy in code comments
```

### Decision Matrix

| Step Type | Compensation Needed? | Strategy |
|-----------|---------------------|----------|
| Read/Query | ❌ No | No-op |
| Cache operation | ❌ No | No-op |
| Wait/Delay | ❌ No | No-op |
| Resource allocation | ✅ Yes | Direct reversal (release) |
| External API call | ✅ Yes | Cancellation |
| Entity creation | ✅ Yes | Logical deletion |
| Financial transaction | ✅ Yes | Counter-transaction |
| Complex operation | ✅ Yes | Manual intervention |
| After pivot | ❌ No | Forward recovery only |

---

## References

- **Saga Manager**: `app/infra/saga/saga_manager.py`
- **Example Sagas**: `app/infra/saga/*.py`
- **Saga Patterns**: `docs/reference/SAGA_PATTERNS.md`
- **Testing Guide**: `docs/testing/SAGA_TESTING.md`

---

**Last Updated**: 2025-11-10
**Next Review**: 2026-01-10
