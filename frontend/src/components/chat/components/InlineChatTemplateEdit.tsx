import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Save, X, RotateCcw } from 'lucide-react';
import { ButtonEditor } from './ButtonEditor';
import { ImagePositionSelector } from './ImagePositionSelector';
import { GlassCard } from '@/components/design-system/GlassCard';
import { useToast } from '@/hooks/use-toast';
import { uploadImageToStorage, deleteImageFromStorage } from './ImageUploadService';
import type { MessageTemplate } from '@/utils/messageTemplates';

interface InlineChatTemplateEditProps {
  template: MessageTemplate | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (updatedTemplate: MessageTemplate) => void;
  onChange?: (updatedTemplate: MessageTemplate) => void;
}

export const InlineChatTemplateEdit: React.FC<InlineChatTemplateEditProps> = ({
  template,
  isOpen,
  onClose,
  onSave,
  onChange
}) => {
  const { toast } = useToast();
  const [editedTemplate, setEditedTemplate] = useState<MessageTemplate | null>(null);
  const [originalImageUrl, setOriginalImageUrl] = useState<string | undefined>();
  const [baselineTemplate, setBaselineTemplate] = useState<MessageTemplate | null>(null);

  // Utility function for deep comparison
  const deepEqual = useCallback((obj1: any, obj2: any): boolean => {
    if (obj1 === obj2) return true;
    if (!obj1 || !obj2) return false;
    if (typeof obj1 !== typeof obj2) return false;
    
    if (Array.isArray(obj1) && Array.isArray(obj2)) {
      if (obj1.length !== obj2.length) return false;
      return obj1.every((item, index) => deepEqual(item, obj2[index]));
    }
    
    if (typeof obj1 === 'object') {
      const keys1 = Object.keys(obj1);
      const keys2 = Object.keys(obj2);
      if (keys1.length !== keys2.length) return false;
      return keys1.every(key => deepEqual(obj1[key], obj2[key]));
    }
    
    return obj1 === obj2;
  }, []);

  // Check if template has changes
  const hasChanges = useMemo(() => {
    if (!baselineTemplate || !editedTemplate) return false;
    return !deepEqual(baselineTemplate, editedTemplate);
  }, [baselineTemplate, editedTemplate, deepEqual]);

  // Initialize state from template prop
  useEffect(() => {
    if (template) {
      // Снимаем снапшот только при смене шаблона (по id) или при первом открытии
      if (!baselineTemplate || baselineTemplate.id !== template.id) {
        const snapshot = JSON.parse(JSON.stringify(template)) as MessageTemplate;
        setEditedTemplate(snapshot);
        setBaselineTemplate(snapshot);
        setOriginalImageUrl(snapshot.template_data.image_url);
      }
    } else {
      setEditedTemplate(null);
      setBaselineTemplate(null);
      setOriginalImageUrl(undefined);
    }
  }, [template, baselineTemplate]);

  // Track changes for onChange callback
  useEffect(() => {
    if (onChange && hasChanges && editedTemplate) {
      onChange(editedTemplate);
    }
  }, [onChange, hasChanges, editedTemplate]);


  const handleFieldChange = (field: keyof MessageTemplate, value: any) => {
    if (!editedTemplate) return;
    
    const updated = {
      ...editedTemplate,
      [field]: value
    };
    setEditedTemplate(updated);
    onChange?.(updated);
  };

  const handleTemplateDataChange = (field: string, value: any) => {
    if (!editedTemplate) return;
    
    const updated = {
      ...editedTemplate,
      template_data: {
        ...editedTemplate.template_data,
        [field]: value
      }
    };
    setEditedTemplate(updated);
    onChange?.(updated);
  };

  const handleImagePositionChange = useCallback((position: 'left' | 'right' | 'top' | 'bottom') => {
    if (editedTemplate) {
      const updated = {
        ...editedTemplate,
        template_data: {
          ...editedTemplate.template_data,
          image_position: position
        }
      };
      setEditedTemplate(updated);
      onChange?.(updated);
    }
  }, [editedTemplate, onChange]);

  const handleImageFormatChange = useCallback((format: 'square' | 'vertical' | 'full-width') => {
    if (editedTemplate) {
      const updated = {
        ...editedTemplate,
        template_data: {
          ...editedTemplate.template_data,
          image_format: format
        }
      };
      setEditedTemplate(updated);
      onChange?.(updated);
    }
  }, [editedTemplate, onChange]);

  const handleImageChange = useCallback((url?: string) => {
    if (editedTemplate) {
      const updated = {
        ...editedTemplate,
        template_data: {
          ...editedTemplate.template_data,
          image_url: url
        }
      };
      setEditedTemplate(updated);
      onChange?.(updated);
    }
  }, [editedTemplate, onChange]);

  const handleReset = () => {
    if (baselineTemplate) {
      const snapshot = JSON.parse(JSON.stringify(baselineTemplate)) as MessageTemplate;
      setEditedTemplate(snapshot);
      setOriginalImageUrl(snapshot.template_data.image_url);
    }
  };

  const handleSave = useCallback(async (showToast = true) => {
    if (editedTemplate) {
      try {
        // Отладочные логи
        
        await onSave(editedTemplate);
        // Обновляем базовую версию после сохранения
        setBaselineTemplate(JSON.parse(JSON.stringify(editedTemplate)) as MessageTemplate);
        
        if (showToast) {
          toast({
            title: "Шаблон сохранён",
            description: "Изменения успешно применены",
          });
        }
      } catch (error: any) {
        
        toast({
          title: "Ошибка сохранения",
          description: error.message || "Не удалось сохранить изменения",
          variant: "error",
        });
      }
    }
  }, [editedTemplate, onSave, toast]);

  const handleClose = () => {
    if (hasChanges) {
      const confirmed = window.confirm('У вас есть несохраненные изменения. Вы уверены, что хотите закрыть?');
      if (!confirmed) return;
    }
    onClose();
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;
      
      if (e.ctrlKey && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
      if (e.key === 'Escape') {
        handleClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, handleSave, handleClose]);

  if (!isOpen || !editedTemplate) {
    return null;
  }

  return (
    <div className="w-full bg-dark-gray/30 backdrop-blur-sm">
      <GlassCard
        variant="elevated"
        padding="sm"
        hover={false}
        className="rounded-xl border-0 shadow-none p-0"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-gradient-to-r from-accent-red/5 to-transparent">
          <div className="flex items-center gap-3">
            <div className="flex flex-col">
              <h3 className="font-semibold text-sm text-white">Редактирование шаблона</h3>
              <p className="text-xs text-gray-400">{editedTemplate.name}</p>
            </div>
            {hasChanges && (
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 bg-warning rounded-full animate-pulse" title="Несохраненные изменения" />
                <span className="text-xs text-warning">•</span>
              </div>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClose}
            className="h-8 w-8 p-0 hover:bg-destructive/20 hover:text-destructive"
          >
            <X size={14} />
          </Button>
        </div>

        <div className="p-4 space-y-4">
            {/* Basic Info Section */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1 h-4 bg-accent-red rounded-full"></div>
                <h4 className="text-sm font-medium text-white">Основная информация</h4>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="name" className="text-xs font-medium text-gray-300">Название</Label>
                  <Input
                    id="name"
                    value={editedTemplate.name}
                    onChange={(e) => handleFieldChange('name', e.target.value)}
                    className="h-9 bg-dark-gray/50 border-white/10 focus:border-accent-red/50"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="category" className="text-xs font-medium text-gray-300">Категория</Label>
                  <Select
                    value={editedTemplate.category}
                    onValueChange={(value) => handleFieldChange('category', value)}
                  >
                    <SelectTrigger className="h-9 bg-dark-gray/50 border-white/10 focus:border-accent-red/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="основные">Основные</SelectItem>
                      <SelectItem value="поиск товара">Поиск</SelectItem>
                      <SelectItem value="финансы">Финансы</SelectItem>
                      <SelectItem value="логистика">Логистика</SelectItem>
                      <SelectItem value="последняя миля">Последняя миля</SelectItem>
                      <SelectItem value="другое">Другое</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description" className="text-xs font-medium text-gray-300">Описание</Label>
                <Input
                  id="description"
                  value={editedTemplate.description}
                  onChange={(e) => handleFieldChange('description', e.target.value)}
                  className="h-9 bg-dark-gray/50 border-white/10 focus:border-accent-red/50"
                  placeholder="Краткое описание шаблона..."
                />
              </div>
            </div>

            {/* Template Content Section */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1 h-4 bg-accent-red rounded-full"></div>
                <h4 className="text-sm font-medium text-accent-red">Содержимое шаблона</h4>
              </div>

              <div className="space-y-2">
                <Label htmlFor="title" className="text-xs font-medium text-gray-300">Заголовок</Label>
                <Input
                  id="title"
                  value={editedTemplate.template_data.title}
                  onChange={(e) => handleTemplateDataChange('title', e.target.value)}
                  className="h-9 bg-dark-gray/50 border-white/10 focus:border-accent-red/50"
                  placeholder="Заголовок сообщения..."
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="content" className="text-xs font-medium text-gray-300">Текст сообщения</Label>
                <Textarea
                  id="content"
                  value={editedTemplate.template_data.description}
                  onChange={(e) => handleTemplateDataChange('description', e.target.value)}
                  className="bg-dark-gray/50 border-white/10 focus:border-accent-red/50 resize-none"
                  rows={4}
                  placeholder="Текст сообщения..."
                />
              </div>
            </div>

            {/* Image Position Section */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1 h-4 bg-info rounded-full"></div>
                <h4 className="text-sm font-medium text-white">Изображение</h4>
              </div>
              <ImagePositionSelector
                position={editedTemplate.template_data.image_position || 'left'}
                onPositionChange={handleImagePositionChange}
                format={editedTemplate.template_data.image_format || 'square'}
                onFormatChange={handleImageFormatChange}
                imageUrl={editedTemplate.template_data.image_url}
                onImageChange={handleImageChange}
              />
            </div>

            {/* Buttons Section */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1 h-4 bg-warning rounded-full"></div>
                <h4 className="text-sm font-medium text-white">Кнопки действий</h4>
              </div>
              <ButtonEditor
                buttons={editedTemplate.template_data.buttons}
                onChange={(buttons) => handleTemplateDataChange('buttons', buttons)}
              />
            </div>
        </div>

        {/* Action Footer */}
        <div className="flex items-center justify-between p-4 border-t border-white/10 bg-gradient-to-r from-dark-gray/50 to-transparent">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReset}
              disabled={!hasChanges}
              className="h-8 text-xs hover:bg-warning/20 hover:text-warning disabled:opacity-50"
            >
              <RotateCcw size={12} className="mr-1.5" />
              Сбросить
            </Button>
          </div>
          
          <Button
            size="sm"
            onClick={() => handleSave()}
            disabled={!hasChanges}
            className="h-8 text-xs bg-accent-red hover:bg-accent-red/80 disabled:opacity-50"
          >
            <Save size={12} className="mr-1.5" />
            Сохранить
          </Button>
        </div>
      </GlassCard>
    </div>
  );
};