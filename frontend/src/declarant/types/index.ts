// =============================================================================
// Declarant Types - TypeScript definitions for Declarant module
// =============================================================================

import { LucideIcon } from 'lucide-react';

// Declarant Batch Status
export type DeclarantBatchStatus =
  | 'pending'      // Ожидает обработки
  | 'processing'   // В процессе обработки
  | 'completed'    // Завершено успешно
  | 'error';       // Ошибка обработки

// Declarant Batch
export interface DeclarantBatch {
  id: string;
  number: string;                    // Номер пакета (например: FTS-00104)
  status: DeclarantBatchStatus;
  documents_total: number;           // Всего документов в пакете
  documents_processed: number;       // Обработано документов
  extracts_count: number;            // Количество извлечений
  created_at: string;                // ISO datetime
  updated_at: string;                // ISO datetime
  error_message?: string;            // Сообщение об ошибке (если есть)
}

// Declarant Statistics
export interface DeclarantStats {
  total_batches: number;             // Всего пакетов
  completed_batches: number;         // Завершенных пакетов
  processing_batches: number;        // В обработке
  error_batches: number;             // С ошибками
  total_documents: number;           // Всего документов
}

// Create Batch Request
export interface CreateBatchRequest {
  documents: File[];                 // Загружаемые файлы
  template_id?: string;              // ID шаблона (опционально)
  priority?: 'low' | 'normal' | 'high';  // Приоритет обработки
  description?: string;              // Описание пакета
}

// Batch Document
export interface BatchDocument {
  id: string;
  batch_id: string;
  filename: string;
  file_size: number;
  status: 'pending' | 'processing' | 'completed' | 'error';
  processed_at?: string;
  error_message?: string;
}

// Batch Extract (результат извлечения данных)
export interface BatchExtract {
  id: string;
  batch_id: string;
  document_id: string;
  data: Record<string, any>;         // Извлеченные данные (JSON)
  confidence: number;                // Уверенность в данных (0-1)
  created_at: string;
}

// =============================================================================
// UI State Types (for Zustand store)
// =============================================================================

export type TableView = 'grid' | 'list';
export type SortOrder = 'asc' | 'desc';

export interface DeclarantUIState {
  // View preferences (persisted)
  tableView: TableView;
  sortOrder: SortOrder;
  selectedFilters: string[];

  // Temporary state
  selectedBatchIds: string[];
  draftBatch: Partial<CreateBatchRequest> | null;

  // Actions
  setTableView: (view: TableView) => void;
  setSortOrder: (order: SortOrder) => void;
  toggleFilter: (filter: string) => void;
  toggleBatchSelection: (id: string) => void;
  selectAllBatches: (ids: string[]) => void;
  clearSelection: () => void;
  setDraftBatch: (draft: Partial<CreateBatchRequest> | null) => void;
}

// =============================================================================
// API Response Types
// =============================================================================

export interface BatchListResponse {
  batches: DeclarantBatch[];
  total: number;
  page: number;
  page_size: number;
}

export interface BatchDetailResponse {
  batch: DeclarantBatch;
  documents: BatchDocument[];
  extracts: BatchExtract[];
}

export interface CreateBatchResponse {
  batch: DeclarantBatch;
  message: string;
}

export interface DeleteBatchResponse {
  success: boolean;
  message: string;
}

// =============================================================================
// Mock Data Interfaces (for development)
// =============================================================================

export interface MockBatch {
  id: string;
  number: string;
  status: DeclarantBatchStatus;
  docs: string;                      // Формат "3/3"
  extracts: number;
  date: string;                      // Formatted date string
  icon: LucideIcon;
  iconColor: string;
  statusText: string;
}
