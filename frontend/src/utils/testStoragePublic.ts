
import { supabase } from '@/integrations/supabase/client';

// Тестовая функция для вызова edge function и публикации bucket
export const makeStoragePublic = async () => {
  try {
    const { data, error } = await supabase.functions.invoke('storage-make-public');
    
    if (error) {
      console.error('Error calling storage-make-public:', error);
      return { success: false, error };
    }
    
    console.log('Storage made public successfully:', data);
    return { success: true, data };
  } catch (error) {
    console.error('Unexpected error calling storage function:', error);
    return { success: false, error };
  }
};

// Функция для запуска backfill медиа-файлов
export const backfillMedia = async (chatId?: string, limit = 50) => {
  try {
    const { data, error } = await supabase.functions.invoke('telegram-backfill-media', {
      body: { chatId, limit }
    });
    
    if (error) {
      console.error('Error calling telegram-backfill-media:', error);
      return { success: false, error };
    }
    
    console.log('Media backfill completed:', data);
    return { success: true, data };
  } catch (error) {
    console.error('Unexpected error calling backfill function:', error);
    return { success: false, error };
  }
};

// Функция для повторной обработки proxy-файлов в storage
export const retryProxyFiles = async (chatId?: string, limit = 50) => {
  try {
    const { data, error } = await supabase.functions.invoke('telegram-backfill-media', {
      body: { chatId, limit, retryProxy: true }
    });
    
    if (error) {
      console.error('Error calling retry proxy files:', error);
      return { success: false, error };
    }
    
    console.log('Proxy files retry completed:', data);
    return { success: true, data };
  } catch (error) {
    console.error('Unexpected error calling retry proxy function:', error);
    return { success: false, error };
  }
};

// Функция для получения статистики файлов
export const getFileStats = async () => {
  try {
    const { data: allFiles } = await supabase
      .from('messages')
      .select('file_status, file_url, telegram_file_id')
      .not('file_url', 'is', null);
    
    const stats = {
      total: allFiles?.length || 0,
      stored: allFiles?.filter(f => f.file_status === 'stored').length || 0,
      proxy: allFiles?.filter(f => f.file_status === 'proxy').length || 0,
      withoutStatus: allFiles?.filter(f => !f.file_status).length || 0,
      withTelegramId: allFiles?.filter(f => f.telegram_file_id).length || 0
    };
    
    console.log('File statistics:', stats);
    return { success: true, stats };
  } catch (error) {
    console.error('Error getting file stats:', error);
    return { success: false, error };
  }
};

// Для вызова из консоли браузера:
// import { makeStoragePublic, backfillMedia, retryProxyFiles, getFileStats } from '@/utils/testStoragePublic';
// makeStoragePublic().then(console.log);
// backfillMedia('chat-id').then(console.log);
// retryProxyFiles().then(console.log);
// getFileStats().then(console.log);
