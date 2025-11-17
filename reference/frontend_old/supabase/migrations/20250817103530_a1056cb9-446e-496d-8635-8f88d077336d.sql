-- Create function to get user chats by supergroup
CREATE OR REPLACE FUNCTION public.get_user_chats_by_supergroup(user_uuid uuid, supergroup_id_param bigint)
RETURNS TABLE(
  id uuid, 
  name text, 
  type text, 
  created_by uuid, 
  created_at timestamp with time zone, 
  updated_at timestamp with time zone, 
  is_active boolean, 
  metadata jsonb, 
  company_id bigint, 
  chat_number integer, 
  telegram_supergroup_id bigint, 
  telegram_topic_id integer, 
  telegram_sync boolean
)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  SELECT 
    c.id, 
    c.name, 
    c.type, 
    c.created_by, 
    c.created_at, 
    c.updated_at, 
    c.is_active, 
    c.metadata, 
    c.company_id, 
    c.chat_number,
    c.telegram_supergroup_id,
    c.telegram_topic_id,
    c.telegram_sync
  FROM public.chats c
  WHERE c.is_active = true
    AND c.telegram_supergroup_id = supergroup_id_param
    AND (
      -- Developer users see all chats in the supergroup
      (SELECT COALESCE(developer, false) FROM public.profiles WHERE user_id = user_uuid) = true
      OR 
      -- Regular users see chats they participate in within the supergroup
      c.id IN (
        SELECT cp.chat_id 
        FROM public.chat_participants cp 
        WHERE cp.user_id = user_uuid AND cp.is_active = true
      )
    )
  ORDER BY c.updated_at DESC;
$function$;