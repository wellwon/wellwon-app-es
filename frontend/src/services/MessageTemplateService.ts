// Stub service - will be replaced with Template domain API
// Reference: /reference/frontend_old/src/services/MessageTemplateService.ts

export interface MessageTemplate {
  id: string;
  name: string;
  description?: string;
  category: string;
  template_data: Record<string, unknown>;
  image_url?: string;
  created_by: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

class MessageTemplateServiceClass {
  async getTemplates(): Promise<MessageTemplate[]> {
    console.warn('[STUB] MessageTemplateService.getTemplates - Template domain not implemented yet');
    return [];
  }

  async getTemplatesByCategory(category: string): Promise<MessageTemplate[]> {
    console.warn('[STUB] MessageTemplateService.getTemplatesByCategory - Template domain not implemented yet');
    return [];
  }

  async getTemplateById(id: string): Promise<MessageTemplate | null> {
    console.warn('[STUB] MessageTemplateService.getTemplateById - Template domain not implemented yet');
    return null;
  }

  async createTemplate(data: Partial<MessageTemplate>): Promise<MessageTemplate | null> {
    console.warn('[STUB] MessageTemplateService.createTemplate - Template domain not implemented yet');
    return null;
  }

  async getAllTemplates(): Promise<MessageTemplate[]> {
    console.warn('[STUB] MessageTemplateService.getAllTemplates - Template domain not implemented yet');
    return [];
  }

  async updateTemplate(id: string, data: Partial<MessageTemplate>): Promise<MessageTemplate | null> {
    console.warn('[STUB] MessageTemplateService.updateTemplate - Template domain not implemented yet');
    return null;
  }

  async deleteTemplate(id: string): Promise<boolean> {
    console.warn('[STUB] MessageTemplateService.deleteTemplate - Template domain not implemented yet');
    return false;
  }

  subscribeToChanges(callback: (templates: MessageTemplate[]) => void): () => void {
    console.warn('[STUB] MessageTemplateService.subscribeToChanges - Template domain not implemented yet');
    return () => {};
  }
}

export const MessageTemplateService = new MessageTemplateServiceClass();
export default MessageTemplateService;
