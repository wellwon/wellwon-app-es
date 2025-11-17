-- ЭТАП 1: НАСТРОЙКА БАЗЫ ДАННЫХ ДЛЯ REALTIME ЧАТОВ

-- 1.1 Создание основных таблиц чатов
CREATE TABLE public.chats (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text,
  type text CHECK (type IN ('direct', 'group', 'company')) DEFAULT 'direct',
  company_id uuid, -- Для фильтрации чатов внутри компании
  created_by uuid REFERENCES auth.users(id) NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  is_active boolean DEFAULT true,
  metadata jsonb DEFAULT '{}'::jsonb -- Дополнительные настройки чата
);

-- Участники чатов
CREATE TABLE public.chat_participants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id uuid REFERENCES public.chats(id) ON DELETE CASCADE,
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  role text CHECK (role IN ('member', 'admin', 'observer')) DEFAULT 'member',
  joined_at timestamp with time zone DEFAULT now(),
  last_read_at timestamp with time zone DEFAULT now(),
  is_active boolean DEFAULT true,
  UNIQUE(chat_id, user_id)
);

-- Сообщения
CREATE TABLE public.messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id uuid REFERENCES public.chats(id) ON DELETE CASCADE,
  sender_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  content text,
  message_type text CHECK (message_type IN ('text', 'file', 'voice', 'image', 'system')) DEFAULT 'text',
  reply_to_id uuid REFERENCES public.messages(id),
  file_url text,
  file_name text,
  file_size bigint,
  file_type text,
  voice_duration integer, -- в секундах для голосовых
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  is_edited boolean DEFAULT false,
  is_deleted boolean DEFAULT false,
  metadata jsonb DEFAULT '{}'::jsonb -- Для дополнительных данных
);

-- Статусы прочтения сообщений
CREATE TABLE public.message_reads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id uuid REFERENCES public.messages(id) ON DELETE CASCADE,
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  read_at timestamp with time zone DEFAULT now(),
  UNIQUE(message_id, user_id)
);

-- Typing индикаторы (реалтайм статус печати)
CREATE TABLE public.typing_indicators (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id uuid REFERENCES public.chats(id) ON DELETE CASCADE,
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  started_at timestamp with time zone DEFAULT now(),
  expires_at timestamp with time zone DEFAULT (now() + interval '10 seconds'),
  UNIQUE(chat_id, user_id)
);

-- 1.2 Создание индексов для производительности
CREATE INDEX idx_chats_company_id ON public.chats(company_id);
CREATE INDEX idx_chats_created_by ON public.chats(created_by);
CREATE INDEX idx_chat_participants_chat_id ON public.chat_participants(chat_id);
CREATE INDEX idx_chat_participants_user_id ON public.chat_participants(user_id);
CREATE INDEX idx_messages_chat_id_created_at ON public.messages(chat_id, created_at DESC);
CREATE INDEX idx_messages_sender_id ON public.messages(sender_id);
CREATE INDEX idx_messages_reply_to_id ON public.messages(reply_to_id);
CREATE INDEX idx_message_reads_message_id ON public.message_reads(message_id);
CREATE INDEX idx_message_reads_user_id ON public.message_reads(user_id);
CREATE INDEX idx_typing_indicators_chat_id ON public.typing_indicators(chat_id);
CREATE INDEX idx_typing_indicators_expires_at ON public.typing_indicators(expires_at);

-- 1.3 Включение RLS на всех таблицах
ALTER TABLE public.chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.message_reads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.typing_indicators ENABLE ROW LEVEL SECURITY;

-- 1.4 Создание RLS политик безопасности

-- Политики для chats
CREATE POLICY "Users can view chats they participate in"
  ON public.chats FOR SELECT
  USING (
    id IN (
      SELECT chat_id FROM public.chat_participants 
      WHERE user_id = auth.uid() AND is_active = true
    )
    OR 
    -- Админы видят все чаты
    EXISTS (
      SELECT 1 FROM public.profiles 
      WHERE user_id = auth.uid() 
      AND type IN ('ww_admin', 'ww_manager', 'ww_developer')
    )
  );

CREATE POLICY "Users can create chats"
  ON public.chats FOR INSERT
  WITH CHECK (auth.uid() = created_by);

CREATE POLICY "Chat creators and admins can update chats"
  ON public.chats FOR UPDATE
  USING (
    created_by = auth.uid()
    OR
    EXISTS (
      SELECT 1 FROM public.profiles 
      WHERE user_id = auth.uid() 
      AND type IN ('ww_admin', 'ww_manager', 'ww_developer')
    )
  );

-- Политики для chat_participants
CREATE POLICY "Users can view participants of their chats"
  ON public.chat_participants FOR SELECT
  USING (
    chat_id IN (
      SELECT chat_id FROM public.chat_participants cp2
      WHERE cp2.user_id = auth.uid() AND cp2.is_active = true
    )
    OR
    EXISTS (
      SELECT 1 FROM public.profiles 
      WHERE user_id = auth.uid() 
      AND type IN ('ww_admin', 'ww_manager', 'ww_developer')
    )
  );

CREATE POLICY "Users can add participants to their chats"
  ON public.chat_participants FOR INSERT
  WITH CHECK (
    chat_id IN (
      SELECT id FROM public.chats 
      WHERE created_by = auth.uid()
    )
    OR
    EXISTS (
      SELECT 1 FROM public.profiles 
      WHERE user_id = auth.uid() 
      AND type IN ('ww_admin', 'ww_manager', 'ww_developer')
    )
  );

