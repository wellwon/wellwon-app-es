import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { getAvailableSections, getDefaultSectionForUser, getUserTheme, isUserAllowedInSection, type SectionId } from '@/config/SectionConfig';
import type { Company } from '@/types/realtime-chat';
import type { SectionConfig as PlatformSectionConfig } from '@/types/platform';
import { logger } from '@/utils/logger';
import {
  useSidebarCollapsed,
  useIsLightTheme,
  useSelectedCompany,
  usePlatformActions,
} from '@/stores/usePlatformStore';

export type PlatformSection = SectionId;

interface PlatformContextType {
  activeSection: PlatformSection;
  setActiveSection: (section: PlatformSection, chatId?: string) => void;
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  userTheme: string;
  availableSections: any[];
  isDeveloper: boolean;
  selectedCompany: Company | null;
  setSelectedCompany: (company: Company | null) => void;
  companyInitialized: boolean;
  chatId?: string;
  // Light theme support (like Declarant page)
  isLightTheme: boolean;
  toggleTheme: () => void;
}

const PlatformContext = createContext<PlatformContextType | null>(null);

export const PlatformProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { section, chatId } = useParams<{ section?: string; chatId?: string }>();
  const navigate = useNavigate();
  const { profile } = useAuth();
  const [activeSection, setActiveSectionState] = useState<PlatformSection>('chat');

  // Platform UI state from Zustand store (persisted automatically)
  const sidebarCollapsed = useSidebarCollapsed();
  const isLightTheme = useIsLightTheme();
  const selectedCompany = useSelectedCompany();
  const platformActions = usePlatformActions();

  // Derive companyInitialized from store hydration (Zustand persist handles this)
  const companyInitialized = true; // Store is hydrated synchronously

  // Get user type - simplified to just isDeveloper boolean
  const isDeveloper = profile?.is_developer || false;
  
  // Get available sections for user type
  const availableSections = useMemo(() => getAvailableSections(isDeveloper), [isDeveloper]);
  
  // Get user theme
  const userTheme = useMemo(() => getUserTheme(isDeveloper), [isDeveloper]);

  // Check if section is valid and accessible for current user
  const isValidAndAccessibleSection = useCallback((section: string): section is PlatformSection => {
    return availableSections.some(s => s.id === section);
  }, [availableSections]);

  // Синхронизация с URL параметром
  useEffect(() => {
    if (section) {
      if (isValidAndAccessibleSection(section)) {
        setActiveSectionState(section);
      } else {
        // Если секция недоступна для пользователя, редиректим на дефолтную
        const defaultSection = getDefaultSectionForUser(isDeveloper);
        navigate(`/platform/${defaultSection}`, { replace: true });
      }
    } else {
      // Если секция не указана, редиректим на дефолтную для типа пользователя
      const defaultSection = getDefaultSectionForUser(isDeveloper);
      navigate(`/platform/${defaultSection}`, { replace: true });
    }
  }, [section, navigate, isValidAndAccessibleSection, isDeveloper]);

  // Auto-redirect when role changes and current section becomes inaccessible
  useEffect(() => {
    if (!activeSection) return;

    const allowed = isUserAllowedInSection(activeSection, isDeveloper);
    if (!allowed) {
      logger.info('Role changed - current section no longer accessible, redirecting', {
        section: activeSection,
        isDeveloper,
        component: 'PlatformContext'
      });
      const defaultSection = getDefaultSectionForUser(isDeveloper);
      navigate(`/platform/${defaultSection}`, { replace: true });
    }
  }, [isDeveloper, activeSection, navigate]);

  // Wrapper for setSidebarCollapsed to maintain context API compatibility
  const setSidebarCollapsed = useCallback((collapsed: boolean) => {
    platformActions.setSidebarCollapsed(collapsed);
  }, [platformActions]);

  // Wrapper for toggleSidebar
  const toggleSidebar = useCallback(() => {
    platformActions.toggleSidebar();
  }, [platformActions]);

  // Wrapper for setSelectedCompany - accepts Company and extracts minimal data
  const setSelectedCompany = useCallback((company: Company | null) => {
    if (company) {
      platformActions.setSelectedCompany({
        id: company.id,
        name: company.name,
        company_type: company.company_type,
      });
    } else {
      platformActions.clearCompany();
    }
  }, [platformActions]);

  // CRITICAL: Clear selectedCompany when it's deleted
  // This prevents repeated "Company not found" errors from persisted localStorage
  useEffect(() => {
    const handleCompanyDeleted = (event: CustomEvent) => {
      const deletedId = event.detail?.company_id || event.detail?.id;
      if (deletedId && selectedCompany?.id === deletedId) {
        logger.info('Company deleted - clearing selectedCompany from store', { deletedId });
        platformActions.clearCompany();
      }
    };

    const handleGroupDeletionCompleted = (event: CustomEvent) => {
      const deletedId = event.detail?.company_id;
      if (deletedId && selectedCompany?.id === deletedId) {
        logger.info('Group deletion completed - clearing selectedCompany from store', { deletedId });
        platformActions.clearCompany();
      }
    };

    window.addEventListener('companyDeleted', handleCompanyDeleted as EventListener);
    window.addEventListener('groupDeletionCompleted', handleGroupDeletionCompleted as EventListener);

    return () => {
      window.removeEventListener('companyDeleted', handleCompanyDeleted as EventListener);
      window.removeEventListener('groupDeletionCompleted', handleGroupDeletionCompleted as EventListener);
    };
  }, [selectedCompany?.id, platformActions]);

  // Toggle theme function (light/dark for content area, sidebar stays dark)
  // Disables transitions for instant theme switch
  const toggleTheme = useCallback(() => {
    // Add no-transitions class to body to disable all transitions during theme change
    document.body.classList.add('no-transitions');

    platformActions.toggleTheme();

    // Remove no-transitions class after a brief moment to re-enable transitions
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.body.classList.remove('no-transitions');
      });
    });
  }, [platformActions]);

  // Функция для изменения активной секции с обновлением URL
  const setActiveSection = useCallback((newSection: PlatformSection, newChatId?: string) => {
    if (newChatId) {
      navigate(`/platform/${newSection}/${newChatId}`);
    } else {
      navigate(`/platform/${newSection}`);
    }
  }, [navigate]);

  // Мемоизация значения контекста для предотвращения лишних ререндеров
  const contextValue = useMemo(() => ({
    activeSection,
    setActiveSection,
    sidebarCollapsed,
    setSidebarCollapsed,
    toggleSidebar,
    userTheme,
    availableSections,
    isDeveloper,
    // Cast minimal stored company to Company type (consumers only use id, name, company_type)
    selectedCompany: selectedCompany as Company | null,
    setSelectedCompany,
    companyInitialized,
    chatId,
    isLightTheme,
    toggleTheme
  }), [activeSection, setActiveSection, sidebarCollapsed, setSidebarCollapsed, toggleSidebar, userTheme, availableSections, isDeveloper, selectedCompany, setSelectedCompany, companyInitialized, chatId, isLightTheme, toggleTheme]);

  return (
    <PlatformContext.Provider value={contextValue}>
      {children}
    </PlatformContext.Provider>
  );
};

export const usePlatform = () => {
  const context = useContext(PlatformContext);
  if (!context) {
    throw new Error('usePlatform must be used within a PlatformProvider');
  }
  return context;
};