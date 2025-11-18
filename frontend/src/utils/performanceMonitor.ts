
/**
 * Мониторинг производительности приложения
 */

import { logger } from './logger';

interface PerformanceMetric {
  name: string;
  value: number;
  timestamp: number;
  component?: string;
}

class PerformanceMonitor {
  private metrics: Map<string, PerformanceMetric> = new Map();
  private observers: PerformanceObserver[] = [];

  constructor() {
    this.initializeObservers();
  }

  private initializeObservers() {
    // Мониторинг Web Vitals
    if ('PerformanceObserver' in window) {
      // LCP (Largest Contentful Paint)
      const lcpObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const lastEntry = entries[entries.length - 1] as PerformanceEntry & { startTime: number };
        this.recordMetric('LCP', lastEntry.startTime);
      });
      
      try {
        lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });
        this.observers.push(lcpObserver);
      } catch (e) {
        logger.debug('LCP observer not supported', { component: 'PerformanceMonitor' });
      }

      // FID (First Input Delay)
      const fidObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        entries.forEach((entry: any) => {
          this.recordMetric('FID', entry.processingStart - entry.startTime);
        });
      });
      
      try {
        fidObserver.observe({ entryTypes: ['first-input'] });
        this.observers.push(fidObserver);
      } catch (e) {
        logger.debug('FID observer not supported', { component: 'PerformanceMonitor' });
      }
    }
  }

  recordMetric(name: string, value: number, component?: string) {
    const metric: PerformanceMetric = {
      name,
      value,
      timestamp: Date.now(),
      component
    };

    this.metrics.set(name, metric);
    logger.performance(name, value, 'ms', { component: component || 'PerformanceMonitor' });
  }

  // Измерение времени выполнения функции
  measureFunction<T>(name: string, fn: () => T, component?: string): T {
    const start = performance.now();
    const result = fn();
    const duration = performance.now() - start;
    this.recordMetric(name, duration, component);
    return result;
  }

  // Измерение времени выполнения асинхронной функции
  async measureAsync<T>(name: string, fn: () => Promise<T>, component?: string): Promise<T> {
    const start = performance.now();
    const result = await fn();
    const duration = performance.now() - start;
    this.recordMetric(name, duration, component);
    return result;
  }

  // Получение всех метрик
  getMetrics(): PerformanceMetric[] {
    return Array.from(this.metrics.values());
  }

  // Получение конкретной метрики
  getMetric(name: string): PerformanceMetric | undefined {
    return this.metrics.get(name);
  }

  // Очистка метрик
  clear() {
    this.metrics.clear();
  }

  // Уничтожение наблюдателей
  destroy() {
    this.observers.forEach(observer => observer.disconnect());
    this.observers = [];
  }
}

// Создаем singleton instance
export const performanceMonitor = new PerformanceMonitor();

// Хук для React компонентов
export const usePerformanceMonitor = () => {
  const measureRender = (componentName: string) => {
    return {
      start: () => {
        const startTime = performance.now();
        return () => {
          const endTime = performance.now();
          performanceMonitor.recordMetric(`${componentName}_render`, endTime - startTime, componentName);
        };
      }
    };
  };

  return {
    measureRender,
    recordMetric: performanceMonitor.recordMetric.bind(performanceMonitor),
    getMetrics: performanceMonitor.getMetrics.bind(performanceMonitor)
  };
};
