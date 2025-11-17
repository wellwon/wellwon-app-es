-- Fix the RLS policy for chat creation to be more permissive
DROP POLICY IF EXISTS "Users can create chats" ON public.chats;

-- Create a simpler, more permissive policy for chat creation
CREATE POLICY "Users can create chats" 
ON public.chats 
FOR INSERT 
TO authenticated
WITH CHECK (auth.uid() = created_by);

-- Also make sure we can view chats properly
DROP POLICY IF EXISTS "Users can view chats they participate in" ON public.chats;
CREATE POLICY "Users can view chats they participate in" 
ON public.chats 
FOR SELECT 
TO authenticated
USING (
  auth.uid() = created_by OR
  id IN (
    SELECT chat_id FROM chat_participants 
    WHERE user_id = auth.uid() AND is_active = true
  ) OR 
  EXISTS (
    SELECT 1 FROM profiles 
    WHERE user_id = auth.uid() 
    AND type = ANY(ARRAY['ww_manager'::user_type, 'ww_developer'::user_type])
  )
);