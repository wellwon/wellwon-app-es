// =============================================================================
// Declarant API Client
// =============================================================================
// API functions for Declarant module
// Currently uses MOCK data for UI development
// Replace with real API calls when backend is ready

// Export Form Templates API
export * from './form-templates-api';

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

export interface DocflowResponse {
  id: string;
  version: number;
  state: number;
  type: number;
  procedure: number;
  singularity?: number;
  customs: number;
  name?: string;
  organization_id: string;
  employee_id: string;
  create_date?: string;
  update_date?: string;
}

/**
 * Create new docflow (пакет декларации) via Kontur API
 */
export async function createDocflow(request: CreateDocflowRequest): Promise<DocflowResponse> {
  const response = await fetch('/declarant/docflows', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Неизвестная ошибка' }));
    throw new Error(errorData.detail || `HTTP error: ${response.status}`);
  }

  return response.json();
}
