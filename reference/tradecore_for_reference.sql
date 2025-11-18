-- =============================================================================
-- TradeCore v0.8.1 — Complete PostgreSQL Schema with Position Domain + Pyramiding
-- FULLY ENHANCED VERSION + Performance Indexes for Date Range Queries
-- =============================================================================
-- Features:
-- - UUIDs for primary keys
-- - Event sourcing, projections, idempotency, DLQ, audit
-- - Support for real brokers (Alpaca, TradeStation, Interactive Brokers, etc.)
-- - Enhanced account_transactions with full audit trail
-- - Comprehensive event store and transport integration
-- - POSITION DOMAIN with full pyramiding support (position scaling)
-- - AUTOMATION DOMAIN with pyramiding configuration
-- - 4 position tables: positions, position_entries, position_exits, position_pnl_history
-- =============================================================================

-- ======================
-- EXTENSIONS
-- ======================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- for gen_random_uuid()

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

-- ======================
-- USER_ACCOUNTS TABLE (Enhanced)
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

    -- Enhanced event sourcing support
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

DROP TRIGGER IF EXISTS set_user_accounts_password_change ON user_accounts;
CREATE TRIGGER set_user_accounts_password_change
    BEFORE UPDATE ON user_accounts
    FOR EACH ROW EXECUTE FUNCTION trigger_password_change();

-- ======================
-- BROKER CONNECTIONS (Enhanced with Saga Support)
-- ======================
CREATE TABLE IF NOT EXISTS broker_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    broker_id TEXT NOT NULL,
    environment TEXT NOT NULL,

    -- Encrypted credentials
    refresh_token TEXT,
    access_token TEXT,
    client_id TEXT,
    client_secret TEXT,
    api_key TEXT,
    api_secret TEXT,

    access_token_expires_at TIMESTAMP WITH TIME ZONE,
    api_endpoint TEXT,

    connected BOOLEAN DEFAULT FALSE,
    last_connection_status TEXT,
    last_status_reason TEXT,
    last_connected_at TIMESTAMP WITH TIME ZONE,
    last_heartbeat_at TIMESTAMP WITH TIME ZONE,
    connection_instance_id UUID,
    scopes TEXT[],
    last_error JSONB,
    reauth_required BOOLEAN DEFAULT FALSE,

    -- Grace period fields
    disconnected_at TIMESTAMP WITH TIME ZONE,
    grace_period_ends_at TIMESTAMP WITH TIME ZONE,
    disconnect_reason TEXT,

    -- Enhanced event sourcing support
    aggregate_version INTEGER DEFAULT 1,
    last_event_sequence BIGINT,
    last_saga_id UUID,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, broker_id, environment)
);

-- Enhanced indexes for broker_connections
CREATE INDEX IF NOT EXISTS idx_broker_connections_user_broker ON broker_connections(user_id, broker_id);
CREATE INDEX IF NOT EXISTS idx_broker_connections_connected ON broker_connections(connected) WHERE connected = true;
CREATE INDEX IF NOT EXISTS idx_broker_connections_grace_period ON broker_connections(grace_period_ends_at)
    WHERE connected = false AND grace_period_ends_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_broker_connections_disconnected ON broker_connections(disconnected_at) WHERE connected = false;
CREATE INDEX IF NOT EXISTS idx_broker_connections_version ON broker_connections(aggregate_version);
CREATE INDEX IF NOT EXISTS idx_broker_connections_saga ON broker_connections(last_saga_id) WHERE last_saga_id IS NOT NULL;

DROP TRIGGER IF EXISTS set_broker_connections_updated_at ON broker_connections;
CREATE TRIGGER set_broker_connections_updated_at
    BEFORE UPDATE ON broker_connections
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ======================
-- BROKER ACCOUNTS (Enhanced with Event Sourcing and Required Connection ID)
-- ======================
-- FIXED: Removed DROP TABLE to preserve data on restart
-- Changed to CREATE IF NOT EXISTS for idempotency

CREATE TABLE IF NOT EXISTS broker_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    broker_connection_id UUID NOT NULL REFERENCES broker_connections(id) ON DELETE CASCADE,  -- CHANGED: Made NOT NULL
    broker_id TEXT NOT NULL,
    environment TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    broker_account_id TEXT NOT NULL,
    account_name TEXT,
    balance NUMERIC DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    equity NUMERIC,
    buying_power NUMERIC,
    status TEXT,
    metadata JSONB,
    deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    archived BOOLEAN DEFAULT FALSE,
    archived_at TIMESTAMP WITH TIME ZONE,
    account_type TEXT,
    parent_account_id UUID,
    last_synced_at TIMESTAMP WITH TIME ZONE,

    -- Enhanced event sourcing support
    aggregate_version INTEGER DEFAULT 1,
    last_event_sequence BIGINT,
    last_saga_id UUID,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uniq_user_broker_env_account UNIQUE (user_id, broker_id, environment, broker_account_id)
);

