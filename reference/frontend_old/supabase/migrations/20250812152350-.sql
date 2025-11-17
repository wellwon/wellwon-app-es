-- Fix infinite recursion in profiles RLS policy
-- The current policy is referencing profiles table from within profiles table policy

-- Drop the problematic policy
DROP POLICY IF EXISTS "Profiles access policy" ON public.profiles;

-- Create a simpler, non-recursive policy
CREATE POLICY "Users can view accessible profiles" 
ON public.profiles 
FOR SELECT 
USING (
  -- Users can see their own profile
  (user_id = auth.uid()) 
  OR 
  -- OR they can see active profiles of other users (but only if they are authenticated)
  ((active = true) AND (auth.uid() IS NOT NULL))
);

-- Ensure developers can still see all profiles (separate policy)
CREATE POLICY "Developers can view all profiles" 
ON public.profiles 
FOR SELECT 
USING (
  EXISTS (
    SELECT 1 FROM public.profiles dev_profile 
    WHERE dev_profile.user_id = auth.uid() 
    AND dev_profile.developer = true
  )
);