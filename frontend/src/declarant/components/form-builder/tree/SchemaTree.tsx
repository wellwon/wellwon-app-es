// =============================================================================
// SchemaTree - Дерево полей JSON схемы (правая панель)
// =============================================================================

import React, { useMemo } from 'react';
import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import {
  Search,
  ChevronRight,
  ChevronDown,
  GripVertical,
  Check,
  Type,
  Hash,
  Calendar,
  List,
  CheckSquare,
  FileText,
  Box,
  Layers,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFormBuilderStore } from '../../../stores/useFormBuilderStore';
import type { FieldDefinition, FieldType } from '../../../types/form-definitions';

interface SchemaTreeProps {
  isDark: boolean;
}

// Icon mapping for field types
const FIELD_TYPE_ICONS: Record<FieldType, React.ComponentType<{ className?: string }>> = {
  text: Type,
  number: Hash,
  date: Calendar,
  datetime: Calendar,
  select: List,
  checkbox: CheckSquare,
  textarea: FileText,
  object: Box,
  array: Layers,
};

// Color mapping for field type icons
const FIELD_TYPE_COLORS: Record<FieldType, string> = {
  text: 'text-blue-400',       // Синий для текста
  number: 'text-emerald-400',  // Зелёный для чисел
  date: 'text-orange-400',     // Оранжевый для дат
  datetime: 'text-orange-400', // Оранжевый для дат
  select: 'text-purple-400',   // Фиолетовый для списков
  checkbox: 'text-pink-400',   // Розовый для чекбоксов
  textarea: 'text-cyan-400',   // Голубой для текстовых полей
  object: 'text-yellow-400',   // Жёлтый для объектов
  array: 'text-indigo-400',    // Индиго для массивов
};

