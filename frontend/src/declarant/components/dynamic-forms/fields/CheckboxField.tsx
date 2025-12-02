// =============================================================================
// CheckboxField - Checkbox field component
// =============================================================================

import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';
import type { FieldComponentProps } from '../../../types/form-definitions';

export const CheckboxField: React.FC<FieldComponentProps> = ({
  field,
  value,
  error,
  onChange,
  onBlur,
  isDark,
  disabled = false,
}) => {
  const [copied, setCopied] = useState(false);

  // Handle various boolean representations
  const isChecked = value === true || value === 'true' || value === 1 || value === '1';

  const handleCopyPath = async () => {
    try {
      await navigator.clipboard.writeText(field.path);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <Checkbox
            id={field.path}
            checked={isChecked}
            onCheckedChange={(checked) => {
              onChange(checked);
              onBlur();
            }}
            disabled={disabled}
            className={cn(
              'h-5 w-5 rounded border-2',
              isDark
                ? 'border-white/20 data-[state=checked]:bg-accent-red data-[state=checked]:border-accent-red'
                : 'border-gray-300 data-[state=checked]:bg-accent-red data-[state=checked]:border-accent-red',
              error && 'border-red-500'
            )}
          />
          <label
            htmlFor={field.path}
            className={cn(
              'text-sm font-medium cursor-pointer select-none',
              isDark ? 'text-white' : 'text-gray-700',
              disabled && 'opacity-50 cursor-not-allowed'
            )}
          >
            {field.label_ru || field.name}
            {field.required && <span className="ml-0.5 text-red-500">*</span>}
          </label>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <span
            className={cn(
              'text-xs font-mono truncate max-w-[200px]',
              isDark ? 'text-gray-500' : 'text-gray-400'
            )}
            title={field.path}
          >
            {field.name}
          </span>
          <button
            type="button"
            onClick={handleCopyPath}
            className={cn(
              'p-1 rounded transition-colors',
              isDark
                ? 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
            )}
            title={`Копировать: ${field.path}`}
          >
            {copied ? (
              <Check className="w-3 h-3 text-green-500" />
            ) : (
              <Copy className="w-3 h-3" />
            )}
          </button>
        </div>
      </div>

      {field.hint_ru && !error && (
        <p className={cn('text-xs ml-8', isDark ? 'text-gray-500' : 'text-gray-400')}>
          {field.hint_ru}
        </p>
      )}

      {error && <p className="text-xs text-red-500 ml-8">{error}</p>}
    </div>
  );
};
