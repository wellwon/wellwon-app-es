import React from 'react';
import { MessageBubble } from './MessageBubble';
import type { Message } from '@/types/realtime-chat';

interface MessageBubbleMemoProps {
  message: Message;
  isOwn: boolean;
  isSending?: boolean;
  currentUser?: {
    id: string;
    first_name?: string;
    last_name?: string;
    avatar_url?: string;
  };
  onReply?: (message: Message) => void;
  className?: string;
}

// Мемоизированный компонент MessageBubble для оптимизации производительности
export const MessageBubbleMemo = React.memo<MessageBubbleMemoProps>(({ 
  message, 
  isOwn, 
  isSending,
  currentUser,
  onReply, 
  className 
}) => {
  return (
    <MessageBubble
      message={message}
      isOwn={isOwn}
      isSending={isSending}
      currentUser={currentUser}
      onReply={onReply}
      className={className}
    />
  );
}, (prevProps, nextProps) => {
  // Кастомная функция сравнения для оптимизации ре-рендеров
  return (
    prevProps.message.id === nextProps.message.id &&
    prevProps.message.content === nextProps.message.content &&
    prevProps.message.is_edited === nextProps.message.is_edited &&
    prevProps.isOwn === nextProps.isOwn &&
    prevProps.isSending === nextProps.isSending &&
    JSON.stringify(prevProps.message.read_by) === JSON.stringify(nextProps.message.read_by) &&
    prevProps.className === nextProps.className
  );
});