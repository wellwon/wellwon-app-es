-- Add company relationship fields to profiles table
ALTER TABLE public.profiles 
ADD COLUMN company_id BIGINT REFERENCES public.companies(id),
ADD COLUMN role_in_company TEXT DEFAULT 'owner';

-- Create index for optimization
CREATE INDEX idx_profiles_company_id ON public.profiles(company_id);

-- Add created_by_user_id to companies table for tracking who created the company
ALTER TABLE public.companies 
ADD COLUMN created_by_user_id UUID REFERENCES auth.users(id);

-- Function to get user's company
CREATE OR REPLACE FUNCTION public.get_user_company(user_uuid UUID)
RETURNS TABLE(
  id BIGINT,
  name TEXT,
  company_type TEXT,
  balance NUMERIC,
  created_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path = 'public'
AS $$
  SELECT c.id, c.name, c.company_type, c.balance, c.created_at, c.updated_at
  FROM companies c
  JOIN profiles p ON p.company_id = c.id
  WHERE p.user_id = user_uuid;
$$;

-- Function to get client company from active chat
CREATE OR REPLACE FUNCTION public.get_client_company_from_chat(chat_uuid UUID)
RETURNS TABLE(
  id BIGINT,
  name TEXT,
  company_type TEXT,
  balance NUMERIC,
  created_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE,
  client_user_id UUID
)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path = 'public'
AS $$
  SELECT c.id, c.name, c.company_type, c.balance, c.created_at, c.updated_at, p.user_id
  FROM companies c
  JOIN profiles p ON p.company_id = c.id
  JOIN chat_participants cp ON cp.user_id = p.user_id
  WHERE cp.chat_id = chat_uuid 
  AND p.type = 'client'
  AND cp.is_active = true
  LIMIT 1;
$$;