// =============================================================================
// Form Templates API - API клиент для шаблонов форм
// =============================================================================

import { API } from '@/api/core';
import type {
  FormTemplate,
  FormTemplateVersion,
  FormTemplateDraft,
  FormTemplateListItem,
  CreateFormTemplateRequest,
  UpdateFormTemplateRequest,
  CreateVersionRequest,
  FormSectionConfig,
} from '../types/form-builder';
import type { FieldDefinition } from '../types/form-definitions';

// =============================================================================
// API Response Types
// =============================================================================

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface ApiResponse<T> {
  data: T;
  message?: string;
}

// =============================================================================
// Form Templates API
// =============================================================================

const BASE_URL = '/api/v1/declarant/form-templates';

/**
 * Получить список шаблонов форм
 */
export async function getFormTemplates(params?: {
  page?: number;
  page_size?: number;
  document_mode_id?: string;
  search?: string;
  is_published?: boolean;
}): Promise<PaginatedResponse<FormTemplateListItem>> {
  const response = await API.get<PaginatedResponse<FormTemplateListItem>>(BASE_URL, { params });
  return response.data;
}

/**
 * Получить шаблон по ID
 */
export async function getFormTemplate(templateId: string): Promise<FormTemplate> {
  const response = await API.get<ApiResponse<FormTemplate>>(`${BASE_URL}/${templateId}`);
  return response.data.data;
}

/**
 * Создать новый шаблон
 */
export async function createFormTemplate(data: CreateFormTemplateRequest): Promise<FormTemplate> {
  const response = await API.post<ApiResponse<FormTemplate>>(BASE_URL, data);
  return response.data.data;
}

/**
 * Обновить шаблон
 */
export async function updateFormTemplate(
  templateId: string,
  data: UpdateFormTemplateRequest
): Promise<FormTemplate> {
  const response = await API.put<ApiResponse<FormTemplate>>(`${BASE_URL}/${templateId}`, data);
  return response.data.data;
}

/**
 * Удалить шаблон
 */
export async function deleteFormTemplate(templateId: string): Promise<void> {
  await API.delete(`${BASE_URL}/${templateId}`);
}

/**
 * Дублировать шаблон
 */
export async function duplicateFormTemplate(
  templateId: string,
  newName?: string
): Promise<FormTemplate> {
  const response = await API.post<ApiResponse<FormTemplate>>(`${BASE_URL}/${templateId}/duplicate`, {
    name: newName,
  });
  return response.data.data;
}

// =============================================================================
// Template Publishing
// =============================================================================

/**
 * Опубликовать шаблон (создает новую версию)
 */
export async function publishFormTemplate(
  templateId: string,
  versionLabel?: string,
  changeDescription?: string
): Promise<FormTemplate> {
  const response = await API.post<ApiResponse<FormTemplate>>(`${BASE_URL}/${templateId}/publish`, {
    version_label: versionLabel,
    change_description: changeDescription,
  });
  return response.data.data;
}

/**
 * Снять с публикации
 */
export async function unpublishFormTemplate(templateId: string): Promise<FormTemplate> {
  const response = await API.post<ApiResponse<FormTemplate>>(`${BASE_URL}/${templateId}/unpublish`);
  return response.data.data;
}

// =============================================================================
// Template Versions
// =============================================================================

/**
 * Получить все версии шаблона
 */
export async function getTemplateVersions(templateId: string): Promise<FormTemplateVersion[]> {
  const response = await API.get<ApiResponse<FormTemplateVersion[]>>(
    `${BASE_URL}/${templateId}/versions`
  );
  return response.data.data;
}

/**
 * Получить конкретную версию
 */
export async function getTemplateVersion(
  templateId: string,
  versionNumber: number
): Promise<FormTemplateVersion> {
  const response = await API.get<ApiResponse<FormTemplateVersion>>(
    `${BASE_URL}/${templateId}/versions/${versionNumber}`
  );
  return response.data.data;
}

