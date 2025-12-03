// =============================================================================
// StructurePanel - Левая панель с настройками и элементами формы
// =============================================================================

import React, { useState } from 'react';
import { useDraggable } from '@dnd-kit/core';
import {
  Settings,
  FileText,
  Type,
  Hash,
  Calendar,
  List,
  CheckSquare,
  AlignLeft,
  Eye,
  EyeOff,
  Plus,
  Trash2,
  Layers,
  Heading2,
  GripVertical,
  SplitSquareHorizontal,
  Code2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFormBuilderStore } from '../../../stores/useFormBuilderStore';
import type { FieldWidth, SelectOption } from '../../../types/form-builder';

interface StructurePanelProps {
  isDark: boolean;
  isPreviewActive?: boolean;
  onTogglePreview?: () => void;
  isJsonPreviewActive?: boolean;
  onToggleJsonPreview?: () => void;
}

type PanelTab = 'settings' | 'elements';

export const StructurePanel: React.FC<StructurePanelProps> = ({
  isDark,
  isPreviewActive,
  onTogglePreview,
  isJsonPreviewActive,
  onToggleJsonPreview,
}) => {
  const [activeTab, setActiveTab] = useState<PanelTab>('settings');

  const {
    template,
    selectedSectionId,
    selectedFieldId,
    getFieldByPath,
  } = useFormBuilderStore();

  const theme = isDark
    ? {
        text: 'text-white',
        textMuted: 'text-gray-400',
        input: 'bg-white/5 border-white/10 text-white placeholder:text-gray-500',
        label: 'text-gray-400',
        border: 'border-white/10',
        cardBg: 'bg-white/5',
        tabActive: 'bg-white/10 text-white',
        tabInactive: 'text-gray-400 hover:text-white hover:bg-white/5',
      }
    : {
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        input: 'bg-white border-gray-200 text-gray-900 placeholder:text-gray-400',
        label: 'text-gray-600',
        border: 'border-gray-200',
        cardBg: 'bg-gray-50',
        tabActive: 'bg-gray-100 text-gray-900',
        tabInactive: 'text-gray-500 hover:text-gray-900 hover:bg-gray-50',
      };

  // Находим выбранное поле (ищем во всех секциях)
  let field = null;
  let fieldSectionId = null;
  if (selectedFieldId && template) {
    for (const section of template.sections) {
      const found = section.fields.find((f) => f.id === selectedFieldId);
      if (found) {
        field = found;
        fieldSectionId = section.id;
        break;
      }
    }
  }
  const schemaField = field ? getFieldByPath(field.schemaPath) : null;

  // Кнопки предпросмотра
  const PreviewButtons = (
    <div className={cn('p-3 border-b flex gap-2', theme.border)}>
      <button
        onClick={onTogglePreview}
        className={cn(
          'flex-1 h-9 px-3 flex items-center justify-center gap-2 rounded-xl border text-sm font-medium',
          isPreviewActive
            ? 'bg-blue-500/20 text-blue-400 border-blue-500/30 hover:bg-blue-500/30'
            : isDark
              ? 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/10 hover:text-white hover:border-white/20'
              : 'bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200 hover:text-gray-900 hover:border-gray-300'
        )}
      >
        <Eye className="w-4 h-4" />
        <span>Превью</span>
      </button>
      <button
        onClick={onToggleJsonPreview}
        className={cn(
          'flex-1 h-9 px-3 flex items-center justify-center gap-2 rounded-xl border text-sm font-medium',
          isJsonPreviewActive
            ? 'bg-green-500/20 text-green-400 border-green-500/30 hover:bg-green-500/30'
            : isDark
              ? 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/10 hover:text-white hover:border-white/20'
              : 'bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200 hover:text-gray-900 hover:border-gray-300'
        )}
      >
        <Code2 className="w-4 h-4" />
        <span>JSON</span>
      </button>
    </div>
  );

  // Табы
  const TabsHeader = (
    <div className={cn('flex border-b', theme.border)}>
      <button
        onClick={() => setActiveTab('settings')}
        className={cn(
          'flex-1 px-4 py-2.5 text-sm font-medium flex items-center justify-center gap-2',
          activeTab === 'settings' ? theme.tabActive : theme.tabInactive
        )}
      >
        <Settings className="w-4 h-4" />
        Настройки
      </button>
      <button
        onClick={() => setActiveTab('elements')}
        className={cn(
          'flex-1 px-4 py-2.5 text-sm font-medium flex items-center justify-center gap-2',
          activeTab === 'elements' ? theme.tabActive : theme.tabInactive
        )}
      >
        <Layers className="w-4 h-4" />
        Элементы
      </button>
    </div>
  );

  return (
    <div className="h-full flex flex-col">
      {/* Preview buttons */}
      {PreviewButtons}

      {/* Tabs */}
      {TabsHeader}

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'settings' ? (
          <SettingsTab
            field={field}
            schemaField={schemaField}
            fieldSectionId={fieldSectionId}
            isDark={isDark}
            theme={theme}
          />
        ) : (
          <ElementsTab isDark={isDark} theme={theme} />
        )}
      </div>
    </div>
  );
};

