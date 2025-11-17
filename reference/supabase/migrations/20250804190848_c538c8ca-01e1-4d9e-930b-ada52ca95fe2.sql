-- Fix message_reads RLS policies to allow proper access
DROP POLICY IF EXISTS "Users can mark their own messages as read" ON public.message_reads;
DROP POLICY IF EXISTS "Users can view their own read receipts" ON public.message_reads;

-- Create better RLS policies for message_reads table
CREATE POLICY "Users can mark messages as read in their chats" 
ON public.message_reads 
FOR INSERT 
WITH CHECK (
  auth.uid() = user_id AND 
  user_participates_in_chat(
    (SELECT chat_id FROM public.messages WHERE id = message_id), 
    auth.uid()
  )
);

CREATE POLICY "Admins can mark any message as read" 
ON public.message_reads 
FOR INSERT 
WITH CHECK (
  EXISTS (
    SELECT 1 FROM public.profiles 
    WHERE user_id = auth.uid() 
    AND type IN ('ww_manager', 'ww_developer')
  )
);

CREATE POLICY "Users can view read receipts for messages in their chats" 
ON public.message_reads 
FOR SELECT 
USING (
  user_participates_in_chat(
    (SELECT chat_id FROM public.messages WHERE id = message_id), 
    auth.uid()
  ) OR
  EXISTS (
    SELECT 1 FROM public.profiles 
    WHERE user_id = auth.uid() 
    AND type IN ('ww_manager', 'ww_developer')
  )
);