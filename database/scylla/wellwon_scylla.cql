-- =============================================================================
-- File: database/scylla/wellwon_scylla.cql
-- Description: Main ScyllaDB schema for WellWon messaging system
-- =============================================================================
-- Version: 2.0.0
-- ScyllaDB Version: 6.2+
-- Last Updated: 2025-11-30
--
-- Architecture: Discord-style message storage
-- - Partition by (channel_id, bucket) prevents unbounded partition growth
-- - Bucket = 10-day time window calculated from Snowflake ID
-- - Snowflake IDs for time-ordered, globally unique message IDs
-- - TWCS compaction for efficient time-series data management
--
-- TABLETS DISABLED: ScyllaDB 6.x enables tablets by default, but tablets
-- are NOT compatible with: Counters, Secondary Indexes, MVs, LWT, CDC
-- We disable tablets to use counter tables and secondary indexes.
-- See: https://docs.scylladb.com/stable/architecture/tablets.html
--
-- Data Distribution:
-- - ScyllaDB: High-volume message content, reactions, sync state
-- - PostgreSQL: Chat metadata, participants, unread tracking, search
-- - Redis: Ephemeral data (typing indicators, presence)
--
-- References:
-- - Discord Architecture: https://discord.com/blog/how-discord-stores-trillions-of-messages
-- - ScyllaDB Best Practices: https://docs.scylladb.com/stable/get-started/data-modeling/best-practices.html
-- =============================================================================

-- =============================================================================
-- KEYSPACE
-- =============================================================================

-- Development (single node) with tablets DISABLED for full feature support
-- noinspection SqlNoDataSourceInspection
CREATE KEYSPACE IF NOT EXISTS wellwon_scylla WITH replication = {'class': 'NetworkTopologyStrategy', 'datacenter1': 1} AND durable_writes = true AND tablets = {'enabled': false};

-- Production recommendation (3-node cluster):
-- CREATE KEYSPACE IF NOT EXISTS wellwon_scylla
-- WITH replication = {
--     'class': 'NetworkTopologyStrategy',
--     'datacenter1': 3
-- }
-- AND durable_writes = true
-- AND tablets = {'enabled': false};

USE wellwon_scylla;


-- =============================================================================
-- TABLE: messages
-- =============================================================================
-- Primary message storage with Discord-style partitioning
-- Partition: (channel_id, bucket) - prevents unbounded partition growth
-- Clustering: message_id DESC - Snowflake ID for time ordering

CREATE TABLE IF NOT EXISTS messages (
    -- Partition key
    channel_id              uuid,
    bucket                  int,            -- 10-day window from Snowflake timestamp

    -- Clustering key (Snowflake ID - time-ordered, globally unique)
    message_id              bigint,

    -- Sender (NULL for unmapped Telegram users)
    sender_id               uuid,

    -- Content
    content                 text,
    message_type            text,           -- text, file, voice, image, system

    -- Reply/Threading
    reply_to_id             bigint,

    -- File attachments
    file_url                text,
    file_name               text,
    file_size               bigint,
    file_type               text,
    voice_duration          int,

    -- Timestamps (derived from Snowflake ID, stored for convenience)
    created_at              timestamp,
    updated_at              timestamp,

    -- Status
    is_edited               boolean,
    is_deleted              boolean,

    -- Source tracking
    source                  text,           -- web, telegram, api

    -- Telegram integration
    telegram_message_id     bigint,
    telegram_user_id        bigint,
    telegram_user_data      text,           -- JSON: {first_name, last_name, username, is_bot}
    telegram_forward_data   text,           -- JSON: forwarded message info
    telegram_topic_id       bigint,         -- Forum topic ID
    sync_direction          text,           -- telegram_to_web, web_to_telegram, bidirectional
    telegram_read_at        timestamp,

    -- Metadata
    metadata                text,           -- JSON: additional message metadata

    PRIMARY KEY ((channel_id, bucket), message_id)
) WITH CLUSTERING ORDER BY (message_id DESC)
AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_size': 10,
    'compaction_window_unit': 'DAYS'
}
AND gc_grace_seconds = 86400
AND comment = 'Chat messages with Discord-style partitioning';


-- =============================================================================
-- TABLE: telegram_message_mapping
-- =============================================================================
-- Dedicated lookup table for Telegram message ID -> ScyllaDB message
-- Replaces secondary index (anti-pattern on large partitioned tables)

