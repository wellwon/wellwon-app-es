-- Исправление предупреждений безопасности

-- 1. Исправляем функцию is_user_developer с правильным search_path
CREATE OR REPLACE FUNCTION public.is_user_developer()
RETURNS BOOLEAN 
LANGUAGE SQL 
STABLE 
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT COALESCE(developer, false)
  FROM public.profiles 
  WHERE user_id = auth.uid();
$$;

-- 2. Исправляем функцию is_developer с правильным search_path
CREATE OR REPLACE FUNCTION public.is_developer()
RETURNS BOOLEAN 
LANGUAGE SQL 
STABLE 
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT COALESCE(developer, false)
  FROM public.profiles
  WHERE user_id = auth.uid();
$$;