// =============================================================================
// File: ImageUploadService.tsx
// Description: Image Upload Service for chat message templates
// TODO: Implement file upload via backend API when MinIO/S3 is set up
// =============================================================================

import { logger } from '@/utils/logger';

export const uploadImageToStorage = async (file: File): Promise<string> => {
  // TODO: Implement file upload via backend API
  // This should POST to /api/files/upload with multipart form data
  // For now, we throw an error indicating file uploads are not yet available
  logger.warn('[ImageUploadService] uploadImageToStorage not yet implemented - waiting for MinIO/S3 integration');
  throw new Error('File upload not yet available - backend storage integration pending');
};

export const deleteImageFromStorage = async (url: string): Promise<void> => {
  // TODO: Implement file deletion via backend API
  // This should DELETE to /api/files/{fileId}
  logger.warn('[ImageUploadService] deleteImageFromStorage not yet implemented - waiting for MinIO/S3 integration');
  // Don't throw error for deletion - just log warning
};
