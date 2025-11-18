// Stub service - will be replaced with Telegram domain API
// Reference: /reference/frontend_old/src/services/TelegramChatService.ts

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
  created_at: string;
  updated_at: string;
}

export interface TelegramGroupMember {
  id: string;
  supergroup_id: number;
  telegram_user_id: number;
  username?: string;
  first_name?: string;
  last_name?: string;
  is_bot: boolean;
  status: string;
  is_active: boolean;
}

class TelegramChatServiceClass {
  async getSupergroups(): Promise<TelegramSupergroup[]> {
    console.warn('[STUB] TelegramChatService.getSupergroups - Telegram domain not implemented yet');
    return [];
  }

  async getAllSupergroups(): Promise<TelegramSupergroup[]> {
    console.warn('[STUB] TelegramChatService.getAllSupergroups - Telegram domain not implemented yet');
    return [];
  }

  async getSupergroupById(id: number): Promise<TelegramSupergroup | null> {
    console.warn('[STUB] TelegramChatService.getSupergroupById - Telegram domain not implemented yet');
    return null;
  }

  async getSupergroupInfo(id: number): Promise<TelegramSupergroup | null> {
    console.warn('[STUB] TelegramChatService.getSupergroupInfo - Telegram domain not implemented yet');
    return null;
  }

  async getSupergroupMembers(supergroupId: number): Promise<TelegramGroupMember[]> {
    console.warn('[STUB] TelegramChatService.getSupergroupMembers - Telegram domain not implemented yet');
    return [];
  }

  async getSupergroupChatCounts(): Promise<Record<number, number>> {
    console.warn('[STUB] TelegramChatService.getSupergroupChatCounts - Telegram domain not implemented yet');
    return {};
  }

  async createSupergroup(data: Partial<TelegramSupergroup>): Promise<TelegramSupergroup | null> {
    console.warn('[STUB] TelegramChatService.createSupergroup - Telegram domain not implemented yet');
    return null;
  }

  async updateSupergroup(id: number, data: Partial<TelegramSupergroup>): Promise<TelegramSupergroup | null> {
    console.warn('[STUB] TelegramChatService.updateSupergroup - Telegram domain not implemented yet');
    return null;
  }

  async syncSupergroup(supergroupId: number): Promise<boolean> {
    console.warn('[STUB] TelegramChatService.syncSupergroup - Telegram domain not implemented yet');
    return false;
  }

  async getCompanySupergroups(companyId: number): Promise<TelegramSupergroup[]> {
    console.warn('[STUB] TelegramChatService.getCompanySupergroups - Telegram domain not implemented yet');
    return [];
  }

  async getTgUsersByIds(ids: number[]): Promise<TelegramGroupMember[]> {
    console.warn('[STUB] TelegramChatService.getTgUsersByIds - Telegram domain not implemented yet');
    return [];
  }

  async updateTgUserRole(supergroupId: number, userId: number, role: string): Promise<boolean> {
    console.warn('[STUB] TelegramChatService.updateTgUserRole - Telegram domain not implemented yet');
    return false;
  }

  getTelegramUserDisplayName(user: TelegramGroupMember | null): string {
    if (!user) return 'Unknown';
    return user.username || `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'Unknown';
  }

  isTelegramChat(chatId: string): boolean {
    return false;
  }

  formatChatInfo(chatId: string): string {
    return '';
  }
}

export const TelegramChatService = new TelegramChatServiceClass();
export default TelegramChatService;
