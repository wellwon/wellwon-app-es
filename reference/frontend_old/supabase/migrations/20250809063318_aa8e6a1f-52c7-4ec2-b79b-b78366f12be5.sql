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

-- Fix get_user_company function (remove fallback to non-existent column)
CREATE OR REPLACE FUNCTION public.get_user_company(user_uuid uuid)
RETURNS TABLE(id bigint, name text, company_type text, balance numeric, status company_status, orders_count integer, turnover numeric, rating numeric, successful_deliveries integer, created_at timestamp with time zone, updated_at timestamp with time zone)
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
    c.updated_at
  FROM public.companies c
  JOIN public.user_companies uc ON uc.company_id = c.id
  WHERE uc.user_id = user_uuid 
    AND uc.is_active = true
    AND uc.relationship_type = 'owner'
  LIMIT 1;
$function$;

-- Fix other functions with search path warnings
CREATE OR REPLACE FUNCTION public.get_client_company_from_chat(chat_uuid uuid)
RETURNS TABLE(id bigint, name text, company_type text, balance numeric, status company_status, orders_count integer, turnover numeric, rating numeric, successful_deliveries integer, created_at timestamp with time zone, updated_at timestamp with time zone, client_user_id uuid)
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
    uc.user_id as client_user_id
  FROM public.companies c
  JOIN public.chats ch ON ch.company_id = c.id
  LEFT JOIN public.user_companies uc ON uc.company_id = c.id AND uc.relationship_type = 'owner' AND uc.is_active = true
  WHERE ch.id = chat_uuid
  LIMIT 1;
$function$;

CREATE OR REPLACE FUNCTION public.get_user_companies(target_user_id uuid, filter_relationship_type user_company_relationship DEFAULT NULL::user_company_relationship)
RETURNS TABLE(id bigint, name text, company_type text, status company_status, relationship_type user_company_relationship, assigned_at timestamp with time zone)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  SELECT 
    c.id,
    c.name,
    c.company_type,
    c.status,
    uc.relationship_type,
    uc.assigned_at
  FROM public.companies c
  JOIN public.user_companies uc ON uc.company_id = c.id
  WHERE uc.user_id = target_user_id
    AND uc.is_active = true
    AND (filter_relationship_type IS NULL OR uc.relationship_type = filter_relationship_type)
  ORDER BY uc.assigned_at DESC;
$function$;

CREATE OR REPLACE FUNCTION public.get_company_users(target_company_id bigint, filter_relationship_type user_company_relationship DEFAULT NULL::user_company_relationship)
RETURNS TABLE(user_id uuid, first_name text, last_name text, avatar_url text, type user_type, relationship_type user_company_relationship, assigned_at timestamp with time zone)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  SELECT 
    p.user_id,
    p.first_name,
    p.last_name,
    p.avatar_url,
    p.type,
    uc.relationship_type,
    uc.assigned_at
  FROM public.profiles p
  JOIN public.user_companies uc ON uc.user_id = p.user_id
  WHERE uc.company_id = target_company_id
    AND uc.is_active = true
    AND p.active = true
    AND (filter_relationship_type IS NULL OR uc.relationship_type = filter_relationship_type)
  ORDER BY uc.assigned_at ASC;
$function$;