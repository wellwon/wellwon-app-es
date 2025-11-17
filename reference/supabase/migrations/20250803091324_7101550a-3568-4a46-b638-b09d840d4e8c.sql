-- Fix foreign key constraints - they should reference profiles.id, not profiles.user_id
-- First drop the existing wrong constraints
ALTER TABLE public.messages DROP CONSTRAINT IF EXISTS messages_sender_id_fkey;
ALTER TABLE public.message_reads DROP CONSTRAINT IF EXISTS message_reads_user_id_fkey;
ALTER TABLE public.message_reads DROP CONSTRAINT IF EXISTS message_reads_message_id_fkey;

-- Add correct foreign key constraints
ALTER TABLE public.messages 
ADD CONSTRAINT messages_sender_id_fkey 
FOREIGN KEY (sender_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.message_reads 
ADD CONSTRAINT message_reads_user_id_fkey 
FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.message_reads 
ADD CONSTRAINT message_reads_message_id_fkey 
FOREIGN KEY (message_id) REFERENCES public.messages(id) ON DELETE CASCADE;

-- Add missing foreign keys for chat participants and chats
ALTER TABLE public.chat_participants 
ADD CONSTRAINT chat_participants_chat_id_fkey 
FOREIGN KEY (chat_id) REFERENCES public.chats(id) ON DELETE CASCADE;

ALTER TABLE public.chat_participants 
ADD CONSTRAINT chat_participants_user_id_fkey 
FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.chats 
ADD CONSTRAINT chats_created_by_fkey 
FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE CASCADE;