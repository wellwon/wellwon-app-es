-- Create function to get archived chats by supergroup
CREATE OR REPLACE FUNCTION public.get_user_chats_by_supergroup_archived(user_uuid uuid, supergroup_id_param bigint)
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
  select 
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
  from public.chats c
  join public.telegram_supergroups t on t.id = c.telegram_supergroup_id
  where c.is_active = false  -- Only archived chats
    and t.is_active = true   -- But supergroup must be active
    and c.telegram_supergroup_id = supergroup_id_param
  order by c.updated_at desc;
$function$;