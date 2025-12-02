// =============================================================================
// ObjectField - Nested object field component (renders children fields)
// =============================================================================

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Copy, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { FieldDefinition, FieldComponentProps } from '../../../types/form-definitions';

interface ObjectFieldProps extends FieldComponentProps {
  renderField: (field: FieldDefinition, parentPath?: string) => React.ReactNode;
}

export const ObjectField: React.FC<ObjectFieldProps> = ({
  field,
  isDark,
  renderField,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [copied, setCopied] = useState(false);

  const children = field.children || [];

  const handleCopyPath = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(field.path);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  if (children.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      {/* Header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className={cn(
          'flex items-center justify-between gap-2 w-full text-left',
          'px-3 py-2 rounded-lg transition-colors',
          isDark
            ? 'hover:bg-white/5'
            : 'hover:bg-gray-100'
        )}
      >
        <div className="flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className={cn('w-4 h-4', isDark ? 'text-gray-400' : 'text-gray-500')} />
          ) : (
            <ChevronRight className={cn('w-4 h-4', isDark ? 'text-gray-400' : 'text-gray-500')} />
          )}
          <span
            className={cn(
              'text-sm font-medium',
              isDark ? 'text-white' : 'text-gray-900'
            )}
          >
            {field.label_ru || field.name}
          </span>
          <span className={cn('text-xs', isDark ? 'text-gray-500' : 'text-gray-400')}>
            ({children.length} {children.length === 1 ? 'поле' : 'полей'})
          </span>
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
          <div
            onClick={handleCopyPath}
            className={cn(
              'p-1 rounded transition-colors cursor-pointer',
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
          </div>
        </div>
      </button>

      {/* Children */}
      {isExpanded && (
        <div
          className={cn(
            'ml-6 pl-4 border-l-2',
            isDark ? 'border-white/10' : 'border-gray-200'
          )}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {children.map((child) => (
              <div key={child.path} className={child.field_type === 'object' || child.field_type === 'array' ? 'col-span-full' : ''}>
                {renderField(child, field.path)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
