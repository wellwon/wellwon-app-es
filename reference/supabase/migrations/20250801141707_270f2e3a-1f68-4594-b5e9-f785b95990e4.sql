-- Удаляем все существующие проблемные RLS политики
DROP POLICY IF EXISTS "Enhanced profile viewing policy" ON public.profiles;
DROP POLICY IF EXISTS "Enhanced profile updating policy" ON public.profiles;

-- Убеждаемся, что базовые политики работают правильно
-- Если они уже существуют, ничего не произойдет
DO $$
BEGIN
    -- Проверяем и пересоздаем политику просмотра если нужно
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'profiles' 
        AND policyname = 'Users can view their own profile'
        AND cmd = 'SELECT'
    ) THEN
        CREATE POLICY "Users can view their own profile" ON public.profiles
        FOR SELECT 
        USING (auth.uid() = user_id);
    END IF;

    -- Проверяем и пересоздаем политику обновления если нужно
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'profiles' 
        AND policyname = 'Users can update their own profile'
        AND cmd = 'UPDATE'
    ) THEN
        CREATE POLICY "Users can update their own profile" ON public.profiles
        FOR UPDATE 
        USING (auth.uid() = user_id AND active = true);
    END IF;
END
$$;