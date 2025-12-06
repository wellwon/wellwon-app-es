-- =============================================================================
-- Migration: 006_rename_company_type_to_client_type.sql
-- Description: Rename company_type to client_type for semantic clarity
-- Both companies and projects are "clients" in WellWon business context
-- Values: 'company' | 'project'
-- =============================================================================

-- Rename column from company_type to client_type
ALTER TABLE companies RENAME COLUMN company_type TO client_type;

-- Drop old index and create new one with correct name
DROP INDEX IF EXISTS idx_companies_company_type;
CREATE INDEX IF NOT EXISTS idx_companies_client_type ON companies(client_type);

-- Update wellwon.sql schema reference comment
COMMENT ON COLUMN companies.client_type IS 'Client type: company (legal entity with VAT/OGRN/KPP) or project (individual/no legal requirements)';
