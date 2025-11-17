-- Update database functions to return new company fields
CREATE OR REPLACE FUNCTION public.get_user_company(user_uuid uuid)
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
   average_delivery_time numeric,
   on_time_delivery_percentage numeric,
   created_at timestamp with time zone, 
   updated_at timestamp with time zone
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
    c.average_delivery_time,
    c.on_time_delivery_percentage,
    c.created_at, 
    c.updated_at
  FROM public.companies c
  JOIN public.profiles p ON p.company_id = c.id
  WHERE p.user_id = user_uuid;
$function$;

CREATE OR REPLACE FUNCTION public.get_client_company_from_chat(chat_uuid uuid)
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
   average_delivery_time numeric,
   on_time_delivery_percentage numeric,
   created_at timestamp with time zone, 
   updated_at timestamp with time zone, 
   client_user_id uuid
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
    c.average_delivery_time,
    c.on_time_delivery_percentage,
    c.created_at, 
    c.updated_at, 
    p.user_id
  FROM public.companies c
  JOIN public.profiles p ON p.company_id = c.id
  JOIN public.chat_participants cp ON cp.user_id = p.user_id
  WHERE cp.chat_id = chat_uuid 
  AND p.type = 'client'
  AND cp.is_active = true
  LIMIT 1;
$function$;