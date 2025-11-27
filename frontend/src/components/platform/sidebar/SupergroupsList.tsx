import React, { useState, useEffect } from 'react';
import * as telegramApi from '@/api/telegram';
import { useAuth } from '@/contexts/AuthContext';

import { OptimizedImage } from '@/components/chat/components/OptimizedImage';
import { logger } from '@/utils/logger';

import type { TelegramSupergroup } from '@/types/chat';

export const SupergroupsList: React.FC = () => {
  const { user } = useAuth();
  const [supergroups, setSupergroups] = useState<TelegramSupergroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadSupergroups = async () => {
      if (!user?.id) return;

      try {
        setLoading(true);
        setError(null);
        
        // Для разработчиков загружаем все супергруппы, для обычных пользователей - только их компании
        const data = await telegramApi.getAllSupergroups();
        setSupergroups(data);
        
        logger.info('Loaded all supergroups', { 
          userId: user.id,
          count: data.length 
        });
      } catch (err) {
        logger.error('Failed to load supergroups', err, { 
          userId: user.id 
        });
        setError('Ошибка загрузки');
      } finally {
        setLoading(false);
      }
    };

    loadSupergroups();
  }, [user?.id]);

  if (loading) {
    return (
      <div className="p-4 text-center">
        <span className="text-gray-400 text-sm">Загрузка...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-center">
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  if (supergroups.length === 0) {
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
          key={supergroup.id}
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