import { toast as originalToast } from '@/hooks/use-toast';

/**
 * Utility functions for creating consistently styled toasts
 * Use these instead of calling toast() directly for better consistency
 */

export const showSuccessToast = (title: string, description?: string) => {
  return originalToast({
    title,
    description,
    variant: "success",
  });
};

export const showErrorToast = (title: string, description?: string) => {
  return originalToast({
    title,
    description,
    variant: "error",
  });
};

export const showWarningToast = (title: string, description?: string) => {
  return originalToast({
    title,
    description,
    variant: "warning",
  });
};

export const showInfoToast = (title: string, description?: string) => {
  return originalToast({
    title,
    description,
    variant: "info",
  });
};

/**
 * Toast Usage Guidelines (ОБНОВЛЕНО):
 * 
 * ✅ УНИФИЦИРОВАННЫЕ ВАРИАНТЫ:
 * - INFO: Объединен с default - для информационных сообщений
 * - SUCCESS: Для успешных операций  
 * - WARNING: Для предупреждений
 * - ERROR: Объединен с destructive - для ошибок
 * 
 * 🎨 ДИЗАЙН:
 * - Все тосты имеют серый бордер (border-gray-300/30)
 * - Иконки увеличены до h-8 w-8 и центрированы по вертикали
 * - Цвета иконок соответствуют типу сообщения
 * 
 * 📋 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:
 * 
 * SUCCESS: showSuccessToast("Данные сохранены", "Изменения успешно применены")
 * ERROR: showErrorToast("Ошибка сохранения", "Попробуйте еще раз") 
 * WARNING: showWarningToast("Внимание", "Изменения не сохранены")
 * INFO: showInfoToast("Информация", "Данные обновлены")
 * 
 * 🚫 НЕ ИСПОЛЬЗУЙТЕ БОЛЬШЕ:
 * - variant: "destructive" → используйте "error"
 * - variant: "default" → используйте "info"
 * 
 * 🛠 ПАНЕЛЬ РАЗРАБОТЧИКА:
 * Кнопки тестирования тостов теперь иконочные с соответствующими цветами
 */