-- Remove the problematic RLS policy that causes infinite recursion
DROP POLICY IF EXISTS "Users can view profiles of chat participants" ON public.profiles;

-- Remove the function that's no longer needed
DROP FUNCTION IF EXISTS public.user_participates_in_chat(uuid, uuid);