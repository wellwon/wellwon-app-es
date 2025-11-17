-- Step 1: Fix the message_type constraint to include 'other'
ALTER TABLE public.messages DROP CONSTRAINT IF EXISTS messages_message_type_check;

-- Add new constraint that includes 'other' type
ALTER TABLE public.messages ADD CONSTRAINT messages_message_type_check 
CHECK (message_type IN ('text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker', 'other', 'system'));

-- Step 2: Add timeout prevention logic - create a function to check if supergroup should be ignored
CREATE OR REPLACE FUNCTION public.should_ignore_telegram_supergroup(supergroup_id bigint)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  -- Check if this is a test/deleted supergroup that should be ignored
  -- Add IDs of supergroups that shouldn't be auto-recreated
  RETURN supergroup_id IN (
    -1002693383546, -1002618114488, -1002554121378, 
    -1002848008437, -1002245678432, -1002779635244, 
    -1002598871574, -1002880892698
  );
END;
$$;