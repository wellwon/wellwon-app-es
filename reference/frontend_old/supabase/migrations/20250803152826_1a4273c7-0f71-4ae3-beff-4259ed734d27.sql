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

-- Add a unique constraint to prevent duplicate participants
ALTER TABLE public.chat_participants 
ADD CONSTRAINT IF NOT EXISTS unique_chat_user 
UNIQUE (chat_id, user_id);

-- Add debugging policy to understand RLS issues
CREATE POLICY "Debug: Allow chat creation for authenticated users" 
ON public.chats 
FOR INSERT 
WITH CHECK (
  auth.uid() IS NOT NULL AND 
  auth.uid() = created_by
);