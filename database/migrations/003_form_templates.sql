-- =============================================================================
-- Migration: Form Templates Tables
-- Description: Tables for Form Builder - custom form templates with versions
-- =============================================================================

-- Шаблоны форм (конфигурация UI для конструктора форм)
CREATE TABLE IF NOT EXISTS dc_form_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Связь с JSON схемой
    document_mode_id VARCHAR(20) NOT NULL,            -- ID формы (например "1002007E")
    gf_code VARCHAR(20) NOT NULL,                     -- Внутренний код Kontur
    type_name VARCHAR(500) NOT NULL,                  -- Название типа документа

    -- Метаданные шаблона
    name VARCHAR(200) NOT NULL,                       -- Название шаблона
    description TEXT,                                 -- Описание шаблона

    -- Версионирование
    version INTEGER DEFAULT 1,
    version_label VARCHAR(100),                       -- Метка версии (например "v1.0.0")
    is_draft BOOLEAN DEFAULT TRUE,                    -- Черновик
    is_published BOOLEAN DEFAULT FALSE,               -- Опубликован
    published_at TIMESTAMPTZ,                         -- Дата публикации
    status VARCHAR(20) DEFAULT 'draft',               -- draft, published, archived

    -- Конфигурация формы (JSONB)
    sections JSONB NOT NULL DEFAULT '[]',             -- Массив секций с полями
    default_values JSONB DEFAULT '{}',                -- Значения по умолчанию

    -- Метаданные
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES ww_user_accounts(user_id) ON DELETE SET NULL,
    updated_by UUID REFERENCES ww_user_accounts(user_id) ON DELETE SET NULL,

    -- Статистика
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMPTZ,

    -- Уникальность: один опубликованный шаблон на document_mode_id
    CONSTRAINT unique_published_template
        UNIQUE NULLS NOT DISTINCT (document_mode_id, is_published)
        WHERE (is_published = TRUE)
);

CREATE INDEX IF NOT EXISTS idx_dc_form_templates_document_mode
    ON dc_form_templates(document_mode_id);
CREATE INDEX IF NOT EXISTS idx_dc_form_templates_status
    ON dc_form_templates(status);
CREATE INDEX IF NOT EXISTS idx_dc_form_templates_is_published
    ON dc_form_templates(is_published) WHERE is_published = TRUE;
CREATE INDEX IF NOT EXISTS idx_dc_form_templates_created_by
    ON dc_form_templates(created_by);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_dc_form_templates_updated_at') THEN
        CREATE TRIGGER set_dc_form_templates_updated_at
            BEFORE UPDATE ON dc_form_templates
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    END IF;
END
$$;

COMMENT ON TABLE dc_form_templates IS 'Шаблоны форм для конструктора форм';
COMMENT ON COLUMN dc_form_templates.sections IS 'JSONB массив секций с конфигурацией полей';

-- Версии шаблонов (история изменений)
CREATE TABLE IF NOT EXISTS dc_form_template_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES dc_form_templates(id) ON DELETE CASCADE,

    -- Номер версии
    version INTEGER NOT NULL,
    version_label VARCHAR(100),                       -- Метка версии

    -- Снапшот конфигурации на момент публикации
    sections_snapshot JSONB NOT NULL,                 -- Копия секций
    default_values_snapshot JSONB DEFAULT '{}',       -- Копия значений по умолчанию

    -- Метаданные
    change_description TEXT,                          -- Описание изменений
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES ww_user_accounts(user_id) ON DELETE SET NULL,

    UNIQUE(template_id, version)
);

CREATE INDEX IF NOT EXISTS idx_dc_form_template_versions_template
    ON dc_form_template_versions(template_id);
CREATE INDEX IF NOT EXISTS idx_dc_form_template_versions_version
    ON dc_form_template_versions(template_id, version DESC);

COMMENT ON TABLE dc_form_template_versions IS 'История версий шаблонов форм';

-- Черновики шаблонов (автосохранение для каждого пользователя)
CREATE TABLE IF NOT EXISTS dc_form_template_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Связь
    template_id UUID REFERENCES dc_form_templates(id) ON DELETE CASCADE,
    document_mode_id VARCHAR(20),                     -- Для новых шаблонов без template_id
    user_id UUID NOT NULL REFERENCES ww_user_accounts(user_id) ON DELETE CASCADE,

    -- Данные черновика
    draft_data JSONB NOT NULL,                        -- Частичные данные шаблона

    -- Метаданные
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Один черновик на пользователя для каждого шаблона/document_mode
    UNIQUE(template_id, user_id),
    UNIQUE(document_mode_id, user_id) WHERE template_id IS NULL
);

CREATE INDEX IF NOT EXISTS idx_dc_form_template_drafts_template
    ON dc_form_template_drafts(template_id);
CREATE INDEX IF NOT EXISTS idx_dc_form_template_drafts_user
    ON dc_form_template_drafts(user_id);
CREATE INDEX IF NOT EXISTS idx_dc_form_template_drafts_document_mode
    ON dc_form_template_drafts(document_mode_id) WHERE document_mode_id IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_dc_form_template_drafts_updated_at') THEN
        CREATE TRIGGER set_dc_form_template_drafts_updated_at
            BEFORE UPDATE ON dc_form_template_drafts
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    END IF;
END
$$;

COMMENT ON TABLE dc_form_template_drafts IS 'Черновики шаблонов для автосохранения';

-- =============================================================================
-- Helper Functions
-- =============================================================================

-- Функция для инкремента usage_count при использовании шаблона
CREATE OR REPLACE FUNCTION dc_increment_template_usage(p_template_id UUID)
RETURNS void AS $$
BEGIN
    UPDATE dc_form_templates
    SET usage_count = usage_count + 1,
        last_used_at = NOW()
    WHERE id = p_template_id;
END;
$$ LANGUAGE plpgsql;

-- Функция для создания новой версии при публикации
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
    -- Получить текущий номер версии
    SELECT COALESCE(MAX(version), 0) + 1 INTO v_new_version
    FROM dc_form_template_versions
    WHERE template_id = p_template_id;

    -- Получить текущую конфигурацию
    SELECT sections, default_values INTO v_sections, v_default_values
    FROM dc_form_templates
    WHERE id = p_template_id;

    -- Создать версию
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

    -- Обновить версию в шаблоне
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

-- Функция для восстановления версии
CREATE OR REPLACE FUNCTION dc_restore_template_version(
    p_template_id UUID,
    p_version INTEGER,
    p_user_id UUID DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_version_record RECORD;
BEGIN
    -- Получить версию
    SELECT * INTO v_version_record
    FROM dc_form_template_versions
    WHERE template_id = p_template_id AND version = p_version;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Восстановить конфигурацию
    UPDATE dc_form_templates
    SET sections = v_version_record.sections_snapshot,
        default_values = v_version_record.default_values_snapshot,
        is_draft = TRUE,
        updated_by = p_user_id
    WHERE id = p_template_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- DONE
-- =============================================================================
SELECT 'Form Templates tables created successfully' as status;
