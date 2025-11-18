import React, { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Save, X, RotateCcw, GripVertical } from 'lucide-react';
import { ButtonEditor } from './ButtonEditor';
import { ImagePositionSelector } from './ImagePositionSelector';
import { GlassCard } from '@/components/design-system/GlassCard';
import { useDraggable } from '@/hooks/useDraggable';
import { useToast } from '@/hooks/use-toast';
import type { MessageTemplate } from '@/utils/messageTemplates';

interface DraggableTemplateEditProps {
  template: MessageTemplate | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (updatedTemplate: MessageTemplate) => void;
}

export const DraggableTemplateEdit: React.FC<DraggableTemplateEditProps> = ({
  template,
  isOpen,
  onClose,
  onSave
}) => {
  const { toast } = useToast();
  const [editedTemplate, setEditedTemplate] = useState<MessageTemplate | null>(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [imageEnabled, setImageEnabled] = useState(false);
  // Remove imagePosition state - it will be handled in the template data directly

  const { elementRef, position, isDragging, resetPosition, handlers } = useDraggable({
    storageKey: 'template-edit-position',
    bounds: {
      top: 20,
      left: 20,
      right: window.innerWidth - 520,
      bottom: window.innerHeight - 620
    }
  });

  // Calculate center position
  const centerX = Math.max(20, (window.innerWidth - 500) / 2);
  const centerY = Math.max(20, (window.innerHeight - 600) / 2);
  
  // Set default position if not set (center of screen)
  const finalPosition = position.x === 0 && position.y === 0 ? {
    x: centerX,
    y: centerY
  } : {
    x: Math.max(20, Math.min(position.x, window.innerWidth - 520)),
    y: Math.max(20, Math.min(position.y, window.innerHeight - 620))
  };

  useEffect(() => {
    if (template) {
      setEditedTemplate(template);
      setImageEnabled(!!template.template_data.image_url);
      // Reset to center when opening new template
      resetPosition();
    }
  }, [template, resetPosition]);

  useEffect(() => {
    if (template && editedTemplate) {
      const isChanged = JSON.stringify(template) !== JSON.stringify(editedTemplate);
      setHasChanges(isChanged);
    }
  }, [template, editedTemplate]);

  // Auto-save
  useEffect(() => {
    if (hasChanges && editedTemplate) {
      const timeoutId = setTimeout(() => {
        handleSave(false); // Silent save
      }, 3000);
      return () => clearTimeout(timeoutId);
    }
  }, [hasChanges, editedTemplate]);

  const handleFieldChange = (field: keyof MessageTemplate, value: any) => {
    if (!editedTemplate) return;
    
    setEditedTemplate(prev => prev ? ({
      ...prev,
      [field]: value
    }) : null);
  };

  const handleTemplateDataChange = (field: string, value: any) => {
    if (!editedTemplate) return;
    
    setEditedTemplate(prev => prev ? ({
      ...prev,
      template_data: {
        ...prev.template_data,
        [field]: value
      }
    }) : null);
  };

  const handleImageEnabledChange = (enabled: boolean) => {
    setImageEnabled(enabled);
    if (!enabled) {
      handleTemplateDataChange('image_url', undefined);
      handleTemplateDataChange('image_position', undefined);
    } else {
      handleTemplateDataChange('image_position', 'left');
    }
  };

  const handleImageChange = (url?: string) => {
    handleTemplateDataChange('image_url', url);
  };

  const handleReset = () => {
    if (template) {
      setEditedTemplate(template);
      setImageEnabled(!!template.template_data.image_url);
      setHasChanges(false);
    }
  };

  const handleSave = useCallback((showToast = true) => {
    if (editedTemplate) {
      onSave(editedTemplate);
      setHasChanges(false);
      if (showToast) {
        toast({
          title: "Шаблон сохранён",
          description: "Изменения успешно применены",
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
    <div
      ref={elementRef}
      className="fixed z-[9999] select-none"
      style={{
        left: `${finalPosition.x}px`,
        top: `${finalPosition.y}px`,
        transform: isDragging ? 'scale(1.02)' : 'scale(1)',
        transition: isDragging ? 'none' : 'transform 0.2s ease',
        visibility: 'visible',
        opacity: 1
      }}
    >
      <GlassCard
        variant="elevated"
        padding="sm"
        hover={false}
        className="w-[500px] overflow-hidden"
      >
      {/* Draggable Header */}
      <div 
        className="flex items-center justify-between p-4 border-b border-white/10 cursor-grab active:cursor-grabbing bg-gradient-to-r from-accent-red/5 to-transparent"
        {...handlers}
      >
        <div className="flex items-center gap-3">
          <div className="p-1.5 rounded-md bg-accent-red/10 border border-accent-red/20">
            <GripVertical size={14} className="text-accent-red" />
          </div>
          <div className="flex flex-col">
            <h3 className="font-semibold text-sm text-white">Редактирование шаблона</h3>
            <p className="text-xs text-gray-400">Перетащите для перемещения</p>
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

      <ScrollArea className="h-[500px]">
        <div className="p-6 space-y-6">
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
                    <SelectItem value="поиск товара">Поиск товара</SelectItem>
                    <SelectItem value="финансы">Финансы</SelectItem>
                    <SelectItem value="логистика">Логистика</SelectItem>
                    <SelectItem value="последняя миля">Последняя миля</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description" className="text-xs font-medium text-gray-300">Описание</Label>
              <Textarea
                id="description"
                value={editedTemplate.description}
                onChange={(e) => handleFieldChange('description', e.target.value)}
                className="bg-dark-gray/50 border-white/10 focus:border-accent-red/50 resize-none"
                rows={3}
                placeholder="Краткое описание шаблона..."
              />
            </div>
          </div>

          {/* Template Content Section */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-1 h-4 bg-accent-green rounded-full"></div>
              <h4 className="text-sm font-medium text-white">Содержимое шаблона</h4>
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
              onPositionChange={(position) => handleTemplateDataChange('image_position', position)}
              format={editedTemplate.template_data.image_format || 'square'}
              onFormatChange={(format) => handleTemplateDataChange('image_format', format)}
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
      </ScrollArea>

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
          {hasChanges && (
            <span className="text-xs text-gray-400">Автосохранение через 3с</span>
          )}
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
