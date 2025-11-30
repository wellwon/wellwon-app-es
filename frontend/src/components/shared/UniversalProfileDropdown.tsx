import React, { useRef, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Settings, LogOut, ArrowRight, User } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useProfileModal } from '@/contexts/ProfileModalContext';
import { useLocation, useNavigate } from 'react-router-dom';
import { useToast } from '@/hooks/use-toast';
import { getUserTypeLabel } from '@/constants/userTypes';

// Conditional platform context import to avoid errors on non-platform pages
let usePlatform: any;
try {
  const platformModule = require('@/contexts/PlatformContext');
  usePlatform = platformModule.usePlatform;
} catch {
  usePlatform = () => ({ effectiveUserType: null, forcedUserType: null });
}

interface UniversalProfileDropdownProps {
  isOpen: boolean;
  onClose: () => void;
  position?: 'top' | 'bottom';
  align?: 'left' | 'right';
  triggerRef?: React.RefObject<HTMLElement>;
}

const UniversalProfileDropdown = ({
  isOpen,
  onClose,
  position = 'bottom',
  align = 'right',
  triggerRef
}: UniversalProfileDropdownProps) => {
  const { user, profile, signOut } = useAuth();
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0 });
  const { openProfileModal } = useProfileModal();
  const { toast } = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const isOnPlatform = location.pathname.startsWith('/platform');
  
  // Safely access platform context only when on platform pages
  let effectiveUserType = profile?.is_developer ? 'developer' : 'manager';
  let forcedUserType = null;
  
  try {
    if (isOnPlatform) {
      const platformContext = usePlatform();
      effectiveUserType = platformContext.effectiveUserType;
      forcedUserType = platformContext.forcedUserType;
    }
  } catch (error) {
    // Platform context not available, use profile type
    effectiveUserType = profile?.is_developer ? 'developer' : 'manager';
  }

  const handleSignOut = async () => {
    onClose();
    // Сохраняем текущий путь для редиректа после повторного входа
    const currentPath = location.pathname;
    const { error } = await signOut();
    if (error) {
      toast({
        title: "Ошибка",
        description: "Не удалось выйти из системы",
        variant: "error",
      });
    } else {
      toast({
        title: "Успешно",
        description: "Вы вышли из системы",
        variant: "success",
      });
      // Редиректим на страницу авторизации с сохранением текущего пути
      // Это позволит вернуться обратно после повторного входа
      const redirectParam = encodeURIComponent(currentPath);
      navigate(`/auth?mode=login&redirect=${redirectParam}`);
    }
  };

  const handleGoToPlatform = () => {
    onClose();
    navigate('/platform');
  };

  const handleProfileSettings = () => {
    openProfileModal();
    onClose();
  };

  const getUserDisplayName = () => {
    // Формируем имя из first_name + last_name
    if (profile?.first_name || profile?.last_name) {
      const firstName = profile?.first_name || '';
      const lastName = profile?.last_name || '';
      return `${firstName} ${lastName}`.trim();
    }
    
    // Если ничего нет, берем email до @
    if (user?.email) {
      return user.email.split('@')[0];
    }
    
    // Последний вариант
    return 'Пользователь';
  };

  const getUserTypeLabelText = () => {
    const baseLabel = getUserTypeLabel(profile?.user_type);

    // Add emulation indicator if in test mode or forced user type
    if (isOnPlatform && forcedUserType) {
      return `${baseLabel} (эмуляция)`;
    }

    return baseLabel;
  };

  // Calculate dropdown position when open
  useEffect(() => {
    if (isOpen && triggerRef?.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const dropdownWidth = 288; // w-72 = 18rem = 288px

      let top = position === 'top'
        ? rect.top - 8 // 8px gap above trigger
        : rect.bottom + 8; // 8px gap below trigger

      let left = align === 'left'
        ? rect.left
        : rect.right - dropdownWidth;

      // Ensure dropdown stays within viewport
      if (left < 8) left = 8;
      if (left + dropdownWidth > window.innerWidth - 8) {
        left = window.innerWidth - dropdownWidth - 8;
      }

      setDropdownPosition({ top, left });
    }
  }, [isOpen, position, align, triggerRef]);

  // Close on escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const dropdownContent = (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[9998]"
        onClick={onClose}
      />

      {/* Dropdown - rendered in portal */}
      <div
        ref={dropdownRef}
        className="fixed w-72 bg-dark-gray/95 backdrop-blur-sm border border-white/10 rounded-xl shadow-2xl z-[9999] overflow-hidden"
        style={{
          top: position === 'top' ? 'auto' : dropdownPosition.top,
          bottom: position === 'top' ? `calc(100vh - ${dropdownPosition.top}px)` : 'auto',
          left: dropdownPosition.left,
        }}
      >
        {/* User Info Section */}
        <div className="p-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-gradient-to-br from-accent-red to-accent-red/80 rounded-full flex items-center justify-center text-white font-semibold">
              {profile?.avatar_url ? (
                <img
                  src={profile.avatar_url}
                  alt="Profile"
                  className="w-full h-full rounded-full object-cover"
                />
              ) : (
                <span>{getUserDisplayName()[0].toUpperCase()}</span>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-white font-semibold truncate">
                {getUserDisplayName()}
              </h3>
              <p className="text-gray-400 text-sm">
                {getUserTypeLabelText()}
              </p>
              <p className="text-gray-500 text-xs truncate">
                {user?.email}
              </p>
            </div>
          </div>
        </div>

        {/* Menu Items */}
        <div className="p-2 space-y-1">
          <button
            className="w-full flex items-center gap-3 px-3 py-2 text-white hover:bg-accent-red/20 rounded-lg transition-all duration-300"
            onClick={handleProfileSettings}
          >
            <User size={16} />
            <span className="text-sm">Настройки профиля</span>
          </button>

          <div className="border-t border-white/10 my-1"></div>

          <button
            className="w-full flex items-center gap-3 px-3 py-2 text-white hover:bg-red-500/20 rounded-lg transition-all duration-300"
            onClick={handleSignOut}
          >
            <LogOut size={16} />
            <span className="text-sm">Выйти</span>
          </button>
        </div>
      </div>
    </>
  );

  return createPortal(dropdownContent, document.body);
};

export default UniversalProfileDropdown;