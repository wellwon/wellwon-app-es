import React, { useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Download } from 'lucide-react';
import { OptimizedImage } from './OptimizedImage';
import type { Message } from '@/types/realtime-chat';

interface ImageMessageBubbleProps {
  message: Message;
  onImageClick: () => void;
  onDownload: () => void;
  renderTimeAndStatus: (overlay?: boolean) => JSX.Element;
  needsInlineTimestamp: (message: Message) => boolean;
}

export const ImageMessageBubble: React.FC<ImageMessageBubbleProps> = ({
  message,
  onImageClick,
  onDownload,
  renderTimeAndStatus,
  needsInlineTimestamp
}) => {
  // Получаем aspect ratio только из метаданных (гарантируется гидрацией)
  const aspectRatio = useMemo(() => {
    return message.metadata?.imageDimensions?.aspectRatio || null;
  }, [message.metadata?.imageDimensions]);

  if (!message.file_url) {
    return null;
  }

  // Если нет aspect ratio (не удалось загрузить), показываем текстовый скелет
  if (!aspectRatio) {
    return (
      <div className="space-y-2">
        <div className="text-sm text-white/70 pr-16">
          Загрузка изображения...
        </div>
      </div>
    );
  }

  const isPortrait = aspectRatio && aspectRatio < 1;

  return (
    <div className="space-y-2">
      <div className="relative group">
        <div className="w-full rounded-lg overflow-hidden">
          <OptimizedImage
            src={message.file_url} 
            alt={message.file_name || 'Изображение'}
            className={isPortrait 
              ? "h-[420px] sm:h-[360px] w-auto cursor-pointer hover:opacity-90 transition-opacity"
              : "w-full max-h-[360px] cursor-pointer hover:opacity-90 transition-opacity"
            }
            onClick={onImageClick}
            aspectRatio={aspectRatio}
            fit={isPortrait ? 'contain' : 'cover'}
          />
        </div>
        <Button
          size="sm"
          variant="secondary"
          className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={onDownload}
        >
          <Download size={16} />
        </Button>
        {needsInlineTimestamp(message) && renderTimeAndStatus(true)}
      </div>
      {message.content && (
        <div className="text-sm pr-16">{message.content}</div>
      )}
    </div>
  );
};