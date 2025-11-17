
-- 1) Enum со значениями-эмодзи
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'telegram_group_state') THEN
    CREATE TYPE public.telegram_group_state AS ENUM ('✅ Working', '🗄️ Archive', '❌ Closed');
  END IF;
END;
$$;

-- 2) Добавляем столбец для выбора статуса в Supabase-UI
ALTER TABLE public.telegram_supergroups
ADD COLUMN IF NOT EXISTS status_emoji public.telegram_group_state NOT NULL DEFAULT '✅ Working';

-- 3) Бэкофилл status_emoji из текущего is_active
UPDATE public.telegram_supergroups
SET status_emoji = CASE
  WHEN is_active IS TRUE THEN '✅ Working'::public.telegram_group_state
  WHEN is_active IS FALSE THEN '🗄️ Archive'::public.telegram_group_state
  ELSE '❌ Closed'::public.telegram_group_state
END
WHERE status_emoji IS DISTINCT FROM CASE
  WHEN is_active IS TRUE THEN '✅ Working'::public.telegram_group_state
  WHEN is_active IS FALSE THEN '🗄️ Archive'::public.telegram_group_state
  ELSE '❌ Closed'::public.telegram_group_state
END;

-- 4) Функции-триггеры для двусторонней синхронизации

-- При изменении status_emoji обновляем is_active
CREATE OR REPLACE FUNCTION public.sync_tg_supergroup_is_active_from_state()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
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

DROP TRIGGER IF EXISTS a_sync_from_state ON public.telegram_supergroups;
CREATE TRIGGER a_sync_from_state
BEFORE INSERT OR UPDATE OF status_emoji ON public.telegram_supergroups
FOR EACH ROW
EXECUTE FUNCTION public.sync_tg_supergroup_is_active_from_state();

-- При изменении is_active проставляем status_emoji
CREATE OR REPLACE FUNCTION public.sync_tg_supergroup_state_from_is_active()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
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

DROP TRIGGER IF EXISTS b_sync_from_is_active ON public.telegram_supergroups;
CREATE TRIGGER b_sync_from_is_active
BEFORE INSERT OR UPDATE OF is_active ON public.telegram_supergroups
FOR EACH ROW
EXECUTE FUNCTION public.sync_tg_supergroup_state_from_is_active();

-- 5) (Опционально) Индекс по новому статусу для удобства фильтрации в SQL-редакторе
CREATE INDEX IF NOT EXISTS idx_telegram_supergroups_status_emoji
  ON public.telegram_supergroups(status_emoji);
