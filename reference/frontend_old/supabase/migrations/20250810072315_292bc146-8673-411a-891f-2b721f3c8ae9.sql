-- Add functions to manage chat-company relationships

-- Function to get chats filtered by company for clients
CREATE OR REPLACE FUNCTION public.get_user_chats_by_company(user_uuid uuid, company_uuid bigint DEFAULT NULL)
RETURNS TABLE(
  id uuid,
  name text,
  type text,
  created_by uuid,
  created_at timestamp with time zone,
  updated_at timestamp with time zone,
  is_active boolean,
  metadata jsonb,
  company_id bigint
)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $$
  -- For admin users, return all chats regardless of company filter
  SELECT c.id, c.name, c.type, c.created_by, c.created_at, c.updated_at, c.is_active, c.metadata, c.company_id
  FROM public.chats c
  WHERE c.is_active = true
    AND (
      -- Admin users see all chats
      (SELECT type FROM public.profiles WHERE user_id = user_uuid) IN ('ww_manager', 'ww_developer')
      OR 
      -- Regular users see chats they participate in
      (
        c.id IN (
          SELECT cp.chat_id 
          FROM public.chat_participants cp 
          WHERE cp.user_id = user_uuid AND cp.is_active = true
        )
        AND (
          -- If company filter is provided, filter by company
          company_uuid IS NULL 
          OR c.company_id = company_uuid 
          OR c.company_id IS NULL -- Include unassigned chats for new users
        )
      )
    )
  ORDER BY c.updated_at DESC;
$$;

-- Function to bind all existing client chats to their first company
CREATE OR REPLACE FUNCTION public.bind_client_chats_to_first_company(client_user_id uuid, company_uuid bigint)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
BEGIN
  -- Update all unassigned chats where this client is a participant
  UPDATE public.chats 
  SET company_id = company_uuid 
  WHERE company_id IS NULL 
    AND id IN (
      SELECT DISTINCT cp.chat_id 
      FROM public.chat_participants cp 
      WHERE cp.user_id = client_user_id 
        AND cp.is_active = true
    );
END;
$$;

-- Function to create chat with company assignment
CREATE OR REPLACE FUNCTION public.create_chat_with_company(
  chat_name text,
  chat_type text,
  creator_id uuid,
  company_uuid bigint DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  new_chat_id uuid;
  user_company_id bigint;
BEGIN
  -- If no company specified, try to get user's selected company
  IF company_uuid IS NULL THEN
    SELECT c.id INTO user_company_id
    FROM public.companies c
    JOIN public.user_companies uc ON uc.company_id = c.id
    WHERE uc.user_id = creator_id 
      AND uc.is_active = true
      AND uc.relationship_type = 'owner'
    ORDER BY uc.assigned_at DESC
    LIMIT 1;
    
    company_uuid := user_company_id;
  END IF;

  -- Create the chat
  INSERT INTO public.chats (name, type, created_by, company_id)
  VALUES (chat_name, chat_type, creator_id, company_uuid)
  RETURNING id INTO new_chat_id;

  -- Add creator as participant
  INSERT INTO public.chat_participants (chat_id, user_id, role)
  VALUES (new_chat_id, creator_id, 'admin')
  ON CONFLICT (chat_id, user_id) DO NOTHING;

  RETURN new_chat_id;
END;
$$;