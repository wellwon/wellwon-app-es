-- Fix database functions to work with new developer boolean column

-- Update is_developer function to use developer column
CREATE OR REPLACE FUNCTION public.is_developer()
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  SELECT COALESCE(developer, false)
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
    WHEN COALESCE(developer, false) = true THEN 'developer'
    ELSE 'user'
  END
  FROM public.profiles 
  WHERE user_id = auth.uid();
$function$;

-- Update all RLS policies to use simplified logic

-- Chat participants policies
DROP POLICY IF EXISTS "Simple chat participants view" ON public.chat_participants;
CREATE POLICY "Simple chat participants view" 
ON public.chat_participants 
FOR SELECT 
USING (
  user_id = auth.uid() OR 
  (SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid())
);

-- Chats policies  
DROP POLICY IF EXISTS "Simple chats view" ON public.chats;
CREATE POLICY "Simple chats view" 
ON public.chats 
FOR SELECT 
USING (
  created_by = auth.uid() OR 
  (SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid())
);

-- Companies policies
DROP POLICY IF EXISTS "Admins and clients can insert companies" ON public.companies;
CREATE POLICY "Users can insert companies" 
ON public.companies 
FOR INSERT 
WITH CHECK (true);

DROP POLICY IF EXISTS "Admins can delete companies" ON public.companies;
CREATE POLICY "Developers can delete companies" 
ON public.companies 
FOR DELETE 
USING ((SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "Admins can update companies" ON public.companies;
CREATE POLICY "Developers can update companies" 
ON public.companies 
FOR UPDATE 
USING ((SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "Admins can view all companies and clients can view their own" ON public.companies;
CREATE POLICY "Users can view companies" 
ON public.companies 
FOR SELECT 
USING (
  (SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()) OR
  (id IN (SELECT uc.company_id FROM user_companies uc WHERE uc.user_id = auth.uid() AND uc.is_active = true))
);

-- Client currencies policies
DROP POLICY IF EXISTS "Admins can delete currency rates" ON public.client_currencies;
CREATE POLICY "Developers can delete currency rates" 
ON public.client_currencies 
FOR DELETE 
USING ((SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "Admins can insert currency rates" ON public.client_currencies;
CREATE POLICY "Developers can insert currency rates" 
ON public.client_currencies 
FOR INSERT 
WITH CHECK ((SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "Admins can update currency rates" ON public.client_currencies;
CREATE POLICY "Developers can update currency rates" 
ON public.client_currencies 
FOR UPDATE 
USING ((SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()));

-- Client news policies
DROP POLICY IF EXISTS "Admins can delete news" ON public.client_news;
CREATE POLICY "Developers can delete news" 
ON public.client_news 
FOR DELETE 
USING ((SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "Admins can insert news" ON public.client_news;
CREATE POLICY "Developers can insert news" 
ON public.client_news 
FOR INSERT 
WITH CHECK ((SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "Admins can update news" ON public.client_news;
CREATE POLICY "Developers can update news" 
ON public.client_news 
FOR UPDATE 
USING ((SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()));

-- User companies policies
DROP POLICY IF EXISTS "Admins can manage company relationships" ON public.user_companies;
CREATE POLICY "Developers can manage company relationships" 
ON public.user_companies 
FOR ALL 
USING ((SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "Users can create their own company relationships" ON public.user_companies;
CREATE POLICY "Users can create their own company relationships" 
ON public.user_companies 
FOR INSERT 
WITH CHECK (
  user_id = auth.uid() OR 
  (SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid())
);

DROP POLICY IF EXISTS "Users can view their own company relationships" ON public.user_companies;
CREATE POLICY "Users can view their own company relationships" 
ON public.user_companies 
FOR SELECT 
USING (
  user_id = auth.uid() OR 
  (SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid())
);

-- Profiles policies
DROP POLICY IF EXISTS "Non-recursive profiles access policy" ON public.profiles;
CREATE POLICY "Profiles access policy" 
ON public.profiles 
FOR SELECT 
USING (
  user_id = auth.uid() OR 
  (SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()) OR
  (active = true AND auth.uid() IS NOT NULL)
);

-- TG users policies
DROP POLICY IF EXISTS "Admins can delete tg_users" ON public.tg_users;
CREATE POLICY "Developers can delete tg_users" 
ON public.tg_users 
FOR DELETE 
USING ((SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "Admins can insert tg_users" ON public.tg_users;
CREATE POLICY "Developers can insert tg_users" 
ON public.tg_users 
FOR INSERT 
WITH CHECK ((SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "Admins can update tg_users" ON public.tg_users;
CREATE POLICY "Developers can update tg_users" 
ON public.tg_users 
FOR UPDATE 
USING ((SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "Admins can view all tg_users" ON public.tg_users;
CREATE POLICY "Developers can view all tg_users" 
ON public.tg_users 
FOR SELECT 
USING ((SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = auth.uid()));

-- Update database functions that reference old types
CREATE OR REPLACE FUNCTION public.assign_admin_to_company(admin_user_id uuid, target_company_id bigint)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  -- Check if user is developer
  IF NOT EXISTS (
    SELECT 1 FROM public.profiles 
    WHERE user_id = admin_user_id 
    AND COALESCE(developer, false) = true
    AND active = true
  ) THEN
    RETURN FALSE;
  END IF;

  -- Insert or update assignment
  INSERT INTO public.user_companies (user_id, company_id, relationship_type)
  VALUES (admin_user_id, target_company_id, 'assigned_admin')
  ON CONFLICT (user_id, company_id, relationship_type) 
  DO UPDATE SET 
    is_active = true,
    updated_at = now();
    
  RETURN TRUE;
END;
$function$;

-- Update functions that add admins to chats
CREATE OR REPLACE FUNCTION public.add_admins_to_new_chat()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  -- Add all active developer users as observers to the new chat
  INSERT INTO public.chat_participants (chat_id, user_id, role)
  SELECT NEW.id, p.user_id, 'observer'
  FROM public.profiles p
  WHERE COALESCE(p.developer, false) = true 
  AND p.active = true
  AND p.user_id != NEW.created_by  -- Don't add creator again
  ON CONFLICT (chat_id, user_id) DO NOTHING;
  
  RETURN NEW;
END;
$function$;

-- Update get_user_chats_by_company function
CREATE OR REPLACE FUNCTION public.get_user_chats_by_company(user_uuid uuid, company_uuid bigint DEFAULT NULL::bigint)
 RETURNS TABLE(id uuid, name text, type text, created_by uuid, created_at timestamp with time zone, updated_at timestamp with time zone, is_active boolean, metadata jsonb, company_id bigint, chat_number integer)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  -- For developer users, return all chats when no company filter is specified
  -- For regular users, only return chats that match the specified company
  SELECT c.id, c.name, c.type, c.created_by, c.created_at, c.updated_at, c.is_active, c.metadata, c.company_id, c.chat_number
  FROM public.chats c
  WHERE c.is_active = true
    AND (
      -- Developer users see all chats when no company filter is provided
      (
        (SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = user_uuid) = true
        AND (
          company_uuid IS NULL -- Show all chats for developers when no company specified
          OR c.company_id = company_uuid -- Or specific company chats when specified
        )
      )
      OR 
      -- Regular users see chats they participate in, filtered by company
      (
        c.id IN (
          SELECT cp.chat_id 
          FROM public.chat_participants cp 
          WHERE cp.user_id = user_uuid AND cp.is_active = true
        )
        AND (
          -- When company filter is provided, only show chats for that specific company
          (company_uuid IS NOT NULL AND c.company_id = company_uuid)
          OR 
          -- When no company filter, only show unassigned chats (company_id IS NULL)
          (company_uuid IS NULL AND c.company_id IS NULL)
        )
      )
    )
  ORDER BY c.updated_at DESC;
$function$;