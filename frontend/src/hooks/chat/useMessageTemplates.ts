// =============================================================================
// File: src/hooks/chat/useMessageTemplates.ts
// Description: React Query hook for message templates with WSE integration
// Pattern: TkDodo's "Using WebSockets with React Query"
// =============================================================================

import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as chatApi from '@/api/chat';
import { logger } from '@/utils/logger';

// -----------------------------------------------------------------------------
// Query Keys
// -----------------------------------------------------------------------------

export const templateKeys = {
  all: ['templates'] as const,
  byCategory: (grouped: boolean) => [...templateKeys.all, 'byCategory', grouped] as const,
};

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

export interface MessageTemplate {
  id: string;
  category: string;
  title: string;
  content: string;
  variables?: string[];
  is_active: boolean;
  sort_order: number;
}

// -----------------------------------------------------------------------------
// useMessageTemplates - Templates grouped by category with WSE
// -----------------------------------------------------------------------------

interface UseMessageTemplatesOptions {
  enabled?: boolean;
  grouped?: boolean;
}

export function useMessageTemplates(options: UseMessageTemplatesOptions = {}) {
  const queryClient = useQueryClient();
  const { enabled = true, grouped = true } = options;

  // WSE event handlers
  useEffect(() => {
    if (!enabled) return;

    const handleTemplateChange = () => {
      logger.debug('WSE: Template change, invalidating');
      queryClient.invalidateQueries({ queryKey: templateKeys.all });
    };

    window.addEventListener('templateCreated', handleTemplateChange);
    window.addEventListener('templateUpdated', handleTemplateChange);
    window.addEventListener('templateDeleted', handleTemplateChange);

    return () => {
      window.removeEventListener('templateCreated', handleTemplateChange);
      window.removeEventListener('templateUpdated', handleTemplateChange);
      window.removeEventListener('templateDeleted', handleTemplateChange);
    };
  }, [enabled, queryClient]);

  const query = useQuery({
    queryKey: templateKeys.byCategory(grouped),
    queryFn: () => chatApi.getTemplatesByCategory(grouped),
    enabled,
    staleTime: 10 * 60 * 1000, // 10 minutes - templates don't change often
  });

  return {
    templates: query.data ?? {},
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

// -----------------------------------------------------------------------------
// Flat list of templates (convenience)
// -----------------------------------------------------------------------------

export function useTemplateList() {
  const { templates, isLoading, isError, error, refetch } = useMessageTemplates({ grouped: true });

  // Flatten grouped templates into a single list
  const templateList = Object.values(templates).flat() as MessageTemplate[];

  return {
    templates: templateList,
    isLoading,
    isError,
    error,
    refetch,
  };
}
