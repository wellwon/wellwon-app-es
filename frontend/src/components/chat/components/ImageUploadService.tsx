import { supabase } from '@/integrations/supabase/client';

export const uploadImageToStorage = async (file: File): Promise<string> => {
  try {
    // Generate unique filename
    const fileExt = file.name.split('.').pop();
    const fileName = `${Date.now()}-${Math.random().toString(36).substring(2)}.${fileExt}`;
    
    // Upload to Supabase Storage
    const { data, error } = await supabase.storage
      .from('message-templates')
      .upload(fileName, file, {
        cacheControl: '3600',
        upsert: false
      });

    if (error) {
      throw error;
    }

    // Get public URL
    const { data: { publicUrl } } = supabase.storage
      .from('message-templates')
      .getPublicUrl(data.path);

    return publicUrl;
  } catch (error) {
    
    throw new Error('Не удалось загрузить изображение');
  }
};

export const deleteImageFromStorage = async (url: string): Promise<void> => {
  try {
    // Extract filename from URL
    const urlParts = url.split('/');
    const fileName = urlParts[urlParts.length - 1];
    
    const { error } = await supabase.storage
      .from('message-templates')
      .remove([fileName]);

    if (error) {
      throw error;
    }
  } catch (error) {
    
    // Don't throw error for deletion failures
  }
};