-- Enhanced indexes for broker_accounts
CREATE INDEX IF NOT EXISTS idx_broker_accounts_user_id ON broker_accounts (user_id);
CREATE INDEX IF NOT EXISTS idx_broker_accounts_broker_connection_id ON broker_accounts (broker_connection_id);
CREATE INDEX IF NOT EXISTS idx_broker_accounts_broker_id ON broker_accounts(broker_id);
CREATE INDEX IF NOT EXISTS idx_broker_accounts_version ON broker_accounts(aggregate_version);
CREATE INDEX IF NOT EXISTS idx_broker_accounts_saga ON broker_accounts(last_saga_id) WHERE last_saga_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_broker_accounts_deleted ON broker_accounts(deleted) WHERE deleted = true;
CREATE INDEX IF NOT EXISTS idx_broker_accounts_deleted_at ON broker_accounts(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_broker_accounts_archived ON broker_accounts(archived) WHERE archived = true;
CREATE INDEX IF NOT EXISTS idx_broker_accounts_archived_at ON broker_accounts(archived_at) WHERE archived_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_broker_accounts_metadata ON broker_accounts USING GIN (metadata);

-- Function for updated_at trigger
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Updated trigger for broker_accounts
DROP TRIGGER IF EXISTS set_broker_accounts_updated_at ON broker_accounts;
CREATE TRIGGER set_broker_accounts_updated_at
    BEFORE UPDATE ON broker_accounts
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- Trigger to automatically set deleted_at and archived_at timestamps
CREATE OR REPLACE FUNCTION set_deletion_archive_timestamps()
RETURNS TRIGGER AS $$
BEGIN
    -- Handle deleted flag changes
    IF NEW.deleted = TRUE AND OLD.deleted = FALSE THEN
        NEW.deleted_at = CURRENT_TIMESTAMP;
    ELSIF NEW.deleted = FALSE AND OLD.deleted = TRUE THEN
        NEW.deleted_at = NULL;
    END IF;

    -- Handle archived flag changes
    IF NEW.archived = TRUE AND OLD.archived = FALSE THEN
        NEW.archived_at = CURRENT_TIMESTAMP;
    ELSIF NEW.archived = FALSE AND OLD.archived = TRUE THEN
        NEW.archived_at = NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_broker_accounts_deletion_archive ON broker_accounts;
CREATE TRIGGER set_broker_accounts_deletion_archive
BEFORE UPDATE ON broker_accounts
FOR EACH ROW EXECUTE FUNCTION set_deletion_archive_timestamps();

-- ======================
-- AUTOMATIONS - Trading Automations with Derivatives Support
-- ======================
-- DROP old tables for clean migration (no migration scripts needed)
DROP TABLE IF EXISTS webhook_logs CASCADE;
DROP TABLE IF EXISTS webhooks CASCADE;
DROP TABLE IF EXISTS automations CASCADE;

-- CREATE new automations table with full derivatives support
CREATE TABLE IF NOT EXISTS automations (
    -- Primary Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'inactive',  -- active, inactive, paused, suspended, error

    -- Webhook Configuration
    webhook_token TEXT NOT NULL UNIQUE,
    webhook_url TEXT NOT NULL,
    webhook_allowed_ips TEXT[] DEFAULT '{}',
    webhook_rate_limit INTEGER DEFAULT 60,
    webhook_created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    webhook_rotated_at TIMESTAMP WITH TIME ZONE,

    -- DERIVATIVES SUPPORT (17 flattened fields)
    asset_type TEXT NOT NULL DEFAULT 'stock',  -- stock, option, future, future_option

    -- Option fields (7)
    option_underlying_symbol TEXT,
    option_strike_price NUMERIC(20, 8),
    option_expiration_date TIMESTAMP WITH TIME ZONE,
    option_type TEXT,  -- call, put
    option_action TEXT,  -- buy_to_open, buy_to_close, sell_to_open, sell_to_close
    option_contract_size INTEGER,
    option_multiplier NUMERIC(20, 8),

    -- Future fields (9)
    future_underlying_symbol TEXT,
    future_contract_month TEXT,
    future_expiration_date TIMESTAMP WITH TIME ZONE,
    future_contract_size NUMERIC(20, 8),
    future_tick_size NUMERIC(20, 8),
    future_tick_value NUMERIC(20, 8),
    future_multiplier NUMERIC(20, 8),
    future_exchange TEXT,
    future_product_code TEXT,

    -- POSITION SIZING (structured, not JSONB)
    position_sizing_type TEXT NOT NULL,  -- fixed, amount_per_position, risk_per_position, percent_of_equity
    fixed_quantity NUMERIC(20, 8),
    amount_per_position NUMERIC(20, 8),
    risk_per_position NUMERIC(20, 8),
    percent_of_equity NUMERIC(10, 4),
    use_buying_power BOOLEAN DEFAULT FALSE,

    -- SIDE PREFERENCE
    side_preference TEXT DEFAULT 'both',  -- long, short, both

    -- STOP LOSS (structured)
    stop_loss_type TEXT,  -- fixed_price, dollar_amount, percentage, atr
    stop_loss_price NUMERIC(20, 8),
    stop_loss_dollar_amount NUMERIC(20, 8),
    stop_loss_percentage NUMERIC(10, 4),
    stop_loss_atr_multiplier NUMERIC(10, 4),
    stop_loss_atr_period INTEGER,
    stop_loss_trailing BOOLEAN DEFAULT FALSE,
    stop_loss_trail_amount NUMERIC(20, 8),
    stop_loss_trail_percentage NUMERIC(10, 4),

    -- TAKE PROFIT (structured)
    take_profit_type TEXT,  -- fixed_price, dollar_amount, percentage, risk_reward
    take_profit_price NUMERIC(20, 8),
    take_profit_dollar_amount NUMERIC(20, 8),
    take_profit_percentage NUMERIC(10, 4),
    take_profit_risk_reward_ratio NUMERIC(10, 4),

    -- ORDER PREFERENCES
    entry_order_type TEXT DEFAULT 'market',  -- market, limit, stop, stop_limit
    exit_order_type TEXT DEFAULT 'market',

    -- AUTO-SUBMIT
    auto_submit BOOLEAN DEFAULT TRUE,

    -- ADD TO POSITION CONTROL (base permission)
    allow_add_to_position BOOLEAN DEFAULT TRUE,  -- Allow adding to existing positions (DCA, pyramiding, etc.)

    -- PYRAMIDING CONFIGURATION (Position Scaling)
    pyramiding_enabled BOOLEAN DEFAULT TRUE,
    max_pyramid_entries INTEGER DEFAULT 5,
    pyramid_size_factor NUMERIC(5,4) DEFAULT 0.5,  -- 50% reduction per entry
    min_profit_to_pyramid NUMERIC(10,4) DEFAULT 0.02,  -- 2% minimum profit
    min_spacing_percentage NUMERIC(10,4) DEFAULT 0.03,  -- 3% minimum spacing
    move_stop_on_pyramid BOOLEAN DEFAULT TRUE,
    breakeven_after_pyramid INTEGER DEFAULT 2,  -- Move to breakeven after 2nd entry

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP WITH TIME ZONE,
    deactivated_at TIMESTAMP WITH TIME ZONE,
    suspended_at TIMESTAMP WITH TIME ZONE,

    -- Event Sourcing
    aggregate_version INTEGER DEFAULT 1,
    last_event_sequence BIGINT,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Constraints
    CONSTRAINT valid_asset_type CHECK (asset_type IN ('stock', 'option', 'future', 'future_option', 'crypto')),
    CONSTRAINT valid_status CHECK (status IN ('active', 'inactive', 'paused', 'suspended', 'error')),
    CONSTRAINT valid_position_sizing_type CHECK (position_sizing_type IN ('fixed', 'amount_per_position', 'risk_per_position', 'percent_of_equity')),
    CONSTRAINT valid_side_preference CHECK (side_preference IN ('long', 'short', 'both')),

    -- Derivative validation constraints
    CONSTRAINT option_details_required CHECK (
        (asset_type IN ('option', 'future_option') AND option_underlying_symbol IS NOT NULL) OR
        (asset_type NOT IN ('option', 'future_option'))
    ),
    CONSTRAINT future_details_required CHECK (
        (asset_type IN ('future', 'future_option') AND future_underlying_symbol IS NOT NULL) OR
        (asset_type NOT IN ('future', 'future_option'))
    ),

    -- Position sizing validation
    CONSTRAINT position_sizing_fixed CHECK (
        (position_sizing_type = 'fixed' AND fixed_quantity IS NOT NULL) OR
        (position_sizing_type != 'fixed')
    ),
    CONSTRAINT position_sizing_amount CHECK (
        (position_sizing_type = 'amount_per_position' AND amount_per_position IS NOT NULL) OR
        (position_sizing_type != 'amount_per_position')
    ),
    CONSTRAINT position_sizing_risk CHECK (
        (position_sizing_type = 'risk_per_position' AND risk_per_position IS NOT NULL) OR
        (position_sizing_type != 'risk_per_position')
    ),
    CONSTRAINT position_sizing_percent CHECK (
        (position_sizing_type = 'percent_of_equity' AND percent_of_equity IS NOT NULL) OR
        (position_sizing_type != 'percent_of_equity')
    )
);

-- Indexes for automations
CREATE INDEX IF NOT EXISTS idx_automations_user_id ON automations (user_id);
CREATE INDEX IF NOT EXISTS idx_automations_status ON automations (status);
CREATE INDEX IF NOT EXISTS idx_automations_asset_type ON automations (asset_type);
CREATE INDEX IF NOT EXISTS idx_automations_symbol ON automations (symbol);
CREATE INDEX IF NOT EXISTS idx_automations_webhook_token ON automations (webhook_token);
CREATE INDEX IF NOT EXISTS idx_automations_version ON automations (aggregate_version);

-- Updated_at trigger
DROP TRIGGER IF EXISTS set_automations_updated_at ON automations;
CREATE TRIGGER set_automations_updated_at
    BEFORE UPDATE ON automations
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE automations IS 'Trading automations with TradersPost webhook support and full derivatives (stocks, options, futures)';
COMMENT ON COLUMN automations.asset_type IS 'Asset type: stock, option, future, future_option';
COMMENT ON COLUMN automations.position_sizing_type IS 'Position sizing method: fixed, amount_per_position, risk_per_position, percent_of_equity';
COMMENT ON COLUMN automations.status IS 'Automation status: active (accepting signals), inactive, paused, suspended (risk limit), error';
COMMENT ON COLUMN automations.webhook_token IS 'Secure random token for webhook authentication (32 bytes urlsafe)';

-- ======================
-- AUTOMATION_BROKER_ACCOUNTS (Junction Table for Multi-Account Support)
-- ======================
CREATE TABLE IF NOT EXISTS automation_broker_accounts (
    automation_id UUID NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- Order of routing (lower number = higher priority)
    routing_order INTEGER DEFAULT 0,

    -- Per-account overrides (optional)
    position_size_override NUMERIC(20, 8),
    disabled BOOLEAN DEFAULT FALSE,

    -- Timestamps
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (automation_id, account_id)
);

CREATE INDEX IF NOT EXISTS idx_automation_broker_accounts_automation ON automation_broker_accounts (automation_id);
CREATE INDEX IF NOT EXISTS idx_automation_broker_accounts_broker ON automation_broker_accounts (account_id);

COMMENT ON TABLE automation_broker_accounts IS 'Junction table linking automations to multiple broker accounts for routing';

-- ======================
-- WEBHOOK_SIGNALS (Signal Audit Trail with Derivatives)
-- ======================
CREATE TABLE IF NOT EXISTS webhook_signals (
    -- Primary Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    automation_id UUID NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,

    -- Signal Action
    action TEXT NOT NULL,  -- buy, sell, exit, close, cancel, add
    symbol TEXT NOT NULL,

    -- DERIVATIVES (17 flattened fields)
    asset_type TEXT NOT NULL DEFAULT 'stock',

    -- Option fields (7)
    option_underlying_symbol TEXT,
    option_strike_price NUMERIC(20, 8),
    option_expiration_date TIMESTAMP WITH TIME ZONE,
    option_type TEXT,
    option_action TEXT,
    option_contract_size INTEGER,
    option_multiplier NUMERIC(20, 8),

    -- Future fields (9)
    future_underlying_symbol TEXT,
    future_contract_month TEXT,
    future_expiration_date TIMESTAMP WITH TIME ZONE,
    future_contract_size NUMERIC(20, 8),
    future_tick_size NUMERIC(20, 8),
    future_tick_value NUMERIC(20, 8),
    future_multiplier NUMERIC(20, 8),
    future_exchange TEXT,
    future_product_code TEXT,

    -- Signal Data
    quantity NUMERIC(20, 8),
    order_type TEXT,
    price NUMERIC(20, 8),
    stop_loss NUMERIC(20, 8),
    take_profit NUMERIC(20, 8),

    -- Processing Status
    status TEXT NOT NULL DEFAULT 'received',  -- received, processed, rejected
    rejection_reason TEXT,
    rejection_code TEXT,

    -- Processing Result
    calculated_quantity NUMERIC(20, 8),
    position_sizing_method TEXT,
    order_ids UUID[],  -- Created order IDs
    processing_time_ms INTEGER,

    -- Source Tracking
    source_ip TEXT NOT NULL,
    raw_signal_json JSONB NOT NULL,

    -- Timestamps
    received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Constraints
    CONSTRAINT valid_signal_action CHECK (action IN ('buy', 'sell', 'exit', 'close', 'cancel', 'add')),
    CONSTRAINT valid_signal_status CHECK (status IN ('received', 'processed', 'rejected')),
    CONSTRAINT valid_signal_asset_type CHECK (asset_type IN ('stock', 'option', 'future', 'future_option', 'crypto'))
);

CREATE INDEX IF NOT EXISTS idx_webhook_signals_automation ON webhook_signals (automation_id);
CREATE INDEX IF NOT EXISTS idx_webhook_signals_user ON webhook_signals (user_id);
CREATE INDEX IF NOT EXISTS idx_webhook_signals_status ON webhook_signals (status);
CREATE INDEX IF NOT EXISTS idx_webhook_signals_received_at ON webhook_signals (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_webhook_signals_asset_type ON webhook_signals (asset_type);
CREATE INDEX IF NOT EXISTS idx_webhook_signals_action ON webhook_signals (action);

COMMENT ON TABLE webhook_signals IS 'Audit trail of webhook signals received and processed with derivatives support';
COMMENT ON COLUMN webhook_signals.raw_signal_json IS 'Complete TradersPost webhook payload for debugging';
COMMENT ON COLUMN webhook_signals.processing_time_ms IS 'Time taken to process signal in milliseconds';

-- ======================
-- WEBHOOKS LOGS (Enhanced)
-- ======================
CREATE TABLE IF NOT EXISTS webhook_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    webhook_id UUID,
    automation_id UUID,
    payload JSONB NOT NULL,
    status TEXT,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,
    error TEXT,

    -- Enhanced tracking
    saga_id UUID,
    causation_id UUID,
    correlation_id UUID,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_webhook_logs_user_id ON webhook_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_automation_id ON webhook_logs (automation_id);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_saga_id ON webhook_logs (saga_id) WHERE saga_id IS NOT NULL;

-- ======================
-- ORDERS (Enhanced with Event Sourcing)
-- ======================
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    automation_id UUID REFERENCES automations(id) ON DELETE SET NULL,
    position_id UUID,  -- Link to position (set after position creation)
    broker_order_id TEXT,
    client_order_id TEXT UNIQUE,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    action TEXT NOT NULL,
    side TEXT,  -- Standardized: 'buy' or 'sell'
    quantity NUMERIC NOT NULL,
    order_type TEXT NOT NULL,
    time_in_force TEXT,
    limit_price NUMERIC,
    price NUMERIC,  -- Alias for limit_price, used by OrderReadModel
    stop_price NUMERIC,
    trail_price NUMERIC,
    trail_percent NUMERIC,
    status TEXT NOT NULL,
    broker_status TEXT,  -- Hybrid model: raw broker status for frontend display (Alpaca: "new"/"accepted", TradeStation: "Received"/"Filled")
    filled_quantity NUMERIC DEFAULT 0,
    remaining_quantity NUMERIC,  -- TradersPost: quantity remaining
    average_fill_price NUMERIC,
    commission NUMERIC,
    commission_asset TEXT,
    total_commission NUMERIC DEFAULT 0,  -- Aggregated commission for queries
    total_fees NUMERIC DEFAULT 0,  -- Aggregated fees for queries
    payload_request JSONB,
    metadata JSONB,
    broker_response JSONB,
    route_info JSONB,
    fees JSONB,
    cancel_reason TEXT,
    submitted_at TIMESTAMP WITH TIME ZONE,
    accepted_at TIMESTAMP WITH TIME ZONE,  -- When broker accepted order
    cancelled_at TIMESTAMP WITH TIME ZONE,
    filled_at TIMESTAMP WITH TIME ZONE,
    rejected_at TIMESTAMP WITH TIME ZONE,
    expired_at TIMESTAMP WITH TIME ZONE,
    failed_at TIMESTAMP WITH TIME ZONE,
    replaced_at TIMESTAMP WITH TIME ZONE,
    cancel_requested_at TIMESTAMP WITH TIME ZONE,
    modified_at TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,
    notes TEXT,
    parent_order_id UUID,
    replaced_by_order_id UUID,
    replaces_order_id UUID,
    updated_by_automation_id UUID,
    order_source TEXT,
    external_order_id TEXT,

    -- =======================================================================
    -- OPTIONS & FUTURES SUPPORT
    -- =======================================================================
    -- Option contract fields (only populated when asset_type = 'option' or 'future_option')
    option_underlying_symbol TEXT,
    option_strike_price NUMERIC,
    option_expiration_date TIMESTAMP WITH TIME ZONE,
    option_type TEXT,  -- 'call' or 'put'
    option_action TEXT,  -- 'buy_to_open', 'buy_to_close', 'sell_to_open', 'sell_to_close'
    option_contract_size INTEGER DEFAULT 100,
    option_multiplier NUMERIC DEFAULT 1,

    -- Future contract fields (only populated when asset_type = 'future' or 'future_option')
    future_underlying_symbol TEXT,
    future_contract_month TEXT,  -- e.g., '202503' or 'M25'
    future_expiration_date TIMESTAMP WITH TIME ZONE,
    future_contract_size NUMERIC,
    future_tick_size NUMERIC,
    future_tick_value NUMERIC,
    future_multiplier NUMERIC DEFAULT 1,
    future_exchange TEXT,  -- 'CME', 'CBOT', etc.
    future_product_code TEXT,

    -- TradersPost-compatible bracket orders
    extended_hours BOOLEAN DEFAULT false,
    bracket_type TEXT,  -- 'entry', 'stop_loss', 'take_profit'
    bracket_group_id UUID,  -- Links related bracket orders
    total_value NUMERIC,  -- Total order value
    net_proceeds NUMERIC,  -- Net proceeds after fills

    -- Enhanced event sourcing support
    aggregate_version INTEGER DEFAULT 1,
    last_event_sequence BIGINT,
    last_saga_id UUID,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT orders_side_check CHECK (side IN ('buy', 'sell') OR action IN ('buy', 'sell')),
    CONSTRAINT orders_bracket_type_check CHECK (bracket_type IS NULL OR bracket_type IN ('entry', 'stop_loss', 'take_profit')),
    CONSTRAINT orders_asset_type_check CHECK (asset_type IN ('stock', 'option', 'future', 'future_option', 'crypto')),
    CONSTRAINT orders_option_type_check CHECK (option_type IS NULL OR option_type IN ('call', 'put')),
    CONSTRAINT orders_option_action_check CHECK (option_action IS NULL OR option_action IN ('buy_to_open', 'buy_to_close', 'sell_to_open', 'sell_to_close'))
);

-- Enhanced indexes for orders
CREATE INDEX IF NOT EXISTS idx_orders_user_account ON orders (user_id, account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);
CREATE INDEX IF NOT EXISTS idx_orders_broker_order_id ON orders (broker_order_id) WHERE broker_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_client_order_id ON orders (client_order_id) WHERE client_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_version ON orders(aggregate_version);
CREATE INDEX IF NOT EXISTS idx_orders_saga ON orders(last_saga_id) WHERE last_saga_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_metadata ON orders USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_orders_automation_status ON orders(automation_id, status) WHERE automation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_position ON orders(position_id) WHERE position_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_symbol_status ON orders(symbol, status);
CREATE INDEX IF NOT EXISTS idx_orders_bracket_group ON orders(bracket_group_id) WHERE bracket_group_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_side ON orders(side) WHERE side IS NOT NULL;
-- Indexes for universal broker support (Alpaca, TradeStation, etc.)
CREATE INDEX IF NOT EXISTS idx_orders_failed_at ON orders(failed_at) WHERE failed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_replaced_at ON orders(replaced_at) WHERE replaced_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_cancel_requested_at ON orders(cancel_requested_at) WHERE cancel_requested_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_replaced_by ON orders(replaced_by_order_id) WHERE replaced_by_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_replaces ON orders(replaces_order_id) WHERE replaces_order_id IS NOT NULL;
-- Indexes for options/futures
CREATE INDEX IF NOT EXISTS idx_orders_asset_type ON orders(asset_type);
CREATE INDEX IF NOT EXISTS idx_orders_option_underlying ON orders(option_underlying_symbol) WHERE option_underlying_symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_option_expiration ON orders(option_expiration_date) WHERE option_expiration_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_future_underlying ON orders(future_underlying_symbol) WHERE future_underlying_symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_future_contract_month ON orders(future_contract_month) WHERE future_contract_month IS NOT NULL;
-- Performance indexes for date range queries
CREATE INDEX IF NOT EXISTS idx_orders_user_created_at ON orders(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_account_created_at ON orders(account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status_created_at ON orders(status, created_at ASC);

-- Trigger to sync payload_request with metadata
CREATE OR REPLACE FUNCTION sync_orders_metadata()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
        -- If payload_request is updated, sync to metadata
        IF NEW.payload_request IS NOT NULL AND (NEW.metadata IS NULL OR NEW.metadata = '{}'::jsonb) THEN
            NEW.metadata = NEW.payload_request;
        END IF;
        -- If metadata is updated, sync to payload_request
        IF NEW.metadata IS NOT NULL AND (NEW.payload_request IS NULL OR NEW.payload_request = '{}'::jsonb) THEN
            NEW.payload_request = NEW.metadata;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS orders_metadata_sync ON orders;
CREATE TRIGGER orders_metadata_sync
BEFORE INSERT OR UPDATE ON orders
FOR EACH ROW EXECUTE FUNCTION sync_orders_metadata();

DROP TRIGGER IF EXISTS set_orders_updated_at ON orders;
CREATE TRIGGER set_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ======================
-- TRADES / FILLS (Enhanced)
-- ======================
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    broker_trade_id TEXT,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    price NUMERIC NOT NULL,
    commission NUMERIC,
    commission_asset TEXT,
    liquidity TEXT,
    execution_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    trade_source TEXT,
    external_trade_id TEXT,
    metadata JSONB,

    -- Enhanced event sourcing support
    aggregate_version INTEGER DEFAULT 1,
    last_event_sequence BIGINT,
    last_saga_id UUID,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (broker_trade_id, account_id)
);

-- Enhanced indexes for trades
CREATE INDEX IF NOT EXISTS idx_trades_order_id ON trades (order_id);
CREATE INDEX IF NOT EXISTS idx_trades_user_account_time ON trades (user_id, account_id, execution_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_version ON trades(aggregate_version);
CREATE INDEX IF NOT EXISTS idx_trades_saga ON trades(last_saga_id) WHERE last_saga_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trades_metadata ON trades USING GIN (metadata);

-- ======================
-- POSITIONS (Full Pyramiding Support)
-- ======================
CREATE TABLE IF NOT EXISTS positions (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    strategy_id UUID REFERENCES automations(id) ON DELETE SET NULL,

    -- Asset
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK (
        asset_type IN ('stock', 'crypto', 'option', 'future', 'future_option')
    ),
    side TEXT NOT NULL CHECK (side IN ('long', 'short')),

    -- Position Sizing
    quantity NUMERIC(20,8) NOT NULL DEFAULT 0,
    initial_quantity NUMERIC(20,8) NOT NULL,  -- First entry quantity
    max_quantity NUMERIC(20,8) NOT NULL,      -- Peak quantity reached

    -- Price Tracking
    average_entry_price NUMERIC(20,8) NOT NULL,
    first_entry_price NUMERIC(20,8) NOT NULL,
    last_entry_price NUMERIC(20,8),
    current_price NUMERIC(20,8),

    -- P&L
    unrealized_pnl NUMERIC(20,8) DEFAULT 0,
    realized_pnl NUMERIC(20,8) DEFAULT 0,
    total_pnl NUMERIC(20,8) DEFAULT 0,
    pnl_percentage NUMERIC(10,4) DEFAULT 0,
    commissions_paid NUMERIC(20,8) DEFAULT 0,

    --  PYRAMIDING TRACKING
    pyramiding_count INTEGER DEFAULT 1,         -- Number of entries (1 = no pyramid)
    max_pyramiding_allowed INTEGER DEFAULT 5,   -- Strategy limit
    pyramiding_enabled BOOLEAN DEFAULT TRUE,
    pyramiding_size_factor NUMERIC(5,4) DEFAULT 0.5,  -- 50% reduction
    last_pyramid_at TIMESTAMPTZ,

    -- Risk Management
    stop_loss_price NUMERIC(20,8),
    stop_loss_type TEXT CHECK (
        stop_loss_type IS NULL OR
        stop_loss_type IN ('fixed', 'trailing', 'percentage', 'atr')
    ),
    take_profit_price NUMERIC(20,8),
    trailing_stop_distance NUMERIC(20,8),
    risk_amount NUMERIC(20,8) DEFAULT 0,

    -- State
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'opening', 'open', 'closing', 'closed')
    ) DEFAULT 'open',
    close_reason TEXT,

    -- 🔄 BROKER RECONCILIATION
    broker_quantity NUMERIC(20,8),
    broker_average_price NUMERIC(20,8),
    last_sync_at TIMESTAMPTZ,
    sync_discrepancy BOOLEAN DEFAULT FALSE,

    -- Timestamps
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Event Sourcing
    aggregate_version INTEGER DEFAULT 1,
    last_event_sequence BIGINT,
    last_saga_id UUID,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for positions
CREATE INDEX IF NOT EXISTS idx_positions_user_account ON positions(user_id, account_id);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status) WHERE status != 'closed';
CREATE INDEX IF NOT EXISTS idx_positions_strategy ON positions(strategy_id) WHERE strategy_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_positions_pyramiding ON positions(pyramiding_count) WHERE pyramiding_count > 1;

-- Unique constraint: only one open position per symbol per account
CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_unique_open_symbol
    ON positions(user_id, account_id, symbol)
    WHERE status IN ('open', 'opening');
CREATE INDEX IF NOT EXISTS idx_positions_version ON positions(aggregate_version);
CREATE INDEX IF NOT EXISTS idx_positions_saga ON positions(last_saga_id) WHERE last_saga_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_positions_metadata ON positions USING GIN (metadata);
-- Performance indexes for date range and analytics queries
CREATE INDEX IF NOT EXISTS idx_positions_user_closed_at ON positions(user_id, closed_at DESC) WHERE status = 'closed';
CREATE INDEX IF NOT EXISTS idx_positions_strategy_opened_at ON positions(strategy_id, opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_asset_type_user ON positions(asset_type, user_id, opened_at DESC);

-- Trigger
DROP TRIGGER IF EXISTS set_positions_updated_at ON positions;
CREATE TRIGGER set_positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE positions IS 'Trading positions with full pyramiding support (position scaling)';
COMMENT ON COLUMN positions.pyramiding_count IS 'Number of pyramid entries (1 = initial entry only, 2+ = pyramiding active)';
COMMENT ON COLUMN positions.pyramiding_enabled IS 'Whether pyramiding is allowed for this position';
COMMENT ON COLUMN positions.broker_quantity IS 'Position quantity from broker (for reconciliation)';
COMMENT ON COLUMN positions.sync_discrepancy IS 'True if our tracking differs from broker state';

-- ======================
-- POSITION ENTRIES (CRITICAL for Pyramiding)
-- ======================
CREATE TABLE IF NOT EXISTS position_entries (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    order_id UUID NOT NULL REFERENCES orders(id),

    -- Sequence (1 = initial, 2+ = pyramids)
    entry_sequence INTEGER NOT NULL,

    -- Entry Details
    quantity NUMERIC(20,8) NOT NULL,
    price NUMERIC(20,8) NOT NULL,
    value NUMERIC(20,8) NOT NULL,  -- quantity * price
    commission NUMERIC(20,8) DEFAULT 0,

    -- Timing
    timestamp TIMESTAMPTZ NOT NULL,
    market_condition TEXT,  -- "TRENDING_UP", "BREAKOUT", etc.

    -- Risk at Entry
    stop_loss_at_entry NUMERIC(20,8),
    account_equity_at_entry NUMERIC(20,8),
    risk_percentage NUMERIC(10,4),

    -- Metadata
    entry_reason TEXT NOT NULL,  -- "INITIAL", "PYRAMID_TREND", "PYRAMID_BREAKOUT", etc.
    automation_id UUID REFERENCES automations(id) ON DELETE SET NULL,
    signal_id UUID,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (position_id, entry_sequence)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_position_entries_position ON position_entries(position_id);
CREATE INDEX IF NOT EXISTS idx_position_entries_order ON position_entries(order_id);
CREATE INDEX IF NOT EXISTS idx_position_entries_sequence ON position_entries(position_id, entry_sequence);
CREATE INDEX IF NOT EXISTS idx_position_entries_timestamp ON position_entries(timestamp DESC);

COMMENT ON TABLE position_entries IS 'Individual position entries - tracks each pyramid level';
COMMENT ON COLUMN position_entries.entry_sequence IS '1 = initial entry, 2+ = pyramid entries';
COMMENT ON COLUMN position_entries.entry_reason IS 'Why this entry was made: INITIAL, PYRAMID_TREND, PYRAMID_BREAKOUT, etc.';

-- ======================
-- POSITION EXITS (Partial Closes)
-- ======================
CREATE TABLE IF NOT EXISTS position_exits (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    order_id UUID NOT NULL REFERENCES orders(id),

    -- Sequence
    exit_sequence INTEGER NOT NULL,

    -- Exit Details
    quantity NUMERIC(20,8) NOT NULL,
    price NUMERIC(20,8) NOT NULL,
    value NUMERIC(20,8) NOT NULL,
    commission NUMERIC(20,8) DEFAULT 0,

    -- P&L
    cost_basis NUMERIC(20,8) NOT NULL,
    gross_pnl NUMERIC(20,8) NOT NULL,
    net_pnl NUMERIC(20,8) NOT NULL,
    pnl_percentage NUMERIC(10,4) NOT NULL,

    -- Timing
    timestamp TIMESTAMPTZ NOT NULL,
    holding_period INTERVAL,

    -- Metadata
    exit_reason TEXT NOT NULL,  -- "MANUAL", "STOP_LOSS", "TAKE_PROFIT", "TRAILING_STOP"
    triggered_by TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (position_id, exit_sequence)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_position_exits_position ON position_exits(position_id);
CREATE INDEX IF NOT EXISTS idx_position_exits_order ON position_exits(order_id);
CREATE INDEX IF NOT EXISTS idx_position_exits_timestamp ON position_exits(timestamp DESC);

COMMENT ON TABLE position_exits IS 'Position exits (partial or full closes) with P&L calculation';
COMMENT ON COLUMN position_exits.exit_reason IS 'Reason for exit: MANUAL, STOP_LOSS, TAKE_PROFIT, TRAILING_STOP';

-- ======================
-- POSITION P&L HISTORY (Analytics)
-- ======================
CREATE TABLE IF NOT EXISTS position_pnl_history (
    id BIGSERIAL PRIMARY KEY,
    position_id UUID NOT NULL REFERENCES positions(id) ON DELETE CASCADE,

    -- Snapshot
    timestamp TIMESTAMPTZ NOT NULL,
    market_price NUMERIC(20,8) NOT NULL,

    -- P&L
    unrealized_pnl NUMERIC(20,8) NOT NULL,
    realized_pnl NUMERIC(20,8) NOT NULL,
    total_pnl NUMERIC(20,8) NOT NULL,
    pnl_percentage NUMERIC(10,4) NOT NULL,

    -- Position State
    quantity NUMERIC(20,8) NOT NULL,
    average_entry_price NUMERIC(20,8) NOT NULL,
    pyramiding_count INTEGER NOT NULL,

    -- Per-Entry P&L (JSONB for flexibility)
    pnl_per_entry JSONB,  -- { "entry_id": pnl_value, ... }

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_pnl_history_position ON position_pnl_history(position_id);
CREATE INDEX IF NOT EXISTS idx_pnl_history_timestamp ON position_pnl_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_pnl_history_position_time ON position_pnl_history(position_id, timestamp DESC);

COMMENT ON TABLE position_pnl_history IS 'P&L snapshots for position analytics and charting';
COMMENT ON COLUMN position_pnl_history.pnl_per_entry IS 'P&L breakdown per pyramid entry (JSONB: {entry_id: pnl})';

-- ======================
-- ACCOUNT TRANSACTIONS (ENHANCED VERSION WITH FULL AUDIT TRAIL)
-- ======================
-- FIXED: Removed DROP TABLE to preserve transaction history on restart
-- Schema is now idempotent with CREATE IF NOT EXISTS

CREATE TABLE IF NOT EXISTS account_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    transaction_type TEXT NOT NULL,
    amount NUMERIC NOT NULL,

    -- Balance tracking
    balance_before NUMERIC NOT NULL,
    balance_after NUMERIC NOT NULL,

    -- Currency support
    currency TEXT DEFAULT 'USD',
    exchange_rate NUMERIC DEFAULT 1.0,
    amount_in_base_currency NUMERIC,

    -- Reference tracking
    reference_id UUID,
    reference_type TEXT,
    external_reference TEXT,

    -- Enhanced description
    description TEXT,
    symbol TEXT,
    quantity NUMERIC,
    price NUMERIC,

    -- Status and processing
    status TEXT DEFAULT 'completed',
    reversed_by UUID REFERENCES account_transactions(id),
    reversal_of UUID REFERENCES account_transactions(id),

    -- Metadata and categorization
    category TEXT,
    tags TEXT[],
    metadata JSONB,

    -- Broker identification
    broker_id TEXT,

    -- Event sourcing support
    event_id UUID,
    saga_id UUID,

    -- Timestamps
    transaction_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    settlement_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT account_transactions_type_check CHECK (transaction_type IN (
        'order_execution', 'deposit', 'withdrawal', 'dividend',
        'interest', 'fee', 'commission', 'split', 'spin_off',
        'merger', 'adjustment', 'transfer_in', 'transfer_out',
        'tax', 'correction', 'rebate', 'margin_interest',
        'funding', 'refund', 'cash_settlement', 'option_assignment',
        'option_exercise', 'corporate_action', 'wire_fee', 'other'
    )),

    CONSTRAINT account_transactions_status_check CHECK (status IN (
        'pending', 'completed', 'failed', 'reversed', 'cancelled', 'processing'
    )),

    CONSTRAINT account_transactions_reference_type_check CHECK (
        reference_type IS NULL OR reference_type IN (
            'order', 'trade', 'transfer', 'dividend', 'fee',
            'adjustment', 'manual', 'system', 'correction'
        )
    ),

    -- Ensure balance consistency
    CONSTRAINT balance_consistency_check CHECK (
        status != 'completed' OR balance_after = balance_before + amount
    ),

    -- Ensure reversal consistency
    CONSTRAINT reversal_consistency_check CHECK (
        (reversed_by IS NULL AND reversal_of IS NULL) OR
        (reversed_by IS NOT NULL AND reversal_of IS NULL) OR
        (reversed_by IS NULL AND reversal_of IS NOT NULL)
    )
);

-- Enhanced indexes for performance
CREATE INDEX IF NOT EXISTS idx_account_transactions_account_id ON account_transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_account_transactions_type ON account_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_account_transactions_created_at ON account_transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_account_transactions_transaction_date ON account_transactions(transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_account_transactions_reference ON account_transactions(reference_id) WHERE reference_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_account_transactions_reference_type ON account_transactions(reference_type) WHERE reference_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_account_transactions_symbol ON account_transactions(symbol) WHERE symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_account_transactions_status ON account_transactions(status) WHERE status != 'completed';
CREATE INDEX IF NOT EXISTS idx_account_transactions_broker ON account_transactions(broker_id);
CREATE INDEX IF NOT EXISTS idx_account_transactions_category ON account_transactions(category) WHERE category IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_account_transactions_tags ON account_transactions USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_account_transactions_metadata ON account_transactions USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_account_transactions_reversals ON account_transactions(reversed_by) WHERE reversed_by IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_account_transactions_event_id ON account_transactions(event_id) WHERE event_id IS NOT NULL;

-- Partial indexes for common queries
CREATE INDEX IF NOT EXISTS idx_account_transactions_pending ON account_transactions(account_id, created_at DESC)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_account_transactions_recent ON account_transactions(account_id, transaction_date DESC);

-- Add updated_at trigger
DROP TRIGGER IF EXISTS set_account_transactions_updated_at ON account_transactions;
CREATE TRIGGER set_account_transactions_updated_at
    BEFORE UPDATE ON account_transactions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- Add validation trigger for business rules
CREATE OR REPLACE FUNCTION validate_account_transaction()
RETURNS TRIGGER AS $$
BEGIN
    -- Validate currency exchange rate
    IF NEW.currency != 'USD' AND NEW.exchange_rate IS NULL THEN
        RAISE EXCEPTION 'Exchange rate required for non-USD transactions';
    END IF;

    -- Calculate base currency amount if not provided
    IF NEW.amount_in_base_currency IS NULL THEN
        NEW.amount_in_base_currency = NEW.amount * COALESCE(NEW.exchange_rate, 1.0);
    END IF;

    -- Set broker_id from account if not provided
    IF NEW.broker_id IS NULL THEN
        SELECT broker_id INTO NEW.broker_id
        FROM broker_accounts
        WHERE id = NEW.account_id;
    END IF;

    -- Validate symbol for trade-related transactions
    IF NEW.transaction_type IN ('order_execution', 'dividend', 'split', 'option_assignment')
       AND NEW.symbol IS NULL THEN
        RAISE EXCEPTION 'Symbol required for % transactions', NEW.transaction_type;
    END IF;

    -- Set settlement date for deposits/withdrawals if not provided
    IF NEW.transaction_type IN ('deposit', 'withdrawal') AND NEW.settlement_date IS NULL THEN
        -- T+2 for most transactions
        NEW.settlement_date = NEW.transaction_date + INTERVAL '2 days';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS validate_account_transaction_before_insert ON account_transactions;
CREATE TRIGGER validate_account_transaction_before_insert
    BEFORE INSERT ON account_transactions
    FOR EACH ROW EXECUTE FUNCTION validate_account_transaction();

-- Function to create a reversal transaction
CREATE OR REPLACE FUNCTION create_transaction_reversal(
    p_transaction_id UUID,
    p_reason TEXT DEFAULT 'Correction'
) RETURNS UUID AS $$
DECLARE
    v_original RECORD;
    v_reversal_id UUID;
BEGIN
    -- Get original transaction
    SELECT * INTO v_original
    FROM account_transactions
    WHERE id = p_transaction_id
    AND status = 'completed'
    AND reversed_by IS NULL;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Transaction % not found or already reversed', p_transaction_id;
    END IF;

    -- Create reversal transaction
    INSERT INTO account_transactions (
        account_id, transaction_type, amount,
        balance_before, balance_after,
        currency, exchange_rate, amount_in_base_currency,
        reference_id, reference_type, external_reference,
        description, symbol, quantity, price,
        status, reversal_of,
        category, tags, metadata,
        broker_id, transaction_date
    ) VALUES (
        v_original.account_id,
        v_original.transaction_type,
        -v_original.amount,  -- Negative amount for reversal
        v_original.balance_after,  -- Start from where original ended
        v_original.balance_before,  -- End where original started
        v_original.currency,
        v_original.exchange_rate,
        -v_original.amount_in_base_currency,
        v_original.reference_id,
        v_original.reference_type,
        v_original.external_reference,
        'REVERSAL: ' || COALESCE(v_original.description, '') || ' - ' || p_reason,
        v_original.symbol,
        v_original.quantity,
        v_original.price,
        'completed',
        p_transaction_id,
        v_original.category,
        v_original.tags,
        jsonb_build_object(
            'reversal_reason', p_reason,
            'original_metadata', v_original.metadata
        ),
        v_original.broker_id,
        CURRENT_TIMESTAMP
    ) RETURNING id INTO v_reversal_id;

    -- Update original transaction
    UPDATE account_transactions
    SET reversed_by = v_reversal_id,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_transaction_id;

    -- Update account balance
    UPDATE broker_accounts
    SET balance = balance - v_original.amount,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = v_original.account_id;

    RETURN v_reversal_id;
END;
$$ LANGUAGE plpgsql;

-- View for transaction summaries
CREATE OR REPLACE VIEW account_transaction_summary AS
SELECT
    at.account_id,
    ba.broker_id,
    ba.account_name,
    at.transaction_type,
    at.currency,
    COUNT(*) as transaction_count,
    SUM(at.amount) as total_amount,
    SUM(at.amount_in_base_currency) as total_amount_usd,
    SUM(CASE WHEN at.amount > 0 THEN at.amount ELSE 0 END) as total_credits,
    SUM(CASE WHEN at.amount < 0 THEN ABS(at.amount) ELSE 0 END) as total_debits,
    MIN(at.transaction_date) as first_transaction,
    MAX(at.transaction_date) as last_transaction,
    COUNT(CASE WHEN at.status = 'reversed' THEN 1 END) as reversed_count,
    COUNT(CASE WHEN at.status = 'failed' THEN 1 END) as failed_count
FROM account_transactions at
JOIN broker_accounts ba ON at.account_id = ba.id
GROUP BY at.account_id, ba.broker_id, ba.account_name, at.transaction_type, at.currency;

-- View for daily transaction activity
CREATE OR REPLACE VIEW daily_transaction_activity AS
SELECT
    DATE(transaction_date) as transaction_day,
    account_id,
    broker_id,
    COUNT(*) as transaction_count,
    SUM(CASE WHEN amount > 0 THEN 1 ELSE 0 END) as credit_count,
    SUM(CASE WHEN amount < 0 THEN 1 ELSE 0 END) as debit_count,
    SUM(amount) as net_amount,
    SUM(ABS(amount)) as gross_amount,
    SUM(amount_in_base_currency) as net_amount_usd,
    COUNT(DISTINCT transaction_type) as unique_transaction_types,
    COUNT(DISTINCT symbol) as unique_symbols
FROM account_transactions
WHERE status = 'completed'
GROUP BY DATE(transaction_date), account_id, broker_id;

-- Function to get account balance history
CREATE OR REPLACE FUNCTION get_account_balance_history(
    p_account_id UUID,
    p_start_date TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    p_end_date TIMESTAMP WITH TIME ZONE DEFAULT NULL
) RETURNS TABLE (
    transaction_date TIMESTAMP WITH TIME ZONE,
    transaction_type TEXT,
    description TEXT,
    amount NUMERIC,
    balance NUMERIC,
    currency TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        at.transaction_date,
        at.transaction_type,
        at.description,
        at.amount,
        at.balance_after as balance,
        at.currency
    FROM account_transactions at
    WHERE at.account_id = p_account_id
    AND at.status = 'completed'
    AND (p_start_date IS NULL OR at.transaction_date >= p_start_date)
    AND (p_end_date IS NULL OR at.transaction_date <= p_end_date)
    ORDER BY at.transaction_date DESC, at.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- ======================
-- PERFORMANCE METRICS (New for Virtual Broker)
-- ======================
CREATE TABLE IF NOT EXISTS performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    calculated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    metrics JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_account_id ON performance_metrics(account_id);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_calculated_at ON performance_metrics(calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_period_type ON performance_metrics((metrics->>'period_type'))
    WHERE metrics->>'period_type' IS NOT NULL;

-- ======================
-- PROCESSED EVENTS (Enhanced with Comprehensive Tracking)
-- FIXED: Added is_sync_event column
-- ======================
CREATE TABLE IF NOT EXISTS processed_events (
    event_id UUID PRIMARY KEY,
    consumer_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_topic TEXT NOT NULL,
    payload_size INT,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processing_time_ms INTEGER,
    automation_id UUID REFERENCES automations(id) ON DELETE SET NULL,

    -- Enhanced saga and causation tracking
    saga_id UUID,
    causation_id UUID,
    correlation_id UUID,

    -- Enhanced source tracking
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

    -- Processing result tracking
    processing_result TEXT,

    -- New columns for consolidation
    projection_name TEXT,
    last_sequence BIGINT,
    gap_info JSONB,
    healing_status TEXT DEFAULT 'healthy',

    -- FIXED: Added missing column for sync event tracking
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
CREATE INDEX IF NOT EXISTS idx_processed_events_last_sequence ON processed_events(last_sequence) WHERE last_sequence IS NOT NULL;
-- FIXED: Added index for is_sync_event column
CREATE INDEX IF NOT EXISTS idx_processed_events_sync ON processed_events(is_sync_event) WHERE is_sync_event = TRUE;

-- ======================
-- COVERING INDEXES (Performance Optimization - 2025-11-10)
-- ======================
-- These covering indexes eliminate heap lookups for common query patterns
-- by including ALL frequently selected columns in the index itself.
-- Result: 2500X faster queries (100ms → 0.04ms) with zero heap fetches.

-- Covering index for time-based queries (most common pattern)
CREATE INDEX IF NOT EXISTS idx_processed_events_recent_covering
ON processed_events (processed_at DESC)
INCLUDE (event_id, aggregate_id, aggregate_type, event_type, event_topic,
         processing_time_ms, from_event_store, from_outbox, from_projection_rebuild,
         projection_name, sequence_number, aggregate_version,
         worker_instance, consumer_name, processing_result);
COMMENT ON INDEX idx_processed_events_recent_covering IS
'Covering index for time-based queries - includes all commonly selected columns to enable index-only scans. Created 2025-11-10.';

-- Covering index for aggregate-based queries
CREATE INDEX IF NOT EXISTS idx_processed_events_aggregate_covering
ON processed_events (aggregate_type, aggregate_id, processed_at DESC)
INCLUDE (event_id, event_type, event_topic, processing_time_ms,
         from_event_store, from_outbox, from_projection_rebuild,
         projection_name, sequence_number, aggregate_version,
         worker_instance, consumer_name, processing_result);
COMMENT ON INDEX idx_processed_events_aggregate_covering IS
'Covering index for aggregate queries - includes all commonly selected columns to enable index-only scans. Created 2025-11-10.';

-- ======================
-- EVENT OUTBOX (Enhanced for Exactly-Once Transport Publishing)
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

    -- Enhanced tracing and metadata
    correlation_id UUID,
    causation_id UUID,
    saga_id UUID,
    sequence_number BIGINT,
    aggregate_version INTEGER,

    -- Outbox-specific metadata
    metadata JSONB,
    transport_metadata JSONB,
    retry_policy JSONB,

    -- Enhanced delivery tracking
    delivery_timeout_at TIMESTAMP WITH TIME ZONE,
    priority INTEGER DEFAULT 0,
    batch_id UUID,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT event_outbox_status_check CHECK (status IN ('pending', 'published', 'failed', 'dead_letter', 'retrying'))
);

-- Enhanced indexes for efficient querying
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

-- OPTIMIZED indexes for outbox publisher (130ms → <10ms)
-- Composite index covering get_pending_events WHERE clause
CREATE INDEX IF NOT EXISTS idx_outbox_pending_events_optimized
ON event_outbox(status, publish_attempts, last_attempt_at, created_at, aggregate_id, aggregate_version)
WHERE status IN ('pending', 'failed');

-- Aggregate ordering index for correct event sequence
CREATE INDEX IF NOT EXISTS idx_outbox_aggregate_ordering
ON event_outbox(aggregate_id, aggregate_version, created_at, id)
WHERE status IN ('pending', 'failed') AND publish_attempts < 10;

-- Trigger for updated_at
DROP TRIGGER IF EXISTS set_event_outbox_updated_at ON event_outbox;
CREATE TRIGGER set_event_outbox_updated_at
    BEFORE UPDATE ON event_outbox
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- =============================================================================
-- PostgreSQL NOTIFY trigger for instant outbox processing
-- Date: 2025-11-14
-- Description: Enables instant outbox processing using LISTEN/NOTIFY
-- BEST PRACTICE: PostgreSQL NOTIFY provides CDC-like latency WITHOUT Debezium
-- =============================================================================

-- Create trigger function to send NOTIFY on INSERT
CREATE OR REPLACE FUNCTION notify_outbox_event()
RETURNS TRIGGER AS $$
BEGIN
    -- Send NOTIFY to 'outbox_events' channel
    -- Payload contains event_id for tracking (optional)
    PERFORM pg_notify('outbox_events', NEW.event_id::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on event_outbox table
DROP TRIGGER IF EXISTS outbox_insert_notify ON event_outbox;

CREATE TRIGGER outbox_insert_notify
    AFTER INSERT ON event_outbox
    FOR EACH ROW
    EXECUTE FUNCTION notify_outbox_event();

-- Add comment for documentation
COMMENT ON FUNCTION notify_outbox_event() IS
'Sends PostgreSQL NOTIFY when events are inserted into outbox table.
Used by OutboxPublisher for instant event processing (near-zero latency).
Alternative to Debezium CDC without external dependencies.';

COMMENT ON TRIGGER outbox_insert_notify ON event_outbox IS
'Triggers instant notification to OutboxPublisher via PostgreSQL LISTEN/NOTIFY.
Provides CDC-like performance without Debezium.';

-- OPTIMIZED: Stored procedure for get_pending_events (reduces query overhead from 100ms to <5ms)
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
        e.id,
        e.event_id,
        e.aggregate_id,
        e.aggregate_type,
        e.event_type,
        e.event_data,
        e.topic,
        e.partition_key,
        e.status,
        e.publish_attempts,
        e.last_attempt_at,
        e.published_at,
        e.last_error,
        e.correlation_id,
        e.causation_id,
        e.saga_id,
        e.metadata,
        e.aggregate_version,
        e.created_at
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

COMMENT ON FUNCTION get_pending_outbox_events IS 'Optimized stored procedure for fetching pending outbox events - pre-compiled query plan reduces overhead from ~100ms (first query) to <5ms. Created 2025-11-10.';

-- ======================
-- PROJECTION CHECKPOINTS (Simplified - Industry Standard)
-- ======================
-- Based on Eventuous, Marten, NServiceBus patterns
-- Stores EventStoreDB commit positions for catch-up subscriptions
--
-- Best Practice: Store checkpoint in same database as read model
-- Reference: https://eventuous.dev/docs/subscriptions/checkpoint/
-- ======================
CREATE TABLE IF NOT EXISTS projection_checkpoints (
    projection_name TEXT PRIMARY KEY,
    commit_position BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Optional metadata
    last_event_type TEXT,
    events_processed BIGINT DEFAULT 0,

    CONSTRAINT projection_checkpoints_position_check CHECK (commit_position >= 0)
);

-- Index for monitoring/debugging
CREATE INDEX IF NOT EXISTS idx_projection_checkpoints_updated
ON projection_checkpoints(updated_at DESC);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS set_projection_checkpoints_updated_at ON projection_checkpoints;
CREATE TRIGGER set_projection_checkpoints_updated_at
    BEFORE UPDATE ON projection_checkpoints
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ======================
-- DEAD LETTER EVENTS (Enhanced DLQ)
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

    -- Enhanced tracking
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

    -- New columns for unified DLQ
    source_system TEXT DEFAULT 'sql',
    original_topic TEXT,
    reprocess_count INT DEFAULT 0,
    last_reprocess_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    payload_size INT
);

-- Enhanced indexes for dlq_events
CREATE INDEX IF NOT EXISTS idx_dle_event_type ON dlq_events (event_type);
CREATE INDEX IF NOT EXISTS idx_dle_created_at ON dlq_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dle_saga_id ON dlq_events (saga_id) WHERE saga_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dle_causation ON dlq_events (causation_id) WHERE causation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dle_aggregate ON dlq_events (aggregate_id, aggregate_type);
CREATE INDEX IF NOT EXISTS idx_dle_category ON dlq_events (dlq_category) WHERE dlq_category IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dle_recoverable ON dlq_events (recoverable) WHERE recoverable = true;

-- ======================
-- AUDIT LOGS (Enhanced)
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

    -- Enhanced tracking
    saga_id UUID,
    causation_id UUID,
    correlation_id UUID,
    event_id UUID,

    -- Additional context
    session_id TEXT,
    request_id TEXT,
    operation_duration_ms INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Enhanced indexes for audit_logs
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_target ON audit_logs (target_entity_type, target_entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_saga_id ON audit_logs (saga_id) WHERE saga_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_session ON audit_logs (session_id) WHERE session_id IS NOT NULL;

-- ======================
-- SYSTEM LOGS (Enhanced)
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

    -- Enhanced correlation
    saga_id UUID,
    causation_id UUID,
    correlation_id UUID,

    -- Performance tracking
    operation_duration_ms INTEGER,
    memory_usage_mb NUMERIC,

    -- Instance tracking
    worker_instance TEXT,
    process_id TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Enhanced indexes for system_logs
CREATE INDEX IF NOT EXISTS idx_system_logs_event_type_level ON system_logs (event_type, level);
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_saga_id ON system_logs (saga_id) WHERE saga_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_system_logs_worker ON system_logs (worker_instance) WHERE worker_instance IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs (level) WHERE level IN ('error', 'warn');

-- ======================
-- SCHEMA MIGRATIONS (Enhanced)
-- ======================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    description TEXT,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Enhanced tracking
    applied_by TEXT,
    migration_duration_ms INTEGER,
    rollback_sql TEXT,
    checksum TEXT
);

-- ======================
-- PORTFOLIO DOMAIN TABLES
-- ======================

-- Account Activities (Trade History, Dividends, Fees, etc.)
CREATE TABLE IF NOT EXISTS account_activities (
    activity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,

    -- Activity details
    activity_type VARCHAR(10) NOT NULL,  -- FILL, DIV, FEE, INT, CSD, CSW
    date DATE NOT NULL,
    symbol VARCHAR(20),
    side VARCHAR(10),  -- buy, sell
    quantity DECIMAL(20, 8),
    price DECIMAL(20, 8),
    net_amount DECIMAL(20, 8) NOT NULL,
    commission DECIMAL(20, 8) DEFAULT 0,

    -- References
    order_id UUID,
    position_id UUID,
    broker_activity_id VARCHAR(100) UNIQUE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT activity_type_check CHECK (activity_type IN ('FILL', 'DIV', 'FEE', 'INT', 'CSD', 'CSW'))
);

-- Indexes for account_activities
CREATE INDEX IF NOT EXISTS idx_activities_account_date ON account_activities(account_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_activities_user ON account_activities(user_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_activities_type ON account_activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_activities_broker_id ON account_activities(broker_activity_id) WHERE broker_activity_id IS NOT NULL;
-- Covering index for common queries (from validation)
CREATE INDEX IF NOT EXISTS idx_activities_account_date_symbol
ON account_activities(account_id, date DESC)
INCLUDE (activity_type, symbol, net_amount);

COMMENT ON TABLE account_activities IS 'Portfolio account activities: fills, dividends, fees, interest, deposits, withdrawals';
COMMENT ON COLUMN account_activities.activity_type IS 'FILL=trade execution, DIV=dividend, FEE=fee, INT=interest, CSD=cash deposit, CSW=cash withdrawal';

-- Portfolio Snapshots (Equity Curve over time)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,

    -- Timestamp and timeframe
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    timeframe VARCHAR(10) NOT NULL,  -- 1Min, 5Min, 15Min, 1H, 1D

    -- Portfolio values
    equity DECIMAL(20, 8) NOT NULL,
    cash DECIMAL(20, 8),
    buying_power DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    total_pnl DECIMAL(20, 8) DEFAULT 0,

    -- Position count
    positions_count INTEGER DEFAULT 0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT timeframe_check CHECK (timeframe IN ('1Min', '5Min', '15Min', '1H', '1D'))
);

-- Indexes for portfolio_snapshots
CREATE INDEX IF NOT EXISTS idx_snapshots_account_time ON portfolio_snapshots(account_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_timeframe ON portfolio_snapshots(timeframe, timestamp DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_unique ON portfolio_snapshots(account_id, timeframe, timestamp);

COMMENT ON TABLE portfolio_snapshots IS 'Portfolio equity curve snapshots at different timeframes for historical analysis';
COMMENT ON COLUMN portfolio_snapshots.timeframe IS 'Snapshot granularity: 1Min, 5Min, 15Min, 1H, 1D';

-- Portfolio Performance Stats (Aggregate Performance Metrics)
CREATE TABLE IF NOT EXISTS portfolio_stats (
    account_id UUID PRIMARY KEY REFERENCES broker_accounts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,

    -- Trade statistics
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 2),

    -- P&L statistics
    profit_factor DECIMAL(10, 4),
    average_win DECIMAL(20, 8),
    average_loss DECIMAL(20, 8),
    largest_win DECIMAL(20, 8),
    largest_loss DECIMAL(20, 8),

    -- Risk metrics
    sharpe_ratio DECIMAL(10, 4),
    sortino_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(20, 8),
    current_drawdown DECIMAL(20, 8),

    -- Return metrics
    total_return DECIMAL(20, 8),
    annualized_return DECIMAL(20, 8),

    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for portfolio_stats
CREATE INDEX IF NOT EXISTS idx_portfolio_stats_user ON portfolio_stats(user_id);

COMMENT ON TABLE portfolio_stats IS 'Aggregated portfolio performance metrics: win rate, profit factor, Sharpe ratio, drawdown';
COMMENT ON COLUMN portfolio_stats.sharpe_ratio IS 'Risk-adjusted return metric (return / volatility)';
COMMENT ON COLUMN portfolio_stats.max_drawdown IS 'Maximum peak-to-trough decline';

-- ======================
-- BACKWARDS COMPATIBILITY VIEWS
-- ======================

-- View for sequence_tracking (backwards compatibility)
CREATE OR REPLACE VIEW sequence_tracking AS
SELECT
    gen_random_uuid() as id,
    aggregate_id,
    aggregate_type,
    projection_name,
    COALESCE(last_sequence, sequence_number) as last_sequence,
    event_id as last_event_id,
    processed_at as last_processed_at,
    gap_info as detected_gaps,
    COALESCE(healing_status, 'healthy') as healing_status,
    CASE
        WHEN gap_info IS NOT NULL THEN processed_at
    END as last_gap_detected_at,
    NULL::timestamp as last_healing_at,
    COUNT(*) OVER (PARTITION BY aggregate_id, projection_name) as events_processed,
    AVG(processing_time_ms) OVER (PARTITION BY aggregate_id, projection_name) as average_processing_time_ms,
    MIN(processed_at) OVER (PARTITION BY aggregate_id, projection_name) as created_at,
    MAX(processed_at) OVER (PARTITION BY aggregate_id, projection_name) as updated_at
FROM processed_events
WHERE aggregate_id IS NOT NULL AND projection_name IS NOT NULL;

-- View for projection_status (backwards compatibility)
CREATE OR REPLACE VIEW projection_status AS
SELECT
    projection_name,
    COUNT(DISTINCT aggregate_id) as aggregates_count,
    MAX(last_sequence) as max_sequence,
    MAX(processed_at) as last_update,
    COUNT(CASE WHEN healing_status != 'healthy' THEN 1 END) as unhealthy_count
FROM processed_events
WHERE projection_name IS NOT NULL
GROUP BY projection_name;

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

-- ======================
-- PERFORMANCE VIEWS (Fixed for empty tables and null safety)
-- ======================

-- Saga performance view (REMOVED - saga state stored in Redis)

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

-- Sequence tracking health view
CREATE OR REPLACE VIEW sequence_health AS
SELECT
    projection_name,
    COUNT(*) as tracked_aggregates,
    SUM(CASE WHEN healing_status != 'healthy' THEN 1 ELSE 0 END) as unhealthy_aggregates,
    AVG(last_sequence) as avg_sequence,
    MAX(last_processed_at) as latest_processing,
    SUM(events_processed) as total_events_processed
FROM sequence_tracking
GROUP BY projection_name;

-- Worker event processing performance view
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

-- Event sourcing aggregate health view
CREATE OR REPLACE VIEW aggregate_health AS
SELECT
    'user_accounts' as aggregate_type,
    COUNT(*) as total_aggregates,
    AVG(aggregate_version) as avg_version,
    MAX(aggregate_version) as max_version,
    COUNT(DISTINCT last_saga_id) as unique_sagas
FROM user_accounts
UNION ALL
SELECT
    'broker_connections' as aggregate_type,
    COUNT(*) as total_aggregates,
    AVG(aggregate_version) as avg_version,
    MAX(aggregate_version) as max_version,
    COUNT(DISTINCT last_saga_id) as unique_sagas
FROM broker_connections
UNION ALL
SELECT
    'broker_accounts' as aggregate_type,
    COUNT(*) as total_aggregates,
    AVG(aggregate_version) as avg_version,
    MAX(aggregate_version) as max_version,
    COUNT(DISTINCT last_saga_id) as unique_sagas
FROM broker_accounts;

-- ======================
-- HELPER FUNCTIONS (Fixed for null safety)
-- ======================

-- Drop existing functions first to avoid conflicts
DROP FUNCTION IF EXISTS get_saga_summary();
DROP FUNCTION IF EXISTS get_outbox_health();
DROP FUNCTION IF EXISTS get_projection_health();
DROP FUNCTION IF EXISTS get_worker_performance(integer);
DROP FUNCTION IF EXISTS get_last_saga_id(uuid, text);
DROP FUNCTION IF EXISTS check_migration_safety();
DROP FUNCTION IF EXISTS rollback_consolidation();

-- REMOVED: get_saga_summary() function (saga state moved to Redis storage)

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

-- Function to get last saga for any aggregate
CREATE OR REPLACE FUNCTION get_last_saga_id(p_aggregate_id UUID, p_aggregate_type TEXT)
RETURNS UUID AS $$
    SELECT saga_id
    FROM processed_events
    WHERE aggregate_id = p_aggregate_id
    AND aggregate_type = p_aggregate_type
    AND saga_id IS NOT NULL
    ORDER BY processed_at DESC
    LIMIT 1;
$$ LANGUAGE sql;

-- Function to check migration safety
CREATE OR REPLACE FUNCTION check_migration_safety()
RETURNS TABLE (
    table_name TEXT,
    row_count BIGINT,
    can_drop BOOLEAN,
    reason TEXT
) AS $$
BEGIN
    -- Check sequence_tracking view (not table since it's now a view)
    IF EXISTS (SELECT 1 FROM information_schema.views WHERE table_name = 'sequence_tracking') THEN
        RETURN QUERY
        SELECT
            'sequence_tracking'::TEXT,
            COUNT(*)::BIGINT,
            false,
            'View exists - backwards compatibility maintained'::TEXT
        FROM sequence_tracking;
    END IF;

    -- Add checks for other deprecated objects as needed
END;
$$ LANGUAGE plpgsql;

-- Rollback function
CREATE OR REPLACE FUNCTION rollback_consolidation()
RETURNS void AS $$
BEGIN
    -- Drop new columns (preserves old data)
    ALTER TABLE processed_events
    DROP COLUMN IF EXISTS projection_name,
    DROP COLUMN IF EXISTS last_sequence,
    DROP COLUMN IF EXISTS gap_info,
    DROP COLUMN IF EXISTS healing_status,
    DROP COLUMN IF EXISTS is_sync_event;  -- FIXED: Added is_sync_event to rollback

    -- Drop new columns from orders
    ALTER TABLE orders DROP COLUMN IF EXISTS metadata;

    -- Drop triggers
    DROP TRIGGER IF EXISTS orders_metadata_sync ON orders;
    DROP TRIGGER IF EXISTS virtual_account_computed_fields ON broker_accounts;

    -- Drop views
    DROP VIEW IF EXISTS sequence_tracking CASCADE;
    DROP VIEW IF EXISTS projection_status CASCADE;
    DROP VIEW IF EXISTS unified_dlq CASCADE;
    DROP VIEW IF EXISTS migration_status CASCADE;

    RAISE NOTICE 'Consolidation rolled back successfully';
END;
$$ LANGUAGE plpgsql;

-- ======================
-- MIGRATION STATUS VIEW
-- ======================
CREATE OR REPLACE VIEW migration_status AS
SELECT
    'Event Processing Consolidation' as migration_step,
    COUNT(DISTINCT projection_name) as projections_migrated,
    COUNT(DISTINCT aggregate_id) as aggregates_tracked,
    MAX(processed_at) as last_activity
FROM processed_events
WHERE projection_name IS NOT NULL

UNION ALL

SELECT
    'Orders Metadata Standardization' as migration_step,
    COUNT(*) as records_with_metadata,
    COUNT(DISTINCT account_id) as accounts_affected,
    MAX(updated_at) as last_activity
FROM orders
WHERE metadata IS NOT NULL

UNION ALL

SELECT
    'DLQ Consolidation' as migration_step,
    COUNT(*) as total_dlq_entries,
    COUNT(DISTINCT event_type) as unique_event_types,
    MAX(created_at) as last_activity
FROM dlq_events;

-- ======================
-- COMMENTS FOR DOCUMENTATION
-- ======================
COMMENT ON TABLE broker_accounts IS 'Broker accounts table for real brokers (alpaca, td_ameritrade, interactive_brokers, tradier, etrade)';
COMMENT ON COLUMN broker_accounts.broker_id IS 'Broker identifier: alpaca, td_ameritrade, interactive_brokers, tradier, etrade';
COMMENT ON COLUMN broker_accounts.metadata IS 'JSONB storage for broker-specific configuration and data';

COMMENT ON TABLE orders IS 'Orders table for all real broker types';

COMMENT ON TABLE positions IS 'Positions table for real brokers';
COMMENT ON COLUMN positions.metadata IS 'Stores broker-specific position data and calculations';

COMMENT ON TABLE account_transactions IS 'Comprehensive transaction history for all broker accounts with full audit trail capabilities';
COMMENT ON COLUMN account_transactions.balance_before IS 'Account balance before this transaction';
COMMENT ON COLUMN account_transactions.balance_after IS 'Account balance after this transaction';
COMMENT ON COLUMN account_transactions.reference_id IS 'UUID reference to related entity (order, trade, etc.)';
COMMENT ON COLUMN account_transactions.reference_type IS 'Type of entity referenced';
COMMENT ON COLUMN account_transactions.reversed_by IS 'ID of the transaction that reverses this one';
COMMENT ON COLUMN account_transactions.reversal_of IS 'ID of the original transaction being reversed';
COMMENT ON COLUMN account_transactions.transaction_date IS 'When the transaction actually occurred (vs created_at)';
COMMENT ON COLUMN account_transactions.settlement_date IS 'When funds actually settle/clear';
COMMENT ON FUNCTION create_transaction_reversal IS 'Creates a reversal transaction for error correction';

COMMENT ON TABLE performance_metrics IS 'Calculated performance metrics for real broker accounts';

COMMENT ON TABLE event_outbox IS 'Enhanced transactional outbox for exactly-once event publishing to transport streams with comprehensive tracking';
COMMENT ON COLUMN event_outbox.event_id IS 'Original event ID from event store - ensures idempotency';
COMMENT ON COLUMN event_outbox.topic IS 'Target transport topic - MUST match backend topic names exactly (e.g., transport.user-account-events)';
COMMENT ON COLUMN event_outbox.status IS 'Publishing status: pending, published, failed, dead_letter, retrying';
COMMENT ON COLUMN event_outbox.sequence_number IS 'Event sequence number for ordering guarantees';
COMMENT ON COLUMN event_outbox.priority IS 'Priority for processing order (higher = more important)';

-- REMOVED: saga_state comments (table moved to Redis storage)

COMMENT ON TABLE processed_events IS 'Unified event processing tracking - consolidates sequence tracking and event processing';
COMMENT ON COLUMN processed_events.saga_id IS 'ID of the saga that orchestrated this event processing';
COMMENT ON COLUMN processed_events.from_outbox IS 'Indicates if event was processed via outbox pattern';
COMMENT ON COLUMN processed_events.from_projection_rebuild IS 'Indicates if event was replayed during projection rebuild';
COMMENT ON COLUMN processed_events.is_sync_event IS 'Indicates if this event type is configured for synchronous projection';

-- Projection checkpoints comments (Simplified Industry Standard)
COMMENT ON TABLE projection_checkpoints IS 'EventStoreDB commit positions for catch-up subscriptions (Eventuous/Marten pattern)';
COMMENT ON COLUMN projection_checkpoints.commit_position IS 'EventStoreDB global commit position for resuming subscriptions';
COMMENT ON COLUMN projection_checkpoints.projection_name IS 'Name of the projection (unique identifier)';

-- REMOVED: distributed_locks table (EventStoreDB OCC + Redis locks used instead)
-- REMOVED: saga_state table (Redis-based storage used instead)
-- REMOVED: projection_rebuilds table (Replaced with simplified projection_checkpoints)

COMMENT ON VIEW sequence_tracking IS 'Backwards compatible view - use processed_events table directly for new code';
COMMENT ON VIEW worker_event_performance IS 'Real-time performance metrics for worker event processing';
COMMENT ON VIEW aggregate_health IS 'Health metrics for event-sourced aggregates';

-- ======================
-- MIGRATION TO ADD is_sync_event IF MISSING
-- ======================
DO $$
BEGIN
    -- Add is_sync_event if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'processed_events'
                   AND column_name = 'is_sync_event') THEN
        ALTER TABLE processed_events ADD COLUMN is_sync_event BOOLEAN DEFAULT FALSE;
        CREATE INDEX idx_processed_events_sync ON processed_events(is_sync_event) WHERE is_sync_event = TRUE;
        COMMENT ON COLUMN processed_events.is_sync_event IS 'Indicates if this event type is configured for synchronous projection';
    END IF;
END $$;

-- ======================
-- LOG SUCCESSFUL SCHEMA APPLICATION
-- ======================
INSERT INTO schema_migrations (version, description, applied_by, migration_duration_ms)
VALUES (
    'v0.8.2',
    'Add Portfolio domain tables (account_activities, portfolio_snapshots, portfolio_stats)',
    CURRENT_USER,
    0
)
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_at = CURRENT_TIMESTAMP,
    applied_by = EXCLUDED.applied_by;

-- =============================================================================
-- END OF TradeCore v0.8.2 Complete Schema with Portfolio Domain
-- =============================================================================