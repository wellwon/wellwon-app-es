-- Добавляем foreign key связь для chat_participants
ALTER TABLE public.chat_participants 
ADD CONSTRAINT fk_chat_participants_user_id 
FOREIGN KEY (user_id) REFERENCES public.profiles(user_id);

-- Добавляем foreign key связь для chat_participants к chats
ALTER TABLE public.chat_participants 
ADD CONSTRAINT fk_chat_participants_chat_id 
FOREIGN KEY (chat_id) REFERENCES public.chats(id);

-- Добавляем foreign key связь для messages
ALTER TABLE public.messages 
ADD CONSTRAINT fk_messages_chat_id 
FOREIGN KEY (chat_id) REFERENCES public.chats(id);

ALTER TABLE public.messages 
ADD CONSTRAINT fk_messages_sender_id 
FOREIGN KEY (sender_id) REFERENCES public.profiles(user_id);

ALTER TABLE public.messages 
ADD CONSTRAINT fk_messages_reply_to_id 
FOREIGN KEY (reply_to_id) REFERENCES public.messages(id);

-- Добавляем foreign key связи для message_reads
ALTER TABLE public.message_reads 
ADD CONSTRAINT fk_message_reads_message_id 
FOREIGN KEY (message_id) REFERENCES public.messages(id);

ALTER TABLE public.message_reads 
ADD CONSTRAINT fk_message_reads_user_id 
FOREIGN KEY (user_id) REFERENCES public.profiles(user_id);

-- Добавляем foreign key связи для typing_indicators
ALTER TABLE public.typing_indicators 
ADD CONSTRAINT fk_typing_indicators_chat_id 
FOREIGN KEY (chat_id) REFERENCES public.chats(id);

ALTER TABLE public.typing_indicators 
ADD CONSTRAINT fk_typing_indicators_user_id 
FOREIGN KEY (user_id) REFERENCES public.profiles(user_id);

-- Создаем функцию для получения роли пользователя (избежание рекурсии в RLS)
CREATE OR REPLACE FUNCTION public.get_current_user_role()
RETURNS TEXT AS $$
  SELECT type::text FROM public.profiles WHERE user_id = auth.uid();
$$ LANGUAGE SQL SECURITY DEFINER STABLE;

-- Удаляем старые RLS политики для chat_participants
DROP POLICY IF EXISTS "Users can view participants of their chats" ON public.chat_participants;
DROP POLICY IF EXISTS "Users can add participants to their chats" ON public.chat_participants;

-- Создаем новые RLS политики для chat_participants (без рекурсии)
CREATE POLICY "Users can view participants of their chats" ON public.chat_participants
FOR SELECT USING (
  chat_id IN (
    SELECT cp2.chat_id 
    FROM chat_participants cp2 
    WHERE cp2.user_id = auth.uid() AND cp2.is_active = true
  ) 
  OR public.get_current_user_role() IN ('ww_manager', 'ww_developer')
);

CREATE POLICY "Users can add participants to their chats" ON public.chat_participants
FOR INSERT WITH CHECK (
  chat_id IN (
    SELECT chats.id 
    FROM chats 
    WHERE chats.created_by = auth.uid()
  ) 
  OR public.get_current_user_role() IN ('ww_manager', 'ww_developer')
);

-- Включаем Realtime для всех чатовых таблиц
ALTER TABLE public.chats REPLICA IDENTITY FULL;
ALTER TABLE public.chat_participants REPLICA IDENTITY FULL;
ALTER TABLE public.messages REPLICA IDENTITY FULL;
ALTER TABLE public.message_reads REPLICA IDENTITY FULL;
ALTER TABLE public.typing_indicators REPLICA IDENTITY FULL;

-- Добавляем таблицы в публикацию supabase_realtime
ALTER PUBLICATION supabase_realtime ADD TABLE public.chats;
ALTER PUBLICATION supabase_realtime ADD TABLE public.chat_participants;
ALTER PUBLICATION supabase_realtime ADD TABLE public.messages;
ALTER PUBLICATION supabase_realtime ADD TABLE public.message_reads;
ALTER PUBLICATION supabase_realtime ADD TABLE public.typing_indicators;