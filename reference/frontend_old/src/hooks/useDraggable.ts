import { useState, useRef, useCallback, useEffect } from 'react';
import { secureSetItem, secureGetItem } from '@/utils/security';
import { logger } from '@/utils/logger';

interface Position {
  x: number;
  y: number;
}

interface DraggableOptions {
  storageKey?: string;
  bounds?: {
    top: number;
    left: number;
    right: number;
    bottom: number;
  };
}

export const useDraggable = (options: DraggableOptions = {}) => {
  const { storageKey, bounds } = options;
  
  const [position, setPosition] = useState<Position>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState<Position>({ x: 0, y: 0 });
  const elementRef = useRef<HTMLDivElement>(null);

  // Загрузка позиции из безопасного хранилища
  useEffect(() => {
    if (storageKey) {
      try {
        const savedPosition = secureGetItem(storageKey, 30 * 24 * 60 * 60 * 1000); // 30 дней
        if (savedPosition) {
          const parsed = JSON.parse(savedPosition) as Position;
          setPosition(parsed);
        }
      } catch (error) {
        logger.error('Position load error', error, { component: 'useDraggable' });
      }
    }
  }, [storageKey]);

  // Безопасное сохранение позиции
  const savePosition = useCallback((newPosition: Position) => {
    if (storageKey) {
      try {
        secureSetItem(storageKey, JSON.stringify(newPosition));
      } catch (error) {
        logger.error('Position save error', error, { component: 'useDraggable' });
      }
    }
  }, [storageKey]);

  // Ограничение позиции в пределах bounds
  const constrainPosition = useCallback((pos: Position): Position => {
    if (!bounds || !elementRef.current) return pos;
    
    const rect = elementRef.current.getBoundingClientRect();
    const constrainedX = Math.max(
      bounds.left,
      Math.min(pos.x, bounds.right - rect.width)
    );
    const constrainedY = Math.max(
      bounds.top,
      Math.min(pos.y, bounds.bottom - rect.height)
    );
    
    return { x: constrainedX, y: constrainedY };
  }, [bounds]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!elementRef.current) return;
    
    e.preventDefault();
    setIsDragging(true);
    
    const rect = elementRef.current.getBoundingClientRect();
    setDragOffset({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    });
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging || !elementRef.current) return;
    
    const newPosition = {
      x: e.clientX - dragOffset.x,
      y: e.clientY - dragOffset.y
    };
    
    const constrainedPosition = constrainPosition(newPosition);
    setPosition(constrainedPosition);
  }, [isDragging, dragOffset, constrainPosition]);

  const handleMouseUp = useCallback(() => {
    if (isDragging) {
      setIsDragging(false);
      savePosition(position);
    }
  }, [isDragging, position, savePosition]);

  // Touch события для мобильных устройств
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (!elementRef.current) return;
    
    e.preventDefault();
    setIsDragging(true);
    
    const touch = e.touches[0];
    const rect = elementRef.current.getBoundingClientRect();
    setDragOffset({
      x: touch.clientX - rect.left,
      y: touch.clientY - rect.top
    });
  }, []);

  const handleTouchMove = useCallback((e: TouchEvent) => {
    if (!isDragging || !elementRef.current) return;
    
    e.preventDefault();
    const touch = e.touches[0];
    const newPosition = {
      x: touch.clientX - dragOffset.x,
      y: touch.clientY - dragOffset.y
    };
    
    const constrainedPosition = constrainPosition(newPosition);
    setPosition(constrainedPosition);
  }, [isDragging, dragOffset, constrainPosition]);

  const handleTouchEnd = useCallback(() => {
    if (isDragging) {
      setIsDragging(false);
      savePosition(position);
    }
  }, [isDragging, position, savePosition]);

  // Подписка на события
  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.addEventListener('touchmove', handleTouchMove, { passive: false });
      document.addEventListener('touchend', handleTouchEnd);
      
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        document.removeEventListener('touchmove', handleTouchMove);
        document.removeEventListener('touchend', handleTouchEnd);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp, handleTouchMove, handleTouchEnd]);

  // Обновление bounds при изменении размера окна
  useEffect(() => {
    const handleResize = () => {
      if (bounds) {
        const constrainedPosition = constrainPosition(position);
        if (constrainedPosition.x !== position.x || constrainedPosition.y !== position.y) {
          setPosition(constrainedPosition);
          savePosition(constrainedPosition);
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [position, constrainPosition, savePosition, bounds]);

  const resetPosition = useCallback(() => {
    setPosition({ x: 0, y: 0 });
  }, []);

  return {
    elementRef,
    position,
    isDragging,
    resetPosition,
    handlers: {
      onMouseDown: handleMouseDown,
      onTouchStart: handleTouchStart,
    }
  };
};