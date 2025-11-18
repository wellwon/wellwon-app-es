export interface ConversationItem {
  id: string;
  title: string;
  last_message: string;
  updated_at: string;
  unread_count: number;
  deal_id?: string;
  company_id?: string;
  status?: string;
  // Telegram integration fields
  telegram_supergroup_id?: number;
  telegram_topic_id?: number;
  telegram_sync?: boolean;
}

export interface DealInfo {
  id: string;
  title: string;
  description?: string;
  amount?: number;
  status: string;
  company_id: string;
  created_at: string;
  updated_at: string;
}

export interface ButtonData {
  text: string;
  action: string;
  variant?: 'primary' | 'secondary' | 'outline';
  disabled?: boolean;
  metadata?: Record<string, unknown>;
}

export interface MessageButton extends ButtonData {
  id: string;
  message_id: string;
  order: number;
}

export interface FormFieldData {
  type: 'text' | 'email' | 'tel' | 'number' | 'textarea' | 'select';
  name: string;
  label: string;
  placeholder?: string;
  required?: boolean;
  options?: Array<{ value: string; label: string }>;
  validation?: {
    pattern?: string;
    min?: number;
    max?: number;
    minLength?: number;
    maxLength?: number;
  };
}

export interface FormData {
  [key: string]: string | number | boolean | null | undefined;
}

export interface TemplateData {
  title?: string;
  description?: string;
  fields?: FormFieldData[];
  buttons?: ButtonData[];
  [key: string]: unknown;
}

// Telegram-specific types
export interface TelegramSupergroup {
  id: number;
  company_id?: number;
  title: string;
  username?: string;
  description?: string;
  invite_link?: string;
  member_count: number;
  is_forum: boolean;
  is_active: boolean;
  bot_is_admin: boolean;
  has_visible_history?: boolean;
  join_to_send_messages?: boolean;
  max_reaction_count?: number;
  accent_color_id?: number;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
  company_logo?: string;
  group_type?: 'client' | 'payments' | 'logistics' | 'buyers' | 'others' | 'wellwon';
}

export interface TelegramGroupMember {
  id: string;
  supergroup_id: number;
  telegram_user_id: number;
  username?: string;
  first_name: string;
  last_name?: string;
  is_bot: boolean;
  status: 'member' | 'administrator' | 'creator' | 'restricted' | 'left' | 'kicked';
  joined_at: string;
  last_seen: string;
  is_active: boolean;
  metadata?: Record<string, unknown>;
}

export interface TelegramMessageData {
  telegram_message_id?: number;
  telegram_user_id?: number;
  telegram_user_data?: {
    id: number;
    first_name: string;
    last_name?: string;
    username?: string;
    is_bot: boolean;
  };
  telegram_topic_id?: number;
  telegram_forward_data?: Record<string, unknown>;
  sync_direction?: 'telegram_to_web' | 'web_to_telegram' | 'bidirectional';
}