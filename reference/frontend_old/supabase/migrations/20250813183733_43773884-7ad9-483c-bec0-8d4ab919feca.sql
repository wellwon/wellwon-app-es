-- Clean up duplicate telegram supergroups
-- Find and merge duplicates where one ID is the positive version and the other is -100 prefixed

-- Function to normalize telegram supergroup ID
CREATE OR REPLACE FUNCTION normalize_telegram_supergroup_id(input_id bigint)
RETURNS bigint
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
  -- If positive ID, add -100 prefix by making it negative and subtracting 1000000000000
  IF input_id > 0 THEN
    RETURN input_id * -1 - 1000000000000;
  END IF;
  
  -- If already negative, return as is
  RETURN input_id;
END;
$$;

-- Create temporary table to identify duplicates
CREATE TEMP TABLE supergroup_duplicates AS
SELECT 
  s1.id as keep_id,
  s2.id as remove_id,
  COALESCE(s1.company_id, s2.company_id) as final_company_id,
  COALESCE(s1.title, s2.title) as final_title,
  COALESCE(s1.description, s2.description) as final_description,
  COALESCE(s1.username, s2.username) as final_username,
  COALESCE(s1.invite_link, s2.invite_link) as final_invite_link,
  GREATEST(COALESCE(s1.member_count, 0), COALESCE(s2.member_count, 0)) as final_member_count,
  COALESCE(s1.is_forum, s2.is_forum) as final_is_forum,
  COALESCE(s1.bot_is_admin, s2.bot_is_admin) as final_bot_is_admin,
  COALESCE(s1.has_visible_history, s2.has_visible_history) as final_has_visible_history,
  COALESCE(s1.join_to_send_messages, s2.join_to_send_messages) as final_join_to_send_messages,
  COALESCE(s1.max_reaction_count, s2.max_reaction_count) as final_max_reaction_count,
  COALESCE(s1.accent_color_id, s2.accent_color_id) as final_accent_color_id,
  -- Merge metadata
  s1.metadata || s2.metadata as final_metadata
FROM telegram_supergroups s1
JOIN telegram_supergroups s2 ON (
  normalize_telegram_supergroup_id(s1.id) = normalize_telegram_supergroup_id(s2.id)
  AND s1.id != s2.id
)
WHERE 
  -- Keep the negative (normalized) ID record
  s1.id < 0 AND s2.id > 0;

-- Update the records we're keeping with merged data
UPDATE telegram_supergroups 
SET 
  company_id = sd.final_company_id,
  title = sd.final_title,
  description = sd.final_description,
  username = sd.final_username,
  invite_link = sd.final_invite_link,
  member_count = sd.final_member_count,
  is_forum = sd.final_is_forum,
  bot_is_admin = sd.final_bot_is_admin,
  has_visible_history = sd.final_has_visible_history,
  join_to_send_messages = sd.final_join_to_send_messages,
  max_reaction_count = sd.final_max_reaction_count,
  accent_color_id = sd.final_accent_color_id,
  metadata = sd.final_metadata,
  updated_at = now()
FROM supergroup_duplicates sd
WHERE telegram_supergroups.id = sd.keep_id;

-- Update chats that reference the duplicate IDs to use the normalized ID
UPDATE chats 
SET telegram_supergroup_id = sd.keep_id
FROM supergroup_duplicates sd
WHERE chats.telegram_supergroup_id = sd.remove_id;

-- Update telegram_group_members to reference the correct supergroup
UPDATE telegram_group_members
SET supergroup_id = sd.keep_id
FROM supergroup_duplicates sd
WHERE telegram_group_members.supergroup_id = sd.remove_id;

-- Delete the duplicate records
DELETE FROM telegram_supergroups 
WHERE id IN (SELECT remove_id FROM supergroup_duplicates);

-- Drop the temporary table
DROP TABLE supergroup_duplicates;

-- Add constraint to prevent future duplicates by normalizing IDs
ALTER TABLE telegram_supergroups 
ADD CONSTRAINT check_normalized_supergroup_id 
CHECK (id < 0);