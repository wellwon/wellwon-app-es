-- Create helper functions for testing without using FOUND variable

-- Create a helper function to update user type for testing
CREATE OR REPLACE FUNCTION public.update_user_type_for_testing(
  target_email text,
  new_user_type user_type
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  user_updated boolean := false;
BEGIN
  UPDATE public.profiles 
  SET type = new_user_type
  WHERE user_id IN (
    SELECT id FROM auth.users WHERE email = target_email
  );
  
  GET DIAGNOSTICS user_updated = ROW_COUNT;
  RETURN user_updated > 0;
END;
$$;

-- Create a helper function to check developer permissions
CREATE OR REPLACE FUNCTION public.is_developer()
RETURNS boolean
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.profiles
    WHERE user_id = auth.uid()
      AND type = 'ww_developer'
  );
$$;