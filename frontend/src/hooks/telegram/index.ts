// =============================================================================
// File: src/hooks/telegram/index.ts
// Description: Telegram hooks with React Query + WSE integration
// Pattern: TkDodo's "Using WebSockets with React Query"
// =============================================================================

import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as telegramApi from '@/api/telegram';
import type { TelegramSupergroup, TelegramGroupMember } from '@/api/telegram';
import { logger } from '@/utils/logger';

// -----------------------------------------------------------------------------
// Query Keys
// -----------------------------------------------------------------------------

export const telegramKeys = {
  all: ['telegram'] as const,
  supergroups: () => [...telegramKeys.all, 'supergroups'] as const,
  supergroup: (id: number) => [...telegramKeys.supergroups(), id] as const,
  members: (groupId: number) => [...telegramKeys.supergroup(groupId), 'members'] as const,
  groupInfo: (groupId: number) => [...telegramKeys.supergroup(groupId), 'info'] as const,
};

// -----------------------------------------------------------------------------
// useTelegramGroup - Single group info with WSE
// -----------------------------------------------------------------------------

export function useTelegramGroup(groupId: number | null) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!groupId) return;

    const handleGroupUpdate = (event: CustomEvent) => {
      const detail = event.detail;
      if (detail?.groupId === groupId || detail?.telegram_group_id === groupId) {
        logger.debug('WSE: Telegram group update, invalidating', { groupId });
        queryClient.invalidateQueries({ queryKey: telegramKeys.supergroup(groupId) });
      }
    };

    window.addEventListener('supergroupUpdated', handleGroupUpdate as EventListener);
    window.addEventListener('telegramGroupUpdated', handleGroupUpdate as EventListener);

    return () => {
      window.removeEventListener('supergroupUpdated', handleGroupUpdate as EventListener);
      window.removeEventListener('telegramGroupUpdated', handleGroupUpdate as EventListener);
    };
  }, [groupId, queryClient]);

  const query = useQuery({
    queryKey: groupId ? telegramKeys.groupInfo(groupId) : ['disabled'],
    queryFn: () => telegramApi.getGroupInfo(groupId!),
    enabled: !!groupId,
    staleTime: 5 * 60 * 1000,
  });

  return {
    group: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

// -----------------------------------------------------------------------------
// useTelegramMembers - Group members with WSE
// -----------------------------------------------------------------------------

export function useTelegramMembers(groupId: number | null) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!groupId) return;

    const handleMemberChange = (event: CustomEvent) => {
      const detail = event.detail;
      if (detail?.groupId === groupId || detail?.telegram_group_id === groupId) {
        logger.debug('WSE: Telegram member change, invalidating', { groupId });
        queryClient.invalidateQueries({ queryKey: telegramKeys.members(groupId) });
      }
    };

    window.addEventListener('telegramMemberJoined', handleMemberChange as EventListener);
    window.addEventListener('telegramMemberLeft', handleMemberChange as EventListener);
    window.addEventListener('telegramMemberUpdated', handleMemberChange as EventListener);

    return () => {
      window.removeEventListener('telegramMemberJoined', handleMemberChange as EventListener);
      window.removeEventListener('telegramMemberLeft', handleMemberChange as EventListener);
      window.removeEventListener('telegramMemberUpdated', handleMemberChange as EventListener);
    };
  }, [groupId, queryClient]);

  const query = useQuery({
    queryKey: groupId ? telegramKeys.members(groupId) : ['disabled'],
    queryFn: () => telegramApi.getGroupMembers(groupId!),
    enabled: !!groupId,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });

  return {
    members: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

// -----------------------------------------------------------------------------
// useTelegramParticipants - Combined group info + members (convenience hook)
// -----------------------------------------------------------------------------

export function useTelegramParticipants(groupId: number | null) {
  const { group, isLoading: isLoadingGroup } = useTelegramGroup(groupId);
  const { members, isLoading: isLoadingMembers, refetch } = useTelegramMembers(groupId);

  return {
    group,
    members,
    isLoading: isLoadingGroup || isLoadingMembers,
    refetch,
  };
}

// -----------------------------------------------------------------------------
// Mutations
// -----------------------------------------------------------------------------

export function useCreateTopic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ supergroupId, name, iconEmoji }: { supergroupId: number; name: string; iconEmoji?: string }) =>
      telegramApi.createTopic(supergroupId, name, iconEmoji),
    onSuccess: (_, { supergroupId }) => {
      queryClient.invalidateQueries({ queryKey: telegramKeys.supergroup(supergroupId) });
    },
  });
}

export function useUpdateMemberRole() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ groupId, userId, role }: { groupId: number; userId: number; role: string }) =>
      telegramApi.updateMemberRole(groupId, userId, role),
    onSuccess: (_, { groupId }) => {
      queryClient.invalidateQueries({ queryKey: telegramKeys.members(groupId) });
    },
  });
}

// Re-export types
export type { TelegramSupergroup, TelegramGroupMember };
