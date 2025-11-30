-- =============================================================================
-- Migration: 003_fix_companies_table.sql
-- Description: Fix companies table to match Event Sourcing schema
-- Run each statement separately if needed
-- =============================================================================

-- Step 1: Add missing columns directly
ALTER TABLE companies ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS user_count INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS created_by UUID;

-- Step 2: Copy data from old column to new
UPDATE companies SET created_by = created_by_user_id WHERE created_by IS NULL AND created_by_user_id IS NOT NULL;

-- Step 3: Create indexes AFTER columns exist
CREATE INDEX IF NOT EXISTS idx_companies_created_by ON companies(created_by);
CREATE INDEX IF NOT EXISTS idx_companies_is_active ON companies(is_active);
