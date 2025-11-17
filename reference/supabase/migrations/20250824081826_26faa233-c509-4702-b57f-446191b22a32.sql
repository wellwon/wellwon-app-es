-- Enhanced reply integrity and cleanup script for WellWon chat system
-- This migration adds constraints, indexes and cleanup for reply_to_id integrity

-- 1. Add index for better reply message performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_reply_to_id 
ON public.messages (reply_to_id) 
WHERE reply_to_id IS NOT NULL;

-- 2. Add index for chat_id + created_at for better pagination
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_chat_created 
ON public.messages (chat_id, created_at DESC);

-- 3. Create function to validate reply_to_id integrity
CREATE OR REPLACE FUNCTION public.validate_reply_to_id()
RETURNS TRIGGER AS $$
BEGIN
  -- Check if reply_to_id exists and is in the same chat
  IF NEW.reply_to_id IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM public.messages 
      WHERE id = NEW.reply_to_id 
      AND chat_id = NEW.chat_id 
      AND (is_deleted IS FALSE OR is_deleted IS NULL)
    ) THEN
      -- Log the invalid reference but don't block the insert
      INSERT INTO public.system_logs (level, message, metadata, created_at)
      VALUES (
        'WARNING',
        'Invalid reply_to_id reference detected',
        jsonb_build_object(
          'message_id', NEW.id,
          'chat_id', NEW.chat_id,
          'reply_to_id', NEW.reply_to_id,
          'sender_id', NEW.sender_id
        ),
        NOW()
      ) ON CONFLICT DO NOTHING;
      
      -- Clear invalid reply_to_id to prevent broken references
      NEW.reply_to_id := NULL;
    END IF;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 4. Create system_logs table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.system_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  level text NOT NULL DEFAULT 'INFO',
  message text NOT NULL,
  metadata jsonb DEFAULT '{}',
  created_at timestamp with time zone DEFAULT now()
);

-- Enable RLS on system_logs
ALTER TABLE public.system_logs ENABLE ROW LEVEL SECURITY;

-- Only developers can view system logs
CREATE POLICY "Developers can view system logs"
ON public.system_logs
FOR SELECT
USING (
  SELECT COALESCE(profiles.developer, false)
  FROM profiles 
  WHERE profiles.user_id = auth.uid()
);

-- 5. Create trigger for reply validation
DROP TRIGGER IF EXISTS validate_reply_to_id_trigger ON public.messages;
CREATE TRIGGER validate_reply_to_id_trigger
  BEFORE INSERT OR UPDATE ON public.messages
  FOR EACH ROW
  EXECUTE FUNCTION public.validate_reply_to_id();

-- 6. ONE-TIME CLEANUP: Remove orphaned reply_to_id references
-- This is a safe operation that only removes invalid references, not messages themselves
WITH orphaned_replies AS (
  SELECT m1.id, m1.chat_id, m1.reply_to_id
  FROM public.messages m1
  WHERE m1.reply_to_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM public.messages m2 
    WHERE m2.id = m1.reply_to_id 
    AND m2.chat_id = m1.chat_id
    AND (m2.is_deleted IS FALSE OR m2.is_deleted IS NULL)
  )
),
cleanup_log AS (
  INSERT INTO public.system_logs (level, message, metadata)
  SELECT 
    'INFO',
    'Cleaned orphaned reply_to_id references',
    jsonb_build_object(
      'total_cleaned', COUNT(*),
      'affected_chats', array_agg(DISTINCT chat_id),
      'cleanup_timestamp', NOW()
    )
  FROM orphaned_replies
  RETURNING id
)
UPDATE public.messages 
SET 
  reply_to_id = NULL,
  metadata = COALESCE(metadata, '{}') || jsonb_build_object('reply_cleaned_at', NOW()::text)
WHERE id IN (SELECT id FROM orphaned_replies);

-- 7. Create function for periodic cleanup (can be called manually)
CREATE OR REPLACE FUNCTION public.cleanup_orphaned_replies()
RETURNS jsonb AS $$
DECLARE
  cleanup_count integer;
  result jsonb;
BEGIN
  WITH orphaned_replies AS (
    SELECT m1.id
    FROM public.messages m1
    WHERE m1.reply_to_id IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM public.messages m2 
      WHERE m2.id = m1.reply_to_id 
      AND m2.chat_id = m1.chat_id
      AND (m2.is_deleted IS FALSE OR m2.is_deleted IS NULL)
    )
  ),
  cleanup_update AS (
    UPDATE public.messages 
    SET reply_to_id = NULL
    WHERE id IN (SELECT id FROM orphaned_replies)
    RETURNING id
  )
  SELECT COUNT(*) INTO cleanup_count FROM cleanup_update;
  
  result := jsonb_build_object(
    'cleaned_count', cleanup_count,
    'timestamp', NOW()
  );
  
  -- Log the cleanup
  INSERT INTO public.system_logs (level, message, metadata)
  VALUES ('INFO', 'Manual cleanup of orphaned replies completed', result);
  
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 8. Grant appropriate permissions
GRANT EXECUTE ON FUNCTION public.cleanup_orphaned_replies() TO authenticated;