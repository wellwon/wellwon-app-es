import React, { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { User } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import UniversalProfileDropdown from '@/components/shared/UniversalProfileDropdown';
import { getUserTypeLabel } from '@/constants/userTypes';

interface SidebarUserCardProps {
  collapsed?: boolean;
}

const SidebarUserCard = ({ collapsed = false }: SidebarUserCardProps) => {
  const { user, profile } = useAuth();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  
  const getUserDisplayName = () => {
    if (profile?.first_name || profile?.last_name) {
      return `${profile.first_name || ''} ${profile.last_name || ''}`.trim();
    }
    // Fallback to username if no name
    if (profile?.username) {
      return profile.username;
    }
    if (user?.username) {
      return user.username;
    }
    // Last resort fallback
    if (user?.email) {
      return user.email.split('@')[0];
    }
    return 'Гость';
  };

  const getUserTypeLabelText = () => {
    return getUserTypeLabel(profile?.user_type);
  };

  const getUserInitials = () => {
    if (profile?.first_name || profile?.last_name) {
      return `${profile.first_name?.[0] || ''}${profile.last_name?.[0] || ''}`.toUpperCase();
    }
    return 'Г';
  };
  
  if (collapsed) {
    return (
      <div className="relative w-full">
        <div
          className="flex justify-center p-2 rounded-lg cursor-pointer bg-white/5 hover:bg-white/10"
          onClick={() => setIsDropdownOpen(!isDropdownOpen)}
        >
          <Avatar className="h-9 w-9">
            <AvatarImage src={profile?.avatar_url} />
            <AvatarFallback className="flex h-full w-full items-center justify-center rounded-full bg-accent-red/20 text-accent-red font-semibold text-sm">
              {getUserInitials()}
            </AvatarFallback>
          </Avatar>
        </div>
        <UniversalProfileDropdown
          isOpen={isDropdownOpen}
          onClose={() => setIsDropdownOpen(false)}
          position="top"
          align="left"
        />
      </div>
    );
  }

  return (
    <div className="relative w-full">
      <div
        className="w-full flex items-center gap-3 p-2 rounded-lg cursor-pointer bg-white/5 hover:bg-white/10"
        onClick={() => setIsDropdownOpen(!isDropdownOpen)}
      >
        <Avatar className="h-10 w-10 shrink-0">
          <AvatarImage src={profile?.avatar_url} />
          <AvatarFallback className="flex h-full w-full items-center justify-center rounded-full bg-accent-red/20 text-accent-red font-semibold text-sm">
            {getUserInitials()}
          </AvatarFallback>
        </Avatar>
        <div className="flex-1 min-w-0 text-left">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-medium text-white truncate">
              {getUserDisplayName()}
            </p>
            {profile?.user_number && (
              <span className="text-xs text-white/70 font-sans shrink-0">
                ID {profile.user_number}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 truncate">
            {profile ? getUserTypeLabelText() : 'Системный пользователь'}
          </p>
        </div>
      </div>
      <UniversalProfileDropdown
        isOpen={isDropdownOpen}
        onClose={() => setIsDropdownOpen(false)}
        position="top"
        align="left"
      />
    </div>
  );
};

export default SidebarUserCard;