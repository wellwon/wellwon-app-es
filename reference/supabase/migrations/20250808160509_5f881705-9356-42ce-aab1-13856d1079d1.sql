-- Fix search path for security functions
DROP FUNCTION IF EXISTS public.get_user_company(UUID);
DROP FUNCTION IF EXISTS public.get_client_company_from_chat(UUID);

-- Function to get user's company with proper search path
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
SET search_path TO 'public'
AS $$
  SELECT c.id, c.name, c.company_type, c.balance, c.created_at, c.updated_at
  FROM public.companies c
  JOIN public.profiles p ON p.company_id = c.id
  WHERE p.user_id = user_uuid;
$$;

-- Function to get client company from active chat with proper search path
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
SET search_path TO 'public'
AS $$
  SELECT c.id, c.name, c.company_type, c.balance, c.created_at, c.updated_at, p.user_id
  FROM public.companies c
  JOIN public.profiles p ON p.company_id = c.id
  JOIN public.chat_participants cp ON cp.user_id = p.user_id
  WHERE cp.chat_id = chat_uuid 
  AND p.type = 'client'
  AND cp.is_active = true
  LIMIT 1;
$$;