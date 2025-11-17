/**
 * Кэш размеров изображений для предотвращения layout shift
 */

import { supabase } from '@/integrations/supabase/client';
import { logger } from './logger';
import { getImageDimensionsFromUrl, type ImageDimensions } from './imageUtils';

interface CachedDimensions extends ImageDimensions {
  cachedAt: number;
}

class ImageDimensionsCache {
  private cache = new Map<string, CachedDimensions>();
  private readonly CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 часа
  private pendingRequests = new Map<string, Promise<ImageDimensions | null>>();

  /**
   * Получить размеры изображения из кэша или загрузить их
   */
  async getDimensions(url: string): Promise<ImageDimensions | null> {
    try {
      // Проверяем кэш
      const cached = this.cache.get(url);
      if (cached && this.isCacheValid(cached)) {
        return {
          width: cached.width,
          height: cached.height,
          aspectRatio: cached.aspectRatio
        };
      }

      // Проверяем, есть ли уже запрос на загрузку
      const existingRequest = this.pendingRequests.get(url);
      if (existingRequest) {
        return await existingRequest;
      }

      // Создаём новый запрос
      const request = this.loadDimensions(url);
      this.pendingRequests.set(url, request);

      try {
        const dimensions = await request;
        this.pendingRequests.delete(url);
        return dimensions;
      } catch (error) {
        this.pendingRequests.delete(url);
        throw error;
      }
    } catch (error) {
      logger.warn('Failed to get image dimensions', { error, url });
      return null;
    }
  }

  /**
   * Загрузить размеры изображения
   */
  private async loadDimensions(url: string): Promise<ImageDimensions | null> {
    try {
      const dimensions = await getImageDimensionsFromUrl(url);
      
      // Кэшируем результат
      this.cache.set(url, {
        ...dimensions,
        cachedAt: Date.now()
      });

      return dimensions;
    } catch (error) {
      logger.warn('Failed to load image dimensions from URL', { error, url });
      return null;
    }
  }

  /**
   * Проверить, валидны ли данные в кэше
   */
  private isCacheValid(cached: CachedDimensions): boolean {
    return Date.now() - cached.cachedAt < this.CACHE_DURATION;
  }

  /**
   * Обновить размеры изображения в сообщении
   */
  async updateMessageDimensions(messageId: string, dimensions: ImageDimensions): Promise<void> {
    try {
      // Сначала получаем текущие метаданные
      const { data: currentMessage, error: fetchError } = await supabase
        .from('messages')
        .select('metadata')
        .eq('id', messageId)
        .single();

      if (fetchError) {
        logger.error('Failed to fetch current message metadata', fetchError, { messageId });
        return;
      }

      // Объединяем существующие метаданные с новыми размерами
      const updatedMetadata = {
        ...((currentMessage?.metadata as any) || {}),
        imageDimensions: {
          width: dimensions.width,
          height: dimensions.height,
          aspectRatio: dimensions.aspectRatio
        }
      };

      const { error } = await supabase
        .from('messages')
        .update({ metadata: updatedMetadata })
        .eq('id', messageId);

      if (error) {
        logger.error('Failed to update message dimensions', error, { messageId });
      } else {
        logger.debug('Updated message dimensions', { messageId, dimensions });
      }
    } catch (error) {
      logger.error('Error updating message dimensions', error, { messageId });
    }
  }

  /**
   * Очистить устаревший кэш
   */
  clearExpiredCache(): void {
    const now = Date.now();
    for (const [url, cached] of this.cache.entries()) {
      if (!this.isCacheValid(cached)) {
        this.cache.delete(url);
      }
    }
  }

  /**
   * Предварительно загрузить размеры для массива сообщений
   */
  async preloadMessagesDimensions(messages: Array<{ id: string; file_url?: string; message_type: string; metadata?: any }>): Promise<void> {
    const imageMessages = messages.filter(msg => 
      msg.message_type === 'image' && 
      msg.file_url && 
      !msg.metadata?.imageDimensions
    );

    if (imageMessages.length === 0) return;

    // Загружаем размеры параллельно с лимитом 6 одновременно
    await this.processWithConcurrencyLimit(imageMessages, 6, async (msg) => {
      try {
        const dimensions = await this.getDimensions(msg.file_url!);
        if (dimensions) {
          // Обновляем БД в фоне (для будущих заходов)
          this.updateMessageDimensions(msg.id, dimensions).catch(() => {
            // Игнорируем ошибки фоновой записи
          });
        }
      } catch (error) {
        logger.warn('Failed to preload dimensions', { error, messageId: msg.id, url: msg.file_url });
      }
    });
  }

  /**
   * Гидрирует массив сообщений с размерами изображений (с лимитом параллелизма)
   */
  async hydrateMessagesWithLimiter<T extends { id: string; file_url?: string; metadata?: any }>(
    messages: T[]
  ): Promise<T[]> {
    const results = await this.processWithConcurrencyLimit(messages, 6, async (msg) => {
      try {
        const dimensions = await this.getDimensions(msg.file_url!);
        if (dimensions) {
          // Обновляем БД в фоне
          this.updateMessageDimensions(msg.id, dimensions).catch(() => {});
          
          return {
            ...msg,
            metadata: {
              ...msg.metadata,
              imageDimensions: dimensions
            }
          };
        }
        return msg;
      } catch {
        return msg;
      }
    });
    
    return results;
  }

  /**
   * Обрабатывает массив элементов с ограничением параллелизма
   */
  private async processWithConcurrencyLimit<T, R>(
    items: T[],
    limit: number,
    processor: (item: T) => Promise<R>
  ): Promise<R[]> {
    const results: R[] = [];
    
    for (let i = 0; i < items.length; i += limit) {
      const batch = items.slice(i, i + limit);
      const batchResults = await Promise.all(batch.map(processor));
      results.push(...batchResults);
    }
    
    return results;
  }
}

export const imageDimensionsCache = new ImageDimensionsCache();

// Очищаем кэш каждый час
setInterval(() => {
  imageDimensionsCache.clearExpiredCache();
}, 60 * 60 * 1000);