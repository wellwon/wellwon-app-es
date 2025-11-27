import React, { useState, useEffect } from 'react';
import { Reply, Image as ImageIcon, File, Mic, Loader2 } from 'lucide-react';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import * as chatApi from '@/api/chat';
import type { Message } from '@/types/realtime-chat';

interface ReplyMessageBubbleProps {
  replyMessage: Message;
  className?: string;
  onReplyClick?: (messageId: string) => void;
}

export const ReplyMessageBubble: React.FC<ReplyMessageBubbleProps> = ({ 
  replyMessage,
  className = '',
  onReplyClick
}) => {
  const { messages } = useRealtimeChatContext();
  
  // Helper function to check if message has complete data
  const isComplete = (message: Message): boolean => {
    return Boolean(
      message.message_type !== 'text' || 
      message.content || 
      message.file_name
    );
  };

  // Initialize resolvedMessage with replyMessage if it's complete
  const [resolvedMessage, setResolvedMessage] = useState<Message | null>(
    isComplete(replyMessage) ? replyMessage : null
  );
  const [isLoading, setIsLoading] = useState(false);
  const [hasAttemptedHydration, setHasAttemptedHydration] = useState(
    isComplete(replyMessage)
  );

  useEffect(() => {
    const hydrateMessage = async () => {
      // Если сообщение уже полное, обновляем состояние и выходим
      if (isComplete(replyMessage)) {
        setResolvedMessage(replyMessage);
        setHasAttemptedHydration(true);
        return;
      }

      // Ищем полное сообщение в контексте
      const contextMessage = messages.find(m => m.id === replyMessage.id);
      if (contextMessage && isComplete(contextMessage)) {
        setResolvedMessage(contextMessage);
        setHasAttemptedHydration(true);
        return;
      }

      // Если не нашли в контексте, запрашиваем из API
      try {
        setIsLoading(true);
        // Fetch single message via chat API - messages are fetched via getMessages
        // For single message lookup, we use the messages API with the specific chat
        const apiMessages = await chatApi.getMessages(replyMessage.chat_id, {
          limit: 1,
          before_id: replyMessage.id,
          after_id: replyMessage.id
        });

        // Find the specific message
        const data = apiMessages.find(m => m.id === replyMessage.id);

        if (data) {
          setResolvedMessage({
            ...replyMessage,
            content: data.content,
            message_type: (data.message_type as Message['message_type']) || 'text',
            file_name: data.file_name || null,
            file_url: data.file_url || null,
            voice_duration: data.voice_duration || null,
            sender_profile: data.sender_name ? {
              first_name: data.sender_name.split(' ')[0] || '',
              last_name: data.sender_name.split(' ').slice(1).join(' ') || '',
              avatar_url: data.sender_avatar_url || null,
              type: null
            } : null,
            telegram_user_data: null // API doesn't return telegram_user_data yet
          });
        } else {
          // Сообщение действительно удалено
          setResolvedMessage(null);
        }
      } catch (error) {
        console.error('Failed to hydrate reply message:', error);
        setResolvedMessage(null);
      } finally {
        setIsLoading(false);
        setHasAttemptedHydration(true);
      }
    };

    hydrateMessage();
  }, [replyMessage.id, messages, replyMessage]);

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
      return message.content.length > 50 
        ? message.content.substring(0, 50) + '...'
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

  const getTypeIcon = (message: Message) => {
    switch (message.message_type) {
      case 'image':
        return <ImageIcon className="w-3 h-3 text-primary/60" />;
      case 'file':
        return <File className="w-3 h-3 text-primary/60" />;
      case 'voice':
        return <Mic className="w-3 h-3 text-primary/60" />;
      default:
        return null;
    }
  };

  const handleClick = () => {
    if (onReplyClick) {
      onReplyClick(replyMessage.id);
    }
  };

  // Определяем что показывать - только если сообщение загружено
  const displayMessage = resolvedMessage || replyMessage;
  const displayName = resolvedMessage ? getDisplayName(resolvedMessage) : '';
  const contentPreview = resolvedMessage ? getContentPreview(resolvedMessage) : (isLoading ? '' : (!resolvedMessage ? 'Удалено' : ''));

  return (
    <div 
      className={`
        flex items-center gap-3 p-3 w-full h-[56px]
        bg-white/5 backdrop-blur-sm
        border border-white/10 rounded-xl
        ${onReplyClick ? 'cursor-pointer hover:bg-white/10 hover:border-white/20' : ''}
        ${className}
      `}
      onClick={handleClick}
    >
      {/* Reply icon */}
      <Reply className="w-3.5 h-3.5 text-primary/70 flex-shrink-0" />
      
      {/* Content - показываем только если есть данные */}
      {resolvedMessage && (
        <div className="min-w-0 flex-1 overflow-hidden">
          <div className="text-xs font-medium text-primary/90 mb-1 truncate">
            {displayName}
          </div>
          <div className="flex items-center gap-2">
            {getTypeIcon(displayMessage)}
            <div className="text-xs text-muted-foreground/80 truncate">
              {contentPreview}
            </div>
          </div>
        </div>
      )}
      
      {/* Loading spinner */}
      {isLoading && (
        <div className="min-w-0 flex-1 overflow-hidden">
          <div className="flex items-center gap-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-primary/70" />
          </div>
        </div>
      )}
      
      {/* Показываем "Удалено" только если попытались загрузить и не нашли */}
      {!isLoading && !resolvedMessage && hasAttemptedHydration && (
        <div className="min-w-0 flex-1 overflow-hidden">
          <div className="text-xs text-muted-foreground/80 truncate">
            Удалено
          </div>
        </div>
      )}
    </div>
  );
};