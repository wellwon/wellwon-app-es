-- =============================================================================
-- WellWon Platform - Complete PostgreSQL Schema
-- Event Sourcing + CQRS Infrastructure + Business Domain
-- =============================================================================
-- Version: 1.0.0
-- Date: 2025-11-24
--
-- Features:
-- - Event Sourcing infrastructure (Outbox, DLQ, Projections)
-- - CQRS pattern support (Commands, Events, Read Models)
-- - WellWon business domains (Companies, Chats, Telegram, etc.)
-- - Comprehensive audit and system logging
-- - CDC trigger for is_developer field changes
-- =============================================================================

-- ======================
-- EXTENSIONS
-- ======================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- for gen_random_uuid()

-- ======================
-- ENUM TYPES
-- ======================

-- User type (business role in platform)
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_type_enum') THEN
        CREATE TYPE user_type_enum AS ENUM (
            'client',
            'payment_agent',
            'logistician',
            'purchaser',
            'unassigned',
            'manager'
        );
    END IF;
END $$;

-- User-Company relationship types
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_company_relationship') THEN
        CREATE TYPE user_company_relationship AS ENUM ('owner', 'manager', 'assigned_admin');
    END IF;
END $$;

-- Company status levels
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'company_status') THEN
        CREATE TYPE company_status AS ENUM ('new', 'bronze', 'silver', 'gold');
    END IF;
END $$;

-- Telegram group states
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'telegram_group_state') THEN
        CREATE TYPE telegram_group_state AS ENUM ('Working', 'Archive', 'Closed');
    END IF;
END $$;

-- Chat business roles
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'chat_business_role') THEN
        CREATE TYPE chat_business_role AS ENUM (
            'client',
            'payment_agent',
            'logistician',
            'purchasers',
            'unassigned'
        );
    END IF;
END $$;

-- ======================
-- BASIC TRIGGER FUNCTIONS
-- ======================
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

ALTER FUNCTION trigger_set_updated_at() OWNER TO wellwon;

-- =============================================================================
-- PART 1: EVENT SOURCING INFRASTRUCTURE
-- =============================================================================

-- ======================
-- USER_ACCOUNTS TABLE (Core Aggregate with ES Support)
-- ======================
CREATE TABLE IF NOT EXISTS user_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    hashed_secret TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    reset_token TEXT,
    reset_token_expires TIMESTAMP WITH TIME ZONE,
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    mfa_enabled BOOLEAN DEFAULT FALSE,
    security_alerts_enabled BOOLEAN DEFAULT TRUE,
    last_password_change TIMESTAMP WITH TIME ZONE,

    -- WellWon-specific fields
    first_name TEXT,
    last_name TEXT,
    phone TEXT,
    avatar_url TEXT,
    bio TEXT,
    is_developer BOOLEAN DEFAULT FALSE,
    user_type user_type_enum DEFAULT 'client' NOT NULL,
    user_number INTEGER,

    -- Event sourcing support
    aggregate_version INTEGER DEFAULT 1,
    last_event_sequence BIGINT,
    last_saga_id UUID,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for user_accounts
CREATE INDEX IF NOT EXISTS idx_user_accounts_username ON user_accounts(username);
CREATE INDEX IF NOT EXISTS idx_user_accounts_email ON user_accounts(email);
CREATE INDEX IF NOT EXISTS idx_user_accounts_role ON user_accounts(role) WHERE role != 'user';
CREATE INDEX IF NOT EXISTS idx_user_accounts_version ON user_accounts(aggregate_version);
CREATE INDEX IF NOT EXISTS idx_user_accounts_saga ON user_accounts(last_saga_id) WHERE last_saga_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_accounts_user_number ON user_accounts(user_number) WHERE user_number IS NOT NULL;

-- Triggers for user_accounts
DROP TRIGGER IF EXISTS set_user_accounts_updated_at ON user_accounts;
CREATE TRIGGER set_user_accounts_updated_at
    BEFORE UPDATE ON user_accounts
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- Password change trigger
CREATE OR REPLACE FUNCTION trigger_password_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_TABLE_NAME = 'user_accounts' THEN
        IF OLD.hashed_password IS DISTINCT FROM NEW.hashed_password THEN
            NEW.last_password_change = CURRENT_TIMESTAMP;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

ALTER FUNCTION trigger_password_change() OWNER TO wellwon;

DROP TRIGGER IF EXISTS set_user_accounts_password_change ON user_accounts;
CREATE TRIGGER set_user_accounts_password_change
    BEFORE UPDATE ON user_accounts
    FOR EACH ROW EXECUTE FUNCTION trigger_password_change();

-- ======================
-- EVENT OUTBOX (Transactional Outbox Pattern)
-- ======================
CREATE TABLE IF NOT EXISTS event_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL UNIQUE,
    aggregate_id UUID NOT NULL,
    aggregate_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data JSONB NOT NULL,
    topic TEXT NOT NULL,
    partition_key TEXT,

    -- Publishing status tracking
    status TEXT NOT NULL DEFAULT 'pending',
    publish_attempts INT DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    published_at TIMESTAMP WITH TIME ZONE,

    -- Error tracking
    last_error TEXT,
    last_error_at TIMESTAMP WITH TIME ZONE,

    -- Tracing and metadata
    correlation_id UUID,
    causation_id UUID,
    saga_id UUID,
    sequence_number BIGINT,
    aggregate_version INTEGER,

    -- Outbox-specific metadata
    metadata JSONB,
    transport_metadata JSONB,
    retry_policy JSONB,

    -- Delivery tracking
    delivery_timeout_at TIMESTAMP WITH TIME ZONE,
    priority INTEGER DEFAULT 0,
    batch_id UUID,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT event_outbox_status_check CHECK (status IN ('pending', 'published', 'failed', 'dead_letter', 'retrying'))
);

-- Indexes for event_outbox
CREATE INDEX IF NOT EXISTS idx_outbox_status_priority_created ON event_outbox(status, priority DESC, created_at) WHERE status IN ('pending', 'retrying');
CREATE INDEX IF NOT EXISTS idx_outbox_event_id ON event_outbox(event_id);
CREATE INDEX IF NOT EXISTS idx_outbox_aggregate ON event_outbox(aggregate_id, aggregate_type);
CREATE INDEX IF NOT EXISTS idx_outbox_published_at ON event_outbox(published_at) WHERE status = 'published';
CREATE INDEX IF NOT EXISTS idx_outbox_saga_id ON event_outbox(saga_id) WHERE saga_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_outbox_causation ON event_outbox(causation_id) WHERE causation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_outbox_sequence ON event_outbox(sequence_number) WHERE sequence_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_outbox_cleanup ON event_outbox(status, published_at) WHERE status = 'published';
CREATE INDEX IF NOT EXISTS idx_outbox_stuck_events ON event_outbox(status, last_attempt_at) WHERE status = 'failed';
CREATE INDEX IF NOT EXISTS idx_outbox_timeout ON event_outbox(delivery_timeout_at) WHERE delivery_timeout_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_outbox_batch ON event_outbox(batch_id) WHERE batch_id IS NOT NULL;

