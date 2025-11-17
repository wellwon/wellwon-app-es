/**
 * Утилиты для работы с изображениями
 */

export interface ImageDimensions {
  width: number;
  height: number;
  aspectRatio: number;
}

/**
 * Получить размеры изображения из File объекта
 */
export function getImageDimensions(file: File): Promise<ImageDimensions> {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith('image/')) {
      reject(new Error('File is not an image'));
      return;
    }

    const img = new Image();
    const url = URL.createObjectURL(file);

    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve({
        width: img.naturalWidth,
        height: img.naturalHeight,
        aspectRatio: img.naturalWidth / img.naturalHeight
      });
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Failed to load image'));
    };

    img.src = url;
  });
}

/**
 * Получить размеры изображения из URL
 */
export function getImageDimensionsFromUrl(url: string): Promise<ImageDimensions> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    
    img.onload = () => {
      resolve({
        width: img.naturalWidth,
        height: img.naturalHeight,
        aspectRatio: img.naturalWidth / img.naturalHeight
      });
    };

    img.onerror = () => {
      reject(new Error('Failed to load image from URL'));
    };

    // Добавляем crossOrigin для работы с Supabase Storage
    img.crossOrigin = 'anonymous';
    img.src = url;
  });
}

/**
 * Вычислить оптимальные размеры для отображения с учетом максимальной ширины
 */
export function calculateDisplayDimensions(
  originalDimensions: ImageDimensions,
  maxWidth: number = 320 // max-w-xs в Tailwind = 320px
): { width: number; height: number } {
  const { width, height, aspectRatio } = originalDimensions;
  
  if (width <= maxWidth) {
    return { width, height };
  }
  
  const displayWidth = maxWidth;
  const displayHeight = Math.round(maxWidth / aspectRatio);
  
  return { width: displayWidth, height: displayHeight };
}