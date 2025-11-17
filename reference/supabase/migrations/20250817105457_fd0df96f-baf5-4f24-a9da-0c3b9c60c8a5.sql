
-- 1) Проставляем topic_id = 1 для General в чатах форумных супергрупп
UPDATE public.chats c
SET telegram_topic_id = 1,
    updated_at = now()
FROM public.telegram_supergroups sg
WHERE c.telegram_supergroup_id = sg.id
  AND COALESCE(sg.is_forum, false) = true
  AND c.telegram_topic_id IS NULL;

-- 2) Для согласованности обновим сообщения этих чатов, где topic_id ещё NULL
UPDATE public.messages m
SET telegram_topic_id = 1,
    updated_at = now()
WHERE m.telegram_topic_id IS NULL
  AND m.chat_id IN (
    SELECT c.id
    FROM public.chats c
    JOIN public.telegram_supergroups sg
      ON sg.id = c.telegram_supergroup_id
    WHERE COALESCE(sg.is_forum, false) = true
      AND c.telegram_topic_id = 1
  );