export const SchemaTree: React.FC<SchemaTreeProps> = ({ isDark }) => {
  const {
    schemaFields,
    schemaSearchQuery,
    expandedNodes,
    setSchemaSearchQuery,
    toggleNodeExpanded,
    expandAllNodes,
    collapseAllNodes,
    isFieldUsed,
  } = useFormBuilderStore();

  const theme = isDark
    ? {
        text: 'text-white',
        textMuted: 'text-gray-400',
        hover: 'hover:bg-white/5',
        border: 'border-white/10',
        input: 'bg-white/5 border-white/10 text-white placeholder:text-gray-500',
        used: 'opacity-50',
      }
    : {
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        hover: 'hover:bg-gray-100',
        border: 'border-gray-200',
        input: 'bg-white border-gray-200 text-gray-900 placeholder:text-gray-400',
        used: 'opacity-50',
      };

  // Filter fields based on search query
  const filteredFields = useMemo(() => {
    if (!schemaSearchQuery.trim()) return schemaFields;

    const query = schemaSearchQuery.toLowerCase();

    const filterFields = (fields: FieldDefinition[]): FieldDefinition[] => {
      return fields
        .map((field) => {
          const matchesSearch =
            field.name.toLowerCase().includes(query) ||
            field.label_ru.toLowerCase().includes(query) ||
            field.path.toLowerCase().includes(query);

          if (field.children) {
            const filteredChildren = filterFields(field.children);
            if (filteredChildren.length > 0 || matchesSearch) {
              return { ...field, children: filteredChildren };
            }
          }

          return matchesSearch ? field : null;
        })
        .filter((f): f is FieldDefinition => f !== null);
    };

    return filterFields(schemaFields);
  }, [schemaFields, schemaSearchQuery]);

  return (
    <div className="h-full flex flex-col">
      {/* Header - compact */}
      <div className={cn('p-3 border-b', theme.border)}>
        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative flex-1">
            <Search className={cn('absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4', theme.textMuted)} />
            <input
              type="text"
              value={schemaSearchQuery}
              onChange={(e) => setSchemaSearchQuery(e.target.value)}
              placeholder="Поиск полей..."
              className={cn(
                'w-full pl-9 pr-3 py-2 rounded-lg border text-sm',
                theme.input
              )}
            />
          </div>

          {/* Expand/Collapse buttons */}
          <div className="flex items-center gap-1">
            <button
              onClick={expandAllNodes}
              className={cn('p-1.5 rounded text-xs', theme.hover, theme.textMuted)}
              title="Развернуть все"
            >
              +
            </button>
            <button
              onClick={collapseAllNodes}
              className={cn('p-1.5 rounded text-xs', theme.hover, theme.textMuted)}
              title="Свернуть все"
            >
              −
            </button>
          </div>
        </div>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto p-2">
        {filteredFields.length === 0 ? (
          <div className={cn('text-center py-8', theme.textMuted)}>
            <Search className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">Поля не найдены</p>
          </div>
        ) : (
          <div className="space-y-0.5">
            {filteredFields.map((field) => (
              <SchemaTreeNode
                key={field.path}
                field={field}
                depth={0}
                isDark={isDark}
                isExpanded={expandedNodes.has(field.path)}
                onToggle={() => toggleNodeExpanded(field.path)}
                isUsed={isFieldUsed(field.path)}
                theme={theme}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer hint */}
      <div className={cn('p-3 border-t text-xs text-center', theme.border, theme.textMuted)}>
        Перетащите поле на canvas для добавления
      </div>
    </div>
  );
};

// =============================================================================
// SchemaTreeNode - Узел дерева (рекурсивный)
// =============================================================================

interface SchemaTreeNodeProps {
  field: FieldDefinition;
  depth: number;
  isDark: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  isUsed: boolean;
  theme: Record<string, string>;
}

const SchemaTreeNode: React.FC<SchemaTreeNodeProps> = ({
  field,
  depth,
  isDark,
  isExpanded,
  onToggle,
  isUsed,
  theme,
}) => {
  const { expandedNodes, toggleNodeExpanded, isFieldUsed } = useFormBuilderStore();
  const hasChildren = field.children && field.children.length > 0;
  const isLeaf = !hasChildren;
  const Icon = FIELD_TYPE_ICONS[field.field_type as FieldType] || Type;
  const iconColor = FIELD_TYPE_COLORS[field.field_type as FieldType] || theme.textMuted;

  // Make leaf nodes draggable
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `schema-${field.path}`,
    data: {
      type: 'schema-field',
      field,
    },
    disabled: !isLeaf || isUsed,
  });

  const style = transform
    ? {
        transform: CSS.Translate.toString(transform),
        zIndex: isDragging ? 100 : undefined,
      }
    : undefined;

  return (
    <div>
      <div
        ref={isLeaf ? setNodeRef : undefined}
        style={style}
        className={cn(
          'flex items-center gap-1.5 px-2 py-1 rounded-md group',
          isLeaf && !isUsed && 'cursor-grab',
          isLeaf && isUsed && theme.used,
          isDragging && 'opacity-50',
          theme.hover
        )}
        {...(isLeaf ? { ...attributes, ...listeners } : {})}
      >
        {/* Indent */}
        {depth > 0 && <div style={{ width: depth * 16 }} />}

        {/* Expand/collapse button for nodes with children */}
        {hasChildren ? (
          <button onClick={onToggle} className="p-0.5">
            {isExpanded ? (
              <ChevronDown className={cn('w-4 h-4', theme.textMuted)} />
            ) : (
              <ChevronRight className={cn('w-4 h-4', theme.textMuted)} />
            )}
          </button>
        ) : (
          <div className="w-5" /> // Spacer for alignment
        )}

        {/* Drag handle for leaf nodes */}
        {isLeaf && !isUsed && (
          <GripVertical
            className={cn('w-3.5 h-3.5 opacity-0 group-hover:opacity-50', theme.textMuted)}
          />
        )}

        {/* Used indicator */}
        {isLeaf && isUsed && (
          <Check className="w-3.5 h-3.5 text-green-500" />
        )}

        {/* Field type icon with color */}
        <Icon className={cn('w-4 h-4 flex-shrink-0', iconColor)} />

        {/* Field label */}
        <span className={cn('flex-1 text-sm truncate', theme.text)}>
          {field.label_ru || field.name}
        </span>

        {/* Variable name badge */}
        <span className={cn('text-xs px-1.5 py-0.5 rounded font-mono', isDark ? 'bg-blue-500/20 text-blue-300' : 'bg-blue-100 text-blue-700')}>
          {field.name}
        </span>
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div className="ml-2">
          {field.children!.map((child) => (
            <SchemaTreeNode
              key={child.path}
              field={child}
              depth={depth + 1}
              isDark={isDark}
              isExpanded={expandedNodes.has(child.path)}
              onToggle={() => toggleNodeExpanded(child.path)}
              isUsed={isFieldUsed(child.path)}
              theme={theme}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default SchemaTree;
