// =============================================================================
// Declarant API Client
// =============================================================================
// API functions for Declarant module
// Currently uses MOCK data for UI development
// Replace with real API calls when backend is ready

// Export Form Templates API
export * from './form-templates-api';

import { API } from '@/api/core';
import { CheckCircle, AlertCircle } from 'lucide-react';
import type {
  DeclarantBatch,
  DeclarantStats,
  CreateBatchRequest,
  CreateBatchResponse,
  DeleteBatchResponse,
  MockBatch,
} from '../types';

// =============================================================================
// MOCK Data (from reference/ww_declarant/declarant_app.tsx)
// =============================================================================

export const MOCK_STATS: DeclarantStats = {
  total_batches: 6,
  completed_batches: 5,
  processing_batches: 0,
  error_batches: 1,
  total_documents: 55,
};

export const MOCK_BATCHES: MockBatch[] = [
  {
    id: '1',
    number: 'FTS-00104',
    status: 'completed',
    docs: '3/3',
    extracts: 3,
    date: '21 нояб. 2025, 11:25',
    icon: CheckCircle,
    iconColor: 'text-accent-green',
    statusText: 'Завершено',
  },
  {
    id: '2',
    number: 'FTS-00103',
    status: 'completed',
    docs: '4/4',
    extracts: 4,
    date: '14 нояб. 2025, 11:42',
    icon: CheckCircle,
    iconColor: 'text-accent-green',
    statusText: 'Завершено',
  },
  {
    id: '3',
    number: 'FTS-00102',
    status: 'error',
    docs: '0/3',
    extracts: 0,
    date: '09 нояб. 2025, 17:19',
    icon: AlertCircle,
    iconColor: 'text-accent-red',
    statusText: 'Ошибка',
  },
  {
    id: '4',
    number: 'FTS-00101',
    status: 'completed',
    docs: '3/3',
    extracts: 3,
    date: '09 нояб. 2025, 17:15',
    icon: CheckCircle,
    iconColor: 'text-accent-green',
    statusText: 'Завершено',
  },
  {
    id: '5',
    number: 'FTS-00100',
    status: 'completed',
    docs: '3/3',
    extracts: 3,
    date: '09 нояб. 2025, 09:58',
    icon: CheckCircle,
    iconColor: 'text-accent-green',
    statusText: 'Завершено',
  },
  {
    id: '6',
    number: 'FTS-00099',
    status: 'completed',
    docs: '3/3',
    extracts: 3,
    date: '09 нояб. 2025, 09:18',
    icon: CheckCircle,
    iconColor: 'text-accent-green',
    statusText: 'Завершено',
  },
];

// =============================================================================
// API Functions (STUB implementations)
// =============================================================================

/**
 * Get all batches
 * TODO: Replace with real API call when backend ready
 */
export async function getDeclarantBatches(): Promise<DeclarantBatch[]> {
  // MOCK: No delay - instant response
  // Convert MOCK_BATCHES to proper DeclarantBatch format
  return MOCK_BATCHES.map((batch) => ({
    id: batch.id,
    number: batch.number,
    status: batch.status,
    documents_total: parseInt(batch.docs.split('/')[1]),
    documents_processed: parseInt(batch.docs.split('/')[0]),
    extracts_count: batch.extracts,
    created_at: batch.date, // Keep original formatted date for mock
    updated_at: batch.date,
    error_message: batch.status === 'error' ? 'Ошибка обработки документов' : undefined,
  }));
}

/**
 * Get statistics
 * TODO: Replace with real API call when backend ready
 */
export async function getDeclarantStats(): Promise<DeclarantStats> {
  // MOCK: No delay - instant response
  return MOCK_STATS;
}

/**
 * Create new batch
 * TODO: Replace with real API call when backend ready
 */
