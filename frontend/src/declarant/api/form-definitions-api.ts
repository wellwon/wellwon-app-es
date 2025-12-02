// =============================================================================
// Form Definitions API - API client for form definitions
// =============================================================================

import { API } from '@/api/core';
import type {
  FormDefinition,
  FormDefinitionsListResponse,
  SyncResultResponse,
} from '../types/form-definitions';

const API_BASE = '/declarant/form-definitions';

/**
 * Get list of all form definitions
 */
export async function getFormDefinitionsList(): Promise<FormDefinitionsListResponse> {
  const response = await API.get<FormDefinitionsListResponse>(API_BASE);
  return response.data;
}

/**
 * Get form definition by document_mode_id
 */
export async function getFormDefinition(documentModeId: string): Promise<FormDefinition> {
  const response = await API.get<FormDefinition>(`${API_BASE}/${documentModeId}`);
  return response.data;
}

/**
 * Sync all form definitions from Kontur API
 */
export async function syncAllFormDefinitions(): Promise<SyncResultResponse> {
  const response = await API.post<SyncResultResponse>(`${API_BASE}/sync`);
  return response.data;
}

/**
 * Sync single form definition from Kontur API
 */
export async function syncFormDefinition(documentModeId: string): Promise<SyncResultResponse> {
  const response = await API.post<SyncResultResponse>(`${API_BASE}/${documentModeId}/sync`);
  return response.data;
}

/**
 * Get raw Kontur schema for form definition
 */
export async function getRawSchema(documentModeId: string): Promise<{
  document_mode_id: string;
  schema_hash: string;
  schema: Record<string, unknown>;
}> {
  const response = await API.get(`${API_BASE}/${documentModeId}/schema`);
  return response.data;
}
