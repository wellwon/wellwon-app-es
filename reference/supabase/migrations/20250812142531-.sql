-- Remove client and performer from user_type enum
-- First, update all existing client and performer users to ww_manager
UPDATE public.profiles 
SET type = 'ww_manager' 
WHERE type IN ('client', 'performer');

-- Recreate the enum with only manager and developer types
ALTER TYPE user_type RENAME TO user_type_old;

CREATE TYPE user_type AS ENUM ('ww_manager', 'ww_developer');

-- Update the column to use the new enum
ALTER TABLE public.profiles 
ALTER COLUMN type TYPE user_type USING type::text::user_type;

-- Drop the old enum
DROP TYPE user_type_old;