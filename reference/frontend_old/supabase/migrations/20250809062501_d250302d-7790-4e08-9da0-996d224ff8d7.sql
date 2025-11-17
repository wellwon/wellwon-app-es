-- Fix the auto-assign company trigger to work properly with chat participants
CREATE OR REPLACE FUNCTION public.auto_assign_company_to_chat()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
  client_user_id uuid;
  client_company_id bigint;
BEGIN
  -- Skip if company_id is already set
  IF NEW.company_id IS NOT NULL THEN
    RETURN NEW;
  END IF;
  
  -- Since participants are added after chat creation, we need to handle this differently
  -- For now, just return the new record and let the application handle company assignment
  RETURN NEW;
END;
$function$;

-- Create a function that can be called after participants are added
CREATE OR REPLACE FUNCTION public.assign_company_to_chat_after_participants(chat_uuid uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
  client_user_id uuid;
  client_company_id bigint;
BEGIN
  -- Find client in chat participants
  SELECT cp.user_id INTO client_user_id
  FROM public.chat_participants cp
  JOIN public.profiles p ON p.user_id = cp.user_id
  WHERE cp.chat_id = chat_uuid 
    AND p.type = 'client'
    AND cp.is_active = true
  LIMIT 1;
  
  -- If client found, get their company
  IF client_user_id IS NOT NULL THEN
    SELECT c.id INTO client_company_id
    FROM public.companies c
    JOIN public.user_companies uc ON uc.company_id = c.id
    WHERE uc.user_id = client_user_id 
      AND uc.is_active = true
      AND uc.relationship_type = 'owner'
    LIMIT 1;
    
    -- Set company_id if found and not already set
    IF client_company_id IS NOT NULL THEN
      UPDATE public.chats 
      SET company_id = client_company_id 
      WHERE id = chat_uuid AND company_id IS NULL;
    END IF;
  END IF;
END;
$function$;