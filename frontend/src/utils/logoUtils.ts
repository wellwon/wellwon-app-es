// Logo utility functions for image validation and processing

export interface ImageValidationResult {
  valid: boolean;
  error?: string;
}

/**
 * Validates an image file for logo upload
 */
export function validateImage(file: File): ImageValidationResult {
  // Check file type
  const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'];
  if (!validTypes.includes(file.type)) {
    return {
      valid: false,
      error: 'Invalid file type. Please upload a JPEG, PNG, GIF, WebP, or SVG image.'
    };
  }

  // Check file size (max 5MB)
  const maxSize = 5 * 1024 * 1024;
  if (file.size > maxSize) {
    return {
      valid: false,
      error: 'File is too large. Maximum size is 5MB.'
    };
  }

  return { valid: true };
}

/**
 * Processes an image file (resize/optimize if needed) and returns a File/Blob
 */
export async function processImage(file: File): Promise<Blob> {
  // For now, just return the file as-is
  // In the future, can add resizing/compression logic here
  return file;
}

/**
 * Gets an image from the clipboard
 */
export async function getImageFromClipboard(): Promise<File | null> {
  try {
    const clipboardItems = await navigator.clipboard.read();

    for (const item of clipboardItems) {
      // Check for image types
      const imageType = item.types.find(type => type.startsWith('image/'));
      if (imageType) {
        const blob = await item.getType(imageType);
        // Convert blob to File
        const file = new File([blob], 'pasted-image.png', { type: imageType });
        return file;
      }
    }

    return null;
  } catch (error) {
    console.error('Failed to read from clipboard:', error);
    return null;
  }
}
