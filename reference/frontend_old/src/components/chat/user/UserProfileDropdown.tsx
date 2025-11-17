import React from 'react';
import { Button } from '@/components/ui/button';
import { Settings } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface UserProfileDropdownProps {
  isOpen: boolean;
  onClose: () => void;
}

const UserProfileDropdown = ({ isOpen, onClose }: UserProfileDropdownProps) => {
  const { toast } = useToast();

  const handleSettings = () => {
    onClose();
    toast({
      title: "Настройки",
      description: "Функция настроек в разработке",
    });
  };

  if (!isOpen) return null;

  return (
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
        </div>
      </div>
    </>
  );
};

export default UserProfileDropdown;