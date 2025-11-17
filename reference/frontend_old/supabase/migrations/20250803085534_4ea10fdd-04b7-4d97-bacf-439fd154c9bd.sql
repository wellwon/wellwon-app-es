-- Создаем security definer функцию для проверки участия в чате (избегаем рекурсивной RLS)
CREATE OR REPLACE FUNCTION public.user_participates_in_chat(chat_id_param uuid, user_id_param uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 
    FROM chat_participants 
    WHERE chat_id = chat_id_param 
    AND user_id = user_id_param 
    AND is_active = true
  );
$$;

-- Удаляем старые политики и создаем новые с использованием security definer функции
DROP POLICY IF EXISTS "Users can view participants of their chats" ON public.chat_participants;
DROP POLICY IF EXISTS "Users can add participants to their chats" ON public.chat_participants;

-- Новые политики без рекурсии
CREATE POLICY "Users can view participants of their chats" 
ON public.chat_participants 
FOR SELECT 
USING (
  public.user_participates_in_chat(chat_id, auth.uid()) OR 
  EXISTS (
    SELECT 1 FROM profiles 
    WHERE user_id = auth.uid() 
    AND type IN ('ww_manager', 'ww_developer')
  )
);

CREATE POLICY "Users can add participants to their chats" 
ON public.chat_participants 
FOR INSERT 
WITH CHECK (
  chat_id IN (
    SELECT id FROM chats WHERE created_by = auth.uid()
  ) OR 
  EXISTS (
    SELECT 1 FROM profiles 
    WHERE user_id = auth.uid() 
    AND type IN ('ww_manager', 'ww_developer')
  )
);

-- Исправляем политику для messages чтобы использовать новую функцию
DROP POLICY IF EXISTS "Users can view messages in their chats" ON public.messages;
CREATE POLICY "Users can view messages in their chats" 
ON public.messages 
FOR SELECT 
USING (
  public.user_participates_in_chat(chat_id, auth.uid()) OR 
  EXISTS (
    SELECT 1 FROM profiles 
    WHERE user_id = auth.uid() 
    AND type IN ('ww_manager', 'ww_developer')
  )
);

DROP POLICY IF EXISTS "Users can send messages to their chats" ON public.messages;
CREATE POLICY "Users can send messages to their chats" 
ON public.messages 
FOR INSERT 
WITH CHECK (
  auth.uid() = sender_id AND 
  public.user_participates_in_chat(chat_id, auth.uid())
);