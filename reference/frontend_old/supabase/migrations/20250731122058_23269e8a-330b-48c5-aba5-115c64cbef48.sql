-- Create enum for user types
CREATE TYPE public.user_type AS ENUM ('client', 'performer', 'ww_manager', 'ww_developer');

-- Add active and type columns to profiles table
ALTER TABLE public.profiles 
ADD COLUMN active BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN type public.user_type NOT NULL DEFAULT 'client';

-- Update existing users to be active (so current users can continue working)
UPDATE public.profiles SET active = true WHERE active = false;

-- Update RLS policies to check active status
DROP POLICY IF EXISTS "Users can view their own profile" ON public.profiles;
DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;
DROP POLICY IF EXISTS "Users can insert their own profile" ON public.profiles;

-- Create new RLS policies that check active status
CREATE POLICY "Active users can view their own profile" 
ON public.profiles 
FOR SELECT 
USING (auth.uid() = user_id AND active = true);

CREATE POLICY "Active users can update their own profile" 
ON public.profiles 
FOR UPDATE 
USING (auth.uid() = user_id AND active = true);

CREATE POLICY "Users can insert their own profile" 
ON public.profiles 
FOR INSERT 
WITH CHECK (auth.uid() = user_id);

-- Update handle_new_user function to set default values
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
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
    false, -- new users are inactive by default
    'client' -- new users are clients by default
  );
  RETURN NEW;
END;
$$;