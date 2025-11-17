import React, { createContext, useContext } from 'react';
import { useRealtimeChat } from '@/hooks/useRealtimeChat';
import type { RealtimeChatContextType } from '@/types/realtime-chat';

const RealtimeChatContext = createContext<RealtimeChatContextType | null>(null);

export const RealtimeChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const chatData = useRealtimeChat();

  return (
    <RealtimeChatContext.Provider value={chatData}>
      {children}
    </RealtimeChatContext.Provider>
  );
};

export const useRealtimeChatContext = () => {
  const context = useContext(RealtimeChatContext);
  if (!context) {
    throw new Error('useRealtimeChatContext must be used within a RealtimeChatProvider');
  }
  return context;
};