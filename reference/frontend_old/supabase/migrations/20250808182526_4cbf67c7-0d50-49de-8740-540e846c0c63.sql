-- Update get_user_company function to use user_companies table first, then fallback to profiles.company_id
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
$function$