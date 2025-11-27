import { API } from '@/api/core';
import { logger } from './logger';

// Admin utility functions for storage and media management
// These functions require backend API endpoints to be implemented

export const makeStoragePublic = async () => {
  try {
    const { data } = await API.post('/admin/storage/make-public');
    console.log('Storage made public successfully:', data);
    return { success: true, data };
  } catch (error) {
    logger.warn('[testStoragePublic] makeStoragePublic endpoint not yet implemented');
    return { success: false, error };
  }
};

export const backfillMedia = async (chatId?: string, limit = 50) => {
  try {
    const { data } = await API.post('/admin/telegram/backfill-media', { chatId, limit });
    console.log('Media backfill completed:', data);
    return { success: true, data };
  } catch (error) {
    logger.warn('[testStoragePublic] backfillMedia endpoint not yet implemented');
    return { success: false, error };
  }
};

export const retryProxyFiles = async (chatId?: string, limit = 50) => {
  try {
    const { data } = await API.post('/admin/telegram/backfill-media', { chatId, limit, retryProxy: true });
    console.log('Proxy files retry completed:', data);
    return { success: true, data };
  } catch (error) {
    logger.warn('[testStoragePublic] retryProxyFiles endpoint not yet implemented');
    return { success: false, error };
  }
};

export const getFileStats = async () => {
  try {
    const { data } = await API.get<{
      total: number;
      stored: number;
      proxy: number;
      withoutStatus: number;
      withTelegramId: number;
    }>('/admin/messages/file-stats');
    console.log('File statistics:', data);
    return { success: true, stats: data };
  } catch (error) {
    logger.warn('[testStoragePublic] getFileStats endpoint not yet implemented');
    return { success: false, error };
  }
};
