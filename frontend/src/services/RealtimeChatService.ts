// =============================================================================
// File: src/services/RealtimeChatService.ts
// Description: Chat Service using Backend API (no Supabase)
// Architecture: Thin client - all logic on backend
// =============================================================================

import * as chatApi from '@/api/chat';
import { logger } from '@/utils/logger';

// Re-export types from API for backward compatibility
export type Chat = chatApi.ChatDetail & {
  // Extended fields for UI
  telegram_supergroup_id?: number;
  participants?: ChatParticipant[];
  metadata?: Record<string, unknown>;
};

export type Message = chatApi.Message;

export type ChatParticipant = chatApi.ChatParticipant;

/**
 * RealtimeChatService - Wrapper around Chat API
 *
 * This service provides a consistent interface for chat operations.
 * All business logic is on the backend - this is a thin API client.
 *
 * Real-time updates come through WSE (WebSocket Engine), not through this service.
 * Use useWSEQuery hook for reactive data fetching with WSE invalidation.
 */
class RealtimeChatServiceClass {
  // ---------------------------------------------------------------------------
  // Chat Operations
  // ---------------------------------------------------------------------------

  async getChats(userId: string): Promise<Chat[]> {
    try {
      const chats = await chatApi.getChats(false, 100, 0);
      return chats as Chat[];
    } catch (error) {
      logger.error('Failed to get chats', error, { component: 'RealtimeChatService' });
      return [];
    }
  }

  async getUserChats(userId: string, companyId: string | null): Promise<Chat[]> {
    try {
      if (companyId) {
        const chats = await chatApi.getCompanyChats(companyId, false, 100, 0);
        return chats as Chat[];
      }
      const chats = await chatApi.getChats(false, 100, 0);
      return chats as Chat[];
    } catch (error) {
      logger.error('Failed to get user chats', error, { component: 'RealtimeChatService' });
      return [];
    }
  }

  async getUserChatsBySupergroup(userId: string, supergroupId: number): Promise<Chat[]> {
    try {
      // Filter chats by telegram supergroup ID
      const allChats = await chatApi.getChats(false, 100, 0);
      return allChats.filter(chat =>
        chat.telegram_chat_id === -supergroupId ||
        chat.telegram_chat_id === supergroupId
      ) as Chat[];
    } catch (error) {
      logger.error('Failed to get chats by supergroup', error, { component: 'RealtimeChatService' });
      return [];
    }
  }

  async getChatById(chatId: string): Promise<Chat | null> {
    try {
      const chat = await chatApi.getChatById(chatId);
      return chat as Chat;
    } catch (error) {
      logger.error('Failed to get chat', error, { component: 'RealtimeChatService', chatId });
      return null;
    }
  }

  async createChat(
    name: string,
    type: string,
    userId: string,
    participantIds: string[],
    companyId?: string
  ): Promise<Chat | null> {
    try {
      const response = await chatApi.createChat({
        name: name || undefined,
        chat_type: type,
        company_id: companyId,
        participant_ids: participantIds,
      });

      // Fetch the created chat
      const chat = await this.getChatById(response.id);
      return chat;
    } catch (error) {
      logger.error('Failed to create chat', error, { component: 'RealtimeChatService' });
      return null;
    }
  }

  async updateChat(chatId: string, name: string, _description: string): Promise<void> {
    try {
      await chatApi.updateChat(chatId, { name });
    } catch (error) {
      logger.error('Failed to update chat', error, { component: 'RealtimeChatService', chatId });
      throw error;
    }
  }

  async deleteChat(chatId: string): Promise<void> {
    try {
      await chatApi.archiveChat(chatId);
    } catch (error) {
      logger.error('Failed to delete chat', error, { component: 'RealtimeChatService', chatId });
      throw error;
    }
  }

  // ---------------------------------------------------------------------------
  // Message Operations
  // ---------------------------------------------------------------------------

  async getMessages(chatId: string, limit: number = 50): Promise<Message[]> {
    try {
      return await chatApi.getMessages(chatId, { limit });
    } catch (error) {
      logger.error('Failed to get messages', error, { component: 'RealtimeChatService', chatId });
      return [];
    }
  }

  async getChatMessages(chatId: string, limit: number, offset: number): Promise<Message[]> {
    try {
      return await chatApi.getMessages(chatId, { limit, offset });
    } catch (error) {
      logger.error('Failed to get chat messages', error, { component: 'RealtimeChatService', chatId });
      return [];
    }
  }

