
-- Readable view for messages with group/chat titles and concatenated sender name
CREATE OR REPLACE VIEW public.messages_with_context AS
SELECT
  m.id,
  m.created_at,
  m.updated_at,
  m.chat_id,
  c.name AS chat_title,
  c.chat_number,
  c.telegram_topic_id AS chat_telegram_topic_id,
  c.telegram_supergroup_id,
  t.title AS group_title,
  m.sender_id,
  TRIM(BOTH ' ' FROM COALESCE(p.first_name, '') || ' ' || COALESCE(p.last_name, '')) AS sender_name,
  m.message_type,
  m.content,
  m.file_type,
  m.file_name,
  m.file_url,
  m.file_size,
  m.voice_duration,
  m.telegram_message_id,
  m.telegram_user_id,
  m.telegram_topic_id AS message_telegram_topic_id,
  m.telegram_user_data,
  m.telegram_forward_data,
  m.sync_direction,
  m.interactive_data,
  m.metadata,
  m.is_deleted,
  m.is_edited
FROM public.messages m
LEFT JOIN public.chats c ON c.id = m.chat_id
LEFT JOIN public.telegram_supergroups t ON t.id = c.telegram_supergroup_id
LEFT JOIN public.profiles p ON p.user_id = m.sender_id;

COMMENT ON VIEW public.messages_with_context IS
'Readable messages view with group title, chat title, and concatenated sender name (first + last). RLS of base tables applies.';


-- Readable view for chats with the Telegram supergroup title
CREATE OR REPLACE VIEW public.chats_with_group AS
SELECT
  c.id,
  c.created_at,
  c.updated_at,
  c.is_active,
  c.chat_number,
  c.company_id,
  c.name AS chat_title,
  c.type,
  c.created_by,
  c.telegram_sync,
  c.telegram_supergroup_id,
  t.title AS group_title,
  c.telegram_topic_id,
  c.metadata
FROM public.chats c
LEFT JOIN public.telegram_supergroups t ON t.id = c.telegram_supergroup_id;

COMMENT ON VIEW public.chats_with_group IS
'Readable chats view with Telegram supergroup title. RLS of base tables applies.';

-- Allow querying these views from the client if needed (RLS on base tables still applies)
GRANT SELECT ON public.messages_with_context TO authenticated;
GRANT SELECT ON public.chats_with_group TO authenticated;
