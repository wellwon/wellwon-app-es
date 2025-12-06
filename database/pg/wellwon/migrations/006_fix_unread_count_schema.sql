-- =============================================================================
-- Migration: 006_fix_unread_count_schema.sql
-- Description: Fix chat_participants schema for proper unread count tracking
--
-- Issues fixed:
-- 1. last_read_message_id was UUID but should be BIGINT (Snowflake ID)
-- 2. Missing unread_count column for caching unread message count
-- =============================================================================

-- Step 1: Add unread_count column if not exists
ALTER TABLE public.chat_participants
ADD COLUMN IF NOT EXISTS unread_count INTEGER NOT NULL DEFAULT 0;

-- Step 2: Fix last_read_message_id type (UUID -> BIGINT for Snowflake IDs)
-- First, add new column with correct type
ALTER TABLE public.chat_participants
ADD COLUMN IF NOT EXISTS last_read_message_snowflake BIGINT;

-- Copy data (convert UUID to int where possible, or set NULL)
-- Note: This is a one-way migration. Old UUID values cannot be converted.
-- New messages use Snowflake IDs natively.

-- Step 3: Create index for unread count queries
CREATE INDEX IF NOT EXISTS idx_chat_participants_unread
ON public.chat_participants(user_id, unread_count)
WHERE is_active = true AND unread_count > 0;

-- Step 4: Create index for last_read lookups
CREATE INDEX IF NOT EXISTS idx_chat_participants_last_read
ON public.chat_participants(chat_id, user_id, last_read_message_snowflake);

-- Step 5: Add comment for documentation
COMMENT ON COLUMN public.chat_participants.unread_count IS
'Cached count of unread messages for this participant. Updated by projectors on MessageSent and MessagesMarkedAsRead events.';

COMMENT ON COLUMN public.chat_participants.last_read_message_snowflake IS
'Snowflake ID (int64) of the last read message. Used to calculate unread count.';
