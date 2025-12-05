# WellWon Platform - Multi-Database Setup Guide

## Overview

WellWon Platform now supports multiple PostgreSQL databases for data isolation and independent scaling. The current setup includes:

- **Main Database (`wellwon`)**: Transactional data, user accounts, companies, Event Sourcing infrastructure
- **Reference Database (`wellwon_reference`)**: Declarant/Customs reference data, forms, and static lookups

## Architecture Benefits

### 1. Data Isolation
- Transactional vs reference data separation
- Independent backup/recovery policies
- Clear ownership boundaries

### 2. Performance Optimization
- Reference database: Read-heavy workload (smaller connection pool)
- Main database: Read/write workload (larger connection pool)
- Independent query optimization strategies

### 3. Scalability
- Future: Shard reference database by region
- Future: Read replicas for reference data
- Easy to add more databases (analytics, reporting, etc.)

### 4. Security
- Fine-grained access control per database
- Isolation of sensitive vs public data

## Quick Start

### Step 1: Create Reference Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE wellwon_reference;

# Grant access
GRANT ALL PRIVILEGES ON DATABASE wellwon_reference TO wellwon;

# Exit
\q
```

### Step 2: Run Schema

```bash
# Apply schema
psql -U wellwon -d wellwon_reference -f database/pg/wellwon_reference.sql
```

### Step 3: Configure Environment

Add to `.env`:

```bash
# Reference Database
POSTGRES_REFERENCE_DSN=postgresql://wellwon:password@localhost/wellwon_reference

# Optional: Override pool sizes (defaults: min=10, max=50)
PG_REFERENCE_POOL_MIN_SIZE=10
PG_REFERENCE_POOL_MAX_SIZE=50
```

### Step 4: Restart Application

```bash
python -m app.server
```

You should see:

```
[STARTUP] Main database pool initialized
[STARTUP] Reference database pool initialized
```

## Configuration Reference

### Database Enum

Located in `app/config/pg_client_config.py`:

```python
class Database(str, Enum):
    """Database identifiers for multi-database support"""
    MAIN = "main"
    REFERENCE = "reference"
```

### PostgresConfig

```python
class PostgresConfig(BaseConfig):
    # Connection strings
    main_dsn: Optional[str] = Field(alias="POSTGRES_DSN")
    reference_dsn: Optional[str] = Field(alias="POSTGRES_REFERENCE_DSN")

    # Pool configuration (main database)
    pool_min_size: int = 20
    pool_max_size: int = 100

    # Pool configuration (reference database - smaller)
    reference_pool_min_size: int = 10
    reference_pool_max_size: int = 50
```

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `POSTGRES_DSN` | Main database connection string | Required |
| `POSTGRES_REFERENCE_DSN` | Reference database connection string | Optional |
| `PG_POOL_MIN_SIZE` | Main database min connections | 20 |
| `PG_POOL_MAX_SIZE` | Main database max connections | 100 |
| `PG_REFERENCE_POOL_MIN_SIZE` | Reference database min connections | 10 |
| `PG_REFERENCE_POOL_MAX_SIZE` | Reference database max connections | 50 |

## Usage Examples

### Query Reference Database

```python
from app.infra.persistence.pg_client import fetch_for_db
from app.config.pg_client_config import Database

# Get all customs offices
customs = await fetch_for_db(
    "SELECT * FROM dc_customs WHERE is_active = TRUE",
    database=Database.REFERENCE
)

# Get form definition
form_def = await fetchrow_for_db(
    "SELECT * FROM dc_form_definitions WHERE document_mode_id = $1",
    "1002007E",
    database=Database.REFERENCE
)
```

### Transaction in Reference Database

```python
from app.infra.persistence.pg_client import transaction_for_db
from app.config.pg_client_config import Database

async with transaction_for_db(database=Database.REFERENCE) as conn:
    # All queries in this block use the same connection
    await conn.execute(
        "INSERT INTO dc_customs (kontur_id, code, short_name) VALUES ($1, $2, $3)",
        "12345", "10000000", "Moscow Customs"
    )
    await conn.execute(
        "INSERT INTO dc_form_sync_history (sync_type, status) VALUES ($1, $2)",
        "single", "success"
    )
    # Automatic commit on context exit (or rollback on exception)
```

### Create Read Repository

```python
# app/infra/read_repos/declarant_read_repo.py
from app.infra.persistence.pg_client import fetch_for_db, fetchrow_for_db
from app.config.pg_client_config import Database

class DeclarantReadRepo:
    """Read repository for Declarant/Customs domain"""

    async def get_form_definition(self, document_mode_id: str):
        """Get form definition by document_mode_id"""
        return await fetchrow_for_db(
            """
            SELECT id, document_mode_id, gf_code, type_name, fields, default_values
            FROM dc_form_definitions
            WHERE document_mode_id = $1 AND is_active = TRUE
            """,
            document_mode_id,
            database=Database.REFERENCE
        )

    async def get_customs_list(self, search: str = None):
        """Get list of customs offices"""
        if search:
            return await fetch_for_db(
                """
                SELECT id, code, short_name, full_name
                FROM dc_customs
                WHERE is_active = TRUE
                  AND short_name ILIKE $1
                ORDER BY short_name
                """,
                f"%{search}%",
                database=Database.REFERENCE
            )
        else:
            return await fetch_for_db(
                """
                SELECT id, code, short_name, full_name
                FROM dc_customs
                WHERE is_active = TRUE
                ORDER BY short_name
                """,
                database=Database.REFERENCE
            )

    async def get_declaration_types(self):
        """Get all declaration types"""
        return await fetch_for_db(
            """
            SELECT id, kontur_id, description
            FROM dc_declaration_types
            WHERE is_active = TRUE
            ORDER BY kontur_id
            """,
            database=Database.REFERENCE
        )
