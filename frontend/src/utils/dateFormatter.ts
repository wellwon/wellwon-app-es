import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

export const formatTime = (date: string | Date) => {
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    return format(dateObj, 'HH:mm');
  } catch {
    return '--:--';
  }
};

export const formatDate = (date: string | Date) => {
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    return format(dateObj, 'dd.MM.yyyy', { locale: ru });
  } catch {
    return '--.--.----';
  }
};

export const formatDateTime = (date: string | Date) => {
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    return format(dateObj, 'dd.MM.yyyy HH:mm', { locale: ru });
  } catch {
    return '--.--.---- --:--';
  }
};