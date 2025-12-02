import React, { useRef } from 'react';
import { useUnifiedSidebar } from '@/contexts/chat';
import { usePlatform } from '@/contexts/PlatformContext';
import { Settings, BarChart3, Users, ShoppingCart, Wrench } from 'lucide-react';

const AdminTabMenu = () => {
  const { contentType, openSidebar, closeSidebar, isOpen } = useUnifiedSidebar();
  const { isLightTheme } = usePlatform();
  const containerRef = useRef<HTMLDivElement>(null);

  const tabs = [
    {
      id: 'deal' as const,
      label: 'СДЕЛКА',
      sublabel: '',
      icon: ShoppingCart
    },
    {
      id: 'services' as const,
      label: 'УСЛУГИ',
      sublabel: '',
      icon: Wrench
    },
    {
      id: 'system-settings' as const,
      label: 'НАСТРОЙКИ',
      sublabel: '',
      icon: Settings
    },
    {
      id: 'analytics' as const,
      label: 'АНАЛИТИКА',
      sublabel: '',
      icon: BarChart3
    },
    {
      id: 'users' as const,
      label: 'ПОЛЬЗОВАТЕЛИ',
      sublabel: '',
      icon: Users
    }
  ];

  const handleTabClick = (tabId: typeof tabs[number]['id']) => {
    if (isOpen && contentType === tabId) {
      closeSidebar();
      return;
    }
    openSidebar(tabId);
  };

  // Theme-aware styles (like Declarant page)
  const theme = isLightTheme ? {
    header: 'bg-white border-gray-300 shadow-sm',
    text: {
      primary: 'text-gray-900',
      secondary: 'text-[#6b7280]',
      active: 'text-accent-gray'
    },
    button: {
      default: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100',
      active: 'bg-gray-100 text-gray-900'
    },
    border: 'border-gray-200'
  } : {
    header: 'bg-dark-gray border-white/10',
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400',
      active: 'text-accent-gray'
    },
    button: {
      default: 'text-gray-400 hover:text-white hover:bg-white/5',
      active: 'bg-accent-gray/20'
    },
    border: 'border-white/10'
  };

  return (
    <div ref={containerRef} className={`h-16 border-b relative z-10 ${theme.header}`}>

      <div className="flex h-full relative z-10 w-full overflow-x-auto scrollbar-hide">
        {/* Tabs container with horizontal scroll */}
        {tabs.map((tab, index) => {
          const Icon = tab.icon;
          const isActive = isOpen && contentType === tab.id;
          const isLast = index === tabs.length - 1;

          return (
            <button
              key={tab.id}
              onClick={() => handleTabClick(tab.id)}
              title={tab.label}
              className={`flex-shrink-0 flex items-center justify-center gap-2 px-4 py-2 ${!isLast ? `border-r ${theme.border}` : ''} transition-all duration-200 group whitespace-nowrap ${
                isActive
                  ? `${theme.button.active} border-b-2 border-accent-gray`
                  : theme.button.default
              }`}
            >
              <Icon
                size={16}
                className={`flex-shrink-0 transition-colors duration-200 ${
                  isActive ? theme.text.active : `${theme.text.secondary} group-hover:${theme.text.primary}`
                }`}
              />
              <span className={`text-xs font-semibold transition-colors duration-200 ${
                isActive ? theme.text.active : `${isLightTheme ? 'text-gray-700' : 'text-gray-300'} group-hover:${theme.text.primary}`
              }`}>
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default AdminTabMenu;