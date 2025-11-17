-- Migration: Create user_companies entries for existing companies without them
-- This will help fix companies that were created before the user_companies system

-- First, let's create user_companies entries for companies where users are linked via chats
INSERT INTO public.user_companies (user_id, company_id, relationship_type, assigned_at)
SELECT DISTINCT 
  c.created_by,
  co.id,
  'owner'::user_company_relationship,
  co.created_at
FROM public.chats c
JOIN public.companies co ON c.company_id = co.id
WHERE c.created_by IS NOT NULL 
  AND co.id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM public.user_companies uc 
    WHERE uc.user_id = c.created_by 
    AND uc.company_id = co.id
  )
ON CONFLICT (user_id, company_id, relationship_type) DO NOTHING;

-- Update the created_by_user_id field where it's missing
UPDATE public.companies 
SET created_by_user_id = (
  SELECT DISTINCT c.created_by 
  FROM public.chats c 
  WHERE c.company_id = companies.id 
  LIMIT 1
)
WHERE created_by_user_id IS NULL;