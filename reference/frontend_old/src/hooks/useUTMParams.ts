
import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { secureSetItem, secureGetItem } from '@/utils/security';

export interface UTMParams {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
}

const UTM_STORAGE_KEY = 'wellwon_utm_params';

export const useUTMParams = () => {
  const [utmParams, setUTMParams] = useState<UTMParams>({});
  const location = useLocation();

  // Извлекаем UTM параметры из URL
  const extractUTMFromURL = (search: string): UTMParams => {
    const urlParams = new URLSearchParams(search);
    const params: UTMParams = {};

    const utmKeys: (keyof UTMParams)[] = [
      'utm_source',
      'utm_medium', 
      'utm_campaign',
      'utm_content',
      'utm_term'
    ];

    utmKeys.forEach(key => {
      const value = urlParams.get(key);
      if (value) {
        params[key] = value;
      }
    });

    return params;
  };

  // Безопасное сохранение в localStorage
  const saveUTMParams = (params: UTMParams) => {
    try {
      secureSetItem(UTM_STORAGE_KEY, JSON.stringify(params));
    } catch {
      // Игнорируем ошибки сохранения
    }
  };

  // Безопасная загрузка из localStorage
  const loadSavedUTMParams = (): UTMParams => {
    try {
      const saved = secureGetItem(UTM_STORAGE_KEY, 7 * 24 * 60 * 60 * 1000); // 7 дней
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  };

  // Добавляем UTM параметры к URL
  const appendUTMToURL = (url: string): string => {
    if (Object.keys(utmParams).length === 0) return url;

    try {
      const urlObj = new URL(url, window.location.origin);
      
      Object.entries(utmParams).forEach(([key, value]) => {
        if (value && !urlObj.searchParams.has(key)) {
          urlObj.searchParams.set(key, value);
        }
      });

      return urlObj.toString();
    } catch {
      return url;
    }
  };

  // Очищаем UTM параметры
  const clearUTMParams = () => {
    setUTMParams({});
    try {
      localStorage.removeItem(UTM_STORAGE_KEY);
    } catch {
      // Игнорируем ошибки
    }
  };

  // Единственный useEffect для всей логики
  useEffect(() => {
    // Проверяем URL на наличие новых UTM параметров
    const urlUTMParams = extractUTMFromURL(location.search);
    
    if (Object.keys(urlUTMParams).length > 0) {
      // Если есть новые UTM параметры в URL, сохраняем их
      setUTMParams(prev => {
        // Проверяем, изменились ли параметры, чтобы избежать лишних обновлений
        const hasChanged = JSON.stringify(prev) !== JSON.stringify(urlUTMParams);
        if (hasChanged) {
          saveUTMParams(urlUTMParams);
          return urlUTMParams;
        }
        return prev;
      });
    } else {
      // Если UTM в URL нет, загружаем сохраненные только при первой загрузке
      setUTMParams(prev => {
        if (Object.keys(prev).length === 0) {
          const savedParams = loadSavedUTMParams();
          return savedParams;
        }
        return prev;
      });
    }
  }, [location.search]);

  return {
    utmParams,
    appendUTMToURL,
    clearUTMParams,
    hasUTMParams: Object.keys(utmParams).length > 0
  };
};
