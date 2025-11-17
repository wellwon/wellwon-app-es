-- Fix client profile to link to company ID 53
UPDATE public.profiles 
SET company_id = 53 
WHERE user_id = 'f6a199cb-0341-48e2-9db4-e42edab52e78';