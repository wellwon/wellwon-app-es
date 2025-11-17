-- Create the user_type enum if it doesn't exist
CREATE TYPE IF NOT EXISTS public.user_type AS ENUM ('client', 'performer', 'ww_manager', 'ww_developer');

-- Create the missing trigger to automatically create profiles when users sign up
CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();