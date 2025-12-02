// =============================================================================
// Form Builder Store - Zustand store для конструктора форм
// =============================================================================

import { create } from 'zustand';
import { produce } from 'immer';
import { v4 as uuidv4 } from 'uuid';
import type {
  FormBuilderState,
  FormTemplate,
  FormSectionConfig,
  FormFieldConfig,
  HistoryEntry,
  DragItem,
  DropTarget,
  BuilderTab,
  PreviewMode,
  FieldWidth,
} from '../types/form-builder';
import type { FieldDefinition } from '../types/form-definitions';

// =============================================================================
// Store Actions Interface
// =============================================================================

interface FormBuilderActions {
  // Initialization
  initBuilder: (template: FormTemplate | null, schemaFields: FieldDefinition[]) => void;
  resetBuilder: () => void;

  // Template actions
  setTemplate: (template: FormTemplate) => void;
  updateTemplateMeta: (updates: Partial<Pick<FormTemplate, 'name' | 'description'>>) => void;

  // Section actions
  addSection: (section: Omit<FormSectionConfig, 'id' | 'order' | 'fields'>) => void;
  updateSection: (sectionId: string, updates: Partial<FormSectionConfig>) => void;
  removeSection: (sectionId: string) => void;
  reorderSections: (fromIndex: number, toIndex: number) => void;

  // Field actions
  addFieldToSection: (sectionId: string, schemaPath: string, index?: number) => void;
  updateField: (sectionId: string, fieldId: string, updates: Partial<FormFieldConfig>) => void;
  updateFieldInSection: (sectionId: string, fieldId: string, updates: Partial<FormFieldConfig>) => void;
  removeFieldFromSection: (sectionId: string, fieldId: string) => void;
  moveField: (fromSectionId: string, toSectionId: string, fieldId: string, toIndex: number) => void;
  reorderFieldsInSection: (sectionId: string, fromIndex: number, toIndex: number) => void;

  // Selection
  selectSection: (sectionId: string | null) => void;
  selectField: (fieldId: string | null) => void;

  // UI State
  setActiveTab: (tab: BuilderTab) => void;
  setPreviewMode: (mode: PreviewMode) => void;
  setPanelWidths: (left: number, right: number) => void;

  // Drag and Drop
  setDraggedItem: (item: DragItem | null) => void;
  setDropTarget: (target: DropTarget | null) => void;

  // Schema tree
  setSchemaSearchQuery: (query: string) => void;
  toggleNodeExpanded: (path: string) => void;
  expandAllNodes: () => void;
  collapseAllNodes: () => void;

  // History (Undo/Redo)
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;

  // State management
  setIsDirty: (dirty: boolean) => void;
  setIsSaving: (saving: boolean) => void;
  setIsLoading: (loading: boolean) => void;

  // Helpers
  getFieldByPath: (schemaPath: string) => FieldDefinition | undefined;
  isFieldUsed: (schemaPath: string) => boolean;
  getUsedFieldPaths: () => Set<string>;

  // Debug import
  addFieldsFromJson: (json: Record<string, unknown>) => number;

  // Version label
  setLoadedVersionLabel: (label: string | null) => void;
  clearLoadedVersionLabel: () => void;
}

// =============================================================================
// Initial State
// =============================================================================

// Загрузка сохранённых размеров панелей
const getSavedPanelWidths = () => {
  try {
    const left = localStorage.getItem('formBuilder.leftPanelWidth');
    const right = localStorage.getItem('formBuilder.rightPanelWidth');
    return {
      left: left ? parseInt(left, 10) : 280,
      right: right ? parseInt(right, 10) : 320,
    };
  } catch {
    return { left: 280, right: 320 };
  }
};

const savedWidths = getSavedPanelWidths();

// Загрузка сохранённой версии из localStorage (после reload при загрузке версии)
const getSavedVersionLabel = (): string | null => {
  try {
    const label = localStorage.getItem('formBuilder.loadedVersionLabel');
    if (label) {
      // Очищаем после чтения (одноразовое использование)
      localStorage.removeItem('formBuilder.loadedVersionLabel');
      return label;
    }
    return null;
  } catch {
    return null;
  }
};

