-- Add is_developer boolean column to profiles
ALTER TABLE public.profiles ADD COLUMN is_developer boolean NOT NULL DEFAULT false;

-- Migrate existing data: set is_developer = true for ww_developer users
UPDATE public.profiles SET is_developer = true WHERE type = 'ww_developer';

-- Drop the old type column and enum
ALTER TABLE public.profiles DROP COLUMN type CASCADE;
DROP TYPE IF EXISTS user_type CASCADE;

-- Update the is_developer function to use the new column
CREATE OR REPLACE FUNCTION public.is_developer()
RETURNS boolean
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  SELECT COALESCE(is_developer, false)
  FROM public.profiles
  WHERE user_id = auth.uid();
$function$;

-- Update get_current_user_type function to return simple types
CREATE OR REPLACE FUNCTION public.get_current_user_type()
RETURNS text
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  SELECT CASE 
    WHEN is_developer = true THEN 'developer'
    ELSE 'client'
  END
  FROM public.profiles 
  WHERE user_id = auth.uid();
$function$;

-- Update RLS policies for chats table
DROP POLICY IF EXISTS "Simple chats view" ON public.chats;
CREATE POLICY "Simple chats view" ON public.chats
FOR SELECT USING (
  (created_by = auth.uid()) OR 
  (SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true
);

-- Update RLS policies for chat_participants table  
DROP POLICY IF EXISTS "Simple chat participants view" ON public.chat_participants;
CREATE POLICY "Simple chat participants view" ON public.chat_participants
FOR SELECT USING (
  (user_id = auth.uid()) OR 
  (SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true
);

-- Update other RLS policies that referenced old user types
DROP POLICY IF EXISTS "Admins can delete currency rates" ON public.client_currencies;
CREATE POLICY "Admins can delete currency rates" ON public.client_currencies
FOR DELETE USING ((SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true);

DROP POLICY IF EXISTS "Admins can insert currency rates" ON public.client_currencies;
CREATE POLICY "Admins can insert currency rates" ON public.client_currencies
FOR INSERT WITH CHECK ((SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true);

DROP POLICY IF EXISTS "Admins can update currency rates" ON public.client_currencies;
CREATE POLICY "Admins can update currency rates" ON public.client_currencies
FOR UPDATE USING ((SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true);

-- Update companies policies
DROP POLICY IF EXISTS "Admins and clients can insert companies" ON public.companies;
CREATE POLICY "Admins and clients can insert companies" ON public.companies
FOR INSERT WITH CHECK (true); -- Anyone can create companies

DROP POLICY IF EXISTS "Admins can delete companies" ON public.companies;
CREATE POLICY "Admins can delete companies" ON public.companies
FOR DELETE USING ((SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true);

DROP POLICY IF EXISTS "Admins can update companies" ON public.companies;
CREATE POLICY "Admins can update companies" ON public.companies
FOR UPDATE USING ((SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true);

DROP POLICY IF EXISTS "Admins can view all companies and clients can view their own" ON public.companies;
CREATE POLICY "Admins can view all companies and clients can view their own" ON public.companies
FOR SELECT USING (
  (SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true OR
  (id IN (SELECT uc.company_id FROM user_companies uc WHERE uc.user_id = auth.uid() AND uc.is_active = true))
);

-- Update other policies similarly
DROP POLICY IF EXISTS "Admins can delete news" ON public.client_news;
CREATE POLICY "Admins can delete news" ON public.client_news
FOR DELETE USING ((SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true);

DROP POLICY IF EXISTS "Admins can insert news" ON public.client_news;
CREATE POLICY "Admins can insert news" ON public.client_news
FOR INSERT WITH CHECK ((SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true);

DROP POLICY IF EXISTS "Admins can update news" ON public.client_news;
CREATE POLICY "Admins can update news" ON public.client_news
FOR UPDATE USING ((SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true);

DROP POLICY IF EXISTS "Admins can manage company relationships" ON public.user_companies;
CREATE POLICY "Admins can manage company relationships" ON public.user_companies
FOR ALL USING ((SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true);

DROP POLICY IF EXISTS "Users can create their own company relationships" ON public.user_companies;
CREATE POLICY "Users can create their own company relationships" ON public.user_companies
FOR INSERT WITH CHECK (
  (user_id = auth.uid()) OR 
  (SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true
);

DROP POLICY IF EXISTS "Users can view their own company relationships" ON public.user_companies;
CREATE POLICY "Users can view their own company relationships" ON public.user_companies
FOR SELECT USING (
  (user_id = auth.uid()) OR 
  (SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true
);

DROP POLICY IF EXISTS "Non-recursive profiles access policy" ON public.profiles;
CREATE POLICY "Non-recursive profiles access policy" ON public.profiles
FOR SELECT USING (
  (user_id = auth.uid()) OR 
  (SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true OR
  ((active = true) AND (auth.uid() IS NOT NULL))
);

DROP POLICY IF EXISTS "Admins can delete tg_users" ON public.tg_users;
CREATE POLICY "Admins can delete tg_users" ON public.tg_users
FOR DELETE USING ((SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true);

DROP POLICY IF EXISTS "Admins can insert tg_users" ON public.tg_users;
CREATE POLICY "Admins can insert tg_users" ON public.tg_users
FOR INSERT WITH CHECK ((SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true);

DROP POLICY IF EXISTS "Admins can update tg_users" ON public.tg_users;
CREATE POLICY "Admins can update tg_users" ON public.tg_users
FOR UPDATE USING ((SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true);

DROP POLICY IF EXISTS "Admins can view all tg_users" ON public.tg_users;
CREATE POLICY "Admins can view all tg_users" ON public.tg_users
FOR SELECT USING ((SELECT is_developer FROM public.profiles WHERE user_id = auth.uid()) = true);