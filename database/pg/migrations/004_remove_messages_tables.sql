-- =============================================================================
-- File: database/pg/migrations/004_remove_messages_tables.sql
-- Description: Remove messages tables (Discord pattern - messages in ScyllaDB)
-- =============================================================================
--
-- IMPORTANT: This migration removes PostgreSQL message storage.
-- Messages are now stored in ScyllaDB following Discord's architecture.
--
-- Before running this migration, ensure:
-- 1. ScyllaDB schema is deployed (database/scylla/wellwon_scylla.cql)
-- 2. All existing messages have been migrated to ScyllaDB (if needed)
-- 3. Backend code no longer references PostgreSQL messages table
--
-- This is a destructive migration - data in messages/message_reads will be lost.
-- =============================================================================

-- Remove message read status table (now tracked in ScyllaDB message_read_positions)
DROP TABLE IF EXISTS public.message_reads CASCADE;

-- Remove messages table (now stored in ScyllaDB)
DROP TABLE IF EXISTS public.messages CASCADE;

-- =============================================================================
-- The following indexes were on the dropped tables, CASCADE should handle them
-- but we explicitly drop them for clarity in case of partial state
-- =============================================================================

-- Messages indexes (may already be dropped by CASCADE)
DROP INDEX IF EXISTS idx_messages_chat_id;
DROP INDEX IF EXISTS idx_messages_sender_id;
DROP INDEX IF EXISTS idx_messages_chat_created_at;
DROP INDEX IF EXISTS idx_messages_reply_to;
DROP INDEX IF EXISTS idx_messages_telegram;
DROP INDEX IF EXISTS idx_messages_content_search;

-- Message reads indexes (may already be dropped by CASCADE)
DROP INDEX IF EXISTS idx_message_reads_message_id;
DROP INDEX IF EXISTS idx_message_reads_user_id;

-- =============================================================================
-- Verification
-- =============================================================================
-- Run after migration to verify tables are removed:
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public' AND table_name IN ('messages', 'message_reads');
-- (Should return 0 rows)

-- =============================================================================
-- EOF
-- =============================================================================
