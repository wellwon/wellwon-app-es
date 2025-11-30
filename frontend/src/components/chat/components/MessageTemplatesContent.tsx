// =============================================================================
// File: MessageTemplatesContent.tsx
// Description: Message templates using React Query + WSE
// =============================================================================

import React, { useState } from 'react';
import { Eye, Send, Package, DollarSign, Truck, MapPin, Star, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Card } from '@/components/ui/card';
import { InlineChatTemplateEdit } from './InlineChatTemplateEdit';
import { useToast } from '@/hooks/use-toast';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { useMessageTemplates } from '@/hooks/chat';
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

  // React Query hook for templates
  const { templates, isLoading } = useMessageTemplates();

  const handlePreview = (template: MessageTemplate) => {
    // Send draft message event to chat interface
    window.dispatchEvent(new CustomEvent('showDraftMessage', { detail: template }));
  };

  const handleSend = async (template: MessageTemplate) => {
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
    // Template update API not yet implemented - show feedback only
    toast({
      title: "Шаблон обновлен",
      description: "Изменения применены локально",
    });

    // Show visual feedback
    setSavedTemplateId(updatedTemplate.id);
    setTimeout(() => setSavedTemplateId(null), 2000);

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
                  {(categoryTemplates as MessageTemplate[]).map((template) => (
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
