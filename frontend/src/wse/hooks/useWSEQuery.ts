// =============================================================================
// File: src/wse/hooks/useWSEQuery.ts
// Description: Hook for integrating WSE realtime with React Query
// Pattern: REST API (primary) + WSE events (reactive invalidation)
// =============================================================================

import { useQuery, useQueryClient, UseQueryOptions, QueryKey } from '@tanstack/react-query';
import { useEffect } from 'react';
import { logger } from '../utils/logger';

/**
 * Hook that combines React Query with WSE realtime updates
 *
 * Uses window CustomEvents dispatched by EventHandlers.ts for reactive cache invalidation.
 * When a matching WSE event is received, the query is automatically invalidated and refetched.
 *
 * @example
 * // Listen for user profile updates
 * const { data, isLoading } = useWSEQuery(
 *   queryKeys.user.profile(),
 *   () => axios.get('/api/auth/me'),
 *   'userAccountUpdated',
 *   {
 *     invalidateOn: (eventData) => eventData.user_id === currentUserId
 *   }
 * );
 *
 * @example
 * // Listen for multiple event types
 * const { data } = useWSEQuery(
 *   queryKeys.companies.list(),
 *   () => axios.get('/api/companies'),
 *   ['entityUpdated', 'notification'],
 *   {
 *     invalidateOn: (eventData) => eventData.entityType === 'company'
 *   }
 * );
 */
export function useWSEQuery<TData = unknown>(
  queryKey: QueryKey,
  queryFn: () => Promise<TData>,
  wseEventTypes: string | string[],
  options?: {
    /**
     * Optional filter function to determine if query should be invalidated
     * Returns true to invalidate, false to ignore the event
     */
    invalidateOn?: (event: any) => boolean;

    /**
     * React Query options (merged with defaults)
     */
    queryOptions?: Omit<UseQueryOptions<TData>, 'queryKey' | 'queryFn'>;
  }
) {
  const queryClient = useQueryClient();

  // Setup React Query
  const query = useQuery({
    queryKey,
    queryFn,
    ...options?.queryOptions
  });

  // Setup WSE realtime invalidation via window CustomEvents
  useEffect(() => {
    const events = Array.isArray(wseEventTypes) ? wseEventTypes : [wseEventTypes];
    logger.debug(`[useWSEQuery] Setting up listeners for events: ${events.join(', ')}`);

    // Create handlers for each event type
    const handlers: Array<{ eventType: string; handler: (event: Event) => void }> = [];

    events.forEach(eventType => {
      const handler = (event: Event) => {
        const customEvent = event as CustomEvent;
        const eventData = customEvent.detail;

        logger.debug(`[useWSEQuery] Received event ${eventType}`, eventData);

        // Check if we should invalidate
        // Pass the event detail (payload) to the filter function
        if (!options?.invalidateOn || options.invalidateOn(eventData)) {
          logger.info(`[useWSEQuery] Invalidating query ${JSON.stringify(queryKey)} due to ${eventType}`);
          queryClient.invalidateQueries({ queryKey });
        } else {
          logger.debug(`[useWSEQuery] Event ${eventType} did not match filter, skipping invalidation`);
        }
      };

      // Subscribe to WSE CustomEvent via window
      // EventHandlers.ts dispatches events like 'userAccountUpdated', 'entityUpdated', etc.
      window.addEventListener(eventType, handler);
      handlers.push({ eventType, handler });

      logger.debug(`[useWSEQuery] Subscribed to ${eventType}`);
    });

    // Cleanup - remove all event listeners
    return () => {
      logger.debug(`[useWSEQuery] Cleaning up listeners for ${events.join(', ')}`);
      handlers.forEach(({ eventType, handler }) => {
        window.removeEventListener(eventType, handler);
        logger.debug(`[useWSEQuery] Unsubscribed from ${eventType}`);
      });
    };
  }, [queryKey, wseEventTypes, queryClient, options?.invalidateOn]);

  return query;
}

/**
 * Helper hook for WSE mutations with optimistic updates
 *
 * @example
 * const { mutate } = useWSEMutation(
 *   (data) => axios.post('/api/messages', data),
 *   {
 *     onSuccess: () => {
 *       queryClient.invalidateQueries(['messages']);
 *     }
 *   }
 * );
 */
export function useWSEMutation<TData = unknown, TVariables = unknown>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  options?: {
    onSuccess?: (data: TData, variables: TVariables) => void;
    onError?: (error: Error, variables: TVariables) => void;
  }
) {
  // TODO: Implement WSE mutation pattern
  // For now, use regular useMutation from React Query
  return {
    mutate: mutationFn,
    ...options
  };
}
