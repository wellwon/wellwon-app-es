import React, { useLayoutEffect, useState, useRef } from 'react';
import { X, Reply } from 'lucide-react';
import type { Message } from '@/types/realtime-chat';

interface ReplyPreviewOverlayProps {
  open: boolean;
  anchorRef: React.RefObject<HTMLElement>;
  replyTarget: Message;
  onCancel: () => void;
  onHeightChange?: (height: number) => void;
}

export const ReplyPreviewOverlay: React.FC<ReplyPreviewOverlayProps> = ({
  open,
  anchorRef,
  replyTarget,
  onCancel,
  onHeightChange
}) => {
  const [position, setPosition] = useState<{
    bottom: number;
    left: number;
    width: number;
  }>({ bottom: 0, left: 0, width: 320 });
  
  const overlayRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!open || !anchorRef.current) return;

    const anchor = anchorRef.current;
    const rect = anchor.getBoundingClientRect();
    const viewportHeight = window.innerHeight;

    setPosition({
      left: rect.left,
      width: rect.width,
      bottom: viewportHeight - rect.top + 8 // 8px отступ над полем ввода
    });

    // Измеряем высоту overlay после рендера
    if (overlayRef.current && onHeightChange) {
      const height = overlayRef.current.clientHeight;
      onHeightChange(height);
    }
  }, [open, anchorRef, onHeightChange]);

  if (!open || !anchorRef.current) {
    return null;
  }

  const getDisplayName = (message: Message): string => {
    if (message.sender_profile) {
      return `${message.sender_profile.first_name || ''} ${message.sender_profile.last_name || ''}`.trim() || 'Пользователь';
    }
    if (message.telegram_user_data) {
      const tgData = message.telegram_user_data;
      return `${tgData.first_name || ''} ${tgData.last_name || ''}`.trim() || tgData.username || 'Пользователь';
    }
    return 'Пользователь';
  };

  const getContentPreview = (message: Message): string => {
    if (message.message_type === 'text' && message.content) {
      return message.content.length > 100 
        ? message.content.substring(0, 100) + '...'
        : message.content;
    }
    if (message.message_type === 'image') {
      return 'Изображение';
    }
    if (message.message_type === 'file') {
      return message.file_name || 'Файл';
    }
    if (message.message_type === 'voice') {
      return 'Голосовое сообщение';
    }
    return 'Сообщение';
  };

  const overlayStyle: React.CSSProperties = {
    position: 'fixed',
    left: position.left,
    width: position.width,
    bottom: position.bottom,
    zIndex: 50,
  };

  return (
    <div 
      ref={overlayRef}
      style={overlayStyle}
      className="flex items-center gap-3 p-3 bg-[#2b2b30] border border-white/10 shadow-xl rounded-lg"
    >
      {/* Reply icon */}
      <Reply className="w-3.5 h-3.5 text-white/70 flex-shrink-0" />
      
      {/* Content */}
      <div className="min-w-0 flex-1 overflow-hidden">
        <div className="text-xs font-medium text-white/90 mb-1 truncate">
          {getDisplayName(replyTarget)}
        </div>
        <div className="text-xs text-white/60 truncate">
          {getContentPreview(replyTarget)}
        </div>
      </div>
      
      {/* Cancel button */}
      <button
        onClick={onCancel}
        className="p-1 hover:bg-white/10 rounded transition-colors flex-shrink-0"
        aria-label="Отмена"
      >
        <X className="w-4 h-4 text-white/60" />
      </button>
    </div>
  );
};