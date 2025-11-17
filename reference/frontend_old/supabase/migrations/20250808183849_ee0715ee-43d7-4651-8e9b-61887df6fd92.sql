-- Migration to fix existing users with company_id in profiles but missing user_companies entries
-- This will help fix the issue with "Тест Клиент" not showing company in the card

-- Create entries in user_companies for users who have company_id in profiles but no user_companies record
INSERT INTO public.user_companies (user_id, company_id, relationship_type, assigned_at, is_active)
SELECT 
  p.user_id,
  p.company_id,
  'owner'::user_company_relationship,
  p.created_at,
  true
FROM public.profiles p
WHERE p.company_id IS NOT NULL
  AND p.active = true
  AND NOT EXISTS (
    SELECT 1 
    FROM public.user_companies uc 
    WHERE uc.user_id = p.user_id 
      AND uc.company_id = p.company_id
      AND uc.is_active = true
  );

-- Add a comment explaining this migration
COMMENT ON TABLE public.user_companies IS 'This table manages user-company relationships. Migration applied to backfill existing profiles with company_id.';