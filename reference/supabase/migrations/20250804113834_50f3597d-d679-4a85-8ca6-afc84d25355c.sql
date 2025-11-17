-- Update user type to ww_developer for the current user
UPDATE profiles 
SET type = 'ww_developer'::user_type, 
    updated_at = now()
WHERE user_id = auth.uid();