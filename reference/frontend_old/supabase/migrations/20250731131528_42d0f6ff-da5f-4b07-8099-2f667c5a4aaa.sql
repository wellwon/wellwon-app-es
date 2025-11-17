-- Create the user_type enum (check if exists first)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_type') THEN
        CREATE TYPE public.user_type AS ENUM ('client', 'performer', 'ww_manager', 'ww_developer');
    END IF;
END $$;

-- Create the missing trigger to automatically create profiles when users sign up
CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();