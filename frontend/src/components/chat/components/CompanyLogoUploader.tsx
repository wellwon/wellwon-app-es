import React, { useCallback, useState, useRef } from 'react';
import { Image, ClipboardPaste, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { validateImage, processImage, getImageFromClipboard } from '@/utils/logoUtils';
import { useToast } from '@/hooks/use-toast';


interface CompanyLogoUploaderProps {
  value?: string;
  onChange: (url: string | undefined) => void;
  onRemove?: () => void;
  disabled?: boolean;
  className?: string;
  size?: 'sm' | 'lg';
  fill?: boolean;
}

export const CompanyLogoUploader: React.FC<CompanyLogoUploaderProps> = ({
  value,
  onChange,
  onRemove,
  disabled = false,
  className,
  size = 'sm',
  fill = false
}) => {
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const sizeClasses = {
    sm: 'w-7 h-7',
    lg: 'w-14 h-14'
  };

  const iconSize = size === 'lg' ? 32 : 20;
  const spinnerSize = size === 'lg' ? 'w-6 h-6' : 'w-4 h-4';
  const removeButtonClasses = size === 'lg' ? 'w-6 h-6 -top-1 -right-1' : 'w-5 h-5 -top-1 -right-1';
  const removeIconSize = size === 'lg' ? 16 : 12;
  const pasteButtonSize = size === 'lg' ? 'w-12 h-12' : 'w-8 h-8';
  const pasteIconSize = size === 'lg' ? 18 : 14;

  const handleFileUpload = useCallback(async (file: File) => {
    if (disabled) return;

    const validation = validateImage(file);
    if (!validation.valid) {
      toast({
        title: "Неверный файл",
        description: validation.error,
        variant: "error"
      });
      return;
    }

    try {
      setIsLoading(true);
      // Process image (resize + convert to WebP)
      const processedFile = await processImage(file);
      // Create object URL for preview (actual upload handled by parent via onChange)
      const objectUrl = URL.createObjectURL(processedFile);
      onChange(objectUrl);

      toast({
        title: "Логотип загружен",
        variant: "success"
      });
    } catch (error) {
      toast({
        title: "Ошибка загрузки",
        description: error instanceof Error ? error.message : 'Неизвестная ошибка',
        variant: "error"
      });
    } finally {
      setIsLoading(false);
    }
  }, [disabled, onChange, toast]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) {
      setIsDragOver(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    
    if (disabled) return;

    const files = Array.from(e.dataTransfer.files);
    const imageFile = files.find(file => file.type.startsWith('image/'));
    
    if (imageFile) {
      handleFileUpload(imageFile);
    }
  }, [disabled, handleFileUpload]);

  const handleClick = useCallback(() => {
    if (!disabled && fileInputRef.current) {
      fileInputRef.current.click();
    }
  }, [disabled]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileUpload(file);
    }
    e.target.value = '';
  }, [handleFileUpload]);

  const handlePasteFromClipboard = useCallback(async () => {
    if (disabled) return;

    try {
      setIsLoading(true);
      const file = await getImageFromClipboard();

      if (!file) {
        toast({
          title: "Нет изображения в буфере",
          description: 'В буфере обмена нет изображения',
          variant: "warning"
        });
        return;
      }

      // Process and create preview
      const processedFile = await processImage(file);
      const objectUrl = URL.createObjectURL(processedFile);
      onChange(objectUrl);

      toast({
        title: "Логотип загружен",
        variant: "success"
      });
    } catch (error) {
      toast({
        title: "Ошибка вставки",
        description: 'Не удалось вставить изображение из буфера обмена',
        variant: "error"
      });
    } finally {
      setIsLoading(false);
    }
  }, [disabled, onChange, toast]);

  const handleRemove = useCallback(() => {
    if (disabled || !value) return;

    // Revoke object URL if it's a blob URL
    if (value.startsWith('blob:')) {
      URL.revokeObjectURL(value);
    }

    onChange(undefined);
    onRemove?.();

    toast({
      title: "Логотип удален",
      variant: "success"
    });
  }, [disabled, value, onChange, onRemove, toast]);

  return (
    <div className={cn(
      fill ? "relative w-full h-full" : "flex items-center gap-2", 
      className
    )}>
      {/* Logo Square */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        className={cn(
          "relative rounded-md border border-white/20 bg-black/20 backdrop-blur-sm cursor-pointer transition-all overflow-hidden group",
          fill ? "absolute inset-0 m-auto h-full aspect-square" : sizeClasses[size],
          isDragOver && "border-accent bg-accent/10",
          disabled && "opacity-50 cursor-not-allowed",
          isLoading && "pointer-events-none"
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileSelect}
          className="hidden"
          disabled={disabled}
        />

        {value ? (
          <>
            <div className="absolute inset-0 m-auto w-full h-full">
              <img
                src={value}
                alt="Company logo"
                className="w-full h-full object-cover rounded-md"
              />
            </div>
            {!disabled && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleRemove();
                }}
                className={cn(
                  "absolute top-2 right-2 rounded-md border border-white/20 bg-black/20 backdrop-blur-sm flex items-center justify-center text-white/60 hover:text-white hover:border-white/30 opacity-0 group-hover:opacity-100 transition-all",
                  pasteButtonSize
                )}
                title="Удалить"
              >
                <X size={pasteIconSize} />
              </button>
            )}
          </>
        ) : (
          <div className="flex items-center justify-center w-full h-full text-white/60">
            {isLoading ? (
              <div className={cn("border-2 border-white/30 border-t-white rounded-full animate-spin", spinnerSize)} />
            ) : (
              <Image size={iconSize} />
            )}
          </div>
        )}
        
        {fill && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              handlePasteFromClipboard();
            }}
            disabled={disabled || isLoading}
            className={cn(
              "absolute bottom-2 right-2 rounded-md border border-white/20 bg-black/20 backdrop-blur-sm flex items-center justify-center text-white/60 hover:text-white hover:border-white/30 transition-all",
              pasteButtonSize,
              disabled && "opacity-50 cursor-not-allowed"
            )}
            title="Вставить из буфера"
          >
            <ClipboardPaste size={pasteIconSize} />
          </button>
        )}
      </div>

      {!fill && (
        <button
          onClick={handlePasteFromClipboard}
          disabled={disabled || isLoading}
          className={cn(
            "rounded-md border border-white/20 bg-black/20 backdrop-blur-sm flex items-center justify-center text-white/60 hover:text-white hover:border-white/30 transition-all",
            pasteButtonSize,
            disabled && "opacity-50 cursor-not-allowed"
          )}
          title="Вставить из буфера"
        >
          <ClipboardPaste size={pasteIconSize} />
        </button>
      )}
    </div>
  );
};
