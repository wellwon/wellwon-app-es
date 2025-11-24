// =============================================================================
// Platform Pro Section Configuration
// =============================================================================
// Конфигурация секций для Platform Pro (developer-only платформа)
// Аналог SectionConfig.ts для основной платформы

import { lazy, ComponentType } from 'react';
import { FileText, type LucideIcon } from 'lucide-react';

// =============================================================================
// Types
// =============================================================================

// Platform Pro Section IDs (расширяемо для будущих модулей)
export type PlatformProSection = 'declarant';

export interface ProSectionConfig {
  id: PlatformProSection;
  label: string;
  icon: LucideIcon;
  component: ComponentType;
  description?: string;
  badge?: number | null;
  group?: string;
}

// =============================================================================
// Lazy-loaded Components
// =============================================================================

const DeclarantContent = lazy(() =>
  import('@/components/platform-pro/sections/declarant/DeclarantContent')
);

// =============================================================================
// Section Configurations
// =============================================================================

export const platformProSections: ProSectionConfig[] = [
  {
    id: 'declarant',
    label: 'Декларация AI',
    icon: FileText,
    component: DeclarantContent,
    description: 'Управление пакетной обработкой деклараций ФТС 3.0',
    group: 'tools',
  },
  // Будущие Pro-модули добавлять здесь
  // {
  //   id: 'analytics-pro',
  //   label: 'Advanced Analytics',
  //   icon: LineChart,
  //   component: AnalyticsProContent,
  //   description: 'Продвинутая аналитика и отчеты',
  //   group: 'analytics',
  // },
];

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Get section configuration by ID
 */
export const getProSectionById = (id: string): ProSectionConfig | undefined => {
  return platformProSections.find((section) => section.id === id);
};

/**
 * Get section component by ID
 */
export const getProSectionComponent = (id: string): ComponentType | undefined => {
  const section = getProSectionById(id);
  return section?.component;
};

/**
 * Check if section ID is valid
 */
export const isValidProSection = (id: string): id is PlatformProSection => {
  return platformProSections.some((section) => section.id === id);
};

/**
 * Get default section (первая в списке)
 */
export const getDefaultProSection = (): PlatformProSection => {
  return platformProSections[0]?.id || 'declarant';
};

/**
 * Get all available sections (для навигации)
 */
export const getAvailableProSections = (): ProSectionConfig[] => {
  return platformProSections;
};