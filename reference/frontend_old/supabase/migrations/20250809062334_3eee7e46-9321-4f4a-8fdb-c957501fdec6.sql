-- Add assigned_manager_id to companies table
ALTER TABLE public.companies 
ADD COLUMN assigned_manager_id uuid REFERENCES auth.users(id);

-- Update existing companies to set assigned_manager_id based on who created them
UPDATE public.companies 
SET assigned_manager_id = created_by_user_id 
WHERE created_by_user_id IS NOT NULL;

-- Add index for better performance
CREATE INDEX idx_companies_assigned_manager ON public.companies(assigned_manager_id);

-- Create function to get client from chat for company assignment
CREATE OR REPLACE FUNCTION public.get_client_from_chat(chat_uuid uuid)
RETURNS uuid
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  SELECT cp.user_id
  FROM public.chat_participants cp
  JOIN public.profiles p ON p.user_id = cp.user_id
  WHERE cp.chat_id = chat_uuid 
    AND p.type = 'client'
    AND cp.is_active = true
  LIMIT 1;
$function$;

-- Create function to auto-assign company to new chats
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
  
  -- Find client in chat participants
  SELECT cp.user_id INTO client_user_id
  FROM public.chat_participants cp
  JOIN public.profiles p ON p.user_id = cp.user_id
  WHERE cp.chat_id = NEW.id 
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
    
    -- Set company_id if found
    IF client_company_id IS NOT NULL THEN
      NEW.company_id = client_company_id;
    END IF;
  END IF;
  
  RETURN NEW;
END;
$function$;

-- Create trigger for auto-assigning company to chats
DROP TRIGGER IF EXISTS trigger_auto_assign_company_to_chat ON public.chats;
CREATE TRIGGER trigger_auto_assign_company_to_chat
  BEFORE INSERT ON public.chats
  FOR EACH ROW
  EXECUTE FUNCTION public.auto_assign_company_to_chat();