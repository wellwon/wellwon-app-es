# Database Patterns Guide

**Version**: TradeCore v0.5
**Last Updated**: 2025-11-10
**Component**: `app/infra/persistence/pg_client.py`

## Overview

The PostgreSQL client (`pg_client.py`) provides a high-performance, reliable database access layer with circuit breakers, retry logic, connection pooling, and multi-database support. All operations are async and include comprehensive monitoring.

**Key Features**:
- Multi-database support (main + virtual broker)
- AsyncPG connection pooling (100 connections default)
- Circuit breakers per database
- Configurable retry with deadlock handling
- Transaction context with isolation
- SYNC projection pattern (2s timeout)
- Granian multi-worker safety
- Health monitoring and diagnostics

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                          │
│                  (Domain Projectors, Commands)                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                     pg_client.py (Proxy)                        │
│              (Database Operations Abstraction)                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐   │
│  │   Convenience Proxies                                   │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │  db.fetch()      │  Main database operations           │   │
│  │  db.fetchrow()   │  (shorthand for fetch_for_db)       │   │
│  │  db.execute()    │                                      │   │
│  │  db.transaction()│                                      │   │
│  │                  │                                      │   │
│  │  vb_db.fetch()   │  VB database operations             │   │
│  │  vb_db.execute() │  (shorthand for VB database)        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │   Reliability Layer (per database)                      │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │  • Circuit Breaker (failure_threshold=5, timeout=30s)   │   │
│  │  • Retry (max_attempts=3, backoff_factor=2.0)           │   │
│  │  • Deadlock Retry (max_attempts=5, immediate)           │   │
│  │  • Pool Exhaustion Detection                            │   │
│  │  • Slow Query Logging (>1000ms)                         │   │
│  │  • Long Transaction Logging (>2000ms)                   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                   AsyncPG Connection Pool                       │
│              (Per Database, Per Worker Process)                 │
├─────────────────────────────────────────────────────────────────┤
│  Main DB Pool (20-100 connections)                              │
│  VB DB Pool (10-50 connections)                                 │
│                                                                  │
│  Features:                                                       │
│  • JSONB codec (automatic dict ↔ JSONB conversion)              │
│  • Connection health checks                                     │
│  • Acquire timeout (30s default)                                │
│  • Command timeout (60s default)                                │
│  • Distributed schema lock (multi-worker safety)                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                      PostgreSQL 15+                             │
│                  (Main + VB Databases)                          │
└─────────────────────────────────────────────────────────────────┘
```

## Core Concepts

### 1. Multi-Database Support

TradeCore uses **two separate databases**:

| Database     | Purpose                        | Pool Size (Prod) |
|--------------|--------------------------------|------------------|
| **Main**     | Domain events, read models     | 20-100           |
| **VB**       | Virtual broker isolated data   | 10-50            |

**Why separate databases?**
- **Isolation**: VB operations don't affect main system
- **Scaling**: Independent scaling and backup
- **Security**: Different access controls
- **Performance**: Dedicated resources for VB workloads

### 2. CQRS Read Models

TradeCore separates **write side** (event sourcing) from **read side** (projections):

```
Write Side (Event Store):
┌──────────────────────────────────────┐
│  Command → Aggregate → Domain Event  │
│  Events stored in KurrentDB/Redpanda │
└──────────────────────────────────────┘
                ↓
         (Domain Event)
                ↓
Read Side (Projections):
┌──────────────────────────────────────┐
│  Event → Projector → Read Model      │
│  Read models stored in PostgreSQL    │
└──────────────────────────────────────┘
```

**Read models** are optimized for queries:
- Denormalized (joins pre-computed)
- Indexed for common queries
- Updated asynchronously by projectors
- Can be rebuilt from events

### 3. SYNC Projections (2s Timeout)

Some projections need to complete **before the HTTP response**:

```python
# SYNC projection (blocks for 2s max)
@projector(UserCreatedEvent, projection_type=ProjectionType.SYNC)
async def project_user_created(event: UserCreatedEvent, pg_client: PGClient):
    # Must complete within 2 seconds
    await pg_client.execute(
        "INSERT INTO users (id, email, created_at) VALUES ($1, $2, $3)",
        event.user_id, event.email, event.timestamp
    )
    # UI needs this data immediately for redirect
