import { supabase } from '@/integrations/supabase/client';
import { logger } from '@/utils/logger';

export class CompanyLogoService {
  private static readonly MAX_FILE_SIZE = 4 * 1024 * 1024; // 4MB
  private static readonly MAX_DIMENSION = 1024;
  private static readonly WEBP_QUALITY = 0.85;
  private static readonly BUCKET_NAME = 'company-logos';

  static validateImage(file: File): { valid: boolean; error?: string } {
    if (!file.type.startsWith('image/')) {
      return { valid: false, error: 'Файл должен быть изображением' };
    }

    if (file.size > this.MAX_FILE_SIZE) {
      return { valid: false, error: `Размер файла не должен превышать ${this.MAX_FILE_SIZE / 1024 / 1024}MB` };
    }

    return { valid: true };
  }

  static async blobToWebP(blob: Blob, maxSize = this.MAX_DIMENSION, quality = this.WEBP_QUALITY): Promise<Blob> {
    return new Promise((resolve, reject) => {
      const img = new Image();
      const objectUrl = URL.createObjectURL(blob);
      
      img.onload = () => {
        URL.revokeObjectURL(objectUrl);
        
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        if (!ctx) {
          reject(new Error('Не удалось создать canvas context'));
          return;
        }

        // Calculate new dimensions
        let { width, height } = img;
        if (width > maxSize || height > maxSize) {
          if (width > height) {
            height = Math.round((height * maxSize) / width);
            width = maxSize;
          } else {
            width = Math.round((width * maxSize) / height);
            height = maxSize;
          }
        }

        canvas.width = width;
        canvas.height = height;
        
        // Draw and convert to WebP
        ctx.drawImage(img, 0, 0, width, height);
        canvas.toBlob(
          (webpBlob) => {
            if (webpBlob) {
              resolve(webpBlob);
            } else {
              // Fallback to PNG if WebP fails
              canvas.toBlob(
                (pngBlob) => {
                  if (pngBlob) {
                    resolve(pngBlob);
                  } else {
                    reject(new Error('Не удалось конвертировать изображение'));
                  }
                },
                'image/png',
                0.9
              );
            }
          },
          'image/webp',
          quality
        );
      };
      
      img.onerror = () => {
        URL.revokeObjectURL(objectUrl);
        reject(new Error('Не удалось загрузить изображение'));
      };
      
      img.src = objectUrl;
    });
  }

  static async uploadImage(imageBlob: Blob): Promise<string> {
    try {
      // Detect content type
      const contentType = imageBlob.type || 'image/webp';
      const extension = contentType === 'image/png' ? 'png' : 'webp';
      
      const fileName = `${Date.now()}-${Math.random().toString(36).substring(2)}.${extension}`;
      const filePath = fileName;

      const { data, error } = await supabase.storage
        .from(this.BUCKET_NAME)
        .upload(filePath, imageBlob, {
          contentType,
          upsert: false
        });

      if (error) {
        logger.error('Ошибка загрузки логотипа в Storage', error, { 
          component: 'CompanyLogoService',
          fileName 
        });
        throw new Error(`Ошибка загрузки: ${error.message}`);
      }

      // Get public URL
      const { data: publicUrlData } = supabase.storage
        .from(this.BUCKET_NAME)
        .getPublicUrl(data.path);

      return publicUrlData.publicUrl;
    } catch (error) {
      logger.error('Ошибка в uploadImage', error, { component: 'CompanyLogoService' });
      throw error;
    }
  }

  static async deleteByUrl(url: string): Promise<void> {
    try {
      // Extract file path from URL
      const urlParts = url.split(`/${this.BUCKET_NAME}/`);
      if (urlParts.length !== 2) {
        logger.warn('Невозможно извлечь путь файла из URL', { url, component: 'CompanyLogoService' });
        return;
      }

      const filePath = urlParts[1];
      
      const { error } = await supabase.storage
        .from(this.BUCKET_NAME)
        .remove([filePath]);

      if (error) {
        logger.error('Ошибка удаления логотипа из Storage', error, { 
          component: 'CompanyLogoService',
          filePath 
        });
        throw new Error(`Ошибка удаления: ${error.message}`);
      }
    } catch (error) {
      logger.error('Ошибка в deleteByUrl', error, { component: 'CompanyLogoService' });
      throw error;
    }
  }

  static async getImageFromClipboard(): Promise<Blob | null> {
    try {
      if (!navigator.clipboard || !navigator.clipboard.read) {
        return null;
      }

      const clipboardItems = await navigator.clipboard.read();
      
      for (const item of clipboardItems) {
        for (const type of item.types) {
          if (type.startsWith('image/')) {
            return await item.getType(type);
          }
        }
      }
      
      return null;
    } catch (error) {
      logger.error('Ошибка чтения изображения из буфера обмена', error, { 
        component: 'CompanyLogoService' 
      });
      return null;
    }
  }

  static async processAndUpload(file: File | Blob): Promise<string> {
    try {
      // Convert to WebP (with PNG fallback)
      const processedBlob = await this.blobToWebP(file);
      
      // Upload to storage
      const publicUrl = await this.uploadImage(processedBlob);
      
      return publicUrl;
    } catch (error) {
      logger.error('Ошибка обработки и загрузки изображения', error, { 
        component: 'CompanyLogoService' 
      });
      throw error;
    }
  }
}