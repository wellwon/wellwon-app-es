/**
 * Query Key Factory - Centralized query key management for React Query
 *
 * Following TkDodo best practices for hierarchical query keys.
 * Provides type-safe, DRY query key generation with targeted invalidation support.
 *
 * Usage:
 * - queryKeys.user.profile() - ['user', 'profile']
 * - queryKeys.companies.list() - ['companies', 'list']
 * - queryKeys.chats.messages('chat-123') - ['chats', 'detail', 'chat-123', 'messages']
 *
 * @see https://tkdodo.eu/blog/effective-react-query-keys
 */

export const queryKeys = {
  /**
   * User query keys
   */
  user: {
    all: ['user'] as const,
    profile: () => [...queryKeys.user.all, 'profile'] as const,
    settings: () => [...queryKeys.user.all, 'settings'] as const,
    notifications: () => [...queryKeys.user.all, 'notifications'] as const,
  },

  /**
   * Company query keys
   */
  companies: {
    all: ['companies'] as const,
    lists: () => [...queryKeys.companies.all, 'list'] as const,
    list: (filters?: { userId?: string; role?: string }) =>
      [...queryKeys.companies.lists(), filters] as const,
    detail: (companyId: string) => [...queryKeys.companies.all, 'detail', companyId] as const,
    participants: (companyId: string) =>
      [...queryKeys.companies.detail(companyId), 'participants'] as const,
    supergroups: (companyId: string) =>
      [...queryKeys.companies.detail(companyId), 'supergroups'] as const,
  },

  /**
   * Chat query keys
   */
  chats: {
    all: ['chats'] as const,
    lists: () => [...queryKeys.chats.all, 'list'] as const,
    list: (filters?: { userId?: string; companyId?: string; type?: string }) =>
      [...queryKeys.chats.lists(), filters] as const,
    byCompany: (companyId: string) =>
      [...queryKeys.chats.lists(), { companyId }] as const,
    detail: (chatId: string) => [...queryKeys.chats.all, 'detail', chatId] as const,
    messages: (chatId: string, filters?: { limit?: number; before?: string }) =>
      [...queryKeys.chats.detail(chatId), 'messages', filters] as const,
    participants: (chatId: string) =>
      [...queryKeys.chats.detail(chatId), 'participants'] as const,
    unreadCount: (chatId?: string) =>
      chatId
        ? [...queryKeys.chats.detail(chatId), 'unread'] as const
        : [...queryKeys.chats.all, 'unread'] as const,
  },

  /**
   * Message template query keys
   */
  templates: {
    all: ['templates'] as const,
    lists: () => [...queryKeys.templates.all, 'list'] as const,
    list: (filters?: { category?: string }) =>
      [...queryKeys.templates.lists(), filters] as const,
    byCategory: (category: string) =>
      [...queryKeys.templates.lists(), { category }] as const,
    detail: (templateId: string) => [...queryKeys.templates.all, 'detail', templateId] as const,
  },

  /**
   * Shipment query keys
   */
  shipments: {
    all: ['shipments'] as const,
    lists: () => [...queryKeys.shipments.all, 'list'] as const,
    list: (filters?: { companyId?: string; status?: string }) =>
      [...queryKeys.shipments.lists(), filters] as const,
    byCompany: (companyId: string, filters?: { status?: string }) =>
      [...queryKeys.shipments.lists(), { companyId, ...filters }] as const,
    byStatus: (status: string) =>
      [...queryKeys.shipments.lists(), { status }] as const,
    detail: (shipmentId: string) => [...queryKeys.shipments.all, 'detail', shipmentId] as const,
    cargo: (shipmentId: string) =>
      [...queryKeys.shipments.detail(shipmentId), 'cargo'] as const,
    tracking: (shipmentId: string) =>
      [...queryKeys.shipments.detail(shipmentId), 'tracking'] as const,
  },

  /**
   * Customs declaration query keys
   */
  customs: {
    all: ['customs'] as const,
    lists: () => [...queryKeys.customs.all, 'list'] as const,
    list: (filters?: { companyId?: string; status?: string; shipmentId?: string }) =>
      [...queryKeys.customs.lists(), filters] as const,
    byShipment: (shipmentId: string) =>
      [...queryKeys.customs.lists(), { shipmentId }] as const,
    detail: (declarationId: string) => [...queryKeys.customs.all, 'detail', declarationId] as const,
    documents: (declarationId: string) =>
      [...queryKeys.customs.detail(declarationId), 'documents'] as const,
  },

  /**
   * Document query keys
   */
  documents: {
    all: ['documents'] as const,
    lists: () => [...queryKeys.documents.all, 'list'] as const,
    list: (filters?: { companyId?: string; type?: string; entityId?: string }) =>
      [...queryKeys.documents.lists(), filters] as const,
    byEntity: (entityType: string, entityId: string) =>
      [...queryKeys.documents.lists(), { entityType, entityId }] as const,
    detail: (documentId: string) => [...queryKeys.documents.all, 'detail', documentId] as const,
  },

  /**
   * Payment/Transaction query keys
   */
  payments: {
    all: ['payments'] as const,
    lists: () => [...queryKeys.payments.all, 'list'] as const,
    list: (filters?: { companyId?: string; status?: string }) =>
      [...queryKeys.payments.lists(), filters] as const,
    byCompany: (companyId: string, filters?: { status?: string }) =>
      [...queryKeys.payments.lists(), { companyId, ...filters }] as const,
    detail: (paymentId: string) => [...queryKeys.payments.all, 'detail', paymentId] as const,
    invoices: (filters?: { companyId?: string; status?: string }) =>
      [...queryKeys.payments.all, 'invoices', filters] as const,
    invoice: (invoiceId: string) => [...queryKeys.payments.all, 'invoice', invoiceId] as const,
  },

  /**
   * Telegram integration query keys
   */
  telegram: {
    all: ['telegram'] as const,
    supergroups: () => [...queryKeys.telegram.all, 'supergroups'] as const,
    supergroup: (supergroupId: string) =>
      [...queryKeys.telegram.supergroups(), supergroupId] as const,
    members: (supergroupId: string) =>
      [...queryKeys.telegram.supergroup(supergroupId), 'members'] as const,
    users: (userIds: string[]) =>
      [...queryKeys.telegram.all, 'users', userIds.sort()] as const,
  },

  /**
   * Analytics/Metrics query keys
   */
  analytics: {
    all: ['analytics'] as const,
    dashboard: (companyId?: string) =>
      [...queryKeys.analytics.all, 'dashboard', companyId] as const,
    shipmentMetrics: (filters?: { companyId?: string; period?: string }) =>
      [...queryKeys.analytics.all, 'shipments', filters] as const,
    financialMetrics: (filters?: { companyId?: string; period?: string }) =>
      [...queryKeys.analytics.all, 'financial', filters] as const,
  },
};

/**
 * Helper function to get the base query key for an entity type
 *
 * Example:
 * ```ts
 * await queryClient.invalidateQueries({ queryKey: getEntityQueryKey('companies') });
 * ```
 */
export type EntityType = keyof typeof queryKeys;

export function getEntityQueryKey(entity: EntityType) {
  return queryKeys[entity].all;
}
