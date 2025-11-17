-- Add chat_number column to chats table
ALTER TABLE public.chats ADD COLUMN chat_number INTEGER;

-- Create a unique index to ensure no duplicate chat numbers
CREATE UNIQUE INDEX idx_chats_chat_number ON public.chats(chat_number);

-- Assign numbers to existing chats based on creation order
WITH numbered_chats AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY created_at ASC) as row_num
  FROM public.chats
  WHERE chat_number IS NULL
)
UPDATE public.chats 
SET chat_number = numbered_chats.row_num
FROM numbered_chats
WHERE chats.id = numbered_chats.id;

-- Create function to get next available chat number
CREATE OR REPLACE FUNCTION public.get_next_chat_number()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  next_number INTEGER;
BEGIN
  -- Get the highest existing chat number and add 1
  SELECT COALESCE(MAX(chat_number), 0) + 1 INTO next_number
  FROM public.chats;
  
  RETURN next_number;
END;
$$;

-- Update the auto_assign_company_to_chat function to assign chat numbers
CREATE OR REPLACE FUNCTION public.auto_assign_company_to_chat()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  client_user_id uuid;
  client_company_id bigint;
  new_chat_number INTEGER;
BEGIN
  -- Assign chat number if not already set
  IF NEW.chat_number IS NULL THEN
    SELECT public.get_next_chat_number() INTO new_chat_number;
    NEW.chat_number := new_chat_number;
  END IF;

  -- Skip if company_id is already set
  IF NEW.company_id IS NOT NULL THEN
    RETURN NEW;
  END IF;
  
  -- Since participants are added after chat creation, we need to handle this differently
  -- For now, just return the new record and let the application handle company assignment
  RETURN NEW;
END;
$$;