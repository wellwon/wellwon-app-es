/**
 * Cache for image dimensions to prevent layout shift
 */

import { API } from '@/api/core';
import { logger } from './logger';
import { getImageDimensionsFromUrl, type ImageDimensions } from './imageUtils';

interface CachedDimensions extends ImageDimensions {
  cachedAt: number;
}

class ImageDimensionsCache {
  private cache = new Map<string, CachedDimensions>();
  private readonly CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours
  private pendingRequests = new Map<string, Promise<ImageDimensions | null>>();

  /**
   * Get image dimensions from cache or load them
   */
  async getDimensions(url: string): Promise<ImageDimensions | null> {
    try {
      // Check cache
      const cached = this.cache.get(url);
      if (cached && this.isCacheValid(cached)) {
        return {
          width: cached.width,
          height: cached.height,
          aspectRatio: cached.aspectRatio
        };
      }

      // Check if there's already a pending request
      const existingRequest = this.pendingRequests.get(url);
      if (existingRequest) {
        return await existingRequest;
      }

      // Create new request
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
   * Load image dimensions
   */
  private async loadDimensions(url: string): Promise<ImageDimensions | null> {
    try {
      const dimensions = await getImageDimensionsFromUrl(url);

      // Cache result
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
   * Check if cached data is valid
   */
  private isCacheValid(cached: CachedDimensions): boolean {
    return Date.now() - cached.cachedAt < this.CACHE_DURATION;
  }

  /**
   * Update image dimensions in message metadata
   */
  async updateMessageDimensions(messageId: string, dimensions: ImageDimensions): Promise<void> {
    try {
      // Update message metadata via API
      await API.patch(`/messages/${messageId}/metadata`, {
        imageDimensions: {
          width: dimensions.width,
          height: dimensions.height,
          aspectRatio: dimensions.aspectRatio
        }
      });
      logger.debug('Updated message dimensions', { messageId, dimensions });
    } catch (error) {
      // API endpoint may not be implemented yet - log and continue
      logger.debug('Failed to update message dimensions (API may not be implemented)', { messageId });
    }
  }

  /**
   * Clear expired cache
   */
  clearExpiredCache(): void {
    for (const [url, cached] of this.cache.entries()) {
      if (!this.isCacheValid(cached)) {
        this.cache.delete(url);
      }
    }
  }

  /**
   * Preload dimensions for array of messages
   */
  async preloadMessagesDimensions(messages: Array<{ id: string; file_url?: string; message_type: string; metadata?: any }>): Promise<void> {
    const imageMessages = messages.filter(msg =>
      msg.message_type === 'image' &&
      msg.file_url &&
      !msg.metadata?.imageDimensions
    );

    if (imageMessages.length === 0) return;

    // Load dimensions in parallel with limit of 6 concurrent
    await this.processWithConcurrencyLimit(imageMessages, 6, async (msg) => {
      try {
        const dimensions = await this.getDimensions(msg.file_url!);
        if (dimensions) {
          // Update DB in background (for future visits)
          this.updateMessageDimensions(msg.id, dimensions).catch(() => {
            // Ignore background write errors
          });
        }
      } catch (error) {
        logger.warn('Failed to preload dimensions', { error, messageId: msg.id, url: msg.file_url });
      }
    });
  }

  /**
   * Hydrate messages array with image dimensions (with concurrency limit)
   */
  async hydrateMessagesWithLimiter<T extends { id: string; file_url?: string; metadata?: any }>(
    messages: T[]
  ): Promise<T[]> {
    const results = await this.processWithConcurrencyLimit(messages, 6, async (msg) => {
      try {
        const dimensions = await this.getDimensions(msg.file_url!);
        if (dimensions) {
          // Update DB in background
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
   * Process array of items with concurrency limit
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

// Clear cache every hour
setInterval(() => {
  imageDimensionsCache.clearExpiredCache();
}, 60 * 60 * 1000);
