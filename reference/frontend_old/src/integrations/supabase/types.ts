export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "13.0.4"
  }
  public: {
    Tables: {
      chat_participants: {
        Row: {
          chat_id: string | null
          id: string
          is_active: boolean | null
          joined_at: string | null
          last_read_at: string | null
          role: string | null
          user_id: string | null
        }
        Insert: {
          chat_id?: string | null
          id?: string
          is_active?: boolean | null
          joined_at?: string | null
          last_read_at?: string | null
          role?: string | null
          user_id?: string | null
        }
        Update: {
          chat_id?: string | null
          id?: string
          is_active?: boolean | null
          joined_at?: string | null
          last_read_at?: string | null
          role?: string | null
          user_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "chat_participants_chat_id_fkey"
            columns: ["chat_id"]
            isOneToOne: false
            referencedRelation: "chats"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "chat_participants_chat_id_fkey"
            columns: ["chat_id"]
            isOneToOne: false
            referencedRelation: "chats_with_group"
            referencedColumns: ["id"]
          },
        ]
      }
      chats: {
        Row: {
          chat_number: number | null
          company_id: number | null
          created_at: string | null
          created_by: string | null
          id: string
          is_active: boolean | null
          metadata: Json | null
          name: string | null
          telegram_supergroup_id: number | null
          telegram_sync: boolean | null
          telegram_topic_id: number | null
          type: string | null
          updated_at: string | null
        }
        Insert: {
          chat_number?: number | null
          company_id?: number | null
          created_at?: string | null
          created_by?: string | null
          id?: string
          is_active?: boolean | null
          metadata?: Json | null
          name?: string | null
          telegram_supergroup_id?: number | null
          telegram_sync?: boolean | null
          telegram_topic_id?: number | null
          type?: string | null
          updated_at?: string | null
        }
        Update: {
          chat_number?: number | null
          company_id?: number | null
          created_at?: string | null
          created_by?: string | null
          id?: string
          is_active?: boolean | null
          metadata?: Json | null
          name?: string | null
          telegram_supergroup_id?: number | null
          telegram_sync?: boolean | null
          telegram_topic_id?: number | null
          type?: string | null
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "chats_telegram_supergroup_id_fkey"
            columns: ["telegram_supergroup_id"]
            isOneToOne: false
            referencedRelation: "telegram_supergroups"
            referencedColumns: ["id"]
          },
        ]
      }
      client_currencies: {
        Row: {
          cny_rub: number
          created_at: string
          eur_rub: number
          id: number
          usd_cny: number
          usd_rub: number
        }
        Insert: {
          cny_rub: number
          created_at?: string
          eur_rub: number
          id?: number
          usd_cny: number
          usd_rub: number
        }
        Update: {
          cny_rub?: number
          created_at?: string
          eur_rub?: number
          id?: number
          usd_cny?: number
          usd_rub?: number
        }
        Relationships: []
      }
      client_news: {
        Row: {
          category: string
          content: string
          created_at: string | null
          date: string
          id: string
          image: string | null
          is_published: boolean | null
          preview: string | null
          title: string
          updated_at: string | null
        }
        Insert: {
          category: string
          content: string
          created_at?: string | null
          date?: string
          id?: string
          image?: string | null
          is_published?: boolean | null
          preview?: string | null
          title: string
          updated_at?: string | null
        }
        Update: {
          category?: string
          content?: string
          created_at?: string | null
          date?: string
          id?: string
          image?: string | null
          is_published?: boolean | null
          preview?: string | null
          title?: string
          updated_at?: string | null
        }
        Relationships: []
      }
      companies: {
        Row: {
          assigned_manager_id: string | null
          balance: number
          city: string | null
          company_type: string
          country: string | null
          created_at: string
          created_by_user_id: string | null
          director: string | null
          email: string | null
          id: number
          kpp: string | null
          name: string
          ogrn: string | null
          orders_count: number
          phone: string | null
          postal_code: string | null
          rating: number
          status: Database["public"]["Enums"]["company_status"]
          street: string | null
          successful_deliveries: number
          tg_accountant: string | null
          tg_dir: string | null
          tg_manager_1: string | null
          tg_manager_2: string | null
          tg_manager_3: string | null
          tg_support: string | null
          turnover: number
          updated_at: string
          vat: string | null
          x_studio_company_or_project: string | null
        }
        Insert: {
          assigned_manager_id?: string | null
          balance?: number
          city?: string | null
          company_type?: string
          country?: string | null
          created_at?: string
          created_by_user_id?: string | null
          director?: string | null
          email?: string | null
          id?: number
          kpp?: string | null
          name: string
          ogrn?: string | null
          orders_count?: number
          phone?: string | null
          postal_code?: string | null
          rating?: number
          status?: Database["public"]["Enums"]["company_status"]
          street?: string | null
          successful_deliveries?: number
          tg_accountant?: string | null
          tg_dir?: string | null
          tg_manager_1?: string | null
          tg_manager_2?: string | null
          tg_manager_3?: string | null
          tg_support?: string | null
          turnover?: number
          updated_at?: string
          vat?: string | null
          x_studio_company_or_project?: string | null
        }
        Update: {
          assigned_manager_id?: string | null
          balance?: number
          city?: string | null
          company_type?: string
          country?: string | null
          created_at?: string
          created_by_user_id?: string | null
          director?: string | null
          email?: string | null
          id?: number
          kpp?: string | null
          name?: string
          ogrn?: string | null
          orders_count?: number
          phone?: string | null
          postal_code?: string | null
          rating?: number
          status?: Database["public"]["Enums"]["company_status"]
          street?: string | null
          successful_deliveries?: number
          tg_accountant?: string | null
          tg_dir?: string | null
          tg_manager_1?: string | null
          tg_manager_2?: string | null
          tg_manager_3?: string | null
          tg_support?: string | null
          turnover?: number
          updated_at?: string
          vat?: string | null
          x_studio_company_or_project?: string | null
        }
        Relationships: []
      }
      message_reads: {
        Row: {
          id: string
          message_id: string | null
          read_at: string | null
          user_id: string | null
        }
        Insert: {
          id?: string
          message_id?: string | null
          read_at?: string | null
          user_id?: string | null
        }
        Update: {
          id?: string
          message_id?: string | null
          read_at?: string | null
          user_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "message_reads_message_id_fkey"
            columns: ["message_id"]
            isOneToOne: false
            referencedRelation: "messages"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "message_reads_message_id_fkey"
            columns: ["message_id"]
            isOneToOne: false
            referencedRelation: "messages_with_context"
            referencedColumns: ["id"]
          },
        ]
      }
      message_templates: {
        Row: {
          category: string
          created_at: string
          created_by: string | null
          description: string | null
          id: string
          image_url: string | null
          is_active: boolean
          name: string
          template_data: Json
          updated_at: string
        }
        Insert: {
          category: string
          created_at?: string
          created_by?: string | null
          description?: string | null
          id?: string
          image_url?: string | null
          is_active?: boolean
          name: string
          template_data: Json
          updated_at?: string
        }
        Update: {
          category?: string
          created_at?: string
          created_by?: string | null
          description?: string | null
          id?: string
          image_url?: string | null
          is_active?: boolean
          name?: string
          template_data?: Json
          updated_at?: string
        }
        Relationships: []
      }
      messages: {
        Row: {
          chat_id: string | null
          content: string | null
          created_at: string | null
          file_name: string | null
          file_size: number | null
          file_status: string
          file_type: string | null
          file_url: string | null
          id: string
          interactive_data: Json | null
          is_deleted: boolean | null
          is_edited: boolean | null
          message_type: string | null
          metadata: Json | null
          reply_to_id: string | null
          sender_id: string | null
          sync_direction: string | null
          telegram_file_id: string | null
          telegram_file_path: string | null
          telegram_forward_data: Json | null
          telegram_message_id: number | null
          telegram_topic_id: number | null
          telegram_user_data: Json | null
          telegram_user_id: number | null
          updated_at: string | null
          voice_duration: number | null
        }
        Insert: {
          chat_id?: string | null
          content?: string | null
          created_at?: string | null
          file_name?: string | null
          file_size?: number | null
          file_status?: string
          file_type?: string | null
          file_url?: string | null
          id?: string
          interactive_data?: Json | null
          is_deleted?: boolean | null
          is_edited?: boolean | null
          message_type?: string | null
          metadata?: Json | null
          reply_to_id?: string | null
          sender_id?: string | null
          sync_direction?: string | null
          telegram_file_id?: string | null
          telegram_file_path?: string | null
          telegram_forward_data?: Json | null
          telegram_message_id?: number | null
          telegram_topic_id?: number | null
          telegram_user_data?: Json | null
          telegram_user_id?: number | null
          updated_at?: string | null
          voice_duration?: number | null
        }
        Update: {
          chat_id?: string | null
          content?: string | null
          created_at?: string | null
          file_name?: string | null
          file_size?: number | null
          file_status?: string
          file_type?: string | null
          file_url?: string | null
          id?: string
          interactive_data?: Json | null
          is_deleted?: boolean | null
          is_edited?: boolean | null
          message_type?: string | null
          metadata?: Json | null
          reply_to_id?: string | null
          sender_id?: string | null
          sync_direction?: string | null
          telegram_file_id?: string | null
          telegram_file_path?: string | null
          telegram_forward_data?: Json | null
          telegram_message_id?: number | null
          telegram_topic_id?: number | null
          telegram_user_data?: Json | null
          telegram_user_id?: number | null
          updated_at?: string | null
          voice_duration?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "messages_chat_id_fkey"
            columns: ["chat_id"]
            isOneToOne: false
            referencedRelation: "chats"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "messages_chat_id_fkey"
            columns: ["chat_id"]
            isOneToOne: false
            referencedRelation: "chats_with_group"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "messages_reply_to_id_fkey"
            columns: ["reply_to_id"]
            isOneToOne: false
            referencedRelation: "messages"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "messages_reply_to_id_fkey"
            columns: ["reply_to_id"]
            isOneToOne: false
            referencedRelation: "messages_with_context"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          active: boolean
          avatar_url: string | null
          bio: string | null
          business_role:
            | Database["public"]["Enums"]["chat_business_role"]
            | null
          created_at: string
          developer: boolean | null
          first_name: string | null
          id: string
          last_name: string | null
          phone: string | null
          role_label: string | null
          telegram_user_id: number | null
          type: Database["public"]["Enums"]["user_type"]
          updated_at: string
          user_id: string
          user_number: number | null
        }
        Insert: {
          active?: boolean
          avatar_url?: string | null
          bio?: string | null
          business_role?:
            | Database["public"]["Enums"]["chat_business_role"]
            | null
          created_at?: string
          developer?: boolean | null
          first_name?: string | null
          id?: string
          last_name?: string | null
          phone?: string | null
          role_label?: string | null
          telegram_user_id?: number | null
          type?: Database["public"]["Enums"]["user_type"]
          updated_at?: string
          user_id: string
          user_number?: number | null
        }
        Update: {
          active?: boolean
          avatar_url?: string | null
          bio?: string | null
          business_role?:
            | Database["public"]["Enums"]["chat_business_role"]
            | null
          created_at?: string
          developer?: boolean | null
          first_name?: string | null
          id?: string
          last_name?: string | null
          phone?: string | null
          role_label?: string | null
          telegram_user_id?: number | null
          type?: Database["public"]["Enums"]["user_type"]
          updated_at?: string
          user_id?: string
          user_number?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "profiles_telegram_user_id_fkey"
            columns: ["telegram_user_id"]
            isOneToOne: false
            referencedRelation: "tg_users"
            referencedColumns: ["id"]
          },
        ]
      }
      system_logs: {
        Row: {
          created_at: string | null
          id: string
          level: string
          message: string
          metadata: Json | null
        }
        Insert: {
          created_at?: string | null
          id?: string
          level?: string
          message: string
          metadata?: Json | null
        }
        Update: {
          created_at?: string | null
          id?: string
          level?: string
          message?: string
          metadata?: Json | null
        }
        Relationships: []
      }
      telegram_group_members: {
        Row: {
          first_name: string | null
          id: string
          is_active: boolean | null
          is_bot: boolean | null
          joined_at: string | null
          last_name: string | null
          last_seen: string | null
          metadata: Json | null
          status: string | null
          supergroup_id: number | null
          telegram_user_id: number
          username: string | null
        }
        Insert: {
          first_name?: string | null
          id?: string
          is_active?: boolean | null
          is_bot?: boolean | null
          joined_at?: string | null
          last_name?: string | null
          last_seen?: string | null
          metadata?: Json | null
          status?: string | null
          supergroup_id?: number | null
          telegram_user_id: number
          username?: string | null
        }
        Update: {
          first_name?: string | null
          id?: string
          is_active?: boolean | null
          is_bot?: boolean | null
          joined_at?: string | null
          last_name?: string | null
          last_seen?: string | null
          metadata?: Json | null
          status?: string | null
          supergroup_id?: number | null
          telegram_user_id?: number
          username?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "telegram_group_members_supergroup_id_fkey"
            columns: ["supergroup_id"]
            isOneToOne: false
            referencedRelation: "telegram_supergroups"
            referencedColumns: ["id"]
          },
        ]
      }
      telegram_supergroups: {
        Row: {
          accent_color_id: number | null
          bot_is_admin: boolean | null
          company_id: number | null
          company_logo: string | null
          created_at: string | null
          description: string | null
          group_type: Database["public"]["Enums"]["telegram_group_type"]
          has_visible_history: boolean | null
          id: number
          invite_link: string | null
          is_active: boolean | null
          is_forum: boolean | null
          join_to_send_messages: boolean | null
          max_reaction_count: number | null
          member_count: number | null
          metadata: Json | null
          responsible_user_id: string | null
          status_emoji: Database["public"]["Enums"]["telegram_group_state"]
          title: string
          updated_at: string | null
          username: string | null
        }
        Insert: {
          accent_color_id?: number | null
          bot_is_admin?: boolean | null
          company_id?: number | null
          company_logo?: string | null
          created_at?: string | null
          description?: string | null
          group_type?: Database["public"]["Enums"]["telegram_group_type"]
          has_visible_history?: boolean | null
          id: number
          invite_link?: string | null
          is_active?: boolean | null
          is_forum?: boolean | null
          join_to_send_messages?: boolean | null
          max_reaction_count?: number | null
          member_count?: number | null
          metadata?: Json | null
          responsible_user_id?: string | null
          status_emoji?: Database["public"]["Enums"]["telegram_group_state"]
          title: string
          updated_at?: string | null
          username?: string | null
        }
        Update: {
          accent_color_id?: number | null
          bot_is_admin?: boolean | null
          company_id?: number | null
          company_logo?: string | null
          created_at?: string | null
          description?: string | null
          group_type?: Database["public"]["Enums"]["telegram_group_type"]
          has_visible_history?: boolean | null
          id?: number
          invite_link?: string | null
          is_active?: boolean | null
          is_forum?: boolean | null
          join_to_send_messages?: boolean | null
          max_reaction_count?: number | null
          member_count?: number | null
          metadata?: Json | null
          responsible_user_id?: string | null
          status_emoji?: Database["public"]["Enums"]["telegram_group_state"]
          title?: string
          updated_at?: string | null
          username?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "telegram_supergroups_company_id_fkey"
            columns: ["company_id"]
            isOneToOne: false
            referencedRelation: "companies"
            referencedColumns: ["id"]
          },
        ]
      }
      tg_users: {
        Row: {
          allows_write_to_pm: boolean | null
          business_role:
            | Database["public"]["Enums"]["chat_business_role"]
            | null
          color_scheme: string | null
          created_at: string
          email: string | null
          first_name: string
          id: number
          is_blocked: boolean | null
          is_bot: boolean | null
          is_premium: boolean | null
          language_code: string | null
          last_name: string | null
          phone_number: string | null
          photo_url: string | null
          policy: boolean
          role_label: string | null
          updated_at: string
          user_number: number | null
          username: string | null
        }
        Insert: {
          allows_write_to_pm?: boolean | null
          business_role?:
            | Database["public"]["Enums"]["chat_business_role"]
            | null
          color_scheme?: string | null
          created_at?: string
          email?: string | null
          first_name: string
          id: number
          is_blocked?: boolean | null
          is_bot?: boolean | null
          is_premium?: boolean | null
          language_code?: string | null
          last_name?: string | null
          phone_number?: string | null
          photo_url?: string | null
          policy?: boolean
          role_label?: string | null
          updated_at?: string
          user_number?: number | null
          username?: string | null
        }
        Update: {
          allows_write_to_pm?: boolean | null
          business_role?:
            | Database["public"]["Enums"]["chat_business_role"]
            | null
          color_scheme?: string | null
          created_at?: string
          email?: string | null
          first_name?: string
          id?: number
          is_blocked?: boolean | null
          is_bot?: boolean | null
          is_premium?: boolean | null
          language_code?: string | null
          last_name?: string | null
          phone_number?: string | null
          photo_url?: string | null
          policy?: boolean
          role_label?: string | null
          updated_at?: string
          user_number?: number | null
          username?: string | null
        }
        Relationships: []
      }
      two_factor_challenges: {
        Row: {
          attempts: number
          code_hash: string
          consumed: boolean
          created_at: string
          expires_at: string
          id: string
          method: string
          user_id: string
        }
        Insert: {
          attempts?: number
          code_hash: string
          consumed?: boolean
          created_at?: string
          expires_at?: string
          id?: string
          method?: string
          user_id: string
        }
        Update: {
          attempts?: number
          code_hash?: string
          consumed?: boolean
          created_at?: string
          expires_at?: string
          id?: string
          method?: string
          user_id?: string
        }
        Relationships: []
      }
      typing_indicators: {
        Row: {
          chat_id: string | null
          expires_at: string | null
          id: string
          started_at: string | null
          user_id: string | null
        }
        Insert: {
          chat_id?: string | null
          expires_at?: string | null
          id?: string
          started_at?: string | null
          user_id?: string | null
        }
        Update: {
          chat_id?: string | null
          expires_at?: string | null
          id?: string
          started_at?: string | null
          user_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "typing_indicators_chat_id_fkey"
            columns: ["chat_id"]
            isOneToOne: false
            referencedRelation: "chats"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "typing_indicators_chat_id_fkey"
            columns: ["chat_id"]
            isOneToOne: false
            referencedRelation: "chats_with_group"
            referencedColumns: ["id"]
          },
        ]
      }
      user_companies: {
        Row: {
          assigned_at: string
          company_id: number
          created_at: string
          id: string
          is_active: boolean
          relationship_type: Database["public"]["Enums"]["user_company_relationship"]
          updated_at: string
          user_id: string
        }
        Insert: {
          assigned_at?: string
          company_id: number
          created_at?: string
          id?: string
          is_active?: boolean
          relationship_type?: Database["public"]["Enums"]["user_company_relationship"]
          updated_at?: string
          user_id: string
        }
        Update: {
          assigned_at?: string
          company_id?: number
          created_at?: string
          id?: string
          is_active?: boolean
          relationship_type?: Database["public"]["Enums"]["user_company_relationship"]
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "user_companies_company_id_fkey"
            columns: ["company_id"]
            isOneToOne: false
            referencedRelation: "companies"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      chats_with_group: {
        Row: {
          chat_number: number | null
          chat_title: string | null
          company_id: number | null
          created_at: string | null
          created_by: string | null
          group_title: string | null
          id: string | null
          is_active: boolean | null
          metadata: Json | null
          telegram_supergroup_id: number | null
          telegram_sync: boolean | null
          telegram_topic_id: number | null
          type: string | null
          updated_at: string | null
        }
        Relationships: [
          {
            foreignKeyName: "chats_telegram_supergroup_id_fkey"
            columns: ["telegram_supergroup_id"]
            isOneToOne: false
            referencedRelation: "telegram_supergroups"
            referencedColumns: ["id"]
          },
        ]
      }
      messages_with_context: {
        Row: {
          chat_id: string | null
          chat_number: number | null
          chat_telegram_topic_id: number | null
          chat_title: string | null
          content: string | null
          created_at: string | null
          file_name: string | null
          file_size: number | null
          file_type: string | null
          file_url: string | null
          group_title: string | null
          id: string | null
          interactive_data: Json | null
          is_deleted: boolean | null
          is_edited: boolean | null
          message_telegram_topic_id: number | null
          message_type: string | null
          metadata: Json | null
          sender_id: string | null
          sender_name: string | null
          sync_direction: string | null
          telegram_forward_data: Json | null
          telegram_message_id: number | null
          telegram_supergroup_id: number | null
          telegram_user_data: Json | null
          telegram_user_id: number | null
          updated_at: string | null
          voice_duration: number | null
        }
        Relationships: [
          {
            foreignKeyName: "chats_telegram_supergroup_id_fkey"
            columns: ["telegram_supergroup_id"]
            isOneToOne: false
            referencedRelation: "telegram_supergroups"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "messages_chat_id_fkey"
            columns: ["chat_id"]
            isOneToOne: false
            referencedRelation: "chats"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "messages_chat_id_fkey"
            columns: ["chat_id"]
            isOneToOne: false
            referencedRelation: "chats_with_group"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Functions: {
      assign_admin_to_company: {
        Args: { admin_user_id: string; target_company_id: number }
        Returns: boolean
      }
      assign_company_to_chat_after_participants: {
        Args: { chat_uuid: string }
        Returns: undefined
      }
      bind_client_chats_to_first_company: {
        Args: { client_user_id: string; company_uuid: number }
        Returns: undefined
      }
      can_access_chat: { Args: { chat_uuid: string }; Returns: boolean }
      cleanup_expired_typing_indicators: { Args: never; Returns: undefined }
      cleanup_orphaned_replies: { Args: never; Returns: Json }
      create_chat_with_company: {
        Args: {
          chat_name: string
          chat_type: string
          company_uuid?: number
          creator_id: string
        }
        Returns: string
      }
      create_company_with_owner: {
        Args: { company_data: Json; owner_user_id: string }
        Returns: {
          balance: number
          city: string
          company_type: string
          country: string
          created_at: string
          director: string
          email: string
          id: number
          kpp: string
          name: string
          ogrn: string
          orders_count: number
          phone: string
          postal_code: string
          rating: number
          status: Database["public"]["Enums"]["company_status"]
          street: string
          successful_deliveries: number
          turnover: number
          updated_at: string
          vat: string
        }[]
      }
      ensure_user_is_participant: {
        Args: { chat_uuid: string; user_uuid: string }
        Returns: boolean
      }
      get_chat_with_telegram_data: {
        Args: { chat_uuid: string }
        Returns: {
          company_id: number
          created_at: string
          id: string
          name: string
          telegram_supergroup_id: number
          telegram_sync: boolean
          telegram_topic_id: number
          type: string
          updated_at: string
        }[]
      }
      get_client_company_from_chat: {
        Args: { chat_uuid: string }
        Returns: {
          balance: number
          client_user_id: string
          company_type: string
          created_at: string
          id: number
          name: string
          orders_count: number
          rating: number
          status: Database["public"]["Enums"]["company_status"]
          successful_deliveries: number
          turnover: number
          updated_at: string
        }[]
      }
      get_client_from_chat: { Args: { chat_uuid: string }; Returns: string }
      get_company_users: {
        Args: {
          filter_relationship_type?: Database["public"]["Enums"]["user_company_relationship"]
          target_company_id: number
        }
        Returns: {
          assigned_at: string
          avatar_url: string
          first_name: string
          last_name: string
          relationship_type: Database["public"]["Enums"]["user_company_relationship"]
          type: Database["public"]["Enums"]["user_type"]
          user_id: string
        }[]
      }
      get_current_user_type: { Args: never; Returns: string }
      get_next_chat_number: { Args: never; Returns: number }
      get_next_user_number: { Args: never; Returns: number }
      get_user_chats_by_company: {
        Args: { company_uuid?: number; user_uuid: string }
        Returns: {
          chat_number: number
          company_id: number
          created_at: string
          created_by: string
          id: string
          is_active: boolean
          metadata: Json
          name: string
          telegram_supergroup_id: number
          telegram_sync: boolean
          telegram_topic_id: number
          type: string
          updated_at: string
        }[]
      }
      get_user_chats_by_supergroup: {
        Args: { supergroup_id_param: number; user_uuid: string }
        Returns: {
          chat_number: number
          company_id: number
          created_at: string
          created_by: string
          id: string
          is_active: boolean
          metadata: Json
          name: string
          telegram_supergroup_id: number
          telegram_sync: boolean
          telegram_topic_id: number
          type: string
          updated_at: string
        }[]
      }
      get_user_chats_by_supergroup_archived: {
        Args: { supergroup_id_param: number; user_uuid: string }
        Returns: {
          chat_number: number
          company_id: number
          created_at: string
          created_by: string
          id: string
          is_active: boolean
          metadata: Json
          name: string
          telegram_supergroup_id: number
          telegram_sync: boolean
          telegram_topic_id: number
          type: string
          updated_at: string
        }[]
      }
      get_user_companies: {
        Args: {
          filter_relationship_type?: Database["public"]["Enums"]["user_company_relationship"]
          target_user_id: string
        }
        Returns: {
          assigned_at: string
          company_type: string
          id: number
          name: string
          relationship_type: Database["public"]["Enums"]["user_company_relationship"]
          status: Database["public"]["Enums"]["company_status"]
        }[]
      }
      get_user_company: {
        Args: { user_uuid: string }
        Returns: {
          balance: number
          company_type: string
          created_at: string
          id: number
          name: string
          orders_count: number
          rating: number
          status: Database["public"]["Enums"]["company_status"]
          successful_deliveries: number
          turnover: number
          updated_at: string
        }[]
      }
      is_active_employee: { Args: never; Returns: boolean }
      is_current_user_developer: { Args: never; Returns: boolean }
      is_developer: { Args: never; Returns: boolean }
      is_user_developer: { Args: never; Returns: boolean }
      normalize_telegram_supergroup_id: {
        Args: { input_id: number }
        Returns: number
      }
      should_ignore_telegram_supergroup: {
        Args: { supergroup_id: number }
        Returns: boolean
      }
      update_chat_telegram_settings: {
        Args: {
          chat_uuid: string
          enable_sync: boolean
          supergroup_id?: number
          topic_id?: number
        }
        Returns: boolean
      }
      update_supabase_config: { Args: never; Returns: undefined }
      update_user_type_for_testing: {
        Args: {
          new_user_type: Database["public"]["Enums"]["user_type"]
          target_email: string
        }
        Returns: boolean
      }
    }
    Enums: {
      chat_business_role:
        | "client"
        | "payment_agent"
        | "logistician"
        | "purchasers"
        | "unassigned"
        | "manager"
      company_status: "new" | "bronze" | "silver" | "gold"
      telegram_group_state: "✅ Working" | "🗄️ Archive" | "❌ Closed"
      telegram_group_type:
        | "client"
        | "payments"
        | "logistics"
        | "buyers"
        | "others"
        | "wellwon"
      telegram_supergroup_status: "Active" | "Archive" | "Closed"
      user_company_relationship: "owner" | "manager" | "assigned_admin"
      user_type: "client" | "performer" | "ww_manager" | "ww_developer"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      chat_business_role: [
        "client",
        "payment_agent",
        "logistician",
        "purchasers",
        "unassigned",
        "manager",
      ],
      company_status: ["new", "bronze", "silver", "gold"],
      telegram_group_state: ["✅ Working", "🗄️ Archive", "❌ Closed"],
      telegram_group_type: [
        "client",
        "payments",
        "logistics",
        "buyers",
        "others",
        "wellwon",
      ],
      telegram_supergroup_status: ["Active", "Archive", "Closed"],
      user_company_relationship: ["owner", "manager", "assigned_admin"],
      user_type: ["client", "performer", "ww_manager", "ww_developer"],
    },
  },
} as const
