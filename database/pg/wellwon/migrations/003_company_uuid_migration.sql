-- =============================================================================
-- Migration: 003_company_uuid_migration.sql
-- Description: Update companies table to use UUID primary key and add missing columns
-- =============================================================================

-- Step 1: Drop dependent constraints
ALTER TABLE user_companies DROP CONSTRAINT IF EXISTS user_companies_company_id_fkey;

-- Step 2: Add new UUID column
ALTER TABLE companies ADD COLUMN IF NOT EXISTS new_id UUID DEFAULT gen_random_uuid();

-- Step 3: Add missing columns for Event Sourcing
ALTER TABLE companies ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS user_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS created_by UUID;

-- Step 4: Migrate created_by_user_id to created_by
UPDATE companies SET created_by = created_by_user_id WHERE created_by IS NULL;

-- Step 5: Update user_companies to reference new UUID
ALTER TABLE user_companies ADD COLUMN IF NOT EXISTS new_company_id UUID;
UPDATE user_companies uc SET new_company_id = c.new_id FROM companies c WHERE uc.company_id = c.id;

-- Step 6: Drop old columns and rename new ones
ALTER TABLE user_companies DROP COLUMN IF EXISTS company_id;
ALTER TABLE user_companies RENAME COLUMN new_company_id TO company_id;
ALTER TABLE user_companies ALTER COLUMN company_id SET NOT NULL;

-- Step 7: Drop old id and rename new_id
ALTER TABLE companies DROP COLUMN IF EXISTS id CASCADE;
ALTER TABLE companies RENAME COLUMN new_id TO id;
ALTER TABLE companies ADD PRIMARY KEY (id);

-- Step 8: Recreate foreign key
ALTER TABLE user_companies
    ADD CONSTRAINT user_companies_company_id_fkey
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE;

-- Step 9: Recreate unique constraint
ALTER TABLE user_companies DROP CONSTRAINT IF EXISTS user_companies_unique;
ALTER TABLE user_companies ADD CONSTRAINT user_companies_unique UNIQUE(user_id, company_id, relationship_type);

-- Step 10: Drop legacy column
ALTER TABLE companies DROP COLUMN IF EXISTS created_by_user_id;

-- Step 11: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_companies_id ON companies(id);
CREATE INDEX IF NOT EXISTS idx_user_companies_company ON user_companies(company_id);

-- Done!
