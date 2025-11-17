-- Fix the handle_new_user function to properly handle null values
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.profiles (user_id, display_name, first_name, last_name)
  VALUES (
    NEW.id,
    COALESCE(
      NULLIF(NEW.raw_user_meta_data->>'display_name', ''),
      CASE 
        WHEN NEW.raw_user_meta_data->>'first_name' IS NOT NULL OR NEW.raw_user_meta_data->>'last_name' IS NOT NULL THEN
          CONCAT(
            COALESCE(NEW.raw_user_meta_data->>'first_name', ''),
            CASE 
              WHEN NEW.raw_user_meta_data->>'first_name' IS NOT NULL AND NEW.raw_user_meta_data->>'last_name' IS NOT NULL THEN ' '
              ELSE ''
            END,
            COALESCE(NEW.raw_user_meta_data->>'last_name', '')
          )
        ELSE NULL
      END
    ),
    NULLIF(NEW.raw_user_meta_data->>'first_name', ''),
    NULLIF(NEW.raw_user_meta_data->>'last_name', '')
  );
  RETURN NEW;
END;
$$;