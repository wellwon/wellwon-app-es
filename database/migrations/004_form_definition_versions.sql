-- =============================================================================
-- Migration: Form Definition Versions
-- Description: Table for storing version snapshots of form definitions
-- =============================================================================

-- Версии определений форм (снапшоты секций)
CREATE TABLE IF NOT EXISTS dc_form_definition_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_mode_id VARCHAR(20) NOT NULL,            -- ID формы
    version_number INTEGER NOT NULL,                   -- Номер версии (1, 2, 3...)
    version_label VARCHAR(100),                        -- Метка версии ("Версия 1.0", "После ревью")
    change_description TEXT,                           -- Описание изменений

    -- Снапшот секций на момент сохранения
    sections_snapshot JSONB NOT NULL DEFAULT '[]',     -- Полные данные секций

    -- Статистика
    fields_count INTEGER DEFAULT 0,                    -- Количество полей в версии
    sections_count INTEGER DEFAULT 0,                  -- Количество секций в версии

    -- Флаг текущей версии
    is_current BOOLEAN DEFAULT FALSE,                  -- Текущая активная версия

    -- Метаданные
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,                                   -- ID пользователя (опционально)

    UNIQUE(document_mode_id, version_number)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_dc_form_definition_versions_document
    ON dc_form_definition_versions(document_mode_id);
CREATE INDEX IF NOT EXISTS idx_dc_form_definition_versions_current
    ON dc_form_definition_versions(document_mode_id, is_current) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_dc_form_definition_versions_number
    ON dc_form_definition_versions(document_mode_id, version_number DESC);

COMMENT ON TABLE dc_form_definition_versions IS 'Версии определений форм - снапшоты секций для Form Builder';
COMMENT ON COLUMN dc_form_definition_versions.sections_snapshot IS 'JSONB массив секций на момент сохранения версии';
COMMENT ON COLUMN dc_form_definition_versions.is_current IS 'Флаг текущей активной версии';

-- =============================================================================
-- DONE
-- =============================================================================
SELECT 'Form definition versions table created successfully' as status;
