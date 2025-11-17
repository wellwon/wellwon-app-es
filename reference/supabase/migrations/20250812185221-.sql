-- Добавляем функции для обновления чатов с Telegram данными
CREATE OR REPLACE FUNCTION public.update_chat_telegram_settings(
  chat_uuid UUID,
  enable_sync BOOLEAN,
  supergroup_id BIGINT DEFAULT NULL,
  topic_id INTEGER DEFAULT NULL
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = 'public'
AS $$
BEGIN
  -- Проверяем права пользователя на этот чат
  IF NOT EXISTS (
    SELECT 1 FROM public.chat_participants cp
    WHERE cp.chat_id = chat_uuid 
      AND cp.user_id = auth.uid()
      AND cp.is_active = true
      AND cp.role IN ('admin', 'observer')
  ) AND NOT EXISTS (
    SELECT 1 FROM public.profiles p
    WHERE p.user_id = auth.uid() 
      AND COALESCE(p.developer, false) = true
  ) THEN
    RETURN FALSE;
  END IF;

  -- Обновляем настройки Telegram для чата
  UPDATE public.chats
  SET 
    telegram_sync = enable_sync,
    telegram_supergroup_id = CASE WHEN enable_sync THEN supergroup_id ELSE NULL END,
    telegram_topic_id = CASE WHEN enable_sync THEN topic_id ELSE NULL END,
    updated_at = now()
  WHERE id = chat_uuid;

  RETURN TRUE;
END;
$$;

-- Функция для получения чатов с Telegram данными
CREATE OR REPLACE FUNCTION public.get_chat_with_telegram_data(chat_uuid UUID)
RETURNS TABLE(
  id UUID,
  name TEXT,
  type TEXT,
  company_id BIGINT,
  telegram_sync BOOLEAN,
  telegram_supergroup_id BIGINT,
  telegram_topic_id INTEGER,
  created_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = 'public'
AS $$
  SELECT 
    c.id,
    c.name,
    c.type,
    c.company_id,
    c.telegram_sync,
    c.telegram_supergroup_id,
    c.telegram_topic_id,
    c.created_at,
    c.updated_at
  FROM public.chats c
  WHERE c.id = chat_uuid
    AND (
      -- Пользователь участвует в чате
      EXISTS (
        SELECT 1 FROM public.chat_participants cp
        WHERE cp.chat_id = c.id 
          AND cp.user_id = auth.uid()
          AND cp.is_active = true
      )
      OR
      -- Или является разработчиком
      EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.user_id = auth.uid() 
          AND COALESCE(p.developer, false) = true
      )
    );
$$;