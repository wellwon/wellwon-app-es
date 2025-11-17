-- Step 1: Update all client and performer users to ww_manager
UPDATE public.profiles 
SET type = 'ww_manager' 
WHERE type IN ('client', 'performer');

-- Step 2: Find and drop policies that depend on the type column
DROP POLICY IF EXISTS "Chat creators and admins can update chats" ON public.chats;

-- Step 3: Drop the default value temporarily
ALTER TABLE public.profiles ALTER COLUMN type DROP DEFAULT;

-- Step 4: Create new enum without client and performer
CREATE TYPE public.user_type_new AS ENUM ('ww_admin', 'ww_manager', 'ww_developer');

-- Step 5: Update the profiles table to use the new enum
ALTER TABLE public.profiles 
ALTER COLUMN type TYPE public.user_type_new 
USING type::text::public.user_type_new;

-- Step 6: Drop the old enum and rename the new one
DROP TYPE public.user_type;
ALTER TYPE public.user_type_new RENAME TO user_type;

-- Step 7: Restore the default value with the new enum
ALTER TABLE public.profiles ALTER COLUMN type SET DEFAULT 'ww_manager'::user_type;

-- Step 8: Recreate the RLS policy with updated type references
CREATE POLICY "Chat creators and admins can update chats"
ON public.chats
FOR UPDATE
TO authenticated
USING (
  created_by = auth.uid() 
  OR EXISTS (
    SELECT 1 FROM public.profiles 
    WHERE user_id = auth.uid() 
    AND type IN ('ww_admin', 'ww_manager', 'ww_developer')
  )
);

-- Step 9: Create new function to replace get_client_company_from_chat
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