// =============================================================================
// TextField - Text input field component
// =============================================================================

import React from 'react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import type { FieldComponentProps } from '../../../types/form-definitions';
import { FieldLabel } from './FieldLabel';

export const TextField: React.FC<FieldComponentProps> = ({
  field,
  value,
  error,
  onChange,
  onBlur,
  isDark,
  disabled = false,
}) => {
  return (
    <div className="space-y-1.5">
      <FieldLabel
        label={field.label_ru || field.name}
        fieldName={field.name}
        fieldPath={field.path}
        required={field.required}
        isDark={isDark}
      />

      <Input
        type="text"
        value={(value as string) || ''}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        placeholder={field.placeholder_ru || ''}
        maxLength={field.max_length || undefined}
        disabled={disabled}
        className={cn(
          'h-10 rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-0 transition-none',
          isDark
            ? 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500 hover:border-white/20'
            : 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400 hover:border-gray-400',
          error && (isDark ? 'border-red-500/50' : 'border-red-500')
        )}
      />

      {field.hint_ru && !error && (
        <p className={cn('text-xs', isDark ? 'text-gray-500' : 'text-gray-400')}>
          {field.hint_ru}
        </p>
      )}

      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
};
