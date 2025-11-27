/**
 * Logo utility functions
 * Pure functions extracted from CompanyLogoService
 */

const MAX_FILE_SIZE = 4 * 1024 * 1024; // 4MB
const MAX_DIMENSION = 1024;
const WEBP_QUALITY = 0.85;

/**
 * Validate image file
 */
export function validateImage(file: File): { valid: boolean; error?: string } {
  if (!file.type.startsWith('image/')) {
    return { valid: false, error: 'File must be an image' };
  }

  if (file.size > MAX_FILE_SIZE) {
    return { valid: false, error: `File size must not exceed ${MAX_FILE_SIZE / 1024 / 1024}MB` };
  }

  return { valid: true };
}

/**
 * Convert image blob to WebP format with resizing
 */
export async function blobToWebP(
  blob: Blob,
  maxSize: number = MAX_DIMENSION,
  quality: number = WEBP_QUALITY
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const objectUrl = URL.createObjectURL(blob);

    img.onload = () => {
      URL.revokeObjectURL(objectUrl);

      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');

      if (!ctx) {
        reject(new Error('Could not create canvas context'));
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
                  reject(new Error('Could not convert image'));
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
      reject(new Error('Could not load image'));
    };

    img.src = objectUrl;
  });
}

/**
 * Process image file (resize + convert to WebP)
 */
export async function processImage(file: File): Promise<File> {
  const processedBlob = await blobToWebP(file);

  return new File(
    [processedBlob],
    file.name.replace(/\.[^/.]+$/, '.webp'),
    { type: processedBlob.type }
  );
}

/**
 * Get image from clipboard
 */
export async function getImageFromClipboard(): Promise<File | null> {
  try {
    if (!navigator.clipboard || !navigator.clipboard.read) {
      return null;
    }

    const clipboardItems = await navigator.clipboard.read();

    for (const item of clipboardItems) {
      for (const type of item.types) {
        if (type.startsWith('image/')) {
          const blob = await item.getType(type);
          return new File([blob], 'clipboard-image.png', { type });
        }
      }
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Get initials from name (for fallback avatar)
 */
export function getInitials(name: string): string {
  if (!name) return '?';
  const words = name.trim().split(/\s+/);
  if (words.length === 1) {
    return words[0].substring(0, 2).toUpperCase();
  }
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

/**
 * Generate data URL with initials (for fallback avatar)
 */
export function generateInitialsDataUrl(name: string, size: number = 64): string {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');

  if (!ctx) return '';

  // Background
  const hue = name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0) % 360;
  ctx.fillStyle = `hsl(${hue}, 60%, 60%)`;
  ctx.fillRect(0, 0, size, size);

  // Text
  ctx.fillStyle = 'white';
  ctx.font = `bold ${size * 0.4}px sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(getInitials(name), size / 2, size / 2);

  return canvas.toDataURL('image/png');
}

/**
 * Resolve logo URL (add base URL if needed)
 */
export function resolveLogoUrl(logo: string | null, baseUrl?: string): string {
  if (!logo) return '';
  if (logo.startsWith('http://') || logo.startsWith('https://') || logo.startsWith('data:')) {
    return logo;
  }
  // Relative URL - prepend base
  return `${baseUrl || ''}${logo}`;
}
