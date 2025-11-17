
/**
 * Система кэширования для оптимизации производительности
 */

import { logger } from './logger';

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  expiry: number;
}

interface CacheOptions {
  ttl?: number; // Time to live в миллисекундах
  maxSize?: number; // Максимальный размер кэша
}

class CacheManager {
  private cache = new Map<string, CacheEntry<any>>();
  private defaultTTL = 5 * 60 * 1000; // 5 минут по умолчанию
  private maxSize = 100; // Максимум 100 записей

  set<T>(key: string, data: T, options: CacheOptions = {}): void {
    const ttl = options.ttl || this.defaultTTL;
    const maxSize = options.maxSize || this.maxSize;

    // Очищаем кэш если он переполнен
    if (this.cache.size >= maxSize) {
      this.cleanup();
    }

    const entry: CacheEntry<T> = {
      data,
      timestamp: Date.now(),
      expiry: Date.now() + ttl
    };

    this.cache.set(key, entry);
    
    logger.debug(`Cache set: ${key}`, { 
      component: 'CacheManager',
      metadata: { ttl, size: this.cache.size }
    });
  }

  get<T>(key: string): T | null {
    const entry = this.cache.get(key);
    
    if (!entry) {
      logger.debug(`Cache miss: ${key}`, { component: 'CacheManager' });
      return null;
    }

    // Проверяем срок действия
    if (Date.now() > entry.expiry) {
      this.cache.delete(key);
      logger.debug(`Cache expired: ${key}`, { component: 'CacheManager' });
      return null;
    }

    logger.debug(`Cache hit: ${key}`, { component: 'CacheManager' });
    return entry.data as T;
  }

  has(key: string): boolean {
    const entry = this.cache.get(key);
    if (!entry) return false;
    
    if (Date.now() > entry.expiry) {
      this.cache.delete(key);
      return false;
    }
    
    return true;
  }

  delete(key: string): boolean {
    const deleted = this.cache.delete(key);
    if (deleted) {
      logger.debug(`Cache deleted: ${key}`, { component: 'CacheManager' });
    }
    return deleted;
  }

  clear(): void {
    const size = this.cache.size;
    this.cache.clear();
    logger.info(`Cache cleared, removed ${size} entries`, { component: 'CacheManager' });
  }

  // Очистка устаревших записей
  cleanup(): void {
    const now = Date.now();
    let removed = 0;
    
    for (const [key, entry] of this.cache.entries()) {
      if (now > entry.expiry) {
        this.cache.delete(key);
        removed++;
      }
    }
    
    logger.info(`Cache cleanup completed, removed ${removed} entries`, { 
      component: 'CacheManager',
      metadata: { remaining: this.cache.size }
    });
  }

  // Получение статистики кэша
  getStats() {
    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      keys: Array.from(this.cache.keys())
    };
  }

  // Автоматическая очистка по расписанию
  startAutoCleanup(intervalMs: number = 5 * 60 * 1000): void {
    setInterval(() => {
      this.cleanup();
    }, intervalMs);
    
    logger.info(`Auto cleanup started, interval: ${intervalMs}ms`, { component: 'CacheManager' });
  }
}

// Singleton instance
export const cacheManager = new CacheManager();

// Утилитарные функции
export const cache = {
  set: <T>(key: string, data: T, options?: CacheOptions) => cacheManager.set(key, data, options),
  get: <T>(key: string) => cacheManager.get<T>(key),
  has: (key: string) => cacheManager.has(key),
  delete: (key: string) => cacheManager.delete(key),
  clear: () => cacheManager.clear(),
  cleanup: () => cacheManager.cleanup(),
  stats: () => cacheManager.getStats()
};

// Хук для кэширования в React компонентах
export const useCache = <T>(key: string, fetcher: () => Promise<T>, options?: CacheOptions) => {
  const getCachedData = async (): Promise<T> => {
    // Проверяем кэш
    const cached = cache.get<T>(key);
    if (cached !== null) {
      return cached;
    }

    // Загружаем данные
    const data = await fetcher();
    cache.set(key, data, options);
    return data;
  };

  return {
    getCachedData,
    invalidate: () => cache.delete(key),
    exists: () => cache.has(key)
  };
};
