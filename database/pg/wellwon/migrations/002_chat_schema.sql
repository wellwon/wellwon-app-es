-- =============================================================================
-- File: database/migrations/002_chat_schema.sql
-- Description: Chat domain read model tables
-- =============================================================================

-- Chat table
CREATE TABLE IF NOT EXISTS public.chats (
    id UUID PRIMARY KEY,
    name TEXT,
    chat_type TEXT NOT NULL CHECK (chat_type IN ('direct', 'group', 'company')),
    company_id UUID,
    created_by UUID NOT NULL REFERENCES public.users(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    participant_count INTEGER NOT NULL DEFAULT 0,
    last_message_at TIMESTAMP WITH TIME ZONE,
    last_message_content TEXT,
    last_message_sender_id UUID REFERENCES public.users(id),
    -- Telegram integration
    telegram_chat_id BIGINT,
    telegram_topic_id BIGINT,  -- Changed from INTEGER to match ScyllaDB
    -- Metadata and versioning
    metadata JSONB NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 0
);

-- Chat participants table
CREATE TABLE IF NOT EXISTS public.chat_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id UUID NOT NULL REFERENCES public.chats(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id),
    role TEXT NOT NULL CHECK (role IN ('member', 'admin', 'observer')) DEFAULT 'member',
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_read_at TIMESTAMP WITH TIME ZONE,
    last_read_message_id UUID,
    is_active BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT unique_chat_participant UNIQUE (chat_id, user_id)
);

-- Messages table
CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY,
    chat_id UUID NOT NULL REFERENCES public.chats(id) ON DELETE CASCADE,
    sender_id UUID REFERENCES public.users(id),  -- NULL for unmapped Telegram users
    content TEXT NOT NULL,
    message_type TEXT NOT NULL CHECK (message_type IN ('text', 'file', 'voice', 'image', 'system')) DEFAULT 'text',
    reply_to_id UUID REFERENCES public.messages(id),
    -- File attachments
    file_url TEXT,
    file_name TEXT,
    file_size BIGINT,
    file_type TEXT,
    voice_duration INTEGER,  -- seconds for voice messages
    -- Timestamps and status
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    is_edited BOOLEAN NOT NULL DEFAULT false,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    -- Source tracking
    source TEXT NOT NULL CHECK (source IN ('web', 'telegram', 'api')) DEFAULT 'web',
    telegram_message_id BIGINT,
    -- Metadata
    metadata JSONB NOT NULL DEFAULT '{}'
);

-- Message read status table
CREATE TABLE IF NOT EXISTS public.message_reads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES public.messages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id),
    read_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_message_read UNIQUE (message_id, user_id)
);

-- =============================================================================
-- Indexes for performance
-- =============================================================================

-- Chats indexes
CREATE INDEX IF NOT EXISTS idx_chats_created_by ON public.chats(created_by);
CREATE INDEX IF NOT EXISTS idx_chats_company_id ON public.chats(company_id) WHERE company_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chats_telegram_chat_id ON public.chats(telegram_chat_id) WHERE telegram_chat_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chats_last_message_at ON public.chats(last_message_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_chats_is_active ON public.chats(is_active) WHERE is_active = true;

-- Chat participants indexes
CREATE INDEX IF NOT EXISTS idx_chat_participants_chat_id ON public.chat_participants(chat_id);
CREATE INDEX IF NOT EXISTS idx_chat_participants_user_id ON public.chat_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_participants_active ON public.chat_participants(chat_id, user_id) WHERE is_active = true;

-- Messages indexes
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON public.messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON public.messages(sender_id) WHERE sender_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_chat_created_at ON public.messages(chat_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_reply_to ON public.messages(reply_to_id) WHERE reply_to_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_telegram ON public.messages(telegram_message_id) WHERE telegram_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_content_search ON public.messages USING gin(to_tsvector('english', content)) WHERE is_deleted = false;

-- Message reads indexes
CREATE INDEX IF NOT EXISTS idx_message_reads_message_id ON public.message_reads(message_id);
CREATE INDEX IF NOT EXISTS idx_message_reads_user_id ON public.message_reads(user_id);

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE public.chats IS 'Chat domain read model - stores chat metadata';
COMMENT ON TABLE public.chat_participants IS 'Chat participants with roles and read positions';
COMMENT ON TABLE public.messages IS 'Chat messages with support for files, voice, and Telegram';
COMMENT ON TABLE public.message_reads IS 'Message read status tracking';

COMMENT ON COLUMN public.chats.telegram_chat_id IS 'Linked Telegram chat ID for integration';
COMMENT ON COLUMN public.chats.telegram_topic_id IS 'Telegram forum topic ID (for supergroups with topics)';
COMMENT ON COLUMN public.messages.source IS 'Message origin: web (WellWon), telegram, or api';
COMMENT ON COLUMN public.messages.telegram_message_id IS 'Original Telegram message ID for deduplication';
