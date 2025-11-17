-- Fix chat creation issues by updating RLS policies and ensuring proper setup

-- 1. Create missing profiles for existing users (if any)
INSERT INTO public.profiles (user_id, first_name, last_name, active, type)
SELECT 
  au.id,
  COALESCE(au.raw_user_meta_data->>'first_name', 'User') as first_name,
  COALESCE(au.raw_user_meta_data->>'last_name', '') as last_name,
  true as active,
  COALESCE(au.raw_user_meta_data->>'user_type', 'client')::public.user_type as type
FROM auth.users au
LEFT JOIN public.profiles p ON au.id = p.user_id
WHERE p.user_id IS NULL;

-- 2. Update RLS policy for chat creation to be more permissive
DROP POLICY IF EXISTS "Users can create chats" ON public.chats;
CREATE POLICY "Users can create chats" 
ON public.chats 
FOR INSERT 
TO authenticated
WITH CHECK (
  auth.uid() = created_by AND 
  EXISTS (
    SELECT 1 FROM public.profiles 
    WHERE user_id = auth.uid() AND active = true
  )
);

-- 3. Ensure the trigger for adding chat participants exists and works
DROP TRIGGER IF EXISTS on_chat_created ON public.chats;
CREATE TRIGGER on_chat_created
  AFTER INSERT ON public.chats
  FOR EACH ROW EXECUTE FUNCTION public.add_chat_creator_as_participant();

-- 4. Update RLS policy for chat participants to allow insertion
DROP POLICY IF EXISTS "Users can add participants to their chats" ON public.chat_participants;
CREATE POLICY "Users can add participants to their chats" 
ON public.chat_participants 
FOR INSERT 
TO authenticated
WITH CHECK (
  (chat_id IN (
    SELECT id FROM public.chats 
    WHERE created_by = auth.uid()
  )) OR 
  (EXISTS (
    SELECT 1 FROM public.profiles 
    WHERE user_id = auth.uid() 
    AND type = ANY(ARRAY['ww_manager'::user_type, 'ww_developer'::user_type])
  )) OR
  (user_id = auth.uid()) -- Allow users to add themselves to chats
);

-- 5. Enable realtime for chat tables (skip publication as it already exists)
ALTER TABLE public.chats REPLICA IDENTITY FULL;
ALTER TABLE public.messages REPLICA IDENTITY FULL;
ALTER TABLE public.chat_participants REPLICA IDENTITY FULL;
ALTER TABLE public.typing_indicators REPLICA IDENTITY FULL;