-- Create trigger to automatically add chat creator as participant
CREATE TRIGGER on_chat_created
  AFTER INSERT ON public.chats
  FOR EACH ROW
  EXECUTE FUNCTION public.add_chat_creator_as_participant();