```

## Adding More Databases

### Step 1: Add to Database Enum

Edit `app/config/pg_client_config.py`:

```python
class Database(str, Enum):
    MAIN = "main"
    REFERENCE = "reference"
    ANALYTICS = "analytics"  # NEW
```

### Step 2: Add Configuration

In `PostgresConfig` class:

```python
# Connection string
analytics_dsn: Optional[str] = Field(
    default=None,
    alias="POSTGRES_ANALYTICS_DSN"
)

# Pool configuration
analytics_pool_min_size: int = Field(default=5)
analytics_pool_max_size: int = Field(default=20)

# Pool property
@property
def analytics_pool(self) -> PoolConfig:
    return PoolConfig(
        min_size=self.analytics_pool_min_size,
        max_size=self.analytics_pool_max_size,
        # ... other settings
    )
```

### Step 3: Add Environment Variable

In `.env`:

```bash
POSTGRES_ANALYTICS_DSN=postgresql://wellwon:password@localhost/wellwon_analytics
```

### Step 4: Use It

```python
from app.config.pg_client_config import Database

# Query analytics database
data = await fetch_for_db(
    "SELECT * FROM analytics_table",
    database=Database.ANALYTICS
)
```

## Database Schema

### wellwon_reference Tables (18 total)

#### Form System Tables (9)
1. **dc_json_templates** - JSON form templates from Kontur API
2. **dc_form_definitions** - Preprocessed form definitions
3. **dc_field_labels_ru** - Russian field labels
4. **dc_form_sections** - Custom UI sections
5. **dc_form_sync_history** - Form sync audit trail
6. **dc_form_templates** - Form Builder templates
7. **dc_form_template_versions** - Template version snapshots
8. **dc_form_template_drafts** - Auto-save drafts
9. **dc_form_definition_versions** - Definition version snapshots

#### Reference Data Tables (8)
10. **dc_customs** - Customs offices (from Kontur API)
11. **dc_declaration_types** - Declaration types (IM, EK, PI, etc.)
12. **dc_procedures** - Customs procedures by declaration type
13. **dc_packaging_groups** - Packaging groups
14. **dc_currencies** - Currency codes (numeric + alpha)
15. **dc_enterprise_categories** - Enterprise categories
16. **dc_measurement_units** - Measurement units
17. **dc_document_types** - Document types with ED-document support

## Connection Pool Sizing

### Recommended Sizing

```
Main Database:
- Min: 20 connections
- Max: 100 connections
- Workload: 70% reads, 30% writes
- Target: <10ms query latency

Reference Database:
- Min: 10 connections
- Max: 50 connections
- Workload: 95% reads, 5% writes
- Target: <5ms query latency

Total Connections per Worker:
- Main: 100
- Reference: 50
- Total: 150

With 4 Workers:
- Main: 400 connections
- Reference: 200 connections
- Total: 600 connections

PostgreSQL max_connections: 650+ (with headroom)
```

### Auto-Scaling

The system automatically scales pool sizes based on:
- Number of workers detected
- Server type (Granian vs dev server)
- Available CPU cores
- Max total connections limit

## Monitoring

### Health Checks

```python
from app.infra.persistence.pg_client import health_check_for_db
from app.config.pg_client_config import Database

# Check main database
main_health = await health_check_for_db(Database.MAIN)
print(f"Main DB: {main_health}")

# Check reference database
ref_health = await health_check_for_db(Database.REFERENCE)
print(f"Reference DB: {ref_health}")
```

### Metrics

Monitor these metrics per database:
- **Pool utilization**: Active connections / Max connections
- **Pool exhaustion events**: When pool hits max size
- **Slow queries**: Queries exceeding threshold (default: 1000ms)
- **Slow pool acquisition**: Waiting for connection (default: 500ms)
- **Circuit breaker state**: CLOSED, OPEN, HALF_OPEN

### Logs

Look for these log messages:

```
[POOL EXHAUSTION] reference at 48/50 connections
[SLOW QUERY] reference took 1234ms: SELECT * FROM dc_form_definitions...
[SLOW POOL] reference acquisition took 789ms
[CIRCUIT BREAKER] reference state changed: CLOSED -> OPEN
```

## Troubleshooting

### Problem: "DSN not configured for database 'reference'"

**Solution:** Add `POSTGRES_REFERENCE_DSN` to `.env`

```bash
POSTGRES_REFERENCE_DSN=postgresql://wellwon:password@localhost/wellwon_reference
```

### Problem: "Pool exhaustion" warnings

**Solution:** Increase pool size or reduce concurrent queries

```bash
# In .env
PG_REFERENCE_POOL_MAX_SIZE=100
```

### Problem: Connection refused

**Solution:** Check database exists and is accessible

```bash
# Test connection
psql -U wellwon -d wellwon_reference -c "SELECT 1"
```

### Problem: Slow queries

**Solution:** Add indexes, optimize queries, or increase resources

```sql
-- Check slow queries
SELECT * FROM pg_stat_statements
WHERE dbname = 'wellwon_reference'
ORDER BY total_exec_time DESC
LIMIT 10;
```

## Best Practices

### 1. Use Explicit Database Parameter

```python
# Good - explicit and clear
data = await fetch_for_db("SELECT ...", database=Database.REFERENCE)