```

**When to use SYNC**:
- User creation (UI redirects to dashboard)
- Account creation (UI shows new account)
- Connection creation (UI shows connection status)
- Order placement (UI updates order list)

**When NOT to use SYNC**:
- Analytics updates
- Audit log entries
- Notifications
- Reporting data

**Performance impact**:
- 75% SYNC rate = 75% of events block HTTP response
- Target: <30% SYNC rate for good UX
- TradeCore average: 25-35% SYNC rate

### 4. Transaction Context (ContextVar Pattern)

**Problem**: Projectors run inside transactions but need to use `pg_client` proxy

**Solution**: ContextVar stores transaction connection

```python
# ContextVar holds current transaction connection
_current_transaction_connection: ContextVar[Optional[asyncpg.Connection]] = ContextVar(
    'transaction_connection', default=None
)

# Transaction sets ContextVar
async with transaction_for_db(database) as conn:
    # ContextVar now holds 'conn'
    token = _current_transaction_connection.set(conn)

    # All pg_client calls use this connection automatically
    await db.execute("INSERT INTO ...")  # Uses transaction conn
    await db.fetch("SELECT ...")         # Uses transaction conn

    # ContextVar reset on exit
    _current_transaction_connection.reset(token)
```

**Benefits**:
- No need to pass connection through all layers
- Projectors use transaction connection automatically
- Prevents "transaction already closed" errors
- Thread-safe (ContextVar is async context-local)

## Basic Usage

### 1. Initialize Connection Pool

```python
from app.infra.persistence.pg_client import init_db_pool, init_all

# Initialize main database pool
await init_db_pool()

# Or initialize all databases
await init_all()

# Later: Get pool
from app.infra.persistence.pg_client import get_pool
pool = await get_pool()
```

### 2. Query Operations

```python
from app.infra.persistence.pg_client import db

# Fetch multiple rows
users = await db.fetch(
    "SELECT * FROM users WHERE status = $1",
    "active"
)
for user in users:
    print(user["email"])

# Fetch single row
user = await db.fetchrow(
    "SELECT * FROM users WHERE id = $1",
    "user-123"
)
print(user["email"] if user else "Not found")

# Fetch single value
count = await db.fetchval(
    "SELECT COUNT(*) FROM orders WHERE user_id = $1",
    "user-123"
)
print(f"Total orders: {count}")
```

### 3. Modify Operations

```python
# Execute DML (INSERT, UPDATE, DELETE)
await db.execute(
    "INSERT INTO users (id, email, created_at) VALUES ($1, $2, $3)",
    "user-123",
    "user@example.com",
    datetime.now(timezone.utc)
)

# Execute with result status
status = await db.execute(
    "UPDATE users SET last_login = $1 WHERE id = $2",
    datetime.now(timezone.utc),
    "user-123"
)
print(status)  # "UPDATE 1"
```

### 4. Transactions

```python
# Transaction automatically commits on success, rolls back on exception
async with db.transaction() as conn:
    # All operations in this block use the same connection
    await conn.execute(
        "INSERT INTO orders (id, user_id, symbol) VALUES ($1, $2, $3)",
        "order-1", "user-123", "AAPL"
    )
    await conn.execute(
        "UPDATE accounts SET balance = balance - $1 WHERE user_id = $2",
        1000.0, "user-123"
    )
    # Automatically commits here if no exceptions

# Rollback on exception
try:
    async with db.transaction() as conn:
        await conn.execute("INSERT INTO orders ...")
        raise ValueError("Order invalid")  # Transaction rolls back
except ValueError:
    pass
```

### 5. Virtual Broker Database

```python
from app.infra.persistence.pg_client import vb_db

# Query VB database
accounts = await vb_db.fetch(
    "SELECT * FROM vb_accounts WHERE user_id = $1",
    "user-123"
)

# Transaction in VB database
async with vb_db.transaction() as conn:
    await conn.execute(
        "UPDATE vb_accounts SET balance = $1 WHERE id = $2",
        95000.0, "vb-1"
    )
```

## Advanced Patterns

### 1. Transaction with Projector (ContextVar Pattern)

```python
# Projector (runs inside transaction automatically)
@projector(OrderPlacedEvent)
async def project_order_placed(event: OrderPlacedEvent, pg_client: PGClient):
    # pg_client automatically uses transaction connection
    await pg_client.execute(
        "INSERT INTO orders (id, symbol, status) VALUES ($1, $2, $3)",
        event.order_id, event.symbol, "pending"
    )

