import { useEffect, useRef, useState, useCallback } from 'react';
import { logger } from '@/utils/logger';

interface UseStaggeredInViewOptions {
  threshold?: number;
  rootMargin?: string;
  debounceMs?: number;
}

export const useStaggeredInView = (itemsCount: number, options: UseStaggeredInViewOptions = {}) => {
  const [visibleItems, setVisibleItems] = useState<boolean[]>(new Array(itemsCount).fill(false));
  const refs = useRef<(HTMLDivElement | null)[]>(new Array(itemsCount).fill(null));
  const observersRef = useRef<IntersectionObserver[]>([]);
  const timeoutsRef = useRef<NodeJS.Timeout[]>([]);

  const { threshold = 0.05, rootMargin = '100px', debounceMs = 50 } = options;

  // Debounce функция для предотвращения множественных срабатываний
  const debounce = useCallback((func: Function, delay: number) => {
    let timeoutId: NodeJS.Timeout;
    return (...args: any[]) => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => func(...args), delay);
    };
  }, []);

  const setRef = useCallback((index: number) => (el: HTMLDivElement | null) => {
    // Cleanup предыдущего observer для этого элемента
    if (observersRef.current[index]) {
      observersRef.current[index].disconnect();
      observersRef.current[index] = null as any;
    }

    // Cleanup предыдущего timeout
    if (timeoutsRef.current[index]) {
      clearTimeout(timeoutsRef.current[index]);
    }

    refs.current[index] = el;
    
    if (el) {
      const debouncedCallback = debounce((isIntersecting: boolean) => {
        if (isIntersecting) {
          setVisibleItems(prev => {
            const newState = [...prev];
            if (!newState[index]) {
              newState[index] = true;
            }
            return newState;
          });
        }
      }, debounceMs);

      // Проверяем поддержку IntersectionObserver
      if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver(
          ([entry]) => {
            debouncedCallback(entry.isIntersecting);
          },
          { 
            threshold, 
            rootMargin,
            root: null
          }
        );

        try {
          observer.observe(el);
          observersRef.current[index] = observer;
        } catch (error) {
          logger.warn('IntersectionObserver failed for element', { 
            index, 
            error: error instanceof Error ? error.message : 'Unknown error', 
            component: 'useStaggeredInView' 
          });
          // Fallback: показываем элемент с задержкой
          timeoutsRef.current[index] = setTimeout(() => {
            setVisibleItems(prev => {
              const newState = [...prev];
              newState[index] = true;
              return newState;
            });
          }, Math.min(index * 150, 1000)); // Стaggered fallback с максимальной задержкой
        }
      } else {
        // Браузер не поддерживает IntersectionObserver
        logger.info('IntersectionObserver not supported, using fallback', { 
          index, 
          component: 'useStaggeredInView' 
        });
        timeoutsRef.current[index] = setTimeout(() => {
          setVisibleItems(prev => {
            const newState = [...prev];
            newState[index] = true;
            return newState;
          });
        }, Math.min(index * 100, 800)); // Более быстрый fallback для старых браузеров
      }
    }
  }, [threshold, rootMargin, debounceMs, debounce]);

  // Fallback: если ничего не загрузилось через 5 секунд, показываем все
  useEffect(() => {
    const fallbackTimeout = setTimeout(() => {
      setVisibleItems(prev => {
        const hasAnyVisible = prev.some(visible => visible);
        if (!hasAnyVisible) {
          logger.info('useStaggeredInView fallback: showing all items after timeout', { 
            component: 'useStaggeredInView',
            itemsCount,
            supportsIntersectionObserver: 'IntersectionObserver' in window 
          });
          return new Array(itemsCount).fill(true);
        }
        return prev;
      });
    }, 5000);

    return () => clearTimeout(fallbackTimeout);
  }, [itemsCount]);

  // Cleanup при размонтировании
  useEffect(() => {
    return () => {
      // Отключаем все observers
      observersRef.current.forEach(observer => {
        if (observer) {
          observer.disconnect();
        }
      });
      observersRef.current = [];

      // Очищаем все timeouts
      timeoutsRef.current.forEach(timeout => {
        if (timeout) {
          clearTimeout(timeout);
        }
      });
      timeoutsRef.current = [];
    };
  }, []);

  return { visibleItems, setRef };
};