import React from 'react';
import { User } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

interface ProfileIconProps {
  onClick: () => void;
  isOpen: boolean;
}

const ProfileIcon = ({ onClick, isOpen }: ProfileIconProps) => {
  const { user, profile } = useAuth();
  
  // Get user initials or fallback
  const getInitials = () => {
    if (profile?.first_name || profile?.last_name) {
      return `${profile.first_name?.[0] || ''}${profile.last_name?.[0] || ''}`.toUpperCase();
    }
    return 'П'; // Default to 'П' for Пользователь
  };

  return (
    <button
      onClick={onClick}
      className={`
        relative w-10 h-10 rounded-full transition-all duration-300
        ${isOpen 
          ? 'bg-accent-red text-white shadow-lg scale-105' 
          : 'bg-medium-gray hover:bg-light-gray text-white hover:scale-105'
        }
        border border-white/20 flex items-center justify-center
        group
      `}
    >
      {profile?.avatar_url ? (
        <img 
          src={profile.avatar_url} 
          alt="Profile" 
          className="w-full h-full rounded-full object-cover"
        />
      ) : (
        <span className="text-sm font-semibold">
          {getInitials()}
        </span>
      )}
      
      {/* Online indicator */}
      <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-green-500 border-2 border-dark-gray rounded-full"></div>
    </button>
  );
};

export default ProfileIcon;