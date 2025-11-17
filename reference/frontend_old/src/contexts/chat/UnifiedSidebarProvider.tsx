import React, { createContext, useContext, useState, ReactNode } from 'react';
import type { DealInfo } from '@/types/deal-info';
import type { SidebarData } from '@/types/platform';

export type SidebarContentType = 
  | 'deal-summary' 
  | 'products' 
  | 'payment' 
  | 'logistics' 
  | 'lastmile'
  | 'tasks'
  | 'tools'
  | 'performance'
  | 'communication'
  | 'services'
  | 'system-settings'
  | 'analytics'
  | 'users'
  | 'chat-list'
  | 'deal'
  | 'message-templates'
  | 'admin-actions'
  | null;

export interface UnifiedSidebarContextType {
  isOpen: boolean;
  contentType: SidebarContentType;
  selectedDeal: DealInfo | null;
  selectedServices: string[];
  openSidebar: (type: SidebarContentType, data?: SidebarData) => void;
  closeSidebar: () => void;
  setSelectedServices: (services: string[]) => void;
  toggleService: (serviceId: string) => void;
}

const UnifiedSidebarContext = createContext<UnifiedSidebarContextType | null>(null);

export const UnifiedSidebarProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [contentType, setContentType] = useState<SidebarContentType>(null);
  const [selectedDeal, setSelectedDeal] = useState<DealInfo | null>(null);
  const [selectedServices, setSelectedServices] = useState<string[]>([]);

  const openSidebar = (type: SidebarContentType, data?: SidebarData) => {
    // Если открываем тот же тип контента - закрываем сайдбар
    if (isOpen && contentType === type) {
      closeSidebar();
      return;
    }

    setContentType(type);
    
    if (type === 'deal-summary' && data) {
      setSelectedDeal(data as unknown as DealInfo);
    }
    
    setIsOpen(true);
  };

  const closeSidebar = () => {
    setIsOpen(false);
    setContentType(null);
    setSelectedDeal(null);
  };

  const toggleService = (serviceId: string) => {
    setSelectedServices(prev => 
      prev.includes(serviceId) 
        ? prev.filter(id => id !== serviceId)
        : [...prev, serviceId]
    );
  };

  return (
    <UnifiedSidebarContext.Provider value={{
      isOpen,
      contentType,
      selectedDeal,
      selectedServices,
      openSidebar,
      closeSidebar,
      setSelectedServices,
      toggleService
    }}>
      {children}
    </UnifiedSidebarContext.Provider>
  );
};

export const useUnifiedSidebar = () => {
  const context = useContext(UnifiedSidebarContext);
  if (!context) {
    throw new Error('useUnifiedSidebar must be used within a UnifiedSidebarProvider');
  }
  return context;
};