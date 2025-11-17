-- Обновление остальных DB функций с search_path для полного устранения проблем безопасности

-- 16. create_chat_with_company
CREATE OR REPLACE FUNCTION public.create_chat_with_company(chat_name text, chat_type text, creator_id uuid, company_uuid bigint DEFAULT NULL::bigint)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
DECLARE
  new_chat_id uuid;
  user_company_id bigint;
BEGIN
  IF company_uuid IS NULL THEN
    SELECT c.id INTO user_company_id
    FROM public.companies c
    JOIN public.user_companies uc ON uc.company_id = c.id
    WHERE uc.user_id = creator_id 
      AND uc.is_active = true
      AND uc.relationship_type = 'owner'
    ORDER BY uc.assigned_at DESC
    LIMIT 1;
    
    company_uuid := user_company_id;
  END IF;

  INSERT INTO public.chats (name, type, created_by, company_id)
  VALUES (chat_name, chat_type, creator_id, company_uuid)
  RETURNING id INTO new_chat_id;

  INSERT INTO public.chat_participants (chat_id, user_id, role)
  VALUES (new_chat_id, creator_id, 'admin')
  ON CONFLICT (chat_id, user_id) DO NOTHING;

  RETURN new_chat_id;
END;
$function$;

-- 17. is_user_developer
CREATE OR REPLACE FUNCTION public.is_user_developer()
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
  SELECT COALESCE(developer, false)
  FROM public.profiles 
  WHERE user_id = auth.uid();
$function$;

-- 18. get_user_chats_by_company
CREATE OR REPLACE FUNCTION public.get_user_chats_by_company(user_uuid uuid, company_uuid bigint DEFAULT NULL::bigint)
 RETURNS TABLE(id uuid, name text, type text, created_by uuid, created_at timestamp with time zone, updated_at timestamp with time zone, is_active boolean, metadata jsonb, company_id bigint, chat_number integer, telegram_supergroup_id bigint, telegram_topic_id integer, telegram_sync boolean)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
  SELECT 
    c.id, 
    c.name, 
    c.type, 
    c.created_by, 
    c.created_at, 
    c.updated_at, 
    c.is_active, 
    c.metadata, 
    c.company_id, 
    c.chat_number,
    c.telegram_supergroup_id,
    c.telegram_topic_id,
    c.telegram_sync
  FROM public.chats c
  WHERE c.is_active = true
    AND (
      (
        (SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = user_uuid) = true
        AND (
          company_uuid IS NULL
          OR c.company_id = company_uuid
        )
      )
      OR 
      (
        c.id IN (
          SELECT cp.chat_id 
          FROM public.chat_participants cp 
          WHERE cp.user_id = user_uuid AND cp.is_active = true
        )
        AND (
          (company_uuid IS NOT NULL AND c.company_id = company_uuid)
          OR 
          (company_uuid IS NULL AND c.company_id IS NULL)
        )
      )
    )
  ORDER BY c.updated_at DESC;
$function$;

-- 19. get_company_users
CREATE OR REPLACE FUNCTION public.get_company_users(target_company_id bigint, filter_relationship_type user_company_relationship DEFAULT NULL::user_company_relationship)
 RETURNS TABLE(user_id uuid, first_name text, last_name text, avatar_url text, type user_type, relationship_type user_company_relationship, assigned_at timestamp with time zone)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
  SELECT 
    p.user_id,
    p.first_name,
    p.last_name,
    p.avatar_url,
    'client'::user_type as type,
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