-- Optimized indexes for outbox publisher
CREATE INDEX IF NOT EXISTS idx_outbox_pending_events_optimized
ON event_outbox(status, publish_attempts, last_attempt_at, created_at, aggregate_id, aggregate_version)
WHERE status IN ('pending', 'failed');

CREATE INDEX IF NOT EXISTS idx_outbox_aggregate_ordering
ON event_outbox(aggregate_id, aggregate_version, created_at, id)
WHERE status IN ('pending', 'failed') AND publish_attempts < 10;

-- Trigger for updated_at
DROP TRIGGER IF EXISTS set_event_outbox_updated_at ON event_outbox;
CREATE TRIGGER set_event_outbox_updated_at
    BEFORE UPDATE ON event_outbox
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- PostgreSQL NOTIFY trigger for instant outbox processing
CREATE OR REPLACE FUNCTION notify_outbox_event()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('outbox_events', NEW.event_id::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

ALTER FUNCTION notify_outbox_event() OWNER TO wellwon;

DROP TRIGGER IF EXISTS outbox_insert_notify ON event_outbox;
CREATE TRIGGER outbox_insert_notify
    AFTER INSERT ON event_outbox
    FOR EACH ROW
    EXECUTE FUNCTION notify_outbox_event();

-- ======================
-- CES OUTBOX (Compensating Event System - for external change detection)
-- ======================
-- NOTE: This table is DEPRECATED - we use event_outbox directly for CES events
-- Keeping for backwards compatibility
CREATE TABLE IF NOT EXISTS cdc_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type TEXT NOT NULL,
    aggregate_id UUID NOT NULL,
    change_type TEXT NOT NULL,
    changed_fields JSONB NOT NULL,
    current_state JSONB NOT NULL,
    metadata JSONB,
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT cdc_outbox_unprocessed CHECK (processed_at IS NULL OR processed_at >= created_at)
);

CREATE INDEX IF NOT EXISTS idx_cdc_outbox_unprocessed ON cdc_outbox(created_at) WHERE processed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_cdc_outbox_aggregate ON cdc_outbox(aggregate_id, aggregate_type);

-- ======================
-- CES TRIGGER FOR ADMIN FIELD CHANGES (Compensating Event System)
-- ======================
-- Pattern: Compensating Event System (Greg Young)
-- PostgreSQL triggers detect EXTERNAL changes (bypassing application)
-- and generate compensating events for audit trail and real-time sync.
--
-- Monitored fields:
-- - is_developer (developer access)
-- - role (user/admin/manager)
-- - user_type (client/logistician/payment_agent/etc)
-- - is_active (ban/unban user)
-- - email_verified (manual email verification)
--
-- CRITICAL: Uses pg_trigger_depth() = 0 to only fire for EXTERNAL changes!
DROP FUNCTION IF EXISTS ces_user_admin_fields_change() CASCADE;
DROP FUNCTION IF EXISTS cdc_user_admin_fields_change() CASCADE;

CREATE FUNCTION ces_user_admin_fields_change()
RETURNS TRIGGER AS $$
DECLARE
    v_event_id UUID;
    v_event_data JSONB;
    v_metadata JSONB;
    v_event_type TEXT;
    v_changed_fields JSONB;
    v_priority INTEGER;
BEGIN
    -- Track which fields changed
    v_changed_fields := jsonb_build_object();

    -- Check each admin field
    IF OLD.is_developer IS DISTINCT FROM NEW.is_developer THEN
        v_changed_fields := v_changed_fields || jsonb_build_object('is_developer', jsonb_build_object('old', OLD.is_developer, 'new', NEW.is_developer));
    END IF;

    IF OLD.role IS DISTINCT FROM NEW.role THEN
        v_changed_fields := v_changed_fields || jsonb_build_object('role', jsonb_build_object('old', OLD.role, 'new', NEW.role));
    END IF;

    IF OLD.user_type IS DISTINCT FROM NEW.user_type THEN
        v_changed_fields := v_changed_fields || jsonb_build_object('user_type', jsonb_build_object('old', OLD.user_type::text, 'new', NEW.user_type::text));
    END IF;

    IF OLD.is_active IS DISTINCT FROM NEW.is_active THEN
        v_changed_fields := v_changed_fields || jsonb_build_object('is_active', jsonb_build_object('old', OLD.is_active, 'new', NEW.is_active));
    END IF;

    IF OLD.email_verified IS DISTINCT FROM NEW.email_verified THEN
        v_changed_fields := v_changed_fields || jsonb_build_object('email_verified', jsonb_build_object('old', OLD.email_verified, 'new', NEW.email_verified));
    END IF;

    -- Only fire if at least one field changed
    IF jsonb_object_keys(v_changed_fields) IS NOT NULL THEN
        v_event_id := gen_random_uuid();

        -- Determine event type based on primary change (CES naming: *Externally)
        -- Priority: 1-5 = security-critical (role, status), 6-10 = important
        IF v_changed_fields ? 'role' THEN
            v_event_type := 'UserRoleChangedExternally';
            v_priority := 1;  -- Security-critical
        ELSIF v_changed_fields ? 'is_active' THEN
            v_event_type := 'UserStatusChangedExternally';
            v_priority := 1;  -- Security-critical
        ELSIF v_changed_fields ? 'user_type' THEN
            v_event_type := 'UserTypeChangedExternally';
            v_priority := 5;
        ELSIF v_changed_fields ? 'email_verified' THEN
            v_event_type := 'UserEmailVerifiedExternally';
            v_priority := 5;
        ELSIF v_changed_fields ? 'is_developer' THEN
            v_event_type := 'UserDeveloperStatusChangedExternally';
            v_priority := 5;
        ELSE
            v_event_type := 'UserAdminFieldsChangedExternally';
            v_priority := 10;
        END IF;

        -- Build event data (CES pattern)
        v_event_data := jsonb_build_object(
            'event_id', v_event_id::text,
            'event_type', v_event_type,
            'aggregate_id', NEW.id::text,
            'aggregate_type', 'UserAccount',
            'user_id', NEW.id::text,
            'email', NEW.email,
            'username', NEW.username,
            'changed_fields', v_changed_fields,
            'current_state', jsonb_build_object(
                'role', NEW.role,
                'user_type', NEW.user_type::text,
                'is_active', NEW.is_active,
                'is_developer', NEW.is_developer,
                'email_verified', NEW.email_verified
            ),
            'changed_at', to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
            'detected_by', 'EXTERNAL_SQL',
            'compensating_event', true
        );

        -- Build metadata (CES pattern with EventStore flags)
        v_metadata := jsonb_build_object(
            'source', 'ces_trigger',
            'trigger_name', TG_NAME,
            'table_name', TG_TABLE_NAME,
            'operation', TG_OP,
            'session_user', session_user,
            'application_name', current_setting('application_name', true),
            'changed_at', to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
            'write_to_eventstore', true,
            'compensating_event', true,
            'severity', CASE WHEN v_priority <= 2 THEN 'CRITICAL' WHEN v_priority <= 5 THEN 'HIGH' ELSE 'MEDIUM' END
        );

        -- Insert into event_outbox (Transactional Outbox Pattern)
        INSERT INTO event_outbox (
            event_id,
            aggregate_id,
            aggregate_type,
            event_type,
            event_data,
            topic,
            partition_key,
            status,
            publish_attempts,
            priority,
            metadata,
            created_at
        ) VALUES (
            v_event_id,
            NEW.id,
            'UserAccount',
            v_event_type,
            v_event_data,
            'transport.user-account-events',
            NEW.id::text,
            'pending',
            0,
            v_priority,
            v_metadata,
            NOW()
        );

        -- Instant notification via LISTEN/NOTIFY
        PERFORM pg_notify('outbox_events', v_event_id::text);

        -- Log for debugging
        RAISE NOTICE 'CES: % event created for user % (fields: %, priority: %)',
            v_event_type, NEW.id, jsonb_object_keys(v_changed_fields), v_priority;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

