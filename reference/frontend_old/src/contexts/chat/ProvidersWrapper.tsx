import React, { ReactNode } from 'react';
import { UnifiedSidebarProvider } from './UnifiedSidebarProvider';
import { RealtimeChatProvider } from '@/contexts/RealtimeChatContext';
import { ChatDisplayOptionsProvider } from './ChatDisplayOptionsContext';

export const ProvidersWrapper: React.FC<{ children: ReactNode }> = ({ children }) => {
  return (
    <RealtimeChatProvider>
      <UnifiedSidebarProvider>
        <ChatDisplayOptionsProvider>
          {children}
        </ChatDisplayOptionsProvider>
      </UnifiedSidebarProvider>
    </RealtimeChatProvider>
  );
};