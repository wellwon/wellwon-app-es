-- Create enum for chat business roles
CREATE TYPE public.chat_business_role AS ENUM (
  'client',
  'payment_agent', 
  'logistician',
  'purchasers',
  'unassigned',
  'manager'
);

-- Add business_role column to profiles table
ALTER TABLE public.profiles 
ADD COLUMN business_role public.chat_business_role;

-- Add business_role column to tg_users table  
ALTER TABLE public.tg_users
ADD COLUMN business_role public.chat_business_role;

-- Create policy for developers to update any profile
CREATE POLICY "Developers can update any profile business role" 
ON public.profiles 
FOR UPDATE 
USING (is_user_developer());

-- Add comment for clarity
COMMENT ON COLUMN public.profiles.business_role IS 'Business role of the user in chat contexts';
COMMENT ON COLUMN public.tg_users.business_role IS 'Business role of the telegram user in chat contexts';