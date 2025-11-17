-- Fix infinite recursion in profiles RLS policies
-- Current policies are causing recursion when checking developer status

-- Drop ALL existing policies for profiles table
DROP POLICY IF EXISTS "Users can view accessible profiles" ON public.profiles;
DROP POLICY IF EXISTS "Developers can view all profiles" ON public.profiles;
DROP POLICY IF EXISTS "Active users can update their own profile" ON public.profiles;
DROP POLICY IF EXISTS "Users can insert their own profile" ON public.profiles;
DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;

-- Create a safe security definer function to check if current user is developer
CREATE OR REPLACE FUNCTION public.is_current_user_developer()
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
  SELECT COALESCE(developer, false)
  FROM profiles
  WHERE user_id = auth.uid();
$$;

-- Create new non-recursive policies
CREATE POLICY "Users can view their own profile"
ON public.profiles
FOR SELECT
USING (user_id = auth.uid());

CREATE POLICY "Users can view active profiles when authenticated"
ON public.profiles
FOR SELECT
USING (
  active = true 
  AND auth.uid() IS NOT NULL 
  AND user_id != auth.uid()
);

CREATE POLICY "Developers can view all profiles"
ON public.profiles
FOR SELECT
USING (public.is_current_user_developer() = true);

CREATE POLICY "Users can insert their own profile"
ON public.profiles
FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own profile"
ON public.profiles
FOR UPDATE
USING (auth.uid() = user_id AND active = true);