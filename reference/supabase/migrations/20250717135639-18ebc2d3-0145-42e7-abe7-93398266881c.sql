-- Создание таблицы profiles для дополнительной информации пользователей
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  display_name TEXT,
  first_name TEXT,
  last_name TEXT,
  avatar_url TEXT,
  bio TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Включаем Row Level Security
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Создание политик RLS (с проверкой существования)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'profiles' 
        AND policyname = 'Профили доступны для просмотра всем пользователям'
    ) THEN
        CREATE POLICY "Профили доступны для просмотра всем пользователям"
        ON public.profiles
        FOR SELECT
        USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'profiles' 
        AND policyname = 'Пользователи могут обновлять свой профиль'
    ) THEN
        CREATE POLICY "Пользователи могут обновлять свой профиль"
        ON public.profiles
        FOR UPDATE
        USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'profiles' 
        AND policyname = 'Пользователи могут создавать свой профиль'
    ) THEN
        CREATE POLICY "Пользователи могут создавать свой профиль"
        ON public.profiles
        FOR INSERT
        WITH CHECK (auth.uid() = user_id);
    END IF;
END $$;

-- Обновление функции для автоматического создания профиля при регистрации (перезаписываем существующую)
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (user_id, display_name, first_name, last_name)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data ->> 'display_name', NEW.email),
    NEW.raw_user_meta_data ->> 'first_name',
    NEW.raw_user_meta_data ->> 'last_name'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;