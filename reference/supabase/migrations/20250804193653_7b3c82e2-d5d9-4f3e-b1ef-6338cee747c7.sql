-- First, remove the problematic profiles policy that causes infinite recursion
DROP POLICY IF EXISTS "Users can view profiles of chat participants" ON public.profiles;

-- Remove all policies that depend on user_participates_in_chat function
DROP POLICY IF EXISTS "Users can view participants of their chats" ON public.chat_participants;
DROP POLICY IF EXISTS "Users can view messages in their chats" ON public.messages;
DROP POLICY IF EXISTS "Users can send messages to their chats" ON public.messages;
DROP POLICY IF EXISTS "Users can mark messages as read in their chats" ON public.message_reads;
DROP POLICY IF EXISTS "Users can view read receipts for messages in their chats" ON public.message_reads;

-- Now remove the function
DROP FUNCTION IF EXISTS public.user_participates_in_chat(uuid, uuid);

-- Recreate the essential policies without the problematic function
-- These use direct table access instead of the problematic function

-- Chat participants policies
CREATE POLICY "Users can view participants of their chats" ON public.chat_participants
FOR SELECT USING (user_id = auth.uid() OR 
  chat_id IN (SELECT chat_id FROM public.chat_participants WHERE user_id = auth.uid() AND is_active = true));

-- Messages policies  
CREATE POLICY "Users can view messages in their chats" ON public.messages
FOR SELECT USING (
  chat_id IN (SELECT chat_id FROM public.chat_participants WHERE user_id = auth.uid() AND is_active = true)
);

CREATE POLICY "Users can send messages to their chats" ON public.messages
FOR INSERT WITH CHECK (
  sender_id = auth.uid() AND 
  chat_id IN (SELECT chat_id FROM public.chat_participants WHERE user_id = auth.uid() AND is_active = true)
);

-- Message reads policies
CREATE POLICY "Users can mark messages as read in their chats" ON public.message_reads
FOR INSERT WITH CHECK (
  user_id = auth.uid() AND 
  message_id IN (
    SELECT m.id FROM public.messages m 
    JOIN public.chat_participants cp ON m.chat_id = cp.chat_id 
    WHERE cp.user_id = auth.uid() AND cp.is_active = true
  )
);

CREATE POLICY "Users can view read receipts for messages in their chats" ON public.message_reads
FOR SELECT USING (
  message_id IN (
    SELECT m.id FROM public.messages m 
    JOIN public.chat_participants cp ON m.chat_id = cp.chat_id 
    WHERE cp.user_id = auth.uid() AND cp.is_active = true
  )
);