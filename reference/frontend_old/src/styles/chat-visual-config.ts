/**
 * Фиксированные визуальные настройки для чат-системы
 * НЕ ИЗМЕНЯТЬ БЕЗ РАЗРЕШЕНИЯ ПОЛЬЗОВАТЕЛЯ
 */

export const CHAT_VISUAL_CONFIG = {
  // Поле ввода
  INPUT_FIELD: {
    borderRadius: 'rounded-[32px]', // ЗАФИКСИРОВАНО - 32px скругление
    background: 'bg-light-gray',
    border: 'border border-white/20',
    padding: 'px-4 py-3',
    shadow: 'shadow-lg'
  },

  // Кнопка отправки
  SEND_BUTTON: {
    borderRadius: 'rounded-full',
    background: 'bg-accent-red',
    hoverBackground: 'hover:bg-accent-red/90',
    textColor: 'text-white'
  },

  // Контейнер чата
  CHAT_CONTAINER: {
    background: 'bg-dark-gray',
    textColor: 'text-white'
  },

  // Разделитель дат
  DATE_SEPARATOR: {
    textColor: 'text-white/60',
    background: 'bg-white/10',
    borderRadius: 'rounded-full'
  },

  // Цветовая схема (темная тема)
  THEME: {
    primary: 'text-white',
    secondary: 'text-white/80',
    tertiary: 'text-white/60',
    borders: 'border-white/10',
    overlays: 'bg-white/10'
  }
} as const;

// Типы для TypeScript
export type ChatVisualConfig = typeof CHAT_VISUAL_CONFIG;