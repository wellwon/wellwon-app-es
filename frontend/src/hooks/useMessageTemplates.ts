/**
 * Hook for message templates
 * Uses React Query for data fetching
 */

import { useTemplatesByCategory, type MessageTemplate } from '@/hooks/queries';

export const useMessageTemplates = () => {
  const { data: templates = {}, isLoading, error, refetch } = useTemplatesByCategory(true);

  // Note: Create/Update/Delete not implemented on backend yet
  // These return stubs for backward compatibility
  const updateTemplate = async (_templateId: string, _updatedTemplate: MessageTemplate): Promise<boolean> => {
    console.warn('Template update not implemented yet');
    return false;
  };

  const createTemplate = async (_template: Omit<MessageTemplate, 'id'>): Promise<string | null> => {
    console.warn('Template creation not implemented yet');
    return null;
  };

  const deleteTemplate = async (_templateId: string): Promise<boolean> => {
    console.warn('Template deletion not implemented yet');
    return false;
  };

  return {
    templates,
    isLoading,
    error: error ? 'Failed to load templates' : null,
    loadTemplates: refetch,
    updateTemplate,
    createTemplate,
    deleteTemplate,
  };
};