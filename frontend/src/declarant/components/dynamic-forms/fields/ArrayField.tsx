// =============================================================================
// ArrayField - Repeatable array field component
// =============================================================================

import React, { useState } from 'react';
import { Plus, Trash2, ChevronDown, ChevronRight, Copy, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { FieldDefinition, FieldComponentProps } from '../../../types/form-definitions';

interface ArrayFieldProps extends FieldComponentProps {
  renderField: (field: FieldDefinition, parentPath?: string) => React.ReactNode;
}

export const ArrayField: React.FC<ArrayFieldProps> = ({
  field,
  value,
  onChange,
  isDark,
  disabled = false,
  renderField,
}) => {
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set([0]));
  const [copied, setCopied] = useState(false);

  const items = Array.isArray(value) ? value : [];
  const children = field.children || [];

  const handleCopyPath = async () => {
    try {
      await navigator.clipboard.writeText(field.path);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const toggleItem = (index: number) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const addItem = () => {
    const newItem: Record<string, unknown> = {};
    // Initialize with default empty values
    children.forEach((child) => {
      newItem[child.name] = '';
    });
    onChange([...items, newItem]);
    // Expand new item
    setExpandedItems((prev) => new Set([...prev, items.length]));
  };

  const removeItem = (index: number) => {
    const newItems = items.filter((_, i) => i !== index);
    onChange(newItems);
    // Update expanded items indices
    setExpandedItems((prev) => {
      const next = new Set<number>();
      prev.forEach((i) => {
        if (i < index) {
          next.add(i);
        } else if (i > index) {
          next.add(i - 1);
        }
      });
      return next;
    });
  };

  if (children.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <label
            className={cn(
              'text-sm font-medium truncate',
              isDark ? 'text-white' : 'text-gray-700',
              field.required && "after:content-['*'] after:ml-0.5 after:text-red-500"
            )}
          >
            {field.label_ru || field.name}
          </label>
          <span className={cn('text-xs font-normal shrink-0', isDark ? 'text-gray-500' : 'text-gray-400')}>
            ({items.length} {items.length === 1 ? 'элемент' : 'элементов'})
          </span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <div className="flex items-center gap-1">
            <span
              className={cn(
                'text-xs font-mono truncate max-w-[150px]',
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

          {!disabled && (
            <button
              type="button"
              onClick={addItem}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                isDark
                  ? 'bg-white/10 text-white hover:bg-white/20'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              )}
            >
              <Plus className="w-4 h-4" />
              Добавить
            </button>
          )}
        </div>
      </div>

      {/* Items */}
      <div className="space-y-3">
        {items.map((item, index) => {
          const isExpanded = expandedItems.has(index);

          return (
            <div
              key={index}
              className={cn(
                'rounded-xl border',
                isDark ? 'border-white/10 bg-white/5' : 'border-gray-200 bg-gray-50'
              )}
            >
              {/* Item Header */}
              <div
                className={cn(
                  'flex items-center justify-between px-4 py-3',
                  isExpanded && (isDark ? 'border-b border-white/10' : 'border-b border-gray-200')
                )}
              >
                <button
                  type="button"
                  onClick={() => toggleItem(index)}
                  className="flex items-center gap-2 flex-1"
                >
                  {isExpanded ? (
                    <ChevronDown className={cn('w-4 h-4', isDark ? 'text-gray-400' : 'text-gray-500')} />
                  ) : (
                    <ChevronRight className={cn('w-4 h-4', isDark ? 'text-gray-400' : 'text-gray-500')} />
                  )}
                  <span className={cn('text-sm font-medium', isDark ? 'text-white' : 'text-gray-900')}>
                    #{index + 1}
                  </span>
                </button>

                {!disabled && (
                  <button
                    type="button"
                    onClick={() => removeItem(index)}
                    className={cn(
                      'p-1.5 rounded-lg transition-colors',
                      isDark
                        ? 'text-gray-400 hover:text-red-400 hover:bg-red-500/10'
                        : 'text-gray-400 hover:text-red-500 hover:bg-red-50'
                    )}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>

              {/* Item Fields */}
              {isExpanded && (
                <div className="p-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {children.map((child) => {
                      // Create a modified field with path pointing to array item
                      const itemField: FieldDefinition = {
                        ...child,
                        path: `${field.path}[${index}].${child.name}`,
                      };
                      return (
                        <div key={child.path}>
                          {renderField(itemField, `${field.path}[${index}]`)}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {/* Empty State */}
        {items.length === 0 && (
          <div
            className={cn(
              'rounded-xl border-2 border-dashed p-6 text-center',
              isDark ? 'border-white/10' : 'border-gray-200'
            )}
          >
            <p className={cn('text-sm', isDark ? 'text-gray-500' : 'text-gray-400')}>
              Нет элементов. Нажмите "Добавить" чтобы добавить первый элемент.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