/**
 * Восстановить версию (делает её текущей)
 */
export async function restoreTemplateVersion(
  templateId: string,
  versionNumber: number
): Promise<FormTemplate> {
  const response = await API.post<ApiResponse<FormTemplate>>(
    `${BASE_URL}/${templateId}/versions/${versionNumber}/restore`
  );
  return response.data.data;
}

// =============================================================================
// Template Drafts
// =============================================================================

/**
 * Получить черновик пользователя для шаблона
 */
export async function getTemplateDraft(templateId: string): Promise<FormTemplateDraft | null> {
  try {
    const response = await API.get<ApiResponse<FormTemplateDraft>>(
      `${BASE_URL}/${templateId}/draft`
    );
    return response.data.data;
  } catch (error: any) {
    if (error.response?.status === 404) {
      return null;
    }
    throw error;
  }
}

/**
 * Сохранить черновик
 */
export async function saveTemplateDraft(
  templateId: string,
  draftData: Partial<FormTemplate>
): Promise<FormTemplateDraft> {
  const response = await API.put<ApiResponse<FormTemplateDraft>>(
    `${BASE_URL}/${templateId}/draft`,
    { draft_data: draftData }
  );
  return response.data.data;
}

/**
 * Удалить черновик
 */
export async function deleteTemplateDraft(templateId: string): Promise<void> {
  await API.delete(`${BASE_URL}/${templateId}/draft`);
}

/**
 * Создать новый черновик (без существующего шаблона)
 */
export async function createNewDraft(
  documentModeId: string,
  draftData: Partial<FormTemplate>
): Promise<FormTemplateDraft> {
  const response = await API.post<ApiResponse<FormTemplateDraft>>(`${BASE_URL}/drafts`, {
    document_mode_id: documentModeId,
    draft_data: draftData,
  });
  return response.data.data;
}

/**
 * Получить все черновики пользователя
 */
export async function getUserDrafts(): Promise<FormTemplateDraft[]> {
  const response = await API.get<ApiResponse<FormTemplateDraft[]>>(`${BASE_URL}/drafts`);
  return response.data.data;
}

// =============================================================================
// Save Sections (Form Builder)
// =============================================================================

interface SaveSectionsResponse {
  success: boolean;
  message: string;
  sections_count: number;
}

/**
 * Save sections to form definition (Form Builder)
 */
export async function saveSections(
  documentModeId: string,
  sections: FormSectionConfig[]
): Promise<SaveSectionsResponse> {
  const response = await API.put<SaveSectionsResponse>(
    `/declarant/form-definitions/${documentModeId}/sections`,
    { sections }
  );
  return response.data;
}

interface SaveFormWidthResponse {
  success: boolean;
  message: string;
  form_width: number;
}

/**
 * Save form width to form definition (Form Builder)
 */
export async function saveFormWidth(
  documentModeId: string,
  formWidth: number
): Promise<SaveFormWidthResponse> {
  const response = await API.put<SaveFormWidthResponse>(
    `/declarant/form-definitions/${documentModeId}/width`,
    { form_width: formWidth }
  );
  return response.data;
}

// =============================================================================
// Schema Fields API
// =============================================================================

interface FormSectionFieldConfig {
  id: string;
  schemaPath: string;
  customLabel?: string;
  customPlaceholder?: string;
  customHint?: string;
  prompt?: string;
  width: string;
  order: number;
  readonly?: boolean;
  defaultValue?: any;
  required?: boolean;
  isSelect?: boolean;           // Флаг: рендерить как select
  selectOptions?: Array<{       // Опции для select
    label: string;
    value: string;
  }>;
}

interface FormSectionData {
  section_key: string;
  title_ru: string;
  description_ru: string;
  icon: string;
  sort_order: number;
  field_paths: string[];
  fields_config: FormSectionFieldConfig[];
  columns: number;
  collapsible: boolean;
  default_expanded: boolean;
}

