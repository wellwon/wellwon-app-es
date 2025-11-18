
import { useCallback } from 'react';

export const useNotificationSound = () => {
  const playNotificationSound = useCallback(() => {
    try {
      const audio = new Audio('/sounds/notification.mp3');
      audio.volume = 0.3;
      
      const playPromise = audio.play();
      
      if (playPromise !== undefined) {
        playPromise.catch(() => {
          // Тихо игнорируем ошибки воспроизведения
        });
      }
    } catch (error) {
      // Тихо игнорируем ошибки
    }
  }, []);

  return { playNotificationSound };
};
