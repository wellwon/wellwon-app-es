import React from 'react';
import { format, isToday, isYesterday, isValid } from 'date-fns';
import { ru } from 'date-fns/locale';
import { usePlatform } from '@/contexts/PlatformContext';

interface DateSeparatorProps {
  date: Date | string;
}

export function DateSeparator({ date }: DateSeparatorProps) {
  const { isLightTheme } = usePlatform();

  // Safely convert to Date object
  const safeDate = React.useMemo(() => {
    if (!date) return null;
    const d = date instanceof Date ? date : new Date(date);
    return isValid(d) ? d : null;
  }, [date]);

  const formatDate = (d: Date) => {
    if (isToday(d)) {
      return 'Сегодня';
    }

    if (isYesterday(d)) {
      return 'Вчера';
    }

    return format(d, 'd MMMM', { locale: ru });
  };

  // Don't render if date is invalid
  if (!safeDate) {
    return null;
  }

  return (
    <div className="flex justify-center py-4">
      <div className={`px-4 py-2 rounded-full text-xs font-medium ${
        isLightTheme
          ? 'bg-gray-200 text-gray-600'
          : 'bg-medium-gray text-gray-400'
      }`}>
        {formatDate(safeDate)}
      </div>
    </div>
  );
}