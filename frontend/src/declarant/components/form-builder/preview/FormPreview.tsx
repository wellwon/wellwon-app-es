// =============================================================================
// FormPreview - Превью формы в реальном времени
// =============================================================================

import React, { useMemo } from 'react';
import { Eye, Monitor, Tablet, Smartphone, RefreshCw, Calendar } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFormBuilderStore } from '../../../stores/useFormBuilderStore';
import type { FormFieldConfig, FormSectionConfig, SelectOption } from '../../../types/form-builder';

interface FormPreviewProps {
  isDark: boolean;
  formWidth?: number; // Ширина формы в %
}

type ViewportSize = 'desktop' | 'tablet' | 'mobile';

export const FormPreview: React.FC<FormPreviewProps> = ({ isDark, formWidth = 100 }) => {
  const { template, getFieldByPath } = useFormBuilderStore();
  const [viewport, setViewport] = React.useState<ViewportSize>('desktop');

  const theme = isDark
    ? {
        bg: 'bg-[#1a1a1e]',
        text: 'text-white',
        textMuted: 'text-gray-400',
        cardBg: 'bg-[#232328]',
        border: 'border-white/10',
        input: 'bg-white/5 border-white/10 text-white placeholder:text-gray-500',
      }
    : {
        bg: 'bg-[#f4f4f4]',
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        cardBg: 'bg-white',
        border: 'border-gray-200',
        input: 'bg-white border-gray-200 text-gray-900 placeholder:text-gray-400',
      };

  const viewportWidths: Record<ViewportSize, string> = {
    desktop: 'max-w-4xl',
    tablet: 'max-w-2xl',
    mobile: 'max-w-sm',
  };

  if (!template) {
    return (
      <div className={cn('h-full flex items-center justify-center', theme.bg)}>
        <div className="text-center">
          <Eye className={cn('w-12 h-12 mx-auto mb-4 opacity-30', theme.textMuted)} />
          <p className={theme.textMuted}>Шаблон не загружен</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('h-full flex flex-col', theme.bg)}>
      {/* Viewport selector */}
      <div className={cn('flex items-center justify-center gap-2 p-4 border-b', theme.border)}>
        <button
          onClick={() => setViewport('desktop')}
          className={cn(
            'p-2 rounded-lg transition-colors',
            viewport === 'desktop'
              ? 'bg-accent-red text-white'
              : cn(theme.textMuted, 'hover:bg-white/10')
          )}
          title="Desktop"
        >
          <Monitor className="w-5 h-5" />
        </button>
        <button
          onClick={() => setViewport('tablet')}
          className={cn(
            'p-2 rounded-lg transition-colors',
            viewport === 'tablet'
              ? 'bg-accent-red text-white'
              : cn(theme.textMuted, 'hover:bg-white/10')
          )}
          title="Tablet"
        >
          <Tablet className="w-5 h-5" />
        </button>
        <button
          onClick={() => setViewport('mobile')}
          className={cn(
            'p-2 rounded-lg transition-colors',
            viewport === 'mobile'
              ? 'bg-accent-red text-white'
              : cn(theme.textMuted, 'hover:bg-white/10')
          )}
          title="Mobile"
        >
          <Smartphone className="w-5 h-5" />
        </button>
      </div>

      {/* Preview content */}
      <div className="flex-1 overflow-auto p-6">
        <div
          className={cn('mx-auto', viewport !== 'desktop' && viewportWidths[viewport])}
          style={{
            // Desktop: вычисляем ширину относительно базовой (56rem)
            maxWidth: viewport === 'desktop' ? `${(56 * formWidth) / 100}rem` : undefined,
            width: viewport === 'desktop' ? '100%' : undefined,
          }}
        >
          {template.sections.length === 0 ? (
            <div
              className={cn(
                'rounded-2xl border p-12 text-center',
                theme.cardBg,
                theme.border
              )}
            >
              <p className={theme.textMuted}>
                Добавьте секции и поля, чтобы увидеть превью формы
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {template.sections.map((section) => (
                <PreviewSection
                  key={section.id}
                  section={section}
                  isDark={isDark}
                  getFieldByPath={getFieldByPath}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// =============================================================================
// PreviewSection - Секция в превью
// =============================================================================

interface PreviewSectionProps {
  section: FormSectionConfig;
  isDark: boolean;
  getFieldByPath: (path: string) => any;
}

const PreviewSection: React.FC<PreviewSectionProps> = ({ section, isDark, getFieldByPath }) => {
  const [isExpanded, setIsExpanded] = React.useState(section.defaultExpanded);

  const theme = isDark
    ? {
        cardBg: 'bg-[#232328]',
        text: 'text-white',
        textMuted: 'text-gray-400',
        border: 'border-white/10',
      }
    : {
        cardBg: 'bg-white',
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        border: 'border-gray-200',
      };

  // Always use 12-column grid for flexible field widths
  // Fields determine their width via col-span-* classes

  return (
    <div className={cn('rounded-2xl border', theme.cardBg, theme.border)}>
      {/* Section header */}
      <div
        className={cn(
          'flex items-center gap-3 px-5 py-4',
          section.collapsible && 'cursor-pointer',
          isExpanded && `border-b ${theme.border}`
        )}
        onClick={() => section.collapsible && setIsExpanded(!isExpanded)}
      >
        <h3 className={cn('font-semibold text-lg', theme.text)}>{section.titleRu}</h3>
        {section.collapsible && (
          <span className={cn('text-sm', theme.textMuted)}>
            {isExpanded ? '▼' : '▶'}
          </span>
        )}
      </div>

      {/* Section content */}
      {(!section.collapsible || isExpanded) && (
        <div className="p-5">
          {section.fields.length === 0 ? (
            <p className={cn('text-sm', theme.textMuted)}>Нет полей в секции</p>
          ) : (
            <div className="grid grid-cols-12 gap-4">
              {section.fields.map((field) => (
                <PreviewField
                  key={field.id}
                  field={field}
                  isDark={isDark}
                  getFieldByPath={getFieldByPath}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// =============================================================================
// PreviewField - Поле в превью
// =============================================================================

interface PreviewFieldProps {
  field: FormFieldConfig;
  isDark: boolean;
  getFieldByPath: (path: string) => any;
}

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

const PreviewField: React.FC<PreviewFieldProps> = ({ field, isDark, getFieldByPath }) => {
  const schemaField = getFieldByPath(field.schemaPath);

  // Унифицированные стили из dynamic-forms
  const theme = isDark
    ? {
        text: 'text-white',
        textMuted: 'text-gray-400',
        input: 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500 hover:border-white/20',
        checkbox: 'bg-white/10 border-white/20',
        icon: 'text-gray-400',
        colorScheme: '[color-scheme:dark]',
      }
    : {
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        input: 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400 hover:border-gray-400',
        checkbox: 'bg-gray-100 border-gray-300',
        icon: 'text-gray-500',
        colorScheme: '',
      };

  // Width classes based on field config (12-column grid)
  const widthClasses: Record<string, string> = {
    full: 'col-span-12',
    'three-quarters': 'col-span-9',
    'two-thirds': 'col-span-8',
    half: 'col-span-6',
    third: 'col-span-4',
    quarter: 'col-span-3',
  };

  const label = field.customLabel || schemaField?.label_ru || field.schemaPath;
  const placeholder = field.customPlaceholder || schemaField?.placeholder_ru || '';

  // Определяем тип поля:
  // 1. Если isSelect - рендерим select
  // 2. Иначе берём тип из схемы и проверяем по названию (автоопределение даты)
  const schemaType = schemaField?.field_type || 'text';
  const inferredType = inferFieldTypeFromLabel(label, schemaType);
  const fieldType = field.isSelect ? 'select' : inferredType;
  const isRequired = field.required ?? schemaField?.required ?? false;

  return (
    <div className={cn(widthClasses[field.width] || 'col-span-6')}>
      {/* Label */}
      <label className={cn('block text-sm font-medium mb-1.5', theme.text)}>
        {label}
        {isRequired && <span className="text-red-500 ml-1">*</span>}
      </label>

      {/* Input based on field type */}
      {renderFieldInput(fieldType, placeholder, field.readonly || false, theme, field.selectOptions, isDark, isRequired)}

      {/* Helper text */}
      {(field.customHint || schemaField?.hint_ru) && (
        <p className={cn('mt-1 text-xs', theme.textMuted)}>{field.customHint || schemaField?.hint_ru}</p>
      )}
    </div>
  );
};

// =============================================================================
// Компоненты полей ввода с отслеживанием состояния заполненности
// =============================================================================

interface FieldInputProps {
  placeholder: string;
  readonly: boolean;
  theme: Record<string, string>;
  isDark?: boolean;
  isRequired?: boolean;
}

// Хук для получения классов стиля с учётом заполненности
function useFieldStyles(
  theme: Record<string, string>,
  isDark: boolean | undefined,
  isRequired: boolean | undefined,
  hasValue: boolean,
  readonly: boolean
) {
  // Красный стиль только для пустых обязательных полей
  const showRequiredStyle = isRequired && !hasValue;

  const requiredStyle = showRequiredStyle
    ? isDark
      ? 'bg-accent-red/10 border-accent-red/30'
      : 'bg-accent-red/5 border-accent-red/20'
    : '';

  return cn(
    'w-full h-10 px-3 py-2 rounded-xl border text-sm transition-colors',
    'focus:outline-none focus:ring-0',
    showRequiredStyle ? requiredStyle : theme.input,
    readonly && 'opacity-60 cursor-not-allowed'
  );
}

// Текстовое поле
const TextFieldInput: React.FC<FieldInputProps> = ({ placeholder, readonly, theme, isDark, isRequired }) => {
  const [value, setValue] = React.useState('');
  const className = useFieldStyles(theme, isDark, isRequired, value.length > 0, readonly);

  return (
    <input
      type="text"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      placeholder={placeholder || 'Введите значение...'}
      readOnly={readonly}
      className={className}
    />
  );
};

// Числовое поле
const NumberFieldInput: React.FC<FieldInputProps> = ({ placeholder, readonly, theme, isDark, isRequired }) => {
  const [value, setValue] = React.useState('');
  const className = useFieldStyles(theme, isDark, isRequired, value.length > 0, readonly);

  return (
    <input
      type="number"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      placeholder={placeholder || '0'}
      readOnly={readonly}
      className={className}
    />
  );
};

// Textarea
const TextareaFieldInput: React.FC<FieldInputProps> = ({ placeholder, readonly, theme, isDark, isRequired }) => {
  const [value, setValue] = React.useState('');
  const className = useFieldStyles(theme, isDark, isRequired, value.length > 0, readonly);

  return (
    <textarea
      value={value}
      onChange={(e) => setValue(e.target.value)}
      placeholder={placeholder || 'Введите текст...'}
      readOnly={readonly}
      rows={4}
      className={cn(className, 'h-auto resize-none')}
    />
  );
};

// Datetime поле
const DatetimeFieldInput: React.FC<FieldInputProps> = ({ readonly, theme, isDark, isRequired }) => {
  const [value, setValue] = React.useState('');
  const className = useFieldStyles(theme, isDark, isRequired, value.length > 0, readonly);

  return (
    <div className="relative">
      <input
        type="datetime-local"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        readOnly={readonly}
        className={cn(className, theme.colorScheme)}
      />
    </div>
  );
};

// Select поле
interface SelectFieldInputProps extends FieldInputProps {
  selectOptions?: SelectOption[];
}

const SelectFieldInput: React.FC<SelectFieldInputProps> = ({
  placeholder, readonly, theme, isDark, isRequired, selectOptions
}) => {
  const [value, setValue] = React.useState('');
  const className = useFieldStyles(theme, isDark, isRequired, value.length > 0, readonly);

  return (
    <select
      value={value}
      onChange={(e) => setValue(e.target.value)}
      disabled={readonly}
      className={cn(className, 'pr-8')}
    >
      <option value="">{placeholder || 'Выберите значение...'}</option>
      {selectOptions && selectOptions.length > 0 ? (
        selectOptions.map((opt, idx) => (
          <option key={idx} value={opt.value}>
            {opt.label || opt.value}
          </option>
        ))
      ) : (
        <>
          <option value="1">Вариант 1</option>
          <option value="2">Вариант 2</option>
        </>
      )}
    </select>
  );
};

// Checkbox поле
interface CheckboxFieldInputProps {
  placeholder: string;
  readonly: boolean;
  theme: Record<string, string>;
}

const CheckboxFieldInput: React.FC<CheckboxFieldInputProps> = ({ placeholder, readonly, theme }) => {
  return (
    <div className="flex items-center gap-2">
      <input
        type="checkbox"
        disabled={readonly}
        className={cn('w-4 h-4 rounded', theme.checkbox)}
      />
      <span className={cn('text-sm', theme.textMuted)}>
        {placeholder || 'Да/Нет'}
      </span>
    </div>
  );
};

// Helper function to render field input based on type
function renderFieldInput(
  fieldType: string,
  placeholder: string,
  readonly: boolean,
  theme: Record<string, string>,
  selectOptions?: SelectOption[],
  isDark?: boolean,
  isRequired?: boolean
) {
  const baseProps = { placeholder, readonly, theme, isDark, isRequired };

  switch (fieldType) {
    case 'checkbox':
      return <CheckboxFieldInput placeholder={placeholder} readonly={readonly} theme={theme} />;

    case 'select':
      return <SelectFieldInput {...baseProps} selectOptions={selectOptions} />;

    case 'textarea':
      return <TextareaFieldInput {...baseProps} />;

    case 'date':
      return (
        <DateMaskedInput
          placeholder={placeholder || '__.__.____'}
          readonly={readonly}
          isDark={isDark}
          isRequired={isRequired}
          theme={theme}
        />
      );

    case 'datetime':
      return <DatetimeFieldInput {...baseProps} />;

    case 'number':
      return <NumberFieldInput {...baseProps} />;

    default:
      return <TextFieldInput {...baseProps} />;
  }
}

// =============================================================================
// DateMaskedInput - Поле даты с маской дд.мм.гггг и валидацией
// =============================================================================

interface DateMaskedInputProps {
  placeholder?: string;
  readonly?: boolean;
  isDark?: boolean;
  isRequired?: boolean;
  theme?: Record<string, string>;
}

// Проверка валидности даты
function isValidDate(day: number, month: number, year: number): boolean {
  // Месяц должен быть 1-12
  if (month < 1 || month > 12) return false;

  // День должен быть минимум 1
  if (day < 1) return false;

  // Количество дней в месяце
  const daysInMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

  // Проверка високосного года для февраля
  if (month === 2) {
    const isLeapYear = (year % 4 === 0 && year % 100 !== 0) || (year % 400 === 0);
    if (isLeapYear && day > 29) return false;
    if (!isLeapYear && day > 28) return false;
  } else {
    if (day > daysInMonth[month - 1]) return false;
  }

  // Год в разумных пределах (1900-2100)
  if (year < 1900 || year > 2100) return false;

  return true;
}

// Корректировка значения при вводе
function clampDatePart(value: string, part: 'day' | 'month' | 'year'): string {
  const num = parseInt(value, 10);
  if (isNaN(num)) return value;

  switch (part) {
    case 'day':
      // Первая цифра дня: 0-3
      if (value.length === 1 && num > 3) return '0' + value;
      // Полный день: 01-31
      if (value.length === 2 && num > 31) return '31';
      if (value.length === 2 && num < 1) return '01';
      break;
    case 'month':
      // Первая цифра месяца: 0-1
      if (value.length === 1 && num > 1) return '0' + value;
      // Полный месяц: 01-12
      if (value.length === 2 && num > 12) return '12';
      if (value.length === 2 && num < 1) return '01';
      break;
    case 'year':
      // Год оставляем как есть при вводе
      break;
  }
  return value;
}

const DateMaskedInput: React.FC<DateMaskedInputProps> = ({
  placeholder = '__.__.____',
  readonly = false,
  isDark,
  isRequired,
  theme,
}) => {
  const [value, setValue] = React.useState('');
  const [hasError, setHasError] = React.useState(false);

  // Определяем, нужен ли красный стиль (обязательное + пустое)
  const hasValue = value.length > 0;
  const showRequiredStyle = isRequired && !hasValue;

  const requiredStyle = showRequiredStyle
    ? isDark
      ? 'bg-accent-red/10 border-accent-red/30'
      : 'bg-accent-red/5 border-accent-red/20'
    : '';

  const baseInputClass = cn(
    'w-full h-10 px-3 py-2 rounded-xl border text-sm transition-colors',
    'focus:outline-none focus:ring-0',
    showRequiredStyle ? requiredStyle : (theme?.input || ''),
    readonly && 'opacity-60 cursor-not-allowed'
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let input = e.target.value.replace(/\D/g, ''); // Только цифры

    // Ограничиваем до 8 цифр (ddmmyyyy)
    if (input.length > 8) {
      input = input.slice(0, 8);
    }

    // Корректируем значения при вводе
    let day = input.slice(0, 2);
    let month = input.slice(2, 4);
    let year = input.slice(4, 8);

    // Автокоррекция дня и месяца
    if (day.length > 0) {
      day = clampDatePart(day, 'day');
    }
    if (month.length > 0) {
      month = clampDatePart(month, 'month');
    }

    // Собираем обратно
    input = day + month + year;

    // Форматируем с точками
    let formatted = '';
    if (input.length > 0) {
      formatted = input.slice(0, 2);
    }
    if (input.length > 2) {
      formatted += '.' + input.slice(2, 4);
    }
    if (input.length > 4) {
      formatted += '.' + input.slice(4, 8);
    }

    setValue(formatted);

    // Валидация полной даты
    if (input.length === 8) {
      const dayNum = parseInt(input.slice(0, 2), 10);
      const monthNum = parseInt(input.slice(2, 4), 10);
      const yearNum = parseInt(input.slice(4, 8), 10);
      setHasError(!isValidDate(dayNum, monthNum, yearNum));
    } else {
      setHasError(false);
    }
  };

  return (
    <div className="relative">
      <input
        type="text"
        value={value}
        onChange={handleChange}
        placeholder={placeholder}
        readOnly={readonly}
        maxLength={10}
        className={cn(baseInputClass, hasError && 'border-red-500 focus:border-red-500')}
      />
      <Calendar className={cn(
        'absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none',
        hasError ? 'text-red-500' : (isDark ? 'text-gray-400' : 'text-gray-500')
      )} />
    </div>
  );
}

export default FormPreview;
