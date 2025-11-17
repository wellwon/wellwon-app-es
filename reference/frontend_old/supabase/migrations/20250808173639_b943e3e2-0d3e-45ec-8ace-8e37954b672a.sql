-- Create relationship types enum
CREATE TYPE user_company_relationship AS ENUM ('owner', 'manager', 'assigned_admin');

-- Create user_companies table for many-to-many relationships
CREATE TABLE public.user_companies (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  company_id BIGINT NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  relationship_type user_company_relationship NOT NULL DEFAULT 'owner',
  assigned_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  
  -- Ensure unique combination of user, company and relationship type
  UNIQUE(user_id, company_id, relationship_type)
);

-- Enable RLS
ALTER TABLE public.user_companies ENABLE ROW LEVEL SECURITY;

-- RLS Policies for user_companies
CREATE POLICY "Users can view their own company relationships" 
ON public.user_companies 
FOR SELECT 
USING (user_id = auth.uid() OR get_current_user_type() = ANY(ARRAY['ww_developer'::text, 'ww_manager'::text]));

CREATE POLICY "Admins can manage company relationships" 
ON public.user_companies 
FOR ALL 
USING (get_current_user_type() = ANY(ARRAY['ww_developer'::text, 'ww_manager'::text]));

CREATE POLICY "Users can create their own company relationships" 
ON public.user_companies 
FOR INSERT 
WITH CHECK (user_id = auth.uid() OR get_current_user_type() = ANY(ARRAY['ww_developer'::text, 'ww_manager'::text]));

-- Add trigger for updated_at
CREATE TRIGGER update_user_companies_updated_at
BEFORE UPDATE ON public.user_companies
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- Create function to get user companies
CREATE OR REPLACE FUNCTION public.get_user_companies(
  target_user_id UUID,
  filter_relationship_type user_company_relationship DEFAULT NULL
)
RETURNS TABLE(
  id BIGINT,
  name TEXT,
  company_type TEXT,
  status company_status,
  relationship_type user_company_relationship,
  assigned_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path = 'public'
AS $$
  SELECT 
    c.id,
    c.name,
    c.company_type,
    c.status,
    uc.relationship_type,
    uc.assigned_at
  FROM public.companies c
  JOIN public.user_companies uc ON uc.company_id = c.id
  WHERE uc.user_id = target_user_id
    AND uc.is_active = true
    AND (filter_relationship_type IS NULL OR uc.relationship_type = filter_relationship_type)
  ORDER BY uc.assigned_at DESC;
$$;

-- Create function to get company users
CREATE OR REPLACE FUNCTION public.get_company_users(
  target_company_id BIGINT,
  filter_relationship_type user_company_relationship DEFAULT NULL
)
RETURNS TABLE(
  user_id UUID,
  first_name TEXT,
  last_name TEXT,
  avatar_url TEXT,
  type user_type,
  relationship_type user_company_relationship,
  assigned_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path = 'public'
AS $$
  SELECT 
    p.user_id,
    p.first_name,
    p.last_name,
    p.avatar_url,
    p.type,
    uc.relationship_type,
    uc.assigned_at
  FROM public.profiles p
  JOIN public.user_companies uc ON uc.user_id = p.user_id
  WHERE uc.company_id = target_company_id
    AND uc.is_active = true
    AND p.active = true
    AND (filter_relationship_type IS NULL OR uc.relationship_type = filter_relationship_type)
  ORDER BY uc.assigned_at ASC;
$$;

-- Update get_client_company_from_chat to use the chat's company_id directly
CREATE OR REPLACE FUNCTION public.get_client_company_from_chat(chat_uuid uuid)
RETURNS TABLE(
  id bigint, 
  name text, 
  company_type text, 
  balance numeric, 
  status company_status, 
  orders_count integer, 
  turnover numeric, 
  rating numeric, 
  successful_deliveries integer, 
  created_at timestamp with time zone, 
  updated_at timestamp with time zone, 
  client_user_id uuid
)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path = 'public'
AS $$
  SELECT 
    c.id, 
    c.name, 
    c.company_type, 
    c.balance, 
    c.status,
    c.orders_count,
    c.turnover,
    c.rating,
    c.successful_deliveries,
    c.created_at, 
    c.updated_at,
    uc.user_id as client_user_id
  FROM public.companies c
  JOIN public.chats ch ON ch.company_id = c.id
  LEFT JOIN public.user_companies uc ON uc.company_id = c.id AND uc.relationship_type = 'owner' AND uc.is_active = true
  WHERE ch.id = chat_uuid
  LIMIT 1;
$$;

-- Function to assign admin to company
CREATE OR REPLACE FUNCTION public.assign_admin_to_company(
  admin_user_id UUID,
  target_company_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = 'public'
AS $$
BEGIN
  -- Check if user is admin
  IF NOT EXISTS (
    SELECT 1 FROM public.profiles 
    WHERE user_id = admin_user_id 
    AND type IN ('ww_manager', 'ww_developer')
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
$$;

-- Migrate existing company_id relationships to new table
INSERT INTO public.user_companies (user_id, company_id, relationship_type)
SELECT 
  user_id, 
  company_id, 
  CASE 
    WHEN type = 'client' THEN 'owner'::user_company_relationship
    ELSE 'assigned_admin'::user_company_relationship
  END
FROM public.profiles 
WHERE company_id IS NOT NULL
ON CONFLICT (user_id, company_id, relationship_type) DO NOTHING;

-- Clear company_id from profiles (but don't drop the column yet for safety)
UPDATE public.profiles SET company_id = NULL;