import React, { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { User } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import UniversalProfileDropdown from '@/components/shared/UniversalProfileDropdown';

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
    // Fallback to email if profile exists but no name
    if (user?.email) {
      return user.email.split('@')[0];
    }
    return 'Гость';
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
          className="w-full h-full rounded-xl flex items-center justify-center cursor-pointer"
          onClick={() => setIsDropdownOpen(!isDropdownOpen)}
        >
          <Avatar className="w-8 h-8">
            <AvatarImage src={profile?.avatar_url} />
            <AvatarFallback className="text-xs font-medium bg-primary/20 text-primary border border-primary/40">
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
      <Button 
        variant="secondary" 
        className="w-full justify-start gap-3 h-full min-h-[60px] px-3 py-2.5 !transition-none !transform-none !hover:bg-white/5 !hover:text-gray-300 !hover:border-white/10 !hover:scale-100 !hover:transform-none"
        onClick={() => setIsDropdownOpen(!isDropdownOpen)}
      >
        <Avatar className="w-10 h-10">
          <AvatarImage src={profile?.avatar_url} />
          <AvatarFallback className="text-sm font-medium bg-primary/20 text-primary border border-primary/40">
            {getUserInitials()}
          </AvatarFallback>
        </Avatar>
        <div className="flex-1 text-left">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-medium">
              {getUserDisplayName()}
            </p>
            {profile?.user_number && (
              <span className="text-xs text-white/70 font-sans">
                ID {profile.user_number}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400">
            {profile ? (
              profile.is_developer ? 'Разработчик' : 'Менеджер'
            ) : 'Системный пользователь'}
          </p>
        </div>
      </Button>
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