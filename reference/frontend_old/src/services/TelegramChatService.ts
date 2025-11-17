import { supabase } from '@/integrations/supabase/client';
import { logger } from '@/utils/logger';
import type { TelegramSupergroup, TelegramGroupMember, TelegramMessageData } from '@/types/chat';
import type { ChatBusinessRole } from '@/constants/userRoles';

export class TelegramChatService {
  /**
   * Получить все супергруппы для компании
   */
  static async getSupergroupsByCompany(companyId: number): Promise<TelegramSupergroup[]> {
    try {
      const { data, error } = await supabase
        .from('telegram_supergroups')
        .select('*')
        .eq('company_id', companyId)
        .eq('is_active', true)
        .order('title');

      if (error) {
        logger.error('Failed to fetch supergroups', error, { 
          component: 'TelegramChatService',
          companyId 
        });
        throw error;
      }

      return (data || []).map(item => ({
        ...item,
        metadata: item.metadata as Record<string, unknown> || {}
      })) as TelegramSupergroup[];
    } catch (error) {
      logger.error('Error in getSupergroupsByCompany', error, { 
        component: 'TelegramChatService',
        companyId 
      });
      return [];
    }
  }

  /**
   * Получить все супергруппы (активные или архивные)
   */
  static async getAllSupergroups(isActive: boolean = true): Promise<TelegramSupergroup[]> {
    try {
      const { data, error } = await supabase
        .from('telegram_supergroups')
        .select('*')
        .eq('is_active', isActive)
        .order('title');

      if (error) {
        logger.error('Failed to fetch all supergroups', error, { 
          component: 'TelegramChatService',
          isActive
        });
        throw error;
      }

      return (data || []).map(item => ({
        ...item,
        metadata: item.metadata as Record<string, unknown> || {}
      })) as TelegramSupergroup[];
    } catch (error) {
      logger.error('Error in getAllSupergroups', error, { 
        component: 'TelegramChatService',
        isActive
      });
      return [];
    }
  }

  /**
   * Получить количество чатов для каждой супергруппы
   */
  static async getSupergroupChatCounts(): Promise<Record<number, number>> {
    try {
      const { data, error } = await supabase
        .from('chats')
        .select('telegram_supergroup_id')
        .not('telegram_supergroup_id', 'is', null)
        .eq('is_active', true);

      if (error) {
        logger.error('Failed to fetch supergroup chat counts', error, { 
          component: 'TelegramChatService'
        });
        throw error;
      }

      // Подсчитываем количество чатов для каждой группы
      const counts: Record<number, number> = {};
      (data || []).forEach(chat => {
        if (chat.telegram_supergroup_id) {
          counts[chat.telegram_supergroup_id] = (counts[chat.telegram_supergroup_id] || 0) + 1;
        }
      });

      return counts;
    } catch (error) {
      logger.error('Error in getSupergroupChatCounts', error, { 
        component: 'TelegramChatService'
      });
      return {};
    }
  }

  /**
   * Получить участников супергруппы
   */
  static async getSupergroupMembers(supergroupId: number): Promise<TelegramGroupMember[]> {
    try {
      const { data, error } = await supabase
        .from('telegram_group_members')
        .select('*')
        .eq('supergroup_id', supergroupId)
        .eq('is_active', true)
        .order('first_name');

      if (error) {
        logger.error('Failed to fetch supergroup members', error, { 
          component: 'TelegramChatService',
          supergroupId 
        });
        throw error;
      }

      return (data || []).map(item => ({
        ...item,
        status: item.status as TelegramGroupMember['status'] || 'member',
        metadata: item.metadata as Record<string, unknown> || {}
      })) as TelegramGroupMember[];
    } catch (error) {
      logger.error('Error in getSupergroupMembers', error, { 
        component: 'TelegramChatService',
        supergroupId 
      });
      return [];
    }
  }

