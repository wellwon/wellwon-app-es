import React from 'react';
import { Forward } from 'lucide-react';

import type { TelegramMessageData } from '@/types/chat';

interface TelegramMessageBubbleProps {
  message: any;
  className?: string;
}

const TelegramMessageBubble: React.FC<TelegramMessageBubbleProps> = ({ 
  message, 
  className = '' 
}) => {
  const telegramData: TelegramMessageData = {
    telegram_message_id: message.telegram_message_id,
    telegram_user_id: message.telegram_user_id,
    telegram_user_data: message.telegram_user_data,
    telegram_topic_id: message.telegram_topic_id,
    telegram_forward_data: message.telegram_forward_data,
    sync_direction: message.sync_direction,
  };

  // Показываем только индикатор пересланного сообщения
  if (!telegramData.telegram_forward_data) {
    return null;
  }

  return (
    <div className={`flex items-center gap-1 text-xs text-muted-foreground ${className}`}>
      <Forward className="w-3 h-3" />
      <span>Пересланное</span>
    </div>
  );
};

export default TelegramMessageBubble;