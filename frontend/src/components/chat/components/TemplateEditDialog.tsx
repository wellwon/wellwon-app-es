import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Save, X, RotateCcw, Eye } from 'lucide-react';
import { ButtonEditor } from './ButtonEditor';
import { ImagePositionSelector } from './ImagePositionSelector';
import type { MessageTemplate } from '@/utils/messageTemplates';

interface TemplateEditDialogProps {
  template: MessageTemplate | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (updatedTemplate: MessageTemplate) => void;
  onPreview: (template: MessageTemplate) => void;
}

export const TemplateEditDialog: React.FC<TemplateEditDialogProps> = ({
  template,
  isOpen,
  onClose,
  onSave,
  onPreview
}) => {
  const [editedTemplate, setEditedTemplate] = useState<MessageTemplate | null>(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [imageEnabled, setImageEnabled] = useState(false);
  // Remove imagePosition state - it will be handled in the template data directly

  useEffect(() => {
    if (template) {
      setEditedTemplate(template);
      setImageEnabled(!!template.template_data.image_url);
    }
  }, [template]);

  useEffect(() => {
    if (template && editedTemplate) {
      const isChanged = JSON.stringify(template) !== JSON.stringify(editedTemplate);
      setHasChanges(isChanged);
    }
  }, [template, editedTemplate]);

  useEffect(() => {
    if (editedTemplate && hasChanges) {
      onPreview(editedTemplate);
    }
  }, [editedTemplate, hasChanges, onPreview]);

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

  const handleSave = () => {
    if (editedTemplate) {
      onSave(editedTemplate);
      setHasChanges(false);
      onClose();
    }
  };

  const handleClose = () => {
    if (hasChanges) {
      const confirmed = window.confirm('У вас есть несохраненные изменения. Вы уверены, что хотите закрыть?');
      if (!confirmed) return;
    }
    onClose();
  };

  if (!editedTemplate) return null;

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] bg-dark-gray border-white/20">
        <DialogHeader>
          <DialogTitle className="text-white">Редактирование шаблона</DialogTitle>
        </DialogHeader>
        
        <ScrollArea className="flex-1 pr-4">
          <div className="space-y-6">
            {/* Basic Info */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="name" className="text-sm text-gray-300">Название</Label>
                <Input
                  id="name"
                  value={editedTemplate.name}
                  onChange={(e) => handleFieldChange('name', e.target.value)}
                  className="bg-dark-gray/50 border-white/20 text-white mt-1"
                />
              </div>
              <div>
                <Label htmlFor="category" className="text-sm text-gray-300">Категория</Label>
                <Select
                  value={editedTemplate.category}
                  onValueChange={(value) => handleFieldChange('category', value)}
                >
                  <SelectTrigger className="bg-dark-gray/50 border-white/20 text-white mt-1">
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

            <div>
              <Label htmlFor="description" className="text-sm text-gray-300">Описание</Label>
              <Textarea
                id="description"
                value={editedTemplate.description}
                onChange={(e) => handleFieldChange('description', e.target.value)}
                className="bg-dark-gray/50 border-white/20 text-white mt-1"
                rows={2}
              />
            </div>

            {/* Template Content */}
            <div>
              <Label htmlFor="title" className="text-sm text-gray-300">Заголовок шаблона</Label>
              <Input
                id="title"
                value={editedTemplate.template_data.title}
                onChange={(e) => handleTemplateDataChange('title', e.target.value)}
                className="bg-dark-gray/50 border-white/20 text-white mt-1"
              />
            </div>

            <div>
              <Label htmlFor="content" className="text-sm text-gray-300">Текст сообщения</Label>
              <Textarea
                id="content"
                value={editedTemplate.template_data.description}
                onChange={(e) => handleTemplateDataChange('description', e.target.value)}
                className="bg-dark-gray/50 border-white/20 text-white mt-1"
                rows={3}
              />
            </div>

            {/* Image Position */}
            <ImagePositionSelector
              position={editedTemplate.template_data.image_position || 'left'}
              onPositionChange={(position) => handleTemplateDataChange('image_position', position)}
              format={editedTemplate.template_data.image_format || 'square'}
              onFormatChange={(format) => handleTemplateDataChange('image_format', format)}
              imageUrl={editedTemplate.template_data.image_url}
              onImageChange={handleImageChange}
            />

            {/* Buttons Editor */}
            <ButtonEditor
              buttons={editedTemplate.template_data.buttons}
              onChange={(buttons) => handleTemplateDataChange('buttons', buttons)}
            />
          </div>
        </ScrollArea>

        {/* Action Buttons */}
        <div className="flex justify-between pt-4 border-t border-white/10 mt-4">
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReset}
              disabled={!hasChanges}
              className="text-gray-400 hover:text-white"
            >
              <RotateCcw size={14} className="mr-1" />
              Сбросить
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => editedTemplate && onPreview(editedTemplate)}
              className="text-blue-400 hover:text-blue-300"
            >
              <Eye size={14} className="mr-1" />
              Превью
            </Button>
          </div>
          
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClose}
              className="text-gray-400 hover:text-white"
            >
              <X size={14} className="mr-1" />
              Отмена
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={!hasChanges}
              className="bg-accent-red hover:bg-accent-red/90"
            >
              <Save size={14} className="mr-1" />
              Сохранить
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};