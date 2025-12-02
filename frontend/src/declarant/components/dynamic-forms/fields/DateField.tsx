// =============================================================================
// DateField - Date input field component with masked input and validation
// =============================================================================

import React, { useState, useEffect } from 'react';
import { Calendar } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { FieldComponentProps } from '../../../types/form-definitions';
import { FieldLabel } from './FieldLabel';

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

// Конвертация ISO даты (YYYY-MM-DD) в формат дд.мм.гггг
function isoToDisplay(isoDate: string): string {
  if (!isoDate) return '';
  const match = isoDate.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (match) {
    return `${match[3]}.${match[2]}.${match[1]}`;
  }
  return isoDate;
}

// Конвертация дд.мм.гггг в ISO формат (YYYY-MM-DD)
function displayToIso(displayDate: string): string {
  if (!displayDate || displayDate.length !== 10) return '';
  const parts = displayDate.split('.');
  if (parts.length === 3) {
    return `${parts[2]}-${parts[1]}-${parts[0]}`;
  }
  return '';
}

export const DateField: React.FC<FieldComponentProps> = ({
  field,
  value,
  error,
  onChange,
  onBlur,
  isDark,
  disabled = false,
}) => {
  // Внутреннее значение в формате дд.мм.гггг
  const [displayValue, setDisplayValue] = useState(() => {
    if (typeof value === 'string' && value) {
      return isoToDisplay(value);
    }
    return '';
  });
  const [validationError, setValidationError] = useState<string | null>(null);

  // Синхронизация с внешним значением
  useEffect(() => {
    if (typeof value === 'string' && value) {
      const converted = isoToDisplay(value);
      if (converted !== displayValue) {
        setDisplayValue(converted);
      }
    } else if (!value && displayValue) {
      setDisplayValue('');
    }
  }, [value]);

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

    setDisplayValue(formatted);

    // Валидация полной даты
    if (input.length === 8) {
      const dayNum = parseInt(input.slice(0, 2), 10);
      const monthNum = parseInt(input.slice(2, 4), 10);
      const yearNum = parseInt(input.slice(4, 8), 10);

      if (isValidDate(dayNum, monthNum, yearNum)) {
        setValidationError(null);
        // Отправляем в ISO формате
        const isoValue = displayToIso(formatted);
        onChange(isoValue);
      } else {
        setValidationError('Некорректная дата');
        onChange('');
      }
    } else {
      setValidationError(null);
      onChange('');
    }
  };

  const hasError = error || validationError;

  return (
    <div className="space-y-1.5">
      <FieldLabel
        label={field.label_ru || field.name}
        fieldName={field.name}
        fieldPath={field.path}
        required={field.required}
        isDark={isDark}
      />

      <div className="relative">
        <input
          type="text"
          value={displayValue}
          onChange={handleChange}
          onBlur={onBlur}
          disabled={disabled}
          placeholder="__.__.____"
          maxLength={10}
          className={cn(
            'w-full h-10 rounded-xl border px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-0',
            isDark
              ? 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500 hover:border-white/20'
              : 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400 hover:border-gray-400',
            hasError && 'border-red-500',
            disabled && 'opacity-60 cursor-not-allowed'
          )}
        />
        <Calendar className={cn(
          'absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none',
          hasError ? 'text-red-500' : (isDark ? 'text-gray-400' : 'text-gray-500')
        )} />
      </div>

      {field.hint_ru && !hasError && (
        <p className={cn('text-xs', isDark ? 'text-gray-500' : 'text-gray-400')}>
          {field.hint_ru}
        </p>
      )}

      {(error || validationError) && (
        <p className="text-xs text-red-500">{error || validationError}</p>
      )}
    </div>
  );
};
