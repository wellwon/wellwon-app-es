
import { UTMParams } from '@/hooks/useUTMParams';

// Добавляет UTM параметры как скрытые поля в FormData
export const addUTMToFormData = (formData: FormData, utmParams: UTMParams): FormData => {
  Object.entries(utmParams).forEach(([key, value]) => {
    if (value) {
      formData.append(key, value);
    }
  });
  return formData;
};

// Создает объект с UTM параметрами для API запросов
export const getUTMForAPI = (utmParams: UTMParams) => {
  const utmData: Record<string, string> = {};
  
  Object.entries(utmParams).forEach(([key, value]) => {
    if (value) {
      utmData[key] = value;
    }
  });
  
  return utmData;
};

// Создает строку с UTM параметрами для добавления к URL
export const utmParamsToString = (utmParams: UTMParams): string => {
  const params = new URLSearchParams();
  
  Object.entries(utmParams).forEach(([key, value]) => {
    if (value) {
      params.append(key, value);
    }
  });
  
  const paramString = params.toString();
  return paramString ? `?${paramString}` : '';
};
