-- Drop existing RLS policies
DROP POLICY IF EXISTS "Active users can view their own profile" ON public.profiles;
DROP POLICY IF EXISTS "Active users can update their own profile" ON public.profiles;

-- Create new RLS policies that allow users to see their own profile regardless of active status
CREATE POLICY "Users can view their own profile" 
ON public.profiles 
FOR SELECT 
USING (auth.uid() = user_id);

-- Allow users to update their own profile only when active
CREATE POLICY "Active users can update their own profile" 
ON public.profiles 
FOR UPDATE 
USING (auth.uid() = user_id AND active = true);

-- Allow WW managers and developers to view all profiles for user management
CREATE POLICY "WW managers can view all profiles" 
ON public.profiles 
FOR SELECT 
USING (
  EXISTS (
    SELECT 1 FROM public.profiles 
    WHERE user_id = auth.uid() 
    AND type IN ('ww_manager', 'ww_developer')
    AND active = true
  )
);

-- Allow WW managers and developers to update any profile
CREATE POLICY "WW managers can update all profiles" 
ON public.profiles 
FOR UPDATE 
USING (
  EXISTS (
    SELECT 1 FROM public.profiles 
    WHERE user_id = auth.uid() 
    AND type IN ('ww_manager', 'ww_developer')
    AND active = true
  )
);

-- Update the handle_new_user function to set new users as active by default
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
BEGIN
  INSERT INTO public.profiles (user_id, display_name, first_name, last_name, active, type)
  VALUES (
    NEW.id,
    COALESCE(
      NULLIF(NEW.raw_user_meta_data->>'display_name', ''),
      CASE 
        WHEN NEW.raw_user_meta_data->>'first_name' IS NOT NULL OR NEW.raw_user_meta_data->>'last_name' IS NOT NULL THEN
          CONCAT(
            COALESCE(NEW.raw_user_meta_data->>'first_name', ''),
            CASE 
              WHEN NEW.raw_user_meta_data->>'first_name' IS NOT NULL AND NEW.raw_user_meta_data->>'last_name' IS NOT NULL THEN ' '
              ELSE ''
            END,
            COALESCE(NEW.raw_user_meta_data->>'last_name', '')
          )
        ELSE NULL
      END
    ),
    NULLIF(NEW.raw_user_meta_data->>'first_name', ''),
    NULLIF(NEW.raw_user_meta_data->>'last_name', ''),
    true, -- new users are now active by default
    'client' -- new users are clients by default
  );
  RETURN NEW;
END;
$function$