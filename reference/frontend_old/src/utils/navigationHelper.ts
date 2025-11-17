/**
 * Утилиты для безопасной навигации без принудительных перезагрузок
 */

import { logger } from './logger';

// Глобальная переменная для хранения navigate функции
declare global {
  interface Window {
    __ROUTER_NAVIGATE__?: (path: string) => void;
  }
}

/**
 * Безопасная навигация с fallback на window.location
 */
export const safeNavigate = (path: string, fallbackToReload = false) => {
  try {
    // Пробуем использовать React Router navigate
    if (window.__ROUTER_NAVIGATE__) {
      logger.info('Using React Router navigation', { path, component: 'navigationHelper' });
      window.__ROUTER_NAVIGATE__(path);
      return;
    }

    // Если нет navigate функции и разрешен fallback
    if (fallbackToReload) {
      logger.warn('Using fallback navigation with reload', { path, component: 'navigationHelper' });
      window.location.href = path;
    } else {
      logger.error('Navigation failed: no navigate function available', { path, component: 'navigationHelper' });
    }
  } catch (error) {
    logger.error('Navigation error', error, { path, component: 'navigationHelper' });
    
    if (fallbackToReload) {
      window.location.href = path;
    }
  }
};

/**
 * Регистрация navigate функции для использования в error boundaries
 */
export const registerNavigateFunction = (navigate: (path: string) => void) => {
  window.__ROUTER_NAVIGATE__ = navigate;
  logger.info('Navigate function registered', { component: 'navigationHelper' });
};

/**
 * Очистка навигационной функции
 */
export const unregisterNavigateFunction = () => {
  delete window.__ROUTER_NAVIGATE__;
  logger.info('Navigate function unregistered', { component: 'navigationHelper' });
};