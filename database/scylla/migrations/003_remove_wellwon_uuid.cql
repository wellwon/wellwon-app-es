-- =============================================================================
-- Migration: 003_remove_wellwon_uuid.cql
-- Description: Remove wellwon_uuid (switch to server-generated Snowflake IDs)
-- =============================================================================
-- Refactoring to Industry Standard Pattern (Discord/Slack):
-- - Server generates Snowflake ID (timestamp + worker_id + sequence)
-- - Snowflake ID is THE permanent message ID
-- - Client uses temp IDs for optimistic UI, reconciles with Snowflake
-- - No UUID mapping needed - frontend uses Snowflake directly after reconciliation
-- =============================================================================
-- Version: 3.0.0
-- Date: 2025-12-05
-- =============================================================================

USE wellwon_scylla;

-- 1. Drop the UUID mapping table (no longer needed)
DROP TABLE IF EXISTS wellwon_uuid_mapping;

-- 2. Remove wellwon_uuid column from messages table
-- Note: ScyllaDB allows dropping columns, data in this column will be deleted
ALTER TABLE messages DROP wellwon_uuid;

-- =============================================================================
-- Verify migration:
-- DESCRIBE TABLE messages;
-- SELECT table_name FROM system_schema.tables WHERE keyspace_name = 'wellwon_scylla';
-- =============================================================================
