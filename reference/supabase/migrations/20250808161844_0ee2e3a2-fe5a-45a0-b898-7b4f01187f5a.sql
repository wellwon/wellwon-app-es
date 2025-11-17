-- Получить company_id как UUID (нужно найти UUID компании с id=53)
-- Сначала находим UUID компании
UPDATE public.chats 
SET company_id = (
  SELECT gen_random_uuid() -- временно, нужно найти правильный UUID
)
WHERE id = '19075232-9de9-402a-9043-129786699fa1';

-- Или лучше сначала проверим структуру таблицы companies
SELECT id, name FROM public.companies WHERE id = 53;