interface FormDefinitionResponse {
  id: string;
  document_mode_id: string;
  gf_code: string;
  type_name: string;
  fields: FieldDefinition[];
  sections: FormSectionData[];
  default_values: Record<string, any>;
  version: number;
  form_width: number;  // Ширина формы в % (70-130)
}

/**
 * Получить поля схемы для document mode
 * Использует существующий API form-definitions
 * Если форма не найдена - автоматически синхронизирует из Kontur API
 */
export async function getSchemaFields(documentModeId: string): Promise<FieldDefinition[]> {
  try {
    console.log('[API] Fetching schema fields for:', documentModeId);
    const response = await API.get<FormDefinitionResponse>(
      `/declarant/form-definitions/${documentModeId}`
    );
    console.log('[API] Response:', {
      status: response.status,
      dataKeys: Object.keys(response.data || {}),
      fieldsCount: response.data?.fields?.length,
      firstField: response.data?.fields?.[0],
    });
    return response.data.fields || [];
  } catch (error: any) {
    console.error('[API] Error fetching schema fields:', error);

    // Если форма не найдена - пробуем синхронизировать
    if (error.response?.status === 404) {
      console.log('[API] Form definition not found, trying to sync...');
      try {
        // Синхронизируем одну форму
        await API.post(`/declarant/form-definitions/${documentModeId}/sync`);
        console.log('[API] Sync completed, fetching again...');

        // Пробуем получить снова
        const retryResponse = await API.get<FormDefinitionResponse>(
          `/declarant/form-definitions/${documentModeId}`
        );
        console.log('[API] Retry response:', {
          fieldsCount: retryResponse.data?.fields?.length,
        });
        return retryResponse.data.fields || [];
      } catch (syncError: any) {
        console.error('[API] Sync failed:', syncError);
        return [];
      }
    }
    throw error;
  }
}

/**
 * Получить полную форму (поля + секции с конфигурациями)
 * Используется для Form Builder чтобы восстановить сохранённое состояние
 */
export async function getFormDefinition(documentModeId: string): Promise<FormDefinitionResponse | null> {
  try {
    console.log('[API] Fetching full form definition for:', documentModeId);
    const response = await API.get<FormDefinitionResponse>(
      `/declarant/form-definitions/${documentModeId}`
    );
    console.log('[API] Full form response:', {
      fieldsCount: response.data?.fields?.length,
      sectionsCount: response.data?.sections?.length,
      sections: response.data?.sections?.map(s => ({
        key: s.section_key,
        fieldsConfigCount: s.fields_config?.length
      })),
    });
    return response.data;
  } catch (error: any) {
    console.error('[API] Error fetching form definition:', error);

    // Если форма не найдена - пробуем синхронизировать
    if (error.response?.status === 404) {
      console.log('[API] Form definition not found, trying to sync...');
      try {
        await API.post(`/declarant/form-definitions/${documentModeId}/sync`);
        const retryResponse = await API.get<FormDefinitionResponse>(
          `/declarant/form-definitions/${documentModeId}`
        );
        return retryResponse.data;
      } catch (syncError: any) {
        console.error('[API] Sync failed:', syncError);
        return null;
      }
    }
    return null;
  }
}

/**
 * Получить список доступных document modes
 */
export async function getAvailableDocumentModes(): Promise<
  Array<{ id: string; name: string; description?: string }>
> {
  try {
    const response = await API.get<{ items: Array<{ document_mode_id: string; type_name: string }> }>(
      '/declarant/form-definitions'
    );
    return response.data.items.map(item => ({
      id: item.document_mode_id,
      name: item.type_name,
    }));
  } catch (error) {
    console.error('Error fetching document modes:', error);
    return [];
  }
}

// =============================================================================
// Export/Import
// =============================================================================

/**
 * Экспортировать шаблон в JSON
 */
export async function exportTemplate(templateId: string): Promise<Blob> {
  const response = await API.get(`${BASE_URL}/${templateId}/export`, {
    responseType: 'blob',
  });
  return response.data;
}

