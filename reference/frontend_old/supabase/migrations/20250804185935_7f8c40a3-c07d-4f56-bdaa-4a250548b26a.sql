-- Function to automatically add admins as observers to new chats
CREATE OR REPLACE FUNCTION public.add_admins_to_new_chat()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
BEGIN
  -- Add all active admin users as observers to the new chat
  INSERT INTO public.chat_participants (chat_id, user_id, role)
  SELECT NEW.id, p.user_id, 'observer'
  FROM public.profiles p
  WHERE p.type IN ('ww_manager', 'ww_developer') 
  AND p.active = true
  AND p.user_id != NEW.created_by  -- Don't add creator again
  ON CONFLICT (chat_id, user_id) DO NOTHING;
  
  RETURN NEW;
END;
$function$;

-- Create trigger to add admins to new chats
DROP TRIGGER IF EXISTS on_chat_created_add_admins ON public.chats;
CREATE TRIGGER on_chat_created_add_admins
  AFTER INSERT ON public.chats
  FOR EACH ROW
  EXECUTE FUNCTION public.add_admins_to_new_chat();

-- Function to update last_read_at for chat participants
CREATE OR REPLACE FUNCTION public.update_participant_last_read()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
BEGIN
  -- Update last_read_at for the chat participant when they read a message
  UPDATE public.chat_participants 
  SET last_read_at = NEW.read_at
  WHERE chat_id = (
    SELECT chat_id 
    FROM public.messages 
    WHERE id = NEW.message_id
  ) 
  AND user_id = NEW.user_id;
  
  RETURN NEW;
END;
$function$;

-- Create trigger to update last_read_at when message is read
DROP TRIGGER IF EXISTS on_message_read_update_participant ON public.message_reads;
CREATE TRIGGER on_message_read_update_participant
  AFTER INSERT ON public.message_reads
  FOR EACH ROW
  EXECUTE FUNCTION public.update_participant_last_read();