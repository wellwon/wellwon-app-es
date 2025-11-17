
-- 1) Добавить колонку is_active (если отсутствует), разрешить NULL, дефолт = true
ALTER TABLE public.telegram_supergroups
ADD COLUMN IF NOT EXISTS is_active boolean;

ALTER TABLE public.telegram_supergroups
ALTER COLUMN is_active DROP NOT NULL,
ALTER COLUMN is_active SET DEFAULT true;

-- 2) Для существующих строк без значения проставить Working (true)
UPDATE public.telegram_supergroups
SET is_active = true
WHERE is_active IS NULL;

-- 3) Если ранее было поле status, аккуратно переназначить значения в is_active:
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'telegram_supergroups'
      AND column_name = 'status'
  ) THEN
    -- Маппинг:
    -- ✅ Working -> true
    -- 🗄️ Archive -> false
    -- ❌ Closed  -> NULL
    UPDATE public.telegram_supergroups
    SET is_active = CASE
      WHEN status::text IN ('✅ Working','Working','Active','working','active') THEN true
      WHEN status::text IN ('🗄️ Archive','Archive','archived','archive') THEN false
      WHEN status::text IN ('❌ Closed','Closed','closed') THEN NULL
      ELSE is_active
    END;
  END IF;
END;
$$;

-- 4) Индекс по is_active для быстрых выборок
CREATE INDEX IF NOT EXISTS idx_telegram_supergroups_is_active
ON public.telegram_supergroups(is_active);
