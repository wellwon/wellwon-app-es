// =============================================================================
// Platform Pro Context
// =============================================================================
// Context for managing Platform Pro state (developer-only платформа)
// Аналог PlatformContext для основной платформы

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';
import {
  type PlatformProSection,
  type ProSectionConfig,
  platformProSections,
  getDefaultProSection,
  isValidProSection,
} from '@/config/PlatformProSectionConfig';

// =============================================================================
// Types
// =============================================================================

// View mode for declarant section
export type DeclarantViewMode = 'list' | 'package' | 'declaration';

interface PlatformProContextType {
  // Active section
  activeSection: PlatformProSection;
  setActiveSection: (section: PlatformProSection) => void;

  // Declarant-specific navigation
  declarantViewMode: DeclarantViewMode;
  packageId: string | null;
  declarationId: string | null;
  navigateToPackage: (packageId: string) => void;
  navigateToDeclaration: (declarationId?: string) => void;
  navigateToDeclarantList: () => void;

  // Sidebar state
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;

  // Theme
  isDark: boolean;
  toggleTheme: () => void;

  // Available sections
  availableSections: ProSectionConfig[];
}

// =============================================================================
// Context
// =============================================================================

const PlatformProContext = createContext<PlatformProContextType | undefined>(undefined);

// =============================================================================
// Provider
// =============================================================================

interface PlatformProProviderProps {
  children: ReactNode;
}

export const PlatformProProvider: React.FC<PlatformProProviderProps> = ({ children }) => {
  const { section, packageId: urlPackageId, declarationId: urlDeclarationId } = useParams<{
    section?: string;
    packageId?: string;
    declarationId?: string;
  }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { profile } = useAuth();

  // State
  const [activeSection, setActiveSectionState] = useState<PlatformProSection>(getDefaultProSection());
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    const stored = localStorage.getItem('platformPro_sidebarCollapsed');
    return stored ? JSON.parse(stored) : false;
  });
  const [isDark, setIsDark] = useState<boolean>(() => {
    const stored = localStorage.getItem('platformPro_theme');
    // Default to dark theme if not set
    return stored === null ? true : stored === 'dark';
  });

  // Available sections (все секции для developers)
  const availableSections = platformProSections;

  // Determine declarant view mode based on URL
  const declarantViewMode: DeclarantViewMode = (() => {
    const path = location.pathname;
    if (path.includes('/platform-pro/declaration')) {
      return 'declaration';
    }
    if (path.includes('/platform-pro/declarant/package/')) {
      return 'package';
    }
    return 'list';
  })();

  const packageId = urlPackageId || null;
  const declarationId = urlDeclarationId || null;

  // Redirect если не developer (дополнительная проверка на уровне Context)
  // Примечание: основная проверка происходит в DeveloperRoute, это резервная
  useEffect(() => {
    // Не редиректим пока profile не загружен (null/undefined)
    if (profile !== null && profile !== undefined && !profile.is_developer) {
      navigate('/platform', { replace: true });
    }
  }, [profile, navigate]);

  // Синхронизация с URL
  useEffect(() => {
    const path = location.pathname;

    // Handle declaration page
    if (path.includes('/platform-pro/declaration')) {
      setActiveSectionState('declarant');
      return;
    }

    // Handle package page
    if (path.includes('/platform-pro/declarant/package/')) {
      setActiveSectionState('declarant');
      return;
    }

    // Handle normal section routing
    if (section) {
      if (isValidProSection(section)) {
        setActiveSectionState(section);
      } else {
        // Невалидная секция - редирект на дефолтную
        const defaultSection = getDefaultProSection();
        navigate(`/platform-pro/${defaultSection}`, { replace: true });
      }
    } else {
      // Нет секции в URL - редирект на дефолтную
      const defaultSection = getDefaultProSection();
      navigate(`/platform-pro/${defaultSection}`, { replace: true });
    }
  }, [section, location.pathname, navigate]);

  // Persist sidebar state
  useEffect(() => {
    localStorage.setItem('platformPro_sidebarCollapsed', JSON.stringify(sidebarCollapsed));
  }, [sidebarCollapsed]);

  // Persist theme
  useEffect(() => {
    localStorage.setItem('platformPro_theme', isDark ? 'dark' : 'light');
  }, [isDark]);

  // Actions
  const setActiveSection = useCallback((newSection: PlatformProSection) => {
    navigate(`/platform-pro/${newSection}`);
  }, [navigate]);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => !prev);
  }, []);

  const toggleTheme = useCallback(() => {
    setIsDark((prev) => !prev);
  }, []);

  // Declarant-specific navigation
  const navigateToPackage = useCallback((pkgId: string) => {
    navigate(`/platform-pro/declarant/package/${pkgId}`);
  }, [navigate]);

  const navigateToDeclaration = useCallback((declId?: string) => {
    if (declId) {
      navigate(`/platform-pro/declaration/${declId}`);
    } else {
      navigate('/platform-pro/declaration');
    }
  }, [navigate]);

  const navigateToDeclarantList = useCallback(() => {
    navigate('/platform-pro/declarant');
  }, [navigate]);

  // Context value
  const value: PlatformProContextType = {
    activeSection,
    setActiveSection,
    declarantViewMode,
    packageId,
    declarationId,
    navigateToPackage,
    navigateToDeclaration,
    navigateToDeclarantList,
    sidebarCollapsed,
    setSidebarCollapsed,
    toggleSidebar,
    isDark,
    toggleTheme,
    availableSections,
  };

  return (
    <PlatformProContext.Provider value={value}>
      {children}
    </PlatformProContext.Provider>
  );
};

// =============================================================================
// Hook
// =============================================================================

export const usePlatformPro = (): PlatformProContextType => {
  const context = useContext(PlatformProContext);

  if (context === undefined) {
    throw new Error('usePlatformPro must be used within a PlatformProProvider');
  }

  return context;
};
