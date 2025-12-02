// =============================================================================
// SelectField - Select dropdown field component
// =============================================================================

import React from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import type { FieldComponentProps } from '../../../types/form-definitions';
import { FieldLabel } from './FieldLabel';

export const SelectField: React.FC<FieldComponentProps> = ({
  field,
  value,
  error,
  onChange,
  onBlur,
  isDark,
  disabled = false,
}) => {
  const options = field.options || [];

  return (
    <div className="space-y-1.5">
      <FieldLabel
        label={field.label_ru || field.name}
        fieldName={field.name}
        fieldPath={field.path}
        required={field.required}
        isDark={isDark}
      />

      <Select
        value={(value as string) || ''}
        onValueChange={(val) => {
          onChange(val);
          onBlur();
        }}
        disabled={disabled}
      >
        <SelectTrigger
          className={cn(
            'w-full h-10 rounded-xl focus:outline-none focus:ring-0 transition-none',
            isDark
              ? 'bg-[#1e1e22] border-white/10 text-white'
              : 'bg-gray-50 border-gray-300 text-gray-900',
            error && (isDark ? 'border-red-500/50' : 'border-red-500')
          )}
        >
          <SelectValue placeholder={field.placeholder_ru || 'Выберите...'} />
        </SelectTrigger>
        <SelectContent
          className={cn(
            isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'
          )}
        >
          {options.map((option) => (
            <SelectItem
              key={option.value}
              value={option.value}
              className={cn(
                isDark ? 'focus:bg-white/10 text-white' : 'focus:bg-gray-100 text-gray-900'
              )}
            >
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {field.hint_ru && !error && (
        <p className={cn('text-xs', isDark ? 'text-gray-500' : 'text-gray-400')}>
          {field.hint_ru}
        </p>
      )}

      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
};
