// Типы для новой системы realtime чатов на Supabase

export interface Chat {
  id: string;
  name: string | null;
  type: 'direct' | 'group' | 'company';
  company_id: number | null;
  chat_number?: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  metadata: Record<string, any>;
  participants?: ChatParticipant[];
  last_message?: Message;
  unread_count?: number;
  // Telegram integration fields
  telegram_sync?: boolean;
  telegram_supergroup_id?: number | null;
  telegram_topic_id?: number | null;
}

export interface ChatParticipant {
  id: string;
  chat_id: string;
  user_id: string;
  role: 'member' | 'admin' | 'observer';
  joined_at: string;
  last_read_at: string;
  is_active: boolean;
  profile?: {
    first_name: string | null;
    last_name: string | null;
    avatar_url: string | null;
    type: string;
  };
}

export interface Message {
  id: string;
  chat_id: string;
  sender_id: string | null;  // null for external Telegram users
  content: string | null;
  message_type: 'text' | 'file' | 'voice' | 'image' | 'system' | 'interactive';
  reply_to_id: string | null;
  file_url: string | null;
  file_name: string | null;
  file_size: number | null;
  file_type: string | null;
  voice_duration: number | null;
  interactive_data?: Record<string, any>;
  created_at: string;
  updated_at: string;
  is_edited: boolean;
  is_deleted: boolean;
  metadata: Record<string, any>;
  sender_profile?: {
    first_name: string | null;
    last_name: string | null;
    avatar_url: string | null;
    type: string;
  } | null;
  reply_to?: Message;
  read_by?: MessageRead[];
  // Message source tracking
  source?: 'web' | 'telegram' | 'api';
  // Telegram integration fields
  telegram_message_id?: number | null;
  telegram_user_id?: number | null;
  telegram_user_data?: {
    first_name?: string;
    last_name?: string;
    username?: string;
    is_bot?: boolean;
  } | null;
  telegram_topic_id?: number | null;
  telegram_forward_data?: Record<string, unknown> | null;
  sync_direction?: 'telegram_to_web' | 'web_to_telegram' | 'bidirectional';
}

export interface MessageRead {
  id: string;
  message_id: string;
  user_id: string;
  read_at: string;
}

export interface TypingIndicator {
  id: string;
  chat_id: string;
  user_id: string;
  started_at: string;
  expires_at: string;
  user_profile?: {
    first_name: string | null;
    last_name: string | null;
    avatar_url: string | null;
  };
}

// Company types
export interface Company {
  id: number;
  name: string;
  company_type: string;
  balance: number;
  status?: 'new' | 'bronze' | 'silver' | 'gold';
  orders_count?: number;
  turnover?: number;
  rating?: number;
  successful_deliveries?: number;
  created_at: string;
  updated_at: string;
  created_by_user_id?: string;
  // Additional fields from database
  vat?: string | null;
  kpp?: string | null;
  ogrn?: string | null;
  director?: string | null;
  email?: string | null;
  phone?: string | null;
  street?: string | null;
  city?: string | null;
  postal_code?: string | null;
  country?: string | null;
  logo_url?: string | null;
}

// User company relationship types
export type UserCompanyRelationship = 'owner' | 'manager' | 'assigned_admin';

export interface UserCompany {
  id: number;
  name: string;
  company_type: string;
  status: 'new' | 'bronze' | 'silver' | 'gold';
  relationship_type: UserCompanyRelationship;
  assigned_at: string;
}

// Message filter types
export type MessageFilter = 'all' | 'images' | 'pdf' | 'doc' | 'xls' | 'voice' | 'other';

// Context типы
export interface RealtimeChatContextType {
  chats: Chat[];
  activeChat: Chat | null;
  messages: Message[];
  filteredMessages: Message[];
  displayedMessages: Message[];
  messageFilter: MessageFilter;
  typingUsers: TypingIndicator[];
  initialLoading: boolean;
  loadingMessages: boolean;
  loadingMoreMessages: boolean;
  sendingMessages: Set<string>;
  hasMoreMessages: boolean;
  filteredHasMore: boolean;
  isCreatingChat: boolean;
  // Removed clientCompany and isLoadingClientCompany - admin-only system
  isLoadingChats: boolean;
  loadCompanyForChat: (chatId: string, forceRefresh?: boolean) => Promise<Company | null>;
  clearCompanyCache: (chatId?: string) => void;
  
  // Действия с чатами
  loadChats: () => Promise<void>;
  createChat: (name: string, type: Chat['type'], participantIds?: string[]) => Promise<Chat>;
  selectChat: (chatId: string, updateUrl?: boolean) => Promise<void>;
  loadMoreMessages: () => Promise<void>;
  addParticipants: (chatId: string, userIds: string[]) => Promise<void>;
  
  // Действия с сообщениями
  sendMessage: (content: string, replyToId?: string) => Promise<void>;
  sendFile: (file: File, replyToId?: string) => Promise<void>;
  sendVoice: (audioBlob: Blob, duration: number, replyToId?: string) => Promise<void>;
  sendInteractiveMessage?: (interactiveData: any, title?: string) => Promise<void>;
  markAsRead: (messageId: string) => Promise<void>;
  
  // Typing индикаторы
  startTyping: () => Promise<void>;
  stopTyping: () => Promise<void>;
  
  // Управление чатами
  updateChat: (chatId: string, name: string, description?: string) => Promise<void>;
  deleteChat: (chatId: string) => Promise<void>;
  
  // Message filtering
  setMessageFilter: (filter: MessageFilter) => Promise<void>;
  
  // Smart scrolling - bulk load history until target message
  loadHistoryUntilMessage: (messageId: string) => Promise<boolean>;
  
  // Chat scope управление
  setScopeBySupergroup: (supergroup: any) => void;
  setScopeByCompany: (companyId: number | null) => void;
  chatScope: {
    type: 'company' | 'supergroup';
    companyId?: number | null;
    supergroupId?: number | null;
    supergroupData?: any;
  };
}

// Параметры для создания чатов и сообщений
export interface CreateChatParams {
  name: string;
  type: Chat['type'];
  participantIds?: string[];
}

export interface SendMessageParams {
  content: string;
  replyToId?: string;
}

export interface SendFileParams {
  file: File;
  replyToId?: string;
}

export interface SendVoiceParams {
  audioBlob: Blob;
  duration: number;
  replyToId?: string;
}