-- Create safe policy for profiles that allows viewing chat participants without recursion
CREATE POLICY "Users can view chat participants profiles" ON public.profiles
FOR SELECT USING (
  -- User can see their own profile
  user_id = auth.uid() OR
  -- Or profiles of participants in chats where they also participate
  user_id IN (
    SELECT cp1.user_id 
    FROM public.chat_participants cp1
    WHERE cp1.chat_id IN (
      SELECT cp2.chat_id 
      FROM public.chat_participants cp2 
      WHERE cp2.user_id = auth.uid() AND cp2.is_active = true
    ) AND cp1.is_active = true
  )
);