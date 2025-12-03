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
  ChevronUp,
  Asterisk,
  Heading2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFormBuilderStore } from '../../../stores/useFormBuilderStore';
import type { FormFieldConfig, FieldWidth, InputFieldType } from '../../../types/form-builder';

interface CanvasFieldProps {
  field: FormFieldConfig;
  sectionId: string;
  index: number;
  isDark: boolean;
  totalFieldsInSection?: number;
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

// Field type options
const FIELD_TYPE_OPTIONS: { value: InputFieldType; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { value: 'text', label: 'Текст', icon: Type },
  { value: 'number', label: 'Число', icon: Hash },
  { value: 'date', label: 'Дата', icon: Calendar },
  { value: 'datetime', label: 'Дата и время', icon: Calendar },
  { value: 'select', label: 'Список', icon: List },
  { value: 'checkbox', label: 'Флажок', icon: CheckSquare },
  { value: 'textarea', label: 'Многострочный', icon: FileText },
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

export const CanvasField: React.FC<CanvasFieldProps> = ({ field, sectionId, index, isDark, totalFieldsInSection = 0 }) => {
  const [showWidthMenu, setShowWidthMenu] = useState(false);
  const [showTypeMenu, setShowTypeMenu] = useState(false);

  const {
    selectedFieldId,
    selectField,
    removeFieldFromSection,
    getFieldByPath,
    updateFieldInSection,
    importedValues,
  } = useFormBuilderStore();

  // Проверяем, является ли это элементом формы (не связанным со схемой)
  const isFormElement = field.schemaPath === '__element__';

  // Если это элемент формы - рендерим специальный компонент
  if (isFormElement) {
    return (
      <CanvasFormElement
        field={field}
        sectionId={sectionId}
        index={index}
        isDark={isDark}
        totalFieldsInSection={totalFieldsInSection}
      />
    );
  }

  const schemaField = getFieldByPath(field.schemaPath);
  const isSelected = selectedFieldId === field.id;

  // Определяем обязательность поля (из конфига или из схемы)
  const isRequired = field.required ?? schemaField?.required ?? false;

  // Get Russian label from schema
  const russianLabel = schemaField?.label_ru || '';
  const displayLabel = field.customLabel || russianLabel || field.schemaPath;

  // Определяем тип поля: приоритет - field.fieldType > схема > автоопределение по названию
  const schemaType = schemaField?.field_type || 'text';
  const inferredType = inferFieldTypeFromLabel(displayLabel, schemaType);
  const effectiveFieldType = field.fieldType || (field.isSelect ? 'select' : inferredType);
  const Icon = FIELD_TYPE_ICONS[effectiveFieldType] || Type;

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
          fieldType={effectiveFieldType}
          placeholder={field.customPlaceholder || schemaField?.placeholder_ru || ''}
          value={importedValues.get(field.schemaPath) || (field.defaultValue as string | undefined)}
          isDark={isDark}
        />
      </div>

      {/* Bottom row - variable name, width selector, delete */}
      {/* Для маленьких полей (quarter) используем вертикальный layout */}
      <div className={cn(
        'mt-2',
        field.width === 'quarter' ? 'flex flex-col gap-2' : 'flex items-center gap-2'
      )}>
        {/* Variable name badge */}
        <span
          className={cn(
            'text-xs font-mono px-2 py-0.5 rounded truncate',
            isDark ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-700',
            field.width === 'quarter' ? 'w-full text-center' : ''
          )}
          title={field.schemaPath}
        >
          {variableName}
        </span>

        {/* Spacer - только для горизонтального layout */}
        {field.width !== 'quarter' && <div className="flex-1" />}

        {/* Кнопки управления - в ряд для маленьких полей */}
        <div className={cn(
          'flex items-center gap-1',
          field.width === 'quarter' && 'justify-center flex-wrap'
        )}>
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

          {/* Field type selector dropdown */}
          <div className="relative">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowTypeMenu(!showTypeMenu);
                setShowWidthMenu(false);
              }}
              className={cn(
                'text-xs px-1.5 py-0.5 rounded flex items-center gap-1 ',
                isDark ? 'bg-purple-500/20 hover:bg-purple-500/30 text-purple-300' : 'bg-purple-100 hover:bg-purple-200 text-purple-700'
              )}
              title="Изменить тип поля"
            >
              <Icon className="w-3 h-3" />
              {/* Для маленьких полей показываем только иконку */}
              {field.width !== 'quarter' && (
                <>
                  {FIELD_TYPE_OPTIONS.find(o => o.value === effectiveFieldType)?.label || 'Текст'}
                  <ChevronDown className="w-3 h-3" />
                </>
              )}
            </button>

