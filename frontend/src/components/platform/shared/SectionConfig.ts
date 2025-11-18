import { lazy } from 'react';
import { LucideIcon, LayoutDashboard, MessageSquare, MessagesSquare, Kanban, Contact, Shield, MessageCircle, Wrench, Building2, Settings, Send } from 'lucide-react';
import { createLazyComponent } from '@/components/shared/LazyErrorBoundary';

// Lazy loading с error handling для компонентов секций
const AdminDashboardContent = createLazyComponent(() => import('../sections/dashboard/AdminDashboardContent'));
const CompanyPageContent = createLazyComponent(() => import('../sections/company/CompanyPageContent'));

// Admin sections
const AdminKanbanContent = createLazyComponent(() => import('../sections/kanban/AdminKanbanContent'));
const AdminContactsContent = createLazyComponent(() => import('../sections/contacts/AdminContactsContent'));
const AdminCompaniesContent = createLazyComponent(() => import('../sections/companies/AdminCompaniesContent'));
const AdminModerationContent = createLazyComponent(() => import('../sections/moderation/AdminModerationContent'));
const AdminChatSettingsContent = createLazyComponent(() => import('../sections/chat-settings/AdminChatSettingsContent'));
const AdminUsefulServicesContent = createLazyComponent(() => import('../sections/useful-services/AdminUsefulServicesContent'));
const AdminSettingsContent = createLazyComponent(() => import('../sections/settings/AdminSettingsContent'));
const TelegramManagementContent = createLazyComponent(() => import('../sections/telegram/TelegramManagementContent'));

// Common sections
const ChatContent = createLazyComponent(() => import('../../chat/ChatContent'));

export type SectionId = 
  | 'dashboard' 
  | 'settings'
  | 'chat'
  | 'personal-chats'
  | 'company-page'
  | 'kanban'
  | 'contacts'
  | 'companies'
  | 'moderation'
  | 'chat-settings'
  | 'useful-services'
  | 'telegram';

export interface SectionConfig {
  id: SectionId;
  label: string;
  icon: LucideIcon;
  component: React.ComponentType<any>;
  badge?: number | null;
  description?: string;
  group?: 'main' | 'processing' | 'other' | 'chats' | 'tools';
  isDeveloperOnly?: boolean;
  isUserOnly?: boolean;
}

export interface SectionGroup {
  id: string;
  label: string;
  sections: SectionConfig[];
}

export const platformSections: SectionConfig[] = [
  // Chat section - Group chats
  {
    id: 'chat',
    label: 'Групповые чаты',
    icon: MessagesSquare,
    component: ChatContent,
    description: 'Групповые чаты с клиентами',
  },

  // Personal chats section - available for all users
  {
    id: 'personal-chats',
    label: 'Персональные чаты',
    icon: MessageSquare,
    component: ChatContent,
    description: 'Персональные чаты с клиентами',
  },
  
  // Dashboard - developer only
  {
    id: 'dashboard',
    label: 'Дашборд',
    icon: LayoutDashboard,
    component: AdminDashboardContent,
    group: 'main',
    description: 'Общий обзор платформы',
    isDeveloperOnly: true,
  },
  
  // Hidden company page section (not shown in menu)
  {
    id: 'company-page',
    label: 'Страница компании',
    icon: Building2,
    component: CompanyPageContent,
    description: 'Подробная информация о компании',
  },
  
  // Settings
  {
    id: 'settings',
    label: 'Настройки',
    icon: Settings,
    component: AdminSettingsContent,
    group: 'other',
    description: 'Настройки системы',
  },
  
  // All sections
  {
    id: 'kanban',
    label: 'Канбан',
    icon: Kanban,
    component: AdminKanbanContent,
    group: 'main',
    description: 'Управление задачами и проектами',
  },
  {
    id: 'contacts',
    label: 'Контакты',
    icon: Contact,
    component: AdminContactsContent,
    group: 'main',
    description: 'Управление контактами и клиентами',
  },
  {
    id: 'companies',
    label: 'Компании',
    icon: Building2,
    component: AdminCompaniesContent,
    group: 'main',
    description: 'Управление компаниями и партнерами',
  },
  {
    id: 'moderation',
    label: 'Модерация',
    icon: Shield,
    component: AdminModerationContent,
    group: 'tools',
    description: 'Модерация чатов и контента',
    isDeveloperOnly: true,
  },
  {
    id: 'chat-settings',
    label: 'Настройки чатов',
    icon: MessageCircle,
    component: AdminChatSettingsContent,
    group: 'chats',
    description: 'Конфигурация и настройки чатов',
    isDeveloperOnly: true,
  },
  {
    id: 'telegram',
    label: 'Telegram',
    icon: Send,
    component: TelegramManagementContent,
    group: 'chats',
    description: 'Управление интеграцией с Telegram',
    isDeveloperOnly: true,
  },
  {
    id: 'useful-services',
    label: 'Полезные сервисы',
    icon: Wrench,
    component: AdminUsefulServicesContent,
    group: 'tools',
    description: 'Инструменты и полезные сервисы',
  },
];