# Transaction caller (sets ContextVar)
async with db.transaction() as conn:
    # ContextVar set to 'conn'
    # Projector calls use this connection
    await project_order_placed(event, db)
    # No need to pass 'conn' explicitly
```

**How it works**:
1. `transaction()` creates connection and sets ContextVar
2. `db.execute()` checks ContextVar first
3. If ContextVar set, uses that connection (transaction)
4. If ContextVar not set, acquires new connection (normal)

### 2. SYNC Projection with Timeout

```python
from app.infra.event_store.sync_decorators import sync_projection

@sync_projection(timeout_seconds=2.0)
@projector(AccountCreatedEvent, projection_type=ProjectionType.SYNC)
async def project_account_created(event: AccountCreatedEvent, pg_client: PGClient):
    # Must complete in 2 seconds or raise TimeoutError
    await pg_client.execute(
        "INSERT INTO accounts (id, name, balance) VALUES ($1, $2, $3)",
        event.account_id, event.name, event.initial_balance
    )
    # UI waits for this to complete before showing account
```

**Timeout behavior**:
- Projection starts
- If exceeds 2s, `asyncio.TimeoutError` raised
- Transaction rolls back
- Event marked as failed (retries later)
- HTTP response returns (doesn't block indefinitely)

### 3. Deadlock Handling

```python
from app.config.reliability_config import ReliabilityConfigs

# Deadlocks are retried immediately (no delay)
retry_config = ReliabilityConfigs.postgres_deadlock_retry()
# max_attempts=5, initial_delay_ms=0, jitter=True

# pg_client automatically uses this config for transactions
async with db.transaction() as conn:
    # If deadlock detected, transaction retries immediately
    await conn.execute("UPDATE accounts SET balance = balance - $1", 100)
    await conn.execute("UPDATE positions SET quantity = quantity + $1", 10)
```

**How it works**:
1. Transaction starts
2. Deadlock detected: `deadlock detected` in error message
3. Retry immediately (no backoff)
4. New transaction attempt
5. Repeat up to 5 times
6. If still failing, raise exception

### 4. Distributed Schema Lock (Granian Multi-Worker)

**Problem**: With `--workers 4`, all 4 workers try to run schema simultaneously

**Solution**: Distributed Redis lock ensures only 1 worker runs schema

```python
from app.infra.persistence.pg_client import run_schema_from_file

# Schema execution (automatically uses distributed lock)
await run_schema_from_file("app/database/tradecore.sql")

# Behind the scenes:
# 1. Worker acquires Redis lock: "schema_init_main_tradecore.sql"
# 2. Other workers wait (up to 2 minutes)
# 3. First worker executes schema
# 4. Lock released
# 5. Other workers skip (schema already done)
```

**Lock configuration**:
```python
# From ReliabilityConfigs.schema_init_lock()
ttl_seconds=60            # Schema can take up to 60s
max_wait_ms=120000        # Wait up to 2 minutes
retry_delay_ms=500        # Check every 500ms
```

### 5. Connection Pool Monitoring

```python
# Monitor pool exhaustion
health = await db.health_check()

# Check pool usage
print(health["pool_info"])
# {
#     "size": 20,
#     "min_size": 20,
#     "max_size": 100
# }

# Warnings logged when pool > 90% used:
# "[POOL EXHAUSTION] main pool at 95/100 active connections (95% usage, 5 free)"
```

### 6. Slow Query Detection

```python
# Automatic slow query logging (>1000ms)
users = await db.fetch("SELECT * FROM users WHERE status = $1", "active")

# If query takes >1000ms:
# [SLOW QUERY] main FETCH took 1523ms: SELECT * FROM users WHERE status = $1 | args: 'active'
```

**Configure threshold**:
```bash
DB_SLOW_QUERY_THRESHOLD_MS=1000
```

### 7. Long Transaction Detection

```python
# Automatic long transaction logging (>2000ms)
async with db.transaction() as conn:
    await conn.execute("INSERT INTO orders ...")
    await asyncio.sleep(3)  # Simulate long operation
    await conn.execute("UPDATE accounts ...")

