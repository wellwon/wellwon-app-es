-- Fix company creation issues: Clean up incorrect company_id assignments to admins

-- Remove company_id from admin profiles (they should only use user_companies)
UPDATE public.profiles 
SET company_id = NULL 
WHERE type IN ('ww_manager', 'ww_developer') 
  AND company_id IS NOT NULL;

-- Add constraint to prevent future company_id assignments to admins
ALTER TABLE public.profiles 
ADD CONSTRAINT check_admin_no_company_id 
CHECK (
  (type IN ('ww_manager', 'ww_developer') AND company_id IS NULL) 
  OR 
  (type NOT IN ('ww_manager', 'ww_developer'))
);