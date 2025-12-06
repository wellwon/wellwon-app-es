// =============================================================================
// File: src/api/telegram.ts — Telegram Domain API Client
// =============================================================================

import { API } from "./core";

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

export interface TelegramSupergroup {
  telegram_group_id: number;
  title: string;
  username: string | null;
  description: string | null;
  invite_link: string | null;
  is_forum: boolean;
  created_at: string;
  // Extended fields from company
  company_id: string | null;
  company_logo: string | null;
  group_type: string | null;
  member_count: number;
  is_active: boolean;
  bot_is_admin: boolean;
}

export interface TelegramGroupMember {
  id: string;
  supergroup_id: number;
  telegram_user_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  is_bot: boolean;
  status: string;
  is_active: boolean;
}

export interface WebhookInfo {
  webhook_url: string;
  webhook_configured: boolean;
  bot_api_available: boolean;
  mtproto_available: boolean;
}

export interface CreateGroupRequest {
  company_id: string;
  title?: string;
}

export interface CreateTopicRequest {
  supergroup_id: number;
  name: string;
  icon_emoji?: string;
}

export interface SendMessageRequest {
  chat_id: number;
  text: string;
  topic_id?: number;
  parse_mode?: string;
}

// -----------------------------------------------------------------------------
// Telegram Group Operations (via Company endpoints)
// -----------------------------------------------------------------------------

export async function getCompanySupergroups(companyId: string): Promise<TelegramSupergroup[]> {
  const { data } = await API.get<TelegramSupergroup[]>(`/companies/${companyId}/telegram`);
  return data;
}

export async function createTelegramGroup(
  companyId: string,
  title: string,
  description?: string
): Promise<{ id: string }> {
  const { data } = await API.post<{ id: string }>(`/companies/${companyId}/telegram`, {
    title,
    description,
  });
  return data;
}

export async function linkTelegramGroup(
  companyId: string,
  telegramGroupId: number
): Promise<{ id: string }> {
  const { data } = await API.post<{ id: string }>(`/companies/${companyId}/telegram/link`, {
    telegram_group_id: telegramGroupId,
  });
  return data;
}

export async function unlinkTelegramGroup(
  companyId: string,
  telegramGroupId: number
): Promise<{ id: string }> {
  const { data } = await API.delete<{ id: string }>(`/companies/${companyId}/telegram/link`, {
    data: { telegram_group_id: telegramGroupId },
  });
  return data;
}

// -----------------------------------------------------------------------------
// Webhook Operations
// -----------------------------------------------------------------------------

export async function getWebhookInfo(): Promise<WebhookInfo> {
  const { data } = await API.get<WebhookInfo>("/telegram/webhook/info");
  return data;
}

export async function setupWebhook(): Promise<{ ok: boolean; message?: string }> {
  const { data } = await API.post<{ ok: boolean; message?: string }>("/telegram/webhook/setup");
  return data;
}

export async function removeWebhook(): Promise<{ ok: boolean; message?: string }> {
  const { data } = await API.post<{ ok: boolean; message?: string }>("/telegram/webhook/remove");
  return data;
}

// -----------------------------------------------------------------------------
// Group Management Operations
// -----------------------------------------------------------------------------

export async function getGroupInfo(groupId: number): Promise<TelegramSupergroup | null> {
  try {
    const { data } = await API.get<TelegramSupergroup>(`/telegram/groups/${groupId}`);
    return data;
  } catch {
    return null;
  }
}

export async function createTopic(
  supergroupId: number,
  name: string,
  iconEmoji?: string
): Promise<{ topic_id: number } | null> {
  try {
    const { data } = await API.post<{ topic_id: number }>(`/telegram/groups/${supergroupId}/topics`, {
      name,
      icon_emoji: iconEmoji,
    });
    return data;
  } catch {
    return null;
  }
}

export async function sendMessage(
  chatId: number,
  text: string,
  topicId?: number
): Promise<{ message_id: number } | null> {
  try {
    const { data } = await API.post<{ message_id: number }>("/telegram/send", {
      chat_id: chatId,
      text,
      topic_id: topicId,
    });
    return data;
  } catch {
    return null;
  }
}

// -----------------------------------------------------------------------------
// Topic Verification
// -----------------------------------------------------------------------------

export interface VerifyTopicsResult {
  verificationResults: unknown[];
  summary: {
    existingTopics: number;
    deletedTopics: number;
    messagesMoved: number;
    generalDuplicatesMerged: number;
  };
  duplicatesMerged?: {
    canonicalChatId: string;
    duplicateIds: string[];
  };
}

