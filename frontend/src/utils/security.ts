// Утилиты для безопасности
import { logger } from './logger';

// Шифрование данных для localStorage
const SECRET_KEY = 'wellwon_secret_2024';

export const encryptData = (data: string): string => {
  try {
    // Простое шифрование для демонстрации (в продакшене используйте crypto API)
    const encrypted = btoa(
      data
        .split('')
        .map((char, i) => 
          String.fromCharCode(char.charCodeAt(0) ^ SECRET_KEY.charCodeAt(i % SECRET_KEY.length))
        )
        .join('')
    );
    return encrypted;
  } catch {
    return data; // Fallback если шифрование не удалось
  }
};

export const decryptData = (encryptedData: string): string => {
  try {
    const decrypted = atob(encryptedData)
      .split('')
      .map((char, i) => 
        String.fromCharCode(char.charCodeAt(0) ^ SECRET_KEY.charCodeAt(i % SECRET_KEY.length))
      )
      .join('');
    return decrypted;
  } catch {
    return encryptedData; // Fallback если расшифровка не удалась
  }
};

// Безопасное сохранение в localStorage
export const secureSetItem = (key: string, value: string): void => {
  try {
    const encrypted = encryptData(value);
    const timestamp = Date.now();
    const dataWithExpiry = JSON.stringify({ data: encrypted, timestamp });
    localStorage.setItem(key, dataWithExpiry);
  } catch (error) {
    logger.error('Secure save error', error, { component: 'security' });
  }
};

// Безопасное получение из localStorage с проверкой срока действия
export const secureGetItem = (key: string, maxAge: number = 24 * 60 * 60 * 1000): string | null => {
  try {
    const item = localStorage.getItem(key);
    if (!item) return null;
    
    const { data, timestamp } = JSON.parse(item);
    
    // Проверяем срок действия
    if (Date.now() - timestamp > maxAge) {
      localStorage.removeItem(key);
      return null;
    }
    
    return decryptData(data);
  } catch (error) {
    logger.error('Secure get error', error, { component: 'security' });
    localStorage.removeItem(key);
    return null;
  }
};

// Очистка устаревших данных
export const cleanupExpiredData = (): void => {
  try {
    const keys = Object.keys(localStorage);
    keys.forEach(key => {
      if (key.startsWith('wellwon_')) {
        secureGetItem(key); // Вызывает автоматическую очистку устаревших данных
      }
    });
  } catch (error) {
    logger.error('Data cleanup error', error, { component: 'security' });
  }
};

// Валидация и санитизация входных данных
export const sanitizeInput = (input: string): string => {
  if (typeof input !== 'string') return '';
  
  return input
    .trim()
    .replace(/[<>\"'&]/g, (match) => {
      const entities: Record<string, string> = {
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '&': '&amp;'
      };
      return entities[match] || match;
    });
};

// Валидация email
export const validateEmail = (email: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email.trim());
};

// Валидация телефона
export const validatePhone = (phone: string): boolean => {
  const phoneRegex = /^[\+]?[1-9][\d]{0,15}$/;
  return phoneRegex.test(phone.replace(/[\s\-\(\)]/g, ''));
};

// Безопасное создание DOM элементов
export const createSafeElement = (tag: string, content: string, className?: string): HTMLElement => {
  const element = document.createElement(tag);
  element.textContent = content; // Используем textContent вместо innerHTML
  if (className) {
    element.className = className;
  }
  return element;
};

// Rate limiting для форм
const submissionTimes = new Map<string, number[]>();

export const checkRateLimit = (identifier: string, maxSubmissions: number = 3, timeWindow: number = 60000): boolean => {
  const now = Date.now();
  const times = submissionTimes.get(identifier) || [];
  
  // Удаляем старые записи
  const recentTimes = times.filter(time => now - time < timeWindow);
  
  if (recentTimes.length >= maxSubmissions) {
    return false; // Превышен лимит
  }
  
  // Добавляем новую запись
  recentTimes.push(now);
  submissionTimes.set(identifier, recentTimes);
  
  return true; // Можно отправлять
};