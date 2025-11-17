-- Update passwords for all test users to '218skladOlegNSP!'
-- Note: This is a one-time operation to fix test accounts

-- First, let's update the admin user type from ww_manager to ww_admin
UPDATE public.profiles 
SET type = 'ww_admin'::user_type 
WHERE user_id IN (
  SELECT id FROM auth.users WHERE email = 'oleg.admin@test.com'
) AND type = 'ww_manager'::user_type;

-- Update passwords for test users
-- Note: In Supabase, we need to update the auth.users table directly
-- This requires admin privileges but is necessary for test account setup

-- For client test user
UPDATE auth.users 
SET encrypted_password = crypt('218skladOlegNSP!', gen_salt('bf'))
WHERE email = 'oleg.client@test.com';

-- For performer test user  
UPDATE auth.users 
SET encrypted_password = crypt('218skladOlegNSP!', gen_salt('bf'))
WHERE email = 'oleg.performer@test.com';

-- For admin test user
UPDATE auth.users 
SET encrypted_password = crypt('218skladOlegNSP!', gen_salt('bf'))
WHERE email = 'oleg.admin@test.com';