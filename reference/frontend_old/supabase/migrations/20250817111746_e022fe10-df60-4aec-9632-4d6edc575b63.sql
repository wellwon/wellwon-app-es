
-- Обновляем названия General-чатов (topic_id = 1) по имени привязанной компании
UPDATE public.chats AS c
SET
  name = comp.name,
  metadata = jsonb_set(COALESCE(c.metadata, '{}'::jsonb), '{is_general}', 'true', true),
  updated_at = now()
FROM public.telegram_supergroups AS tsg
JOIN public.companies AS comp
  ON comp.id = tsg.company_id
WHERE c.telegram_supergroup_id = tsg.id
  AND tsg.is_forum = true
  AND c.telegram_topic_id = 1
  AND c.is_active = true
  AND c.name IS DISTINCT FROM comp.name;
