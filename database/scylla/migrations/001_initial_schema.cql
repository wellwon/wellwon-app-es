-- =============================================================================
-- Migration: 001_initial_schema
-- Description: Initial ScyllaDB schema for WellWon messaging
-- =============================================================================
-- Date: 2025-11-30
-- Version: 2.0.0
-- ScyllaDB Version: 6.2+
--
-- This migration creates the initial message storage schema following
-- Discord's architecture for storing trillions of messages.
--
-- TABLETS DISABLED: Required for counter tables, secondary indexes
-- See: https://docs.scylladb.com/stable/architecture/tablets.html
-- =============================================================================

-- Create keyspace with tablets disabled for full feature support
CREATE KEYSPACE IF NOT EXISTS wellwon_scylla
WITH replication = {
    'class': 'NetworkTopologyStrategy',
    'datacenter1': 1
}
AND durable_writes = true
AND tablets = {'enabled': false};

USE wellwon_scylla;

-- Core messages table
CREATE TABLE IF NOT EXISTS messages (
    channel_id              uuid,
    bucket                  int,
    message_id              bigint,
    sender_id               uuid,
    content                 text,
    message_type            text,
    reply_to_id             bigint,
    file_url                text,
    file_name               text,
    file_size               bigint,
    file_type               text,
    voice_duration          int,
    created_at              timestamp,
    updated_at              timestamp,
    is_edited               boolean,
    is_deleted              boolean,
    source                  text,
    telegram_message_id     bigint,
    telegram_user_id        bigint,
    telegram_user_data      text,
    telegram_forward_data   text,
    telegram_topic_id       bigint,
    sync_direction          text,
    telegram_read_at        timestamp,
    metadata                text,
    PRIMARY KEY ((channel_id, bucket), message_id)
) WITH CLUSTERING ORDER BY (message_id DESC)
AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_size': 10,
    'compaction_window_unit': 'DAYS'
}
AND gc_grace_seconds = 86400
AND comment = 'Chat messages with Discord-style partitioning';

-- Telegram message mapping (replaces secondary index)
CREATE TABLE IF NOT EXISTS telegram_message_mapping (
    telegram_message_id     bigint,
    telegram_chat_id        bigint,
    channel_id              uuid,
    bucket                  int,
    message_id              bigint,
    created_at              timestamp,
    PRIMARY KEY ((telegram_message_id, telegram_chat_id))
) WITH gc_grace_seconds = 86400
AND comment = 'Fast Telegram message ID lookup';

-- Individual reactions
CREATE TABLE IF NOT EXISTS message_reactions (
    channel_id      uuid,
    message_id      bigint,
    emoji           text,
    user_id         uuid,
    created_at      timestamp,
    PRIMARY KEY ((channel_id, message_id), emoji, user_id)
) WITH CLUSTERING ORDER BY (emoji ASC, user_id ASC)
AND gc_grace_seconds = 86400
AND comment = 'Emoji reactions on messages';

-- Reaction counts (counter table - requires tablets disabled)
CREATE TABLE IF NOT EXISTS message_reaction_counts (
    channel_id      uuid,
    message_id      bigint,
    emoji           text,
    count           counter,
    PRIMARY KEY ((channel_id, message_id), emoji)
) WITH comment = 'Reaction counts per emoji';

-- Pinned messages
CREATE TABLE IF NOT EXISTS pinned_messages (
    channel_id      uuid,
    message_id      bigint,
    pinned_by       uuid,
    pinned_at       timestamp,
    content_preview text,
    sender_id       uuid,
    PRIMARY KEY (channel_id, message_id)
) WITH CLUSTERING ORDER BY (message_id DESC)
AND gc_grace_seconds = 86400
AND comment = 'Pinned messages per channel';

-- Telegram sync state
CREATE TABLE IF NOT EXISTS telegram_sync_state (
    channel_id              uuid,
    telegram_chat_id        bigint,
    telegram_topic_id       bigint,
    last_synced_message_id  bigint,
    last_sync_at            timestamp,
    sync_enabled            boolean,
    sync_direction          text,
    error_count             int,
    last_error              text,
    last_error_at           timestamp,
    PRIMARY KEY (channel_id)
) WITH gc_grace_seconds = 86400
AND comment = 'Telegram sync state tracking';

-- Secondary index (requires tablets disabled)
CREATE INDEX IF NOT EXISTS idx_telegram_sync_chat
ON telegram_sync_state (telegram_chat_id);

-- Channel metadata (denormalized)
CREATE TABLE IF NOT EXISTS channel_metadata (
    channel_id          uuid,
    channel_name        text,
    channel_type        text,
    company_id          uuid,
    created_by          uuid,
    created_at          timestamp,
    updated_at          timestamp,
    is_active           boolean,
    participant_count   int,
    PRIMARY KEY (channel_id)
) WITH gc_grace_seconds = 86400
AND comment = 'Denormalized channel metadata';

-- Message read positions
CREATE TABLE IF NOT EXISTS message_read_positions (
    channel_id              uuid,
    user_id                 uuid,
    last_read_message_id    bigint,
    last_read_at            timestamp,
    unread_count            int,
    PRIMARY KEY (channel_id, user_id)
) WITH gc_grace_seconds = 86400
AND comment = 'User read positions per channel';

-- =============================================================================
-- END MIGRATION 001
-- =============================================================================
