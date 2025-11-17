-- Завершение обновления всех остальных DB функций

-- 20. get_current_user_type
CREATE OR REPLACE FUNCTION public.get_current_user_type()
 RETURNS text
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
  SELECT CASE 
    WHEN COALESCE(developer, false) = true THEN 'developer'
    ELSE 'user'
  END
  FROM public.profiles 
  WHERE user_id = auth.uid();
$function$;

-- 21. is_developer
CREATE OR REPLACE FUNCTION public.is_developer()
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
  SELECT COALESCE(developer, false)
  FROM public.profiles
  WHERE user_id = auth.uid();
$function$;

-- 22. should_ignore_telegram_supergroup
CREATE OR REPLACE FUNCTION public.should_ignore_telegram_supergroup(supergroup_id bigint)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
BEGIN
  RETURN supergroup_id IN (
    -1002693383546, -1002618114488, -1002554121378, 
    -1002848008437, -1002245678432, -1002779635244, 
    -1002598871574, -1002880892698
  );
END;
$function$;

-- 23. get_next_user_number
CREATE OR REPLACE FUNCTION public.get_next_user_number()
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
DECLARE
  next_number INTEGER;
BEGIN
  SELECT COALESCE(MAX(user_number), 0) + 1 INTO next_number
  FROM public.profiles;
  
  RETURN next_number;
END;
$function$;

-- 24. normalize_telegram_supergroup_id
CREATE OR REPLACE FUNCTION public.normalize_telegram_supergroup_id(input_id bigint)
 RETURNS bigint
 LANGUAGE plpgsql
 IMMUTABLE
 SET search_path TO 'public', pg_temp
AS $function$
BEGIN
  IF input_id > 0 THEN
    RETURN input_id * -1 - 1000000000000;
  END IF;
  
  RETURN input_id;
END;
$function$;

-- 25. update_updated_at_column
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$function$;

-- 26. get_next_chat_number
CREATE OR REPLACE FUNCTION public.get_next_chat_number()
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
DECLARE
  next_number INTEGER;
BEGIN
  SELECT COALESCE(MAX(chat_number), 0) + 1 INTO next_number
  FROM public.chats;
  
  RETURN next_number;
END;
$function$;

-- 27. update_chat_telegram_settings
CREATE OR REPLACE FUNCTION public.update_chat_telegram_settings(chat_uuid uuid, enable_sync boolean, supergroup_id bigint DEFAULT NULL::bigint, topic_id integer DEFAULT NULL::integer)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM public.chat_participants cp
    WHERE cp.chat_id = chat_uuid 
      AND cp.user_id = auth.uid()
      AND cp.is_active = true
      AND cp.role IN ('admin', 'observer')
  ) AND NOT EXISTS (
    SELECT 1 FROM public.profiles p
    WHERE p.user_id = auth.uid() 
      AND COALESCE(p.developer, false) = true
  ) THEN
    RETURN FALSE;
  END IF;

  UPDATE public.chats
  SET 
    telegram_sync = enable_sync,
    telegram_supergroup_id = CASE WHEN enable_sync THEN supergroup_id ELSE NULL END,
    telegram_topic_id = CASE WHEN enable_sync THEN topic_id ELSE NULL END,
    updated_at = now()
  WHERE id = chat_uuid;

  RETURN TRUE;
END;
$function$;