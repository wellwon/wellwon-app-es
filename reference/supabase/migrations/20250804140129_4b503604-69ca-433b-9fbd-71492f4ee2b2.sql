-- Create test users for layout testing
-- These users will be used for testing different user types and their interactions

-- Insert test users profiles (assuming they have been registered via auth)
-- Note: The actual auth.users entries need to be created via the signup form first

-- Create client test user profile
INSERT INTO public.profiles (user_id, first_name, last_name, active, type)
VALUES (
  'f47ac10b-58cc-4372-a567-0e02b2c3d479'::uuid,  -- This will need to be updated with actual UUID after signup
  'Oleg',
  'Client',
  true,
  'client'
) ON CONFLICT (user_id) DO UPDATE SET
  first_name = EXCLUDED.first_name,
  last_name = EXCLUDED.last_name,
  type = EXCLUDED.type;

-- Create performer test user profile  
INSERT INTO public.profiles (user_id, first_name, last_name, active, type)
VALUES (
  'f47ac10b-58cc-4372-a567-0e02b2c3d480'::uuid,  -- This will need to be updated with actual UUID after signup
  'Oleg',
  'Performer', 
  true,
  'performer'
) ON CONFLICT (user_id) DO UPDATE SET
  first_name = EXCLUDED.first_name,
  last_name = EXCLUDED.last_name,
  type = EXCLUDED.type;

-- Create admin test user profile
INSERT INTO public.profiles (user_id, first_name, last_name, active, type)
VALUES (
  'f47ac10b-58cc-4372-a567-0e02b2c3d481'::uuid,  -- This will need to be updated with actual UUID after signup
  'Oleg',
  'Admin',
  true,
  'ww_admin'
) ON CONFLICT (user_id) DO UPDATE SET
  first_name = EXCLUDED.first_name,
  last_name = EXCLUDED.last_name,
  type = EXCLUDED.type;

-- Create a function to help developers quickly switch user types for testing
CREATE OR REPLACE FUNCTION public.get_test_users()
RETURNS TABLE (
  user_id uuid,
  full_name text,
  user_type user_type,
  email text
)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $$
  SELECT 
    p.user_id,
    CONCAT(p.first_name, ' ', p.last_name) as full_name,
    p.type as user_type,
    au.email
  FROM public.profiles p
  LEFT JOIN auth.users au ON p.user_id = au.id
  WHERE p.first_name = 'Oleg' 
    AND p.last_name IN ('Client', 'Performer', 'Admin', 'Shkola')
  ORDER BY p.type;
$$;