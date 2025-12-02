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
  onDelete?: (messageId: string) => void;
  className?: string;
}

// Мемоизированный компонент MessageBubble для оптимизации производительности
export const MessageBubbleMemo = React.memo<MessageBubbleMemoProps>(({
  message,
  isOwn,
  isSending,
  currentUser,
  onReply,
  onDelete,
  className
}) => {
  return (
    <MessageBubble
      message={message}
      isOwn={isOwn}
      isSending={isSending}
      currentUser={currentUser}
      onReply={onReply}
      onDelete={onDelete}
      className={className}
    />
  );
}, (prevProps, nextProps) => {
  // Кастомная функция сравнения для оптимизации ре-рендеров
  // IMPORTANT: Must check callback existence to ensure action buttons render
  // IMPORTANT: Must compare telegram_message_id for delivery status (double gray checkmark)
  // IMPORTANT: Must compare telegram_read_at for read status (double blue checkmark)
  return (
    prevProps.message.id === nextProps.message.id &&
    prevProps.message.content === nextProps.message.content &&
    prevProps.message.is_edited === nextProps.message.is_edited &&
    prevProps.isOwn === nextProps.isOwn &&
    prevProps.isSending === nextProps.isSending &&
    JSON.stringify(prevProps.message.read_by) === JSON.stringify(nextProps.message.read_by) &&
    prevProps.message.telegram_message_id === nextProps.message.telegram_message_id &&
    prevProps.message.telegram_read_at === nextProps.message.telegram_read_at &&
    prevProps.className === nextProps.className &&
    // Check if callback availability changed (don't compare function refs, just existence)
    !!prevProps.onReply === !!nextProps.onReply &&
    !!prevProps.onDelete === !!nextProps.onDelete
  );
});

MessageBubbleMemo.displayName = 'MessageBubbleMemo';