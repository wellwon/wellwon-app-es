-- Drop the problematic recursive policy
DROP POLICY IF EXISTS "Safe profiles access policy" ON public.profiles;

-- Create a security definer function to avoid recursion
CREATE OR REPLACE FUNCTION public.get_current_user_type()
RETURNS TEXT AS $$
  SELECT type::text FROM public.profiles WHERE user_id = auth.uid();
$$ LANGUAGE SQL SECURITY DEFINER STABLE;

-- Create a new non-recursive policy using the function
CREATE POLICY "Non-recursive profiles access policy" ON public.profiles
FOR SELECT USING (
  user_id = auth.uid() OR
  public.get_current_user_type() IN ('ww_developer', 'ww_manager') OR
  (active = true AND auth.uid() IS NOT NULL)
);