# Logs:
# [LONG TRANSACTION] main transaction took 3042ms (threshold: 2000ms)
```

**Configure threshold**:
```bash
DB_LONG_TRANSACTION_THRESHOLD_MS=2000
```

## Read Model Design

### 1. Denormalization

**Event Sourcing** (normalized):
```sql
-- Events table (append-only)
CREATE TABLE events (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(100),
    aggregate_id UUID,
    data JSONB,
    timestamp TIMESTAMPTZ
);
```

**Read Model** (denormalized):
```sql
-- User read model (optimized for queries)
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    -- Denormalized data from multiple events
    total_orders INT DEFAULT 0,
    total_spent DECIMAL(15,2) DEFAULT 0,
    last_order_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    -- Indexed columns
    INDEX idx_users_email (email),
    INDEX idx_users_status (status),
    INDEX idx_users_created_at (created_at)
);
```

**Benefits**:
- Single query vs joins across tables
- Pre-computed aggregates (total_orders, total_spent)
- Indexed for common queries
- Fast reads (optimized for SELECT)

### 2. Indexing Strategy

**Primary Key**: Always indexed automatically
```sql
id UUID PRIMARY KEY  -- Auto-indexed
```

**Foreign Keys**: Index for joins
```sql
user_id UUID NOT NULL,
INDEX idx_orders_user_id (user_id)
```

**Filter Columns**: Index for WHERE clauses
```sql
status VARCHAR(20) NOT NULL,
INDEX idx_orders_status (status)
```

**Timestamp Columns**: Index for ranges
```sql
created_at TIMESTAMPTZ NOT NULL,
INDEX idx_orders_created_at (created_at)
```

**Composite Index**: For multi-column queries
```sql
INDEX idx_orders_user_status (user_id, status)
-- Optimized for: WHERE user_id = $1 AND status = $2
```

**JSONB Index**: For JSONB queries
```sql
data JSONB NOT NULL,
INDEX idx_orders_data_gin ON orders USING GIN (data)
-- Optimized for: WHERE data @> '{"symbol": "AAPL"}'
```

### 3. Projection Update Pattern

```python
@projector(OrderPlacedEvent)
async def project_order_placed(event: OrderPlacedEvent, pg_client: PGClient):
    # Insert into orders table
    await pg_client.execute("""
        INSERT INTO orders (id, user_id, symbol, quantity, status, placed_at)
        VALUES ($1, $2, $3, $4, $5, $6)
    """, event.order_id, event.user_id, event.symbol, event.quantity, "pending", event.timestamp)

    # Update user aggregate (denormalized)
    await pg_client.execute("""
        UPDATE users
        SET total_orders = total_orders + 1,
            last_order_at = $1,
            updated_at = $1
        WHERE id = $2
    """, event.timestamp, event.user_id)
```

### 4. Idempotent Projections

**Problem**: Events may be replayed (retry, projection rebuild)

**Solution**: Use UPSERT (ON CONFLICT) for idempotency

```python
@projector(OrderPlacedEvent)
async def project_order_placed(event: OrderPlacedEvent, pg_client: PGClient):
    # Idempotent insert (won't fail on replay)
    await pg_client.execute("""
        INSERT INTO orders (id, user_id, symbol, quantity, status, placed_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (id) DO UPDATE
        SET status = EXCLUDED.status,
            updated_at = EXCLUDED.placed_at
    """, event.order_id, event.user_id, event.symbol, event.quantity, "pending", event.timestamp)
```

**When to use**:
- All projectors should be idempotent
- Use `ON CONFLICT` for inserts
- Use conditional updates for modifications
- Never use counters without checking existence

### 5. Aggregate Functions Best Practice

❌ **Wrong** (causes "aggregate function" error):
```python
# Missing GROUP BY
await pg_client.fetch("""
    SELECT user_id, COUNT(*) as order_count
    FROM orders
    WHERE status = $1
""", "filled")
# ERROR: column "user_id" must appear in GROUP BY clause
```

✅ **Correct** (with GROUP BY):
```python
await pg_client.fetch("""
    SELECT user_id, COUNT(*) as order_count
    FROM orders
    WHERE status = $1
    GROUP BY user_id
""", "filled")
```

✅ **Correct** (single aggregate, no GROUP BY needed):
```python
await pg_client.fetchval("""
    SELECT COUNT(*)
    FROM orders
    WHERE status = $1
""", "filled")
```

## Migration and Schema

### 1. Schema Files

```
app/database/
├── tradecore.sql        # Main database schema
└── tradecore_vb.sql     # VB database schema
```

### 2. Run Schema

```python
from app.infra.persistence.pg_client import run_schema_from_file

