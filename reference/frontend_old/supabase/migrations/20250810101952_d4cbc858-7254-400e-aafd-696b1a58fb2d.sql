-- Add user_number column to profiles table
ALTER TABLE public.profiles ADD COLUMN user_number INTEGER;

-- Create a unique index to ensure no duplicate user numbers
CREATE UNIQUE INDEX idx_profiles_user_number ON public.profiles(user_number);

-- Assign numbers to existing users based on creation order
WITH numbered_users AS (
  SELECT user_id, ROW_NUMBER() OVER (ORDER BY created_at ASC) as row_num
  FROM public.profiles
  WHERE user_number IS NULL
)
UPDATE public.profiles 
SET user_number = numbered_users.row_num
FROM numbered_users
WHERE profiles.user_id = numbered_users.user_id;

-- Create function to get next available user number
CREATE OR REPLACE FUNCTION public.get_next_user_number()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  next_number INTEGER;
BEGIN
  -- Get the highest existing user number and add 1
  SELECT COALESCE(MAX(user_number), 0) + 1 INTO next_number
  FROM public.profiles;
  
  RETURN next_number;
END;
$$;

-- Update the handle_new_user function to assign user numbers
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  new_user_number INTEGER;
BEGIN
  -- Get the next user number
  SELECT public.get_next_user_number() INTO new_user_number;
  
  INSERT INTO public.profiles (user_id, first_name, last_name, active, type, user_number)
  VALUES (
    NEW.id,
    NULLIF(NEW.raw_user_meta_data->>'first_name', ''),
    NULLIF(NEW.raw_user_meta_data->>'last_name', ''),
    true, -- new users are active by default
    COALESCE(NULLIF(NEW.raw_user_meta_data->>'user_type', ''), 'client')::public.user_type,
    new_user_number
  );
  RETURN NEW;
END;
$$;