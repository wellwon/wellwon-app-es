// =============================================================================
// Platform Pro Sidebar
// =============================================================================

import React from 'react';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { usePlatformPro } from '@/contexts/PlatformProContext';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { useAuth } from '@/contexts/AuthContext';

const PlatformProSidebar: React.FC = () => {
  const {
    activeSection,
    setActiveSection,
    sidebarCollapsed,
    toggleSidebar,
    availableSections,
  } = usePlatformPro();

  const { profile, user } = useAuth();

  // Always dark theme for Pro sidebar
  const theme = {
    sidebar: 'bg-[#232328] border-gray-700',
    header: 'border-gray-700',
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400',
    },
    button: {
      default: 'text-gray-300 hover:text-white hover:bg-white/10',
      active: 'bg-accent-red/20 text-accent-red border border-accent-red/30',
    },
    profile: 'bg-white/5 hover:bg-white/10',
  };

  const getUserDisplayName = () => {
    if (profile?.first_name || profile?.last_name) {
      return `${profile.first_name || ''} ${profile.last_name || ''}`.trim();
    }
    if (user?.email) {
      return user.email.split('@')[0];
    }
    return 'Developer';
  };

  const getUserInitials = () => {
    if (profile?.first_name || profile?.last_name) {
      return `${profile.first_name?.[0] || ''}${profile.last_name?.[0] || ''}`.toUpperCase();
    }
    return 'D';
  };

  return (
    <div
      className={`
        ${sidebarCollapsed ? 'w-[60px]' : 'w-60'}
        border-r flex flex-col h-screen transition-all duration-300
        ${theme.sidebar}
      `}
    >
      {/* Header with logo */}
      <div
        className={`h-16 flex items-center ${
          sidebarCollapsed ? 'justify-center' : 'justify-between px-4'
        } border-b ${theme.header}`}
      >
        {/* Logo - shown only when expanded */}
        {!sidebarCollapsed && (
          <div className="relative">
            <span className="text-accent-red font-black text-xl">Well</span>
            <span className="text-white font-black text-xl">Won</span>
            <span className="text-white text-xl font-extrabold"> Pro</span>
            <div className="absolute -bottom-0.5 left-0 w-10 h-0.5 bg-accent-red"></div>
          </div>
        )}

        {/* Toggle button */}
        <button
          onClick={toggleSidebar}
          className={`h-8 w-8 p-0 rounded-lg transition-colors flex items-center justify-center ${theme.button.default}`}
          aria-label={sidebarCollapsed ? 'Развернуть сайдбар' : 'Свернуть сайдбар'}
        >
          {sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto py-4 px-3">
        <div className="space-y-3">
          {/* Group header - only when expanded */}
          {!sidebarCollapsed && (
            <div className={`text-xs font-semibold uppercase tracking-wider px-3 ${theme.text.secondary}`}>
              Pro Модули
            </div>
          )}

          <div className={sidebarCollapsed ? 'space-y-2' : 'space-y-1'}>
            {availableSections.map((section) => {
              const Icon = section.icon;
              const isActive = activeSection === section.id;

              if (sidebarCollapsed) {
                // Compact version - icon only
                return (
                  <div
                    key={section.id}
                    className="relative flex justify-center cursor-pointer"
                    title={section.label}
                    onClick={() => setActiveSection(section.id)}
                  >
                    <div
                      className={`
                        w-12 h-12 flex items-center justify-center rounded-xl transition-all duration-200
                        ${
                          isActive
                            ? 'bg-accent-red/20 border border-accent-red/30'
                            : 'hover:bg-white/10'
                        }
                      `}
                    >
                      <Icon
                        size={20}
                        className={isActive ? 'text-accent-red' : 'text-gray-400'}
                      />
                    </div>
                  </div>
                );
              }

              // Full version - icon + text
              return (
                <div
                  key={section.id}
                  className={`
                    flex items-center px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200
                    ${
                      isActive
                        ? `${theme.button.active} shadow-sm`
                        : theme.button.default
                    }
                  `}
                  onClick={() => setActiveSection(section.id)}
                >
                  <Icon size={20} className="mr-3" />
                  <span className="font-medium text-sm">{section.label}</span>
                  {section.badge !== undefined && section.badge !== null && (
                    <span className="ml-auto bg-accent-red text-white text-xs px-2 py-0.5 rounded-full">
                      {section.badge}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* User Profile - at bottom */}
      <div className={`border-t p-3 ${theme.header}`}>
        <div
          className={`flex ${
            sidebarCollapsed ? 'justify-center' : 'items-center gap-3'
          } p-2 rounded-lg cursor-pointer ${theme.profile}`}
        >
          <Avatar className="h-9 w-9">
            {profile?.avatar_url ? (
              <img src={profile.avatar_url} alt="Profile" className="w-full h-full object-cover" />
            ) : (
              <AvatarFallback className="bg-accent-red/20 text-accent-red font-semibold text-sm">
                {getUserInitials()}
              </AvatarFallback>
            )}
          </Avatar>

          {/* Text - only when expanded */}
          {!sidebarCollapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{getUserDisplayName()}</p>
              <p className="text-xs text-gray-400 truncate">Developer</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PlatformProSidebar;
