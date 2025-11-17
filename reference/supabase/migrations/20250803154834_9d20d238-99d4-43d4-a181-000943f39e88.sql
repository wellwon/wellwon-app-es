-- Add foreign key constraints to support proper joins for sender profiles
-- This will enable the join syntax in our queries

-- Add foreign key constraint from messages.sender_id to profiles.user_id
-- We need to use user_id instead of id since that's the column that references auth.users
ALTER TABLE messages 
ADD CONSTRAINT messages_sender_id_fkey 
FOREIGN KEY (sender_id) REFERENCES profiles(user_id) ON DELETE CASCADE;