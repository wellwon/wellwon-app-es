-- Сделать поле created_by nullable для поддержки Telegram чатов
ALTER TABLE public.chats 
ALTER COLUMN created_by DROP NOT NULL;