  async getChatMessagesFiltered(
    chatId: string,
    filter: string,
    limit: number,
    offset: number
  ): Promise<Message[]> {
    try {
      // Use search for filtered messages
      if (filter && filter !== 'all') {
        return await chatApi.searchMessages(chatId, filter, limit);
      }
      return await chatApi.getMessages(chatId, { limit, offset });
    } catch (error) {
      logger.error('Failed to get filtered messages', error, { component: 'RealtimeChatService', chatId });
      return [];
    }
  }

  async getMessageMeta(messageId: string): Promise<Message | null> {
    // Message metadata is included in message fetch
    logger.debug('getMessageMeta called - use getMessages instead', { messageId });
    return null;
  }

  async countMessagesNewerThan(chatId: string, timestamp: string): Promise<number> {
    try {
      // Get recent messages and count
      const messages = await chatApi.getMessages(chatId, { limit: 100 });
      const newerMessages = messages.filter(m => new Date(m.created_at) > new Date(timestamp));
      return newerMessages.length;
    } catch (error) {
      logger.error('Failed to count newer messages', error, { component: 'RealtimeChatService', chatId });
      return 0;
    }
  }

  async sendMessage(chatId: string, content: string, type: string = 'text'): Promise<Message | null> {
    try {
      const response = await chatApi.sendMessage(chatId, {
        content,
        message_type: type,
      });

      // Return a partial message object for optimistic UI
      return {
        id: response.id,
        chat_id: chatId,
        content,
        message_type: type,
        created_at: new Date().toISOString(),
      } as Message;
    } catch (error) {
      logger.error('Failed to send message', error, { component: 'RealtimeChatService', chatId });
      return null;
    }
  }

  async sendTextMessage(
    chatId: string,
    userId: string,
    content: string,
    replyToId?: string
  ): Promise<Message | null> {
    try {
      const response = await chatApi.sendMessage(chatId, {
        content,
        message_type: 'text',
        reply_to_id: replyToId,
      });

      return {
        id: response.id,
        chat_id: chatId,
        sender_id: userId,
        content,
        message_type: 'text',
        reply_to_id: replyToId || null,
        created_at: new Date().toISOString(),
      } as Message;
    } catch (error) {
      logger.error('Failed to send text message', error, { component: 'RealtimeChatService', chatId });
      throw error;
    }
  }

  async sendFileMessage(
    chatId: string,
    userId: string,
    file: File,
    replyToId?: string
  ): Promise<Message | null> {
    try {
      // First, upload the file
      const uploadResult = await chatApi.uploadChatFile(chatId, file);

      if (!uploadResult.success || !uploadResult.file_url) {
        logger.error('Failed to upload file', { error: uploadResult.error }, { component: 'RealtimeChatService' });
        throw new Error(uploadResult.error || 'Failed to upload file');
      }

      // Then send the message with file info
      const response = await chatApi.sendMessage(chatId, {
        content: file.name,
        message_type: 'file',
        reply_to_id: replyToId,
        file_url: uploadResult.file_url,
        file_name: uploadResult.file_name,
        file_size: uploadResult.file_size,
        file_type: uploadResult.file_type,
      });

      return {
        id: response.id,
        chat_id: chatId,
        sender_id: userId,
        content: file.name,
        message_type: 'file',
        reply_to_id: replyToId || null,
        file_url: uploadResult.file_url || null,
        file_name: uploadResult.file_name || null,
        file_size: uploadResult.file_size || null,
        file_type: uploadResult.file_type || null,
        created_at: new Date().toISOString(),
      } as Message;
    } catch (error) {
      logger.error('Failed to send file message', error, { component: 'RealtimeChatService', chatId });
      throw error;
    }
  }

  async sendVoiceMessage(
    chatId: string,
    userId: string,
    audioBlob: Blob,
    duration: number,
    replyToId?: string
  ): Promise<Message | null> {
    try {
      // First, upload the voice message
      const uploadResult = await chatApi.uploadVoiceMessage(chatId, audioBlob, duration);

      if (!uploadResult.success || !uploadResult.file_url) {
        logger.error('Failed to upload voice message', { error: uploadResult.error }, { component: 'RealtimeChatService' });
        throw new Error(uploadResult.error || 'Failed to upload voice message');
      }

      // Then send the message with voice info
      const response = await chatApi.sendMessage(chatId, {
        content: 'Voice message',
        message_type: 'voice',
        reply_to_id: replyToId,
        file_url: uploadResult.file_url,
        voice_duration: uploadResult.duration || duration,
      });

      return {
        id: response.id,
        chat_id: chatId,
        sender_id: userId,
        content: 'Voice message',
        message_type: 'voice',
        reply_to_id: replyToId || null,
        file_url: uploadResult.file_url || null,
        voice_duration: uploadResult.duration || duration,
        created_at: new Date().toISOString(),
      } as Message;
    } catch (error) {
      logger.error('Failed to send voice message', error, { component: 'RealtimeChatService', chatId });
      throw error;
    }
  }

