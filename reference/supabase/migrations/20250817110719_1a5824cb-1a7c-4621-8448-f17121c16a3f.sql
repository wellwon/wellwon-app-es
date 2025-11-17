-- Backfill General chat names with company names where applicable
UPDATE public.chats 
SET 
  name = COALESCE(companies.name, chats.name),
  metadata = jsonb_set(
    COALESCE(chats.metadata, '{}'),
    '{is_general}', 
    'true'
  ),
  updated_at = now()
FROM public.telegram_supergroups tsg
LEFT JOIN public.companies ON companies.id = tsg.company_id
WHERE chats.telegram_supergroup_id = tsg.id
  AND chats.telegram_topic_id = 1
  AND tsg.is_forum = true
  AND chats.is_active = true;