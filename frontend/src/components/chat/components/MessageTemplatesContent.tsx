import React, { useState, useEffect } from 'react';
import { Eye, Send, Package, DollarSign, Truck, MapPin, Star, Edit3, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Card } from '@/components/ui/card';
import { InlineChatTemplateEdit } from './InlineChatTemplateEdit';
import { useToast } from '@/hooks/use-toast';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { MessageTemplateService } from '@/services/MessageTemplateService';
import { supabase } from '@/integrations/supabase/client';
import type { MessageTemplate } from '@/utils/messageTemplates';

const CATEGORY_ICONS = {
  'основные': Star,
  'поиск товара': Package,
  'финансы': DollarSign,
  'логистика': Truck,
  'последняя миля': MapPin,
  'другое': Star,
} as const;

export const MessageTemplatesContent: React.FC = () => {
  const { sendInteractiveMessage, activeChat } = useRealtimeChatContext();
  const { toast } = useToast();
  const [editingTemplate, setEditingTemplate] = useState<MessageTemplate | null>(null);
  const [savedTemplateId, setSavedTemplateId] = useState<string | null>(null);
  const [templates, setTemplates] = useState<Record<string, MessageTemplate[]>>({});
  const [isLoading, setIsLoading] = useState(true);

  // Load templates from Supabase on component mount
  useEffect(() => {
    loadTemplatesFromSupabase();
    
    // Subscribe to realtime changes
    const channel = MessageTemplateService.subscribeToChanges(() => {
      loadTemplatesFromSupabase();
    });

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  const loadTemplatesFromSupabase = async () => {
    setIsLoading(true);
    try {
      const templatesData = await MessageTemplateService.getAllTemplates();
      setTemplates(templatesData);
    } catch (error) {
      
      toast({
        title: "Ошибка",
        description: "Не удалось загрузить шаблоны сообщений",
        variant: "error",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handlePreview = (template: MessageTemplate) => {
    // Send draft message event to chat interface
    window.dispatchEvent(new CustomEvent('showDraftMessage', { detail: template }));
  };

  const handleSend = async (template: MessageTemplate) => {
    // Проверяем, выбран ли чат
    if (!activeChat) {
      toast({
        title: "Выберите чат",
        description: "Для отправки шаблона необходимо выбрать чат в списке слева",
        variant: "error",
      });
      return;
    }

    try {
      
      await sendInteractiveMessage(template.template_data, template.name);
      toast({
        title: "Сообщение отправлено",
        description: `Шаблон "${template.name}" успешно отправлен`,
      });
    } catch (error) {
      
      toast({
        title: "Ошибка отправки",
        description: "Не удалось отправить сообщение",
        variant: "error",
      });
    }
  };

  const handleEdit = (template: MessageTemplate) => {
    
    setEditingTemplate(template);
  };

  const handleSaveTemplate = async (updatedTemplate: MessageTemplate) => {
    try {
      const success = await MessageTemplateService.updateTemplate(updatedTemplate.id, updatedTemplate);
      
      if (success) {
        toast({
          title: "Шаблон сохранен",
          description: "Изменения успешно сохранены",
        });
        
        // Show visual feedback
        setSavedTemplateId(updatedTemplate.id);
        setTimeout(() => setSavedTemplateId(null), 2000);
        
        // Reload templates to get fresh data
        await loadTemplatesFromSupabase();
      } else {
        throw new Error('Failed to update template');
      }
    } catch (error) {
      
      toast({
        title: "Ошибка",
        description: "Не удалось сохранить изменения",
        variant: "error",
      });
    }
    
    setEditingTemplate(null);
  };

  const handleCloseEdit = () => {
    setEditingTemplate(null);
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
          <p className="text-sm text-muted-foreground">Загрузка шаблонов...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <ScrollArea className="h-full">
        <div className="p-4 space-y-4">
          {Object.entries(templates).map(([categoryKey, categoryTemplates]) => {
            const IconComponent = CATEGORY_ICONS[categoryKey as keyof typeof CATEGORY_ICONS];
            
            return (
              <div key={categoryKey}>
                <div className="flex items-center gap-2 mb-3">
                  <IconComponent size={16} className="text-accent-red" />
                  <h4 className="text-sm font-medium text-white capitalize">
                    {categoryKey === 'поиск товара' ? 'Поиск' : categoryKey}
                  </h4>
                </div>
                
                <div className="space-y-2 ml-6">
                  {categoryTemplates.map((template) => (
                    <div key={template.id}>
                      <Card className="p-3 bg-dark-gray/50 border-white/10">
                        <div className="flex items-center justify-between">
                          <div className="flex-1 min-w-0">
                            <h5 className="text-sm font-medium text-white truncate">
                              {template.name}
                            </h5>
                            <p className="text-xs text-gray-400 truncate">
                              {template.description}
                            </p>
                          </div>
                          
                          <div className="flex gap-1 ml-2">
                            {/* Preview Button */}
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-8 w-8 p-0 rounded-full hover:bg-white/10"
                              onClick={() => handlePreview(template)}
                            >
                              <Eye size={14} className="text-gray-400" />
                            </Button>
                            
                            {/* Send Button */}
                            <Button
                              size="sm"
                              className="h-8 w-8 p-0 rounded-full bg-accent-red hover:bg-accent-red/90"
                              onClick={() => handleSend(template)}
                            >
                              <Send size={14} />
                            </Button>
                            
                            {/* Saved indicator */}
                            {savedTemplateId === template.id && (
                              <div className="h-8 w-8 flex items-center justify-center rounded-full bg-green-600">
                                <Check size={14} className="text-white" />
                              </div>
                            )}
                          </div>
                        </div>
                      </Card>
                    </div>
                  ))}
                </div>
                
                {/* Separator between categories */}
                <Separator className="mt-4 bg-white/10" />
              </div>
            );
          })}
        </div>
      </ScrollArea>

      {/* Inline Template Edit */}
      <InlineChatTemplateEdit
        template={editingTemplate}
        isOpen={!!editingTemplate}
        onClose={handleCloseEdit}
        onSave={handleSaveTemplate}
      />
    </>
  );
};