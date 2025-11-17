import { supabase } from '@/integrations/supabase/client';
import { MessageTemplate } from '@/utils/messageTemplates';
import { logger } from '@/utils/logger';

export interface SupabaseMessageTemplate {
  id: string;
  name: string;
  description: string | null;
  category: string;
  template_data: {
    type: string;
    title: string;
    description: string;
    image_url?: string;
    image_position?: 'left' | 'right';
    buttons: Array<{
      text: string;
      action: string;
      style?: string;
    }>;
  };
  image_url: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

export class MessageTemplateService {
  // Загрузить все активные шаблоны
  static async getAllTemplates(): Promise<Record<string, MessageTemplate[]>> {
    try {
      const { data, error } = await supabase
        .from('message_templates')
        .select('*')
        .eq('is_active', true)
        .order('name', { ascending: true });

      if (error) throw error;

      // Преобразуем в формат, ожидаемый приложением
      const templatesByCategory: Record<string, MessageTemplate[]> = {};
      
      // Custom sorting order for categories
      const categoryOrder = ['основные', 'поиск товара', 'финансы', 'логистика', 'последняя миля', 'другое'];
      
      data?.forEach((template: SupabaseMessageTemplate) => {
        const messageTemplate: MessageTemplate = {
          id: template.id,
          name: template.name,
          description: template.description || '',
          category: template.category,
          template_data: {
            type: template.template_data.type,
            title: template.template_data.title,
            description: template.template_data.description,
            image_url: template.image_url || template.template_data.image_url,
            image_position: template.template_data.image_position as 'left' | 'right' | undefined,
            buttons: template.template_data.buttons.map(button => ({
              text: button.text,
              action: button.action,
              style: button.style
            }))
          }
        };

        if (!templatesByCategory[template.category]) {
          templatesByCategory[template.category] = [];
        }
        templatesByCategory[template.category].push(messageTemplate);
      });

      // Sort categories according to custom order
      const sortedTemplatesByCategory: Record<string, MessageTemplate[]> = {};
      categoryOrder.forEach(category => {
        if (templatesByCategory[category]) {
          sortedTemplatesByCategory[category] = templatesByCategory[category];
        }
      });
      
      // Add any remaining categories not in the predefined order
      Object.keys(templatesByCategory).forEach(category => {
        if (!categoryOrder.includes(category)) {
          sortedTemplatesByCategory[category] = templatesByCategory[category];
        }
      });

      return sortedTemplatesByCategory;
    } catch (error) {
      logger.error('Error loading templates', error, { component: 'MessageTemplateService' });
      return {};
    }
  }

  // Сохранить обновленный шаблон
  static async updateTemplate(templateId: string, updatedTemplate: MessageTemplate): Promise<boolean> {
    try {
      // Принудительно обновляем сессию перед операцией
      const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
      
      if (sessionError || !sessionData.session) {
        logger.error('Session error in template update', sessionError, { component: 'MessageTemplateService' });
        throw new Error('Сессия истекла. Пожалуйста, перезайдите в систему');
      }

      // Дополнительная проверка текущего пользователя
      const { data: { user }, error: authError } = await supabase.auth.getUser();
      
      if (authError || !user) {
        logger.error('Authentication error in template update', authError, { component: 'MessageTemplateService' });
        throw new Error('Необходимо войти в систему для сохранения шаблонов');
      }

      logger.debug('Template update authentication successful', {
        userEmail: user.email,
        sessionExpiry: sessionData.session.expires_at,
        userId: sessionData.session.user.id,
        templateId,
        component: 'MessageTemplateService'
      });
      
      // Подготавливаем данные для обновления
      const updateData = {
        name: updatedTemplate.name,
        description: updatedTemplate.description,
        category: updatedTemplate.category,
        template_data: {
          ...updatedTemplate.template_data,
          // Убеждаемся, что image_url в template_data синхронизирован
          image_url: updatedTemplate.template_data.image_url
        },
        image_url: updatedTemplate.template_data.image_url || null,
        updated_at: new Date().toISOString()
      };
      
      logger.debug('Sending template update to Supabase', { updateData, component: 'MessageTemplateService' });

      const { data, error } = await supabase
        .from('message_templates')
        .update(updateData)
        .eq('id', templateId)
        .select();

      if (data) logger.debug('Template update response received', { data, component: 'MessageTemplateService' });
      if (error) logger.error('Template update database error', error, { component: 'MessageTemplateService' });

      if (error) {
        // Детальный анализ ошибки
        if (error.code === 'PGRST116' || error.message.includes('RLS')) {
          throw new Error('Недостаточно прав для изменения этого шаблона');
        }
        throw error;
      }
      
      logger.info('Template successfully updated in database', { templateId, component: 'MessageTemplateService' });
      return true;
    } catch (error) {
      logger.error('Error updating template', error, { templateId, component: 'MessageTemplateService' });
      throw error;
    }
  }

  // Создать новый шаблон
  static async createTemplate(template: Omit<MessageTemplate, 'id'>): Promise<string | null> {
    try {
      const { data, error } = await supabase
        .from('message_templates')
        .insert({
          name: template.name,
          description: template.description,
          category: template.category,
          template_data: template.template_data,
          image_url: template.template_data.image_url || null,
          created_by: (await supabase.auth.getUser()).data.user?.id || null
        })
        .select('id')
        .single();

      if (error) throw error;
      return data?.id || null;
    } catch (error) {
      logger.error('Error creating template', error, { component: 'MessageTemplateService' });
      return null;
    }
  }

  // Деактивировать шаблон
  static async deleteTemplate(templateId: string): Promise<boolean> {
    try {
      const { error } = await supabase
        .from('message_templates')
        .update({ is_active: false })
        .eq('id', templateId);

      if (error) throw error;
      return true;
    } catch (error) {
      logger.error('Error deleting template', error, { component: 'MessageTemplateService' });
      return false;
    }
  }

  // Подписка на изменения шаблонов
  static subscribeToChanges(callback: (payload: any) => void) {
    return supabase
      .channel('message_templates_changes')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'message_templates'
        },
        callback
      )
      .subscribe();
  }
}