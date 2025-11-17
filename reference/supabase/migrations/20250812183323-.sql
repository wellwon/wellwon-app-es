-- Этап 1: Расширение базы данных для Telegram супергрупп

-- 1. Создаем таблицу telegram_supergroups (связь с companies)
CREATE TABLE public.telegram_supergroups (
  id BIGINT PRIMARY KEY, -- Telegram group ID
  company_id BIGINT REFERENCES public.companies(id),
  title TEXT NOT NULL,
  username TEXT,
  description TEXT,
  invite_link TEXT,
  member_count INTEGER DEFAULT 0,
  is_forum BOOLEAN DEFAULT false,
  is_active BOOLEAN DEFAULT true,
  bot_is_admin BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  metadata JSONB DEFAULT '{}'::jsonb
);

-- 2. Расширяем таблицу chats полями для Telegram
ALTER TABLE public.chats 
ADD COLUMN telegram_supergroup_id BIGINT REFERENCES public.telegram_supergroups(id),
ADD COLUMN telegram_topic_id INTEGER, -- ID темы в супергруппе (для Forum групп)
ADD COLUMN telegram_sync BOOLEAN DEFAULT false; -- флаг синхронизации с Telegram

-- 3. Создаем таблицу telegram_group_members (участники, НЕ связанные с profiles)
CREATE TABLE public.telegram_group_members (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  supergroup_id BIGINT REFERENCES public.telegram_supergroups(id),
  telegram_user_id BIGINT NOT NULL,
  username TEXT,
  first_name TEXT,
  last_name TEXT,
  is_bot BOOLEAN DEFAULT false,
  status TEXT DEFAULT 'member', -- member, administrator, creator, restricted, left, kicked
  joined_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  last_seen TIMESTAMP WITH TIME ZONE DEFAULT now(),
  is_active BOOLEAN DEFAULT true,
  metadata JSONB DEFAULT '{}'::jsonb,
  
  UNIQUE(supergroup_id, telegram_user_id)
);

-- 4. Расширяем таблицу messages полями для Telegram
ALTER TABLE public.messages 
ADD COLUMN telegram_message_id BIGINT, -- ID сообщения в Telegram
ADD COLUMN telegram_user_id BIGINT, -- ID пользователя Telegram (НЕ из profiles)
ADD COLUMN telegram_user_data JSONB, -- данные пользователя Telegram (имя, username и тд)
ADD COLUMN telegram_topic_id INTEGER, -- ID темы в супергруппе
ADD COLUMN telegram_forward_data JSONB, -- данные о пересланном сообщении
ADD COLUMN sync_direction TEXT DEFAULT 'bidirectional'; -- 'telegram_to_web', 'web_to_telegram', 'bidirectional'

-- 5. Включаем RLS для новых таблиц
ALTER TABLE public.telegram_supergroups ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.telegram_group_members ENABLE ROW LEVEL SECURITY;

-- 6. Создаем RLS политики для telegram_supergroups
CREATE POLICY "Developers can manage all supergroups" 
ON public.telegram_supergroups 
FOR ALL 
USING (
  SELECT COALESCE(developer, false) 
  FROM public.profiles 
  WHERE user_id = auth.uid()
);

CREATE POLICY "Users can view supergroups of their companies" 
ON public.telegram_supergroups 
FOR SELECT 
USING (
  company_id IN (
    SELECT uc.company_id 
    FROM public.user_companies uc 
    WHERE uc.user_id = auth.uid() AND uc.is_active = true
  )
);

-- 7. Создаем RLS политики для telegram_group_members
CREATE POLICY "Developers can manage all group members" 
ON public.telegram_group_members 
FOR ALL 
USING (
  SELECT COALESCE(developer, false) 
  FROM public.profiles 
  WHERE user_id = auth.uid()
);

CREATE POLICY "Users can view members of their company supergroups" 
ON public.telegram_group_members 
FOR SELECT 
USING (
  supergroup_id IN (
    SELECT tsg.id 
    FROM public.telegram_supergroups tsg
    JOIN public.user_companies uc ON uc.company_id = tsg.company_id
    WHERE uc.user_id = auth.uid() AND uc.is_active = true
  )
);

-- 8. Создаем функцию обновления updated_at для telegram_supergroups
CREATE TRIGGER update_telegram_supergroups_updated_at
BEFORE UPDATE ON public.telegram_supergroups
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- 9. Создаем индексы для производительности
CREATE INDEX idx_telegram_supergroups_company_id ON public.telegram_supergroups(company_id);
CREATE INDEX idx_chats_telegram_supergroup_id ON public.chats(telegram_supergroup_id);
CREATE INDEX idx_chats_telegram_topic_id ON public.chats(telegram_topic_id);
CREATE INDEX idx_telegram_group_members_supergroup_id ON public.telegram_group_members(supergroup_id);
CREATE INDEX idx_telegram_group_members_telegram_user_id ON public.telegram_group_members(telegram_user_id);
CREATE INDEX idx_messages_telegram_message_id ON public.messages(telegram_message_id);
CREATE INDEX idx_messages_telegram_user_id ON public.messages(telegram_user_id);
CREATE INDEX idx_messages_telegram_topic_id ON public.messages(telegram_topic_id);