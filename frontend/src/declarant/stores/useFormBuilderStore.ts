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
  FormElementType,
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
  moveSection: (sectionId: string, direction: 'up' | 'down') => void;

  // Field actions
  addFieldToSection: (sectionId: string, schemaPath: string, index?: number) => void;
  addElementToSection: (sectionId: string, elementType: FormElementType, label: string, index?: number) => void;
  splitSection: (sectionId: string, atFieldIndex: number) => void;
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
  importedValues: Map<string, string>; // Temporary values from JSON import
  setImportedValues: (values: Map<string, string>) => void;
  clearImportedValues: () => void;

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

const initialState: FormBuilderState & { importedValues: Map<string, string> } = {
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
  importedValues: new Map(),
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

  moveSection: (sectionId, direction) =>
    set(
      produce((draft: FormBuilderState) => {
        if (!draft.template) return;

        const index = draft.template.sections.findIndex((s) => s.id === sectionId);
        if (index === -1) return;

        const newIndex = direction === 'up' ? index - 1 : index + 1;

        // Check bounds
        if (newIndex < 0 || newIndex >= draft.template.sections.length) return;

        // Swap sections
        const [moved] = draft.template.sections.splice(index, 1);
        draft.template.sections.splice(newIndex, 0, moved);

        // Update orders
        draft.template.sections.forEach((s, i) => {
          s.order = i;
        });
        draft.isDirty = true;
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

  addElementToSection: (sectionId, elementType, label, index) => {
    const newElement: FormFieldConfig = {
      id: uuidv4(),
      schemaPath: '__element__',
      elementType,
      customLabel: label,
      width: 'full' as FieldWidth,
      order: 0,
    };

    set(
      produce((draft: FormBuilderState) => {
        if (draft.template) {
          const section = draft.template.sections.find((s) => s.id === sectionId);
          if (section) {
            const insertIndex = index ?? section.fields.length;
            section.fields.splice(insertIndex, 0, newElement);

            // Update orders
            section.fields.forEach((f, i) => {
              f.order = i;
            });

            // Save history
            draft.history = draft.history.slice(0, draft.historyIndex + 1);
            draft.history.push({
              id: uuidv4(),
              actionType: 'field_added',
              description: `Добавлен элемент "${label}"`,
              timestamp: new Date().toISOString(),
              beforeState: [...draft.template.sections],
              afterState: draft.template.sections.map((s) => ({ ...s, fields: [...s.fields] })),
            });
            draft.historyIndex = draft.history.length - 1;

            draft.selectedFieldId = newElement.id;
            draft.isDirty = true;
          }
        }
      })
    );
  },

  splitSection: (sectionId, atFieldIndex) => {
    set(
      produce((draft: FormBuilderState) => {
        if (!draft.template) return;

        const sectionIndex = draft.template.sections.findIndex((s) => s.id === sectionId);
        if (sectionIndex === -1) return;

        const section = draft.template.sections[sectionIndex];
        if (atFieldIndex <= 0 || atFieldIndex >= section.fields.length) return;

        // Поля для новой секции (от atFieldIndex до конца)
        const fieldsForNewSection = section.fields.splice(atFieldIndex);

        // Обновляем порядок в оригинальной секции
        section.fields.forEach((f, i) => {
          f.order = i;
        });

        // Создаём новую секцию
        const newSection: FormSectionConfig = {
          id: uuidv4(),
          key: `section_${Date.now()}`,
          titleRu: `${section.titleRu} (продолжение)`,
          descriptionRu: '',
          icon: section.icon,
          order: sectionIndex + 1,
          columns: section.columns,
          collapsible: section.collapsible,
          defaultExpanded: section.defaultExpanded,
          fields: fieldsForNewSection.map((f, i) => ({ ...f, order: i })),
        };

        // Вставляем новую секцию после текущей
        draft.template.sections.splice(sectionIndex + 1, 0, newSection);

        // Обновляем порядок всех секций
        draft.template.sections.forEach((s, i) => {
          s.order = i;
        });

        // Save history
        draft.history = draft.history.slice(0, draft.historyIndex + 1);
        draft.history.push({
          id: uuidv4(),
          actionType: 'section_added',
          description: `Секция "${section.titleRu}" разделена`,
          timestamp: new Date().toISOString(),
          beforeState: [...draft.template.sections],
          afterState: draft.template.sections.map((s) => ({ ...s, fields: [...s.fields] })),
        });
        draft.historyIndex = draft.history.length - 1;

        draft.isDirty = true;
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

  importedValues: new Map(),

  setImportedValues: (values) => set({ importedValues: values }),

  clearImportedValues: () => set({ importedValues: new Map() }),

  addFieldsFromJson: (json: Record<string, unknown>) => {
    const state = get();
    if (!state.template) return 0;

    // Get existing paths
    const existingPaths = state.getUsedFieldPaths();

    // Human-readable section names mapping
    const sectionNames: Record<string, string> = {
      'DocumentID': 'Идентификатор документа',
      'CertNumber': 'Номер сертификата',
      'AddDeclaration': 'Дополнительная декларация',
      'OrganizationQuarantine': 'Карантинная организация',
      'DescriptionConsignment': 'Описание груза',
      'Consignee': 'Получатель',
      'Exporter': 'Экспортёр',
      'Packaging': 'Упаковка',
      'Desinfestation': 'Обеззараживание',
      'PlaceIssue': 'Место выдачи',
      'PersonSignature': 'Подпись',
      'RFOrganizationFeatures': 'Реквизиты организации',
      'LegalAddress': 'Юридический адрес',
      'default': 'Основные поля',
    };

    // Section icons mapping
    const sectionIcons: Record<string, string> = {
      'DocumentID': 'FileText',
      'CertNumber': 'FileCheck',
      'DescriptionConsignment': 'Package',
      'Consignee': 'Building2',
      'Exporter': 'Truck',
      'Packaging': 'Box',
      'Desinfestation': 'Shield',
      'PlaceIssue': 'MapPin',
      'PersonSignature': 'PenTool',
      'OrganizationQuarantine': 'AlertTriangle',
      'RFOrganizationFeatures': 'Briefcase',
      'LegalAddress': 'Home',
      'default': 'FileText',
    };

    // Collect all values for temporary display
    const importedValues = new Map<string, string>();

    // Group fields by section key
    interface FieldInfo {
      path: string;
      label: string;
      value: unknown;
    }

    interface SectionGroup {
      key: string;
      title: string;
      icon: string;
      order: number;
      fields: FieldInfo[];
    }

    const sections: Map<string, SectionGroup> = new Map();
    let sectionOrder = 0;

    // Recursively extract fields - each nested object becomes its own section
    const extractAndGroup = (
      obj: unknown,
      prefix = '',
      sectionKey = 'default',
      depth = 0
    ): void => {
      if (!obj || typeof obj !== 'object') return;

      // Handle arrays - take first element if it's an object
      if (Array.isArray(obj)) {
        if (obj.length > 0 && typeof obj[0] === 'object' && obj[0] !== null) {
          extractAndGroup(obj[0], prefix, sectionKey, depth);
        } else if (obj.length > 0) {
          // Array of primitives - add as single field
          if (!sections.has(sectionKey)) {
            sections.set(sectionKey, {
              key: sectionKey,
              title: sectionNames[sectionKey] || sectionKey,
              icon: sectionIcons[sectionKey] || 'FileText',
              order: sectionOrder++,
              fields: [],
            });
          }
          const section = sections.get(sectionKey)!;
          const pathParts = prefix.split('.');
          const fieldName = pathParts[pathParts.length - 1];
          const value = obj.map(v => String(v)).join(', ');

          section.fields.push({
            path: prefix,
            label: fieldName,
            value: obj,
          });

          // Store value for display
          importedValues.set(prefix, value);
        }
        return;
      }

      // Handle objects
      for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
        const path = prefix ? `${prefix}.${key}` : key;

        if (value && typeof value === 'object' && !Array.isArray(value)) {
          // This is a nested object - create a new section for it
          // Use the key as section name
          const nestedSectionKey = key;

          if (!sections.has(nestedSectionKey)) {
            sections.set(nestedSectionKey, {
              key: nestedSectionKey,
              title: sectionNames[nestedSectionKey] || nestedSectionKey,
              icon: sectionIcons[nestedSectionKey] || 'FileText',
              order: sectionOrder++,
              fields: [],
            });
          }

          // Recurse into nested object with new section key
          extractAndGroup(value, path, nestedSectionKey, depth + 1);
        } else if (Array.isArray(value)) {
          // Array field
          extractAndGroup(value, path, sectionKey, depth);
        } else {
          // Leaf node - add to current section
          if (!sections.has(sectionKey)) {
            sections.set(sectionKey, {
              key: sectionKey,
              title: sectionNames[sectionKey] || sectionKey,
              icon: sectionIcons[sectionKey] || 'FileText',
              order: sectionOrder++,
              fields: [],
            });
          }

          const section = sections.get(sectionKey)!;
          section.fields.push({
            path,
            label: key,
            value,
          });

          // Store value for display
          if (value !== null && value !== undefined) {
            importedValues.set(path, String(value));
          }
        }
      }
    };

    extractAndGroup(json);

    // Filter out existing paths and count new ones
    let totalNewFields = 0;
    const sectionsToCreate: SectionGroup[] = [];

    // Sort sections by order
    const sortedSections = Array.from(sections.values()).sort((a, b) => a.order - b.order);

    for (const section of sortedSections) {
      const newFields = section.fields.filter((f) => !existingPaths.has(f.path));
      if (newFields.length > 0) {
        sectionsToCreate.push({
          ...section,
          fields: newFields,
        });
        totalNewFields += newFields.length;
      }
    }

    if (totalNewFields === 0) return 0;

    set(
      produce((draft: FormBuilderState & { importedValues: Map<string, string> }) => {
        if (!draft.template) return;

        const beforeState = draft.template.sections.map((s) => ({ ...s, fields: [...s.fields] }));

        // Create sections for each group
        for (const sectionData of sectionsToCreate) {
          const sectionKey = `import-${sectionData.key}`;

          // Find existing section or create new
          let section = draft.template.sections.find((s) => s.key === sectionKey);

          if (!section) {
            section = {
              id: uuidv4(),
              key: sectionKey,
              titleRu: sectionData.title,
              descriptionRu: '',
              icon: sectionData.icon,
              order: draft.template.sections.length,
              columns: 2,
              collapsible: true,
              defaultExpanded: true,
              fields: [],
            };
            draft.template.sections.push(section);
          }

          // Add fields to section (without defaultValue - values are temporary)
          for (const fieldInfo of sectionData.fields) {
            const schemaField = state.getFieldByPath(fieldInfo.path);

            const newField: FormFieldConfig = {
              id: uuidv4(),
              schemaPath: fieldInfo.path,
              customLabel: schemaField?.label_ru || fieldInfo.label,
              width: 'half' as FieldWidth,
              order: section.fields.length,
            };

            section.fields.push(newField);
          }
        }

        // Store imported values for temporary display
        draft.importedValues = importedValues;

        // Save history
        draft.history = draft.history.slice(0, draft.historyIndex + 1);
        draft.history.push({
          id: uuidv4(),
          actionType: 'fields_imported',
          description: `Импортировано ${totalNewFields} полей в ${sectionsToCreate.length} секций`,
          timestamp: new Date().toISOString(),
          beforeState,
          afterState: draft.template.sections.map((s) => ({ ...s, fields: [...s.fields] })),
        });
        draft.historyIndex = draft.history.length - 1;

        draft.isDirty = true;
      })
    );

    return totalNewFields;
  },

  // =========================================================================
  // Version label
  // =========================================================================

  setLoadedVersionLabel: (label) => set({ loadedVersionLabel: label }),
  clearLoadedVersionLabel: () => set({ loadedVersionLabel: null }),
}));