# Bad - relies on default (Database.MAIN)
data = await fetch_for_db("SELECT ...")  # Which database?
```

### 2. No Cross-Database Transactions

```python
# ❌ WRONG - Cannot do this
async with transaction_for_db() as conn:
    await fetch_for_db("INSERT INTO main.users...", database=Database.MAIN)
    await fetch_for_db("INSERT INTO reference.forms...", database=Database.REFERENCE)
    # These are TWO databases = TWO connections = NO atomic transaction

# ✅ CORRECT - Use Saga pattern for cross-database operations
class SyncFormDataSaga:
    async def execute(self):
        # Step 1: Write to reference database
        form_id = await self.create_form_in_reference()

        # Step 2: Write to main database
        try:
            await self.update_user_forms_in_main(form_id)
        except Exception:
            # Compensation: Rollback reference database
            await self.delete_form_from_reference(form_id)
            raise
```

### 3. Use Read Repositories

Encapsulate database access in repository classes:

```python
# Good
class DeclarantReadRepo:
    async def get_customs_list(self):
        return await fetch_for_db(..., database=Database.REFERENCE)

# Usage
repo = DeclarantReadRepo()
customs = await repo.get_customs_list()
```

### 4. Circuit Breakers Per Database

Circuit breakers are automatically isolated per database. Reference database failure won't affect main database.

### 5. Monitor Pool Utilization

Set up alerts for:
- Pool exhaustion > 90%
- Slow queries > 1000ms
- Circuit breaker state changes

## Security

### 1. Separate Credentials

Use different passwords for each database:

```bash
POSTGRES_DSN=postgresql://wellwon:mainpass@localhost/wellwon
POSTGRES_REFERENCE_DSN=postgresql://wellwon:refpass@localhost/wellwon_reference
```

### 2. Least Privilege

Reference database should be read-only for most application users:

```sql
-- Create read-only role
CREATE ROLE wellwon_reference_readonly;
GRANT CONNECT ON DATABASE wellwon_reference TO wellwon_reference_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO wellwon_reference_readonly;
```

### 3. Connection Encryption

Use SSL for production:

```bash
POSTGRES_REFERENCE_DSN=postgresql://wellwon:pass@host/wellwon_reference?sslmode=require
```

## Reference Database Schema (Customs Tables)

### Customs Reference Data

The reference database contains static and semi-static data for the Customs domain. This data rarely changes and is shared across all declarations.

#### Customs Reference Tables (7 core tables)

| Table | Purpose | Update Frequency | Cache TTL |
|-------|---------|------------------|-----------|
| `dc_json_templates` | Form templates from Kontur API (18003, 18104, etc.) | Quarterly | 24 hours |
| `dc_form_definitions` | Preprocessed form definitions with field schemas | Quarterly | 24 hours |
| `dc_procedures` | Customs procedures (40 = import, 10 = export, etc.) | Yearly | 24 hours |
| `dc_customs` | Customs offices (8-digit codes, names, addresses) | Quarterly | 24 hours |
| `dc_declaration_types` | Declaration types (IM, EX, TR, TI, TE) | Rarely | 24 hours |
| `dc_document_types` | Document types (invoice, packing list, certificate) | Yearly | 24 hours |
| `dc_common_orgs` | Common organizations (contractors) synced from Kontur | Weekly | 1 hour |

#### Table Details

**dc_json_templates** (Form Templates)
```sql
CREATE TABLE dc_json_templates (
    id SERIAL PRIMARY KEY,
    kontur_id VARCHAR(50) UNIQUE,        -- Kontur template ID
    document_mode_id VARCHAR(20) NOT NULL,  -- e.g., "1006107E"
    gf_code VARCHAR(20) NOT NULL,        -- e.g., "18003"
    type_name VARCHAR(100) NOT NULL,     -- "ДТ" (Declaration)
    template_json JSONB,                 -- Full template from Kontur API
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Use Case:** Query available form templates for declaration creation

---

**dc_form_definitions** (Preprocessed Forms)
```sql
CREATE TABLE dc_form_definitions (
    id SERIAL PRIMARY KEY,
    document_mode_id VARCHAR(20) NOT NULL,
    gf_code VARCHAR(20),
    type_name VARCHAR(100),
    fields JSONB,                        -- Preprocessed field list
    default_values JSONB,                -- Default field values
    validation_rules JSONB,              -- Validation rules
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Use Case:** Validate form data before submission to Kontur API

---

**dc_procedures** (Customs Procedures)
```sql
CREATE TABLE dc_procedures (
    id SERIAL PRIMARY KEY,
    kontur_id VARCHAR(50),
    code VARCHAR(10) NOT NULL,           -- "40", "10", etc.
    name VARCHAR(500) NOT NULL,
    declaration_type_id INTEGER,         -- FK to dc_declaration_types
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Common Procedures:**
- `40` - Release for domestic consumption (import)
- `10` - Export
- `51` - Temporary import for up to 2 years

---

**dc_customs** (Customs Offices)
```sql
CREATE TABLE dc_customs (
    id SERIAL PRIMARY KEY,
    kontur_id VARCHAR(50) UNIQUE,
    code VARCHAR(20) UNIQUE NOT NULL,    -- 8-digit code (e.g., "10702010")
    short_name VARCHAR(500),
    full_name VARCHAR(1000),
    address TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Example:**
- Code: `10702010` - Московская таможня (Moscow Customs)
- Code: `10714000` - Шереметьевская таможня (Sheremetyevo Airport Customs)

---

**dc_declaration_types** (Declaration Types)
```sql
CREATE TABLE dc_declaration_types (
    id SERIAL PRIMARY KEY,
    kontur_id VARCHAR(50) UNIQUE,
    code VARCHAR(10) UNIQUE NOT NULL,    -- "IM", "EX", "TR", etc.
    description VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Types:**
- `IM` - Import
- `EX` - Export
- `TR` - Transit
- `TI` - Temporary import
- `TE` - Temporary export

---

**dc_document_types** (Document Types)
```sql
CREATE TABLE dc_document_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    ed_document BOOLEAN DEFAULT false,   -- Electronic document flag
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Common Types:**
- `INVOICE` - Commercial invoice
- `PACKING_LIST` - Packing list
- `CERTIFICATE` - Certificate of origin
- `CONTRACT` - Foreign trade contract

---

**dc_common_orgs** (Common Organizations)
```sql
CREATE TABLE dc_common_orgs (
    id SERIAL PRIMARY KEY,
    kontur_id VARCHAR(50) UNIQUE,
    full_name VARCHAR(1000) NOT NULL,
    short_name VARCHAR(500),
    inn VARCHAR(20),                     -- Russian INN (tax ID)
    address TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Use Case:** Pre-populate contractor/supplier data in declarations

**Data Source:** Synced weekly from Kontur API (`list_common_orgs()`)

---

## Event Enrichment Pattern

### What is Event Enrichment?

**Event enrichment** is a pattern where command handlers query reference data BEFORE emitting events, and include that data in the event payload. This makes events:
- **Complete historical record** - Events contain all context needed
- **Saga-ready** - Sagas don't need QueryBus to process events
- **Projector-friendly** - Projectors can update read models without additional queries

### Pattern Flow

```python
# In Command Handler:
# 1. Query reference DB BEFORE emitting event
customs_office = await query_bus.query(
    GetCustomsOfficeQuery(code="10702010")
)  # wellwon_reference DB

# 2. Emit event with enriched data
event = DeclarationCreated(
    customs_office_code="10702010",
    customs_office_name=customs_office.name  # Enrichment!
)

# In Projector:
# 3. Use enriched data directly (no additional queries needed)
await db.execute(
    "INSERT INTO customs_declarations (customs_office_name) VALUES ($1)",
    event.customs_office_name  # Already enriched!
)
```

### Without Enrichment (❌ BAD)

```python
# Command Handler emits minimal event
event = DeclarationCreated(
    customs_office_code="10702010"
    # Missing: customs_office_name
)

# Projector must query reference DB (slower, more complex)
@sync_projection("domain", "DeclarationCreated")
async def project_declaration_created(self, event: DeclarationCreated):
    # Must query reference DB to get name
    customs_office = await self.query_bus.query(
        GetCustomsOfficeQuery(code=event.customs_office_code)
    )

    await self.db.execute(
        "INSERT INTO customs_declarations (customs_office_name) VALUES ($1)",
        customs_office.name  # Extra query needed
    )
```

**Problems:**
- Projector needs QueryBus dependency
- Additional query on every event
- Slower projection
- Projector logic more complex

---

### With Enrichment (✅ GOOD)

```python
# Command Handler enriches event
class CreateDeclarationHandler:
    async def handle(self, command: CreateDeclarationCommand):
        # 1. Query reference data
        form_template = await self.query_bus.query(
            GetFormTemplateQuery(
                document_mode_id=command.document_mode_id
            )
        )  # wellwon_reference DB

        customs_office = await self.query_bus.query(
            GetCustomsOfficeQuery(
                office_code=command.customs_office_code
            )
        )  # wellwon_reference DB

        # 2. Load aggregate
        aggregate = await self.load_aggregate(command.declaration_id)

        # 3. Emit event with enriched data
        aggregate.create_new_declaration(
            form_name=form_template.name,              # Enriched
            customs_office_name=customs_office.name,   # Enriched
            customs_office_code=command.customs_office_code
        )

        # 4. Publish events
        await self.publish_events(aggregate)


# Projector uses enriched data (simple!)
@sync_projection("domain", "DeclarationCreated")
async def project_declaration_created(self, event: DeclarationCreated):
    # No additional queries needed!
    await self.db.execute(
        """
        INSERT INTO customs_declarations (
            id, form_name, customs_office_code, customs_office_name
        ) VALUES ($1, $2, $3, $4)
        """,
        event.declaration_id,
        event.form_name,                    # From event
        event.customs_office_code,          # From event
        event.customs_office_name           # From event (enriched!)
    )
```

**Benefits:**
- Projector is simple (no QueryBus dependency)
- No additional queries (faster)
- Events are complete historical record
- Saga-ready (Sagas can use enriched data)

---

### Example: Full Event with Enrichment

```python
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

@domain_event(category="domain")
class DeclarationCreated(BaseEvent):
    """Event emitted when customs declaration is created"""

    # Core data
    declaration_id: UUID
    company_id: UUID
    user_id: UUID

    # Form data (from command)
    gf_code: str                        # "18003"
    document_mode_id: str               # "1006107E"
    declaration_type: str               # "IM"
    customs_procedure_code: str         # "40"
    customs_office_code: str            # "10702010"

    # Enriched data (from reference DB queries)
    form_name: str                      # "ДТ (импорт/экспорт)"
    declaration_type_name: str          # "Импорт"
    customs_procedure_name: str         # "Выпуск для внутреннего потребления"
    customs_office_name: str            # "Московская таможня"
    company_name: str                   # From UserAccount domain
    user_username: str                  # From UserAccount domain

    # Metadata
    created_at: datetime
```

**Result:**
- Event contains ALL context needed
- Projector doesn't need any additional queries
- Event log is complete historical record
- Anyone can understand the event without querying other tables

---

## Query Patterns for Dual Database

### Pattern 1: Reference Data in Command Handlers (Event Enrichment)

**Use Case:** Enrich events with human-readable reference data

```python
from app.customs.queries import GetFormTemplateQuery, GetCustomsOfficeQuery

class CreateDeclarationHandler:
    async def handle(self, command: CreateDeclarationCommand):
        # Query reference DB for enrichment
        form_template = await self.query_bus.query(
            GetFormTemplateQuery(document_mode_id=command.document_mode_id)
        )  # wellwon_reference DB

        customs_office = await self.query_bus.query(
            GetCustomsOfficeQuery(office_code=command.customs_office_code)
        )  # wellwon_reference DB

        # Use data to enrich event
        aggregate.create_new_declaration(
            form_name=form_template.name,              # Enriched
            customs_office_name=customs_office.name    # Enriched
        )
```

**Why:** Events become complete historical record

---

### Pattern 2: Reference Data in Query Handlers

**Use Case:** User queries for reference data (forms, customs offices, procedures)

```python
from app.config.pg_client_config import Database
from app.infra.persistence.pg_client import fetch_for_db

class GetFormTemplateQueryHandler:
    async def handle(self, query: GetFormTemplateQuery):
        # Query reference DB
        result = await fetchrow_for_db(
            """
            SELECT
                document_mode_id,
                gf_code,
                type_name,
                fields,
                validation_rules
            FROM dc_form_definitions
            WHERE document_mode_id = $1 AND is_active = TRUE
            """,
            query.document_mode_id,
            database=Database.REFERENCE  # wellwon_reference DB
        )

        if not result:
            return None

        return FormTemplate(**result)
```

**Caching:** Reference queries cached 24 hours (data rarely changes)

```python
# With caching
from app.infra.cache import get_cache

class GetFormTemplateQueryHandler:
    async def handle(self, query: GetFormTemplateQuery):
        cache_key = f"form_template:{query.document_mode_id}"

        # Check cache first
        cached = await get_cache().get(cache_key)
        if cached:
            return FormTemplate.parse_raw(cached)

        # Query reference DB
        result = await fetchrow_for_db(...)
        template = FormTemplate(**result)

        # Cache for 24 hours
        await get_cache().setex(
            cache_key,
            86400,  # 24 hours
            template.json()
        )

        return template
```

---

### Pattern 3: Avoid Cross-Database Joins

Cross-database joins are **slow**, **complex**, and **not atomic**. Avoid them!

#### ❌ BAD (Slow SQL Join)

```sql
-- Joining across databases is slow and complex
SELECT
    d.id,
    d.declaration_number,
    c.name as customs_office_name  -- From reference DB
FROM wellwon.customs_declarations d
JOIN wellwon_reference.dc_customs c ON d.customs_office_code = c.code
WHERE d.company_id = $1;
```

**Problems:**
- Slow (cross-database join)
- Complex query plan
- Not supported by all PostgreSQL drivers
- Cannot use indexes efficiently

---

#### ✅ GOOD (Event Enrichment)

```python
# Enrich event during command handling
class CreateDeclarationHandler:
    async def handle(self, command: CreateDeclarationCommand):
        # Query reference DB
        customs_office = await self.query_bus.query(
            GetCustomsOfficeQuery(code=command.customs_office_code)
        )

        # Emit event with enriched data
        event = DeclarationCreated(
            customs_office_code=command.customs_office_code,
            customs_office_name=customs_office.name  # Already included!
        )

        # Projector writes to main DB (no join needed)
        # customs_office_name is already in the event
```

**Result:** Main DB has denormalized `customs_office_name` column (fast queries, no joins)

---

#### ✅ GOOD (Application-Level Join)

If you must join data from both databases, do it in Python:

```python
from app.config.pg_client_config import Database

class ListDeclarationsWithOfficeNamesQuery:
    async def handle(self, query):
        # Step 1: Query main DB
        declarations = await fetch_for_db(
            """
            SELECT id, declaration_number, customs_office_code, created_at
            FROM customs_declarations
            WHERE company_id = $1
            """,
            query.company_id,
            database=Database.MAIN
        )

        # Step 2: Query reference DB separately
        customs_offices = await fetch_for_db(
            """
            SELECT code, short_name
            FROM dc_customs
            WHERE is_active = TRUE
            """,
            database=Database.REFERENCE
        )

        # Step 3: Join in Python (create lookup map)
        offices_map = {o["code"]: o["short_name"] for o in customs_offices}

        # Step 4: Enrich declarations
        for d in declarations:
            d["customs_office_name"] = offices_map.get(
                d["customs_office_code"],
                "Unknown"
            )

        return declarations
```

**Benefits:**
- No cross-database SQL join
- Can cache `customs_offices` lookup map
- Clear separation of concerns
- Works with any database driver

---

### Pattern 4: Avoid Cross-Database Transactions

**Important:** You CANNOT have atomic transactions across two databases!

#### ❌ WRONG (Does Not Work)

```python
# This does NOT work - two databases = two connections
async with transaction_for_db() as conn:
    # Main DB
    await execute_for_db(
        "INSERT INTO customs_declarations (...) VALUES (...)",
        database=Database.MAIN
    )

    # Reference DB (DIFFERENT connection!)
    await execute_for_db(
        "INSERT INTO dc_common_orgs (...) VALUES (...)",
        database=Database.REFERENCE
    )

    # These are TWO separate transactions!
    # If second fails, first is already committed
```

**Problem:** No atomic commit across databases

---

#### ✅ CORRECT (Use Saga Pattern)

For cross-database operations, use Saga pattern with compensation:

```python
class SyncOrganizationSaga:
    """Saga for syncing organization across databases"""

    async def execute(self, org_data):
        # Step 1: Create in reference DB
        try:
            ref_org_id = await self.create_in_reference(org_data)
            self.saga_data["ref_org_id"] = ref_org_id
        except Exception as e:
            # No compensation needed (first step)
            raise

        # Step 2: Create in main DB
        try:
            main_org_id = await self.create_in_main(org_data, ref_org_id)
            self.saga_data["main_org_id"] = main_org_id
        except Exception as e:
            # Compensation: Delete from reference DB
            await self.compensate_reference(ref_org_id)
            raise

        return {"ref_org_id": ref_org_id, "main_org_id": main_org_id}

    async def create_in_reference(self, org_data):
        """Create organization in reference DB"""
        result = await execute_for_db(
            """
            INSERT INTO dc_common_orgs (full_name, inn, address)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            org_data.full_name,
            org_data.inn,
            org_data.address,
            database=Database.REFERENCE
        )
        return result["id"]

    async def create_in_main(self, org_data, ref_org_id):
        """Create organization in main DB"""
        result = await execute_for_db(
            """
            INSERT INTO companies (name, inn, reference_org_id)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            org_data.full_name,
            org_data.inn,
            ref_org_id,
            database=Database.MAIN
        )
        return result["id"]

    async def compensate_reference(self, ref_org_id):
        """Compensation: Delete from reference DB"""
        await execute_for_db(
            "DELETE FROM dc_common_orgs WHERE id = $1",
            ref_org_id,
            database=Database.REFERENCE
        )
```

**Benefits:**
- Explicit compensation logic
- Clear step-by-step flow
- Audit trail (Saga events)
- Can retry failed steps

---

## Migration Strategy for Reference Tables

### Adding New Reference Table

Follow these steps to add a new reference table to `wellwon_reference`:

#### Step 1: Create Migration SQL

```sql
-- database/pg/migrations/ref_006_new_reference_table.sql
-- Target: wellwon_reference

-- =====================================================================
-- Table: dc_new_reference
-- Purpose: [Describe purpose]
-- Data Source: [Kontur API / Manual / Other]
-- Update Frequency: [Weekly / Monthly / Rarely]
-- =====================================================================

CREATE TABLE dc_new_reference (
    id SERIAL PRIMARY KEY,
    kontur_id VARCHAR(50) UNIQUE,        -- If from Kontur API
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_new_reference_code ON dc_new_reference(code);
CREATE INDEX idx_new_reference_active ON dc_new_reference(is_active);

-- Comments
COMMENT ON TABLE dc_new_reference IS '[Purpose description]';
COMMENT ON COLUMN dc_new_reference.kontur_id IS 'Kontur API identifier';
COMMENT ON COLUMN dc_new_reference.code IS 'Code used in declarations';
```

#### Step 2: Apply Migration

```bash
# Apply to reference database
psql -U wellwon -d wellwon_reference -f database/pg/migrations/ref_006_new_reference_table.sql
```

#### Step 3: Create Pydantic Model

```python
# app/customs/read_models.py

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class NewReferenceOption(BaseModel):
    """Read model for new reference data"""

    id: int
    kontur_id: Optional[str] = None
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

#### Step 4: Create Query and Query Handler

```python
# app/customs/queries.py

from pydantic import BaseModel

class GetNewReferenceQuery(BaseModel):
    """Query to get new reference data"""
    code: Optional[str] = None
    is_active: bool = True


# app/customs/query_handlers/reference_query_handlers.py

from app.config.pg_client_config import Database
from app.infra.persistence.pg_client import fetch_for_db
from app.customs.read_models import NewReferenceOption

class GetNewReferenceQueryHandler:
    """Query handler for new reference data"""

    async def handle(self, query: GetNewReferenceQuery):
        # Query wellwon_reference DB
        results = await fetch_for_db(
            """
            SELECT
                id, kontur_id, code, name, description, is_active,
                created_at, updated_at
            FROM dc_new_reference
            WHERE is_active = $1
            ORDER BY name
            """,
            query.is_active,
            database=Database.REFERENCE
        )

        return [NewReferenceOption(**r) for r in results]
```

#### Step 5: Register Query Handler

```python
# app/core/startup/cqrs.py

from app.customs.query_handlers.reference_query_handlers import (
    GetNewReferenceQueryHandler
)

# Register query handler
query_bus.register_handler(
    GetNewReferenceQuery,
    GetNewReferenceQueryHandler()
)
```

#### Step 6: Use in Command Handlers (Enrichment)

```python
# app/customs/command_handlers/declaration_handlers.py

class CreateDeclarationHandler:
    async def handle(self, command: CreateDeclarationCommand):
        # Query new reference data
        reference_data = await self.query_bus.query(
            GetNewReferenceQuery(code=command.some_code)
        )

        # Enrich event with reference data
        event = DeclarationCreated(
            reference_code=command.some_code,
            reference_name=reference_data[0].name  # Enrichment!
        )

        # Publish event
        await self.publish_events([event])
```

---

### Syncing Reference Data from External APIs

Some reference data comes from external sources (Kontur API, government APIs). Use background jobs to sync periodically.

#### Example: Sync Common Organizations from Kontur

```python
# app/services/kontur_sync_service.py

from app.infra.kontur.adapter import get_kontur_adapter
from app.config.pg_client_config import Database
from app.infra.persistence.pg_client import execute_for_db
from app.config.logging_config import get_logger

log = get_logger("wellwon.services.kontur_sync")

class KonturSyncService:
    """Background service to sync reference data from Kontur API"""

    async def sync_common_organizations(self):
        """Sync common organizations from Kontur to reference DB"""

        log.info("Starting sync of common organizations from Kontur API")

        # 1. Fetch from Kontur API
        kontur_adapter = get_kontur_adapter()
        kontur_orgs = await kontur_adapter.list_common_orgs()

        log.info(f"Fetched {len(kontur_orgs)} organizations from Kontur API")

        # 2. Update reference DB (wellwon_reference)
        synced_count = 0
        for org in kontur_orgs:
            await execute_for_db(
                """
                INSERT INTO dc_common_orgs (
                    kontur_id, full_name, short_name, inn, address, is_active
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (kontur_id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    short_name = EXCLUDED.short_name,
                    inn = EXCLUDED.inn,
                    address = EXCLUDED.address,
                    is_active = EXCLUDED.is_active,
                    updated_at = NOW()
                """,
                org["id"],
                org["full_name"],
                org["short_name"],
                org["inn"],
                org.get("address"),
                True,
                database=Database.REFERENCE
            )
            synced_count += 1

        log.info(f"Synced {synced_count} common organizations to reference DB")

        return synced_count
```

#### Scheduled Execution (Weekly Sync)

```python
# app/workers/data_sync_worker.py

from app.services.kontur_sync_service import KonturSyncService
import asyncio

async def sync_kontur_reference_data():
    """Background job to sync Kontur reference data"""

    sync_service = KonturSyncService()

    while True:
        try:
            # Sync common organizations
            await sync_service.sync_common_organizations()

            # Sync customs offices
            await sync_service.sync_customs_offices()

            # Wait 7 days (weekly sync)
            await asyncio.sleep(7 * 24 * 60 * 60)

        except Exception as e:
            log.error(f"Error syncing Kontur reference data: {e}")
            # Wait 1 hour before retrying
            await asyncio.sleep(60 * 60)
```

---

## Performance Optimization

### Connection Pooling

Configure separate connection pools for main and reference databases with different sizes based on workload.

#### Recommended Pool Sizes

```python
# app/config/pg_client_config.py

class PostgresConfig(BaseConfig):
    # Main DB pool (wellwon) - High write volume
    pool_min_size: int = 10
    pool_max_size: int = 50       # Larger for write workload

    # Reference DB pool (wellwon_reference) - Read-optimized
    reference_pool_min_size: int = 5
    reference_pool_max_size: int = 20  # Smaller (mostly reads)
```

#### Pool Configuration

```python
# app/infra/persistence/postgres_connection.py

import asyncpg

# Main DB pool (wellwon)
main_pool = await asyncpg.create_pool(
    dsn=POSTGRES_DSN_MAIN,
    min_size=10,
    max_size=50,              # High write volume
    command_timeout=60,       # 60s timeout
    server_settings={
        'application_name': 'wellwon-main'
    }
)

# Reference DB pool (wellwon_reference)
ref_pool = await asyncpg.create_pool(
    dsn=POSTGRES_DSN_REFERENCE,
    min_size=5,
    max_size=20,              # Read-optimized
    command_timeout=30,       # Shorter timeout (reads are fast)
    server_settings={
        'application_name': 'wellwon-reference',
        'default_transaction_read_only': 'on'  # Read-only mode
    }
)
```

**Benefits:**
- Main DB: Larger pool for write workload
- Reference DB: Smaller pool (fewer connections needed)
- Read-only mode prevents accidental writes to reference DB
- Separate application names for monitoring

---

### Caching Strategy

Cache reference data aggressively (data rarely changes).

#### Cache TTL by Data Type

| Data Type | TTL | Rationale |
|-----------|-----|-----------|
| Form templates | 24 hours | Static (updated quarterly) |
| Customs procedures | 24 hours | Static (updated by legislation) |
| Customs offices | 24 hours | Rarely updated (quarterly) |
| Common organizations | 1 hour | Synced from Kontur API (weekly updates) |
| Document types | 24 hours | Static |
| Declaration types | 24 hours | Static |

#### Example: Cached Query Handler

```python
from app.infra.cache import get_cache
from app.config.pg_client_config import Database
from app.infra.persistence.pg_client import fetchrow_for_db

class GetFormTemplateQueryHandler:
    """Query handler with Redis caching"""

    async def handle(self, query: GetFormTemplateQuery):
        cache_key = f"form_template:{query.document_mode_id}"

        # Check Redis cache
        cached = await get_cache().get(cache_key)
        if cached:
            log.debug(f"Cache hit: {cache_key}")
            return FormTemplate.parse_raw(cached)

        log.debug(f"Cache miss: {cache_key}")

        # Query reference DB
        result = await fetchrow_for_db(
            """
            SELECT document_mode_id, gf_code, type_name, fields, validation_rules
            FROM dc_form_definitions
            WHERE document_mode_id = $1 AND is_active = TRUE
            """,
            query.document_mode_id,
            database=Database.REFERENCE
        )

        if not result:
            return None

        template = FormTemplate(**result)

        # Cache for 24 hours
        await get_cache().setex(
            cache_key,
            86400,  # 24 hours
            template.json()
        )

        return template
```

**Benefits:**
- Reduce database load (repeated queries served from cache)
- Faster response times (Redis is much faster than PostgreSQL)
- Lower connection pool usage

---

### Read Replicas (Future)

For production scaling, use read replicas for the reference database.

#### Architecture

```
┌──────────────────────────────────────────────────────┐
│ Main Database (wellwon)                              │
│                                                      │
│  ┌─────────────┐                                    │
│  │  Primary    │ (Read/Write)                       │
│  │ (Leader)    │                                    │
│  └──────┬──────┘                                    │
│         │                                           │
│         │ Replication                               │
│         ▼                                           │
│  ┌─────────────┐                                    │
│  │   Replica   │ (Read-Only)                       │
│  │ (Follower)  │ - Background jobs                 │
│  └─────────────┘                                    │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ Reference Database (wellwon_reference)                │
│                                                      │
│  ┌─────────────┐                                    │
│  │  Primary    │ (Read/Write)                       │
│  │ (Leader)    │ - Sync jobs only                  │
│  └──────┬──────┘                                    │
│         │                                           │
│         │ Replication                               │
│         ├──────────────┬──────────────┐            │
│         ▼              ▼              ▼            │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐      │
│  │Replica 1 │   │Replica 2 │   │Replica 3 │      │
│  │(API)     │   │(Jobs)    │   │(Reports) │      │
│  └──────────┘   └──────────┘   └──────────┘      │
└──────────────────────────────────────────────────────┘
```

#### Configuration

```python
# app/config/pg_client_config.py

class PostgresConfig(BaseConfig):
    # Reference DB primary (for sync jobs)
    reference_dsn: Optional[str] = Field(alias="POSTGRES_REFERENCE_DSN")

    # Reference DB replica (for API queries)
    reference_replica_dsn: Optional[str] = Field(
        alias="POSTGRES_REFERENCE_REPLICA_DSN"
    )
```

```bash
# .env
POSTGRES_REFERENCE_DSN=postgresql://wellwon:pass@reference-primary:5432/wellwon_reference
POSTGRES_REFERENCE_REPLICA_DSN=postgresql://wellwon:pass@reference-replica:5432/wellwon_reference
```

#### Usage

```python
# Query replica for API requests
customs = await fetch_for_db(
    "SELECT * FROM dc_customs WHERE is_active = TRUE",
    database=Database.REFERENCE_REPLICA  # Read from replica
)

# Write to primary (sync jobs)
await execute_for_db(
    "INSERT INTO dc_customs (...) VALUES (...)",
    database=Database.REFERENCE  # Write to primary
)
```

**Benefits:**
- Scale read capacity horizontally
- Reduce load on primary (sync jobs use separate replica)
- Higher availability (replica failover)

---

## Next Steps

1. **Implement Kontur API Client** - Sync forms from Kontur API to reference database
2. **Create Declarant Domain** - CQRS/ES domain for customs declarations
3. **Build Form Builder UI** - Frontend for creating/managing form templates
4. **Add Analytics Database** - Separate database for reporting queries
5. **Implement Read Replicas** - Scale read-heavy reference database

## Resources

- [Industry Best Practices Research](../../../docs/research/MULTI_DATABASE_RESEARCH.md)
- [PostgreSQL Configuration](app/config/pg_client_config.py)
- [PG Client Implementation](app/infra/persistence/pg_client.py)
- [Reference Schema](database/pg/wellwon_reference.sql)
