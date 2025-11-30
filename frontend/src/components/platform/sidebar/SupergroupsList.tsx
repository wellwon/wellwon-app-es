// =============================================================================
// File: SupergroupsList.tsx
// Description: Supergroups list using React Query + WSE
// =============================================================================

import React from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useActiveSupergroups } from '@/hooks/useSupergroups';
import { OptimizedImage } from '@/components/chat/components/OptimizedImage';

export const SupergroupsList: React.FC = () => {
  const { user } = useAuth();
  const { data: supergroups, isLoading, isError } = useActiveSupergroups();

  if (!user?.id) {
    return null;
  }

  if (isLoading) {
    return (
      <div className="p-4 text-center">
        <span className="text-gray-400 text-sm">Загрузка...</span>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-4 text-center">
        <p className="text-red-400 text-sm">Ошибка загрузки</p>
      </div>
    );
  }

  if (!supergroups || supergroups.length === 0) {
    return (
      <div className="p-4 text-center">
        <p className="text-gray-400 text-sm">Нет супергрупп</p>
      </div>
    );
  }

  return (
    <div className="overflow-y-auto">
      {supergroups.map((supergroup) => (
        <div
          key={supergroup.telegram_group_id}
          className="p-4 border-b border-white/5 hover:bg-white/5 transition-colors cursor-pointer"
        >
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-md bg-white/10 flex items-center justify-center overflow-hidden border border-white/20">
              {supergroup.company_logo ? (
                <OptimizedImage
                  src={supergroup.company_logo}
                  alt={supergroup.title || 'Company logo'}
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="text-gray-300 text-sm font-medium">
                  {supergroup.title?.charAt(0).toUpperCase() || 'T'}
                </span>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="text-white font-medium text-sm truncate">
                {supergroup.title || 'Telegram Supergroup'}
              </h4>
              <p className="text-gray-400 text-xs">
                {supergroup.member_count || 0} участников
              </p>
            </div>
            <div className="text-right">
              <div className={`w-2 h-2 rounded-full ${
                supergroup.is_active ? 'bg-green-400' : 'bg-gray-500'
              }`} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
