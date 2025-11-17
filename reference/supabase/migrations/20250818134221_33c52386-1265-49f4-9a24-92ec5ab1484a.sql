-- Обновление всех DB функций с search_path для безопасности
-- Это предотвращает атаки через смену search_path

-- 1. get_client_from_chat
CREATE OR REPLACE FUNCTION public.get_client_from_chat(chat_uuid uuid)
 RETURNS uuid
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
  SELECT cp.user_id
  FROM public.chat_participants cp
  JOIN public.profiles p ON p.user_id = cp.user_id
  WHERE cp.chat_id = chat_uuid 
    AND p.type = 'client'
    AND cp.is_active = true
  LIMIT 1;
$function$;

-- 2. cleanup_expired_typing_indicators
CREATE OR REPLACE FUNCTION public.cleanup_expired_typing_indicators()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
BEGIN
  DELETE FROM public.typing_indicators 
  WHERE expires_at < now();
END;
$function$;

-- 3. add_chat_creator_as_participant
CREATE OR REPLACE FUNCTION public.add_chat_creator_as_participant()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
BEGIN
  INSERT INTO public.chat_participants (chat_id, user_id, role)
  VALUES (NEW.id, NEW.created_by, 'admin')
  ON CONFLICT (chat_id, user_id) DO NOTHING;
  
  RETURN NEW;
END;
$function$;

-- 4. update_user_type_for_testing
CREATE OR REPLACE FUNCTION public.update_user_type_for_testing(target_email text, new_user_type user_type)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
DECLARE
  user_updated boolean := false;
BEGIN
  UPDATE public.profiles 
  SET type = new_user_type
  WHERE user_id IN (
    SELECT id FROM auth.users WHERE email = target_email
  );
  
  GET DIAGNOSTICS user_updated = ROW_COUNT;
  RETURN user_updated > 0;
END;
$function$;

-- 5. sync_tg_supergroup_is_active_from_state
CREATE OR REPLACE FUNCTION public.sync_tg_supergroup_is_active_from_state()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
BEGIN
  IF TG_OP = 'INSERT' OR NEW.status_emoji IS DISTINCT FROM COALESCE(OLD.status_emoji, NULL) THEN
    IF NEW.status_emoji = '✅ Working' THEN
      NEW.is_active := TRUE;
    ELSIF NEW.status_emoji = '🗄️ Archive' THEN
      NEW.is_active := FALSE;
    ELSIF NEW.status_emoji = '❌ Closed' THEN
      NEW.is_active := NULL;
    END IF;
  END IF;
  RETURN NEW;
END;
$function$;

-- 6. update_participant_last_read
CREATE OR REPLACE FUNCTION public.update_participant_last_read()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
BEGIN
  UPDATE public.chat_participants 
  SET last_read_at = NEW.read_at
  WHERE chat_id = (
    SELECT chat_id 
    FROM public.messages 
    WHERE id = NEW.message_id
  ) 
  AND user_id = NEW.user_id;
  
  RETURN NEW;
END;
$function$;

-- 7. add_admins_to_new_chat
CREATE OR REPLACE FUNCTION public.add_admins_to_new_chat()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
BEGIN
  INSERT INTO public.chat_participants (chat_id, user_id, role)
  SELECT NEW.id, p.user_id, 'observer'
  FROM public.profiles p
  WHERE COALESCE(p.developer, false) = true 
  AND p.active = true
  AND p.user_id != NEW.created_by
  ON CONFLICT (chat_id, user_id) DO NOTHING;
  
  RETURN NEW;
END;
$function$;

-- 8. sync_tg_supergroup_state_from_is_active
CREATE OR REPLACE FUNCTION public.sync_tg_supergroup_state_from_is_active()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
BEGIN
  IF TG_OP = 'INSERT' OR NEW.is_active IS DISTINCT FROM COALESCE(OLD.is_active, NULL) THEN
    IF NEW.is_active IS TRUE THEN
      NEW.status_emoji := '✅ Working'::public.telegram_group_state;
    ELSIF NEW.is_active IS FALSE THEN
      NEW.status_emoji := '🗄️ Archive'::public.telegram_group_state;
    ELSE
      NEW.status_emoji := '❌ Closed'::public.telegram_group_state;
    END IF;
  END IF;
  RETURN NEW;
END;
$function$;

-- 9. is_current_user_developer
CREATE OR REPLACE FUNCTION public.is_current_user_developer()
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
  SELECT COALESCE(developer, false)
  FROM profiles
  WHERE user_id = auth.uid();
$function$;

-- 10. assign_company_to_chat_after_participants
CREATE OR REPLACE FUNCTION public.assign_company_to_chat_after_participants(chat_uuid uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
DECLARE
  client_user_id uuid;
  client_company_id bigint;
BEGIN
  SELECT cp.user_id INTO client_user_id
  FROM public.chat_participants cp
  JOIN public.profiles p ON p.user_id = cp.user_id
  WHERE cp.chat_id = chat_uuid 
    AND p.type = 'client'
    AND cp.is_active = true
  LIMIT 1;
  
  IF client_user_id IS NOT NULL THEN
    SELECT c.id INTO client_company_id
    FROM public.companies c
    JOIN public.user_companies uc ON uc.company_id = c.id
    WHERE uc.user_id = client_user_id 
      AND uc.is_active = true
      AND uc.relationship_type = 'owner'
    LIMIT 1;
    
    IF client_company_id IS NOT NULL THEN
      UPDATE public.chats 
      SET company_id = client_company_id 
      WHERE id = chat_uuid AND company_id IS NULL;
    END IF;
  END IF;
END;
$function$;