// =============================================================================
// SettingsTab - Таб с настройками поля
// =============================================================================

interface SettingsTabProps {
  field: any;
  schemaField: any;
  fieldSectionId: string | null;
  isDark: boolean;
  theme: any;
}

const SettingsTab: React.FC<SettingsTabProps> = ({ field, schemaField, fieldSectionId, isDark, theme }) => {
  if (!field) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6">
        <Settings className={cn('w-12 h-12 mb-4 opacity-30', theme.textMuted)} />
        <p className={cn('text-center', theme.textMuted)}>
          Выберите поле на canvas для редактирования настроек
        </p>
      </div>
    );
  }

  return (
    <div className="p-4">
      <FieldProperties field={field} schemaField={schemaField} sectionId={fieldSectionId!} isDark={isDark} theme={theme} />
    </div>
  );
};

// =============================================================================
// ElementsTab - Таб с элементами формы для drag-n-drop
// =============================================================================

interface ElementsTabProps {
  isDark: boolean;
  theme: any;
}

const ElementsTab: React.FC<ElementsTabProps> = ({ isDark, theme }) => {
  // Доступные элементы формы
  const elements = [
    {
      type: 'subheading',
      label: 'Подзаголовок',
      description: 'Текстовый заголовок внутри секции',
      icon: Heading2,
    },
    {
      type: 'section-divider',
      label: 'Разделитель секции',
      description: 'Разбивает секцию на две части',
      icon: SplitSquareHorizontal,
    },
  ];

  return (
    <div className="p-4 space-y-3">
      <p className={cn('text-xs', theme.textMuted)}>
        Перетащите элемент в секцию на форме
      </p>

      {elements.map((element) => (
        <DraggableElement
          key={element.type}
          type={element.type}
          label={element.label}
          description={element.description}
          icon={element.icon}
          isDark={isDark}
          theme={theme}
        />
      ))}
    </div>
  );
};

// =============================================================================
// DraggableElement - Перетаскиваемый элемент
// =============================================================================

interface DraggableElementProps {
  type: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  isDark: boolean;
  theme: any;
}

const DraggableElement: React.FC<DraggableElementProps> = ({
  type,
  label,
  description,
  icon: Icon,
  isDark,
  theme,
}) => {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `element-${type}`,
    data: {
      type: 'form-element',
      elementType: type,
      label,
    },
  });

  // Определяем цвет иконки в зависимости от типа
  const iconColor = type === 'section-divider'
    ? (isDark ? 'text-orange-400' : 'text-orange-600')
    : (isDark ? 'text-purple-400' : 'text-purple-600');

  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className={cn(
        'p-3 rounded-xl border cursor-grab active:cursor-grabbing select-none',
        theme.cardBg,
        theme.border,
        isDragging && 'opacity-50',
        type === 'section-divider'
          ? 'hover:border-orange-500/50'
          : 'hover:border-purple-500/50'
      )}
    >
      <div className="flex items-center gap-3">
        <GripVertical className={cn('w-4 h-4', theme.textMuted)} />
        <Icon className={cn('w-5 h-5', iconColor)} />
        <div className="flex-1 min-w-0">
          <p className={cn('text-sm font-medium', theme.text)}>{label}</p>
          <p className={cn('text-xs', theme.textMuted)}>{description}</p>
        </div>
      </div>
    </div>
  );
};

