// =============================================================================
// Form Builder Types - Типы для конструктора форм
// =============================================================================

import type { FieldDefinition } from './form-definitions';

// =============================================================================
// Условная логика (Conditional Logic)
// =============================================================================

export type ConditionOperator =
  | 'equals'
  | 'not_equals'
  | 'contains'
  | 'not_contains'
  | 'greater_than'
  | 'less_than'
  | 'is_empty'
  | 'is_not_empty';

export interface FieldCondition {
  id: string;
  sourceFieldPath: string;
  operator: ConditionOperator;
  value: unknown;
}

export interface ConditionalLogic {
  conditions: FieldCondition[];
  logic: 'AND' | 'OR';
  action: 'show' | 'hide' | 'enable' | 'disable' | 'set_required';
}

// =============================================================================
// Валидация
// =============================================================================

export interface ValidationRules {
  minValue?: number;
  maxValue?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  patternMessage?: string;
}

// =============================================================================
// Конфигурация поля в форме
// =============================================================================

export type FieldWidth = 'full' | 'three-quarters' | 'two-thirds' | 'half' | 'third' | 'quarter';

// Опция для поля типа список (select)
export interface SelectOption {
  label: string;   // Отображаемое название (например "Мужской")
  value: string;   // Значение для сохранения (например "0")
}

export interface FormFieldConfig {
  id: string;
  schemaPath: string;              // JSON path из схемы (например "ContractTerms.Amount")
  customLabel?: string;            // Переопределенный label
  customPlaceholder?: string;
  customHint?: string;
  prompt?: string;                 // Промпт для извлечения переменных
  width: FieldWidth;
  order: number;
  conditionalLogic?: ConditionalLogic;
  customValidation?: ValidationRules;
  defaultValue?: unknown;
  readonly?: boolean;
  hidden?: boolean;
  required?: boolean;              // Переопределение обязательности (если не задано - берётся из схемы)
  isSelect?: boolean;              // Флаг что поле является списком (select)
  selectOptions?: SelectOption[];  // Опции для списка
}

// =============================================================================
// Секция формы
// =============================================================================

export interface FormSectionConfig {
  id: string;
  key: string;                     // Уникальный ключ секции
  titleRu: string;
  descriptionRu?: string;
  icon: string;                    // Lucide icon name
  order: number;
  columns: 1 | 2 | 3 | 4;
  collapsible: boolean;
  defaultExpanded: boolean;
  fields: FormFieldConfig[];
  conditionalLogic?: ConditionalLogic;
}

// =============================================================================
// Шаблон формы
// =============================================================================

export type TemplateStatus = 'draft' | 'published' | 'archived';

export interface FormTemplate {
  id: string;
  name: string;
  description?: string;
  documentModeId: string;          // Связь с JSON схемой
  gfCode: string;
  typeName: string;

  // Версионирование
  version: number;
  versionLabel?: string;
  isDraft: boolean;
  isPublished: boolean;
  publishedAt?: string;
  status: TemplateStatus;          // Статус шаблона

  // Конфигурация формы
  sections: FormSectionConfig[];
  defaultValues: Record<string, unknown>;

  // Метаданные
  createdAt: string;
  updatedAt: string;
  createdBy: string;
  updatedBy?: string;
  usageCount: number;
  lastUsedAt?: string;
}

// =============================================================================
// Версия шаблона
// =============================================================================

export interface FormTemplateVersion {
  id: string;
  templateId: string;
  version: number;
  versionLabel?: string;
  sectionsSnapshot: FormSectionConfig[];
  defaultValuesSnapshot: Record<string, unknown>;
  createdAt: string;
  createdBy: string;
  changeDescription?: string;
}

// =============================================================================
// Черновик
// =============================================================================

export interface FormTemplateDraft {
  id: string;
  templateId?: string;
  documentModeId?: string;
  userId: string;
  draftData: Partial<FormTemplate>;
  createdAt: string;
  updatedAt: string;
}

// =============================================================================
// История изменений (Undo/Redo)
// =============================================================================

export type HistoryActionType =
  | 'field_added'
  | 'field_removed'
  | 'field_moved'
  | 'field_modified'
  | 'section_added'
  | 'section_removed'
  | 'section_modified'
  | 'section_reordered'
  | 'bulk_action';

export interface HistoryEntry {
  id: string;
  actionType: HistoryActionType;
  description: string;
  timestamp: string;
  beforeState: FormSectionConfig[];
  afterState: FormSectionConfig[];
}

// =============================================================================
// Drag and Drop
// =============================================================================

export type DragItemType = 'schema-field' | 'canvas-field' | 'section';

export interface DragItem {
  type: DragItemType;
  id: string;
  data: FieldDefinition | FormFieldConfig | FormSectionConfig;
  sourceSection?: string;
}

export interface DropTarget {
  type: 'section' | 'canvas' | 'field-position';
  sectionId?: string;
  index?: number;
}

// =============================================================================
// Builder State
// =============================================================================

export type BuilderTab = 'structure' | 'preview' | 'history' | 'versions';
export type PreviewMode = 'desktop' | 'tablet' | 'mobile';

export interface FormBuilderState {
  // Основные данные
  template: FormTemplate | null;
  schemaFields: FieldDefinition[];     // Все поля из JSON схемы

  // Выбор
  selectedSectionId: string | null;
  selectedFieldId: string | null;

  // UI
  activeTab: BuilderTab;
  previewMode: PreviewMode;
  leftPanelWidth: number;
  rightPanelWidth: number;

  // Drag and Drop
  draggedItem: DragItem | null;
  dropTarget: DropTarget | null;

  // История (Undo/Redo)
  history: HistoryEntry[];
  historyIndex: number;

  // Состояние
  isDirty: boolean;
  isSaving: boolean;
  isLoading: boolean;

  // Дерево схемы
  schemaSearchQuery: string;
  expandedNodes: Set<string>;

  // Ошибки
  validationErrors: ValidationError[];

  // Загруженная версия (для отображения в заголовке)
  loadedVersionLabel: string | null;
}

// =============================================================================
// Валидация конфигурации
// =============================================================================

export interface ValidationError {
  type: 'error' | 'warning';
  path: string;
  message: string;
}

// =============================================================================
// API Types
// =============================================================================

export interface FormTemplateListItem {
  id: string;
  name: string;
  documentModeId: string;
  typeName: string;
  version: number;
  isPublished: boolean;
  updatedAt: string;
  usageCount: number;
}

export interface CreateFormTemplateRequest {
  name: string;
  description?: string;
  documentModeId: string;
  gfCode: string;
  typeName: string;
  sections: FormSectionConfig[];
  defaultValues?: Record<string, unknown>;
}

export interface UpdateFormTemplateRequest {
  name?: string;
  description?: string;
  sections?: FormSectionConfig[];
  defaultValues?: Record<string, unknown>;
  versionLabel?: string;
}

export interface CreateVersionRequest {
  versionLabel?: string;
  changeDescription?: string;
}
