
-- 1) Функция и триггер: при назначении/изменении company_id у супергруппы
--    синхронизировать company_id во всех связанных чатах

CREATE OR REPLACE FUNCTION public.propagate_supergroup_company_to_chats()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
BEGIN
  -- Если у супергруппы указана компания — проставляем её во всех чатах этой группы.
  IF NEW.company_id IS NOT NULL THEN
    UPDATE public.chats c
    SET company_id = NEW.company_id,
        updated_at = now()
    WHERE c.telegram_supergroup_id = NEW.id
      AND (c.company_id IS DISTINCT FROM NEW.company_id);
  END IF;

  -- Если company_id у супергруппы очищен (NULL) — ничего не делаем (по требованиям).
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_propagate_company_on_supergroup ON public.telegram_supergroups;
CREATE TRIGGER trg_propagate_company_on_supergroup
AFTER INSERT OR UPDATE OF company_id ON public.telegram_supergroups
FOR EACH ROW
EXECUTE FUNCTION public.propagate_supergroup_company_to_chats();


-- 2) Функция и триггер: при создании/изменении чата с telegram_supergroup_id
--    автоматически проставлять company_id из супергруппы

CREATE OR REPLACE FUNCTION public.apply_supergroup_company_on_chat()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
  sg_company_id bigint;
BEGIN
  IF NEW.telegram_supergroup_id IS NOT NULL THEN
    SELECT company_id
      INTO sg_company_id
    FROM public.telegram_supergroups
    WHERE id = NEW.telegram_supergroup_id;

    -- Если у супергруппы есть company_id, то в чате делаем его таким же.
    IF sg_company_id IS NOT NULL THEN
      IF NEW.company_id IS DISTINCT FROM sg_company_id THEN
        NEW.company_id := sg_company_id;
      END IF;
    END IF;
  END IF;

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_apply_supergroup_company_on_chat_insupd ON public.chats;
CREATE TRIGGER trg_apply_supergroup_company_on_chat_insupd
BEFORE INSERT OR UPDATE OF telegram_supergroup_id, company_id ON public.chats
FOR EACH ROW
EXECUTE FUNCTION public.apply_supergroup_company_on_chat();


-- 3) Разовая синхронизация существующих данных:
--    Приводим все чаты к company_id своей супергруппы (если он задан)
--    Перезаписываем отличающиеся значения, чтобы “во всех чатах” было одинаково.
UPDATE public.chats c
SET company_id = t.company_id,
    updated_at = now()
FROM public.telegram_supergroups t
WHERE c.telegram_supergroup_id = t.id
  AND t.company_id IS NOT NULL
  AND (c.company_id IS DISTINCT FROM t.company_id);