            {/* Type dropdown menu */}
            {showTypeMenu && (
              <div
                className={cn(
                  'absolute right-0 bottom-full mb-1 py-1 rounded-lg shadow-lg z-50 min-w-[120px]',
                  isDark ? 'bg-[#2a2a2e] border border-white/10' : 'bg-white border border-gray-200'
                )}
                onClick={(e) => e.stopPropagation()}
              >
                {FIELD_TYPE_OPTIONS.map((option) => {
                  const OptionIcon = option.icon;
                  return (
                    <button
                      key={option.value}
                      onClick={(e) => {
                        e.stopPropagation();
                        updateFieldInSection(sectionId, field.id, { fieldType: option.value });
                        setShowTypeMenu(false);
                      }}
                      className={cn(
                        'w-full px-3 py-1.5 text-xs text-left flex items-center gap-2',
                        effectiveFieldType === option.value
                          ? 'bg-purple-500/20 text-purple-400'
                          : isDark
                            ? 'text-gray-300 hover:bg-white/10'
                            : 'text-gray-700 hover:bg-gray-100'
                      )}
                    >
                      <OptionIcon className="w-3.5 h-3.5" />
                      {option.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Width selector dropdown */}
          <div className="relative">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowWidthMenu(!showWidthMenu);
                setShowTypeMenu(false);
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
    </div>
  );
};

// =============================================================================
// FieldPreview - Превью поля
// =============================================================================

interface FieldPreviewProps {
  fieldType: string;
  placeholder: string;
  value?: string;
  isDark: boolean;
}

const FieldPreview: React.FC<FieldPreviewProps> = ({ fieldType, placeholder, value, isDark }) => {
  // Стили согласно дизайн-системе declarant
  const hasValue = value !== undefined && value !== '';

  const theme = isDark
    ? {
        input: 'bg-[#1e1e22] border-white/10 hover:border-white/20',
        inputText: hasValue ? 'text-white' : 'text-gray-500',
        checkbox: 'border-white/20',
        select: 'bg-[#1e1e22] border-white/10',
        selectText: hasValue ? 'text-white' : 'text-gray-500',
      }
    : {
        input: 'bg-gray-50 border-gray-300 hover:border-gray-400',
        inputText: hasValue ? 'text-gray-900' : 'text-gray-400',
        checkbox: 'border-gray-300',
        select: 'bg-gray-50 border-gray-300',
        selectText: hasValue ? 'text-gray-900' : 'text-gray-400',
      };

  // Truncate long values for display
  const displayValue = value && value.length > 50 ? value.substring(0, 50) + '...' : value;

  switch (fieldType) {
    case 'checkbox':
      return (
        <div className="flex items-center gap-2">
          <div className={cn(
            'w-5 h-5 rounded border-2 flex items-center justify-center',
            theme.checkbox,
            value === 'true' && 'bg-accent-red border-accent-red'
          )}>
            {value === 'true' && (
              <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            )}
          </div>
          <span className={cn('text-sm', isDark ? 'text-gray-500' : 'text-gray-400')}>
            {placeholder || 'Да/Нет'}
          </span>
        </div>
      );

    case 'select':
      return (
        <div className={cn(
          'h-10 px-3 rounded-xl border text-sm flex items-center justify-between',
          theme.select,
          theme.selectText
        )}>
          <span className="truncate">{displayValue || placeholder || 'Выберите значение...'}</span>
          <ChevronDown className={cn('w-4 h-4 mr-3 flex-shrink-0', isDark ? 'text-gray-400' : 'text-gray-500')} />
        </div>
      );

    case 'textarea':
      return (
        <div className={cn(
          'px-3 py-2 rounded-xl border text-sm min-h-[60px] resize-none',
          theme.input,
          theme.inputText
        )}>
          {displayValue || placeholder || 'Введите текст...'}
        </div>
      );

    case 'date':
    case 'datetime':
      return (
        <div className={cn(
          'h-10 px-3 rounded-xl border text-sm flex items-center gap-2',
          theme.input,
          theme.inputText
        )}>
          <Calendar className={cn('w-4 h-4 flex-shrink-0', isDark ? 'text-gray-400' : 'text-gray-500')} />
          <span className="truncate">{displayValue || placeholder || 'дд.мм.гггг'}</span>
        </div>
      );

    case 'number':
      return (
        <div className={cn(
          'h-10 px-3 rounded-xl border text-sm flex items-center',
          theme.input,
          theme.inputText
        )}>
          {displayValue || placeholder || '0'}
        </div>
      );

    default:
      return (
        <div className={cn(
          'h-10 px-3 rounded-xl border text-sm flex items-center',
          theme.input,
          theme.inputText
        )}>
          <span className="truncate">{displayValue || placeholder || 'Введите значение...'}</span>
        </div>
      );
  }
};

// =============================================================================
// CanvasFormElement - Элемент формы (подзаголовок и т.д.)
// =============================================================================

interface CanvasFormElementProps {
  field: FormFieldConfig;
  sectionId: string;
  index: number;
  isDark: boolean;
  totalFieldsInSection: number;
}

const CanvasFormElement: React.FC<CanvasFormElementProps> = ({ field, sectionId, index, isDark, totalFieldsInSection }) => {
  const {
    selectedFieldId,
    selectField,
    removeFieldFromSection,
    updateFieldInSection,
    reorderFieldsInSection,
  } = useFormBuilderStore();

  const isSelected = selectedFieldId === field.id;
  const isFirst = index === 0;
  const isLast = index === totalFieldsInSection - 1;

  // Make element sortable
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
        bg: 'bg-transparent',
        text: 'text-white',
        textMuted: 'text-gray-400',
        border: 'border-purple-500/30',
        hover: 'hover:bg-purple-500/10',
        selected: 'ring-2 ring-purple-500 bg-purple-500/10',
        line: 'bg-gradient-to-r from-transparent via-purple-500/50 to-transparent',
      }
    : {
        bg: 'bg-transparent',
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        border: 'border-purple-200',
        hover: 'hover:bg-purple-50',
        selected: 'ring-2 ring-purple-500 bg-purple-50',
        line: 'bg-gradient-to-r from-transparent via-purple-400/50 to-transparent',
      };

  // Для отображения используем customLabel, для редактирования - тоже, но без fallback
  const displayLabel = field.customLabel || '';

  // Перемещение поля вверх/вниз
  const handleMoveUp = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isFirst) {
      reorderFieldsInSection(sectionId, index, index - 1);
    }
  };

  const handleMoveDown = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isLast) {
      reorderFieldsInSection(sectionId, index, index + 1);
    }
  };

