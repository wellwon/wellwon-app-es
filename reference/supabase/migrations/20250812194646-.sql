-- Удаляем существующее CHECK ограничение для типа чата
ALTER TABLE public.chats DROP CONSTRAINT IF EXISTS chats_type_check;

-- Создаем новое CHECK ограничение с добавленным типом 'telegram_group'
ALTER TABLE public.chats ADD CONSTRAINT chats_type_check 
CHECK (type IN ('direct', 'group', 'channel', 'telegram_group'));