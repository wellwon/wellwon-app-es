// Stub types - Supabase has been replaced with Event Sourcing backend
// These types exist only to prevent import errors during migration

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

// Stub Database type
export interface Database {
  public: {
    Tables: {
      profiles: {
        Row: {
          id: string;
          user_id: string;
          display_name: string | null;
          first_name: string | null;
          last_name: string | null;
          avatar_url: string | null;
          bio: string | null;
          type: string | null;
          active: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: Record<string, unknown>;
        Update: Record<string, unknown>;
      };
      companies: {
        Row: {
          id: number;
          name: string;
          description: string | null;
          vat: string | null;
          email: string | null;
          phone: string | null;
          company_type: string | null;
          status: string;
          created_at: string;
          updated_at: string;
        };
        Insert: Record<string, unknown>;
        Update: Record<string, unknown>;
      };
      chats: {
        Row: {
          id: string;
          name: string | null;
          type: string;
          company_id: string | null;
          created_by: string;
          is_active: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: Record<string, unknown>;
        Update: Record<string, unknown>;
      };
      messages: {
        Row: {
          id: string;
          chat_id: string;
          sender_id: string;
          content: string;
          message_type: string;
          file_url: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: Record<string, unknown>;
        Update: Record<string, unknown>;
      };
    };
    Enums: {
      user_type: 'ww_admin' | 'ww_manager' | 'entrepreneur' | 'investor' | 'client';
      company_status: 'active' | 'inactive' | 'suspended';
      chat_type: 'direct' | 'group' | 'company' | 'telegram_group';
      message_type: 'text' | 'file' | 'voice' | 'image' | 'system';
    };
  };
}

// Common Supabase types that might be referenced
export type Tables<T extends keyof Database['public']['Tables']> = Database['public']['Tables'][T]['Row'];
export type Enums<T extends keyof Database['public']['Enums']> = Database['public']['Enums'][T];