  // Подзаголовок - визуальный разделитель с редактируемым текстом
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'col-span-12 py-2 cursor-pointer group relative',
        isDragging && 'opacity-50',
        isSelected && 'bg-purple-500/10 rounded-xl'
      )}
      onClick={(e) => {
        e.stopPropagation();
        selectField(field.id);
      }}
    >
      {/* Визуальный разделитель с заголовком */}
      <div className="flex items-center gap-3">
        {/* Левая линия */}
        <div className={cn('flex-1 h-px', theme.line)} />

        {/* Центральный блок с drag handle, иконкой и текстом */}
        <div
          className={cn(
            'flex items-center gap-2 px-3 py-1.5 rounded-lg border',
            'bg-gradient-to-r',
            isDark
              ? 'from-purple-500/10 to-purple-600/10 border-purple-500/30'
              : 'from-purple-50 to-purple-100 border-purple-200',
            isSelected && 'ring-2 ring-purple-500'
          )}
        >
          {/* Drag handle */}
          <div
            {...attributes}
            {...listeners}
            className="cursor-grab active:cursor-grabbing opacity-50 hover:opacity-100"
          >
            <GripVertical className={cn('w-4 h-4', theme.textMuted)} />
          </div>

          {/* Icon */}
          <Heading2 className={cn('w-4 h-4', isDark ? 'text-purple-400' : 'text-purple-600')} />

          {/* Editable label */}
          <input
            type="text"
            value={displayLabel}
            onChange={(e) => {
              e.stopPropagation();
              updateFieldInSection(sectionId, field.id, { customLabel: e.target.value });
            }}
            onClick={(e) => e.stopPropagation()}
            className={cn(
              'bg-transparent font-semibold text-sm border-none outline-none min-w-[100px]',
              isDark ? 'text-purple-300' : 'text-purple-700',
              'placeholder:text-purple-400/50'
            )}
            placeholder="Введите заголовок..."
          />

          {/* Actions - visible on hover */}
          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
            {/* Move Up */}
            <button
              onClick={handleMoveUp}
              disabled={isFirst}
              className={cn(
                'p-1 rounded',
                isFirst ? 'opacity-30 cursor-not-allowed' : 'hover:bg-purple-500/20'
              )}
              title="Переместить вверх"
            >
              <ChevronUp className={cn('w-3.5 h-3.5', theme.textMuted)} />
            </button>

            {/* Move Down */}
            <button
              onClick={handleMoveDown}
              disabled={isLast}
              className={cn(
                'p-1 rounded',
                isLast ? 'opacity-30 cursor-not-allowed' : 'hover:bg-purple-500/20'
              )}
              title="Переместить вниз"
            >
              <ChevronDown className={cn('w-3.5 h-3.5', theme.textMuted)} />
            </button>

            {/* Delete */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeFieldFromSection(sectionId, field.id);
              }}
              className="p-1 rounded hover:bg-accent-red/20"
              title="Удалить"
            >
              <Trash2 className="w-3.5 h-3.5 text-accent-red" />
            </button>
          </div>
        </div>

        {/* Правая линия */}
        <div className={cn('flex-1 h-px', theme.line)} />
      </div>
    </div>
  );
};

export default CanvasField;
