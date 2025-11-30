# ScyllaDB Migrations

This directory contains ScyllaDB/CQL migration files for the WellWon messaging system.

## Migration Strategy

Unlike PostgreSQL which has robust migration tools (Alembic, Flyway), ScyllaDB migrations
are typically managed manually. We follow these conventions:

### File Naming

```
{version}_{description}.cql
```

Examples:
- `001_initial_schema.cql`
- `002_add_message_mentions.cql`
- `003_add_message_threads.cql`

### Migration Tracking

We track applied migrations in a dedicated table:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    description text,
    applied_at timestamp,
    checksum text
);
```

### Running Migrations

**Development:**
```bash
# Run single migration
cqlsh -f migrations/001_initial_schema.cql

# Or via Docker
docker exec -i scylladb cqlsh < migrations/001_initial_schema.cql
```

**Production:**
```bash
# Use the migration runner script
python -m app.infra.persistence.scylladb.migrate --target 001
```

## Migration Best Practices

### 1. Idempotent Statements

Always use `IF NOT EXISTS` and `IF EXISTS`:
```sql
CREATE TABLE IF NOT EXISTS messages (...);
DROP TABLE IF EXISTS old_table;
```

### 2. No Breaking Changes

ScyllaDB doesn't support many ALTER operations. Plan schema carefully:
- Can ADD columns
- Cannot DROP columns (mark as deprecated instead)
- Cannot change PRIMARY KEY
- Cannot change column types

### 3. Materialized Views

MVs are tied to base table. Changes require:
1. Drop MV
2. Modify base table
3. Recreate MV

### 4. Testing

Test migrations on a separate keyspace first:
```sql
CREATE KEYSPACE wellwon_scylla_test WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};
```

## Current Schema Version

| Version | Description | Date |
|---------|-------------|------|
| 001 | Initial schema (messages, reactions, sync) | 2025-11-30 |

## Rollback Strategy

ScyllaDB doesn't support transactions for DDL. Rollbacks are manual:

1. Create backup of affected tables
2. Apply reverse migration
3. Verify data integrity

For production, always test migrations on staging first.
