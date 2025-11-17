import React from 'react';
import { useUnifiedSidebar } from '@/contexts/chat';
import { Settings, BarChart3, Users, ShoppingCart, Wrench } from 'lucide-react';

const AdminTabMenu = () => {
  const { contentType, openSidebar, closeSidebar, isOpen } = useUnifiedSidebar();

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

  return (
    <div className="h-16 bg-dark-gray border-b border-white/10 relative z-10">
      
      <div className="flex h-full relative z-10">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = isOpen && contentType === tab.id;
          
          return (
            <button
              key={tab.id}
              onClick={() => handleTabClick(tab.id)}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 border-r border-white/10 last:border-r-0 transition-all duration-300 group ${
                isActive 
                  ? 'bg-accent-gray/20 border-b-2 border-accent-gray' 
                  : 'hover:bg-white/5'
              }`}
            >
              <Icon 
                size={16} 
                className={`transition-colors duration-300 ${
                  isActive ? 'text-accent-gray' : 'text-gray-400 group-hover:text-white'
                }`}
              />
              <div className="flex flex-col items-center">
                <span className={`text-xs font-semibold transition-colors duration-300 ${
                  isActive ? 'text-accent-gray' : 'text-gray-300 group-hover:text-white'
                }`}>
                  {tab.label}
                </span>
                {tab.sublabel && (
                  <span className={`text-xs transition-colors duration-300 ${
                    isActive ? 'text-accent-gray/80' : 'text-gray-500 group-hover:text-gray-400'
                  }`}>
                    {tab.sublabel}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default AdminTabMenu;