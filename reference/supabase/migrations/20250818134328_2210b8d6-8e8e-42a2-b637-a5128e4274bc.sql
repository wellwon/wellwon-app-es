-- Обновление остальных DB функций с search_path для безопасности (исправление)

-- 11. assign_tg_user_number
CREATE OR REPLACE FUNCTION public.assign_tg_user_number()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
BEGIN
  IF NEW.user_number IS NULL THEN
    NEW.user_number := nextval('public.tg_user_id_seq');
  END IF;
  RETURN NEW;
END;
$function$;

-- 12. propagate_supergroup_company_to_chats
CREATE OR REPLACE FUNCTION public.propagate_supergroup_company_to_chats()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
BEGIN
  IF NEW.company_id IS NOT NULL THEN
    UPDATE public.chats c
    SET company_id = NEW.company_id,
        updated_at = now()
    WHERE c.telegram_supergroup_id = NEW.id
      AND (c.company_id IS DISTINCT FROM NEW.company_id);
  END IF;
  RETURN NEW;
END;
$function$;

-- 13. bind_client_chats_to_first_company
CREATE OR REPLACE FUNCTION public.bind_client_chats_to_first_company(client_user_id uuid, company_uuid bigint)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
BEGIN
  UPDATE public.chats 
  SET company_id = company_uuid 
  WHERE company_id IS NULL 
    AND id IN (
      SELECT DISTINCT cp.chat_id 
      FROM public.chat_participants cp 
      WHERE cp.user_id = client_user_id 
        AND cp.is_active = true
    );
END;
$function$;

-- 14. auto_assign_company_to_chat
CREATE OR REPLACE FUNCTION public.auto_assign_company_to_chat()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
DECLARE
  new_chat_number INTEGER;
BEGIN
  IF NEW.chat_number IS NULL THEN
    SELECT public.get_next_chat_number() INTO new_chat_number;
    NEW.chat_number := new_chat_number;
  END IF;

  IF NEW.company_id IS NOT NULL THEN
    RETURN NEW;
  END IF;
  
  RETURN NEW;
END;
$function$;

-- 15. apply_supergroup_company_on_chat
CREATE OR REPLACE FUNCTION public.apply_supergroup_company_on_chat()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', pg_temp
AS $function$
DECLARE
  sg_company_id bigint;
BEGIN
  IF NEW.telegram_supergroup_id IS NOT NULL THEN
    SELECT company_id
      INTO sg_company_id
    FROM public.telegram_supergroups
    WHERE id = NEW.telegram_supergroup_id;

    IF sg_company_id IS NOT NULL THEN
      IF NEW.company_id IS DISTINCT FROM sg_company_id THEN
        NEW.company_id := sg_company_id;
      END IF;
    END IF;
  END IF;

  RETURN NEW;
END;
$function$;