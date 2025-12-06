-- =============================================================================
-- Migration: 004_fix_existing_companies.sql
-- Description: Fix existing companies table to use UUID
-- RUN THIS FIRST before re-running wellwon.sql
-- =============================================================================

-- Drop dependent objects first
DROP FUNCTION IF EXISTS get_user_companies(UUID, user_company_relationship) CASCADE;
DROP FUNCTION IF EXISTS get_company_users(UUID, user_company_relationship) CASCADE;
DROP FUNCTION IF EXISTS get_company_users(BIGINT, user_company_relationship) CASCADE;

-- Drop foreign keys
ALTER TABLE IF EXISTS telegram_supergroups DROP CONSTRAINT IF EXISTS telegram_supergroups_company_id_fkey;
ALTER TABLE IF EXISTS user_companies DROP CONSTRAINT IF EXISTS user_companies_company_id_fkey;
ALTER TABLE IF EXISTS user_companies DROP CONSTRAINT IF EXISTS user_companies_unique;

-- Drop the old tables (will lose data - backup first if needed!)
DROP TABLE IF EXISTS user_companies CASCADE;
DROP TABLE IF EXISTS telegram_supergroups CASCADE;
DROP TABLE IF EXISTS companies CASCADE;

-- Now the tables will be recreated fresh when you run wellwon.sql
SELECT 'Old tables dropped. Now run wellwon.sql to recreate with correct schema.' as status;
