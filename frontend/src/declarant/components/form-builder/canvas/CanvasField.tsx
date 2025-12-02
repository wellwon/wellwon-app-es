// =============================================================================
// CanvasField - Поле на canvas с поддержкой сортировки
// =============================================================================

import React, { useState } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  GripVertical,
  Trash2,
  Type,
  Hash,
  Calendar,
  List,
  CheckSquare,
  FileText,
  ChevronDown,
  Asterisk,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFormBuilderStore } from '../../../stores/useFormBuilderStore';
import type { FormFieldConfig, FieldWidth } from '../../../types/form-builder';
import type { FieldType } from '../../../types/form-definitions';

interface CanvasFieldProps {
  field: FormFieldConfig;
  sectionId: string;
  index: number;
  isDark: boolean;
}

// Icon mapping for field types
const FIELD_TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  text: Type,
  number: Hash,
  date: Calendar,
  datetime: Calendar,
  select: List,
  checkbox: CheckSquare,
  textarea: FileText,
};

// Width options for selector
const WIDTH_OPTIONS: { value: FieldWidth; label: string }[] = [
  { value: 'full', label: '100%' },
  { value: 'three-quarters', label: '75%' },
  { value: 'two-thirds', label: '66%' },
  { value: 'half', label: '50%' },
  { value: 'third', label: '33%' },
  { value: 'quarter', label: '25%' },
];

// Определение типа поля по названию (если схема указывает text, но название содержит ключевые слова)
function inferFieldTypeFromLabel(label: string, schemaType: string): string {
  if (schemaType !== 'text') return schemaType; // Доверяем схеме если не text

  const lowerLabel = label.toLowerCase();

  // Проверка на дату: только явные паттерны со словом "дата" или "date"
  const datePatterns = [
    'дата', 'date', 'birthday', 'birthdate',
    'дата выдачи', 'дата создания', 'дата изменения', 'дата окончания', 'дата начала'
  ];

  for (const pattern of datePatterns) {
    if (lowerLabel.includes(pattern)) {
      return 'date';
    }
  }

  return schemaType;
}

