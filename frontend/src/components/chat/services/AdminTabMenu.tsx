import React, { useState, useEffect, useRef } from 'react';
import { useUnifiedSidebar } from '@/contexts/chat';
import { usePlatform } from '@/contexts/PlatformContext';
import { Settings, BarChart3, Users, ShoppingCart, Wrench, Sun, Moon } from 'lucide-react';

const AdminTabMenu = () => {
  const { contentType, openSidebar, closeSidebar, isOpen } = useUnifiedSidebar();
  const { isLightTheme, toggleTheme } = usePlatform();
  const [isCompact, setIsCompact] = useState(false);
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
    <div className={`h-16 border-b relative z-10 ${theme.header}`}>

      <div className="flex h-full relative z-10">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = isOpen && contentType === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => handleTabClick(tab.id)}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 border-r ${theme.border} transition-all duration-300 group ${
                isActive
                  ? `${theme.button.active} border-b-2 border-accent-gray`
                  : theme.button.default
              }`}
            >
              <Icon
                size={16}
                className={`transition-colors duration-300 ${
                  isActive ? theme.text.active : `${theme.text.secondary} group-hover:${theme.text.primary}`
                }`}
              />
              <div className="flex flex-col items-center">
                <span className={`text-xs font-semibold transition-colors duration-300 ${
                  isActive ? theme.text.active : `${isLightTheme ? 'text-gray-700' : 'text-gray-300'} group-hover:${theme.text.primary}`
                }`}>
                  {tab.label}
                </span>
                {tab.sublabel && (
                  <span className={`text-xs transition-colors duration-300 ${
                    isActive ? 'text-accent-gray/80' : `${theme.text.secondary} group-hover:${isLightTheme ? 'text-gray-600' : 'text-gray-400'}`
                  }`}>
                    {tab.sublabel}
                  </span>
                )}
              </div>
            </button>
          );
        })}

        {/* Theme toggle button */}
        <button
          onClick={toggleTheme}
          className={`w-16 flex-shrink-0 flex items-center justify-center transition-all duration-300 ${theme.button.default}`}
          aria-label={isLightTheme ? "Переключить на тёмную тему" : "Переключить на светлую тему"}
        >
          {isLightTheme ? <Moon size={18} /> : <Sun size={18} />}
        </button>
      </div>
    </div>
  );
};

export default AdminTabMenu;