export async function createDeclarantBatch(
  batchData: CreateBatchRequest
): Promise<CreateBatchResponse> {
  // Simulated API delay
  await new Promise((resolve) => setTimeout(resolve, 1000));

  // MOCK response
  const newBatch: DeclarantBatch = {
    id: `${Date.now()}`,
    number: `FTS-${String(Date.now()).slice(-5)}`,
    status: 'pending',
    documents_total: batchData.documents.length,
    documents_processed: 0,
    extracts_count: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  return {
    batch: newBatch,
    message: 'Пакет создан успешно',
  };
}

/**
 * Delete batch
 * TODO: Replace with real API call when backend ready
 */
export async function deleteDeclarantBatch(batchId: string): Promise<DeleteBatchResponse> {
  // Simulated API delay
  await new Promise((resolve) => setTimeout(resolve, 500));

  console.log('Deleting batch:', batchId);

  return {
    success: true,
    message: 'Пакет удален успешно',
  };
}

/**
 * Get batch by ID
 * TODO: Implement when needed
 */
export async function getDeclarantBatchById(batchId: string): Promise<DeclarantBatch | null> {
  const batches = await getDeclarantBatches();
  return batches.find((b) => b.id === batchId) || null;
}

// =============================================================================
// Docflow API (пакеты деклараций)
// =============================================================================

export interface CreateDocflowRequest {
  type: number;  // Declaration type: 0=ИМ, 1=ЭК, etc.
  procedure: number;  // Customs procedure ID
  customs: number;  // Customs office code
  organization_id: string;  // Organization UUID
  employee_id: string;  // Employee UUID
  singularity?: number;  // Optional singularity ID
  name?: string;  // Optional docflow name
}

export interface DocflowDocument {
  document_id: string;
  form_id: string;
  name: string;
  is_core: boolean;
  gfv?: string;
  doc_number?: string;
  state?: number;
}

export interface DocflowResponse {
  id: string;  // Kontur docflow ID
  ww_number: string;  // Our WW-XXXXXX number
  name?: string;
  declaration_type: number;
  procedure: number;
  status: number;
  org_name?: string;
  inn?: string;
  kpp?: string;
  gtd_number?: string;
  process_id?: string;
  created?: string;
  changed?: string;
  // Documents (returned from create endpoint)
  documents?: DocflowDocument[];
}

export interface DocflowDocumentsResponse {
  documents: DocflowDocument[];
}

// List response types
export interface DocflowListItem {
  id: string;  // Our internal UUID
  kontur_id: string;  // Kontur's UUID
  ww_number: string;  // Our WW-XXXXXX number
  name?: string;
  declaration_type: number;
  declaration_type_code: string;  // ИМ/ЭК/ТТ
  procedure: number;
  status: number;
  status_text?: string;
  org_name?: string;
  inn?: string;
  gtd_number?: string;
  documents_count: number;
  created_at?: string;
  updated_at?: string;
}

export interface DocflowListResponse {
  items: DocflowListItem[];
  total: number;
  skip: number;
  take: number;
}

export interface DocflowDetailResponse {
  id: string;  // Our internal UUID
  kontur_id: string;
  ww_number: string;
  name?: string;
  declaration_type: number;
  declaration_type_code: string;
  procedure: number;
  status: number;
  status_text?: string;
  customs_code?: number;
  org_name?: string;
  inn?: string;
  kpp?: string;
  employee_id?: string;
  gtd_number?: string;
  process_id?: string;
  documents: DocflowDocument[];
  kontur_created?: string;
  kontur_changed?: string;
  created_at?: string;
  updated_at?: string;
}

/**
 * Create new docflow (пакет декларации) via Kontur API
 * Backend now returns full response with documents and URLs
 */
export async function createDocflow(request: CreateDocflowRequest): Promise<DocflowResponse> {
  const response = await API.post<DocflowResponse>('/declarant/docflows', request);
  return response.data;
}

/**
 * Get documents list for a docflow
 */
export async function getDocflowDocuments(docflowId: string): Promise<DocflowDocumentsResponse> {
  const response = await API.get<DocflowDocumentsResponse>(`/declarant/docflows/${docflowId}/documents`);
  return response.data;
}

/**
 * List docflows from database with pagination and filtering
 */
export async function listDocflows(params?: {
  skip?: number;
  take?: number;
  declaration_type?: number;
  status?: number;
  search?: string;
}): Promise<DocflowListResponse> {
  const response = await API.get<DocflowListResponse>('/declarant/docflows', { params });
  return response.data;
}

/**
 * Get docflow by WW number (e.g., WW-123456)
 */
export async function getDocflowByWwNumber(wwNumber: string): Promise<DocflowDetailResponse> {
  const response = await API.get<DocflowDetailResponse>(`/declarant/docflows/by-ww/${wwNumber}`);
  return response.data;
}

/**
 * Get docflow by Kontur ID
 */
export async function getDocflowByKonturId(konturId: string): Promise<DocflowDetailResponse> {
  const response = await API.get<DocflowDetailResponse>(`/declarant/docflows/by-kontur/${konturId}`);
  return response.data;
}

/**
 * Delete docflow from database (only from our DB, not from Kontur)
 */
export async function deleteDocflow(konturId: string): Promise<{ success: boolean; message: string }> {
  const response = await API.delete<{ success: boolean; message: string }>(`/declarant/docflows/${konturId}`);
  return response.data;
}

// =============================================================================
// References API (Справочники)
// =============================================================================

export interface OrganizationItem {
  id: string;
  kontur_id: string;
  name?: string;
  inn?: string;
  kpp?: string;
  ogrn?: string;
  address?: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface OrganizationsListResponse {
  items: OrganizationItem[];
  total: number;
  last_updated?: string;
}

export interface EmployeeItem {
  id: string;
  kontur_id: string;
  organization_id?: string;
  surname?: string;
  name?: string;
  patronymic?: string;
  phone?: string;
  email?: string;
  auth_letter_date?: string;
  auth_letter_number?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmployeesListResponse {
  items: EmployeeItem[];
  total: number;
  last_updated?: string;
}

/**
 * Get all organizations from reference
 */
export async function getOrganizations(includeInactive = false): Promise<OrganizationsListResponse> {
  const response = await API.get<OrganizationsListResponse>('/declarant/references/organizations', {
    params: { include_inactive: includeInactive }
  });
  return response.data;
}

/**
 * Get all employees from reference
 */
export async function getEmployees(params?: {
  includeInactive?: boolean;
  organizationId?: string;
}): Promise<EmployeesListResponse> {
  const response = await API.get<EmployeesListResponse>('/declarant/references/employees', {
    params: {
      include_inactive: params?.includeInactive ?? false,
      organization_id: params?.organizationId
    }
  });
  return response.data;
}
