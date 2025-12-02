// =============================================================================
// FieldLabel - Common label component with copy button for all field types
// =============================================================================

import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FieldLabelProps {
  label: string;
  fieldName: string;
  fieldPath: string;
  required?: boolean;
  isDark: boolean;
}

export const FieldLabel: React.FC<FieldLabelProps> = ({
  label,
  fieldName,
  fieldPath,
  required = false,
  isDark,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopyPath = async () => {
    try {
      await navigator.clipboard.writeText(fieldPath);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="flex items-center justify-between gap-2">
      <label
        className={cn(
          'text-sm font-medium truncate',
          isDark ? 'text-white' : 'text-gray-700',
          required && "after:content-['*'] after:ml-0.5 after:text-red-500"
        )}
      >
        {label}
      </label>
      <div className="flex items-center gap-1 shrink-0">
        <span
          className={cn(
            'text-xs font-mono truncate max-w-[200px]',
            isDark ? 'text-gray-500' : 'text-gray-400'
          )}
          title={fieldPath}
        >
          {fieldName}
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
          title={`Копировать: ${fieldPath}`}
        >
          {copied ? (
            <Check className="w-3 h-3 text-green-500" />
          ) : (
            <Copy className="w-3 h-3" />
          )}
        </button>
      </div>
    </div>
  );
};
