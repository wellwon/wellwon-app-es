-- Удаляем проблемные RLS политики, которые обращаются к auth.users
DROP POLICY IF EXISTS "Enhanced profile viewing policy" ON public.profiles;
DROP POLICY IF EXISTS "Enhanced profile updating policy" ON public.profiles;

-- Создаем простые RLS политики без обращений к auth.users
CREATE POLICY "Users can view their own profile" ON public.profiles
FOR SELECT 
USING (auth.uid() = user_id);

CREATE POLICY "Users can update their own profile" ON public.profiles
FOR UPDATE 
USING (auth.uid() = user_id AND active = true);

-- Создаем функцию для безопасной проверки user_type
CREATE OR REPLACE FUNCTION public.get_current_user_type()
RETURNS TEXT AS $$
DECLARE
  user_type_value TEXT;
BEGIN
  -- Получаем тип пользователя из auth.users через RPC
  SELECT COALESCE(
    (auth.jwt() ->> 'user_metadata')::json ->> 'user_type',
    'client'
  ) INTO user_type_value;
  
  RETURN user_type_value;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;