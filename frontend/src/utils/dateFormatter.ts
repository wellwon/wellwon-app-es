import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

export const formatTime = (date: string | Date) => {
  try {
    let dateObj: Date;
    if (typeof date === 'string') {
      // Ensure UTC timezone is properly handled
      // If no timezone info, assume UTC and append Z
      const isoString = date.endsWith('Z') || date.includes('+') || date.includes('-', 10)
        ? date
        : date + 'Z';
      dateObj = new Date(isoString);
    } else {
      dateObj = date;
    }
    // format() will automatically convert to local timezone
    return format(dateObj, 'HH:mm');
  } catch {
    return '--:--';
  }
};

const parseDate = (date: string | Date): Date => {
  if (typeof date === 'string') {
    // Ensure UTC timezone is properly handled
    const isoString = date.endsWith('Z') || date.includes('+') || date.includes('-', 10)
      ? date
      : date + 'Z';
    return new Date(isoString);
  }
  return date;
};

export const formatDate = (date: string | Date) => {
  try {
    const dateObj = parseDate(date);
    return format(dateObj, 'dd.MM.yyyy', { locale: ru });
  } catch {
    return '--.--.----';
  }
};

export const formatDateTime = (date: string | Date) => {
  try {
    const dateObj = parseDate(date);
    return format(dateObj, 'dd.MM.yyyy HH:mm', { locale: ru });
  } catch {
    return '--.--.---- --:--';
  }
};