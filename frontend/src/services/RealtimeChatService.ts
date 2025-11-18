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

  async getChatById(chatId: string): Promise<Chat | null> {
    console.warn('[STUB] RealtimeChatService.getChatById - Chat domain not implemented yet');
    return null;
  }

  async getMessages(chatId: string, limit?: number): Promise<Message[]> {
    console.warn('[STUB] RealtimeChatService.getMessages - Chat domain not implemented yet');
    return [];
  }

  async sendMessage(chatId: string, content: string, type?: string): Promise<Message | null> {
    console.warn('[STUB] RealtimeChatService.sendMessage - Chat domain not implemented yet');
    return null;
  }

  async createChat(name: string, type: string, participantIds: string[]): Promise<Chat | null> {
    console.warn('[STUB] RealtimeChatService.createChat - Chat domain not implemented yet');
    return null;
  }

  async getChatParticipants(chatId: string): Promise<ChatParticipant[]> {
    console.warn('[STUB] RealtimeChatService.getChatParticipants - Chat domain not implemented yet');
    return [];
  }

  async markAsRead(chatId: string, messageId: string): Promise<boolean> {
    console.warn('[STUB] RealtimeChatService.markAsRead - Chat domain not implemented yet');
    return false;
  }

  subscribeToChat(chatId: string, callback: (message: Message) => void): () => void {
    console.warn('[STUB] RealtimeChatService.subscribeToChat - Use WSE instead');
    return () => {};
  }
}

export const RealtimeChatService = new RealtimeChatServiceClass();
// Legacy export for backward compatibility
export const realtimeChatService = RealtimeChatService;
export default RealtimeChatService;
