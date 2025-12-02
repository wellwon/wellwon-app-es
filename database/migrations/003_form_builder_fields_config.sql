-- =============================================================================
-- Migration: Form Builder Fields Config
-- Description: Add fields_config column to store full field configurations
-- =============================================================================

-- Add fields_config column for storing complete field configurations from Form Builder
ALTER TABLE dc_form_sections
    ADD COLUMN IF NOT EXISTS fields_config JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN dc_form_sections.fields_config IS 'Full field configurations from Form Builder (id, schemaPath, width, customLabel, etc.)';

-- =============================================================================
-- DONE
-- =============================================================================
SELECT 'Form Builder fields_config column added successfully' as status;
