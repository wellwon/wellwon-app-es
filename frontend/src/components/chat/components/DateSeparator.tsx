import React from 'react';
import { format, isToday, isYesterday } from 'date-fns';
import { ru } from 'date-fns/locale';
import { usePlatform } from '@/contexts/PlatformContext';

interface DateSeparatorProps {
  date: Date;
}

export function DateSeparator({ date }: DateSeparatorProps) {
  const { isLightTheme } = usePlatform();

  const formatDate = (date: Date) => {
    if (isToday(date)) {
      return 'Сегодня';
    }

    if (isYesterday(date)) {
      return 'Вчера';
    }

    return format(date, 'd MMMM', { locale: ru });
  };

  return (
    <div className="flex justify-center py-4">
      <div className={`px-4 py-2 rounded-full text-xs font-medium ${
        isLightTheme
          ? 'bg-gray-200 text-gray-600'
          : 'bg-medium-gray text-gray-400'
      }`}>
        {formatDate(date)}
      </div>
    </div>
  );
}