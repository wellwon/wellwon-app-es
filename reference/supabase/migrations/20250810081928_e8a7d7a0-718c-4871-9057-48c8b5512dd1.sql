-- Fix the get_user_chats_by_company function to properly filter chats by company
CREATE OR REPLACE FUNCTION public.get_user_chats_by_company(user_uuid uuid, company_uuid bigint DEFAULT NULL::bigint)
 RETURNS TABLE(id uuid, name text, type text, created_by uuid, created_at timestamp with time zone, updated_at timestamp with time zone, is_active boolean, metadata jsonb, company_id bigint)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  -- For admin users, return all chats when no company filter is specified
  -- For regular users, only return chats that match the specified company
  SELECT c.id, c.name, c.type, c.created_by, c.created_at, c.updated_at, c.is_active, c.metadata, c.company_id
  FROM public.chats c
  WHERE c.is_active = true
    AND (
      -- Admin users see all chats when no company filter is provided
      (
        (SELECT type FROM public.profiles WHERE user_id = user_uuid) IN ('ww_manager', 'ww_developer')
        AND (
          company_uuid IS NULL -- Show all chats for admins when no company specified
          OR c.company_id = company_uuid -- Or specific company chats when specified
        )
      )
      OR 
      -- Regular users see chats they participate in, filtered by company
      (
        c.id IN (
          SELECT cp.chat_id 
          FROM public.chat_participants cp 
          WHERE cp.user_id = user_uuid AND cp.is_active = true
        )
        AND (
          -- When company filter is provided, only show chats for that specific company
          (company_uuid IS NOT NULL AND c.company_id = company_uuid)
          OR 
          -- When no company filter, only show unassigned chats (company_id IS NULL)
          (company_uuid IS NULL AND c.company_id IS NULL)
        )
      )
    )
  ORDER BY c.updated_at DESC;
$function$