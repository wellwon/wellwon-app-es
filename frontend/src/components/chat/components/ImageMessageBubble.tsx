import React, { useMemo, useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Download, Image as ImageIcon } from 'lucide-react';
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
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [naturalAspectRatio, setNaturalAspectRatio] = useState<number | null>(null);

  // Get aspect ratio from metadata or from loaded image
  const aspectRatio = useMemo(() => {
    return message.metadata?.imageDimensions?.aspectRatio || naturalAspectRatio || null;
  }, [message.metadata?.imageDimensions, naturalAspectRatio]);

  // Reset state when file_url changes
  useEffect(() => {
    setImageLoaded(false);
    setImageError(false);
    setNaturalAspectRatio(null);
  }, [message.file_url]);

  if (!message.file_url) {
    return null;
  }

  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    if (img.naturalWidth && img.naturalHeight) {
      setNaturalAspectRatio(img.naturalWidth / img.naturalHeight);
    }
    setImageLoaded(true);
  };

  const handleImageError = () => {
    setImageError(true);
  };

  // If image failed to load, show error state with download option
  if (imageError) {
    return (
      <div className="space-y-2">
        <div className="relative group flex flex-col items-center justify-center gap-2 p-4 bg-white/5 rounded-lg border border-white/10">
          <ImageIcon size={32} className="text-white/40" />
          <span className="text-sm text-white/60">Изображение недоступно</span>
          <Button
            size="sm"
            variant="secondary"
            onClick={onDownload}
            className="mt-2"
          >
            <Download size={14} className="mr-1" />
            Скачать
          </Button>
          {renderTimeAndStatus(false)}
        </div>
        {message.content && (
          <div className="text-sm pr-16">{message.content}</div>
        )}
      </div>
    );
  }

  const isPortrait = aspectRatio && aspectRatio < 1;

  return (
    <div className="space-y-1">
      <div className="relative group inline-block">
        <img
          src={message.file_url}
          alt={message.file_name || 'Изображение'}
          className="max-h-[160px] max-w-[200px] w-auto h-auto cursor-pointer hover:opacity-90 transition-opacity object-cover rounded-lg"
          onLoad={handleImageLoad}
          onError={handleImageError}
          onClick={onImageClick}
        />
        {/* Download button - visible on hover */}
        <Button
          size="sm"
          variant="secondary"
          className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity bg-black/50 hover:bg-black/70 text-white h-6 w-6 p-0"
          onClick={(e) => {
            e.stopPropagation();
            onDownload();
          }}
        >
          <Download size={12} />
        </Button>
        {needsInlineTimestamp(message) && renderTimeAndStatus(true)}
      </div>
      {message.content && (
        <div className="text-sm">{message.content}</div>
      )}
    </div>
  );
};