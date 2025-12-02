/**
 * Types for TestApp - Тестовая страница дизайн-системы
 */

import { LucideIcon } from 'lucide-react';

/**
 * Состояние формы создания декларации
 */
export interface CreateDeclarationState {
  direction: '' | 'IM' | 'EK' | 'TT';
  customsProcedure: string;
  feature: string;
  customsOffice: string;
  organization: string;
  declarant: string;
  transitType: string;
  transitFeature: string;
  selectedGoodsDocs: string[];
  selectedRegDocs: string[];
}

/**
 * Конфигурация темы (светлая/тёмная)
 */
export interface ThemeConfig {
  page: string;
  text: {
    primary: string;
    secondary: string;
  };
  card: {
    background: string;
    border: string;
  };
  button: {
    default: string;
    danger: string;
  };
  table: {
    header: string;
    row: string;
    border: string;
  };
}

/**
 * Тип декларации для кнопок
 */
export interface DeclarationType {
  value: string;
  label: string;
  description: string;
}

/**
 * Элемент выпадающего списка
 */
export interface SelectOption {
  value: string;
  label: string;
}

/**
 * Данные пакета декларации
 */
export interface BatchData {
  id: string;
  number: string;
  status: string;
  docs: string;
  extracts: number;
  date: string;
  icon: LucideIcon;
  iconColor: string;
  statusText: string;
}

/**
 * Статистика по пакетам
 */
export interface StatsData {
  total_batches: number;
  completed_batches: number;
  processing_batches: number;
  total_documents: number;
}

/**
 * Документ (основной, по товарам, регистрационный)
 */
export interface DocumentItem {
  id: string;
  name?: string;
  type?: string;
  code?: string;
  number?: string;
  date?: string;
  status?: string;
  statusColor?: string;
  hasLink?: boolean;
  linkedGoods?: number;
  archived?: boolean;
  presentedWithDT?: boolean;
}

/**
 * Пропсы для SidebarMock
 */
export interface SidebarMockProps {
  collapsed: boolean;
  toggleSidebar: () => void;
  activeSection: string;
  setActiveSection: (id: string) => void;
}

/**
 * Пропсы для HeaderBarMock
 */
export interface HeaderBarMockProps {
  isDark: boolean;
  toggleTheme: () => void;
  activeSection: string;
  viewMode: 'list' | 'create';
  onBack: () => void;
}

/**
 * Пропсы для CreateDeclarationPage
 */
export interface CreateDeclarationPageProps {
  // Состояние формы
  state: CreateDeclarationState;
  onDirectionChange: (direction: '' | 'IM' | 'EK' | 'TT') => void;
  onCustomsProcedureChange: (value: string) => void;
  onFeatureChange: (value: string) => void;
  onCustomsOfficeChange: (value: string) => void;
  onOrganizationChange: (value: string) => void;
  onDeclarantChange: (value: string) => void;
  onTransitTypeChange: (value: string) => void;
  onTransitFeatureChange: (value: string) => void;
  onSelectedGoodsDocsChange: (docs: string[]) => void;
  onSelectedRegDocsChange: (docs: string[]) => void;

  // Тема
  isDark: boolean;
  theme: ThemeConfig;

  // Стили Select
  selectStyles: string;
  selectContentStyles: string;

  // Действия
  onCancel: () => void;
  onSave: () => void;
}
