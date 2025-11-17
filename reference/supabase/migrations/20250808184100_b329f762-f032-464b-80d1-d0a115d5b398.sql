-- Remove company_id from admin/manager profiles who shouldn't have companies assigned
-- Admins should not have company_id in their profiles, only clients should

UPDATE public.profiles 
SET company_id = NULL, 
    role_in_company = NULL
WHERE type IN ('ww_manager', 'ww_developer')
  AND company_id IS NOT NULL;

-- Also remove corresponding user_companies entries for admins where relationship_type is 'owner'
-- Admins can have 'assigned_admin' relationship but not 'owner'
DELETE FROM public.user_companies 
WHERE user_id IN (
  SELECT user_id 
  FROM public.profiles 
  WHERE type IN ('ww_manager', 'ww_developer')
) 
AND relationship_type = 'owner';

-- Add comment explaining the cleanup
COMMENT ON COLUMN public.profiles.company_id IS 'Company ID should only be set for client users, not for admins/managers';