  /**
   * Отправить сообщение в Telegram через Edge Function
   */
  static async sendMessageToTelegram(
    chatId: string,
    content: string,
    userId: string,
    options: {
      messageType?: string;
      fileUrl?: string;
      fileName?: string;
      fileType?: string;
      replyToTelegramMessageId?: number;
    } = {}
  ): Promise<{ success: boolean; messageId?: string; telegramMessageId?: number; error?: string }> {
    try {
      const { data, error } = await supabase.functions.invoke('telegram-send', {
        body: {
          chatId,
          content,
          userId,
          messageType: options.messageType || 'text',
          fileUrl: options.fileUrl,
          fileName: options.fileName,
          fileType: options.fileType,
          replyToTelegramMessageId: options.replyToTelegramMessageId,
        }
      });

      if (error) {
        logger.error('Failed to send message to Telegram', error, { 
          component: 'TelegramChatService',
          chatId,
          userId 
        });
        return { success: false, error: error.message };
      }

      logger.info('Message sent to Telegram successfully', { 
        component: 'TelegramChatService',
        chatId,
        messageId: data?.messageId,
        telegramMessageId: data?.telegramMessageId
      });

      return {
        success: true,
        messageId: data?.supabaseMessageId,
        telegramMessageId: data?.telegramMessageId,
      };
    } catch (error) {
      logger.error('Error in sendMessageToTelegram', error, { 
        component: 'TelegramChatService',
        chatId,
        userId 
      });
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  }

  /**
   * Нормализация ID супергруппы Telegram (добавление префикса -100)
   */
  static normalizeTelegramSupergroupId(id: number): number {
    // If positive ID, add -100 prefix by making it negative and subtracting 1000000000000
    if (id > 0) {
      return id * -1 - 1000000000000;
    }
    // If already negative, return as is
    return id;
  }

  /**
   * Создать или обновить супергруппу с новыми полями
   */
  static async upsertSupergroup(supergroupData: Partial<TelegramSupergroup> & { id: number }): Promise<TelegramSupergroup> {
    try {
      // Normalize the ID before upserting
      const normalizedId = this.normalizeTelegramSupergroupId(supergroupData.id);
      
      // Check for potential duplicates with different ID formats
      const originalId = supergroupData.id;
      if (originalId !== normalizedId) {
        // Delete any duplicate with the non-normalized ID if it exists
        await supabase
          .from('telegram_supergroups')
          .delete()
          .eq('id', originalId);
      }

      const upsertData = {
        id: normalizedId,
        title: supergroupData.title,
        username: supergroupData.username,
        description: supergroupData.description,
        invite_link: supergroupData.invite_link,
        member_count: supergroupData.member_count || 0,
        is_forum: supergroupData.is_forum || false,
        has_visible_history: supergroupData.has_visible_history ?? true,
        join_to_send_messages: supergroupData.join_to_send_messages ?? false,
        max_reaction_count: supergroupData.max_reaction_count ?? 11,
        accent_color_id: supergroupData.accent_color_id,
        company_id: supergroupData.company_id,
        group_type: supergroupData.group_type,
        bot_is_admin: supergroupData.bot_is_admin || false,
        metadata: supergroupData.metadata as any || {}
      };

      logger.info('Upserting supergroup with data', { 
        component: 'TelegramChatService',
        supergroupId: normalizedId,
        upsertData
      });

      const { data, error } = await supabase
        .from('telegram_supergroups')
        .upsert(upsertData, {
          onConflict: 'id'
        })
        .select()
        .single();

      if (error) {
        logger.error('Failed to upsert supergroup', error, { 
          component: 'TelegramChatService',
          supergroupId: normalizedId 
        });
        throw error;
      }

      return {
        ...data,
        metadata: data.metadata as Record<string, unknown> || {}
      } as TelegramSupergroup;
    } catch (error) {
      logger.error('Error upserting supergroup', error, { 
        component: 'TelegramChatService',
        supergroupId: supergroupData.id 
      });
      throw error;
    }
  }

  /**
   * Получить информацию о супергруппе
   */
  static async getSupergroupInfo(supergroupId: number): Promise<TelegramSupergroup | null> {
    try {
      const { data, error } = await supabase
        .from('telegram_supergroups')
        .select('*')
        .eq('id', supergroupId)
        .maybeSingle();

      if (error) {
        logger.error('Failed to fetch supergroup info', error, { 
          component: 'TelegramChatService',
          supergroupId 
        });
        return null;
      }

      return data ? {
        ...data,
        metadata: data.metadata as Record<string, unknown> || {}
      } as TelegramSupergroup : null;
    } catch (error) {
      logger.error('Error in getSupergroupInfo', error, { 
        component: 'TelegramChatService',
        supergroupId 
      });
      return null;
    }
  }

  /**
   * Проверить, является ли чат Telegram-синхронизированным
   */
  static isTelegramChat(chat: any): boolean {
    return !!(chat?.telegram_sync && chat?.telegram_supergroup_id);
  }

  /**
   * Получить отображаемое имя для Telegram пользователя
   */
  static getTelegramUserDisplayName(telegramUserData?: TelegramMessageData['telegram_user_data']): string {
    if (!telegramUserData) return 'Unknown User';
    
    const { first_name, last_name, username } = telegramUserData;
    
    if (first_name && last_name) {
      return `${first_name} ${last_name}`;
    }
    
    if (first_name) {
      return first_name;
    }
    
    if (username) {
      return `@${username}`;
    }
    
    return 'Unknown User';
  }

  /**
   * Обновить супергруппу
   */
  static async updateSupergroup(supergroupId: number, updates: Partial<TelegramSupergroup>): Promise<TelegramSupergroup> {
    try {
      // Clean the updates to match database types
      const cleanUpdates: any = {
        title: updates.title,
        description: updates.description,
        username: updates.username,
        invite_link: updates.invite_link,
        company_logo: updates.company_logo,
        company_id: updates.company_id,
        group_type: updates.group_type,
        is_active: updates.is_active, // Include is_active for archiving
      };

      logger.info('Updating supergroup with data', { 
        component: 'TelegramChatService',
        supergroupId,
        updates: cleanUpdates
      });

      // Only include metadata if it exists
      if (updates.metadata) {
        cleanUpdates.metadata = updates.metadata;
      }

      const { data, error } = await supabase
        .from('telegram_supergroups')
        .update(cleanUpdates)
        .eq('id', supergroupId)
        .select()
        .single();

      if (error) {
        logger.error('Failed to update supergroup', error, { 
          component: 'TelegramChatService',
          supergroupId 
        });
        throw error;
      }

      return {
        ...data,
        metadata: data.metadata as Record<string, unknown> || {}
      } as TelegramSupergroup;
    } catch (error) {
      logger.error('Error in updateSupergroup', error, { 
        component: 'TelegramChatService',
        supergroupId 
      });
      throw error;
    }
  }

  /**
   * Форматировать информацию о чате для отображения
   */
  static formatChatInfo(chat: any): { displayName: string; subtitle?: string; isTelegram: boolean } {
    const isTelegram = this.isTelegramChat(chat);
    
    if (!isTelegram) {
      return {
        displayName: chat.name || 'Unnamed Chat',
        isTelegram: false,
      };
    }

    let displayName = chat.name || 'Telegram Chat';
    let subtitle = undefined;

    // Добавляем индикатор темы для форум-групп
    if (chat.telegram_topic_id) {
      subtitle = `Topic #${chat.telegram_topic_id}`;
    }

    return {
      displayName,
      subtitle,
      isTelegram: true,
    };
  }

  /**
   * Получить данные tg_users по массиву telegram_user_id
   */
  static async getTgUsersByIds(telegramUserIds: number[]): Promise<any[]> {
    try {
      if (telegramUserIds.length === 0) return [];

      const { data, error } = await supabase
        .from('tg_users')
        .select('id, first_name, last_name, username, role_label')
        .in('id', telegramUserIds);

      if (error) {
        logger.error('Error fetching tg_users by ids', error);
        throw error;
      }

      return data || [];
    } catch (error) {
      logger.error('Failed to get tg_users by ids', error);
      throw error;
    }
  }

  /**
   * Обновить роль tg_user
   */
  static async updateTgUserRole(telegramUserId: number, roleLabel: string | null): Promise<boolean> {
    try {
      const { error } = await supabase
        .from('tg_users')
        .update({ role_label: roleLabel })
        .eq('id', telegramUserId);

      if (error) {
        logger.error('Error updating tg_user role', error, { telegramUserId, roleLabel });
        throw error;
      }

      logger.info('TG user role updated successfully', { telegramUserId, roleLabel });
      return true;
    } catch (error) {
      logger.error('Failed to update tg_user role', error);
      return false;
    }
  }
}
