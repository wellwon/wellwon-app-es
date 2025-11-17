-- Добавляем foreign key для связи messages.sender_id с profiles.user_id
ALTER TABLE public.messages 
ADD CONSTRAINT fk_messages_sender_profile 
FOREIGN KEY (sender_id) REFERENCES auth.users(id) ON DELETE CASCADE;

-- Добавляем индекс для улучшения производительности
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON public.messages(sender_id);