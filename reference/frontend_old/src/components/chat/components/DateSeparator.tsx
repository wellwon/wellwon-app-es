import React from 'react';
import { format, isToday, isYesterday } from 'date-fns';
import { ru } from 'date-fns/locale';

interface DateSeparatorProps {
  date: Date;
}

export function DateSeparator({ date }: DateSeparatorProps) {
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
      <div className="bg-medium-gray px-4 py-2 rounded-full text-xs text-gray-400 font-medium">
        {formatDate(date)}
      </div>
    </div>
  );
}