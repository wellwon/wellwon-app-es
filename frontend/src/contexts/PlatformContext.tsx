import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { getAvailableSections, getDefaultSectionForUser, getUserTheme, isUserAllowedInSection, type SectionId } from '@/config/SectionConfig';
import type { Company } from '@/types/realtime-chat';
import type { SectionConfig as PlatformSectionConfig } from '@/types/platform';
import { logger } from '@/utils/logger';

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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const saved = localStorage.getItem('ww-platform-sidebar-collapsed');
    return saved === 'true';
  });
  const [isInitialized, setIsInitialized] = useState(false);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [companyInitialized, setCompanyInitialized] = useState(false);
  // Light theme support (like Declarant page - content is light, sidebar stays dark)
  const [isLightTheme, setIsLightTheme] = useState(() => {
    const saved = localStorage.getItem('ww-platform-light-theme');
    return saved === 'true';
  });

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

  // Загрузка состояния из localStorage (только один раз)
  useEffect(() => {
    if (isInitialized) return;

    try {
      const savedCompany = localStorage.getItem('ww-platform-selected-company');
      if (savedCompany) {
        try {
          const company = JSON.parse(savedCompany);
          // Security: Only store company ID and name, not full object
          if (company && company.id && company.name) {
            logger.debug('Restored company from localStorage', { companyId: company.id, component: 'PlatformContext' });
            setSelectedCompany(company);
          } else {
            localStorage.removeItem('ww-platform-selected-company');
          }
        } catch (error) {
          logger.error('Error restoring company from localStorage', error, { component: 'PlatformContext' });
          localStorage.removeItem('ww-platform-selected-company');
        }
      }
      setCompanyInitialized(true);
    } catch (error) {
      logger.error('Error loading platform state', error, { component: 'PlatformContext' });
    }

    setIsInitialized(true);
  }, [isInitialized]);

  // Сохранение состояния в localStorage только если инициализирован
  useEffect(() => {
    if (!isInitialized) return;
    localStorage.setItem('ww-platform-sidebar-collapsed', JSON.stringify(sidebarCollapsed));
  }, [sidebarCollapsed, isInitialized]);

  // Сохранение выбранной компании в localStorage (только ID и название)
  useEffect(() => {
    if (!isInitialized) return;
    if (selectedCompany) {
      // Security: Store only essential data (no sensitive company details)
      const companyToStore = {
        id: selectedCompany.id,
        name: selectedCompany.name,
        company_type: selectedCompany.company_type
      };
      localStorage.setItem('ww-platform-selected-company', JSON.stringify(companyToStore));
    } else {
      localStorage.removeItem('ww-platform-selected-company');
    }
  }, [selectedCompany, isInitialized]);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed(!sidebarCollapsed);
  }, [sidebarCollapsed]);

  // Toggle theme function (light/dark for content area, sidebar stays dark)
  // Disables transitions for instant theme switch
  const toggleTheme = useCallback(() => {
    // Add no-transitions class to body to disable all transitions during theme change
    document.body.classList.add('no-transitions');

    const newValue = !isLightTheme;
    setIsLightTheme(newValue);
    localStorage.setItem('ww-platform-light-theme', String(newValue));

    // Remove no-transitions class after a brief moment to re-enable transitions
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.body.classList.remove('no-transitions');
      });
    });
  }, [isLightTheme]);

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
    selectedCompany,
    setSelectedCompany,
    companyInitialized,
    chatId,
    isLightTheme,
    toggleTheme
  }), [activeSection, setActiveSection, sidebarCollapsed, toggleSidebar, userTheme, availableSections, isDeveloper, selectedCompany, companyInitialized, chatId, isLightTheme, toggleTheme]);

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