-- =============================================================================
-- Migration: 005_user_external_identities.sql
-- Description: External identity linking (Telegram, etc.)
-- =============================================================================

-- External identity providers mapping
-- Allows linking multiple external accounts (Telegram, Google, etc.) to WellWon users
CREATE TABLE IF NOT EXISTS user_external_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,  -- 'telegram', 'google', 'apple', etc.
    external_id VARCHAR(255) NOT NULL,  -- Provider's user ID
    external_username VARCHAR(255),  -- Optional: username on provider
    external_data JSONB,  -- Provider-specific metadata
    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,

    -- Each external identity can only be linked to one WellWon user
    CONSTRAINT unique_external_identity UNIQUE (provider, external_id)
);

-- Index for fast lookup by provider + external_id
CREATE INDEX IF NOT EXISTS idx_external_identities_lookup
ON user_external_identities(provider, external_id);

-- Index for finding all identities of a user
CREATE INDEX IF NOT EXISTS idx_external_identities_user
ON user_external_identities(user_id);

COMMENT ON TABLE user_external_identities IS 'Links external provider accounts (Telegram, Google, etc.) to WellWon users';
