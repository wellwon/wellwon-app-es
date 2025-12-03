-- =============================================================================
-- WellWon Platform - Reference Database Schema
-- Declarant/Customs Module Reference Tables
-- =============================================================================
-- Version: 1.0.0
-- Date: 2025-12-02
--
-- Purpose: Reference data for Customs/Declarant domain
-- - Kontur API form definitions and templates
-- - Russian customs reference data (procedures, customs offices, etc.)
-- - Static reference tables (currencies, units, document types)
--
-- This database is separate from the main database for:
-- 1. Data isolation (reference vs transactional)
-- 2. Independent scaling (read-heavy workload)
-- 3. Separate backup/recovery policies
-- 4. Future sharding/replication strategies
-- =============================================================================

-- Set default schema
SET search_path = public;

-- =============================================================================
-- EXTENSIONS
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- Fuzzy text search (provides gin_trgm_ops for GIN indexes)

-- NOTE: IDEs may show warnings about "gin_trgm_ops" - this is harmless
-- The operator class is provided by pg_trgm extension and works correctly in PostgreSQL

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Trigger function for updated_at timestamp
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION trigger_set_updated_at IS 'Auto-update updated_at timestamp on row modification';

-- =============================================================================
-- PART 1: FORM SYSTEM (Dynamic Forms from Kontur API)
-- =============================================================================

-- 1. JSON Templates (from Kontur API /common/v1/jsonTemplates)
CREATE TABLE IF NOT EXISTS dc_json_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gf_code TEXT NOT NULL,                       -- Kontur internal code (e.g. "18003")
    document_mode_id TEXT NOT NULL,              -- Form ID per FTS album (e.g. "1006107E")
    type_name TEXT NOT NULL,                     -- Template variant name
    document_type_code VARCHAR(10),              -- Document type code (link to dc_document_types.code)
    is_active BOOLEAN DEFAULT TRUE,              -- Is template active
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    -- Unique per combination of gf + documentModeId + typeName
    UNIQUE(gf_code, document_mode_id, type_name)
);

CREATE INDEX IF NOT EXISTS idx_dc_json_templates_gf_code
    ON dc_json_templates(gf_code);
CREATE INDEX IF NOT EXISTS idx_dc_json_templates_document_mode_id
    ON dc_json_templates(document_mode_id);