const initialState: FormBuilderState = {
  template: null,
  schemaFields: [],
  selectedSectionId: null,
  selectedFieldId: null,
  activeTab: 'structure',
  previewMode: 'desktop',
  leftPanelWidth: savedWidths.left,
  rightPanelWidth: savedWidths.right,
  draggedItem: null,
  dropTarget: null,
  history: [],
  historyIndex: -1,
  isDirty: false,
  isSaving: false,
  isLoading: false,
  schemaSearchQuery: '',
  expandedNodes: new Set(),
  validationErrors: [],
  loadedVersionLabel: getSavedVersionLabel(),
};

// =============================================================================
// Store
// =============================================================================

export const useFormBuilderStore = create<FormBuilderState & FormBuilderActions>((set, get) => ({
  ...initialState,

  // =========================================================================
  // Initialization
  // =========================================================================

  initBuilder: (template, schemaFields) => {
    console.log('[Store] initBuilder called:', {
      templateId: template?.id,
      templateName: template?.name,
      schemaFieldsCount: schemaFields?.length,
      schemaFieldsFirst: schemaFields?.[0],
    });

    // Собираем все пути для expandedNodes
    const allPaths = new Set<string>();
    const collectPaths = (fields: FieldDefinition[], parentPath = '') => {
      for (const field of fields) {
        const path = parentPath ? `${parentPath}.${field.name}` : field.name;
        if (field.children && field.children.length > 0) {
          allPaths.add(path);
          collectPaths(field.children, path);
        }
      }
    };
    collectPaths(schemaFields || []);

    set({
      template,
      schemaFields,
      selectedSectionId: template?.sections[0]?.id || null,
      selectedFieldId: null,
      history: [],
      historyIndex: -1,
      isDirty: false,
      expandedNodes: allPaths,
      isLoading: false,
    });
  },

  resetBuilder: () => set(initialState),

  // =========================================================================
  // Template actions
  // =========================================================================

  setTemplate: (template) => set({ template, isDirty: false }),

  updateTemplateMeta: (updates) =>
    set(
      produce((state: FormBuilderState) => {
        if (state.template) {
          Object.assign(state.template, updates);
          state.isDirty = true;
        }
      })
    ),

  // =========================================================================
  // Section actions
  // =========================================================================

  addSection: (sectionData) => {
    const state = get();
    const newSection: FormSectionConfig = {
      ...sectionData,
      id: uuidv4(),
      order: state.template?.sections.length || 0,
      fields: [],
    };

    set(
      produce((draft: FormBuilderState) => {
        if (draft.template) {
          // Save history
          draft.history = draft.history.slice(0, draft.historyIndex + 1);
          draft.history.push({
            id: uuidv4(),
            actionType: 'section_added',
            description: `Добавлена секция "${sectionData.titleRu}"`,
            timestamp: new Date().toISOString(),
            beforeState: [...draft.template.sections],
            afterState: [...draft.template.sections, newSection],
          });
          draft.historyIndex = draft.history.length - 1;

          draft.template.sections.push(newSection);
          draft.selectedSectionId = newSection.id;
          draft.isDirty = true;
        }
      })
    );
  },

  updateSection: (sectionId, updates) =>
    set(
      produce((draft: FormBuilderState) => {
        if (draft.template) {
          const section = draft.template.sections.find((s) => s.id === sectionId);
          if (section) {
            Object.assign(section, updates);
            draft.isDirty = true;
          }
        }
      })
    ),

  removeSection: (sectionId) =>
    set(
      produce((draft: FormBuilderState) => {
        if (draft.template) {
          const index = draft.template.sections.findIndex((s) => s.id === sectionId);
          if (index !== -1) {
            const removed = draft.template.sections[index];

            // Save history
            draft.history = draft.history.slice(0, draft.historyIndex + 1);
            draft.history.push({
              id: uuidv4(),
              actionType: 'section_removed',
              description: `Удалена секция "${removed.titleRu}"`,
              timestamp: new Date().toISOString(),
              beforeState: [...draft.template.sections],
              afterState: draft.template.sections.filter((s) => s.id !== sectionId),
            });
            draft.historyIndex = draft.history.length - 1;

            draft.template.sections.splice(index, 1);

            // Update orders
            draft.template.sections.forEach((s, i) => {
              s.order = i;
            });

            // Clear selection if removed section was selected
            if (draft.selectedSectionId === sectionId) {
              draft.selectedSectionId = draft.template.sections[0]?.id || null;
              draft.selectedFieldId = null;
            }
            draft.isDirty = true;
          }
        }
      })
    ),

  reorderSections: (fromIndex, toIndex) =>
    set(
      produce((draft: FormBuilderState) => {
        if (draft.template && fromIndex !== toIndex) {
          const [moved] = draft.template.sections.splice(fromIndex, 1);
          draft.template.sections.splice(toIndex, 0, moved);

          // Update orders
          draft.template.sections.forEach((s, i) => {
            s.order = i;
          });
          draft.isDirty = true;
        }
      })
    ),

  // =========================================================================
  // Field actions
  // =========================================================================

  addFieldToSection: (sectionId, schemaPath, index) => {
    const state = get();
    const schemaField = state.getFieldByPath(schemaPath);
    if (!schemaField) return;

    const newField: FormFieldConfig = {
      id: uuidv4(),
      schemaPath,
      width: 'half' as FieldWidth,
      order: 0,
    };

    set(
      produce((draft: FormBuilderState) => {
        if (draft.template) {
          const section = draft.template.sections.find((s) => s.id === sectionId);
          if (section) {
            const insertIndex = index ?? section.fields.length;
            section.fields.splice(insertIndex, 0, newField);

            // Update orders
            section.fields.forEach((f, i) => {
              f.order = i;
            });

            // Save history
            draft.history = draft.history.slice(0, draft.historyIndex + 1);
            draft.history.push({
              id: uuidv4(),
              actionType: 'field_added',
              description: `Добавлено поле "${schemaField.label_ru || schemaField.name}"`,
              timestamp: new Date().toISOString(),
              beforeState: [...draft.template.sections],
              afterState: draft.template.sections.map((s) => ({ ...s, fields: [...s.fields] })),
            });
            draft.historyIndex = draft.history.length - 1;

            draft.selectedFieldId = newField.id;
            draft.isDirty = true;
          }
        }
      })
    );
  },

  updateField: (sectionId, fieldId, updates) =>
    set(
      produce((draft: FormBuilderState) => {
        if (draft.template) {
          const section = draft.template.sections.find((s) => s.id === sectionId);
          if (section) {
            const field = section.fields.find((f) => f.id === fieldId);
            if (field) {
              Object.assign(field, updates);
              draft.isDirty = true;
            }
          }
        }
      })
    ),

  // Alias for updateField (same functionality)
  updateFieldInSection: (sectionId, fieldId, updates) =>
    set(
      produce((draft: FormBuilderState) => {
        if (draft.template) {
          const section = draft.template.sections.find((s) => s.id === sectionId);
          if (section) {
            const field = section.fields.find((f) => f.id === fieldId);
            if (field) {
              Object.assign(field, updates);
              draft.isDirty = true;
            }
          }
        }
      })
    ),

  removeFieldFromSection: (sectionId, fieldId) =>
    set(
      produce((draft: FormBuilderState) => {
        if (draft.template) {
          const section = draft.template.sections.find((s) => s.id === sectionId);
          if (section) {
            const index = section.fields.findIndex((f) => f.id === fieldId);
            if (index !== -1) {
              section.fields.splice(index, 1);

              // Update orders
              section.fields.forEach((f, i) => {
                f.order = i;
              });

              // Clear selection if removed field was selected
              if (draft.selectedFieldId === fieldId) {
                draft.selectedFieldId = null;
              }
              draft.isDirty = true;
            }
          }
        }
      })
    ),

  moveField: (fromSectionId, toSectionId, fieldId, toIndex) =>
    set(
      produce((draft: FormBuilderState) => {
        if (draft.template) {
          const fromSection = draft.template.sections.find((s) => s.id === fromSectionId);
          const toSection = draft.template.sections.find((s) => s.id === toSectionId);

          if (fromSection && toSection) {
            const fieldIndex = fromSection.fields.findIndex((f) => f.id === fieldId);
            if (fieldIndex !== -1) {
              const [field] = fromSection.fields.splice(fieldIndex, 1);
              toSection.fields.splice(toIndex, 0, field);

              // Update orders in both sections
              fromSection.fields.forEach((f, i) => {
                f.order = i;
              });
              toSection.fields.forEach((f, i) => {
                f.order = i;
              });

              draft.isDirty = true;
            }
          }
        }
      })
    ),

  reorderFieldsInSection: (sectionId, fromIndex, toIndex) =>
    set(
      produce((draft: FormBuilderState) => {
        if (draft.template && fromIndex !== toIndex) {
          const section = draft.template.sections.find((s) => s.id === sectionId);
          if (section) {
            const [moved] = section.fields.splice(fromIndex, 1);
            section.fields.splice(toIndex, 0, moved);

            // Update orders
            section.fields.forEach((f, i) => {
              f.order = i;
            });
            draft.isDirty = true;
          }
        }
      })
    ),

  // =========================================================================
  // Selection
  // =========================================================================

  selectSection: (sectionId) =>
    set({
      selectedSectionId: sectionId,
      selectedFieldId: null,
    }),

  selectField: (fieldId) => set({ selectedFieldId: fieldId }),

  // =========================================================================
  // UI State
  // =========================================================================

  setActiveTab: (tab) => set({ activeTab: tab }),
  setPreviewMode: (mode) => set({ previewMode: mode }),
  setPanelWidths: (left, right) => {
    // Сохраняем в localStorage
    try {
      localStorage.setItem('formBuilder.leftPanelWidth', String(left));
      localStorage.setItem('formBuilder.rightPanelWidth', String(right));
    } catch {
      // Игнорируем ошибки localStorage
    }
    set({ leftPanelWidth: left, rightPanelWidth: right });
  },

  // =========================================================================
  // Drag and Drop
  // =========================================================================

  setDraggedItem: (item) => set({ draggedItem: item }),
  setDropTarget: (target) => set({ dropTarget: target }),

  // =========================================================================
  // Schema tree
  // =========================================================================

  setSchemaSearchQuery: (query) => set({ schemaSearchQuery: query }),

  toggleNodeExpanded: (path) => {
    const state = get();
    const newExpandedNodes = new Set(state.expandedNodes);
    if (newExpandedNodes.has(path)) {
      newExpandedNodes.delete(path);
    } else {
      newExpandedNodes.add(path);
    }
    set({ expandedNodes: newExpandedNodes });
  },

  expandAllNodes: () => {
    const state = get();
    const allPaths = new Set<string>();
    const collectPaths = (fields: FieldDefinition[], parentPath = '') => {
      for (const field of fields) {
        const path = parentPath ? `${parentPath}.${field.name}` : field.name;
        if (field.children && field.children.length > 0) {
          allPaths.add(path);
          collectPaths(field.children, path);
        }
      }
    };
    collectPaths(state.schemaFields);
    set({ expandedNodes: allPaths });
  },

  collapseAllNodes: () => set({ expandedNodes: new Set() }),

  // =========================================================================
  // History (Undo/Redo)
  // =========================================================================

  undo: () =>
    set(
      produce((draft: FormBuilderState) => {
        if (draft.historyIndex >= 0 && draft.template) {
          const entry = draft.history[draft.historyIndex];
          draft.template.sections = entry.beforeState;
          draft.historyIndex--;
          draft.isDirty = true;
        }
      })
    ),

  redo: () =>
    set(
      produce((draft: FormBuilderState) => {
        if (draft.historyIndex < draft.history.length - 1 && draft.template) {
          draft.historyIndex++;
          const entry = draft.history[draft.historyIndex];
          draft.template.sections = entry.afterState;
          draft.isDirty = true;
        }
      })
    ),

  canUndo: () => get().historyIndex >= 0,
  canRedo: () => get().historyIndex < get().history.length - 1,

  // =========================================================================
  // State management
  // =========================================================================

  setIsDirty: (dirty) => set({ isDirty: dirty }),
  setIsSaving: (saving) => set({ isSaving: saving }),
  setIsLoading: (loading) => set({ isLoading: loading }),

  // =========================================================================
  // Helpers
  // =========================================================================

  getFieldByPath: (schemaPath) => {
    const state = get();
    const parts = schemaPath.split('.');
    let current: FieldDefinition[] = state.schemaFields;
    let found: FieldDefinition | undefined;

    for (let i = 0; i < parts.length; i++) {
      found = current.find((f) => f.name === parts[i]);
      if (!found) return undefined;
      if (i < parts.length - 1 && found.children) {
        current = found.children;
      }
    }
    return found;
  },

  isFieldUsed: (schemaPath) => {
    const state = get();
    if (!state.template) return false;

    for (const section of state.template.sections) {
      if (section.fields.some((f) => f.schemaPath === schemaPath)) {
        return true;
      }
    }
    return false;
  },

  getUsedFieldPaths: () => {
    const state = get();
    const paths = new Set<string>();
    if (state.template) {
      for (const section of state.template.sections) {
        for (const field of section.fields) {
          paths.add(field.schemaPath);
        }
      }
    }
    return paths;
  },

  // =========================================================================
  // Debug import
  // =========================================================================

  addFieldsFromJson: (json: Record<string, unknown>) => {
    const state = get();
    if (!state.template) return 0;

    // Get existing paths
    const existingPaths = state.getUsedFieldPaths();

    // Recursively extract all paths from JSON
    const extractPaths = (obj: unknown, prefix = ''): string[] => {
      const paths: string[] = [];

      if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
        for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
          const path = prefix ? `${prefix}.${key}` : key;

          if (value && typeof value === 'object' && !Array.isArray(value)) {
            // For nested objects, add the path and recurse
            paths.push(...extractPaths(value, path));
          } else {
            // Leaf node - add the path
            paths.push(path);
          }
        }
      }

      return paths;
    };

    const jsonPaths = extractPaths(json);
    const newPaths = jsonPaths.filter((path) => !existingPaths.has(path));

    if (newPaths.length === 0) return 0;

    // Create or find "Import" section
    let importSectionId: string | null = null;

    set(
      produce((draft: FormBuilderState) => {
        if (!draft.template) return;

        // Find or create "Import" section
        let importSection = draft.template.sections.find(
          (s) => s.key === 'debug-import'
        );

        if (!importSection) {
          importSection = {
            id: uuidv4(),
            key: 'debug-import',
            titleRu: 'Импорт (Debug)',
            descriptionRu: 'Поля, импортированные из JSON документа',
            icon: 'Bug',
            order: draft.template.sections.length,
            columns: 2,
            collapsible: true,
            defaultExpanded: true,
            fields: [],
          };
          draft.template.sections.push(importSection);
        }

        importSectionId = importSection.id;

        // Add new fields
        for (const path of newPaths) {
          // Try to find in schema
          const schemaField = state.getFieldByPath(path);
          const pathParts = path.split('.');
          const fieldName = pathParts[pathParts.length - 1];

          const newField: FormFieldConfig = {
            id: uuidv4(),
            schemaPath: path,
            customLabel: schemaField?.label_ru || fieldName,
            width: 'half' as FieldWidth,
            order: importSection.fields.length,
          };

          importSection.fields.push(newField);
        }

        // Save history
        draft.history = draft.history.slice(0, draft.historyIndex + 1);
        draft.history.push({
          id: uuidv4(),
          actionType: 'fields_imported',
          description: `Импортировано ${newPaths.length} полей из JSON`,
          timestamp: new Date().toISOString(),
          beforeState: [...state.template!.sections],
          afterState: draft.template.sections.map((s) => ({ ...s, fields: [...s.fields] })),
        });
        draft.historyIndex = draft.history.length - 1;

        draft.isDirty = true;
      })
    );

    return newPaths.length;
  },

  // =========================================================================
  // Version label
  // =========================================================================

  setLoadedVersionLabel: (label) => set({ loadedVersionLabel: label }),
  clearLoadedVersionLabel: () => set({ loadedVersionLabel: null }),
}));
