-- Allow clients to create companies temporarily
DROP POLICY IF EXISTS "Admins can insert companies" ON public.companies;

CREATE POLICY "Admins and clients can insert companies" 
ON public.companies 
FOR INSERT 
TO authenticated
WITH CHECK (
  get_current_user_type() = ANY (ARRAY['ww_developer'::text, 'ww_manager'::text, 'client'::text])
);

-- Also allow clients to view companies they own
DROP POLICY IF EXISTS "Admins can view all companies" ON public.companies;

CREATE POLICY "Admins can view all companies and clients can view their own" 
ON public.companies 
FOR SELECT 
TO authenticated
USING (
  get_current_user_type() = ANY (ARRAY['ww_developer'::text, 'ww_manager'::text]) 
  OR 
  (
    get_current_user_type() = 'client'::text 
    AND id IN (
      SELECT uc.company_id 
      FROM user_companies uc 
      WHERE uc.user_id = auth.uid() 
      AND uc.is_active = true
    )
  )
);