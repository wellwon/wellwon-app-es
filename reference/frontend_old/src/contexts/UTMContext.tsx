
import React, { createContext, useContext, ReactNode, useMemo } from 'react';
import { useUTMParams, UTMParams } from '@/hooks/useUTMParams';

interface UTMContextType {
  utmParams: UTMParams;
  appendUTMToURL: (url: string) => string;
  clearUTMParams: () => void;
  hasUTMParams: boolean;
}

const UTMContext = createContext<UTMContextType | undefined>(undefined);

export const useUTMContext = () => {
  const context = useContext(UTMContext);
  if (!context) {
    throw new Error('useUTMContext must be used within UTMProvider');
  }
  return context;
};

interface UTMProviderProps {
  children: ReactNode;
}

export const UTMProvider: React.FC<UTMProviderProps> = ({ children }) => {
  const utmHook = useUTMParams();

  // Мемоизируем значение контекста для предотвращения лишних ререндеров
  const contextValue = useMemo(() => utmHook, [
    JSON.stringify(utmHook.utmParams),
    utmHook.hasUTMParams
  ]);

  return (
    <UTMContext.Provider value={contextValue}>
      {children}
    </UTMContext.Provider>
  );
};
