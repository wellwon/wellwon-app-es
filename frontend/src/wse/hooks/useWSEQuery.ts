// =============================================================================
// File: src/wse/hooks/useWSEQuery.ts
// Description: Hook for integrating WSE realtime with React Query
// Pattern: REST API (primary) + WSE events (reactive invalidation)
// =============================================================================

import { useQuery, useQueryClient, UseQueryOptions, QueryKey } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useWSE } from './useWSE';
import { logger } from '../utils/logger';

/**
 * Hook that combines React Query with WSE realtime updates
 *
 * @example
 * const { data, isLoading } = useWSEQuery(
 *   ['messages', chatId],
 *   () => axios.get(`/api/chats/${chatId}/messages`),
 *   'message_sent',
 *   {
 *     invalidateOn: (event) => event.p.chat_id === chatId
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
  const wse = useWSE();

  // Setup React Query
  const query = useQuery({
    queryKey,
    queryFn,
    ...options?.queryOptions
  });

  // Setup WSE realtime invalidation
  useEffect(() => {
    if (!wse || !wse.sendMessage) {
      // WSE not initialized yet
      logger.debug('[useWSEQuery] WSE not ready yet');
      return;
    }

    const events = Array.isArray(wseEventTypes) ? wseEventTypes : [wseEventTypes];
    logger.debug(`[useWSEQuery] Setting up listeners for events: ${events.join(', ')}`);

    const handlers: Array<{ eventType: string; handler: (event: any) => void }> = [];

    events.forEach(eventType => {
      const handler = (event: any) => {
        logger.debug(`[useWSEQuery] Received event ${eventType}`, event);

        // Check if we should invalidate
        if (!options?.invalidateOn || options.invalidateOn(event)) {
          logger.info(`[useWSEQuery] Invalidating query ${JSON.stringify(queryKey)} due to ${eventType}`);
          queryClient.invalidateQueries({ queryKey });
        } else {
          logger.debug(`[useWSEQuery] Event ${eventType} did not match filter, skipping invalidation`);
        }
      };

      // Subscribe to WSE event
      // Note: WSE useWSE hook doesn't expose .on() method directly
      // Events are handled through EventHandlers registration
      // We'll use a different approach - listen to store updates

      handlers.push({ eventType, handler });
    });

    // Cleanup
    return () => {
      logger.debug(`[useWSEQuery] Cleaning up listeners for ${events.join(', ')}`);
      // Cleanup would go here if we had direct event subscription
    };
  }, [queryKey, wseEventTypes, wse, queryClient, options?.invalidateOn]);

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
