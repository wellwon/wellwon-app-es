/**
 * Query Key Factory - Centralized query key management for React Query
 *
 * Following TkDodo best practices for hierarchical query keys.
 * Provides type-safe, DRY query key generation with targeted invalidation support.
 *
 * Usage:
 * - queryKeys.orders.all - ['orders']
 * - queryKeys.orders.byAccount('acc-123') - ['orders', 'list', { accountId: 'acc-123' }]
 * - queryKeys.orders.detail('order-456') - ['orders', 'detail', 'order-456']
 *
 * @see https://tkdodo.eu/blog/effective-react-query-keys
 */

export const queryKeys = {
  /**
   * Order query keys
   */
  orders: {
    all: ['orders'] as const,
    lists: () => [...queryKeys.orders.all, 'list'] as const,
    list: (filters?: {
      accountId?: string;
      automationId?: string;
      symbol?: string;
      status?: string;
      limit?: number;
      offset?: number;
    }) => [...queryKeys.orders.lists(), filters] as const,
    byAccount: (accountId: string, filters?: { status?: string; symbol?: string }) =>
      [...queryKeys.orders.lists(), { accountId, ...filters }] as const,
    byAutomation: (automationId: string, filters?: { status?: string }) =>
      [...queryKeys.orders.lists(), { automationId, ...filters }] as const,
    bySymbol: (symbol: string) =>
      [...queryKeys.orders.lists(), { symbol }] as const,
    byStatus: (status: string) =>
      [...queryKeys.orders.lists(), { status }] as const,
    detail: (orderId: string) => [...queryKeys.orders.all, 'detail', orderId] as const,
    fills: (orderId: string) => [...queryKeys.orders.detail(orderId), 'fills'] as const,
    metrics: (filters?: { accountId?: string; automationId?: string }) =>
      [...queryKeys.orders.all, 'metrics', filters] as const,
  },

  /**
   * Position query keys
   */
  positions: {
    all: ['positions'] as const,
    lists: () => [...queryKeys.positions.all, 'list'] as const,
    list: (filters?: { accountId?: string; symbol?: string }) =>
      [...queryKeys.positions.lists(), filters] as const,
    byAccount: (accountId: string, filters?: { symbol?: string }) =>
      [...queryKeys.positions.lists(), { accountId, ...filters }] as const,
    bySymbol: (symbol: string) =>
      [...queryKeys.positions.lists(), { symbol }] as const,
    detail: (positionId: string) => [...queryKeys.positions.all, 'detail', positionId] as const,
  },

  /**
   * Broker account query keys
   */
  accounts: {
    all: ['accounts'] as const,
    lists: () => [...queryKeys.accounts.all, 'list'] as const,
    list: (filters?: { brokerId?: string; environment?: string }) =>
      [...queryKeys.accounts.lists(), filters] as const,
    byBroker: (brokerId: string, environment?: string) =>
      [...queryKeys.accounts.lists(), { brokerId, environment }] as const,
    detail: (accountId: string) => [...queryKeys.accounts.all, 'detail', accountId] as const,
    balance: (accountId: string) => [...queryKeys.accounts.detail(accountId), 'balance'] as const,
  },

  /**
   * Broker connection query keys
   */
  brokers: {
    all: ['brokers'] as const,
    lists: () => [...queryKeys.brokers.all, 'list'] as const,
    connections: () => [...queryKeys.brokers.all, 'connections'] as const,
    connection: (brokerId: string) =>
      [...queryKeys.brokers.connections(), brokerId] as const,
    detail: (brokerId: string) => [...queryKeys.brokers.all, 'detail', brokerId] as const,
  },

  /**
   * User query keys
   */
  user: {
    all: ['user'] as const,
    profile: () => [...queryKeys.user.all, 'profile'] as const,
    settings: () => [...queryKeys.user.all, 'settings'] as const,
  },

  /**
   * Automation query keys
   */
  automations: {
    all: ['automations'] as const,
    lists: () => [...queryKeys.automations.all, 'list'] as const,
    list: (filters?: { status?: string; accountId?: string }) =>
      [...queryKeys.automations.lists(), filters] as const,
    detail: (automationId: string) =>
      [...queryKeys.automations.all, 'detail', automationId] as const,
    metrics: (automationId: string) =>
      [...queryKeys.automations.detail(automationId), 'metrics'] as const,
  },

  /**
   * Market data query keys
   */
  marketData: {
    all: ['marketData'] as const,
    quote: (symbol: string) => [...queryKeys.marketData.all, 'quote', symbol] as const,
    quotes: (symbols: string[]) =>
      [...queryKeys.marketData.all, 'quotes', symbols.sort()] as const,
    bars: (symbol: string, timeframe: string) =>
      [...queryKeys.marketData.all, 'bars', symbol, timeframe] as const,
  },
};

/**
 * Helper function to invalidate all queries for a specific entity type
 *
 * Example:
 * ```ts
 * await invalidateEntity(queryClient, 'orders');
 * ```
 */
export type EntityType = keyof typeof queryKeys;

export function getEntityQueryKey(entity: EntityType) {
  return queryKeys[entity].all;
}
