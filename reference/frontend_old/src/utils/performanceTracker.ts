/**
 * Утилиты для отслеживания производительности и перезагрузок
 */

import { logger } from './logger';

interface PageLoadMetrics {
  timestamp: number;
  url: string;
  loadType: 'initial' | 'navigation' | 'reload';
  userAgent: string;
}

class PerformanceTracker {
  private pageLoads: PageLoadMetrics[] = [];
  private navigationStartTime: number = 0;

  constructor() {
    this.initializeTracking();
  }

  private initializeTracking() {
    // Отслеживаем загрузки страниц
    if (typeof window !== 'undefined') {
      this.navigationStartTime = performance.now();
      
      // Отслеживаем тип загрузки
      const loadType = this.getLoadType();
      
      this.recordPageLoad({
        timestamp: Date.now(),
        url: window.location.href,
        loadType,
        userAgent: navigator.userAgent.substring(0, 100) // Ограничиваем размер
      });

      // Отслеживаем изменения URL
      this.trackNavigationChanges();
    }
  }

  private getLoadType(): 'initial' | 'navigation' | 'reload' {
    if (typeof window === 'undefined') return 'initial';
    
    const navigation = (performance as any).navigation;
    if (navigation) {
      switch (navigation.type) {
        case 1: return 'reload';
        case 2: return 'navigation';
        default: return 'initial';
      }
    }
    
    // Fallback для старых браузеров - проверяем через document.referrer
    if (document.referrer === window.location.href) {
      return 'reload';
    }
    
    return 'initial';
  }

  private trackNavigationChanges() {
    // Отслеживаем изменения через history API
    const originalPushState = history.pushState;
    const originalReplaceState = history.replaceState;

    history.pushState = (...args) => {
      this.recordPageLoad({
        timestamp: Date.now(),
        url: args[2] as string || window.location.href,
        loadType: 'navigation',
        userAgent: navigator.userAgent.substring(0, 100)
      });
      return originalPushState.apply(history, args);
    };

    history.replaceState = (...args) => {
      this.recordPageLoad({
        timestamp: Date.now(),
        url: args[2] as string || window.location.href,
        loadType: 'navigation',
        userAgent: navigator.userAgent.substring(0, 100)
      });
      return originalReplaceState.apply(history, args);
    };

    // Отслеживаем события браузера
    window.addEventListener('popstate', () => {
      this.recordPageLoad({
        timestamp: Date.now(),
        url: window.location.href,
        loadType: 'navigation',
        userAgent: navigator.userAgent.substring(0, 100)
      });
    });
  }

  private recordPageLoad(metrics: PageLoadMetrics) {
    this.pageLoads.push(metrics);
    
    // Ограничиваем размер массива
    if (this.pageLoads.length > 50) {
      this.pageLoads = this.pageLoads.slice(-30);
    }

    logger.info('Page load tracked', {
      component: 'PerformanceTracker',
      metadata: {
        loadType: metrics.loadType,
        url: metrics.url,
        timestamp: metrics.timestamp
      }
    });

    // Проверяем на подозрительные перезагрузки
    this.detectSuspiciousReloads();
  }

  private detectSuspiciousReloads() {
    const recentLoads = this.pageLoads.filter(
      load => Date.now() - load.timestamp < 60000 // Последние 60 секунд
    );

    const reloads = recentLoads.filter(load => load.loadType === 'reload');
    
    if (reloads.length >= 3) {
      logger.warn('Suspicious reload pattern detected', {
        component: 'PerformanceTracker',
        metadata: {
          reloadCount: reloads.length,
          timeWindow: '60s',
          urls: reloads.map(r => r.url)
        }
      });
    }
  }

  getMetrics() {
    return {
      pageLoads: this.pageLoads,
      totalLoads: this.pageLoads.length,
      reloadCount: this.pageLoads.filter(l => l.loadType === 'reload').length,
      navigationCount: this.pageLoads.filter(l => l.loadType === 'navigation').length
    };
  }

  recordCustomMetric(name: string, value: number, metadata?: Record<string, any>) {
    logger.info(`Performance metric: ${name}`, {
      component: 'PerformanceTracker',
      metadata: {
        metricName: name,
        value,
        timestamp: Date.now(),
        ...metadata
      }
    });
  }
}

export const performanceTracker = new PerformanceTracker();