import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Settings, LogOut } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { EnhancedProfileEditModal } from '@/components/shared/EnhancedProfileEditModal';

interface UserProfileDropdownProps {
  isOpen: boolean;
  onClose: () => void;
}

const UserProfileDropdown = ({ isOpen, onClose }: UserProfileDropdownProps) => {
  const { logout } = useAuth();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const handleSettings = () => {
    onClose();
    setIsSettingsOpen(true);
  };

  const handleLogout = async () => {
    onClose();
    await logout();
  };

  if (!isOpen && !isSettingsOpen) return null;

  return (
    <>
      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={onClose}
          />

          <div className="absolute bottom-full left-0 right-0 mb-2 bg-dark-gray/95 backdrop-blur-sm border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden">
            <div className="p-2 space-y-1">
              <Button
                variant="ghost"
                className="w-full justify-start gap-3 h-10 text-white hover:bg-accent-red/20 transition-all duration-300"
                onClick={handleSettings}
              >
                <Settings size={16} />
                <span className="text-sm">Настройки</span>
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start gap-3 h-10 text-white hover:bg-red-500/20 transition-all duration-300"
                onClick={handleLogout}
              >
                <LogOut size={16} />
                <span className="text-sm">Выйти</span>
              </Button>
            </div>
          </div>
        </>
      )}

      {/* Profile Settings Modal */}
      <EnhancedProfileEditModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </>
  );
};

export default UserProfileDropdown;