  async sendInteractiveMessage(
    chatId: string,
    userId: string,
    interactiveData: unknown,
    title?: string
  ): Promise<Message | null> {
    try {
      const content = JSON.stringify({ type: 'interactive', data: interactiveData, title });
      const response = await chatApi.sendMessage(chatId, {
        content,
        message_type: 'interactive',
      });

      return {
        id: response.id,
        chat_id: chatId,
        sender_id: userId,
        content,
        message_type: 'interactive',
        created_at: new Date().toISOString(),
      } as Message;
    } catch (error) {
      logger.error('Failed to send interactive message', error, { component: 'RealtimeChatService', chatId });
      throw error;
    }
  }

  // ---------------------------------------------------------------------------
  // Participant Operations
  // ---------------------------------------------------------------------------

  async getChatParticipants(chatId: string): Promise<ChatParticipant[]> {
    try {
      return await chatApi.getParticipants(chatId, false);
    } catch (error) {
      logger.error('Failed to get participants', error, { component: 'RealtimeChatService', chatId });
      return [];
    }
  }

  async addParticipants(chatId: string, userIds: string[]): Promise<void> {
    try {
      await Promise.all(
        userIds.map(userId => chatApi.addParticipant(chatId, { user_id: userId }))
      );
    } catch (error) {
      logger.error('Failed to add participants', error, { component: 'RealtimeChatService', chatId });
      throw error;
    }
  }

  // ---------------------------------------------------------------------------
  // Read Status & Typing
  // ---------------------------------------------------------------------------

  async markAsRead(messageId: string, userId: string): Promise<void> {
    // Note: Backend expects chat_id, not message_id directly
    // This is handled through mark messages as read endpoint
    logger.debug('markAsRead called', { messageId, userId });
  }

  async startTyping(chatId: string, userId: string): Promise<void> {
    try {
      await chatApi.startTyping(chatId);
    } catch (error) {
      // Typing errors are non-critical
      logger.debug('Failed to send typing start', { chatId });
    }
  }

  async stopTyping(chatId: string, userId: string): Promise<void> {
    try {
      await chatApi.stopTyping(chatId);
    } catch (error) {
      // Typing errors are non-critical
      logger.debug('Failed to send typing stop', { chatId });
    }
  }

  // ---------------------------------------------------------------------------
  // Realtime Subscriptions (WSE-based)
  // ---------------------------------------------------------------------------
  // NOTE: Real-time updates are now handled through WSE (WebSocket Engine)
  // These methods are kept for backward compatibility but delegate to WSE

  subscribeToChat(chatId: string, callbacks: {
    onMessage?: (message: Message) => void;
    onTyping?: (userId: string) => void;
    onRead?: (userId: string, messageIds: string[]) => void;
  }): () => void {
    logger.debug('subscribeToChat - use WSE hooks instead', { chatId });

    // Return cleanup function
    return () => {
      logger.debug('Unsubscribed from chat', { chatId });
    };
  }

  unsubscribeFromChat(chatId: string): void {
    logger.debug('unsubscribeFromChat - handled by WSE', { chatId });
  }

  subscribeToChatsUpdates(
    userId: string,
    companyId: string | null,
    callbacks: {
      onChatUpdate?: (chat: Chat) => void;
      onChatCreate?: (chat: Chat) => void;
      onChatDelete?: (chat: Chat) => void;
      onNewMessage?: (chatId: string, message: Message) => void;
    },
    supergroupId?: number | null
  ): { unsubscribe: () => void } {
    logger.debug('subscribeToChatsUpdates - use WSE hooks instead', { userId, companyId });

    return {
      unsubscribe: () => {
        logger.debug('Unsubscribed from chats updates');
      }
    };
  }

  unsubscribeFromChatsUpdates(): void {
    logger.debug('unsubscribeFromChatsUpdates - handled by WSE');
  }
}

export const RealtimeChatService = new RealtimeChatServiceClass();
// Legacy export for backward compatibility
export const realtimeChatService = RealtimeChatService;
export default RealtimeChatService;
