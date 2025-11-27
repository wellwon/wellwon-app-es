import React, { useState, useEffect } from 'react';
import * as telegramApi from '@/api/telegram';
import { GlassButton } from '@/components/design-system/GlassButton';
import { API } from '@/api/core';
import { GlassInput } from '@/components/design-system/GlassInput';
import { GlassCard } from '@/components/design-system/GlassCard';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar';
import { TelegramIcon } from '@/components/ui/TelegramIcon';
import { Crown, Edit3, Check, X, AlertCircle, Briefcase } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { logger } from '@/utils/logger';
import { avatarCache } from '@/utils/avatarCache';

interface ChatParticipantsSectionProps {
  activeChat: any;
}

interface TelegramParticipant {
  id: string;
  telegram_user_id: number;
  first_name: string | null;
  last_name: string | null;
  username: string | null;
  is_bot: boolean;
  status: string | null;
  roleLabel?: string | null;
}

interface Manager {
  user_id: string;
  first_name: string | null;
  last_name: string | null;
  avatar_url: string | null;
  role_label?: string | null;
}

export const ChatParticipantsSection: React.FC<ChatParticipantsSectionProps> = ({ activeChat }) => {
  const { toast } = useToast();
  const [telegramParticipants, setTelegramParticipants] = useState<TelegramParticipant[]>([]);
  const [managers, setManagers] = useState<Manager[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editingManagerId, setEditingManagerId] = useState<string | null>(null);
  const [editingRoleValue, setEditingRoleValue] = useState<string>('');
  const [managersAvatarsLoaded, setManagersAvatarsLoaded] = useState<Record<string, boolean>>({});

  // Preload manager avatars
  useEffect(() => {
    managers.forEach(manager => {
      if (manager.avatar_url && !avatarCache.isLoaded(manager.avatar_url)) {
        avatarCache.preload(manager.avatar_url).catch(() => {
          // Handle errors silently
        });
      }
    });
  }, [managers]);

  const handleManagerAvatarLoad = (userId: string, avatarUrl: string) => {
    avatarCache.markLoaded(avatarUrl);
    setManagersAvatarsLoaded(prev => ({ ...prev, [userId]: true }));
  };

  useEffect(() => {
    const supergroupId = activeChat?.telegram_supergroup_id;
    if (!supergroupId) {
      setTelegramParticipants([]);
      setManagers([]);
      return;
    }
    loadChatParticipants(supergroupId);
  }, [activeChat?.telegram_supergroup_id]);

  const loadChatParticipants = async (supergroupId?: string) => {
    const groupId = supergroupId || activeChat?.telegram_supergroup_id;
    if (!groupId) return;

    setLoading(true);
    try {
      // Получаем информацию о супергруппе
      const supergroupInfo = await telegramApi.getGroupInfo(Number(groupId));
      if (!supergroupInfo) return;

      // Загружаем участников Telegram (уже включает role_label)
      const members = await telegramApi.getGroupMembers(Number(groupId));
      const nonBotMembers = members.filter(m => !m.is_bot);

      // Преобразуем в формат компонента
      const participantsWithUserData: TelegramParticipant[] = nonBotMembers.map(member => ({
        id: member.id,
        telegram_user_id: member.telegram_user_id,
        first_name: member.first_name,
        last_name: member.last_name,
        username: member.username,
        is_bot: member.is_bot,
        status: member.status,
        roleLabel: (member as any).role_label || null
      }));

      setTelegramParticipants(participantsWithUserData);

      // Получаем менеджеров компании - via user API
      if (supergroupInfo?.company_id) {
        try {
          // TODO: Add company users endpoint to fetch managers
          // For now, we'll use the company users endpoint when available
          const { data: managersData } = await API.get('/users/active');
          setManagers(managersData || []);
        } catch (err) {
          logger.warn('Failed to load managers - endpoint may not be available yet', { error: err });
          setManagers([]);
        }
      }
    } catch (error) {
      logger.error('Failed to load chat participants', error);
      toast({
        title: 'Ошибка загрузки',
        description: 'Не удалось загрузить участников чата',
        variant: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const updateTelegramUserRole = async (telegramUserId: number, newRoleLabel: string) => {
    const groupId = activeChat?.telegram_supergroup_id;
    if (!groupId) return;

    try {
      const roleToSave = newRoleLabel.trim() || '';
      const success = await telegramApi.updateMemberRole(Number(groupId), telegramUserId, roleToSave);

      if (success) {
        // Обновляем локальное состояние
        setTelegramParticipants(prev =>
          prev.map(p =>
            p.telegram_user_id === telegramUserId
              ? { ...p, roleLabel: roleToSave || null }
              : p
          )
        );

        toast({
          title: 'Роль обновлена',
          description: 'Роль пользователя успешно изменена',
          variant: 'success'
        });
      } else {
        throw new Error('Update failed');
      }
    } catch (error) {
      logger.error('Failed to update telegram user role', error);
      toast({
        title: 'Ошибка обновления',
        description: 'Недостаточно прав для изменения роли',
        variant: 'error'
      });
    }

    setEditingUserId(null);
    setEditingRoleValue('');
  };

  const updateManagerRole = async (userId: string, newRoleLabel: string) => {
    try {
      const roleToSave = newRoleLabel.trim() || null;

      // Update manager role via API
      await API.patch(`/users/${userId}/profile`, { role_label: roleToSave });

      // Обновляем локальное состояние
      setManagers(prev =>
        prev.map(m =>
          m.user_id === userId
            ? { ...m, role_label: roleToSave }
            : m
        )
      );

      toast({
        title: 'Роль обновлена',
        description: 'Роль менеджера успешно изменена',
        variant: 'success'
      });
    } catch (error) {
      logger.error('Failed to update manager role', error);
      toast({
        title: 'Ошибка обновления',
        description: 'Не удалось изменить роль менеджера',
        variant: 'error'
      });
    }

    setEditingManagerId(null);
    setEditingRoleValue('');
  };

  const startEditingRole = (userId: string, currentRole: string | null, isTelegram: boolean = false) => {
    if (isTelegram) {
      setEditingUserId(userId);
    } else {
      setEditingManagerId(userId);
    }
    setEditingRoleValue(currentRole || '');
  };

  const cancelEditing = () => {
    setEditingUserId(null);
    setEditingManagerId(null);
    setEditingRoleValue('');
  };

  const saveRole = (userId: string, isTelegram: boolean = false) => {
    if (isTelegram) {
      const telegramUserId = parseInt(userId);
      updateTelegramUserRole(telegramUserId, editingRoleValue);
    } else {
      updateManagerRole(userId, editingRoleValue);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent, userId: string, isTelegram: boolean = false) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      saveRole(userId, isTelegram);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      cancelEditing();
    }
  };

  // Вспомогательные функции для отображения
  const getDisplayRole = (roleLabel?: string | null): string => {
    return roleLabel || 'Нет роли';
  };

  const getParticipantName = (participant: TelegramParticipant): string => {
    if (participant.first_name && participant.last_name) {
      return `${participant.first_name} ${participant.last_name}`;
    }
    if (participant.first_name) return participant.first_name;
    if (participant.username) return `@${participant.username}`;
    return 'Пользователь';
  };

  const getManagerName = (manager: Manager): string => {
    if (manager.first_name && manager.last_name) {
      return `${manager.first_name} ${manager.last_name}`;
    }
    if (manager.first_name) return manager.first_name;
    return 'Менеджер';
  };

  const getUserInitials = (name: string): string => {
    const words = name.split(' ').filter(Boolean);
    if (words.length >= 2) {
      return (words[0][0] + words[1][0]).toUpperCase();
    }
    return words[0]?.[0]?.toUpperCase() || 'П';
  };

  if (!activeChat || !activeChat.telegram_supergroup_id) {
    return (
      <GlassCard variant="default" padding="lg" className="text-center" hover={false}>
        <div className="text-white/60">Выберите чат для просмотра участников</div>
      </GlassCard>
    );
  }

  if (loading) {
    return (
      <GlassCard variant="default" padding="lg" className="text-center" hover={false}>
        <div className="text-white/60">Загрузка участников...</div>
      </GlassCard>
    );
  }

  return (
    <div className="space-y-4">
      {/* Telegram пользователи */}
      <GlassCard variant="default" padding="lg" hover={false}>
        <div className="flex items-center gap-2 mb-4">
          <TelegramIcon className="w-5 h-5 text-accent-red" />
          <h3 className="text-lg font-semibold text-white">Telegram пользователи</h3>
          <Badge variant="secondary" className="ml-auto bg-white/20 text-white">
            {telegramParticipants.length}
          </Badge>
        </div>
        
        <div className="space-y-2">
          {telegramParticipants.length === 0 ? (
            <div className="text-center text-white/60 py-4">
              Участники не найдены
            </div>
          ) : (
            telegramParticipants.map((participant) => (
              <div key={participant.id} className="flex items-center p-3 rounded-lg bg-[#2b2b30] hover:bg-white/10 transition-colors">
                <div className="flex items-center justify-between w-full">
                  <div className="flex items-center gap-3 flex-1">
                    <Avatar className="w-10 h-10">
                      <AvatarFallback className="bg-accent-red/20 text-accent-red border-2 border-accent-red font-medium text-sm">
                        {getUserInitials(getParticipantName(participant))}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="text-white font-medium text-sm">
                          {getParticipantName(participant)}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        {editingUserId === participant.telegram_user_id.toString() ? (
                          <div className="flex items-center gap-2 flex-1">
                            <GlassInput
                              value={editingRoleValue}
                              onChange={(e) => setEditingRoleValue(e.target.value)}
                              onKeyDown={(e) => handleKeyDown(e, participant.telegram_user_id.toString(), true)}
                              placeholder="Введите роль"
                              className="w-32 h-7 text-xs"
                              autoFocus
                            />
                            <GlassButton
                              size="icon"
                              variant="primary"
                              onClick={() => saveRole(participant.telegram_user_id.toString(), true)}
                              className="h-6 w-6"
                            >
                              <Check size={12} />
                            </GlassButton>
                            <GlassButton
                              size="icon"
                              variant="secondary"
                              onClick={cancelEditing}
                              className="h-6 w-6"
                            >
                              <X size={12} />
                            </GlassButton>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            {!participant.roleLabel ? (
                              <AlertCircle className="w-3 h-3" />
                            ) : participant.roleLabel === 'Developer' ? (
                              <Crown size={12} />
                            ) : (
                              <TelegramIcon className="w-3 h-3" />
                            )}
                            <Badge 
                              variant="secondary" 
                              className={`text-xs cursor-pointer hover:bg-white/20 flex items-center gap-1 bg-[#414145] ${
                                !participant.roleLabel ? 'text-accent-red' : ''
                              }`}
                              onClick={() => startEditingRole(participant.telegram_user_id.toString(), participant.roleLabel, true)}
                            >
                              {getDisplayRole(participant.roleLabel)}
                              <Edit3 size={10} />
                            </Badge>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </GlassCard>

      {/* Менеджеры */}
      <GlassCard variant="default" padding="lg" hover={false}>
        <div className="flex items-center gap-2 mb-4">
          <Crown size={20} className="text-accent-red" />
          <h3 className="text-lg font-semibold text-white">Менеджеры</h3>
          <Badge variant="secondary" className="ml-auto bg-white/20 text-white">
            {managers.length}
          </Badge>
        </div>
        
        <div className="space-y-2">
          {managers.length === 0 ? (
            <div className="text-center text-white/60 py-4">
              Менеджеры не назначены
            </div>
          ) : (
            managers.map((manager) => (
              <div key={manager.user_id} className="flex items-center p-3 rounded-lg bg-[#2b2b30] hover:bg-white/10 transition-colors">
                <div className="flex items-center justify-between w-full">
                  <div className="flex items-center gap-3 flex-1">
                    <Avatar className="w-10 h-10">
                      {manager.avatar_url ? (
                        <>
                          <AvatarImage 
                            src={manager.avatar_url} 
                            alt={getManagerName(manager)} 
                            onLoad={() => handleManagerAvatarLoad(manager.user_id, manager.avatar_url)}
                            loading="eager"
                            className={`transition-opacity duration-200 ${managersAvatarsLoaded[manager.user_id] ? 'opacity-100' : 'opacity-0'}`}
                          />
                          <AvatarFallback className={`
                            bg-gray-600/20 text-gray-300 border-2 border-gray-500 font-medium text-sm transition-opacity duration-200
                            ${managersAvatarsLoaded[manager.user_id] ? 'opacity-0 absolute inset-0' : 'opacity-100'}
                          `}>
                            {getUserInitials(getManagerName(manager))}
                          </AvatarFallback>
                        </>
                      ) : (
                        <AvatarFallback className="bg-gray-600/20 text-gray-300 border-2 border-gray-500 font-medium text-sm">
                          {getUserInitials(getManagerName(manager))}
                        </AvatarFallback>
                      )}
                    </Avatar>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="text-white font-medium text-sm">
                          {getManagerName(manager)}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        {editingManagerId === manager.user_id ? (
                          <div className="flex items-center gap-2 flex-1">
                            <GlassInput
                              value={editingRoleValue}
                              onChange={(e) => setEditingRoleValue(e.target.value)}
                              onKeyDown={(e) => handleKeyDown(e, manager.user_id, false)}
                              placeholder="Введите роль"
                              className="w-32 h-7 text-xs"
                              autoFocus
                            />
                            <GlassButton
                              size="icon"
                              variant="primary"
                              onClick={() => saveRole(manager.user_id)}
                              className="h-6 w-6"
                            >
                              <Check size={12} />
                            </GlassButton>
                            <GlassButton
                              size="icon"
                              variant="secondary"
                              onClick={cancelEditing}
                              className="h-6 w-6"
                            >
                              <X size={12} />
                            </GlassButton>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            {!manager.role_label ? (
                              <AlertCircle className="w-3 h-3" />
                            ) : manager.role_label === 'Developer' ? (
                              <Crown size={12} />
                            ) : (
                              <Briefcase className="w-3 h-3" />
                            )}
                            <Badge 
                              variant="secondary" 
                              className={`text-xs cursor-pointer hover:bg-white/20 flex items-center gap-1 bg-[#414145] ${
                                !manager.role_label ? 'text-accent-red' : ''
                              }`}
                              onClick={() => startEditingRole(manager.user_id, manager.role_label)}
                            >
                              {getDisplayRole(manager.role_label)}
                              <Edit3 size={10} />
                            </Badge>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </GlassCard>
    </div>
  );
};