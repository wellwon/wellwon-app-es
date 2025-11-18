import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Plus, Trash2, GripVertical } from 'lucide-react';
import { IconSelector } from './IconSelector';

interface ButtonData {
  text: string;
  action: string;
  style?: string;
  icon?: string;
}

interface ButtonEditorProps {
  buttons: ButtonData[];
  onChange: (buttons: ButtonData[]) => void;
}

export const ButtonEditor: React.FC<ButtonEditorProps> = ({ buttons, onChange }) => {
  const addButton = () => {
    const newButton: ButtonData = {
      text: 'Новая кнопка',
      action: 'custom',
      style: 'primary'
    };
    onChange([...buttons, newButton]);
  };

  const removeButton = (index: number) => {
    const newButtons = buttons.filter((_, i) => i !== index);
    onChange(newButtons);
  };

  const updateButton = (index: number, field: keyof ButtonData, value: string) => {
    const newButtons = buttons.map((button, i) => 
      i === index ? { ...button, [field]: value } : button
    );
    onChange(newButtons);
  };

  const moveButton = (fromIndex: number, toIndex: number) => {
    const newButtons = [...buttons];
    const [movedButton] = newButtons.splice(fromIndex, 1);
    newButtons.splice(toIndex, 0, movedButton);
    onChange(newButtons);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label className="text-sm text-gray-300">Кнопки ({buttons.length})</Label>
        <Button
          size="sm"
          variant="ghost"
          onClick={addButton}
          className="text-accent-red hover:text-accent-red/80 hover:bg-accent-red/10"
        >
          <Plus size={14} className="mr-1" />
          Добавить
        </Button>
      </div>

      <div className="space-y-2 max-h-60 overflow-y-auto">
        {buttons.map((button, index) => (
          <div
            key={index}
            className="flex items-center gap-2 p-3 bg-dark-gray/40 rounded-lg border border-white/5"
          >
            <div className="cursor-grab text-gray-500">
              <GripVertical size={16} />
            </div>
            
            <div className="flex-1 space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <Input
                  value={button.text}
                  onChange={(e) => updateButton(index, 'text', e.target.value)}
                  placeholder="Текст кнопки"
                  className="bg-dark-gray/50 border-white/10 text-white text-sm"
                />
                
                <Input
                  value={button.action}
                  onChange={(e) => updateButton(index, 'action', e.target.value)}
                  placeholder="Строка действия"
                  className="bg-dark-gray/50 border-white/10 text-white text-sm"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-2">
                <IconSelector
                  value={button.icon}
                  onChange={(value) => updateButton(index, 'icon', value || '')}
                  placeholder="Выберите иконку"
                />
                
                <Select
                  value={button.style || 'primary'}
                  onValueChange={(value) => updateButton(index, 'style', value)}
                >
                  <SelectTrigger className="bg-dark-gray/50 border-white/10 text-white text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="primary">Основная</SelectItem>
                    <SelectItem value="secondary">Вторичная</SelectItem>
                    <SelectItem value="outline">Контур</SelectItem>
                    <SelectItem value="ghost">Прозрачная</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            <Button
              size="sm"
              variant="ghost"
              onClick={() => removeButton(index)}
              className="text-red-400 hover:text-red-300 hover:bg-red-400/10 p-1"
            >
              <Trash2 size={14} />
            </Button>
          </div>
        ))}
      </div>

      {buttons.length === 0 && (
        <div className="text-center py-6 text-gray-500 text-sm">
          Нет кнопок. Нажмите "Добавить" чтобы создать первую кнопку.
        </div>
      )}
    </div>
  );
};