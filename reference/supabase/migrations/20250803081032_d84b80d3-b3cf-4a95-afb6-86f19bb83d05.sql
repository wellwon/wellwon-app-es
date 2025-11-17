-- Исправление предупреждений безопасности: Function Search Path Mutable

-- Обновляем функцию add_chat_creator_as_participant
CREATE OR REPLACE FUNCTION add_chat_creator_as_participant()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.chat_participants (chat_id, user_id, role)
  VALUES (NEW.id, NEW.created_by, 'admin');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Обновляем функцию cleanup_expired_typing_indicators
CREATE OR REPLACE FUNCTION cleanup_expired_typing_indicators()
RETURNS void AS $$
BEGIN
  DELETE FROM public.typing_indicators 
  WHERE expires_at < now();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;