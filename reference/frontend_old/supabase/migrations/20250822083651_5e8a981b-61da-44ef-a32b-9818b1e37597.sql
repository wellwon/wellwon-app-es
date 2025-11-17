-- Добавляем недостающую колонку is_bot в tg_users
ALTER TABLE public.tg_users ADD COLUMN IF NOT EXISTS is_bot boolean DEFAULT false;

-- 1) Функция для UPSERT в tg_users на основе telegram_group_members
CREATE OR REPLACE FUNCTION public.upsert_tg_user_from_member()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
BEGIN
  INSERT INTO public.tg_users AS u (id, first_name, last_name, username, is_bot)
  VALUES (
    NEW.telegram_user_id,
    COALESCE(NULLIF(NEW.first_name, ''), NULLIF(NEW.username, ''), 'Unknown'),
    NULLIF(NEW.last_name, ''),
    NULLIF(NEW.username, ''),
    COALESCE(NEW.is_bot, false)
  )
  ON CONFLICT (id) DO UPDATE
  SET
    first_name = COALESCE(EXCLUDED.first_name, u.first_name),
    last_name  = COALESCE(EXCLUDED.last_name,  u.last_name),
    username   = COALESCE(EXCLUDED.username,   u.username),
    is_bot     = COALESCE(EXCLUDED.is_bot,     u.is_bot),
    updated_at = timezone('utc', now());
  RETURN NEW;
END;
$$;

-- 2) Триггеры: на вставку и на обновление ключевых полей
DROP TRIGGER IF EXISTS trg_tg_users_sync_from_members_ins ON public.telegram_group_members;
CREATE TRIGGER trg_tg_users_sync_from_members_ins
AFTER INSERT ON public.telegram_group_members
FOR EACH ROW
EXECUTE FUNCTION public.upsert_tg_user_from_member();

DROP TRIGGER IF EXISTS trg_tg_users_sync_from_members_upd ON public.telegram_group_members;
CREATE TRIGGER trg_tg_users_sync_from_members_upd
AFTER UPDATE OF first_name, last_name, username, is_bot ON public.telegram_group_members
FOR EACH ROW
WHEN (NEW.telegram_user_id IS NOT NULL)
EXECUTE FUNCTION public.upsert_tg_user_from_member();

-- 3) Бэкфилл: внести недостающих пользователей в tg_users из существующих участников групп
INSERT INTO public.tg_users (id, first_name, last_name, username, is_bot)
SELECT DISTINCT
  tgm.telegram_user_id,
  COALESCE(NULLIF(tgm.first_name, ''), NULLIF(tgm.username, ''), 'Unknown'),
  NULLIF(tgm.last_name, ''),
  NULLIF(tgm.username, ''),
  COALESCE(tgm.is_bot, false)
FROM public.telegram_group_members tgm
LEFT JOIN public.tg_users tu ON tu.id = tgm.telegram_user_id
WHERE tu.id IS NULL
ON CONFLICT (id) DO NOTHING;

-- 4) Дозаполнить пропуски, если в tg_users есть null, а в участниках есть значения
WITH latest AS (
  SELECT DISTINCT ON (telegram_user_id)
         telegram_user_id, first_name, last_name, username, is_bot
  FROM public.telegram_group_members
  ORDER BY telegram_user_id, joined_at DESC
)
UPDATE public.tg_users tu
SET
  first_name = COALESCE(tu.first_name, COALESCE(NULLIF(latest.first_name,''), NULLIF(latest.username,''), 'Unknown')),
  last_name  = COALESCE(tu.last_name,  NULLIF(latest.last_name,'')),
  username   = COALESCE(tu.username,   NULLIF(latest.username,'')),
  is_bot     = COALESCE(tu.is_bot,     latest.is_bot),
  updated_at = timezone('utc', now())
FROM latest
WHERE tu.id = latest.telegram_user_id
  AND (tu.first_name IS NULL OR tu.last_name IS NULL OR tu.username IS NULL OR tu.is_bot IS NULL);