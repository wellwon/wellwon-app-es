-- Добавляем колонку is_developer
ALTER TABLE public.profiles 
ADD COLUMN is_developer boolean NOT NULL DEFAULT false;

-- Переносим данные из type в is_developer
UPDATE public.profiles 
SET is_developer = true 
WHERE type = 'ww_developer';

-- Удаляем колонку type
ALTER TABLE public.profiles 
DROP COLUMN type;

-- Обновляем функцию get_current_user_type для проверки разработчика
CREATE OR REPLACE FUNCTION public.is_developer()
RETURNS boolean
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path = 'public'
AS $$
  SELECT COALESCE(is_developer, false)
  FROM public.profiles
  WHERE user_id = auth.uid();
$$;

-- Заменяем старую функцию get_current_user_type
DROP FUNCTION IF EXISTS public.get_current_user_type();

CREATE OR REPLACE FUNCTION public.get_current_user_role()
RETURNS text
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path = 'public'
AS $$
  SELECT CASE 
    WHEN is_developer = true THEN 'developer'
    ELSE 'manager'
  END
  FROM public.profiles 
  WHERE user_id = auth.uid();
$$;