-- Link "Тест Клиент" to company 58 (from their active chat)
INSERT INTO public.user_companies (user_id, company_id, relationship_type, is_active)
SELECT 
  'dd98e4bd-7898-4b99-8758-43cfde66efb5'::uuid as user_id,
  58 as company_id,
  'owner' as relationship_type,
  true as is_active
WHERE NOT EXISTS (
  SELECT 1 FROM public.user_companies 
  WHERE user_id = 'dd98e4bd-7898-4b99-8758-43cfde66efb5'::uuid 
  AND company_id = 58 
  AND is_active = true
);

-- Also update profile for backward compatibility
UPDATE public.profiles 
SET company_id = 58 
WHERE user_id = 'dd98e4bd-7898-4b99-8758-43cfde66efb5'::uuid 
  AND type = 'client' 
  AND company_id IS NULL;