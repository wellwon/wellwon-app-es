-- Remove the conflicting RLS policy that blocks updates
DROP POLICY IF EXISTS "Creators can update their templates" ON public.message_templates;

-- Update existing templates to have a valid created_by (use first available user or system)
UPDATE public.message_templates 
SET created_by = (
  SELECT id FROM auth.users 
  WHERE email LIKE '%@wellwon%' OR email LIKE '%developer%' 
  LIMIT 1
)
WHERE created_by IS NULL;

-- If no developer users exist, use any user
UPDATE public.message_templates 
SET created_by = (SELECT id FROM auth.users LIMIT 1)
WHERE created_by IS NULL;