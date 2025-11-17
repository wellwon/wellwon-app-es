import React from 'react';
import { cn } from '@/lib/utils';
import { Check, Clock, AlertCircle, Wifi, WifiOff } from 'lucide-react';

interface SyncIndicatorProps {
  status?: 'syncing' | 'synced' | 'error' | 'offline';
  className?: string;
  size?: 'sm' | 'md';
  showText?: boolean;
}

/**
 * SyncIndicator - Тонкий индикатор синхронизации без блокирующего лоадера
 */
export const SyncIndicator: React.FC<SyncIndicatorProps> = ({
  status = 'synced',
  className,
  size = 'sm',
  showText = false
}) => {
  const sizeClasses = {
    sm: 'h-3 w-3',
    md: 'h-4 w-4'
  };

  const textClasses = {
    sm: 'text-xs',
    md: 'text-sm'
  };

  const renderIcon = () => {
    switch (status) {
      case 'syncing':
        return (
          <div className={cn(
            "border-2 border-accent-red border-t-transparent rounded-full animate-spin",
            sizeClasses[size]
          )} />
        );
      case 'synced':
        return (
          <Check className={cn(
            "text-green-500",
            sizeClasses[size]
          )} />
        );
      case 'error':
        return (
          <AlertCircle className={cn(
            "text-red-500",
            sizeClasses[size]
          )} />
        );
      case 'offline':
        return (
          <WifiOff className={cn(
            "text-gray-500",
            sizeClasses[size]
          )} />
        );
      default:
        return null;
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'syncing':
        return 'Синхронизация...';
      case 'synced':
        return 'Синхронизировано';
      case 'error':
        return 'Ошибка синхронизации';
      case 'offline':
        return 'Нет связи';
      default:
        return '';
    }
  };

  if (status === 'synced' && !showText) {
    return null; // Не показываем успешный статус без текста
  }

  return (
    <div className={cn(
      "inline-flex items-center gap-1 opacity-70 transition-opacity duration-300",
      className
    )}>
      {renderIcon()}
      {showText && (
        <span className={cn(
          "text-gray-400",
          textClasses[size]
        )}>
          {getStatusText()}
        </span>
      )}
    </div>
  );
};

/**
 * InlineSyncIndicator - Встроенный индикатор для UI элементов
 */
export const InlineSyncIndicator: React.FC<{
  isUpdating?: boolean;
  hasError?: boolean;
  className?: string;
}> = ({
  isUpdating = false,
  hasError = false,
  className
}) => {
  if (!isUpdating && !hasError) {
    return null;
  }

  return (
    <SyncIndicator
      status={hasError ? 'error' : isUpdating ? 'syncing' : 'synced'}
      size="sm"
      className={cn("ml-2", className)}
    />
  );
};