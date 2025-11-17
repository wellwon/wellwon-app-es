-- Fix the company assignment issues and RLS policies

-- 1. Fix existing incorrect company assignments
-- Find companies created by admins that should belong to clients
UPDATE public.user_companies uc
SET user_id = (
  SELECT cp.user_id 
  FROM public.chat_participants cp
  JOIN public.profiles p ON p.user_id = cp.user_id
  JOIN public.chats ch ON ch.id = cp.chat_id
  WHERE ch.company_id = uc.company_id 
    AND p.type = 'client'
    AND cp.is_active = true
  LIMIT 1
)
WHERE uc.relationship_type = 'owner'
  AND uc.user_id IN (
    SELECT user_id FROM public.profiles WHERE type IN ('ww_manager', 'ww_developer')
  )
  AND EXISTS (
    SELECT 1 FROM public.chats ch 
    JOIN public.chat_participants cp ON cp.chat_id = ch.id
    JOIN public.profiles p ON p.user_id = cp.user_id
    WHERE ch.company_id = uc.company_id 
      AND p.type = 'client'
      AND cp.is_active = true
  );

-- 2. Fix message_reads RLS policies to allow proper message reading
-- Drop existing conflicting policies
DROP POLICY IF EXISTS "Users can mark any message as read in their chats" ON public.message_reads;
DROP POLICY IF EXISTS "Users can view read status of messages in their chats" ON public.message_reads;
DROP POLICY IF EXISTS "Users can view read receipts for messages in their chats" ON public.message_reads;

-- Create new working policies
CREATE POLICY "Users can mark messages as read" 
ON public.message_reads 
FOR INSERT 
WITH CHECK (
  user_id = auth.uid() AND
  EXISTS (
    SELECT 1 FROM public.chat_participants cp
    JOIN public.messages m ON m.chat_id = cp.chat_id
    WHERE m.id = message_reads.message_id 
      AND cp.user_id = auth.uid()
      AND cp.is_active = true
  )
);

CREATE POLICY "Users can view their own read status" 
ON public.message_reads 
FOR SELECT 
USING (
  user_id = auth.uid() OR
  EXISTS (
    SELECT 1 FROM public.chat_participants cp
    JOIN public.messages m ON m.chat_id = cp.chat_id
    WHERE m.id = message_reads.message_id 
      AND cp.user_id = auth.uid()
      AND cp.is_active = true
  )
);

CREATE POLICY "Users can update their read status" 
ON public.message_reads 
FOR UPDATE 
USING (user_id = auth.uid());

-- 3. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_user_companies_user_id_active ON public.user_companies(user_id, is_active, relationship_type);
CREATE INDEX IF NOT EXISTS idx_message_reads_user_message ON public.message_reads(user_id, message_id);
CREATE INDEX IF NOT EXISTS idx_chat_participants_user_chat ON public.chat_participants(user_id, chat_id, is_active);