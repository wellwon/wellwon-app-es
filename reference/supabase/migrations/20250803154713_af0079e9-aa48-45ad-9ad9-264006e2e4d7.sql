-- Create a developer user profile for testing admin functionality
-- First, let's check if we have any existing profiles we can update
UPDATE profiles 
SET type = 'ww_developer' 
WHERE user_id = '4161d61c-2d75-425e-b40f-7aa32388c1cd' -- Current user
AND type = 'performer';

-- If no rows were affected, we'll still have the current user available
-- The admin panel should now be visible