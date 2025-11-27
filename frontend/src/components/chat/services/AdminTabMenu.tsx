import React, { useState, useEffect, useRef, useLayoutEffect } from 'react';
import { useUnifiedSidebar } from '@/contexts/chat';
import { usePlatform } from '@/contexts/PlatformContext';
import { Settings, BarChart3, Users, ShoppingCart, Wrench, Sun, Moon } from 'lucide-react';

const AdminTabMenu = () => {
  const { contentType, openSidebar, closeSidebar, isOpen } = useUnifiedSidebar();
  const { isLightTheme, toggleTheme } = usePlatform();
  const [isCompact, setIsCompact] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const tabsRef = useRef<HTMLDivElement>(null);

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

  // Check if tabs should be compact (icons only)
  // Using useLayoutEffect to prevent flash of wrong layout
  useLayoutEffect(() => {
    const checkWidth = () => {
      if (containerRef.current) {
        // Get available width for tabs (container minus theme button 64px)
        const containerWidth = containerRef.current.offsetWidth;
        const availableForTabs = containerWidth - 64; // 64px for theme toggle
        // Each tab with text needs ~110px minimum, with icon only ~50px
        // 5 tabs * 110px = 550px minimum for text mode
        const needsCompact = availableForTabs < 500;
        setIsCompact(needsCompact);
      }
    };

    // Initial check - run synchronously
    checkWidth();

    // Use ResizeObserver for container size changes
    const resizeObserver = new ResizeObserver(() => {
      checkWidth();
    });

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

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
    <div ref={containerRef} className={`h-16 border-b relative z-10 overflow-hidden ${theme.header}`}>

      <div className="flex h-full relative z-10 w-full">
        {/* Tabs container - takes remaining space */}
        <div className="flex flex-1 min-w-0 overflow-hidden">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = isOpen && contentType === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => handleTabClick(tab.id)}
                title={tab.label}
                className={`flex-1 min-w-0 flex items-center justify-center gap-2 ${isCompact ? 'px-1' : 'px-3'} py-2 border-r ${theme.border} transition-all duration-200 group overflow-hidden ${
                  isActive
                    ? `${theme.button.active} border-b-2 border-accent-gray`
                    : theme.button.default
                }`}
              >
                <Icon
                  size={isCompact ? 20 : 16}
                  className={`flex-shrink-0 transition-colors duration-200 ${
                    isActive ? theme.text.active : `${theme.text.secondary} group-hover:${theme.text.primary}`
                  }`}
                />
                {!isCompact && (
                  <span className={`text-xs font-semibold transition-colors duration-200 truncate ${
                    isActive ? theme.text.active : `${isLightTheme ? 'text-gray-700' : 'text-gray-300'} group-hover:${theme.text.primary}`
                  }`}>
                    {tab.label}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Theme toggle button - fixed width, always visible */}
        <button
          onClick={toggleTheme}
          className={`w-16 flex-shrink-0 flex items-center justify-center border-l ${theme.border} transition-all duration-200 ${theme.button.default}`}
          aria-label={isLightTheme ? "Переключить на тёмную тему" : "Переключить на светлую тему"}
        >
          {isLightTheme ? <Moon size={18} /> : <Sun size={18} />}
        </button>
      </div>
    </div>
  );
};

export default AdminTabMenu;