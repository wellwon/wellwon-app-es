// Stub service - will be replaced with Chat domain + WSE
// Reference: /reference/frontend_old/src/services/RealtimeChatService.ts

export interface Chat {
  id: string;
  name?: string;
  type: 'direct' | 'group' | 'company' | 'telegram_group';
  company_id?: string;
  created_by: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  chat_id: string;
  sender_id: string;
  content: string;
  message_type: 'text' | 'file' | 'voice' | 'image' | 'system';
  file_url?: string;
  file_name?: string;
  reply_to_id?: string;
  is_edited: boolean;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChatParticipant {
  id: string;
  chat_id: string;
  user_id: string;
  role: 'member' | 'admin' | 'observer';
  joined_at: string;
  last_read_at?: string;
  is_active: boolean;
}

class RealtimeChatServiceClass {
  async getChats(userId: string): Promise<Chat[]> {
    console.warn('[STUB] RealtimeChatService.getChats - Chat domain not implemented yet');
    return [];
  }

  async getUserChats(userId: string, companyId: string | null): Promise<Chat[]> {
    console.warn('[STUB] RealtimeChatService.getUserChats - Chat domain not implemented yet');
    return [];
  }

  async getUserChatsBySupergroup(userId: string, supergroupId: number): Promise<Chat[]> {
    console.warn('[STUB] RealtimeChatService.getUserChatsBySupergroup - Chat domain not implemented yet');
    return [];
  }

  async getChatById(chatId: string): Promise<Chat | null> {
    console.warn('[STUB] RealtimeChatService.getChatById - Chat domain not implemented yet');
    return null;
  }

  async getMessages(chatId: string, limit?: number): Promise<Message[]> {
    console.warn('[STUB] RealtimeChatService.getMessages - Chat domain not implemented yet');
    return [];
  }

  async getChatMessages(chatId: string, limit: number, offset: number): Promise<Message[]> {
    console.warn('[STUB] RealtimeChatService.getChatMessages - Chat domain not implemented yet');
    return [];
  }

  async getChatMessagesFiltered(chatId: string, filter: string, limit: number, offset: number): Promise<Message[]> {
    console.warn('[STUB] RealtimeChatService.getChatMessagesFiltered - Chat domain not implemented yet');
    return [];
  }

  async getMessageMeta(messageId: string): Promise<any> {
    console.warn('[STUB] RealtimeChatService.getMessageMeta - Chat domain not implemented yet');
    return null;
  }

  async countMessagesNewerThan(chatId: string, timestamp: string): Promise<number> {
    console.warn('[STUB] RealtimeChatService.countMessagesNewerThan - Chat domain not implemented yet');
    return 0;
  }

  async sendMessage(chatId: string, content: string, type?: string): Promise<Message | null> {
    console.warn('[STUB] RealtimeChatService.sendMessage - Chat domain not implemented yet');
    return null;
  }

  async sendTextMessage(chatId: string, userId: string, content: string, replyToId?: string): Promise<Message> {
    console.warn('[STUB] RealtimeChatService.sendTextMessage - Chat domain not implemented yet');
    return null as any;
  }

  async sendFileMessage(chatId: string, userId: string, file: File, replyToId?: string): Promise<Message> {
    console.warn('[STUB] RealtimeChatService.sendFileMessage - Chat domain not implemented yet');
    return null as any;
  }

  async sendVoiceMessage(chatId: string, userId: string, audioBlob: Blob, duration: number, replyToId?: string): Promise<Message> {
    console.warn('[STUB] RealtimeChatService.sendVoiceMessage - Chat domain not implemented yet');
    return null as any;
  }

  async sendInteractiveMessage(chatId: string, userId: string, interactiveData: any, title?: string): Promise<Message> {
    console.warn('[STUB] RealtimeChatService.sendInteractiveMessage - Chat domain not implemented yet');
    return null as any;
  }

  async createChat(name: string, type: string, userId: string, participantIds: string[], companyId?: string): Promise<Chat> {
    console.warn('[STUB] RealtimeChatService.createChat - Chat domain not implemented yet');
    return null as any;
  }

  async updateChat(chatId: string, name: string, description: string): Promise<void> {
    console.warn('[STUB] RealtimeChatService.updateChat - Chat domain not implemented yet');
  }

  async deleteChat(chatId: string): Promise<void> {
    console.warn('[STUB] RealtimeChatService.deleteChat - Chat domain not implemented yet');
  }

  async addParticipants(chatId: string, userIds: string[]): Promise<void> {
    console.warn('[STUB] RealtimeChatService.addParticipants - Chat domain not implemented yet');
  }

  async getChatParticipants(chatId: string): Promise<ChatParticipant[]> {
    console.warn('[STUB] RealtimeChatService.getChatParticipants - Chat domain not implemented yet');
    return [];
  }

  async markAsRead(messageId: string, userId: string): Promise<void> {
    console.warn('[STUB] RealtimeChatService.markAsRead - Chat domain not implemented yet');
  }

  async startTyping(chatId: string, userId: string): Promise<void> {
    console.warn('[STUB] RealtimeChatService.startTyping - Chat domain not implemented yet');
  }

  async stopTyping(chatId: string, userId: string): Promise<void> {
    console.warn('[STUB] RealtimeChatService.stopTyping - Chat domain not implemented yet');
  }

  subscribeToChat(chatId: string, callbacks: any): () => void {
    console.warn('[STUB] RealtimeChatService.subscribeToChat - Use WSE instead');
    return () => {};
  }

  unsubscribeFromChat(chatId: string): void {
    console.warn('[STUB] RealtimeChatService.unsubscribeFromChat - Use WSE instead');
  }

  subscribeToChatsUpdates(userId: string, companyId: string | null, callbacks: any, supergroupId?: number | null): any {
    console.warn('[STUB] RealtimeChatService.subscribeToChatsUpdates - Use WSE instead');
    return {};
  }

  unsubscribeFromChatsUpdates(): void {
    console.warn('[STUB] RealtimeChatService.unsubscribeFromChatsUpdates - Use WSE instead');
  }
}

export const RealtimeChatService = new RealtimeChatServiceClass();
// Legacy export for backward compatibility
export const realtimeChatService = RealtimeChatService;
export default RealtimeChatService;