export async function verifyTopics(
  supergroupId: number,
  dryRun: boolean = false
): Promise<VerifyTopicsResult | null> {
  try {
    const { data } = await API.post(`/telegram/groups/${supergroupId}/verify-topics`, {
      dry_run: dryRun,
    });

    // Transform backend response to frontend expected format
    // Backend returns: { success, verified_count, created_count, errors, dry_run }
    // Frontend expects: { verificationResults, summary, duplicatesMerged }
    return {
      verificationResults: data.errors || [],
      summary: {
        existingTopics: data.verified_count || 0,
        deletedTopics: 0,
        messagesMoved: 0,
        generalDuplicatesMerged: 0,
      },
      duplicatesMerged: undefined,
    };
  } catch {
    return null;
  }
}

// -----------------------------------------------------------------------------
// All Supergroups (aggregated from all companies)
// -----------------------------------------------------------------------------

export async function getAllSupergroups(
  activeOnly: boolean = true
): Promise<TelegramSupergroup[]> {
  try {
    const { data } = await API.get<TelegramSupergroup[]>("/telegram/supergroups", {
      params: { active_only: activeOnly },
    });
    return data;
  } catch {
    // Fallback: if no dedicated endpoint, return empty
    console.warn('[API] getAllSupergroups endpoint not available');
    return [];
  }
}

export async function getSupergroupChatCounts(): Promise<Record<number, number>> {
  try {
    const { data } = await API.get<Record<number, number>>("/telegram/supergroups/chat-counts");
    return data;
  } catch {
    console.warn('[API] getSupergroupChatCounts endpoint not available');
    return {};
  }
}

export async function updateSupergroup(
  supergroupId: number,
  updates: Partial<TelegramSupergroup>
): Promise<boolean> {
  try {
    await API.patch(`/telegram/supergroups/${supergroupId}`, updates);
    return true;
  } catch {
    return false;
  }
}

export interface GenerateInviteLinkResponse {
  success: boolean;
  invite_link?: string;
  error?: string;
}

/**
 * Generate a new invite link for a Telegram group.
 * This creates a new link via MTProto and saves it to the database.
 */
export async function generateInviteLink(groupId: number): Promise<GenerateInviteLinkResponse> {
  try {
    const { data } = await API.post<GenerateInviteLinkResponse>(
      `/telegram/group/${groupId}/generate-invite-link`
    );
    return data;
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.detail || error.message || 'Failed to generate invite link'
    };
  }
}

export async function deleteSupergroup(supergroupId: number): Promise<boolean> {
  try {
    await API.delete(`/telegram/supergroups/${supergroupId}`);
    return true;
  } catch {
    return false;
  }
}

// -----------------------------------------------------------------------------
// Member Management
// -----------------------------------------------------------------------------

export interface GroupMembersResponse {
  success: boolean;
  members: TelegramGroupMember[];
  total_count: number;
  error?: string;
}

export async function getGroupMembers(groupId: number): Promise<TelegramGroupMember[]> {
  try {
    const { data } = await API.get<GroupMembersResponse>(`/telegram/groups/${groupId}/members`);
    if (data.success) {
      return data.members.map(m => ({
        ...m,
        id: String(m.user_id),
        supergroup_id: groupId,
        telegram_user_id: m.user_id,
        is_active: true,
      })) as TelegramGroupMember[];
    }
    return [];
  } catch {
    console.warn('[API] getGroupMembers failed');
    return [];
  }
}

export async function updateMemberRole(
  groupId: number,
  userId: number,
  role: string
): Promise<boolean> {
  try {
    const { data } = await API.patch<{ success: boolean }>(`/telegram/groups/${groupId}/members/${userId}/role`, {
      role,
    });
    return data.success;
  } catch {
    return false;
  }
}

// -----------------------------------------------------------------------------
// Client Invitation to Group
// -----------------------------------------------------------------------------

export interface InviteToGroupRequest {
  contact: string;  // Phone (+79001234567) or @username
  client_name: string;
}

export interface InviteToGroupResponse {
  success: boolean;
  status: string;  // 'success', 'already_member', 'not_found', 'privacy_restricted', 'rate_limit'
  telegram_user_id?: number;
  error?: string;
}

/**
 * Invite external client to Telegram group by phone or @username.
 * Works directly with supergroupId, no chatId required.
 */
export async function inviteToGroup(
  groupId: number,
  request: InviteToGroupRequest
): Promise<InviteToGroupResponse> {
  try {
    const { data } = await API.post<InviteToGroupResponse>(
      `/telegram/groups/${groupId}/invite`,
      request
    );
    return data;
  } catch (error: any) {
    return {
      success: false,
      status: error.response?.data?.detail || 'error',
      error: error.response?.data?.detail || error.message || 'Failed to invite client'
    };
  }
}