CREATE INDEX IF NOT EXISTS idx_dc_json_templates_is_active
    ON dc_json_templates(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_dc_json_templates_type_name
    ON dc_json_templates USING gin(type_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_dc_json_templates_document_type_code
    ON dc_json_templates(document_type_code) WHERE document_type_code IS NOT NULL;

DROP TRIGGER IF EXISTS set_dc_json_templates_updated_at ON dc_json_templates;
CREATE TRIGGER set_dc_json_templates_updated_at
    BEFORE UPDATE ON dc_json_templates
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_json_templates IS 'Kontur Declarant JSON form templates (from /common/v1/jsonTemplates)';
COMMENT ON COLUMN dc_json_templates.gf_code IS 'Kontur internal code (gf)';
COMMENT ON COLUMN dc_json_templates.document_mode_id IS 'Form ID per FTS formats album';
COMMENT ON COLUMN dc_json_templates.type_name IS 'Template variant name';


-- 2. Form Definitions (Preprocessed Kontur schemas)
CREATE TABLE IF NOT EXISTS dc_form_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_mode_id VARCHAR(20) NOT NULL UNIQUE,   -- Form ID (e.g. "1002007E")
    gf_code VARCHAR(20) NOT NULL,                   -- Kontur internal code
    type_name VARCHAR(500) NOT NULL,                -- Form name

    -- Processed form structure
    fields JSONB NOT NULL DEFAULT '[]',             -- Array of field definitions
    default_values JSONB DEFAULT '{}',              -- Default values

    -- Original schema for change tracking
    kontur_schema_json JSONB,                       -- Source schema from Kontur
    kontur_schema_hash VARCHAR(64),                 -- SHA256 for comparison

    -- Metadata
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

DROP TRIGGER IF EXISTS set_dc_form_definitions_updated_at ON dc_form_definitions;
CREATE TRIGGER set_dc_form_definitions_updated_at
    BEFORE UPDATE ON dc_form_definitions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_form_definitions IS 'Form definitions for universal renderer (from Kontur JSON schemas)';
COMMENT ON COLUMN dc_form_definitions.fields IS 'JSONB array of form field definitions';
COMMENT ON COLUMN dc_form_definitions.kontur_schema_json IS 'Original Kontur JSON schema for change tracking';
COMMENT ON COLUMN dc_form_definitions.kontur_schema_hash IS 'SHA256 hash for fast comparison during sync';


-- 3. Field Labels (Russian localization)
CREATE TABLE IF NOT EXISTS dc_field_labels_ru (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    field_path VARCHAR(500) NOT NULL UNIQUE,        -- Field path: "ESADout_CUConsignee.EqualIndicator"
    label_ru VARCHAR(500) NOT NULL,                 -- Russian label: "Совпадает с декларантом"
    hint_ru VARCHAR(1000),                          -- Tooltip hint
    placeholder_ru VARCHAR(200),                    -- Input placeholder
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_field_labels_path
    ON dc_field_labels_ru(field_path);
CREATE INDEX IF NOT EXISTS idx_dc_field_labels_path_prefix
    ON dc_field_labels_ru USING gin(field_path gin_trgm_ops);

DROP TRIGGER IF EXISTS set_dc_field_labels_ru_updated_at ON dc_field_labels_ru;
CREATE TRIGGER set_dc_field_labels_ru_updated_at
    BEFORE UPDATE ON dc_field_labels_ru
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_field_labels_ru IS 'Russian labels for form fields (localization separate from schemas)';


-- 4. Form Sections (Custom UI grouping)
CREATE TABLE IF NOT EXISTS dc_form_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_definition_id UUID REFERENCES dc_form_definitions(id) ON DELETE CASCADE,

    section_key VARCHAR(100) NOT NULL,              -- Section key: "organizations"
    title_ru VARCHAR(200) NOT NULL,                 -- Title: "Организации"
    description_ru VARCHAR(500),                    -- Section description
    icon VARCHAR(50) DEFAULT 'FileText',            -- Lucide icon name
    sort_order INTEGER DEFAULT 0,                   -- Sort order
    field_paths JSONB NOT NULL DEFAULT '[]',        -- Array of field paths: ["sender.name", "sender.inn"]
    fields_config JSONB DEFAULT '[]',               -- Full field configurations from Form Builder
    columns INTEGER DEFAULT 2,                      -- Number of grid columns
    collapsible BOOLEAN DEFAULT FALSE,              -- Can collapse section
    default_expanded BOOLEAN DEFAULT TRUE,          -- Expanded by default

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(form_definition_id, section_key)
);

CREATE INDEX IF NOT EXISTS idx_dc_form_sections_definition
    ON dc_form_sections(form_definition_id);

DROP TRIGGER IF EXISTS set_dc_form_sections_updated_at ON dc_form_sections;
CREATE TRIGGER set_dc_form_sections_updated_at
    BEFORE UPDATE ON dc_form_sections
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_form_sections IS 'Custom sections for grouping fields in form UI';
COMMENT ON COLUMN dc_form_sections.fields_config IS 'Full field configurations from Form Builder (id, schemaPath, width, customLabel, etc.)';


-- 5. Form Sync History (Audit trail)
CREATE TABLE IF NOT EXISTS dc_form_sync_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_mode_id VARCHAR(20),                   -- NULL for full sync
    sync_type VARCHAR(20) NOT NULL,                 -- 'full', 'single'
    status VARCHAR(20) NOT NULL,                    -- 'success', 'partial', 'failed'

    total_processed INTEGER DEFAULT 0,
    forms_created INTEGER DEFAULT 0,
    forms_updated INTEGER DEFAULT 0,
    schemas_changed INTEGER DEFAULT 0,              -- Number of changed schemas
    errors INTEGER DEFAULT 0,
    error_details JSONB,                            -- Array of errors

    sync_duration_ms INTEGER,                       -- Sync duration
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_form_sync_history_document
    ON dc_form_sync_history(document_mode_id);
CREATE INDEX IF NOT EXISTS idx_dc_form_sync_history_date
    ON dc_form_sync_history(synced_at DESC);

COMMENT ON TABLE dc_form_sync_history IS 'Form definition sync history from Kontur API';


-- 6. Form Templates (Form Builder templates with versioning)
CREATE TABLE IF NOT EXISTS dc_form_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to JSON schema
    document_mode_id VARCHAR(20) NOT NULL,            -- Form ID (e.g. "1002007E")
    gf_code VARCHAR(20) NOT NULL,                     -- Kontur internal code
    type_name VARCHAR(500) NOT NULL,                  -- Document type name

    -- Template metadata
    name VARCHAR(200) NOT NULL,                       -- Template name
    description TEXT,                                 -- Template description

    -- Versioning
    version INTEGER DEFAULT 1,
    version_label VARCHAR(100),                       -- Version label (e.g. "v1.0.0")
    is_draft BOOLEAN DEFAULT TRUE,                    -- Draft status
    is_published BOOLEAN DEFAULT FALSE,               -- Published status
    published_at TIMESTAMPTZ,                         -- Publication date
    status VARCHAR(20) DEFAULT 'draft',               -- draft, published, archived

    -- Form configuration (JSONB)
    sections JSONB NOT NULL DEFAULT '[]',             -- Array of sections with fields
    default_values JSONB DEFAULT '{}',                -- Default values

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,                                  -- User ID (cross-database reference, nullable)
    updated_by UUID,

    -- Statistics
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMPTZ,

    -- PostgreSQL 18 feature: NULLS NOT DISTINCT in unique constraints
    -- Ensures only one published template per document_mode_id
    CONSTRAINT unique_published_template
        UNIQUE NULLS NOT DISTINCT (document_mode_id, is_published)
);

CREATE INDEX IF NOT EXISTS idx_dc_form_templates_document_mode
    ON dc_form_templates(document_mode_id);
CREATE INDEX IF NOT EXISTS idx_dc_form_templates_status
    ON dc_form_templates(status);
CREATE INDEX IF NOT EXISTS idx_dc_form_templates_is_published
    ON dc_form_templates(is_published) WHERE is_published = TRUE;
CREATE INDEX IF NOT EXISTS idx_dc_form_templates_created_by
    ON dc_form_templates(created_by);

DROP TRIGGER IF EXISTS set_dc_form_templates_updated_at ON dc_form_templates;
CREATE TRIGGER set_dc_form_templates_updated_at
    BEFORE UPDATE ON dc_form_templates
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_form_templates IS 'Form Builder templates';
COMMENT ON COLUMN dc_form_templates.sections IS 'JSONB array of sections with field configuration';
COMMENT ON COLUMN dc_form_templates.created_by IS 'User ID from main database (enforce in application, not FK)';


-- 7. Form Template Versions (Version snapshots)
CREATE TABLE IF NOT EXISTS dc_form_template_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES dc_form_templates(id) ON DELETE CASCADE,

    -- Version number
    version INTEGER NOT NULL,
    version_label VARCHAR(100),                       -- Version label

    -- Configuration snapshot at publication
    sections_snapshot JSONB NOT NULL,                 -- Copy of sections
    default_values_snapshot JSONB DEFAULT '{}',       -- Copy of default values

    -- Metadata
    change_description TEXT,                          -- Change description
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,

    UNIQUE(template_id, version)
);

