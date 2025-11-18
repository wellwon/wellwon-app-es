import React from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';
import { getIconComponent, AVAILABLE_ICONS } from '@/utils/iconUtils';

interface IconSelectorProps {
  value?: string;
  onChange: (value?: string) => void;
  placeholder?: string;
}

export const IconSelector: React.FC<IconSelectorProps> = ({ 
  value, 
  onChange, 
  placeholder = "Выберите иконку" 
}) => {
  const clearIcon = () => onChange(undefined);
  
  const IconComponent = value ? getIconComponent(value) : null;

  return (
    <div className="flex items-center gap-2">
      <Select value={value || ""} onValueChange={(val) => onChange(val || undefined)}>
        <SelectTrigger className="bg-dark-gray/50 border-white/10 text-white text-sm flex-1">
          <div className="flex items-center gap-2">
            {IconComponent && <IconComponent size={14} />}
            <SelectValue placeholder={placeholder} />
          </div>
        </SelectTrigger>
        <SelectContent className="max-h-60">
          <SelectItem value="">
            <span className="text-gray-400">Без иконки</span>
          </SelectItem>
          {AVAILABLE_ICONS.map(({ name, label }) => {
            const Icon = getIconComponent(name);
            return (
              <SelectItem key={name} value={name}>
                <div className="flex items-center gap-2">
                  <Icon size={14} />
                  <span>{label}</span>
                </div>
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
      
      {value && (
        <Button
          size="sm"
          variant="ghost"
          onClick={clearIcon}
          className="text-gray-400 hover:text-white hover:bg-white/10 p-1 h-8 w-8"
        >
          <X size={12} />
        </Button>
      )}
    </div>
  );
};