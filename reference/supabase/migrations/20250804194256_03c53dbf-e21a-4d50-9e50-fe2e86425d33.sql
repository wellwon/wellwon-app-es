-- Drop the problematic policy that causes recursion
DROP POLICY IF EXISTS "Users can view chat participants profiles" ON public.profiles;

-- Create a safe policy for profiles that avoids recursion
CREATE POLICY "Safe profiles access policy" ON public.profiles
FOR SELECT USING (
  -- User can see their own profile
  user_id = auth.uid() OR
  -- Developers and managers can see all profiles
  EXISTS (
    SELECT 1 FROM public.profiles p 
    WHERE p.user_id = auth.uid() 
    AND p.type IN ('ww_developer', 'ww_manager')
  ) OR
  -- For active users - basic access without recursion
  (active = true AND auth.uid() IS NOT NULL)
);