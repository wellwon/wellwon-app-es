import React, { ReactNode } from 'react';
import { UnifiedSidebarProvider } from './UnifiedSidebarProvider';
import { RealtimeChatProvider } from '@/contexts/RealtimeChatContext';
// ChatDisplayOptionsProvider removed - state now managed by useChatUIStore (Zustand)

export const ProvidersWrapper: React.FC<{ children: ReactNode }> = ({ children }) => {
  return (
    <RealtimeChatProvider>
      <UnifiedSidebarProvider>
        {children}
      </UnifiedSidebarProvider>
    </RealtimeChatProvider>
  );
};