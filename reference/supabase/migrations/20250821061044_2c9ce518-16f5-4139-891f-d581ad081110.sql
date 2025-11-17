-- Обновление конфигурации Edge функции telegram-verify-topics
CREATE OR REPLACE FUNCTION update_supabase_config() RETURNS void AS $$
BEGIN
    -- Функция для обновления конфигурации Edge функций
    RAISE NOTICE 'Edge function telegram-verify-topics should be added to supabase/config.toml';
END;
$$ LANGUAGE plpgsql;