# Main database
await run_schema_from_file("app/database/tradecore.sql")

# VB database
await run_vb_schema("app/database/tradecore_vb.sql")
```

### 3. Schema Structure

```sql
-- Drop existing (dev/test only)
DROP TABLE IF EXISTS users CASCADE;

-- Create table
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_created_at ON users(created_at DESC);

-- Add constraints
ALTER TABLE users ADD CONSTRAINT chk_status
    CHECK (status IN ('active', 'inactive', 'suspended'));
```

### 4. Migrations (Future)

TradeCore currently uses **full schema files**. For production, use **migrations**:

**Alembic** (recommended):
```bash
# Install
pip install alembic

# Initialize
alembic init migrations

# Create migration
alembic revision -m "add users table"

# Apply migrations
alembic upgrade head
```

**Migration file**:
```python
# migrations/versions/001_add_users_table.py

def upgrade():
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        # ...
    )

def downgrade():
    op.drop_table('users')
```

## Configuration Reference

### Environment Variables

```bash
# Main Database
POSTGRES_DSN=postgresql://user:password@localhost:5432/tradecore
DATABASE_URL=postgresql://user:password@localhost:5432/tradecore
PG_POOL_MIN_SIZE=20                # Production default
PG_POOL_MAX_SIZE=100               # Production default
PG_POOL_TIMEOUT_SEC=30.0
PG_COMMAND_TIMEOUT_SEC=60.0

# VB Database
VB_POSTGRES_DSN=postgresql://user:password@localhost:5432/tradecore_vb
VB_DATABASE_URL=postgresql://user:password@localhost:5432/tradecore_vb
VB_PG_POOL_MIN_SIZE=10
VB_PG_POOL_MAX_SIZE=50
VB_PG_POOL_TIMEOUT_SEC=30.0
VB_PG_COMMAND_TIMEOUT_SEC=60.0

# Feature Flags
ENABLE_VB_DATABASE=true

# Monitoring
DB_SLOW_QUERY_THRESHOLD_MS=1000
DB_POOL_EXHAUSTION_THRESHOLD=0.9
DB_LONG_TRANSACTION_THRESHOLD_MS=2000
DB_SLOW_ACQUIRE_THRESHOLD_MS=500
```

### Pool Sizing

**Development** (single worker):
```bash
PG_POOL_MIN_SIZE=5
PG_POOL_MAX_SIZE=20
```

**Production** (4 workers):
```bash
PG_POOL_MIN_SIZE=20        # 5 per worker
PG_POOL_MAX_SIZE=100       # 25 per worker

# Total connections: 4 workers × 25 = 100
# PostgreSQL max_connections: 200 (2x buffer)
```

**Formula**:
```
Max Pool Per Worker = PG_POOL_MAX_SIZE / Number of Workers
Total Connections = Number of Workers × Max Pool Per Worker
PostgreSQL max_connections = Total Connections × 2 (safety buffer)
```

## Best Practices

### 1. Query Parameterization

✅ **Good** (parameterized):
```python
# Safe from SQL injection
user = await db.fetchrow(
    "SELECT * FROM users WHERE email = $1",
    user_email
)
```

❌ **Bad** (string interpolation):
```python
# SQL injection vulnerability!
user = await db.fetchrow(
    f"SELECT * FROM users WHERE email = '{user_email}'"
)
```

### 2. Transaction Scope

✅ **Good** (minimal scope):
```python
# Short transaction
async with db.transaction() as conn:
    await conn.execute("INSERT INTO orders ...")
    await conn.execute("UPDATE accounts ...")
# Released immediately
```

❌ **Bad** (long transaction):
```python
# Holds connection too long
async with db.transaction() as conn:
    await conn.execute("INSERT INTO orders ...")
    await expensive_api_call()  # Don't do this!
    await conn.execute("UPDATE accounts ...")
```

### 3. Error Handling

✅ **Good** (specific errors):
```python
from asyncpg.exceptions import UniqueViolationError, ForeignKeyViolationError

