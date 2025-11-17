-- Migrate any remaining company data from profiles to user_companies
-- This ensures all company relationships are in user_companies before removing old columns

-- Insert any missing relationships from profiles to user_companies
INSERT INTO public.user_companies (user_id, company_id, relationship_type)
SELECT 
  p.user_id,
  p.company_id,
  'owner'::user_company_relationship  -- Use only valid enum value
FROM public.profiles p
WHERE p.company_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM public.user_companies uc 
    WHERE uc.user_id = p.user_id 
      AND uc.company_id = p.company_id 
      AND uc.is_active = true
  )
ON CONFLICT (user_id, company_id, relationship_type) DO NOTHING;

-- Clean up profiles.company_id for all users (not just admins)
UPDATE public.profiles 
SET company_id = NULL, role_in_company = NULL 
WHERE company_id IS NOT NULL;

-- Remove the constraint we added earlier
ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS check_admin_no_company_id;

-- Remove the obsolete columns entirely
ALTER TABLE public.profiles 
DROP COLUMN IF EXISTS company_id,
DROP COLUMN IF EXISTS role_in_company;