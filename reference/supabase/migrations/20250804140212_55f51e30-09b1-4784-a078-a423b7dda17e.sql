-- Remove the failed test user profiles and create a helper function instead
-- This approach will allow creating test users through the normal signup process

-- Remove the test profiles that failed to insert
DELETE FROM public.profiles 
WHERE user_id IN (
  'f47ac10b-58cc-4372-a567-0e02b2c3d479'::uuid,
  'f47ac10b-58cc-4372-a567-0e02b2c3d480'::uuid,
  'f47ac10b-58cc-4372-a567-0e02b2c3d481'::uuid
);

-- Create a helper function to update user type for testing
CREATE OR REPLACE FUNCTION public.update_user_type_for_testing(
  target_email text,
  new_user_type user_type
)
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
  UPDATE public.profiles 
  SET type = new_user_type
  WHERE user_id IN (
    SELECT id FROM auth.users WHERE email = target_email
  );
  
  SELECT FOUND;
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