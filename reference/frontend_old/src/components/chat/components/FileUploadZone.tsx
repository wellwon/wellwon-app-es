import React, { useCallback, useState } from 'react';
import { Upload, X, ImageIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FileUploadZoneProps {
  onFileSelect: (file: File) => void;
  onRemove: () => void;
  currentImageUrl?: string;
  className?: string;
}

export const FileUploadZone: React.FC<FileUploadZoneProps> = ({
  onFileSelect,
  onRemove,
  currentImageUrl,
  className
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    
    const files = Array.from(e.dataTransfer.files);
    const imageFile = files.find(file => file.type.startsWith('image/'));
    
    if (imageFile) {
      handleFileUpload(imageFile);
    }
  }, []);

  const handleFileUpload = useCallback((file: File) => {
    if (!file.type.startsWith('image/')) return;
    
    setIsLoading(true);
    const reader = new FileReader();
    
    reader.onload = () => {
      onFileSelect(file);
      setIsLoading(false);
    };
    
    reader.readAsDataURL(file);
  }, [onFileSelect]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileUpload(file);
    }
  }, [handleFileUpload]);

  return (
    <div className={cn("space-y-2", className)}>
      {currentImageUrl ? (
        <div className="relative">
          <div className="relative w-full h-32 rounded-lg overflow-hidden bg-dark-gray/50 border border-white/10">
            <img
              src={currentImageUrl}
              alt="Preview"
              className="w-full h-full object-cover"
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                target.nextElementSibling?.classList.remove('hidden');
              }}
            />
            <div className="hidden absolute inset-0 flex items-center justify-center text-gray-500">
              <ImageIcon size={32} />
            </div>
          </div>
          <button
            onClick={onRemove}
            className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 hover:bg-red-600 rounded-full flex items-center justify-center transition-colors"
          >
            <X size={12} className="text-white" />
          </button>
        </div>
      ) : (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={cn(
            "relative border-2 border-dashed rounded-lg text-center transition-all w-full h-full min-h-[6rem] flex items-center justify-center",
            isDragOver
              ? "border-accent-red bg-accent-red/10"
              : "border-white/20 hover:border-white/30",
            isLoading && "pointer-events-none opacity-50"
          )}
        >
          <input
            type="file"
            accept="image/*"
            onChange={handleInputChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            disabled={isLoading}
          />
          
          <div className="flex flex-col items-center gap-1 p-2">
            <Upload size={16} className="text-gray-400" />
            <div className="text-xs text-gray-300 text-center leading-tight">
              {isLoading ? 'Загрузка...' : 'Добавить фото'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};