ALTER FUNCTION ces_user_admin_fields_change() OWNER TO wellwon;

-- CES Trigger: Only fires for EXTERNAL changes (pg_trigger_depth() = 0)
DROP TRIGGER IF EXISTS cdc_user_admin_fields ON user_accounts;
DROP TRIGGER IF EXISTS ces_user_admin_fields ON user_accounts;
CREATE TRIGGER ces_user_admin_fields
    AFTER UPDATE OF is_developer, role, user_type, is_active, email_verified ON user_accounts
    FOR EACH ROW
    WHEN (pg_trigger_depth() = 0)
    EXECUTE FUNCTION ces_user_admin_fields_change();

-- Stored procedure for fetching pending outbox events
CREATE OR REPLACE FUNCTION get_pending_outbox_events(
    p_max_attempts INTEGER,
    p_cutoff_time TIMESTAMPTZ,
    p_created_after TIMESTAMPTZ,
    p_limit INTEGER
)
RETURNS TABLE (
    id UUID,
    event_id UUID,
    aggregate_id UUID,
    aggregate_type TEXT,
    event_type TEXT,
    event_data JSONB,
    topic TEXT,
    partition_key TEXT,
    status TEXT,
    publish_attempts INT,
    last_attempt_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    last_error TEXT,
    correlation_id UUID,
    causation_id UUID,
    saga_id UUID,
    metadata JSONB,
    aggregate_version INTEGER,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id, e.event_id, e.aggregate_id, e.aggregate_type, e.event_type,
        e.event_data, e.topic, e.partition_key, e.status, e.publish_attempts,
        e.last_attempt_at, e.published_at, e.last_error, e.correlation_id,
        e.causation_id, e.saga_id, e.metadata, e.aggregate_version, e.created_at
    FROM event_outbox e
    WHERE e.status IN ('pending', 'failed')
      AND e.publish_attempts < p_max_attempts
      AND (e.last_attempt_at IS NULL OR e.last_attempt_at < p_cutoff_time)
      AND e.created_at > p_created_after
    ORDER BY e.aggregate_id, e.aggregate_version, e.created_at, e.id
    LIMIT p_limit
    FOR UPDATE SKIP LOCKED;
END;
$$;

ALTER FUNCTION get_pending_outbox_events(INTEGER, TIMESTAMPTZ, TIMESTAMPTZ, INTEGER) OWNER TO wellwon;

-- ======================
-- PROCESSED EVENTS (Event Processing Tracking)
-- ======================
CREATE TABLE IF NOT EXISTS processed_events (
    event_id UUID PRIMARY KEY,
    consumer_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_topic TEXT NOT NULL,
    payload_size INT,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processing_time_ms INTEGER,

    -- Saga and causation tracking
    saga_id UUID,
    causation_id UUID,
    correlation_id UUID,

    -- Source tracking
    from_event_store BOOLEAN DEFAULT FALSE,
    from_outbox BOOLEAN DEFAULT FALSE,
    from_projection_rebuild BOOLEAN DEFAULT FALSE,
    rebuild_id UUID,
    rebuild_projection TEXT,

    -- Worker and instance tracking
    worker_instance TEXT,
    consumer_group TEXT,
    partition_id INTEGER,
    offset_position BIGINT,

    -- Sequence tracking
    sequence_number BIGINT,
    aggregate_id UUID,
    aggregate_type TEXT,
    aggregate_version INTEGER,

    -- Processing result
    processing_result TEXT,

    -- Projection tracking
    projection_name TEXT,
    last_sequence BIGINT,
    gap_info JSONB,
    healing_status TEXT DEFAULT 'healthy',

    -- Sync event tracking
    is_sync_event BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Comprehensive indexes for processed_events
CREATE INDEX IF NOT EXISTS idx_processed_events_consumer ON processed_events(consumer_name);
CREATE INDEX IF NOT EXISTS idx_processed_events_type ON processed_events(event_type);
CREATE INDEX IF NOT EXISTS idx_processed_events_topic ON processed_events(event_topic);
CREATE INDEX IF NOT EXISTS idx_processed_events_processed_at ON processed_events(processed_at DESC);
CREATE INDEX IF NOT EXISTS idx_processed_events_from_store ON processed_events(from_event_store) WHERE from_event_store = true;
CREATE INDEX IF NOT EXISTS idx_processed_events_saga_id ON processed_events(saga_id) WHERE saga_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_processed_events_causation ON processed_events(causation_id) WHERE causation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_processed_events_correlation ON processed_events(correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_processed_events_outbox ON processed_events(from_outbox) WHERE from_outbox = true;
CREATE INDEX IF NOT EXISTS idx_processed_events_rebuild ON processed_events(from_projection_rebuild, rebuild_id) WHERE from_projection_rebuild = true;
CREATE INDEX IF NOT EXISTS idx_processed_events_sequence ON processed_events(sequence_number) WHERE sequence_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_processed_events_aggregate ON processed_events(aggregate_id, aggregate_type, aggregate_version);
CREATE INDEX IF NOT EXISTS idx_processed_events_projection_name ON processed_events(projection_name) WHERE projection_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_processed_events_sync ON processed_events(is_sync_event) WHERE is_sync_event = TRUE;

-- Covering indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_processed_events_recent_covering
ON processed_events (processed_at DESC)
INCLUDE (event_id, aggregate_id, aggregate_type, event_type, event_topic,
         processing_time_ms, from_event_store, from_outbox, from_projection_rebuild,
         projection_name, sequence_number, aggregate_version,
         worker_instance, consumer_name, processing_result);

CREATE INDEX IF NOT EXISTS idx_processed_events_aggregate_covering
ON processed_events (aggregate_type, aggregate_id, processed_at DESC)
INCLUDE (event_id, event_type, event_topic, processing_time_ms,
         from_event_store, from_outbox, from_projection_rebuild,
         projection_name, sequence_number, aggregate_version,
         worker_instance, consumer_name, processing_result);

-- ======================
-- PROJECTION CHECKPOINTS
-- ======================
CREATE TABLE IF NOT EXISTS projection_checkpoints (
    projection_name TEXT PRIMARY KEY,
    commit_position BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Metadata
    last_event_type TEXT,
    events_processed BIGINT DEFAULT 0,

    CONSTRAINT projection_checkpoints_position_check CHECK (commit_position >= 0)
);

CREATE INDEX IF NOT EXISTS idx_projection_checkpoints_updated
ON projection_checkpoints(updated_at DESC);

DROP TRIGGER IF EXISTS set_projection_checkpoints_updated_at ON projection_checkpoints;
CREATE TRIGGER set_projection_checkpoints_updated_at
    BEFORE UPDATE ON projection_checkpoints
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ======================
-- DEAD LETTER QUEUE (DLQ)
-- ======================
CREATE TABLE IF NOT EXISTS dlq_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_event_id UUID,
    event_type TEXT,
    topic_name TEXT,
    raw_payload JSONB NOT NULL,
    error_message TEXT,
    error_type TEXT,
    consumer_name TEXT,
    retry_count INT DEFAULT 0,
    last_attempted_at TIMESTAMP WITH TIME ZONE,

    -- Tracking
    saga_id UUID,
    causation_id UUID,
    correlation_id UUID,
    aggregate_id UUID,
    aggregate_type TEXT,
    sequence_number BIGINT,

    -- Classification
    dlq_reason TEXT,
    dlq_category TEXT,
    recoverable BOOLEAN DEFAULT TRUE,

    -- Recovery tracking
    recovery_attempted BOOLEAN DEFAULT FALSE,
    recovery_attempted_at TIMESTAMP WITH TIME ZONE,
    recovery_success BOOLEAN,

    -- Unified DLQ
    source_system TEXT DEFAULT 'sql',
    original_topic TEXT,
    reprocess_count INT DEFAULT 0,
    last_reprocess_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    payload_size INT
);

CREATE INDEX IF NOT EXISTS idx_dle_event_type ON dlq_events (event_type);
CREATE INDEX IF NOT EXISTS idx_dle_created_at ON dlq_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dle_saga_id ON dlq_events (saga_id) WHERE saga_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dle_causation ON dlq_events (causation_id) WHERE causation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dle_aggregate ON dlq_events (aggregate_id, aggregate_type);
CREATE INDEX IF NOT EXISTS idx_dle_category ON dlq_events (dlq_category) WHERE dlq_category IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dle_recoverable ON dlq_events (recoverable) WHERE recoverable = true;

-- ======================
-- AUDIT LOGS
-- ======================
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES user_accounts(id) ON DELETE SET NULL,
    actor_identity TEXT,
    action TEXT NOT NULL,
    target_entity_type TEXT,
    target_entity_id TEXT,
    status TEXT DEFAULT 'SUCCESS',
    details JSONB,
    entity_snapshot JSONB,
    client_ip TEXT,
    user_agent TEXT,

    -- Tracking
    saga_id UUID,
    causation_id UUID,
    correlation_id UUID,
    event_id UUID,

    -- Context
    session_id TEXT,
    request_id TEXT,
    operation_duration_ms INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_target ON audit_logs (target_entity_type, target_entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_saga_id ON audit_logs (saga_id) WHERE saga_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_session ON audit_logs (session_id) WHERE session_id IS NOT NULL;

-- ======================
-- SYSTEM LOGS
-- ======================
CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    event_source TEXT,
    event_type TEXT NOT NULL,
    level TEXT DEFAULT 'info',
    message TEXT,
    context JSONB,
    stacktrace TEXT,
    external_id TEXT,

    -- Correlation
    saga_id UUID,
    causation_id UUID,
    correlation_id UUID,

    -- Performance
    operation_duration_ms INTEGER,
    memory_usage_mb NUMERIC,

    -- Instance tracking
    worker_instance TEXT,
    process_id TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_logs_event_type_level ON system_logs (event_type, level);
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_saga_id ON system_logs (saga_id) WHERE saga_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_system_logs_worker ON system_logs (worker_instance) WHERE worker_instance IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs (level) WHERE level IN ('error', 'warn');

-- ======================
-- SCHEMA MIGRATIONS
-- ======================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    description TEXT,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Tracking
    applied_by TEXT,
    migration_duration_ms INTEGER,
    rollback_sql TEXT,
    checksum TEXT
);

-- =============================================================================
-- PART 2: WELLWON BUSINESS DOMAIN TABLES
-- =============================================================================

-- ======================
-- COMPANIES
-- ======================
CREATE TABLE IF NOT EXISTS companies (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    vat TEXT,
    ogrn TEXT,
    kpp TEXT,
    postal_code TEXT,
    country_id INTEGER DEFAULT 190,
    director TEXT,
    street TEXT,
    city TEXT,
    email TEXT,
    phone TEXT,
    company_type TEXT NOT NULL DEFAULT 'company',
    balance DECIMAL(10,2) NOT NULL DEFAULT 0.00,

    -- Status and metrics
    status company_status DEFAULT 'new',
    orders_count INTEGER DEFAULT 0 NOT NULL,
    rating NUMERIC(3,2) DEFAULT 0.0,
    successful_deliveries INTEGER DEFAULT 0 NOT NULL,
    turnover NUMERIC(15,2) DEFAULT 0.00 NOT NULL,
    on_time_delivery_percentage NUMERIC(5,2),
    average_delivery_time NUMERIC(8,2),
    logo_url TEXT,

    -- Telegram contacts
    tg_dir TEXT,
    tg_accountant TEXT,
    tg_manager_1 TEXT,
    tg_manager_2 TEXT,
    tg_manager_3 TEXT,
    tg_support TEXT,

    -- References
    created_by_user_id UUID REFERENCES user_accounts(id),
    assigned_manager_id UUID REFERENCES user_accounts(id),

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_companies_vat ON companies(vat);
CREATE INDEX IF NOT EXISTS idx_companies_email ON companies(email);
CREATE INDEX IF NOT EXISTS idx_companies_company_type ON companies(company_type);
CREATE INDEX IF NOT EXISTS idx_companies_assigned_manager ON companies(assigned_manager_id);
CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);

DROP TRIGGER IF EXISTS set_companies_updated_at ON companies;
CREATE TRIGGER set_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ======================
-- USER_COMPANIES (Many-to-Many)
-- ======================
CREATE TABLE IF NOT EXISTS user_companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    relationship_type user_company_relationship NOT NULL DEFAULT 'owner',
    assigned_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT user_companies_unique UNIQUE(user_id, company_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_user_companies_user ON user_companies(user_id);
CREATE INDEX IF NOT EXISTS idx_user_companies_company ON user_companies(company_id);

DROP TRIGGER IF EXISTS set_user_companies_updated_at ON user_companies;
CREATE TRIGGER set_user_companies_updated_at
    BEFORE UPDATE ON user_companies
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ======================
-- CHATS
-- ======================
CREATE TABLE IF NOT EXISTS chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT,
    type TEXT NOT NULL CHECK (type IN ('direct', 'group', 'company')),
    company_id UUID,
    created_by UUID NOT NULL REFERENCES user_accounts(id),
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB,

    -- Telegram integration
    telegram_supergroup_id BIGINT,
    telegram_topic_id INTEGER,
    telegram_sync BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chats_company_id ON chats(company_id);
CREATE INDEX IF NOT EXISTS idx_chats_created_by ON chats(created_by);
CREATE INDEX IF NOT EXISTS idx_chats_telegram_supergroup_id ON chats(telegram_supergroup_id);
CREATE INDEX IF NOT EXISTS idx_chats_type ON chats(type);

DROP TRIGGER IF EXISTS set_chats_updated_at ON chats;
CREATE TRIGGER set_chats_updated_at
    BEFORE UPDATE ON chats
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ======================
-- CHAT_PARTICIPANTS
-- ======================
CREATE TABLE IF NOT EXISTS chat_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'member' CHECK (role IN ('member', 'admin', 'observer')),
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_read_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,

    CONSTRAINT chat_participants_unique UNIQUE(chat_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_participants_chat_id ON chat_participants(chat_id);
CREATE INDEX IF NOT EXISTS idx_chat_participants_user_id ON chat_participants(user_id);

-- ======================
-- MESSAGES
-- ======================
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    sender_id UUID REFERENCES user_accounts(id) ON DELETE CASCADE,
    content TEXT,
    message_type TEXT DEFAULT 'text' CHECK (message_type IN ('text', 'file', 'voice', 'image', 'system')),
    reply_to_id UUID REFERENCES messages(id),

    -- File fields
    file_url TEXT,
    file_name TEXT,
    file_size BIGINT,
    file_type TEXT,
    voice_duration INTEGER,

    -- Telegram integration
    telegram_message_id BIGINT,
    telegram_user_id BIGINT,
    telegram_user_data JSONB,
    telegram_topic_id INTEGER,
    telegram_forward_data JSONB,
    sync_direction TEXT,

    -- Status
    is_edited BOOLEAN DEFAULT FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,
    metadata JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_id_created_at ON messages(chat_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_reply_to_id ON messages(reply_to_id);
CREATE INDEX IF NOT EXISTS idx_messages_telegram_message_id ON messages(telegram_message_id);
CREATE INDEX IF NOT EXISTS idx_messages_telegram_user_id ON messages(telegram_user_id);

DROP TRIGGER IF EXISTS set_messages_updated_at ON messages;
CREATE TRIGGER set_messages_updated_at
    BEFORE UPDATE ON messages
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ======================
-- MESSAGE_READS
-- ======================
CREATE TABLE IF NOT EXISTS message_reads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    read_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT message_reads_unique UNIQUE(message_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_message_reads_message_id ON message_reads(message_id);
CREATE INDEX IF NOT EXISTS idx_message_reads_user_id ON message_reads(user_id);

-- ======================
-- TYPING_INDICATORS
-- ======================
CREATE TABLE IF NOT EXISTS typing_indicators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP + INTERVAL '10 seconds'),

    CONSTRAINT typing_indicators_unique UNIQUE(chat_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_typing_indicators_chat_id ON typing_indicators(chat_id);
CREATE INDEX IF NOT EXISTS idx_typing_indicators_expires_at ON typing_indicators(expires_at);

-- ======================
-- TELEGRAM_SUPERGROUPS
-- ======================
CREATE TABLE IF NOT EXISTS telegram_supergroups (
    id BIGINT PRIMARY KEY,
    company_id BIGINT REFERENCES companies(id),
    title TEXT NOT NULL,
    username TEXT,
    description TEXT,
    invite_link TEXT,
    member_count INTEGER DEFAULT 0,
    is_forum BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    bot_is_admin BOOLEAN DEFAULT FALSE,
    status_emoji telegram_group_state,
    metadata JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telegram_supergroups_company_id ON telegram_supergroups(company_id);

DROP TRIGGER IF EXISTS set_telegram_supergroups_updated_at ON telegram_supergroups;
CREATE TRIGGER set_telegram_supergroups_updated_at
    BEFORE UPDATE ON telegram_supergroups
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- Add foreign key to chats after telegram_supergroups exists
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_chats_telegram_supergroup'
    ) THEN
        ALTER TABLE chats
        ADD CONSTRAINT fk_chats_telegram_supergroup
        FOREIGN KEY (telegram_supergroup_id) REFERENCES telegram_supergroups(id);
    END IF;
END $$;

-- ======================
-- TELEGRAM_GROUP_MEMBERS
-- ======================
CREATE TABLE IF NOT EXISTS telegram_group_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supergroup_id BIGINT NOT NULL REFERENCES telegram_supergroups(id) ON DELETE CASCADE,
    telegram_user_id BIGINT NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    is_bot BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'member',
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB,

    CONSTRAINT telegram_group_members_unique UNIQUE(supergroup_id, telegram_user_id)
);

CREATE INDEX IF NOT EXISTS idx_telegram_group_members_supergroup_id ON telegram_group_members(supergroup_id);
CREATE INDEX IF NOT EXISTS idx_telegram_group_members_telegram_user_id ON telegram_group_members(telegram_user_id);

-- ======================
-- TG_USERS (Telegram Users)
-- ======================
CREATE TABLE IF NOT EXISTS tg_users (
    id BIGINT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT,
    username TEXT,
    language_code TEXT,
    photo_url TEXT,
    phone_number TEXT,
    email TEXT,
    allows_write_to_pm BOOLEAN,
    color_scheme TEXT,
    is_premium BOOLEAN,
    is_blocked BOOLEAN DEFAULT FALSE,
    policy BOOLEAN NOT NULL DEFAULT FALSE,

    -- Odoo integration
    odoo_partner_id INTEGER,
    odoo_name TEXT,
    odoo_surname TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tg_users_username ON tg_users(username);

DROP TRIGGER IF EXISTS set_tg_users_updated_at ON tg_users;
CREATE TRIGGER set_tg_users_updated_at
    BEFORE UPDATE ON tg_users
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ======================
-- MESSAGE_TEMPLATES
-- ======================
CREATE TABLE IF NOT EXISTS message_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    template_data JSONB NOT NULL,
    image_url TEXT,
    created_by UUID REFERENCES user_accounts(id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_message_templates_category ON message_templates(category);
CREATE INDEX IF NOT EXISTS idx_message_templates_created_by ON message_templates(created_by);

DROP TRIGGER IF EXISTS set_message_templates_updated_at ON message_templates;
CREATE TRIGGER set_message_templates_updated_at
    BEFORE UPDATE ON message_templates
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ======================
-- NEWS
-- ======================
CREATE TABLE IF NOT EXISTS news (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    category TEXT NOT NULL,
    image TEXT,
    preview TEXT,
    is_published BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_news_date ON news(date DESC);
CREATE INDEX IF NOT EXISTS idx_news_category ON news(category);
CREATE INDEX IF NOT EXISTS idx_news_published ON news(is_published) WHERE is_published = TRUE;

DROP TRIGGER IF EXISTS set_news_updated_at ON news;
CREATE TRIGGER set_news_updated_at
    BEFORE UPDATE ON news
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ======================
-- CURRENCIES
-- ======================
CREATE TABLE IF NOT EXISTS currencies (
    id BIGINT PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    eur_rub NUMERIC,
    cny_rub NUMERIC,
    usd_rub NUMERIC,
    usd_cny NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- PART 3: MONITORING VIEWS AND HELPER FUNCTIONS
-- =============================================================================

-- Outbox performance view
CREATE OR REPLACE VIEW outbox_performance AS
SELECT
    event_type,
    status,
    COUNT(*) as count,
    AVG(publish_attempts) as avg_attempts,
    AVG(CASE
        WHEN published_at IS NOT NULL AND created_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (published_at - created_at))
    END) as avg_publish_time_seconds,
    SUM(CASE WHEN status = 'dead_letter' THEN 1 ELSE 0 END) as dead_letter_count
FROM event_outbox
GROUP BY event_type, status;

-- Projection rebuild performance view
CREATE OR REPLACE VIEW projection_rebuild_performance AS
SELECT
    projection_name,
    commit_position,
    updated_at,
    last_event_type,
    events_processed
FROM projection_checkpoints
ORDER BY updated_at DESC;

-- Worker event performance view
CREATE OR REPLACE VIEW worker_event_performance AS
SELECT
    worker_instance,
    event_type,
    event_topic,
    COUNT(*) as events_processed,
    AVG(processing_time_ms) as avg_processing_time_ms,
    MAX(processing_time_ms) as max_processing_time_ms,
    MIN(processing_time_ms) as min_processing_time_ms,
    SUM(CASE WHEN from_event_store THEN 1 ELSE 0 END) as event_store_events,
    SUM(CASE WHEN from_outbox THEN 1 ELSE 0 END) as outbox_events,
    SUM(CASE WHEN from_projection_rebuild THEN 1 ELSE 0 END) as rebuild_events,
    MAX(processed_at) as last_processed_at
FROM processed_events
WHERE processed_at > NOW() - INTERVAL '24 hours'
GROUP BY worker_instance, event_type, event_topic;

-- Unified DLQ view
CREATE OR REPLACE VIEW unified_dlq AS
SELECT
    id,
    original_event_id as event_id,
    event_type,
    COALESCE(topic_name, original_topic) as topic,
    raw_payload,
    error_message,
    error_type,
    consumer_name,
    retry_count + COALESCE(reprocess_count, 0) as total_attempts,
    created_at,
    CASE
        WHEN recovery_success THEN 'recovered'
        WHEN NOT recoverable THEN 'permanent_failure'
        WHEN retry_count >= 3 THEN 'max_retries_exceeded'
        ELSE 'pending_retry'
    END as status
FROM dlq_events;

-- Function to get outbox health
CREATE OR REPLACE FUNCTION get_outbox_health()
RETURNS TABLE (
    status TEXT,
    count BIGINT,
    oldest_pending_minutes NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        o.status,
        COUNT(*) as count,
        ROUND(
            EXTRACT(EPOCH FROM (NOW() - MIN(
                CASE
                    WHEN o.status = 'pending' AND o.created_at IS NOT NULL
                    THEN o.created_at
                END
            ))) / 60,
            2
        ) as oldest_pending_minutes
    FROM event_outbox o
    GROUP BY o.status;
END;
$$ LANGUAGE plpgsql;

ALTER FUNCTION get_outbox_health() OWNER TO wellwon;

-- Function to get projection health
CREATE OR REPLACE FUNCTION get_projection_health()
RETURNS TABLE (
    projection_name TEXT,
    tracked_aggregates BIGINT,
    unhealthy_count BIGINT,
    last_processing_minutes_ago NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pe.projection_name,
        COUNT(DISTINCT pe.aggregate_id) as tracked_aggregates,
        COUNT(CASE WHEN pe.healing_status != 'healthy' THEN 1 END) as unhealthy_count,
        ROUND(
            CASE
                WHEN MAX(pe.processed_at) IS NOT NULL
                THEN EXTRACT(EPOCH FROM (NOW() - MAX(pe.processed_at))) / 60
            END,
            2
        ) as last_processing_minutes_ago
    FROM processed_events pe
    WHERE pe.projection_name IS NOT NULL
    GROUP BY pe.projection_name;
END;
$$ LANGUAGE plpgsql;

ALTER FUNCTION get_projection_health() OWNER TO wellwon;

-- Function to get worker performance stats
CREATE OR REPLACE FUNCTION get_worker_performance(p_hours_back INTEGER DEFAULT 24)
RETURNS TABLE (
    worker_instance TEXT,
    total_events BIGINT,
    avg_processing_time_ms NUMERIC,
    error_rate NUMERIC,
    unique_event_types BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pe.worker_instance,
        COUNT(*) as total_events,
        ROUND(AVG(pe.processing_time_ms), 2) as avg_processing_time_ms,
        ROUND(100.0 * COUNT(CASE WHEN pe.processing_time_ms > 1000 THEN 1 END)::NUMERIC / NULLIF(COUNT(*), 0), 2) as error_rate,
        COUNT(DISTINCT pe.event_type) as unique_event_types
    FROM processed_events pe
    WHERE pe.processed_at > NOW() - (p_hours_back || ' hours')::INTERVAL
      AND pe.worker_instance IS NOT NULL
    GROUP BY pe.worker_instance;
END;
$$ LANGUAGE plpgsql;

ALTER FUNCTION get_worker_performance(INTEGER) OWNER TO wellwon;

-- Helper functions for user companies
CREATE OR REPLACE FUNCTION get_user_companies(
    p_user_id UUID,
    p_filter_type user_company_relationship DEFAULT NULL
)
RETURNS TABLE (
    company_id BIGINT,
    company_name TEXT,
    relationship_type user_company_relationship,
    assigned_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.name,
        uc.relationship_type,
        uc.assigned_at
    FROM user_companies uc
    JOIN companies c ON c.id = uc.company_id
    WHERE uc.user_id = p_user_id
      AND uc.is_active = TRUE
      AND (p_filter_type IS NULL OR uc.relationship_type = p_filter_type);
END;
$$ LANGUAGE plpgsql;

ALTER FUNCTION get_user_companies(UUID, user_company_relationship) OWNER TO wellwon;

CREATE OR REPLACE FUNCTION get_company_users(
    p_company_id BIGINT,
    p_filter_type user_company_relationship DEFAULT NULL
)
RETURNS TABLE (
    user_id UUID,
    email TEXT,
    username TEXT,
    relationship_type user_company_relationship,
    assigned_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        u.id,
        u.email,
        u.username,
        uc.relationship_type,
        uc.assigned_at
    FROM user_companies uc
    JOIN user_accounts u ON u.id = uc.user_id
    WHERE uc.company_id = p_company_id
      AND uc.is_active = TRUE
      AND (p_filter_type IS NULL OR uc.relationship_type = p_filter_type);
END;
$$ LANGUAGE plpgsql;

ALTER FUNCTION get_company_users(BIGINT, user_company_relationship) OWNER TO wellwon;

-- =============================================================================
-- DECLARANT MODULE: Reference Tables
-- =============================================================================

-- Шаблоны JSON форм документов (из Kontur API /common/v1/jsonTemplates)
-- Один documentModeId может иметь несколько вариантов typeName (410 записей, 145 уникальных форм)
CREATE TABLE IF NOT EXISTS dc_json_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gf_code TEXT NOT NULL,                       -- Внутренний код Kontur (например "18003")
    document_mode_id TEXT NOT NULL,              -- ID формы по альбому ФТС (например "1006107E")
    type_name TEXT NOT NULL,                     -- Название варианта шаблона
    is_active BOOLEAN DEFAULT TRUE,              -- Активен ли шаблон
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Уникальность по комбинации gf + documentModeId + typeName
    UNIQUE(gf_code, document_mode_id, type_name)
);

-- Индексы для dc_json_templates
CREATE INDEX IF NOT EXISTS idx_dc_json_templates_gf_code
    ON dc_json_templates(gf_code);
CREATE INDEX IF NOT EXISTS idx_dc_json_templates_document_mode_id
    ON dc_json_templates(document_mode_id);
CREATE INDEX IF NOT EXISTS idx_dc_json_templates_is_active
    ON dc_json_templates(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_dc_json_templates_type_name
    ON dc_json_templates USING gin(type_name gin_trgm_ops);

-- Триггер для updated_at
CREATE TRIGGER set_dc_json_templates_updated_at
    BEFORE UPDATE ON dc_json_templates
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- Комментарии
COMMENT ON TABLE dc_json_templates IS 'Справочник шаблонов JSON форм Kontur.Declarant (из /common/v1/jsonTemplates)';
COMMENT ON COLUMN dc_json_templates.gf_code IS 'Внутренний код Kontur (gf)';
COMMENT ON COLUMN dc_json_templates.document_mode_id IS 'ID формы по альбому форматов ФТС';
COMMENT ON COLUMN dc_json_templates.type_name IS 'Название варианта шаблона';

-- =============================================================================
-- DECLARANT MODULE: Form Definitions (Universal Form Generator)
-- =============================================================================

-- Определения форм (предобработанные схемы из Kontur API)
CREATE TABLE IF NOT EXISTS dc_form_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_mode_id VARCHAR(20) NOT NULL UNIQUE,   -- ID формы (например "1002007E")
    gf_code VARCHAR(20) NOT NULL,                   -- Внутренний код Kontur
    type_name VARCHAR(500) NOT NULL,                -- Название формы

    -- Обработанная структура формы
    fields JSONB NOT NULL DEFAULT '[]',             -- Массив определений полей
    default_values JSONB DEFAULT '{}',              -- Значения по умолчанию

    -- Оригинальная схема для отслеживания изменений
    kontur_schema_json JSONB,                       -- Исходная схема от Kontur
    kontur_schema_hash VARCHAR(64),                 -- SHA256 для сравнения

    -- Метаданные
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_form_definitions_document_mode
    ON dc_form_definitions(document_mode_id);
CREATE INDEX IF NOT EXISTS idx_dc_form_definitions_gf_code
    ON dc_form_definitions(gf_code);
CREATE INDEX IF NOT EXISTS idx_dc_form_definitions_is_active
    ON dc_form_definitions(is_active) WHERE is_active = TRUE;

CREATE TRIGGER set_dc_form_definitions_updated_at
    BEFORE UPDATE ON dc_form_definitions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_form_definitions IS 'Определения форм для универсального рендерера (из JSON схем Kontur)';
COMMENT ON COLUMN dc_form_definitions.fields IS 'JSONB массив определений полей формы';
COMMENT ON COLUMN dc_form_definitions.kontur_schema_json IS 'Оригинальная JSON схема от Kontur для отслеживания изменений';
COMMENT ON COLUMN dc_form_definitions.kontur_schema_hash IS 'SHA256 хеш схемы для быстрого сравнения при синхронизации';

-- Русские лейблы для полей форм (локализация)
CREATE TABLE IF NOT EXISTS dc_field_labels_ru (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    field_path VARCHAR(500) NOT NULL UNIQUE,        -- Путь поля: "ESADout_CUConsignee.EqualIndicator"
    label_ru VARCHAR(500) NOT NULL,                 -- Русское название: "Совпадает с декларантом"
    hint_ru VARCHAR(1000),                          -- Подсказка при наведении
    placeholder_ru VARCHAR(200),                    -- Placeholder в поле ввода
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_field_labels_path
    ON dc_field_labels_ru(field_path);
CREATE INDEX IF NOT EXISTS idx_dc_field_labels_path_prefix
    ON dc_field_labels_ru USING gin(field_path gin_trgm_ops);

CREATE TRIGGER set_dc_field_labels_ru_updated_at
    BEFORE UPDATE ON dc_field_labels_ru
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_field_labels_ru IS 'Русские лейблы для полей форм (локализация отдельно от схем)';

-- Секции форм (кастомная группировка полей в UI)
CREATE TABLE IF NOT EXISTS dc_form_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_definition_id UUID REFERENCES dc_form_definitions(id) ON DELETE CASCADE,

    section_key VARCHAR(100) NOT NULL,              -- Ключ секции: "organizations"
    title_ru VARCHAR(200) NOT NULL,                 -- Заголовок: "Организации"
    description_ru VARCHAR(500),                    -- Описание секции
    icon VARCHAR(50) DEFAULT 'FileText',            -- Имя иконки Lucide
    sort_order INTEGER DEFAULT 0,                   -- Порядок сортировки
    field_paths JSONB NOT NULL DEFAULT '[]',        -- Массив путей полей: ["sender.name", "sender.inn"]
    columns INTEGER DEFAULT 2,                      -- Количество колонок в grid
    collapsible BOOLEAN DEFAULT FALSE,              -- Можно ли сворачивать
    default_expanded BOOLEAN DEFAULT TRUE,          -- Развернуто по умолчанию

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(form_definition_id, section_key)
);

CREATE INDEX IF NOT EXISTS idx_dc_form_sections_definition
    ON dc_form_sections(form_definition_id);

CREATE TRIGGER set_dc_form_sections_updated_at
    BEFORE UPDATE ON dc_form_sections
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_form_sections IS 'Кастомные секции для группировки полей в UI формы';

-- История синхронизации форм (аудит)
CREATE TABLE IF NOT EXISTS dc_form_sync_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_mode_id VARCHAR(20),                   -- NULL для full sync
    sync_type VARCHAR(20) NOT NULL,                 -- 'full', 'single'
    status VARCHAR(20) NOT NULL,                    -- 'success', 'partial', 'failed'

    total_processed INTEGER DEFAULT 0,
    forms_created INTEGER DEFAULT 0,
    forms_updated INTEGER DEFAULT 0,
    schemas_changed INTEGER DEFAULT 0,              -- Количество изменившихся схем
    errors INTEGER DEFAULT 0,
    error_details JSONB,                            -- Массив ошибок

    sync_duration_ms INTEGER,                       -- Длительность синхронизации
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_form_sync_history_document
    ON dc_form_sync_history(document_mode_id);
CREATE INDEX IF NOT EXISTS idx_dc_form_sync_history_date
    ON dc_form_sync_history(synced_at DESC);

COMMENT ON TABLE dc_form_sync_history IS 'История синхронизации определений форм с Kontur API';

-- =============================================================================
-- DECLARANT MODULE: References from Kontur API
-- =============================================================================

-- Таможенные органы (из Kontur API GET /common/v1/options/customs)
CREATE TABLE IF NOT EXISTS dc_customs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kontur_id VARCHAR(100) NOT NULL UNIQUE,          -- ID из Kontur API
    code VARCHAR(20),                                 -- Код таможенного органа (8 цифр)
    short_name VARCHAR(200),                          -- Краткое название
    full_name VARCHAR(500),                           -- Полное название
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_customs_kontur_id ON dc_customs(kontur_id);
CREATE INDEX IF NOT EXISTS idx_dc_customs_code ON dc_customs(code);
CREATE INDEX IF NOT EXISTS idx_dc_customs_is_active ON dc_customs(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_dc_customs_name ON dc_customs USING gin(short_name gin_trgm_ops);

CREATE TRIGGER set_dc_customs_updated_at
    BEFORE UPDATE ON dc_customs
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_customs IS 'Справочник таможенных органов (из Kontur API /common/v1/options/customs)';


-- Типы деклараций / Направления перемещения (из Kontur API GET /common/v1/options/declarationTypes)
CREATE TABLE IF NOT EXISTS dc_declaration_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kontur_id INTEGER NOT NULL UNIQUE,               -- ID из Kontur API (числовой)
    description VARCHAR(200) NOT NULL,               -- Описание (ИМ, ЭК, ПИ и т.д.)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_declaration_types_kontur_id ON dc_declaration_types(kontur_id);
CREATE INDEX IF NOT EXISTS idx_dc_declaration_types_is_active ON dc_declaration_types(is_active) WHERE is_active = TRUE;

CREATE TRIGGER set_dc_declaration_types_updated_at
    BEFORE UPDATE ON dc_declaration_types
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_declaration_types IS 'Справочник типов деклараций / направлений перемещения (из Kontur API /common/v1/options/declarationTypes)';


-- Таможенные процедуры (из Kontur API GET /common/v1/options/declarationProcedureTypes)
CREATE TABLE IF NOT EXISTS dc_procedures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kontur_id INTEGER NOT NULL,                      -- ID из Kontur API (числовой)
    declaration_type_id INTEGER NOT NULL,            -- К какому типу декларации относится (foreign key на kontur_id)
    code VARCHAR(10) NOT NULL,                       -- Код процедуры (40, 10 и т.д.)
    name VARCHAR(500) NOT NULL,                      -- Название процедуры
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(kontur_id, declaration_type_id)
);

CREATE INDEX IF NOT EXISTS idx_dc_procedures_kontur_id ON dc_procedures(kontur_id);
CREATE INDEX IF NOT EXISTS idx_dc_procedures_declaration_type ON dc_procedures(declaration_type_id);
CREATE INDEX IF NOT EXISTS idx_dc_procedures_code ON dc_procedures(code);
CREATE INDEX IF NOT EXISTS idx_dc_procedures_is_active ON dc_procedures(is_active) WHERE is_active = TRUE;

CREATE TRIGGER set_dc_procedures_updated_at
    BEFORE UPDATE ON dc_procedures
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_procedures IS 'Справочник таможенных процедур (из Kontur API /common/v1/options/declarationProcedureTypes)';


-- Группы упаковки (статический справочник)
CREATE TABLE IF NOT EXISTS dc_packaging_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_packaging_groups_code ON dc_packaging_groups(code);
CREATE INDEX IF NOT EXISTS idx_dc_packaging_groups_is_active ON dc_packaging_groups(is_active) WHERE is_active = TRUE;

CREATE TRIGGER set_dc_packaging_groups_updated_at
    BEFORE UPDATE ON dc_packaging_groups
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_packaging_groups IS 'Справочник групп упаковки';


-- Валюты (статический справочник)
CREATE TABLE IF NOT EXISTS dc_currencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(10) NOT NULL UNIQUE,           -- Цифровой код (643, 840, etc.)
    alpha_code VARCHAR(3) NOT NULL,              -- Буквенный код (RUB, USD, etc.)
    name VARCHAR(200) NOT NULL,                  -- Название валюты
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_currencies_code ON dc_currencies(code);
CREATE INDEX IF NOT EXISTS idx_dc_currencies_alpha_code ON dc_currencies(alpha_code);
CREATE INDEX IF NOT EXISTS idx_dc_currencies_is_active ON dc_currencies(is_active) WHERE is_active = TRUE;

CREATE TRIGGER set_dc_currencies_updated_at
    BEFORE UPDATE ON dc_currencies
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_currencies IS 'Справочник валют';


-- Категории предприятий (статический справочник)
CREATE TABLE IF NOT EXISTS dc_enterprise_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(1000) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_enterprise_categories_code ON dc_enterprise_categories(code);
CREATE INDEX IF NOT EXISTS idx_dc_enterprise_categories_is_active ON dc_enterprise_categories(is_active) WHERE is_active = TRUE;

CREATE TRIGGER set_dc_enterprise_categories_updated_at
    BEFORE UPDATE ON dc_enterprise_categories
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_enterprise_categories IS 'Справочник категорий предприятий';


-- Единицы измерения (статический справочник)
CREATE TABLE IF NOT EXISTS dc_measurement_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(10) NOT NULL UNIQUE,
    short_name VARCHAR(50) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_measurement_units_code ON dc_measurement_units(code);
CREATE INDEX IF NOT EXISTS idx_dc_measurement_units_is_active ON dc_measurement_units(is_active) WHERE is_active = TRUE;

CREATE TRIGGER set_dc_measurement_units_updated_at
    BEFORE UPDATE ON dc_measurement_units
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_measurement_units IS 'Справочник единиц измерения';


-- Виды документов (статический справочник)
CREATE TABLE IF NOT EXISTS dc_document_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(10) NOT NULL UNIQUE,            -- Код документа (01011, 02011, etc.)
    name TEXT NOT NULL,                          -- Наименование документа
    ed_documents TEXT,                           -- ЭД-документы (типы электронных документов)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_document_types_code ON dc_document_types(code);
CREATE INDEX IF NOT EXISTS idx_dc_document_types_is_active ON dc_document_types(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_dc_document_types_name ON dc_document_types USING gin(name gin_trgm_ops);

CREATE TRIGGER set_dc_document_types_updated_at
    BEFORE UPDATE ON dc_document_types
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_document_types IS 'Справочник видов документов';


-- =============================================================================
-- INITIAL DATA
-- =============================================================================

-- Insert initial schema migration record
INSERT INTO schema_migrations (version, description, applied_by)
VALUES ('1.0.0', 'Initial WellWon schema with ES infrastructure', 'system')
ON CONFLICT (version) DO NOTHING;

-- =============================================================================
-- END OF SCHEMA
-- =============================================================================
