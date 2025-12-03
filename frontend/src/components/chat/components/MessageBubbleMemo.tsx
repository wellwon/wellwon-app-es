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
  // Custom comparison function for optimal re-renders
  // IMPORTANT: Must check callback existence to ensure action buttons render
  // IMPORTANT: Must compare telegram_message_id for delivery status (double gray checkmark)
  // IMPORTANT: Must compare telegram_read_at for read status (double blue checkmark)

  const prevMsg = prevProps.message;
  const nextMsg = nextProps.message;

  // Fast shallow comparison - avoid JSON.stringify
  return (
    // Identity
    prevMsg.id === nextMsg.id &&
    // Content
    prevMsg.content === nextMsg.content &&
    prevMsg.is_edited === nextMsg.is_edited &&
    prevMsg.is_deleted === nextMsg.is_deleted &&
    // File/media (for file URL updates)
    prevMsg.file_url === nextMsg.file_url &&
    prevMsg.file_type === nextMsg.file_type &&
    prevMsg.voice_duration === nextMsg.voice_duration &&
    // Read status - compare length instead of full serialization
    (prevMsg.read_by?.length ?? 0) === (nextMsg.read_by?.length ?? 0) &&
    // Telegram sync status
    prevMsg.telegram_message_id === nextMsg.telegram_message_id &&
    prevMsg.telegram_read_at === nextMsg.telegram_read_at &&
    // Props
    prevProps.isOwn === nextProps.isOwn &&
    prevProps.isSending === nextProps.isSending &&
    prevProps.className === nextProps.className &&
    // Check if callback availability changed (don't compare function refs, just existence)
    !!prevProps.onReply === !!nextProps.onReply &&
    !!prevProps.onDelete === !!nextProps.onDelete
  );
});

MessageBubbleMemo.displayName = 'MessageBubbleMemo';