-- Политики для messages
CREATE POLICY "Users can view messages in their chats"
  ON public.messages FOR SELECT
  USING (
    chat_id IN (
      SELECT chat_id FROM public.chat_participants 
      WHERE user_id = auth.uid() AND is_active = true
    )
    OR
    EXISTS (
      SELECT 1 FROM public.profiles 
      WHERE user_id = auth.uid() 
      AND type IN ('ww_admin', 'ww_manager', 'ww_developer')
    )
  );

CREATE POLICY "Users can send messages to their chats"
  ON public.messages FOR INSERT
  WITH CHECK (
    auth.uid() = sender_id
    AND chat_id IN (
      SELECT chat_id FROM public.chat_participants 
      WHERE user_id = auth.uid() AND is_active = true
    )
  );

-- Политики для message_reads
CREATE POLICY "Users can view read status of messages in their chats"
  ON public.message_reads FOR SELECT
  USING (
    message_id IN (
      SELECT m.id FROM public.messages m
      JOIN public.chat_participants cp ON m.chat_id = cp.chat_id
      WHERE cp.user_id = auth.uid() AND cp.is_active = true
    )
  );

CREATE POLICY "Users can mark messages as read"
  ON public.message_reads FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Политики для typing_indicators
CREATE POLICY "Users can view typing indicators in their chats"
  ON public.typing_indicators FOR SELECT
  USING (
    chat_id IN (
      SELECT chat_id FROM public.chat_participants 
      WHERE user_id = auth.uid() AND is_active = true
    )
  );

CREATE POLICY "Users can set typing indicators in their chats"
  ON public.typing_indicators FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND chat_id IN (
      SELECT chat_id FROM public.chat_participants 
      WHERE user_id = auth.uid() AND is_active = true
    )
  );

CREATE POLICY "Users can update their typing indicators"
  ON public.typing_indicators FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their typing indicators"
  ON public.typing_indicators FOR DELETE
  USING (auth.uid() = user_id);

-- 1.5 Создание триггеров и функций

-- Функция обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггеры для автообновления updated_at
CREATE TRIGGER update_chats_updated_at 
  BEFORE UPDATE ON public.chats 
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_messages_updated_at 
  BEFORE UPDATE ON public.messages 
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Функция автоматического добавления создателя чата как участника
CREATE OR REPLACE FUNCTION add_chat_creator_as_participant()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.chat_participants (chat_id, user_id, role)
  VALUES (NEW.id, NEW.created_by, 'admin');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER add_creator_as_participant
  AFTER INSERT ON public.chats
  FOR EACH ROW EXECUTE FUNCTION add_chat_creator_as_participant();

-- Функция очистки старых typing индикаторов
CREATE OR REPLACE FUNCTION cleanup_expired_typing_indicators()
RETURNS void AS $$
BEGIN
  DELETE FROM public.typing_indicators 
  WHERE expires_at < now();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 1.6 Настройка Storage для файлов чата
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'chat-files', 
  'chat-files', 
  false,
  52428800, -- 50MB limit
  ARRAY['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'audio/webm', 'audio/mp3', 'audio/wav', 'application/pdf', 'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
);

-- RLS политики для chat-files bucket
CREATE POLICY "Users can upload files to chats they participate in"
  ON storage.objects FOR INSERT
  WITH CHECK (
    bucket_id = 'chat-files'
    AND auth.uid()::text = (storage.foldername(name))[1]
  );

CREATE POLICY "Users can view files in their chats"
  ON storage.objects FOR SELECT
  USING (
    bucket_id = 'chat-files'
    AND (
      -- Пользователь загрузил файл
      auth.uid()::text = (storage.foldername(name))[1]
      OR
      -- Пользователь участвует в чате где был загружен файл
      EXISTS (
        SELECT 1 FROM public.chat_participants cp
        JOIN public.messages m ON m.chat_id = cp.chat_id
        WHERE cp.user_id = auth.uid()
        AND cp.is_active = true
        AND m.file_url IS NOT NULL
        AND m.file_url LIKE '%' || name || '%'
      )
      OR
      -- Админы видят все файлы
      EXISTS (
        SELECT 1 FROM public.profiles 
        WHERE user_id = auth.uid() 
        AND type IN ('ww_admin', 'ww_manager', 'ww_developer')
      )
    )
  );

-- 1.7 Настройка Realtime подписок
ALTER PUBLICATION supabase_realtime ADD TABLE public.chats;
ALTER PUBLICATION supabase_realtime ADD TABLE public.chat_participants;  
ALTER PUBLICATION supabase_realtime ADD TABLE public.messages;
ALTER PUBLICATION supabase_realtime ADD TABLE public.message_reads;
ALTER PUBLICATION supabase_realtime ADD TABLE public.typing_indicators;

-- Настройка REPLICA IDENTITY для realtime
ALTER TABLE public.chats REPLICA IDENTITY FULL;
ALTER TABLE public.chat_participants REPLICA IDENTITY FULL;
ALTER TABLE public.messages REPLICA IDENTITY FULL;
ALTER TABLE public.message_reads REPLICA IDENTITY FULL;
ALTER TABLE public.typing_indicators REPLICA IDENTITY FULL;