/**
 * Импортировать шаблон из JSON
 */
export async function importTemplate(file: File): Promise<FormTemplate> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await API.post<ApiResponse<FormTemplate>>(`${BASE_URL}/import`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data.data;
}

/**
 * Валидировать JSON перед импортом
 */
export async function validateImport(
  file: File
): Promise<{ valid: boolean; errors?: string[]; preview?: Partial<FormTemplate> }> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await API.post<
    ApiResponse<{ valid: boolean; errors?: string[]; preview?: Partial<FormTemplate> }>
  >(`${BASE_URL}/import/validate`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data.data;
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Скачать экспортированный шаблон
 */
export async function downloadTemplateExport(templateId: string, templateName: string): Promise<void> {
  const blob = await exportTemplate(templateId);
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${templateName.replace(/\s+/g, '_')}_template.json`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

/**
 * Автосохранение черновика (debounced)
 */
let autoSaveTimeout: NodeJS.Timeout | null = null;

export function autoSaveDraft(
  templateId: string,
  draftData: Partial<FormTemplate>,
  delay: number = 2000
): Promise<FormTemplateDraft> {
  return new Promise((resolve, reject) => {
    if (autoSaveTimeout) {
      clearTimeout(autoSaveTimeout);
    }

    autoSaveTimeout = setTimeout(async () => {
      try {
        const result = await saveTemplateDraft(templateId, draftData);
        resolve(result);
      } catch (error) {
        reject(error);
      }
    }, delay);
  });
}

/**
 * Отменить автосохранение
 */
export function cancelAutoSave(): void {
  if (autoSaveTimeout) {
    clearTimeout(autoSaveTimeout);
    autoSaveTimeout = null;
  }
}

// =============================================================================
// Form Definition Versions API
// =============================================================================

const DEFINITIONS_URL = '/declarant/form-definitions';

export interface FormDefinitionVersion {
  id: string;
  version_number: number;
  version_label: string | null;
  change_description: string | null;
  fields_count: number;
  sections_count: number;
  created_at: string | null;
  is_current: boolean;
}

interface VersionsListResponse {
  items: FormDefinitionVersion[];
  total: number;
}

interface CreateVersionRequest {
  version_label?: string;
  change_description?: string;
}

/**
 * Получить список версий формы
 */
export async function getFormVersions(documentModeId: string): Promise<FormDefinitionVersion[]> {
  const response = await API.get<VersionsListResponse>(
    `${DEFINITIONS_URL}/${documentModeId}/versions`
  );
  return response.data.items;
}

/**
 * Создать новую версию
 */
export async function createFormVersion(
  documentModeId: string,
  versionLabel?: string,
  changeDescription?: string
): Promise<FormDefinitionVersion> {
  const response = await API.post<FormDefinitionVersion>(
    `${DEFINITIONS_URL}/${documentModeId}/versions`,
    {
      version_label: versionLabel,
      change_description: changeDescription,
    }
  );
  return response.data;
}

/**
 * Получить конкретную версию с данными секций
 */
export async function getFormVersion(
  documentModeId: string,
  versionNumber: number
): Promise<FormDefinitionVersion & { sections_snapshot: any[] }> {
  const response = await API.get(
    `${DEFINITIONS_URL}/${documentModeId}/versions/${versionNumber}`
  );
  return response.data;
}

/**
 * Восстановить версию
 */
export async function restoreFormVersion(
  documentModeId: string,
  versionNumber: number
): Promise<{ success: boolean; message: string; version_number: number }> {
  const response = await API.post(
    `${DEFINITIONS_URL}/${documentModeId}/versions/${versionNumber}/restore`
  );
  return response.data;
}

/**
 * Удалить версию
 */
export async function deleteFormVersion(
  documentModeId: string,
  versionNumber: number
): Promise<{ success: boolean; message: string }> {
  const response = await API.delete(
    `${DEFINITIONS_URL}/${documentModeId}/versions/${versionNumber}`
  );
  return response.data;
}
