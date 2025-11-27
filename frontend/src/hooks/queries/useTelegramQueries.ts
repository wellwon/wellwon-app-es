/**
 * Telegram domain React Query hooks
 * Replaces TelegramChatService
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as telegramApi from '@/api/telegram';
import { queryKeys } from '@/lib/queryKeys';

// Re-export types
export type {
  TelegramSupergroup,
  TelegramGroupMember,
  WebhookInfo,
} from '@/api/telegram';

// =============================================================================
// Supergroup Queries
// =============================================================================

/**
 * Fetch all supergroups
 */
export function useSupergroups(activeOnly: boolean = true) {
  return useQuery({
    queryKey: queryKeys.telegram.supergroups(),
    queryFn: () => telegramApi.getAllSupergroups(activeOnly),
  });
}

/**
 * Fetch supergroup by ID
 */
export function useSupergroup(groupId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.telegram.supergroup(String(groupId || '')),
    queryFn: () => telegramApi.getGroupInfo(groupId!),
    enabled: !!groupId,
  });
}

/**
 * Fetch chat counts per supergroup
 */
export function useSupergroupChatCounts() {
  return useQuery({
    queryKey: ['telegram', 'supergroups', 'chat-counts'],
    queryFn: () => telegramApi.getSupergroupChatCounts(),
  });
}

/**
 * Fetch supergroup members
 */
export function useSupergroupMembers(groupId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.telegram.members(String(groupId || '')),
    queryFn: () => telegramApi.getGroupMembers(groupId!),
    enabled: !!groupId,
  });
}

// =============================================================================
// Webhook Queries
// =============================================================================

/**
 * Fetch webhook info
 */
export function useWebhookInfo() {
  return useQuery({
    queryKey: ['telegram', 'webhook', 'info'],
    queryFn: () => telegramApi.getWebhookInfo(),
  });
}

// =============================================================================
// Supergroup Mutations
// =============================================================================

/**
 * Update supergroup
 */
export function useUpdateSupergroup() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ groupId, updates }: {
      groupId: number;
      updates: Partial<telegramApi.TelegramSupergroup>;
    }) => telegramApi.updateSupergroup(groupId, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.telegram.supergroup(String(variables.groupId)) });
      queryClient.invalidateQueries({ queryKey: queryKeys.telegram.supergroups() });
    },
  });
}

// =============================================================================
// Topic Mutations
// =============================================================================

/**
 * Create topic in supergroup
 */
export function useCreateTopic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ supergroupId, name, iconEmoji }: {
      supergroupId: number;
      name: string;
      iconEmoji?: string;
    }) => telegramApi.createTopic(supergroupId, name, iconEmoji),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.telegram.supergroup(String(variables.supergroupId)) });
    },
  });
}

/**
 * Verify topics in supergroup
 */
export function useVerifyTopics() {
  return useMutation({
    mutationFn: ({ supergroupId, dryRun }: {
      supergroupId: number;
      dryRun?: boolean;
    }) => telegramApi.verifyTopics(supergroupId, dryRun ?? false),
  });
}

// =============================================================================
// Messaging Mutations
// =============================================================================

/**
 * Send Telegram message
 */
export function useSendTelegramMessage() {
  return useMutation({
    mutationFn: ({ chatId, text, topicId }: {
      chatId: number;
      text: string;
      topicId?: number;
    }) => telegramApi.sendMessage(chatId, text, topicId),
  });
}

// =============================================================================
// Webhook Mutations
// =============================================================================

/**
 * Setup webhook
 */
export function useSetupWebhook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => telegramApi.setupWebhook(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['telegram', 'webhook', 'info'] });
    },
  });
}

/**
 * Remove webhook
 */
export function useRemoveWebhook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => telegramApi.removeWebhook(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['telegram', 'webhook', 'info'] });
    },
  });
}

// =============================================================================
// Member Management Mutations
// =============================================================================

/**
 * Update member role
 */
export function useUpdateMemberRole() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ groupId, userId, role }: {
      groupId: number;
      userId: number;
      role: string;
    }) => telegramApi.updateMemberRole(groupId, userId, role),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.telegram.members(String(variables.groupId)) });
    },
  });
}

// =============================================================================
// Utility Functions (not hooks - pure functions)
// =============================================================================

/**
 * Get display name for Telegram user
 */
export function getTelegramUserDisplayName(user: telegramApi.TelegramGroupMember | null): string {
  if (!user) return 'Unknown';
  return user.username || `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'Unknown';
}

/**
 * Check if chat ID is a Telegram chat
 */
export function isTelegramChat(chatId: string): boolean {
  const parsed = parseInt(chatId, 10);
  return !isNaN(parsed) && parsed < 0;
}

/**
 * Format supergroup info for display
 */
export function formatSupergroupInfo(supergroup: telegramApi.TelegramSupergroup): string {
  const parts: string[] = [supergroup.title];
  if (supergroup.username) {
    parts.push(`@${supergroup.username}`);
  }
  if (supergroup.member_count > 0) {
    parts.push(`${supergroup.member_count} members`);
  }
  return parts.join(' | ');
}
