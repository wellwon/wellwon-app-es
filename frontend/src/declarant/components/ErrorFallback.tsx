// =============================================================================
// ErrorFallback - Error state component for Declarant module
// =============================================================================
// Стилизован согласно DESIGN_SYSTEM.md v5.0

import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ErrorFallbackProps {
  title?: string;
  message?: string;
  error?: string | Error;
  onRetry?: () => void;
  retryLabel?: string;
  isDark?: boolean;
}

export const ErrorFallback: React.FC<ErrorFallbackProps> = ({
  title = 'Что-то пошло не так',
  message = 'Произошла ошибка при загрузке.',
  error,
  onRetry,
  retryLabel = 'Перезагрузить страницу',
  isDark = true,
}) => {
  const errorMessage = error instanceof Error ? error.message : error;

  // Theme based on DESIGN_SYSTEM.md Section 7.2
  const theme = isDark
    ? {
        page: 'bg-[#1a1a1e]',
        card: 'bg-[#232328] border-white/10',
        text: {
          primary: 'text-white',
          secondary: 'text-gray-400',
          muted: 'text-gray-500',
        },
        errorBg: 'bg-black/30',
      }
    : {
        page: 'bg-[#f4f4f4]',
        card: 'bg-white border-gray-300 shadow-sm',
        text: {
          primary: 'text-gray-900',
          secondary: 'text-gray-600',
          muted: 'text-gray-400',
        },
        errorBg: 'bg-gray-100',
      };

  const handleRetry = () => {
    if (onRetry) {
      onRetry();
    } else {
      window.location.reload();
    }
  };

  return (
    <div className={cn('min-h-screen flex items-center justify-center p-8', theme.page)}>
      {/* Card - Section 4: rounded-2xl, Section 5.2: p-6 (card padding = 24px, using p-8 for more space) */}
      <div className={cn('max-w-md w-full p-8 rounded-2xl border', theme.card)}>
        {/* Header with icon - Section 3: gap-3 */}
        <div className="flex items-center gap-3 mb-4">
          {/* Icon - accent-red from Section 1.4 */}
          <AlertCircle className="w-8 h-8 text-accent-red flex-shrink-0" />
          {/* Title - Section 2.2: text-xl for card titles, Section 2.3: font-bold */}
          <h1 className={cn('text-xl font-bold', theme.text.primary)}>{title}</h1>
        </div>

        {/* Message - Section 2.2: text-sm for body, Section 1.2: secondary text */}
        <p className={cn('text-sm mb-4', theme.text.secondary)}>{message}</p>

        {/* Error details - monospace font from Section 2.1 */}
        {errorMessage && (
          <div className={cn('mb-4 p-3 rounded-lg', theme.errorBg)}>
            <p className={cn('text-xs font-mono break-all', theme.text.muted)}>
              {errorMessage}
            </p>
          </div>
        )}

        {/* Button - Section 9.2: Primary Button (CTA) */}
        {/* h-10 px-4 rounded-xl, text-sm font-medium, bg-accent-red */}
        <button
          onClick={handleRetry}
          className={cn(
            'w-full h-10 px-4 rounded-xl flex items-center justify-center gap-2',
            'bg-accent-red text-white text-sm font-medium',
            'hover:bg-accent-red/90 transition-colors',
            'focus:outline-none focus:ring-0'
          )}
        >
          <RefreshCw className="w-4 h-4" />
          {retryLabel}
        </button>
      </div>
    </div>
  );
};

export default ErrorFallback;
