// =============================================================================
// useFormTemplates - React Query hooks для шаблонов форм
// =============================================================================

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getFormTemplates,
  getFormTemplate,
  createFormTemplate,
  updateFormTemplate,
  deleteFormTemplate,
  duplicateFormTemplate,
  publishFormTemplate,
  unpublishFormTemplate,
  getTemplateVersions,
  getTemplateVersion,
  restoreTemplateVersion,
  getTemplateDraft,
  saveTemplateDraft,
  deleteTemplateDraft,
  getUserDrafts,
  getSchemaFields,
  getFormDefinition,
  exportTemplate,
  importTemplate,
  downloadTemplateExport,
  autoSaveDraft,
  cancelAutoSave,
} from '../api/form-templates-api';
import type {
  FormTemplate,
  FormTemplateListItem,
  CreateFormTemplateRequest,
  UpdateFormTemplateRequest,
} from '../types/form-builder';
import type { FieldDefinition } from '../types/form-definitions';

// =============================================================================
// Query Keys
// =============================================================================

export const formTemplateKeys = {
  all: ['form-templates'] as const,
  lists: () => [...formTemplateKeys.all, 'list'] as const,
  list: (filters: Record<string, any>) => [...formTemplateKeys.lists(), filters] as const,
  details: () => [...formTemplateKeys.all, 'detail'] as const,
  detail: (id: string) => [...formTemplateKeys.details(), id] as const,
  versions: (id: string) => [...formTemplateKeys.detail(id), 'versions'] as const,
  version: (id: string, version: number) => [...formTemplateKeys.versions(id), version] as const,
  draft: (id: string) => [...formTemplateKeys.detail(id), 'draft'] as const,
  userDrafts: () => [...formTemplateKeys.all, 'user-drafts'] as const,
  schema: (documentModeId: string) => ['schema-fields', documentModeId] as const,
};

// =============================================================================
// Templates Queries
// =============================================================================

/**
 * Получить список шаблонов
 */
export function useFormTemplates(params?: {
  page?: number;
  page_size?: number;
  document_mode_id?: string;
  search?: string;
  is_published?: boolean;
}) {
  return useQuery({
    queryKey: formTemplateKeys.list(params || {}),
    queryFn: () => getFormTemplates(params),
  });
}

/**
 * Получить шаблон по ID
 */
export function useFormTemplate(templateId: string | undefined) {
  return useQuery({
    queryKey: formTemplateKeys.detail(templateId!),
    queryFn: () => getFormTemplate(templateId!),
    enabled: !!templateId,
  });
}

/**
 * Получить опубликованный шаблон для document mode
 */
export function usePublishedTemplate(documentModeId: string | undefined) {
  return useQuery({
    queryKey: formTemplateKeys.list({ document_mode_id: documentModeId, is_published: true }),
    queryFn: () => getFormTemplates({ document_mode_id: documentModeId, is_published: true }),
    enabled: !!documentModeId,
    select: (data) => data.items[0] || null,
  });
}

// =============================================================================
// Templates Mutations
// =============================================================================

/**
 * Создать шаблон
 */
export function useCreateFormTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateFormTemplateRequest) => createFormTemplate(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: formTemplateKeys.lists() });
    },
  });
}

/**
 * Обновить шаблон
 */
export function useUpdateFormTemplate(templateId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateFormTemplateRequest) => updateFormTemplate(templateId, data),
    onSuccess: (updatedTemplate) => {
      queryClient.setQueryData(formTemplateKeys.detail(templateId), updatedTemplate);
      queryClient.invalidateQueries({ queryKey: formTemplateKeys.lists() });
    },
  });
}

/**
 * Удалить шаблон
 */
export function useDeleteFormTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (templateId: string) => deleteFormTemplate(templateId),
    onSuccess: (_, templateId) => {
      queryClient.removeQueries({ queryKey: formTemplateKeys.detail(templateId) });
      queryClient.invalidateQueries({ queryKey: formTemplateKeys.lists() });
    },
  });
}

/**
 * Дублировать шаблон
 */
export function useDuplicateFormTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ templateId, newName }: { templateId: string; newName?: string }) =>
      duplicateFormTemplate(templateId, newName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: formTemplateKeys.lists() });
    },
  });
}

// =============================================================================
// Publishing Mutations
// =============================================================================

/**
 * Опубликовать шаблон
 */
export function usePublishFormTemplate(templateId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params?: { versionLabel?: string; changeDescription?: string }) =>
      publishFormTemplate(templateId, params?.versionLabel, params?.changeDescription),
    onSuccess: (updatedTemplate) => {
      queryClient.setQueryData(formTemplateKeys.detail(templateId), updatedTemplate);
      queryClient.invalidateQueries({ queryKey: formTemplateKeys.lists() });
      queryClient.invalidateQueries({ queryKey: formTemplateKeys.versions(templateId) });
    },
  });
}

