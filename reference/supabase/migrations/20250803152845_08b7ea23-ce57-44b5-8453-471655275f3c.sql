-- Remove duplicate trigger first
DROP TRIGGER IF EXISTS add_creator_as_participant ON public.chats;

-- Update the function to handle potential duplicates and improve error handling
CREATE OR REPLACE FUNCTION public.add_chat_creator_as_participant()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
BEGIN
  -- Only insert if the participant doesn't already exist
  INSERT INTO public.chat_participants (chat_id, user_id, role)
  VALUES (NEW.id, NEW.created_by, 'admin')
  ON CONFLICT (chat_id, user_id) DO NOTHING;
  
  RETURN NEW;
END;
$function$;

-- Add a unique constraint to prevent duplicate participants (PostgreSQL 9.5+ syntax)
DO $$ 
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint 
    WHERE conname = 'unique_chat_user'
  ) THEN
    ALTER TABLE public.chat_participants 
    ADD CONSTRAINT unique_chat_user UNIQUE (chat_id, user_id);
  END IF;
END $$;