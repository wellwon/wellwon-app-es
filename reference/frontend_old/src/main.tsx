
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// Инициализация систем оптимизации
import { cacheManager } from './utils/cacheManager'
import { performanceMonitor } from './utils/performanceMonitor'
import { logger } from './utils/logger'

// Запускаем автоматическую очистку кэша
cacheManager.startAutoCleanup();

// Логируем запуск приложения
logger.info('Application starting', { 
  component: 'Main',
  metadata: {
    userAgent: navigator.userAgent,
    timestamp: new Date().toISOString(),
    isDevelopment: import.meta.env.DEV
  }
});

// Измеряем время загрузки
const startTime = performance.now();

createRoot(document.getElementById("root")!).render(
  import.meta.env.DEV ? (
    <App />
  ) : (
    <StrictMode>
      <App />
    </StrictMode>
  )
);

// Логируем время инициализации
const initTime = performance.now() - startTime;
performanceMonitor.recordMetric('app_initialization', initTime, 'Main');
