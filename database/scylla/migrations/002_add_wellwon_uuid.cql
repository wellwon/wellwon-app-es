-- =============================================================================
-- Migration: 002_add_wellwon_uuid.cql
-- Description: Add wellwon_uuid for frontend cache matching after logout/login
-- =============================================================================
-- Problem: Frontend generates UUID, projector converts to Snowflake for storage.
-- After logout/login, API returns Snowflake but frontend expects UUID.
-- Solution: Store original UUID alongside Snowflake ID.
-- =============================================================================
-- Version: 2.1.0
-- Date: 2025-12-05
-- =============================================================================

USE wellwon_scylla;

-- 1. Add wellwon_uuid column to messages table
ALTER TABLE messages ADD wellwon_uuid uuid;

-- 2. Create lookup table for fast UUID -> message location queries
CREATE TABLE IF NOT EXISTS wellwon_uuid_mapping (
    wellwon_uuid            uuid,
    channel_id              uuid,
    bucket                  int,
    message_id              bigint,
    created_at              timestamp,

    PRIMARY KEY (wellwon_uuid)
) WITH gc_grace_seconds = 86400
AND comment = 'Fast lookup: WellWon UUID -> ScyllaDB message';

-- =============================================================================
-- Verify migration:
-- DESCRIBE TABLE messages;
-- DESCRIBE TABLE wellwon_uuid_mapping;
-- =============================================================================
