-- Drop the old restrictive policy that conflicts with the new one
DROP POLICY IF EXISTS "Users can view their own profile" ON public.profiles;

-- The "Safe profiles access policy" already exists and should now work without conflicts