export const CanvasField: React.FC<CanvasFieldProps> = ({ field, sectionId, index, isDark }) => {
  const [showWidthMenu, setShowWidthMenu] = useState(false);

  const {
    selectedFieldId,
    selectField,
    removeFieldFromSection,
    getFieldByPath,
    updateFieldInSection,
  } = useFormBuilderStore();

  const schemaField = getFieldByPath(field.schemaPath);
  const isSelected = selectedFieldId === field.id;

  // Определяем обязательность поля (из конфига или из схемы)
  const isRequired = field.required ?? schemaField?.required ?? false;

  // Get Russian label from schema
  const russianLabel = schemaField?.label_ru || '';
  const displayLabel = field.customLabel || russianLabel || field.schemaPath;

  // Определяем тип поля с учётом автоопределения по названию
  const schemaType = schemaField?.field_type || 'text';
  const inferredType = inferFieldTypeFromLabel(displayLabel, schemaType);
  const Icon = FIELD_TYPE_ICONS[inferredType] || Type;

  // Make field sortable
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: field.id,
    data: {
      type: 'canvas-field',
      field,
      sectionId,
      index,
    },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 100 : undefined,
  };

  const theme = isDark
    ? {
        bg: 'bg-white/5',
        text: 'text-white',
        textMuted: 'text-gray-400',
        border: 'border-white/10',
        hover: 'hover:bg-white/10',
        selected: 'ring-2 ring-accent-red bg-white/10',
        input: 'bg-white/5 border-white/10',
      }
    : {
        bg: 'bg-gray-50',
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        border: 'border-gray-200',
        hover: 'hover:bg-gray-100',
        selected: 'ring-2 ring-accent-red bg-gray-100',
        input: 'bg-white border-gray-200',
      };

  // Width classes based on field config (12-column grid)
  const widthClasses: Record<FieldWidth, string> = {
    full: 'col-span-12',
    'three-quarters': 'col-span-9',
    'two-thirds': 'col-span-8',
    half: 'col-span-6',
    third: 'col-span-4',
    quarter: 'col-span-3',
  };

  const variableName = field.schemaPath.split('.').pop() || field.schemaPath;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'rounded-xl border p-3 cursor-pointer group',
        // Фон для обязательных полей - полупрозрачный красный из дизайн системы
        isRequired
          ? isDark
            ? 'bg-accent-red/10 border-accent-red/30'
            : 'bg-accent-red/5 border-accent-red/20'
          : theme.bg,
        !isRequired && theme.border,
        isDragging && 'opacity-50',
        isSelected ? theme.selected : theme.hover,
        widthClasses[field.width]
      )}
      onClick={(e) => {
        e.stopPropagation();
        selectField(field.id);
      }}
    >
      {/* Header - только drag и label */}
      <div className="flex items-center gap-2 mb-2">
        {/* Drag handle */}
        <div
          {...attributes}
          {...listeners}
          className="cursor-grab active:cursor-grabbing"
        >
          <GripVertical
            className={cn('w-4 h-4 opacity-50 group-hover:opacity-100', theme.textMuted)}
          />
        </div>

        {/* Field type icon */}
        <Icon className={cn('w-4 h-4', theme.textMuted)} />

        {/* Label - русское название */}
        <span className={cn('flex-1 text-sm font-medium truncate', theme.text)}>
          {displayLabel}
          {isRequired && <span className="text-accent-red ml-1">*</span>}
        </span>
      </div>

      {/* Field preview */}
      <div className="pointer-events-none">
        <FieldPreview
          fieldType={schemaField?.field_type || 'text'}
          placeholder={field.customPlaceholder || schemaField?.placeholder_ru || ''}
          isDark={isDark}
        />
      </div>

      {/* Bottom row - variable name, width selector, delete */}
      <div className="mt-2 flex items-center gap-2">
        {/* Variable name badge */}
        <span
          className={cn(
            'text-xs font-mono px-2 py-0.5 rounded',
            isDark ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-700'
          )}
          title={field.schemaPath}
        >
          {variableName}
        </span>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Required toggle button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            updateFieldInSection(sectionId, field.id, { required: !isRequired });
          }}
          className={cn(
            'flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded ',
            isRequired
              ? 'bg-accent-red/20 text-accent-red hover:bg-accent-red/30'
              : isDark
                ? 'bg-white/10 text-gray-400 hover:bg-white/20 hover:text-gray-300'
                : 'bg-gray-200 text-gray-400 hover:bg-gray-300 hover:text-gray-500'
          )}
          title={isRequired ? 'Убрать обязательность' : 'Сделать обязательным'}
        >
          <Asterisk className="w-3 h-3" />
        </button>

        {/* Width selector dropdown */}
        <div className="relative">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowWidthMenu(!showWidthMenu);
            }}
            className={cn(
              'text-xs px-1.5 py-0.5 rounded flex items-center gap-0.5 ',
              isDark ? 'bg-white/10 hover:bg-white/20' : 'bg-gray-200 hover:bg-gray-300',
              theme.textMuted
            )}
            title="Изменить ширину"
          >
            {WIDTH_OPTIONS.find(o => o.value === field.width)?.label || '50%'}
            <ChevronDown className="w-3 h-3" />
          </button>

          {/* Width dropdown menu */}
          {showWidthMenu && (
            <div
              className={cn(
                'absolute right-0 bottom-full mb-1 py-1 rounded-lg shadow-lg z-50 min-w-[80px]',
                isDark ? 'bg-[#2a2a2e] border border-white/10' : 'bg-white border border-gray-200'
              )}
              onClick={(e) => e.stopPropagation()}
            >
              {WIDTH_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  onClick={(e) => {
                    e.stopPropagation();
                    updateFieldInSection(sectionId, field.id, { width: option.value });
                    setShowWidthMenu(false);
                  }}
                  className={cn(
                    'w-full px-3 py-1 text-xs text-left ',
                    field.width === option.value
                      ? 'bg-accent-red/20 text-accent-red'
                      : isDark
                        ? 'text-gray-300 hover:bg-white/10'
                        : 'text-gray-700 hover:bg-gray-100'
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Delete button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            removeFieldFromSection(sectionId, field.id);
          }}
          className={cn('p-1 rounded opacity-50 hover:opacity-100 ', theme.hover)}
          title="Удалить"
        >
          <Trash2 className="w-3.5 h-3.5 text-accent-red" />
        </button>
      </div>
    </div>
  );
};

// =============================================================================
// FieldPreview - Превью поля
// =============================================================================

interface FieldPreviewProps {
  fieldType: string;
  placeholder: string;
  isDark: boolean;
}

const FieldPreview: React.FC<FieldPreviewProps> = ({ fieldType, placeholder, isDark }) => {
  // Стили согласно дизайн-системе declarant
  const theme = isDark
    ? {
        input: 'bg-[#1e1e22] border-white/10 text-gray-500 hover:border-white/20',
        checkbox: 'border-white/20',
        select: 'bg-[#1e1e22] border-white/10 text-gray-500',
      }
    : {
        input: 'bg-gray-50 border-gray-300 text-gray-400 hover:border-gray-400',
        checkbox: 'border-gray-300',
        select: 'bg-gray-50 border-gray-300 text-gray-400',
      };

  switch (fieldType) {
    case 'checkbox':
      return (
        <div className="flex items-center gap-2">
          <div className={cn('w-5 h-5 rounded border-2', theme.checkbox)} />
          <span className={cn('text-sm', isDark ? 'text-gray-500' : 'text-gray-400')}>
            {placeholder || 'Да/Нет'}
          </span>
        </div>
      );

    case 'select':
      return (
        <div className={cn(
          'h-10 px-3 rounded-xl border text-sm flex items-center justify-between',
          theme.select
        )}>
          <span>{placeholder || 'Выберите значение...'}</span>
          <ChevronDown className={cn('w-4 h-4 mr-3', isDark ? 'text-gray-400' : 'text-gray-500')} />
        </div>
      );

    case 'textarea':
      return (
        <div className={cn(
          'px-3 py-2 rounded-xl border text-sm min-h-[60px] resize-none',
          theme.input
        )}>
          {placeholder || 'Введите текст...'}
        </div>
      );

    case 'date':
    case 'datetime':
      return (
        <div className={cn(
          'h-10 px-3 rounded-xl border text-sm flex items-center gap-2',
          theme.input
        )}>
          <Calendar className={cn('w-4 h-4', isDark ? 'text-gray-400' : 'text-gray-500')} />
          <span>{placeholder || 'дд.мм.гггг'}</span>
        </div>
      );

    case 'number':
      return (
        <div className={cn('h-10 px-3 rounded-xl border text-sm flex items-center', theme.input)}>
          {placeholder || '0'}
        </div>
      );

    default:
      return (
        <div className={cn('h-10 px-3 rounded-xl border text-sm flex items-center', theme.input)}>
          {placeholder || 'Введите значение...'}
        </div>
      );
  }
};

export default CanvasField;
