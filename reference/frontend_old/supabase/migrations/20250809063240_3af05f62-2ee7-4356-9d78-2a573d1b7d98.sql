-- Fix search path security warnings for all functions

-- Fix auto_assign_company_to_chat function
CREATE OR REPLACE FUNCTION public.auto_assign_company_to_chat()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
  client_user_id uuid;
  client_company_id bigint;
BEGIN
  -- Skip if company_id is already set
  IF NEW.company_id IS NOT NULL THEN
    RETURN NEW;
  END IF;
  
  -- Since participants are added after chat creation, we need to handle this differently
  -- For now, just return the new record and let the application handle company assignment
  RETURN NEW;
END;
$function$;

-- Fix assign_company_to_chat_after_participants function
CREATE OR REPLACE FUNCTION public.assign_company_to_chat_after_participants(chat_uuid uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
  client_user_id uuid;
  client_company_id bigint;
BEGIN
  -- Find client in chat participants
  SELECT cp.user_id INTO client_user_id
  FROM public.chat_participants cp
  JOIN public.profiles p ON p.user_id = cp.user_id
  WHERE cp.chat_id = chat_uuid 
    AND p.type = 'client'
    AND cp.is_active = true
  LIMIT 1;
  
  -- If client found, get their company
  IF client_user_id IS NOT NULL THEN
    SELECT c.id INTO client_company_id
    FROM public.companies c
    JOIN public.user_companies uc ON uc.company_id = c.id
    WHERE uc.user_id = client_user_id 
      AND uc.is_active = true
      AND uc.relationship_type = 'owner'
    LIMIT 1;
    
    -- Set company_id if found and not already set
    IF client_company_id IS NOT NULL THEN
      UPDATE public.chats 
      SET company_id = client_company_id 
      WHERE id = chat_uuid AND company_id IS NULL;
    END IF;
  END IF;
END;
$function$;

-- Fix get_current_user_type function
CREATE OR REPLACE FUNCTION public.get_current_user_type()
RETURNS text
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  SELECT type::text FROM public.profiles WHERE user_id = auth.uid();
$function$;

-- Fix get_user_company function  
CREATE OR REPLACE FUNCTION public.get_user_company(user_uuid uuid)
RETURNS TABLE(id bigint, name text, company_type text, balance numeric, status company_status, orders_count integer, turnover numeric, rating numeric, successful_deliveries integer, created_at timestamp with time zone, updated_at timestamp with time zone)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  -- First try to get company from user_companies table (new schema)
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
    c.updated_at
  FROM public.companies c
  JOIN public.user_companies uc ON uc.company_id = c.id
  WHERE uc.user_id = user_uuid 
    AND uc.is_active = true
    AND uc.relationship_type = 'owner'
  
  UNION ALL
  
  -- Fallback to old schema (profiles.company_id) if not found in user_companies
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
    c.updated_at
  FROM public.companies c
  JOIN public.profiles p ON p.company_id = c.id
  WHERE p.user_id = user_uuid
    AND NOT EXISTS (
      SELECT 1 FROM public.user_companies uc 
      WHERE uc.user_id = user_uuid AND uc.is_active = true
    )
  
  LIMIT 1;
$function$;