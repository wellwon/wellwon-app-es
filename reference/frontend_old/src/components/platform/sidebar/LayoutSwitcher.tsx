import React from 'react';
import { usePlatform } from '@/contexts/PlatformContext';
import { useAuth } from '@/contexts/AuthContext';
import { Badge } from '@/components/ui/badge';
import { Code, User } from 'lucide-react';

interface LayoutSwitcherProps {
  collapsed?: boolean;
}

const LayoutSwitcher: React.FC<LayoutSwitcherProps> = ({ collapsed = false }) => {
  const { isDeveloper } = usePlatform();
  const { profile } = useAuth();

  if (!profile) return null;

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1 p-2">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 border border-primary/30">
          {isDeveloper ? (
            <Code className="h-4 w-4 text-primary" />
          ) : (
            <User className="h-4 w-4 text-gray-400" />
          )}
        </div>
        <Badge variant="outline" className="text-xs">
          {isDeveloper ? 'DEV' : 'USER'}
        </Badge>
      </div>
    );
  }

  return (
    <div className="p-3 border-b border-white/10">
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/20 border border-primary/30">
          {isDeveloper ? (
            <Code className="h-5 w-5 text-primary" />
          ) : (
            <User className="h-5 w-5 text-gray-400" />
          )}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-white text-sm font-medium">
              {profile.first_name} {profile.last_name}
            </span>
            <Badge 
              variant={isDeveloper ? "default" : "secondary"} 
              className="text-xs"
            >
              {isDeveloper ? 'Разработчик' : 'Пользователь'}
            </Badge>
          </div>
          <p className="text-gray-400 text-xs">
            {isDeveloper ? 'Полный доступ к системе' : 'Стандартный доступ'}
          </p>
        </div>
      </div>
    </div>
  );
};

export default LayoutSwitcher;