// Динамические группы секций в зависимости от типа пользователя
const getGroupsForUserType = (isDeveloper: boolean): SectionGroup[] => {
  const availableSections = getAvailableSections(isDeveloper);
  
  return [
    {
      id: 'main',
      label: 'Главное',
      sections: availableSections.filter(section => section.group === 'main')
    },
    {
      id: 'chats',
      label: 'Чаты',
      sections: availableSections.filter(section => section.group === 'chats')
    },
    {
      id: 'tools',
      label: 'Инструменты',
      sections: availableSections.filter(section => section.group === 'tools')
    },
    {
      id: 'other',
      label: 'Другое',
      sections: availableSections.filter(section => section.group === 'other')
    }
  ].filter(group => group.sections.length > 0);
};

export const sectionGroups: SectionGroup[] = [
  {
    id: 'main',
    label: 'Главное',
    sections: platformSections.filter(section => section.group === 'main')
  },
  {
    id: 'processing',
    label: 'Обработка',
    sections: platformSections.filter(section => section.group === 'processing')
  },
  {
    id: 'chats',
    label: 'Чаты',
    sections: platformSections.filter(section => section.group === 'chats')
  },
  {
    id: 'tools',
    label: 'Инструменты',
    sections: platformSections.filter(section => section.group === 'tools')
  },
  {
    id: 'other',
    label: 'Другое',
    sections: platformSections.filter(section => section.group === 'other')
  }
];

export const getChatSection = (): SectionConfig | undefined => {
  return platformSections.find(section => section.id === 'chat');
};

export const getSectionById = (id: SectionId): SectionConfig | undefined => {
  return platformSections.find(section => section.id === id);
};

export const getSectionComponent = (id: SectionId, isDeveloper?: boolean) => {
  const section = getSectionById(id);
  if (!section) return null;
  
  return section.component;
};

// Utility functions for user-based filtering
export const getAvailableSections = (isDeveloper: boolean): SectionConfig[] => {
  return platformSections.filter(section => {
    if (section.isDeveloperOnly && !isDeveloper) return false;
    if (section.isUserOnly && isDeveloper) return false;
    return true;
  });
};

export const getUngroupedSections = (isDeveloper: boolean): SectionConfig[] => {
  const availableSections = getAvailableSections(isDeveloper);
  
  return availableSections.filter(section => 
    !section.group && (section.id === 'chat' || section.id === 'personal-chats')
  );
};

export const getAvailableSectionGroups = (isDeveloper: boolean): SectionGroup[] => {
  return getGroupsForUserType(isDeveloper);
};

export const isUserAllowedInSection = (sectionId: SectionId, isDeveloper: boolean): boolean => {
  const section = getSectionById(sectionId);
  if (!section) return false;
  
  if (section.isDeveloperOnly && !isDeveloper) return false;
  if (section.isUserOnly && isDeveloper) return false;
  
  return true;
};

export const getDefaultSectionForUser = (isDeveloper: boolean): SectionId => {
  return isDeveloper ? 'dashboard' : 'chat';
};

export const getUserTheme = (isDeveloper: boolean): string => {
  return isDeveloper ? 'theme-admin' : 'theme-default';
};