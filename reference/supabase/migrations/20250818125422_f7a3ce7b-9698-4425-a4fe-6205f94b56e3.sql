-- Обновляем названия топиков по имени из сохранённых сообщений Telegram
UPDATE public.chats AS c
SET
  name = (
    SELECT COALESCE(
      msg.metadata->'raw_message'->'reply_to_message'->'forum_topic_created'->>'name',
      msg.metadata->'raw_message'->'reply_to_message'->'forum_topic_edited'->>'name',
      msg.metadata->'raw_message'->'forum_topic_created'->>'name',
      msg.metadata->'raw_message'->'forum_topic_edited'->>'name'
    )
    FROM public.messages msg
    WHERE msg.chat_id = c.id
      AND msg.metadata->'raw_message' IS NOT NULL
      AND (
        msg.metadata->'raw_message'->'reply_to_message'->'forum_topic_created'->>'name' IS NOT NULL
        OR msg.metadata->'raw_message'->'reply_to_message'->'forum_topic_edited'->>'name' IS NOT NULL
        OR msg.metadata->'raw_message'->'forum_topic_created'->>'name' IS NOT NULL
        OR msg.metadata->'raw_message'->'forum_topic_edited'->>'name' IS NOT NULL
      )
    ORDER BY msg.created_at DESC
    LIMIT 1
  ),
  updated_at = now()
WHERE c.telegram_topic_id IS NOT NULL 
  AND c.telegram_topic_id != 1
  AND c.is_active = true
  AND c.name LIKE '% - Topic %'
  AND EXISTS (
    SELECT 1 
    FROM public.messages msg
    WHERE msg.chat_id = c.id
      AND msg.metadata->'raw_message' IS NOT NULL
      AND (
        msg.metadata->'raw_message'->'reply_to_message'->'forum_topic_created'->>'name' IS NOT NULL
        OR msg.metadata->'raw_message'->'reply_to_message'->'forum_topic_edited'->>'name' IS NOT NULL
        OR msg.metadata->'raw_message'->'forum_topic_created'->>'name' IS NOT NULL
        OR msg.metadata->'raw_message'->'forum_topic_edited'->>'name' IS NOT NULL
      )
  );