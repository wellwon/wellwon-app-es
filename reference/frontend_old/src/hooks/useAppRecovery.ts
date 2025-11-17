
/**
 * Hook for automatic application state recovery
 * during errors, reloads and failures
 */

import { useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { logger } from '@/utils/logger';
import { debounce } from '@/utils/performanceOptimizer';

interface AppState {
  route: string;
  timestamp: number;
}

const STORAGE_KEY = 'wellwon_app_state';
const RECOVERY_TIMEOUT = 5 * 60 * 1000; // 5 minutes

export const useAppRecovery = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const saveTimeoutRef = useRef<NodeJS.Timeout>();

  // Save application state
  const saveAppState = () => {
    const state: AppState = {
      route: location.pathname,
      timestamp: Date.now(),
    };
    
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      logger.debug('App state saved', { 
        component: 'AppRecovery',
        metadata: { ...state } as Record<string, unknown>
      });
    } catch (error) {
      logger.error('Failed to save app state', error, { component: 'AppRecovery' });
    }
  };

  // Recover application state
  const recoverAppState = () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (!saved) return;

      const state: AppState = JSON.parse(saved);
      const now = Date.now();
      
      // Check if state is expired
      if (now - state.timestamp > RECOVERY_TIMEOUT) {
        localStorage.removeItem(STORAGE_KEY);
        logger.info('App state expired, removed', { component: 'AppRecovery' });
        return;
      }

      logger.info('App state recovered', { 
        component: 'AppRecovery',
        metadata: { ...state } as Record<string, unknown>
      });

    } catch (error) {
      logger.error('Failed to recover app state', error, { component: 'AppRecovery' });
      localStorage.removeItem(STORAGE_KEY);
    }
  };

  // Debounced save function to prevent excessive saves
  const debouncedSaveAppState = useRef(
    debounce(saveAppState, 2000)
  ).current;

  // Effect for recovery on load
  useEffect(() => {
    recoverAppState();
  }, []);

  // Effect for saving on changes with additional stability checks
  useEffect(() => {
    // Skip if still loading or invalid route
    if (!location.pathname || location.pathname === '') return;
    
    // Clear previous timeout
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    
    // Use debounced save only for meaningful changes
    const currentRoute = location.pathname;
    
    // Avoid saving during initial mount or invalid states
    if (currentRoute !== '/') {
      debouncedSaveAppState();
    }
  }, [location.pathname, debouncedSaveAppState]);

  // Handler before page close
  useEffect(() => {
    const handleBeforeUnload = () => {
      // Immediate save before unload
      saveAppState();
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        saveAppState();
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  // Function for forced recovery
  const forceRecover = () => {
    logger.info('Force recovery initiated', { component: 'AppRecovery' });
    recoverAppState();
  };

  // Function for state reset
  const resetAppState = () => {
    localStorage.removeItem(STORAGE_KEY);
    logger.info('App state reset', { component: 'AppRecovery' });
  };

  return {
    forceRecover,
    resetAppState,
  };
};