/**
 * Снять с публикации
 */
export function useUnpublishFormTemplate(templateId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => unpublishFormTemplate(templateId),
    onSuccess: (updatedTemplate) => {
      queryClient.setQueryData(formTemplateKeys.detail(templateId), updatedTemplate);
      queryClient.invalidateQueries({ queryKey: formTemplateKeys.lists() });
    },
  });
}

// =============================================================================
// Versions Queries/Mutations
// =============================================================================

/**
 * Получить версии шаблона
 */
export function useTemplateVersions(templateId: string | undefined) {
  return useQuery({
    queryKey: formTemplateKeys.versions(templateId!),
    queryFn: () => getTemplateVersions(templateId!),
    enabled: !!templateId,
  });
}

/**
 * Получить конкретную версию
 */
export function useTemplateVersion(templateId: string | undefined, version: number | undefined) {
  return useQuery({
    queryKey: formTemplateKeys.version(templateId!, version!),
    queryFn: () => getTemplateVersion(templateId!, version!),
    enabled: !!templateId && version !== undefined,
  });
}

/**
 * Восстановить версию
 */
export function useRestoreTemplateVersion(templateId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (version: number) => restoreTemplateVersion(templateId, version),
    onSuccess: (updatedTemplate) => {
      queryClient.setQueryData(formTemplateKeys.detail(templateId), updatedTemplate);
      queryClient.invalidateQueries({ queryKey: formTemplateKeys.lists() });
    },
  });
}

// =============================================================================
// Drafts Queries/Mutations
// =============================================================================

/**
 * Получить черновик пользователя
 */
export function useTemplateDraft(templateId: string | undefined) {
  return useQuery({
    queryKey: formTemplateKeys.draft(templateId!),
    queryFn: () => getTemplateDraft(templateId!),
    enabled: !!templateId,
  });
}

/**
 * Сохранить черновик
 */
export function useSaveTemplateDraft(templateId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (draftData: Partial<FormTemplate>) => saveTemplateDraft(templateId, draftData),
    onSuccess: (savedDraft) => {
      queryClient.setQueryData(formTemplateKeys.draft(templateId), savedDraft);
    },
  });
}

/**
 * Удалить черновик
 */
export function useDeleteTemplateDraft(templateId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => deleteTemplateDraft(templateId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: formTemplateKeys.draft(templateId) });
    },
  });
}

/**
 * Получить все черновики пользователя
 */
export function useUserDrafts() {
  return useQuery({
    queryKey: formTemplateKeys.userDrafts(),
    queryFn: getUserDrafts,
  });
}

// =============================================================================
// Schema Fields Query
// =============================================================================

/**
 * Получить поля схемы для document mode
 */
export function useSchemaFields(documentModeId: string | undefined) {
  return useQuery({
    queryKey: formTemplateKeys.schema(documentModeId!),
    queryFn: () => getSchemaFields(documentModeId!),
    enabled: !!documentModeId,
    staleTime: 1000 * 60 * 30, // 30 минут - схемы редко меняются
  });
}

/**
 * Получить полную форму (поля + секции с конфигурациями)
 * Используется для Form Builder чтобы восстановить сохранённое состояние
 */
export function useFormDefinition(documentModeId: string | undefined) {
  return useQuery({
    queryKey: ['form-definition', documentModeId],
    queryFn: () => getFormDefinition(documentModeId!),
    enabled: !!documentModeId,
    staleTime: 1000 * 60 * 5, // 5 минут - свежие данные для Form Builder
  });
}

// =============================================================================
// Export/Import Mutations
// =============================================================================

/**
 * Экспортировать шаблон
 */
export function useExportTemplate() {
  return useMutation({
    mutationFn: ({ templateId, templateName }: { templateId: string; templateName: string }) =>
      downloadTemplateExport(templateId, templateName),
  });
}

/**
 * Импортировать шаблон
 */
export function useImportTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => importTemplate(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: formTemplateKeys.lists() });
    },
  });
}

// =============================================================================
// Auto-save Hook
// =============================================================================

/**
 * Hook для автосохранения черновика
 */
export function useAutoSaveDraft(templateId: string | undefined, delay: number = 2000) {
  const queryClient = useQueryClient();

  const save = async (draftData: Partial<FormTemplate>) => {
    if (!templateId) return;

    try {
      const savedDraft = await autoSaveDraft(templateId, draftData, delay);
      queryClient.setQueryData(formTemplateKeys.draft(templateId), savedDraft);
      return savedDraft;
    } catch (error) {
      console.error('Auto-save failed:', error);
      throw error;
    }
  };

  const cancel = () => {
    cancelAutoSave();
  };

  return { save, cancel };
}