try:
    await db.execute(
        "INSERT INTO users (id, email) VALUES ($1, $2)",
        user_id, email
    )
except UniqueViolationError:
    raise DuplicateUserError(f"User with email {email} already exists")
except ForeignKeyViolationError:
    raise InvalidReferenceError("Referenced entity does not exist")
```

❌ **Bad** (generic errors):
```python
try:
    await db.execute("INSERT INTO users ...")
except Exception as e:
    # Too generic, hard to debug
    raise DatabaseError("Insert failed")
```

### 4. Datetime Handling

✅ **Good** (timezone-aware):
```python
from datetime import datetime, timezone

# Always use UTC
created_at = datetime.now(timezone.utc)

await db.execute(
    "INSERT INTO users (id, created_at) VALUES ($1, $2)",
    user_id, created_at
)
```

❌ **Bad** (naive datetime):
```python
# Deprecated! Don't use utcnow()
created_at = datetime.utcnow()

# Naive datetime (no timezone)
created_at = datetime.now()
```

### 5. Batch Operations

✅ **Good** (batch insert):
```python
# Efficient batch insert
values = [
    ("user-1", "user1@example.com"),
    ("user-2", "user2@example.com"),
    ("user-3", "user3@example.com")
]

await db.execute("""
    INSERT INTO users (id, email)
    SELECT * FROM UNNEST($1::uuid[], $2::text[])
""", [v[0] for v in values], [v[1] for v in values])
```

❌ **Bad** (loop inserts):
```python
# Many round-trips!
for user_id, email in users:
    await db.execute(
        "INSERT INTO users (id, email) VALUES ($1, $2)",
        user_id, email
    )
```

## Troubleshooting

### Pool Exhaustion

**Symptoms**: `asyncio.TimeoutError` on acquire, slow response times

**Diagnosis**:
```python
health = await db.health_check()
print(health["pool_info"])
```

**Solutions**:
1. Increase `PG_POOL_MAX_SIZE`
2. Review long-running transactions
3. Add connection pooling at application layer
4. Scale horizontally (more workers)

### Deadlocks

**Symptoms**: `deadlock detected` in logs, transaction retries

**Diagnosis**:
```sql
-- Check for locks
SELECT * FROM pg_locks WHERE NOT granted;

-- Check blocking queries
SELECT pid, query FROM pg_stat_activity WHERE wait_event_type = 'Lock';
```

**Solutions**:
1. Acquire locks in consistent order
2. Use shorter transactions
3. Increase `pg_client` deadlock retry attempts
4. Add row-level locking (`SELECT ... FOR UPDATE`)

### Slow Queries

**Symptoms**: High latency, slow query warnings

**Diagnosis**:
```sql
-- Enable slow query log
ALTER SYSTEM SET log_min_duration_statement = '1000';  -- 1 second
SELECT pg_reload_conf();

-- Check slow queries
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**Solutions**:
1. Add indexes for common queries
2. Review query plans (`EXPLAIN ANALYZE`)
3. Denormalize data (reduce joins)
4. Use materialized views for complex queries

### Transaction Timeout

**Symptoms**: `canceling statement due to user request`

**Diagnosis**:
```python
# Check command timeout
print(f"Timeout: {os.getenv('PG_COMMAND_TIMEOUT_SEC')}s")
```

**Solutions**:
1. Increase `PG_COMMAND_TIMEOUT_SEC`
2. Split large transactions
3. Review slow operations in transaction
4. Use async operations outside transaction

## Related Documentation

- **Circuit Breaker**: See `CIRCUIT_BREAKER_GUIDE.md`
- **CQRS Architecture**: See `docs/cqrs.md`
- **Event Sourcing**: See `docs/event_store_architecture.md`
- **SYNC Projections**: See `docs/README_SYNC_PROJECTIONS.md`

## Summary

The PostgreSQL client provides a robust, high-performance database layer for TradeCore:

- **Multi-database** support (main + VB)
- **Connection pooling** with health monitoring
- **Circuit breakers** and retry logic
- **Transaction context** with ContextVar pattern
- **SYNC projections** with 2s timeout
- **Granian multi-worker** safety with distributed locks

**Key takeaway**: Use `db.fetch()` for main database, `vb_db.fetch()` for VB database, always use transactions for multi-step operations, keep transactions short, and monitor pool usage to prevent exhaustion.
