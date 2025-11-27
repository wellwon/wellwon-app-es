import { useState, useEffect } from 'react';
import { MessageTemplate } from '@/utils/messageTemplates';
import { MessageTemplateService } from '@/services/MessageTemplateService';
import { supabase } from '@/integrations/supabase/client';
import { logger } from '@/utils/logger';

export const useMessageTemplates = () => {
  const [templates, setTemplates] = useState<Record<string, MessageTemplate[]>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadTemplates = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const templatesData = await MessageTemplateService.getAllTemplates();
      setTemplates(templatesData);
    } catch (err) {
      logger.error('Error loading templates', err, { component: 'useMessageTemplates' });
      setError('Не удалось загрузить шаблоны сообщений');
    } finally {
      setIsLoading(false);
    }
  };

  const updateTemplate = async (templateId: string, updatedTemplate: MessageTemplate): Promise<boolean> => {
    try {
      const success = await MessageTemplateService.updateTemplate(templateId, updatedTemplate);
      if (success) {
        await loadTemplates(); // Reload templates after update
      }
      return success;
    } catch (err) {
      logger.error('Error updating template', err, { component: 'useMessageTemplates' });
      return false;
    }
  };

  const createTemplate = async (template: Omit<MessageTemplate, 'id'>): Promise<string | null> => {
    try {
      const templateId = await MessageTemplateService.createTemplate(template);
      if (templateId) {
        await loadTemplates(); // Reload templates after creation
      }
      return templateId;
    } catch (err) {
      logger.error('Error creating template', err, { component: 'useMessageTemplates' });
      return null;
    }
  };

  const deleteTemplate = async (templateId: string): Promise<boolean> => {
    try {
      const success = await MessageTemplateService.deleteTemplate(templateId);
      if (success) {
        await loadTemplates(); // Reload templates after deletion
      }
      return success;
    } catch (err) {
      logger.error('Error deleting template', err, { component: 'useMessageTemplates' });
      return false;
    }
  };

  useEffect(() => {
    loadTemplates();
    
    // Subscribe to realtime changes
    const channel = MessageTemplateService.subscribeToChanges(() => {
      loadTemplates();
    });

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  return {
    templates,
    isLoading,
    error,
    loadTemplates,
    updateTemplate,
    createTemplate,
    deleteTemplate,
  };
};