-- Remove client and performer from user_type enum and convert existing users
-- First, update all client and performer users to ww_manager
UPDATE public.profiles 
SET type = 'ww_manager' 
WHERE type IN ('client', 'performer');

-- Drop the default value temporarily
ALTER TABLE public.profiles ALTER COLUMN type DROP DEFAULT;

-- Create new enum without client and performer
CREATE TYPE public.user_type_new AS ENUM ('ww_admin', 'ww_manager', 'ww_developer');

-- Update the profiles table to use the new enum
ALTER TABLE public.profiles 
ALTER COLUMN type TYPE public.user_type_new 
USING type::text::public.user_type_new;

-- Drop the old enum and rename the new one
DROP TYPE public.user_type;
ALTER TYPE public.user_type_new RENAME TO user_type;

-- Restore the default value with the new enum
ALTER TABLE public.profiles ALTER COLUMN type SET DEFAULT 'ww_manager'::user_type;

-- Create new function to replace get_client_company_from_chat
CREATE OR REPLACE FUNCTION public.get_company_from_chat(chat_uuid uuid)
RETURNS TABLE(
  id bigint, 
  name text, 
  company_type text, 
  balance numeric, 
  status company_status, 
  orders_count integer, 
  turnover numeric, 
  rating numeric, 
  successful_deliveries integer, 
  created_at timestamp with time zone, 
  updated_at timestamp with time zone, 
  owner_user_id uuid
)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  SELECT 
    c.id, 
    c.name, 
    c.company_type, 
    c.balance, 
    c.status,
    c.orders_count,
    c.turnover,
    c.rating,
    c.successful_deliveries,
    c.created_at, 
    c.updated_at,
    uc.user_id as owner_user_id
  FROM public.companies c
  JOIN public.chats ch ON ch.company_id = c.id
  LEFT JOIN public.user_companies uc ON uc.company_id = c.id AND uc.relationship_type = 'owner' AND uc.is_active = true
  WHERE ch.id = chat_uuid
  LIMIT 1;
$function$;