
import React from 'react';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

interface LoaderProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'spinner' | 'dots' | 'pulse';
  text?: string;
}

/**
 * Loader - красивый лоадер в стиле дизайн-системы
 * 
 * @param size - размер лоадера
 * @param variant - тип анимации (spinner, dots, pulse)
 * @param text - текст для отображения
 */
export const Loader: React.FC<LoaderProps> = ({
  className,
  size = 'md',
  variant = 'spinner',
  text = 'Загрузка...',
  ...props
}) => {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8', 
    lg: 'h-12 w-12',
  };

  const renderLoader = () => {
    switch (variant) {
      case 'dots':
        return (
          <div className="bg-card/80 backdrop-blur-sm rounded-full px-3 py-1 flex items-center gap-2 border border-white/10">
            <div className={cn(
              "border border-primary/60 border-t-transparent rounded-full animate-spin",
              size === 'sm' ? 'w-3 h-3' : size === 'md' ? 'w-4 h-4' : 'w-5 h-5'
            )} />
          </div>
        );
      
      case 'pulse':
        return (
          <div className={cn(
            "rounded-full bg-accent-red animate-pulse",
            sizeClasses[size]
          )} />
        );
      
      case 'spinner':
      default:
        return (
          <Loader2 className={cn(
            "animate-spin text-accent-red",
            sizeClasses[size]
          )} />
        );
    }
  };

  if (variant === 'dots') {
    return (
      <div className={cn("flex items-center", className)} {...props}>
        {renderLoader()}
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col items-center gap-4", className)} {...props}>
      {renderLoader()}
      {text && (
        <p className={cn(
          "text-gray-300 font-medium animate-pulse",
          size === 'sm' ? 'text-sm' : size === 'md' ? 'text-base' : 'text-lg'
        )}>
          {text}
        </p>
      )}
    </div>
  );
};

/**
 * LoadingScreen - полноэкранный лоадер
 */
export const LoadingScreen: React.FC<{ text?: string; variant?: 'spinner' | 'dots' | 'pulse' }> = ({ 
  text = 'Загрузка...', 
  variant = 'spinner' 
}) => {
  return (
    <div className="fixed inset-0 bg-[hsl(var(--dark-gray))] flex items-center justify-center z-50">
      <div className="text-center">
        <Loader size="lg" variant={variant} text={text} />
      </div>
    </div>
  );
};