// =============================================================================
// FieldProperties - Расширенные свойства поля
// =============================================================================

interface FieldPropertiesProps {
  field: any;
  schemaField: any;
  sectionId: string;
  isDark: boolean;
  theme: any;
}

const FieldProperties: React.FC<FieldPropertiesProps> = ({ field, schemaField, sectionId, isDark, theme }) => {
  const { updateField } = useFormBuilderStore();

  // Иконка типа поля
  const FIELD_TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
    text: Type,
    number: Hash,
    date: Calendar,
    datetime: Calendar,
    select: List,
    checkbox: CheckSquare,
    textarea: AlignLeft,
  };

  const Icon = FIELD_TYPE_ICONS[schemaField?.field_type || 'text'] || Type;

  const handleUpdate = (updates: any) => {
    updateField(sectionId, field.id, updates);
  };

  const widthOptions: { value: FieldWidth; label: string; icon: string }[] = [
    { value: 'full', label: '100%', icon: '████' },
    { value: 'three-quarters', label: '75%', icon: '███░' },
    { value: 'two-thirds', label: '66%', icon: '██░' },
    { value: 'half', label: '50%', icon: '██' },
    { value: 'third', label: '33%', icon: '█░' },
    { value: 'quarter', label: '25%', icon: '█' },
  ];

  // Извлекаем имя переменной (последняя часть пути)
  const variableName = field.schemaPath.split('.').pop() || field.schemaPath;

  return (
    <div className="space-y-6">
      {/* Field info */}
      <div className={cn('p-3 rounded-xl', theme.cardBg)}>
        <div className="flex items-center gap-2 mb-2">
          <Icon className={cn('w-4 h-4', theme.textMuted)} />
          <span className={cn('text-sm font-medium font-mono', isDark ? 'text-blue-400' : 'text-blue-600')}>
            {variableName}
          </span>
        </div>
        <p className={cn('text-xs break-all', theme.textMuted)}>
          {field.schemaPath}
        </p>
      </div>

      {/* Label */}
      <div>
        <label className={cn('text-xs font-medium mb-1.5 block', theme.label)}>
          Название поля
        </label>
        <input
          type="text"
          value={field.customLabel || ''}
          onChange={(e) => handleUpdate({ customLabel: e.target.value || undefined })}
          placeholder={schemaField?.label_ru || 'Название по умолчанию'}
          className={cn(
            'w-full px-3 py-2 rounded-lg border text-sm',
            theme.input
          )}
        />
        {schemaField?.label_ru && (
          <p className={cn('text-xs mt-1', theme.textMuted)}>
            По умолчанию: {schemaField.label_ru}
          </p>
        )}
      </div>

      {/* Placeholder */}
      <div>
        <label className={cn('text-xs font-medium mb-1.5 block', theme.label)}>
          Placeholder
        </label>
        <input
          type="text"
          value={field.customPlaceholder || ''}
          onChange={(e) => handleUpdate({ customPlaceholder: e.target.value || undefined })}
          placeholder={schemaField?.placeholder_ru || 'Введите текст...'}
          className={cn(
            'w-full px-3 py-2 rounded-lg border text-sm',
            theme.input
          )}
        />
        <p className={cn('text-xs mt-1.5', theme.textMuted)}>
          Текст-подсказка внутри пустого поля ввода. Исчезает при вводе.
        </p>
        {schemaField?.placeholder_ru && (
          <p className={cn('text-xs mt-1', theme.textMuted)}>
            По умолчанию: {schemaField.placeholder_ru}
          </p>
        )}
      </div>

      {/* Hint */}
      <div>
        <label className={cn('text-xs font-medium mb-1.5 block', theme.label)}>
          Подсказка
        </label>
        <textarea
          value={field.customHint || ''}
          onChange={(e) => handleUpdate({ customHint: e.target.value || undefined })}
          placeholder={schemaField?.hint_ru || 'Подсказка для пользователя...'}
          rows={2}
          className={cn(
            'w-full px-3 py-2 rounded-lg border text-sm resize-none',
            theme.input
          )}
        />
      </div>

      {/* Prompt */}
      <div>
        <label className={cn('text-xs font-medium mb-1.5 block', theme.label)}>
          Промпт
        </label>
        <textarea
          value={field.prompt !== undefined ? field.prompt : (schemaField?.label_ru || '')}
          onChange={(e) => handleUpdate({ prompt: e.target.value })}
          placeholder="Инструкция для извлечения значения из документа..."
          rows={3}
          className={cn(
            'w-full px-3 py-2 rounded-lg border text-sm resize-none',
            theme.input
          )}
        />
        <p className={cn('text-xs mt-1.5', theme.textMuted)}>
          Текст промпта для AI-извлечения значения этой переменной из документа.
        </p>
      </div>

      {/* Width - 2 rows, 3 columns */}
      <div>
        <label className={cn('text-xs font-medium mb-1.5 block', theme.label)}>
          Ширина поля
        </label>
        <div className="grid grid-cols-3 gap-2">
          {widthOptions.map((option) => (
            <button
              key={option.value}
              onClick={() => handleUpdate({ width: option.value })}
              className={cn(
                'py-2 px-2 rounded-lg border text-xs font-medium',
                field.width === option.value
                  ? 'bg-accent-red text-white border-accent-red'
                  : cn(theme.input, 'hover:border-accent-red/50')
              )}
            >
              <div className={cn('font-mono mb-0.5 text-[10px]', field.width === option.value ? 'text-white' : theme.textMuted)}>
                {option.icon}
              </div>
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Default value */}
      <div>
        <label className={cn('text-xs font-medium mb-1.5 block', theme.label)}>
          Значение по умолчанию
        </label>
        <input
          type="text"
          value={field.defaultValue || ''}
          onChange={(e) => handleUpdate({ defaultValue: e.target.value || undefined })}
          placeholder="Не задано"
          className={cn(
            'w-full px-3 py-2 rounded-lg border text-sm',
            theme.input
          )}
        />
      </div>

      {/* Checkboxes */}
      <div className="space-y-3">
        <label className={cn('flex items-center gap-3 cursor-pointer group', theme.text)}>
          <input
            type="checkbox"
            checked={field.required !== undefined ? field.required : (schemaField?.required || false)}
            onChange={(e) => handleUpdate({ required: e.target.checked })}
            className="rounded border-gray-300 text-accent-red focus:ring-accent-red"
          />
          <div className="flex items-center gap-2">
            <span className="text-sm">Обязательное</span>
            <span className="text-accent-red text-sm font-medium">*</span>
            {schemaField?.required && field.required === undefined && (
              <span className={cn('text-xs', theme.textMuted)}>(из схемы)</span>
            )}
          </div>
        </label>

        <label className={cn('flex items-center gap-3 cursor-pointer group', theme.text)}>
          <input
            type="checkbox"
            checked={field.readonly || false}
            onChange={(e) => handleUpdate({ readonly: e.target.checked })}
            className="rounded border-gray-300 text-accent-red focus:ring-accent-red"
          />
          <div className="flex items-center gap-2">
            <span className="text-sm">Только для чтения</span>
            <EyeOff className={cn('w-4 h-4', theme.textMuted)} />
          </div>
        </label>

        <label className={cn('flex items-center gap-3 cursor-pointer group', theme.text)}>
          <input
            type="checkbox"
            checked={field.isSelect || false}
            onChange={(e) => {
              handleUpdate({
                isSelect: e.target.checked,
                selectOptions: e.target.checked ? (field.selectOptions || []) : undefined
              });
            }}
            className="rounded border-gray-300 text-accent-red focus:ring-accent-red"
          />
          <div className="flex items-center gap-2">
            <span className="text-sm">Список</span>
            <List className={cn('w-4 h-4', theme.textMuted)} />
          </div>
        </label>
      </div>

      {/* Select Options Editor */}
      {field.isSelect && (
        <SelectOptionsEditor
          options={field.selectOptions || []}
          onChange={(options) => handleUpdate({ selectOptions: options })}
          isDark={isDark}
          theme={theme}
        />
      )}

      {/* Validation info from schema */}
      {(schemaField?.min_value !== undefined || schemaField?.max_value !== undefined || schemaField?.max_length || schemaField?.pattern) && (
        <div className={cn('p-3 rounded-xl', theme.cardBg)}>
          <p className={cn('text-xs font-medium mb-2', theme.label)}>Валидация из схемы:</p>
          <ul className={cn('text-xs space-y-1', theme.textMuted)}>
            {schemaField.min_value !== undefined && <li>Мин. значение: {schemaField.min_value}</li>}
            {schemaField.max_value !== undefined && <li>Макс. значение: {schemaField.max_value}</li>}
            {schemaField.max_length && <li>Макс. длина: {schemaField.max_length}</li>}
            {schemaField.pattern && <li>Паттерн: {schemaField.pattern}</li>}
          </ul>
        </div>
      )}
    </div>
  );
};

// =============================================================================
// SelectOptionsEditor - Редактор опций для поля-списка
// =============================================================================

interface SelectOptionsEditorProps {
  options: SelectOption[];
  onChange: (options: SelectOption[]) => void;
  isDark: boolean;
  theme: any;
}

const SelectOptionsEditor: React.FC<SelectOptionsEditorProps> = ({ options, onChange, isDark, theme }) => {
  const handleAddOption = () => {
    onChange([...options, { label: '', value: '' }]);
  };

  const handleRemoveOption = (index: number) => {
    const newOptions = options.filter((_, i) => i !== index);
    onChange(newOptions);
  };

  const handleUpdateOption = (index: number, field: 'label' | 'value', newValue: string) => {
    const newOptions = options.map((opt, i) =>
      i === index ? { ...opt, [field]: newValue } : opt
    );
    onChange(newOptions);
  };

  return (
    <div className={cn('p-3 rounded-xl', theme.cardBg)}>
      <div className="flex items-center justify-between mb-3">
        <label className={cn('text-xs font-medium', theme.label)}>
          Значения списка
        </label>
        <button
          onClick={handleAddOption}
          className={cn(
            'flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium',
            'bg-accent-red text-white hover:bg-accent-red/90'
          )}
        >
          <Plus className="w-3 h-3" />
          Добавить
        </button>
      </div>

      {options.length === 0 ? (
        <p className={cn('text-xs text-center py-4', theme.textMuted)}>
          Нет значений. Нажмите "Добавить" для создания опции.
        </p>
      ) : (
        <div className="space-y-2">
          {/* Header */}
          <div className="grid grid-cols-[1fr_1fr_28px] gap-2 px-1">
            <span className={cn('text-xs font-medium', theme.textMuted)}>Название</span>
            <span className={cn('text-xs font-medium', theme.textMuted)}>Значение</span>
            <span></span>
          </div>

          {/* Options */}
          {options.map((option, index) => (
            <div key={index} className="grid grid-cols-[1fr_1fr_28px] gap-2 items-center">
              <input
                type="text"
                value={option.label}
                onChange={(e) => handleUpdateOption(index, 'label', e.target.value)}
                placeholder="Мужской"
                className={cn(
                  'w-full px-2 py-1.5 rounded-lg border text-xs',
                  theme.input
                )}
              />
              <input
                type="text"
                value={option.value}
                onChange={(e) => handleUpdateOption(index, 'value', e.target.value)}
                placeholder="0"
                className={cn(
                  'w-full px-2 py-1.5 rounded-lg border text-xs',
                  theme.input
                )}
              />
              <button
                onClick={() => handleRemoveOption(index)}
                className={cn(
                  'p-1.5 rounded-lg',
                  'text-accent-red hover:bg-accent-red/10'
                )}
                title="Удалить опцию"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      <p className={cn('text-xs mt-3', theme.textMuted)}>
        Название — отображается пользователю. Значение — сохраняется в данных.
      </p>
    </div>
  );
};

export default StructurePanel;
