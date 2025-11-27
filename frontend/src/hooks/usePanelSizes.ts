import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'ww:panel-sizes';

interface PanelSizes {
  chatSidebar: number;  // percentage for chat sidebar (left)
  rightSidebar: number; // percentage for right sidebar
}

const DEFAULT_SIZES: PanelSizes = {
  chatSidebar: 20,   // ~320px out of typical 1600px viewport
  rightSidebar: 25,  // ~420px out of typical 1600px viewport
};

export function usePanelSizes() {
  const [sizes, setSizes] = useState<PanelSizes>(() => {
    if (typeof window === 'undefined') return DEFAULT_SIZES;

    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        return {
          chatSidebar: parsed.chatSidebar ?? DEFAULT_SIZES.chatSidebar,
          rightSidebar: parsed.rightSidebar ?? DEFAULT_SIZES.rightSidebar,
        };
      }
    } catch (error) {
      console.warn('Failed to load panel sizes from localStorage:', error);
    }
    return DEFAULT_SIZES;
  });

  const saveSizes = useCallback((newSizes: Partial<PanelSizes>) => {
    setSizes(prev => {
      const updated = { ...prev, ...newSizes };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch (error) {
        console.warn('Failed to save panel sizes to localStorage:', error);
      }
      return updated;
    });
  }, []);

  const resetSizes = useCallback(() => {
    setSizes(DEFAULT_SIZES);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      console.warn('Failed to reset panel sizes in localStorage:', error);
    }
  }, []);

  return {
    sizes,
    saveSizes,
    resetSizes,
    DEFAULT_SIZES,
  };
}
