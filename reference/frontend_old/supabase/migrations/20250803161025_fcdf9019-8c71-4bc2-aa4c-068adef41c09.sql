-- Добавляем внешний ключ для связи messages.sender_id -> profiles.user_id
ALTER TABLE public.messages 
ADD CONSTRAINT messages_sender_id_fkey 
FOREIGN KEY (sender_id) 
REFERENCES auth.users(id) ON DELETE CASCADE;

-- Добавляем индекс для улучшения производительности
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON public.messages(sender_id);