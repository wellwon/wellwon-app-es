-- Add new fields to telegram_supergroups table
ALTER TABLE public.telegram_supergroups 
ADD COLUMN has_visible_history boolean DEFAULT true,
ADD COLUMN join_to_send_messages boolean DEFAULT false,
ADD COLUMN max_reaction_count integer DEFAULT 11,
ADD COLUMN accent_color_id integer;