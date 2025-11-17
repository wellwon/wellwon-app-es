import React from 'react';
import { usePlatform } from '@/contexts/PlatformContext';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { useIsMobile } from '@/hooks/use-mobile';
import SidebarMain from './SidebarMain';
import SidebarChat from './SidebarChat';

const PlatformSidebar = () => {
  const { activeSection } = usePlatform();
  const { chats } = useRealtimeChatContext();
  const { isDeveloper } = usePlatform();
  const isMobile = useIsMobile();

  // На мобильных устройствах скрываем сайдбары
  if (isMobile) {
    return null;
  }

  return (
    <div className="flex h-screen">
      {/* Главное меню - цвет #2c2c33 */}
      <div style={{ backgroundColor: '#2c2c33' }}>
        <SidebarMain />
      </div>
      {/* Чат-сайдбар - цвет #232328 */}
      {activeSection === 'chat' && (
        <SidebarChat />
      )}
    </div>
  );
};

export default PlatformSidebar;