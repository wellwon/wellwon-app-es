import React from 'react';
import { MessageCircle, Users, Hash } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface TelegramIndicatorProps {
  chat: any;
  showDetails?: boolean;
  className?: string;
}

// Helper to check if chat is a Telegram chat
function isTelegramChat(chat: any): boolean {
  return !!chat?.telegram_chat_id || !!chat?.telegram_supergroup_id;
}

// Format chat info for display
function formatChatInfo(chat: any): { displayName: string; subtitle: string | null } {
  const displayName = chat?.telegram_title || chat?.name || 'Telegram Chat';
  const subtitle = chat?.telegram_username ? `@${chat.telegram_username}` : null;
  return { displayName, subtitle };
}

const TelegramIndicator: React.FC<TelegramIndicatorProps> = ({
  chat,
  showDetails = false,
  className = ''
}) => {
  if (!isTelegramChat(chat)) {
    return null;
  }

  const { displayName, subtitle } = formatChatInfo(chat);

  const TelegramIcon = () => (
    <MessageCircle 
      className="w-4 h-4 text-blue-500" 
      fill="currentColor"
    />
  );

  if (!showDetails) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className={`inline-flex ${className}`}>
              <TelegramIcon />
            </div>
          </TooltipTrigger>
          <TooltipContent>
            <p>Синхронизация с Telegram включена</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <TelegramIcon />
      
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">
            {displayName}
          </span>
          
          <Badge variant="outline" className="text-xs">
            <Users className="w-3 h-3 mr-1" />
            Супергруппа
          </Badge>
        </div>
        
        {subtitle && (
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Hash className="w-3 h-3" />
            <span>{subtitle}</span>
          </div>
        )}
        
        {chat.telegram_supergroup_id && (
          <div className="text-xs text-muted-foreground">
            ID: {chat.telegram_supergroup_id}
          </div>
        )}
      </div>
    </div>
  );
};

export default TelegramIndicator;