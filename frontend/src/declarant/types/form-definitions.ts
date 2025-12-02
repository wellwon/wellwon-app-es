// =============================================================================
// Form Definitions Types - TypeScript definitions for Universal Form Generator
// =============================================================================

// Field Types
export type FieldType =
  | 'text'
  | 'number'
  | 'date'
  | 'datetime'
  | 'select'
  | 'checkbox'
  | 'textarea'
  | 'object'
  | 'array';

// Field Option (for select fields)
export interface FieldOption {
  value: string;
  label: string;
}

// Field Definition
export interface FieldDefinition {
  path: string;           // "Contract.ContractDate"
  name: string;           // "ContractDate"
  field_type: FieldType;
  required: boolean;
  label_ru: string;       // "Дата договора"
  hint_ru?: string;
  placeholder_ru?: string;
  min_value?: number;
  max_value?: number;
  max_length?: number;
  options?: FieldOption[];
  pattern?: string;
  children?: FieldDefinition[];  // For object/array types
}

// Form Section
export interface FormSection {
  section_key: string;
  title_ru: string;
  description_ru?: string;
  icon: string;           // Lucide icon name
  sort_order: number;
  field_paths: string[];
  columns: number;
  collapsible: boolean;
  default_expanded: boolean;
}

// Complete Form Definition
export interface FormDefinition {
  id: string;
  document_mode_id: string;
  gf_code: string;
  type_name: string;
  fields: FieldDefinition[];
  sections: FormSection[];
  default_values: Record<string, unknown>;
  version: number;
}

// Form Definition List Item (for overview)
export interface FormDefinitionListItem {
  id: string;
  document_mode_id: string;
  gf_code: string;
  type_name: string;
  fields_count: number;
  version: number;
}

// Form State
export interface FormState {
  values: Record<string, unknown>;
  errors: Record<string, string>;
  touched: Record<string, boolean>;
  isDirty: boolean;
}

// API Response Types
export interface FormDefinitionsListResponse {
  items: FormDefinitionListItem[];
  total: number;
}

export interface SyncResultResponse {
  success: boolean;
  total_processed: number;
  forms_created: number;
  forms_updated: number;
  schemas_changed: number;
  errors: number;
  error_details: Array<{ document_mode_id?: string; error: string }>;
  sync_duration_ms: number;
  message: string;
}

// Props for field components
export interface FieldComponentProps {
  field: FieldDefinition;
  value: unknown;
  error?: string;
  onChange: (value: unknown) => void;
  onBlur: () => void;
  isDark: boolean;
  disabled?: boolean;
}
