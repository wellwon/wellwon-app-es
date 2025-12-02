-- =============================================================================
-- Migration: Dynamic Forms Tables
-- Description: Tables for universal form generator from Kontur JSON schemas
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

-- Create trigger only if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_dc_form_definitions_updated_at') THEN
        CREATE TRIGGER set_dc_form_definitions_updated_at
            BEFORE UPDATE ON dc_form_definitions
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    END IF;
END
$$;

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

-- Create trgm extension if not exists (for fuzzy search)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_dc_field_labels_path_prefix
    ON dc_field_labels_ru USING gin(field_path gin_trgm_ops);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_dc_field_labels_ru_updated_at') THEN
        CREATE TRIGGER set_dc_field_labels_ru_updated_at
            BEFORE UPDATE ON dc_field_labels_ru
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    END IF;
END
$$;

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

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_dc_form_sections_updated_at') THEN
        CREATE TRIGGER set_dc_form_sections_updated_at
            BEFORE UPDATE ON dc_form_sections
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    END IF;
END
$$;

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
-- DONE
-- =============================================================================
SELECT 'Dynamic Forms tables created successfully' as status;
