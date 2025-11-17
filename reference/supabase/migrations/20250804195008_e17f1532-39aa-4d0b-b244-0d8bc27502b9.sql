-- Fix infinite recursion in chat RLS policies

-- Drop the problematic recursive policies
DROP POLICY IF EXISTS "Users can view participants of their chats" ON public.chat_participants;
DROP POLICY IF EXISTS "Users can view chats they participate in" ON public.chats;

-- Create simple, non-recursive policies for chat_participants
CREATE POLICY "Simple chat participants view" ON public.chat_participants
FOR SELECT USING (
  user_id = auth.uid() OR 
  public.get_current_user_type() IN ('ww_developer', 'ww_manager')
);

-- Create simple, non-recursive policy for chats
CREATE POLICY "Simple chats view" ON public.chats
FOR SELECT USING (
  created_by = auth.uid() OR 
  public.get_current_user_type() IN ('ww_developer', 'ww_manager')
);