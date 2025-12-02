import React, { useLayoutEffect, useState, useRef } from 'react';
import { X, Image as ImageIcon, FileText, Mic, Reply } from 'lucide-react';
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
      bottom: viewportHeight - rect.top + 8
    });

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
      return message.content.length > 80
        ? message.content.substring(0, 80) + '...'
        : message.content;
    }
    if (message.message_type === 'image') {
      return message.content?.trim() || 'Фото';
    }
    if (message.message_type === 'file') {
      return message.file_name || 'Файл';
    }
    if (message.message_type === 'voice') {
      return 'Голосовое сообщение';
    }
    return message.content || 'Сообщение';
  };

  const getMessageTypeIcon = (message: Message) => {
    switch (message.message_type) {
      case 'image':
        return <ImageIcon size={14} className="text-accent-red/70" />;
      case 'file':
        return <FileText size={14} className="text-accent-blue/70" />;
      case 'voice':
        return <Mic size={14} className="text-accent-green/70" />;
      default:
        return null;
    }
  };

  const hasImageThumbnail = replyTarget.message_type === 'image' && replyTarget.file_url;

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
      className="animate-reply-panel-enter"
    >
      {/* Main container with glass effect */}
      <div className="
        flex items-stretch gap-0
        bg-[#232328]/95 backdrop-blur-md
        border border-white/10
        shadow-lg shadow-black/20
        rounded-xl
        overflow-hidden
      ">
        {/* Accent line - Telegram/WhatsApp style */}
        <div className="w-1 bg-accent-red animate-accent-line flex-shrink-0" />

        {/* Content area */}
        <div className="flex items-center gap-3 px-3 py-2.5 flex-1 min-w-0">
          {/* Reply icon with subtle background */}
          <div className="
            w-8 h-8 rounded-lg
            bg-accent-red/10
            flex items-center justify-center
            flex-shrink-0
          ">
            <Reply size={16} className="text-accent-red" />
          </div>

          {/* Text content */}
          <div className="min-w-0 flex-1 overflow-hidden">
            {/* Sender name in accent color */}
            <div className="text-sm font-semibold text-accent-red truncate mb-0.5">
              {getDisplayName(replyTarget)}
            </div>

            {/* Message preview with type icon */}
            <div className="flex items-center gap-1.5 text-sm text-white/60 truncate">
              {getMessageTypeIcon(replyTarget)}
              <span className="truncate">{getContentPreview(replyTarget)}</span>
            </div>
          </div>

          {/* Image thumbnail for image messages */}
          {hasImageThumbnail && (
            <div className="flex-shrink-0 w-10 h-10 rounded-lg overflow-hidden bg-white/5">
              <img
                src={replyTarget.file_url!}
                alt="Preview"
                className="w-full h-full object-cover"
              />
            </div>
          )}
        </div>

        {/* Cancel button */}
        <button
          onClick={onCancel}
          className="
            px-3 flex items-center justify-center
            hover:bg-white/5
            transition-colors duration-150
            group
          "
          aria-label="Отмена"
        >
          <X
            size={18}
            className="text-white/40 group-hover:text-white/70 transition-colors duration-150"
          />
        </button>
      </div>
    </div>
  );
};