CREATE TABLE IF NOT EXISTS telegram_message_mapping (
    telegram_message_id     bigint,
    telegram_chat_id        bigint,
    channel_id              uuid,
    bucket                  int,
    message_id              bigint,
    created_at              timestamp,

    PRIMARY KEY ((telegram_message_id, telegram_chat_id))
) WITH gc_grace_seconds = 86400
AND comment = 'Fast lookup: Telegram message ID -> ScyllaDB message';


-- =============================================================================
-- TABLE: message_reactions
-- =============================================================================
-- Individual reaction records (who reacted with what emoji)

CREATE TABLE IF NOT EXISTS message_reactions (
    channel_id      uuid,
    message_id      bigint,
    emoji           text,
    user_id         uuid,
    created_at      timestamp,

    PRIMARY KEY ((channel_id, message_id), emoji, user_id)
) WITH CLUSTERING ORDER BY (emoji ASC, user_id ASC)
AND gc_grace_seconds = 86400
AND comment = 'Individual emoji reactions on messages';


-- =============================================================================
-- TABLE: message_reaction_counts
-- =============================================================================
-- Counter table for efficient reaction count queries
-- Note: Counter tables require tablets = {'enabled': false}

CREATE TABLE IF NOT EXISTS message_reaction_counts (
    channel_id      uuid,
    message_id      bigint,
    emoji           text,
    count           counter,

    PRIMARY KEY ((channel_id, message_id), emoji)
) WITH comment = 'Aggregated reaction counts per emoji (counter table)';


-- =============================================================================
-- TABLE: pinned_messages
-- =============================================================================
-- Pinned messages per channel (denormalized for fast access)

CREATE TABLE IF NOT EXISTS pinned_messages (
    channel_id      uuid,
    message_id      bigint,
    pinned_by       uuid,
    pinned_at       timestamp,
    content_preview text,           -- First 200 chars of message
    sender_id       uuid,

    PRIMARY KEY (channel_id, message_id)
) WITH CLUSTERING ORDER BY (message_id DESC)
AND gc_grace_seconds = 86400
AND comment = 'Pinned messages per channel';


-- =============================================================================
-- TABLE: telegram_sync_state
-- =============================================================================
-- Tracks synchronization state between WellWon and Telegram

CREATE TABLE IF NOT EXISTS telegram_sync_state (
    channel_id              uuid,
    telegram_chat_id        bigint,
    telegram_topic_id       bigint,
    last_synced_message_id  bigint,
    last_sync_at            timestamp,
    sync_enabled            boolean,
    sync_direction          text,           -- inbound, outbound, bidirectional
    error_count             int,
    last_error              text,
    last_error_at           timestamp,

    PRIMARY KEY (channel_id)
) WITH gc_grace_seconds = 86400
AND comment = 'Telegram sync state tracking per channel';

-- Secondary index for reverse lookup (find channel by Telegram chat)
-- Note: Secondary indexes require tablets = {'enabled': false}
CREATE INDEX IF NOT EXISTS idx_telegram_sync_chat
ON telegram_sync_state (telegram_chat_id);


-- =============================================================================
-- TABLE: channel_metadata
-- =============================================================================
-- Denormalized channel info for ScyllaDB queries
-- Avoids cross-database joins with PostgreSQL

CREATE TABLE IF NOT EXISTS channel_metadata (
    channel_id          uuid,
    channel_name        text,
    channel_type        text,           -- direct, group, company
    company_id          uuid,
    created_by          uuid,
    created_at          timestamp,
    updated_at          timestamp,
    is_active           boolean,
    participant_count   int,

    PRIMARY KEY (channel_id)
) WITH gc_grace_seconds = 86400
AND comment = 'Denormalized channel metadata for ScyllaDB-only queries';


-- =============================================================================
-- TABLE: message_read_positions
-- =============================================================================
-- Track read position per user per channel (for unread counts)

CREATE TABLE IF NOT EXISTS message_read_positions (
    channel_id              uuid,
    user_id                 uuid,
    last_read_message_id    bigint,
    last_read_at            timestamp,
    unread_count            int,            -- Cached count, may be approximate

    PRIMARY KEY (channel_id, user_id)
) WITH gc_grace_seconds = 86400
AND comment = 'User read positions per channel for unread tracking';


-- =============================================================================
-- VERIFICATION
-- =============================================================================
-- Run in cqlsh after applying:
-- DESCRIBE KEYSPACE wellwon_scylla;
-- SELECT table_name FROM system_schema.tables WHERE keyspace_name = 'wellwon_scylla';

-- =============================================================================
-- EOF
-- =============================================================================
