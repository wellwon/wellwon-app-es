-- Добавляем foreign key связи между messages и profiles
ALTER TABLE public.messages 
ADD CONSTRAINT messages_sender_id_fkey 
FOREIGN KEY (sender_id) REFERENCES public.profiles(user_id) ON DELETE CASCADE;

-- Также добавляем foreign key для message_reads
ALTER TABLE public.message_reads 
ADD CONSTRAINT message_reads_user_id_fkey 
FOREIGN KEY (user_id) REFERENCES public.profiles(user_id) ON DELETE CASCADE;

ALTER TABLE public.message_reads 
ADD CONSTRAINT message_reads_message_id_fkey 
FOREIGN KEY (message_id) REFERENCES public.messages(id) ON DELETE CASCADE;