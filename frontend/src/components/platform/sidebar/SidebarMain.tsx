import React, { useState, useEffect } from 'react';
import { usePlatform } from '@/contexts/PlatformContext';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { SidebarUserCard } from '@/components/chat';


import CreateCompanyDialog from './CreateCompanyDialog';
import { AdminFormsModal } from '@/components/chat/components/AdminFormsModal';
import LayoutSwitcher from './LayoutSwitcher';
import { CompanyService } from '@/services/CompanyService';
import { supabase } from '@/integrations/supabase/client';
import type { Company } from '@/types/realtime-chat';

import { ChevronRight, ChevronLeft } from 'lucide-react';
import { getAvailableSectionGroups, getChatSection, getUngroupedSections, SectionConfig, SectionId } from '@/config/SectionConfig';

// Вспомогательная функция для рендеринга секции
const renderSection = (section: SectionConfig, activeSection: SectionId, setActiveSection: (id: SectionId) => void, sidebarCollapsed: boolean, chatMode: 'groups' | 'personal', setChatMode: (mode: 'groups' | 'personal') => void) => {
  const Icon = section.icon;
  const isActive = (section.id === 'chat' && activeSection === 'chat' && chatMode === 'groups') ||
    (section.id === 'personal-chats' && activeSection === 'chat' && chatMode === 'personal') ||
    (activeSection === section.id && section.id !== 'chat' && section.id !== 'personal-chats');
  
  const handleClick = () => {
    if (section.id === 'chat') {
      setActiveSection('chat');
      setChatMode('groups');
      // Dispatch event to SidebarChat
      window.dispatchEvent(new CustomEvent('chatModeChange', { detail: 'groups' }));
    } else if (section.id === 'personal-chats') {
      setActiveSection('chat');
      setChatMode('personal');
      // Dispatch event to SidebarChat
      window.dispatchEvent(new CustomEvent('chatModeChange', { detail: 'personal' }));
    } else {
      setActiveSection(section.id);
    }
  };
  
  if (sidebarCollapsed) {
    return (
      <div key={section.id} onClick={handleClick} className="relative flex justify-center cursor-pointer" title={section.label}>
        <div className={`
          w-12 h-12 flex items-center justify-center rounded-xl
          backdrop-blur-sm border
          ${isActive ? 'bg-medium-gray/80 border-accent-red text-accent-red' : 'bg-medium-gray/60 text-gray-400 border-white/10 hover:text-white hover:bg-medium-gray/80 hover:border-white/20'}
        `}>
          <Icon size={20} />
        </div>
        {section.badge && (
          <Badge variant="destructive" className="absolute -top-1 -right-1 w-5 h-5 p-0 text-xs flex items-center justify-center bg-accent-red border-0 rounded-full text-white">
            {section.badge}
          </Badge>
        )}
      </div>
    );
  }

  return (
    <div key={section.id} onClick={handleClick} className={`
      w-full h-12 flex items-center justify-between px-3 rounded-lg cursor-pointer
      ${isActive ? 'bg-accent-red/20 text-white border border-accent-red/30' : 'text-gray-300 hover:text-white hover:bg-white/10'}
    `}>
      <div className="flex items-center gap-3">
        <Icon size={20} />
        <span className="font-medium text-sm">{section.label}</span>
      </div>
      {section.badge && (
        <Badge variant="destructive" className="h-5 w-5 p-0 text-xs flex items-center justify-center bg-accent-red border-0">
          {section.badge}
        </Badge>
      )}
    </div>
  );
};
const SidebarMain = () => {
  const {
    activeSection,
    setActiveSection,
    sidebarCollapsed,
    toggleSidebar,
    availableSections,
    isDeveloper,
  } = usePlatform();
  const realtimeChat = useRealtimeChatContext();
  const chats = realtimeChat?.chats || [];
  const { user, profile } = useAuth();
  
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [chatMode, setChatMode] = useState<'groups' | 'personal'>('groups');

  // Sync chatMode from SidebarChat on component mount
  useEffect(() => {
    const handleChatModeSync = (event: CustomEvent<'groups' | 'personal'>) => {
      const mode = event.detail;
      setChatMode(mode === 'groups' ? 'groups' : 'personal');
    };

    window.addEventListener('chatModeSync', handleChatModeSync as EventListener);
    return () => window.removeEventListener('chatModeSync', handleChatModeSync as EventListener);
  }, []);

  // Company loading is now handled entirely by CompanySelector component

  const handleCreateRequest = () => {
    setShowCreateDialog(true);
  };

  const handleConfirmCreate = () => {
    setShowCreateDialog(false);
    setShowCreateForm(true);
  };

  const handleCompanyCreated = () => {
    setShowCreateForm(false);
    // Company will be automatically selected by the form modal
  };

  // Get available section groups for current user
  const availableGroups = getAvailableSectionGroups(isDeveloper);
  
  // Get ungrouped sections for current user
  const ungroupedSections = getUngroupedSections(isDeveloper);

  // Функция подсчёта непрочитанных сообщений
  const getTotalUnreadCount = () => {
    if (!chats || chats.length === 0) return 0;
    return chats.reduce((total, chat) => {
      const unreadCount = chat.unread_count || 0;
      return total + unreadCount;
    }, 0);
  };

  // Получаем unread count и показываем только если больше 0
  const unreadCount = getTotalUnreadCount();
  const shouldShowBadge = unreadCount > 0;

  // Добавляем бейджи для ungrouped секций
  const ungroupedSectionsWithBadges = ungroupedSections.map(section => ({
    ...section,
    badge: (section.id === 'chat' || section.id === 'personal-chats') && shouldShowBadge ? unreadCount : section.badge
  }));

  // Добавляем бейджи для секций в группах
  const groupsWithBadges = availableGroups.map(group => ({
    ...group,
    sections: group.sections.map(section => ({
      ...section,
      badge: (section.id === 'chat' || section.id === 'personal-chats') && shouldShowBadge ? unreadCount : section.badge
    }))
  }));
  return <div
    className="h-screen backdrop-blur-sm border-r border-white/10 flex flex-col"
    style={{
      backgroundColor: '#232328',
      width: sidebarCollapsed ? '80px' : '272px'
    }}
  >
      {/* Header с логотипом */}
      <div className={`h-16 flex items-center px-4 border-b border-white/10 ${sidebarCollapsed ? 'justify-center' : 'justify-between'}`}>
        {!sidebarCollapsed && <div className="relative">
            <span className="text-accent-red font-black text-2xl">Well</span>
            <span className="text-white font-black text-2xl">Won</span>
            <span className="text-white text-2xl font-extrabold"> App</span>
            <div className="absolute -bottom-0.5 left-0 w-10 h-0.5 bg-accent-red"></div>
          </div>}
        
        <Button variant="ghost" size="icon" onClick={toggleSidebar} className="text-gray-400 hover:text-white hover:bg-white/10 rounded-lg h-8 w-8">
          {sidebarCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </Button>
      </div>

      {/* Navigation */}
      <div className="p-3">
        <div className={sidebarCollapsed ? 'space-y-3' : 'space-y-4'}>
          {/* Ungrouped sections - вверху без заголовка */}
          {ungroupedSectionsWithBadges.length > 0 && (
            <div className={sidebarCollapsed ? 'space-y-2 mb-4' : 'space-y-1 mb-6'}>
              {ungroupedSectionsWithBadges.map(section => 
                renderSection(section, activeSection, setActiveSection, sidebarCollapsed, chatMode, setChatMode)
              )}
            </div>
          )}

          {/* Группы секций */}
          {groupsWithBadges.map(group => <div key={group.id} className={sidebarCollapsed ? 'space-y-2' : 'space-y-3'}>
              {/* Заголовок группы - только когда не свернуто */}
              {!sidebarCollapsed && <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-3">
                  {group.label}
                </div>}
              
              {/* Секции группы */}
              <div className={sidebarCollapsed ? 'space-y-2' : 'space-y-1'}>
                {group.sections.map(section => renderSection(section, activeSection, setActiveSection, sidebarCollapsed, chatMode, setChatMode))}
              </div>
            </div>)}
        </div>
      </div>



      {/* User Profile - внизу */}
      <div className="border-t border-white/10 mt-auto flex items-stretch px-2.5 py-2.5 min-h-24">
        <SidebarUserCard collapsed={sidebarCollapsed} />
      </div>
      
      {/* Create Company Dialog */}
      <CreateCompanyDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onConfirm={handleConfirmCreate}
      />
      
      <AdminFormsModal
        isOpen={showCreateForm}
        onClose={() => setShowCreateForm(false)}
        formType="company-registration"
        onSuccess={handleCompanyCreated}
      />
    </div>;
};
export default SidebarMain;