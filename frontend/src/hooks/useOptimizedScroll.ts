import { useCallback, useRef } from 'react';
import { logger } from '@/utils/logger';

interface UseOptimizedScrollOptions {
  onScrollComplete?: () => void;
  delay?: number;
}

interface ScrollToBottomOptions {
  force?: boolean;
}

export const useOptimizedScroll = ({ onScrollComplete, delay = 300 }: UseOptimizedScrollOptions = {}) => {
  const timeoutRef = useRef<NodeJS.Timeout>();

  const scrollToBottom = useCallback((scrollAreaRef: React.RefObject<HTMLDivElement>, options: ScrollToBottomOptions = {}) => {
    try {
      if (scrollAreaRef.current) {
        // Ищем viewport для Radix ScrollArea
        const viewport = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
        const element = viewport || scrollAreaRef.current;
        
        if (options.force) {
          // Force scroll with smooth behavior (для кнопки "вниз")
          element.scrollTo({ top: element.scrollHeight, behavior: 'smooth' });
        } else {
          // Проверяем, нужен ли скролл - помещается ли контент в viewport
          const isScrollNeeded = element.scrollHeight > element.clientHeight;
          
          if (isScrollNeeded) {
            // Мгновенный скролл без анимации (для открытия чата и авто-скролла)
            element.scrollTop = element.scrollHeight;
          }
        }
        
        // Debounced callback
        if (onScrollComplete) {
          clearTimeout(timeoutRef.current);
          timeoutRef.current = setTimeout(onScrollComplete, delay);
        }
      }
    } catch (error) {
      logger.error('Ошибка прокрутки:', error, { component: 'useOptimizedScroll' });
    }
  }, [onScrollComplete, delay]);

  const checkIfScrollNeeded = useCallback((scrollAreaRef: React.RefObject<HTMLDivElement>) => {
    try {
      if (scrollAreaRef.current) {
        const viewport = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
        const element = viewport || scrollAreaRef.current;
        return element.scrollHeight > element.clientHeight;
      }
      return false;
    } catch (error) {
      logger.error('Ошибка проверки скролла:', error, { component: 'useOptimizedScroll' });
      return false;
    }
  }, []);

  return { scrollToBottom, checkIfScrollNeeded };
};