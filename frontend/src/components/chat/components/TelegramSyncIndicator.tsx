import React from 'react';
import { MessageCircle, CheckCircle, AlertCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface TelegramSyncIndicatorProps {
  isActive: boolean;
  lastSyncStatus?: 'success' | 'error' | 'pending';
  lastSyncTime?: string;
  className?: string;
}

const TelegramSyncIndicator: React.FC<TelegramSyncIndicatorProps> = ({
  isActive,
  lastSyncStatus = 'success',
  lastSyncTime,
  className = ''
}) => {

  if (!isActive) {
    return null;
  }

  const getStatusIcon = () => {
    switch (lastSyncStatus) {
      case 'success':
        return <CheckCircle className="w-3 h-3 text-green-400" />;
      case 'error':
        return <AlertCircle className="w-3 h-3 text-red-400" />;
      case 'pending':
        return <div className="w-3 h-3 border border-yellow-400 border-t-transparent rounded-full animate-spin" />;
      default:
        return <MessageCircle className="w-3 h-3 text-blue-400" />;
    }
  };

  const getTooltipText = () => {
    let statusText = '';
    switch (lastSyncStatus) {
      case 'success':
        statusText = 'Синхронизация успешна';
        break;
      case 'error':
        statusText = 'Ошибка синхронизации';
        break;
      case 'pending':
        statusText = 'Синхронизация в процессе';
        break;
      default:
        statusText = 'Синхронизация активна';
    }

    if (lastSyncTime) {
      const syncTime = new Date(lastSyncTime).toLocaleString('ru');
      return `${statusText} (Последняя синхронизация: ${syncTime})`;
    }

    return statusText;
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={`inline-flex items-center ${className}`}>
            <Badge variant="outline" className="text-xs bg-blue-500/10 border-blue-500/30">
              {getStatusIcon()}
              <span className="ml-1">Telegram</span>
            </Badge>
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <p>{getTooltipText()}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default TelegramSyncIndicator;