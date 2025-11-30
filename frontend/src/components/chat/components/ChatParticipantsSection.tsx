// =============================================================================
// File: ChatParticipantsSection.tsx
// Description: Chat participants section using React Query + WSE
// =============================================================================

import React, { useState, useEffect } from 'react';
import { useTelegramMembers, useUpdateMemberRole } from '@/hooks/telegram';
import { GlassButton } from '@/components/design-system/GlassButton';
import { GlassInput } from '@/components/design-system/GlassInput';
import { GlassCard } from '@/components/design-system/GlassCard';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar';
import { TelegramIcon } from '@/components/ui/TelegramIcon';
import { Crown, Edit3, Check, X, AlertCircle, Briefcase, Shield, Star } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
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

export const ChatParticipantsSection: React.FC<ChatParticipantsSectionProps> = ({ activeChat }) => {
  const { toast } = useToast();
  const groupId = activeChat?.telegram_supergroup_id ? Number(activeChat.telegram_supergroup_id) : null;

  // React Query hooks
  const { members, isLoading } = useTelegramMembers(groupId);
  const updateRoleMutation = useUpdateMemberRole();

  // UI State
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editingRoleValue, setEditingRoleValue] = useState<string>('');

  // Filter out bots and map to component format
  const telegramParticipants: TelegramParticipant[] = members
    .filter(m => !m.is_bot)
    .map(member => ({
      id: member.id,
      telegram_user_id: member.telegram_user_id,
      first_name: member.first_name,
      last_name: member.last_name,
      username: member.username,
      is_bot: member.is_bot,
      status: member.status,
      roleLabel: (member as any).role_label || null
    }));

  const updateTelegramUserRole = async (telegramUserId: number, newRoleLabel: string) => {
    if (!groupId) return;

    try {
      const roleToSave = newRoleLabel.trim() || '';
      await updateRoleMutation.mutateAsync({
        groupId,
        userId: telegramUserId,
        role: roleToSave,
      });

      toast({
        title: 'Роль обновлена',
        description: 'Роль пользователя успешно изменена',
        variant: 'success'
      });
    } catch (error) {
      toast({
        title: 'Ошибка обновления',
        description: 'Недостаточно прав для изменения роли',
        variant: 'error'
      });
    }

    setEditingUserId(null);
    setEditingRoleValue('');
  };

  const startEditingRole = (userId: string, currentRole: string | null) => {
    setEditingUserId(userId);
    setEditingRoleValue(currentRole || '');
  };

  const cancelEditing = () => {
    setEditingUserId(null);
    setEditingRoleValue('');
  };

  const saveRole = (userId: string) => {
    const telegramUserId = parseInt(userId);
    updateTelegramUserRole(telegramUserId, editingRoleValue);
  };

  const handleKeyDown = (e: React.KeyboardEvent, userId: string) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      saveRole(userId);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      cancelEditing();
    }
  };

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

  if (isLoading) {
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
                        {/* Telegram Admin Status Badge */}
                        {participant.status === 'creator' && (
                          <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
                            <Star size={10} className="mr-0.5" />
                            Владелец
                          </Badge>
                        )}
                        {participant.status === 'administrator' && (
                          <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 bg-blue-500/20 text-blue-400 border border-blue-500/30">
                            <Shield size={10} className="mr-0.5" />
                            Админ
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        {editingUserId === participant.telegram_user_id.toString() ? (
                          <div className="flex items-center gap-2 flex-1">
                            <GlassInput
                              value={editingRoleValue}
                              onChange={(e) => setEditingRoleValue(e.target.value)}
                              onKeyDown={(e) => handleKeyDown(e, participant.telegram_user_id.toString())}
                              placeholder="Введите роль"
                              className="w-32 h-7 text-xs"
                              autoFocus
                            />
                            <GlassButton
                              size="icon"
                              variant="primary"
                              onClick={() => saveRole(participant.telegram_user_id.toString())}
                              disabled={updateRoleMutation.isPending}
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
                              onClick={() => startEditingRole(participant.telegram_user_id.toString(), participant.roleLabel)}
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
    </div>
  );
};
