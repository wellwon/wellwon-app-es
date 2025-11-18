
import { UTMParams } from '@/hooks/useUTMParams';
import { logger } from './logger';

// Конфигурация Telegram бота
const TELEGRAM_BOT_USERNAME = 'wellwon-app'; // Исправлено на правильное имя бота

export interface TelegramLinkParams {
  utmParams: UTMParams;
  pageSource: string;
  customMessage?: string;
}

// Безопасное кодирование UTF-8 строки в base64
const safeBase64Encode = (str: string): string => {
  try {
    // Кодируем UTF-8 строку в base64 через encodeURIComponent
    return btoa(encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, (match, p1) => {
      return String.fromCharCode(parseInt(p1, 16));
    }));
  } catch (error) {
    logger.error('Failed to encode string to base64', error, { component: 'telegramUtils' });
    // Fallback - просто используем timestamp как уникальный параметр
    return btoa(Date.now().toString());
  }
};

// Генерация параметра start для Telegram бота
export const generateStartParameter = ({ utmParams, pageSource, customMessage }: TelegramLinkParams): string => {
  const data = {
    page: pageSource,
    utm: utmParams,
    ...(customMessage && { msg: customMessage })
  };
  
  // Безопасно кодируем данные в base64
  const encoded = safeBase64Encode(JSON.stringify(data));
  return encoded.replace(/[+/=]/g, ''); // Убираем специальные символы для URL
};

// Генерация ссылки на Telegram бота с предзаполненным сообщением (основной способ)
export const generateTelegramBotLink = (params: TelegramLinkParams): string => {
  const { utmParams, pageSource, customMessage } = params;
  
  // Создаем предзаполненное сообщение с UTM данными
  let message = customMessage || `Здравствуйте! Я пришёл со страницы "${pageSource}". Интересует финансирование торговых операций.`;
  
  // Добавляем UTM данные в сообщение если они есть
  if (Object.keys(utmParams).length > 0) {
    const utmInfo = Object.entries(utmParams)
      .filter(([_, value]) => value)
      .map(([key, value]) => `${key}: ${value}`)
      .join(', ');
    
    if (utmInfo) {
      message += `\n\nДанные перехода: ${utmInfo}`;
    }
  }
  
  const encodedMessage = encodeURIComponent(message);
  const link = `https://t.me/${TELEGRAM_BOT_USERNAME}?text=${encodedMessage}`;
  
  // Debug logs удалены для production
  
  return link;
};

// Альтернативная ссылка через start параметр (дополнительный способ)
export const generateTelegramStartLink = (params: TelegramLinkParams): string => {
  const startParam = generateStartParameter(params);
  return `https://t.me/${TELEGRAM_BOT_USERNAME}?start=${startParam}`;
};

// Безопасное декодирование base64
const safeBase64Decode = (str: string): string => {
  try {
    const decoded = atob(str);
    return decodeURIComponent(decoded.split('').map(c => {
      return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
  } catch (error) {
    logger.error('Failed to decode base64 string', error, { component: 'telegramUtils' });
    return '';
  }
};

// Декодирование start параметра (для использования в боте)
export const decodeStartParameter = (startParam: string): TelegramLinkParams | null => {
  try {
    const decoded = safeBase64Decode(startParam);
    return JSON.parse(decoded);
  } catch (error) {
    logger.error('Failed to decode start parameter', error, { component: 'telegramUtils' });
    return null;
  }
};
