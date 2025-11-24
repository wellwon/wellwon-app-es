// =============================================================================
// Platform Pro Context
// =============================================================================
// Context for managing Platform Pro state (developer-only платформа)
// Аналог PlatformContext для основной платформы

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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

interface PlatformProContextType {
  // Active section
  activeSection: PlatformProSection;
  setActiveSection: (section: PlatformProSection) => void;

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
  const { section } = useParams<{ section?: string }>();
  const navigate = useNavigate();
  const { profile } = useAuth();

  // State
  const [activeSection, setActiveSectionState] = useState<PlatformProSection>(getDefaultProSection());
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    const stored = localStorage.getItem('platformPro_sidebarCollapsed');
    return stored ? JSON.parse(stored) : false;
  });
  const [isDark, setIsDark] = useState<boolean>(() => {
    const stored = localStorage.getItem('platformPro_theme');
    return stored === 'dark';
  });

  // Available sections (все секции для developers)
  const availableSections = platformProSections;

  // Redirect если не developer (дополнительная проверка на уровне Context)
  useEffect(() => {
    if (profile && !profile.is_developer) {
      navigate('/platform', { replace: true });
    }
  }, [profile, navigate]);

  // Синхронизация с URL
  useEffect(() => {
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
  }, [section, navigate]);

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

  // Context value
  const value: PlatformProContextType = {
    activeSection,
    setActiveSection,
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
