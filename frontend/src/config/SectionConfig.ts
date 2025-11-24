import { lazy } from 'react';
import {
  LucideIcon,
  LayoutDashboard,
  MessageSquare,
  MessagesSquare,
  Kanban,
  Contact,
  Shield,
  MessageCircle,
  Wrench,
  Building2,
  Settings,
  Send
} from 'lucide-react';

// Lazy load section components
const AdminDashboardContent = lazy(() => import('@/components/platform/sections/dashboard/AdminDashboardContent'));
const ChatContent = lazy(() => import('@/components/chat/ChatContent'));
const AdminKanbanContent = lazy(() => import('@/components/platform/sections/kanban/AdminKanbanContent'));
const AdminContactsContent = lazy(() => import('@/components/platform/sections/contacts/AdminContactsContent'));
const AdminCompaniesContent = lazy(() => import('@/components/platform/sections/companies/AdminCompaniesContent'));
const AdminModerationContent = lazy(() => import('@/components/platform/sections/moderation/AdminModerationContent'));
const AdminChatSettingsContent = lazy(() => import('@/components/platform/sections/chat-settings/AdminChatSettingsContent'));
const TelegramManagementContent = lazy(() => import('@/components/platform/sections/telegram/TelegramManagementContent'));
const AdminSettingsContent = lazy(() => import('@/components/platform/sections/settings/AdminSettingsContent'));

export type SectionId =
  | 'dashboard'
  | 'settings'
  | 'chat'
  | 'personal-chats'
  | 'kanban'
  | 'contacts'
  | 'companies'
  | 'moderation'
  | 'chat-settings'
  | 'telegram';

export interface SectionConfig {
  id: SectionId;
  label: string;
  icon: LucideIcon;
  component: React.ComponentType<any>;
  badge?: number | null;
  description?: string;
  group?: 'main' | 'chats' | 'tools' | 'other';
  isDeveloperOnly?: boolean;  // Controls developer-only UI access
}

export interface SectionGroup {
  id: string;
  label: string;
  sections: SectionConfig[];
}

export const platformSections: SectionConfig[] = [
  // ──────────────────────────────────────────────────────────────────────
  // DEVELOPER-ONLY SECTIONS
  // ──────────────────────────────────────────────────────────────────────

  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: LayoutDashboard,
    component: AdminDashboardContent,
    group: 'main',
    description: 'Platform overview and analytics',
    isDeveloperOnly: true,  // DEVELOPER ONLY
  },

  {
    id: 'moderation',
    label: 'Moderation',
    icon: Shield,
    component: AdminModerationContent,
    group: 'tools',
    description: 'Chat and content moderation',
    isDeveloperOnly: true,  // DEVELOPER ONLY
  },

  {
    id: 'chat-settings',
    label: 'Chat Settings',
    icon: MessageCircle,
    component: AdminChatSettingsContent,
    group: 'chats',
    description: 'Chat configuration and settings',
    isDeveloperOnly: true,  // DEVELOPER ONLY
  },

  {
    id: 'telegram',
    label: 'Telegram',
    icon: Send,
    component: TelegramManagementContent,
    group: 'chats',
    description: 'Telegram integration management',
    isDeveloperOnly: true,  // DEVELOPER ONLY
  },

  // ──────────────────────────────────────────────────────────────────────
  // UNIVERSAL SECTIONS (All users)
  // ──────────────────────────────────────────────────────────────────────

  {
    id: 'chat',
    label: 'Group Chats',
    icon: MessagesSquare,
    component: ChatContent,
    description: 'Group chats with clients',
  },

  {
    id: 'personal-chats',
    label: 'Personal Chats',
    icon: MessageSquare,
    component: ChatContent,
    description: 'Personal chats with clients',
  },

  {
    id: 'kanban',
    label: 'Kanban',
    icon: Kanban,
    component: AdminKanbanContent,
    group: 'main',
    description: 'Task and project management',
  },

  {
    id: 'contacts',
    label: 'Contacts',
    icon: Contact,
    component: AdminContactsContent,
    group: 'main',
    description: 'Contact and client management',
  },

  {
    id: 'companies',
    label: 'Companies',
    icon: Building2,
    component: AdminCompaniesContent,
    group: 'main',
    description: 'Company and partner management',
  },

  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    component: AdminSettingsContent,
    group: 'other',
    description: 'System settings',
  },
];

// ─────────────────────────────────────────────────────────────────────────
// HELPER FUNCTIONS
// ─────────────────────────────────────────────────────────────────────────

/**
 * Get sections available to user based on developer status
 * @param isDeveloper - Whether user is a developer
 */
export const getAvailableSections = (isDeveloper: boolean): SectionConfig[] => {
  return platformSections.filter(section => {
    // Filter out developer-only sections for non-developers
    if (section.isDeveloperOnly && !isDeveloper) return false;
    return true;
  });
};

/**
 * Get ungrouped sections (chats)
 */
export const getUngroupedSections = (isDeveloper: boolean): SectionConfig[] => {
  const availableSections = getAvailableSections(isDeveloper);
  return availableSections.filter(
    section => !section.group && (section.id === 'chat' || section.id === 'personal-chats')
  );
};

/**
 * Get section groups for user
 */
export const getAvailableSectionGroups = (isDeveloper: boolean): SectionGroup[] => {
  const availableSections = getAvailableSections(isDeveloper);

  return [
    {
      id: 'main',
      label: 'Main',
      sections: availableSections.filter(section => section.group === 'main'),
    },
    {
      id: 'chats',
      label: 'Chats',
      sections: availableSections.filter(section => section.group === 'chats'),
    },
    {
      id: 'tools',
      label: 'Tools',
      sections: availableSections.filter(section => section.group === 'tools'),
    },
    {
      id: 'other',
      label: 'Other',
      sections: availableSections.filter(section => section.group === 'other'),
    },
  ].filter(group => group.sections.length > 0);
};

/**
 * Check if user can access section
 */
export const isUserAllowedInSection = (sectionId: SectionId, isDeveloper: boolean): boolean => {
  const section = getSectionById(sectionId);
  if (!section) return false;

  // Deny access to developer-only sections for non-developers
  if (section.isDeveloperOnly && !isDeveloper) return false;

  return true;
};

/**
 * Get default section for user based on role
 */
export const getDefaultSectionForUser = (isDeveloper: boolean): SectionId => {
  return isDeveloper ? 'dashboard' : 'chat';
};

/**
 * Get theme for user based on role
 */
export const getUserTheme = (isDeveloper: boolean): string => {
  return isDeveloper ? 'theme-admin' : 'theme-default';
};

/**
 * Get section by ID
 */
export const getSectionById = (id: SectionId): SectionConfig | undefined => {
  return platformSections.find(section => section.id === id);
};

/**
 * Get chat section
 */
export const getChatSection = (): SectionConfig | undefined => {
  return platformSections.find(section => section.id === 'chat');
};