CREATE INDEX IF NOT EXISTS idx_dc_form_template_versions_template
    ON dc_form_template_versions(template_id);
CREATE INDEX IF NOT EXISTS idx_dc_form_template_versions_version
    ON dc_form_template_versions(template_id, version DESC);

COMMENT ON TABLE dc_form_template_versions IS 'Form template version history';


-- 8. Form Template Drafts (Auto-save per user)
CREATE TABLE IF NOT EXISTS dc_form_template_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link
    template_id UUID REFERENCES dc_form_templates(id) ON DELETE CASCADE,
    document_mode_id VARCHAR(20),                     -- For new templates without template_id
    user_id UUID NOT NULL,                            -- User ID from main database

    -- Draft data
    draft_data JSONB NOT NULL,                        -- Partial template data

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- One draft per user for each template/document_mode
    UNIQUE NULLS NOT DISTINCT (template_id, user_id),
    UNIQUE NULLS NOT DISTINCT (document_mode_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_dc_form_template_drafts_template
    ON dc_form_template_drafts(template_id);
CREATE INDEX IF NOT EXISTS idx_dc_form_template_drafts_user
    ON dc_form_template_drafts(user_id);
CREATE INDEX IF NOT EXISTS idx_dc_form_template_drafts_document_mode
    ON dc_form_template_drafts(document_mode_id) WHERE document_mode_id IS NOT NULL;

DROP TRIGGER IF EXISTS set_dc_form_template_drafts_updated_at ON dc_form_template_drafts;
CREATE TRIGGER set_dc_form_template_drafts_updated_at
    BEFORE UPDATE ON dc_form_template_drafts
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_form_template_drafts IS 'Template drafts for auto-save';


-- 9. Form Definition Versions (Version snapshots)
CREATE TABLE IF NOT EXISTS dc_form_definition_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_mode_id VARCHAR(20) NOT NULL,            -- Form ID
    version_number INTEGER NOT NULL,                   -- Version number (1, 2, 3...)
    version_label VARCHAR(100),                        -- Version label ("Version 1.0", "After review")
    change_description TEXT,                           -- Change description

    -- Section snapshot at save
    sections_snapshot JSONB NOT NULL DEFAULT '[]',     -- Full section data

    -- Statistics
    fields_count INTEGER DEFAULT 0,                    -- Field count in version
    sections_count INTEGER DEFAULT 0,                  -- Section count in version

    -- Current version flag
    is_current BOOLEAN DEFAULT FALSE,                  -- Current active version

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,                                   -- User ID (optional)

    UNIQUE(document_mode_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_dc_form_definition_versions_document
    ON dc_form_definition_versions(document_mode_id);
CREATE INDEX IF NOT EXISTS idx_dc_form_definition_versions_current
    ON dc_form_definition_versions(document_mode_id, is_current) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_dc_form_definition_versions_number
    ON dc_form_definition_versions(document_mode_id, version_number DESC);

COMMENT ON TABLE dc_form_definition_versions IS 'Form definition versions - section snapshots for Form Builder';
COMMENT ON COLUMN dc_form_definition_versions.sections_snapshot IS 'JSONB array of sections at version save';
COMMENT ON COLUMN dc_form_definition_versions.is_current IS 'Current active version flag';


-- =============================================================================
-- FORM TEMPLATE HELPER FUNCTIONS
-- =============================================================================

-- Function to increment usage_count when template is used
CREATE OR REPLACE FUNCTION dc_increment_template_usage(p_template_id UUID)
RETURNS void AS $$
BEGIN
    UPDATE dc_form_templates
    SET usage_count = usage_count + 1,
        last_used_at = NOW()
    WHERE id = p_template_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION dc_increment_template_usage IS 'Increment template usage counter';


-- Function to create new version on publication
CREATE OR REPLACE FUNCTION dc_create_template_version(
    p_template_id UUID,
    p_version_label VARCHAR(100) DEFAULT NULL,
    p_change_description TEXT DEFAULT NULL,
    p_user_id UUID DEFAULT NULL
)
RETURNS INTEGER AS $$
DECLARE
    v_new_version INTEGER;
    v_sections JSONB;
    v_default_values JSONB;
BEGIN
    -- Get current version number
    SELECT COALESCE(MAX(version), 0) + 1 INTO v_new_version
    FROM dc_form_template_versions
    WHERE template_id = p_template_id;

    -- Get current configuration
    SELECT sections, default_values INTO v_sections, v_default_values
    FROM dc_form_templates
    WHERE id = p_template_id;

    -- Create version
    INSERT INTO dc_form_template_versions (
        template_id,
        version,
        version_label,
        sections_snapshot,
        default_values_snapshot,
        change_description,
        created_by
    ) VALUES (
        p_template_id,
        v_new_version,
        p_version_label,
        v_sections,
        v_default_values,
        p_change_description,
        p_user_id
    );

    -- Update version in template
    UPDATE dc_form_templates
    SET version = v_new_version,
        version_label = p_version_label,
        is_published = TRUE,
        is_draft = FALSE,
        status = 'published',
        published_at = NOW(),
        updated_by = p_user_id
    WHERE id = p_template_id;

    RETURN v_new_version;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION dc_create_template_version IS 'Create new template version and publish';


-- Function to restore version
CREATE OR REPLACE FUNCTION dc_restore_template_version(
    p_template_id UUID,
    p_version INTEGER,
    p_user_id UUID DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_version_record RECORD;
BEGIN
    -- Get version
    SELECT * INTO v_version_record
    FROM dc_form_template_versions
    WHERE template_id = p_template_id AND version = p_version;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Restore configuration
    UPDATE dc_form_templates
    SET sections = v_version_record.sections_snapshot,
        default_values = v_version_record.default_values_snapshot,
        is_draft = TRUE,
        updated_by = p_user_id
    WHERE id = p_template_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION dc_restore_template_version IS 'Restore template from version snapshot';


-- =============================================================================
-- PART 2: REFERENCE DATA (Customs/Declarant Module)
-- =============================================================================

-- 10. Customs Offices (from Kontur API /common/v1/options/customs)
CREATE TABLE IF NOT EXISTS dc_customs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kontur_id VARCHAR(100) NOT NULL UNIQUE,          -- ID from Kontur API
    code VARCHAR(20),                                 -- Customs office code (8 digits)
    short_name VARCHAR(200),                          -- Short name
    full_name VARCHAR(500),                           -- Full name
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_customs_kontur_id ON dc_customs(kontur_id);
CREATE INDEX IF NOT EXISTS idx_dc_customs_code ON dc_customs(code);
CREATE INDEX IF NOT EXISTS idx_dc_customs_is_active ON dc_customs(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_dc_customs_name ON dc_customs USING gin(short_name gin_trgm_ops);

DROP TRIGGER IF EXISTS set_dc_customs_updated_at ON dc_customs;
CREATE TRIGGER set_dc_customs_updated_at
    BEFORE UPDATE ON dc_customs
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_customs IS 'Customs offices reference (from Kontur API /common/v1/options/customs)';


-- 11. Declaration Types (from Kontur API /common/v1/options/declarationTypes)
CREATE TABLE IF NOT EXISTS dc_declaration_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kontur_id INTEGER NOT NULL UNIQUE,               -- ID from Kontur API (numeric)
    description VARCHAR(200) NOT NULL,               -- Description (IM, EK, PI, etc.)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_declaration_types_kontur_id ON dc_declaration_types(kontur_id);
CREATE INDEX IF NOT EXISTS idx_dc_declaration_types_is_active ON dc_declaration_types(is_active) WHERE is_active = TRUE;

DROP TRIGGER IF EXISTS set_dc_declaration_types_updated_at ON dc_declaration_types;
CREATE TRIGGER set_dc_declaration_types_updated_at
    BEFORE UPDATE ON dc_declaration_types
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_declaration_types IS 'Declaration types / movement directions reference (from Kontur API /common/v1/options/declarationTypes)';


-- 12. Customs Procedures (from Kontur API /common/v1/options/declarationProcedureTypes)
CREATE TABLE IF NOT EXISTS dc_procedures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kontur_id INTEGER NOT NULL,                      -- ID from Kontur API (numeric)
    declaration_type_id INTEGER NOT NULL,            -- Which declaration type (foreign key to kontur_id)
    code VARCHAR(10) NOT NULL,                       -- Procedure code (40, 10, etc.)
    name VARCHAR(500) NOT NULL,                      -- Procedure name
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(kontur_id, declaration_type_id)
);

CREATE INDEX IF NOT EXISTS idx_dc_procedures_kontur_id ON dc_procedures(kontur_id);
CREATE INDEX IF NOT EXISTS idx_dc_procedures_declaration_type ON dc_procedures(declaration_type_id);
CREATE INDEX IF NOT EXISTS idx_dc_procedures_code ON dc_procedures(code);
CREATE INDEX IF NOT EXISTS idx_dc_procedures_is_active ON dc_procedures(is_active) WHERE is_active = TRUE;

DROP TRIGGER IF EXISTS set_dc_procedures_updated_at ON dc_procedures;
CREATE TRIGGER set_dc_procedures_updated_at
    BEFORE UPDATE ON dc_procedures
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_procedures IS 'Customs procedures reference (from Kontur API /common/v1/options/declarationProcedureTypes)';


-- 13. Packaging Groups (Static reference)
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

DROP TRIGGER IF EXISTS set_dc_packaging_groups_updated_at ON dc_packaging_groups;
CREATE TRIGGER set_dc_packaging_groups_updated_at
    BEFORE UPDATE ON dc_packaging_groups
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_packaging_groups IS 'Packaging groups reference';


-- 14. Currencies (Static reference)
CREATE TABLE IF NOT EXISTS dc_currencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(10) NOT NULL UNIQUE,           -- Numeric code (643, 840, etc.)
    alpha_code VARCHAR(3) NOT NULL,              -- Alpha code (RUB, USD, etc.)
    name VARCHAR(200) NOT NULL,                  -- Currency name
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_currencies_code ON dc_currencies(code);
CREATE INDEX IF NOT EXISTS idx_dc_currencies_alpha_code ON dc_currencies(alpha_code);
CREATE INDEX IF NOT EXISTS idx_dc_currencies_is_active ON dc_currencies(is_active) WHERE is_active = TRUE;

DROP TRIGGER IF EXISTS set_dc_currencies_updated_at ON dc_currencies;
CREATE TRIGGER set_dc_currencies_updated_at
    BEFORE UPDATE ON dc_currencies
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_currencies IS 'Currencies reference';


-- 15. Enterprise Categories (Static reference)
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

DROP TRIGGER IF EXISTS set_dc_enterprise_categories_updated_at ON dc_enterprise_categories;
CREATE TRIGGER set_dc_enterprise_categories_updated_at
    BEFORE UPDATE ON dc_enterprise_categories
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_enterprise_categories IS 'Enterprise categories reference';


-- 16. Measurement Units (Static reference)
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

DROP TRIGGER IF EXISTS set_dc_measurement_units_updated_at ON dc_measurement_units;
CREATE TRIGGER set_dc_measurement_units_updated_at
    BEFORE UPDATE ON dc_measurement_units
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_measurement_units IS 'Measurement units reference';


-- 17. Document Types (Static reference)
CREATE TABLE IF NOT EXISTS dc_document_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(10) NOT NULL UNIQUE,            -- Document code (01011, 02011, etc.)
    name TEXT NOT NULL,                          -- Document name
    ed_documents TEXT,                           -- ED-documents (electronic document types)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_document_types_code ON dc_document_types(code);
CREATE INDEX IF NOT EXISTS idx_dc_document_types_is_active ON dc_document_types(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_dc_document_types_name ON dc_document_types USING gin(name gin_trgm_ops);

DROP TRIGGER IF EXISTS set_dc_document_types_updated_at ON dc_document_types;
CREATE TRIGGER set_dc_document_types_updated_at
    BEFORE UPDATE ON dc_document_types
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE dc_document_types IS 'Document types reference';


-- =============================================================================
-- SCHEMA MIGRATIONS TRACKING
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    applied_by VARCHAR(100) DEFAULT 'system'
);

-- Insert initial migration record
INSERT INTO schema_migrations (version, description, applied_by)
VALUES ('1.0.0', 'Initial wellwon_reference schema with 18 declarant tables', 'system')
ON CONFLICT (version) DO NOTHING;


-- =============================================================================
-- SUMMARY
-- =============================================================================

SELECT 'wellwon_reference schema created successfully' as status,
       'Total tables: 18 (9 form system + 8 reference data + 1 schema_migrations)' as details,
       NOW() as created_at;
