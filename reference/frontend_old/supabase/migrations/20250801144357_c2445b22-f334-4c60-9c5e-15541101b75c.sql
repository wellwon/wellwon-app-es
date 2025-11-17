-- Убираем поле display_name из таблицы profiles, так как оно будет вычисляться динамически
ALTER TABLE public.profiles DROP COLUMN display_name;

-- Обновляем функцию handle_new_user() чтобы не работать с display_name
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.profiles (user_id, first_name, last_name, active, type)
  VALUES (
    NEW.id,
    NULLIF(NEW.raw_user_meta_data->>'first_name', ''),
    NULLIF(NEW.raw_user_meta_data->>'last_name', ''),
    true, -- new users are active by default
    COALESCE(NULLIF(NEW.raw_user_meta_data->>'user_type', ''), 'client')::public.user_type
  );
  RETURN NEW;
END;
$$;