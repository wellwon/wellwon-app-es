// =============================================================================
// FormBuilderPage - Главная страница конструктора форм
// =============================================================================

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { DndContext, DragEndEvent, DragOverEvent, DragStartEvent, DragOverlay, closestCenter } from '@dnd-kit/core';
import { Loader2, AlertCircle, GripVertical, Type, Hash, Calendar, List, CheckSquare, FileText as TextIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFormBuilderStore } from '../../stores/useFormBuilderStore';
import { BuilderLayout } from './BuilderLayout';
import { BuilderHeader } from './BuilderHeader';
import { StructurePanel } from './panels/StructurePanel';
import { FormCanvas } from './canvas/FormCanvas';
import { SchemaTree } from './tree/SchemaTree';
import { FormPreview } from './preview/FormPreview';
import { HistoryPanel } from './panels/HistoryPanel';
import { VersionsPanel } from './panels/VersionsPanel';
import { useFormDefinition } from '../../hooks/useFormTemplates';
import { saveSections, saveFormWidth } from '../../api/form-templates-api';
import type { FormTemplate } from '../../types/form-builder';
import type { FieldDefinition } from '../../types/form-definitions';

interface FormBuilderPageProps {
  defaultIsDark?: boolean;
}

// Mock data для разработки - потом заменим на API
const mockSchemaFields: FieldDefinition[] = [
  {
    path: 'ContractTerms',
    name: 'ContractTerms',
    field_type: 'object',
    required: false,
    label_ru: 'Условия контракта',
    hint_ru: '',
    placeholder_ru: '',
    children: [
      { path: 'ContractTerms.DealSign', name: 'DealSign', field_type: 'checkbox', required: false, label_ru: 'Признак сделки', hint_ru: '', placeholder_ru: '' },
      { path: 'ContractTerms.Amount', name: 'Amount', field_type: 'number', required: true, label_ru: 'Сумма контракта', hint_ru: '', placeholder_ru: '' },
      { path: 'ContractTerms.CurrencyCode', name: 'CurrencyCode', field_type: 'select', required: true, label_ru: 'Код валюты', hint_ru: '', placeholder_ru: '' },
      { path: 'ContractTerms.ContractDate', name: 'ContractDate', field_type: 'date', required: true, label_ru: 'Дата контракта', hint_ru: '', placeholder_ru: '' },
      { path: 'ContractTerms.ContractNumber', name: 'ContractNumber', field_type: 'text', required: true, label_ru: 'Номер контракта', hint_ru: '', placeholder_ru: '' },
    ],
  },
  {
    path: 'ForeignPerson',
    name: 'ForeignPerson',
    field_type: 'object',
    required: false,
    label_ru: 'Иностранная сторона',
    hint_ru: '',
    placeholder_ru: '',
    children: [
      { path: 'ForeignPerson.Name', name: 'Name', field_type: 'text', required: true, label_ru: 'Наименование', hint_ru: '', placeholder_ru: '' },
      { path: 'ForeignPerson.CountryCode', name: 'CountryCode', field_type: 'select', required: true, label_ru: 'Код страны', hint_ru: '', placeholder_ru: '' },
      { path: 'ForeignPerson.Address', name: 'Address', field_type: 'textarea', required: false, label_ru: 'Адрес', hint_ru: '', placeholder_ru: '' },
    ],
  },
  {
    path: 'RussianPerson',
    name: 'RussianPerson',
    field_type: 'object',
    required: false,
    label_ru: 'Российская сторона',
    hint_ru: '',
    placeholder_ru: '',
    children: [
      { path: 'RussianPerson.Name', name: 'Name', field_type: 'text', required: true, label_ru: 'Наименование', hint_ru: '', placeholder_ru: '' },
      { path: 'RussianPerson.INN', name: 'INN', field_type: 'text', required: true, label_ru: 'ИНН', hint_ru: '', placeholder_ru: '' },
      { path: 'RussianPerson.KPP', name: 'KPP', field_type: 'text', required: false, label_ru: 'КПП', hint_ru: '', placeholder_ru: '' },
    ],
  },
];

const mockTemplate: FormTemplate = {
  id: 'mock-template-1',
  name: 'Договор купли-продажи',
  description: 'Шаблон формы для договора купли-продажи',
  documentModeId: '1002004E',
  gfCode: 'GF001',
  typeName: 'Contract',
  version: 1,
  isDraft: true,
  isPublished: false,
  status: 'draft',
  sections: [],
  defaultValues: {},
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  createdBy: 'user-1',
  usageCount: 0,
};

export const FormBuilderPage: React.FC<FormBuilderPageProps> = ({ defaultIsDark = true }) => {
  const { templateId } = useParams<{ templateId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Theme state - stored in localStorage
  const [isDark, setIsDark] = useState(() => {
    const stored = localStorage.getItem('formBuilder.isDark');
    return stored !== null ? stored === 'true' : defaultIsDark;
  });

  // Form width state - loaded from API, falls back to localStorage
  const [formWidth, setFormWidth] = useState(() => {
    const stored = localStorage.getItem('formBuilder.formWidth');
    return stored !== null ? parseInt(stored, 10) : 100;
  });
  // Track if form width was changed from initial loaded value
  const [initialFormWidth, setInitialFormWidth] = useState<number | null>(null);
  const [isFormWidthDirty, setIsFormWidthDirty] = useState(false);

  // Toggle theme handler
  const handleToggleTheme = useCallback(() => {
    setIsDark(prev => {
      const newValue = !prev;
      localStorage.setItem('formBuilder.isDark', String(newValue));
      return newValue;
    });
  }, []);

  // Form width change handler
  const handleFormWidthChange = useCallback((width: number) => {
    setFormWidth(width);
    localStorage.setItem('formBuilder.formWidth', String(width));
    // Mark as dirty if changed from initial value
    if (initialFormWidth !== null && width !== initialFormWidth) {
      setIsFormWidthDirty(true);
    } else if (initialFormWidth !== null && width === initialFormWidth) {
      setIsFormWidthDirty(false);
    }
  }, [initialFormWidth]);

  // Query params - documentModeId is the key identifier
  const queryDocumentModeId = searchParams.get('documentModeId');
  const queryGfCode = searchParams.get('gfCode');
  const queryTypeName = searchParams.get('typeName');

  // documentModeId from URL params (for new) or from route param (existing template ID = documentModeId)
  const documentModeId = queryDocumentModeId || templateId;

  // Load full form definition (schema + fields + saved sections) - this already exists in DB
  const { data: formDefinitionData, isLoading: isLoadingDefinition, isFetched: isDefinitionFetched } = useFormDefinition(documentModeId || undefined);

  // Extract fields from form definition for backwards compatibility
  const formDefinition = formDefinitionData?.fields;


  const {
    template,
    schemaFields,
    activeTab,
    isDirty,
    isSaving,
    isLoading: isStoreLoading,
    leftPanelWidth,
    rightPanelWidth,
    draggedItem,
    loadedVersionLabel,
    initBuilder,
    setActiveTab,
    setPanelWidths,
    setDraggedItem,
    setDropTarget,
    addFieldToSection,
    moveField,
    reorderFieldsInSection,
    undo,
    redo,
    canUndo,
    canRedo,
    setIsSaving,
    setIsDirty,
    getFieldByPath,
  } = useFormBuilderStore();

  // Debug logging
  console.log('[FormBuilder]', {
    templateId,
    documentModeId,
    queryTypeName,
    isLoadingDefinition,
    isDefinitionFetched,
    fieldsCount: formDefinition?.length,
    sectionsCount: formDefinitionData?.sections?.length,
    hasTemplate: !!template,
    savedSections: formDefinitionData?.sections?.map(s => ({
      key: s.section_key,
      fieldsConfigCount: s.fields_config?.length
    })),
  });

  // Initialize builder when form definition (schema) is loaded
  useEffect(() => {
    if (!isDefinitionFetched || !documentModeId || !formDefinitionData) return;

    // Convert saved sections from API format to Form Builder format
    const savedSections = formDefinitionData.sections
      ?.filter(s => s.fields_config && s.fields_config.length > 0)
      ?.map((s, idx) => ({
        id: `section-${s.section_key}-${idx}`,
        key: s.section_key,
        titleRu: s.title_ru,
        descriptionRu: s.description_ru || '',
        icon: s.icon || 'FileText',
        order: s.sort_order,
        columns: s.columns as 1 | 2 | 3 | 4,
        collapsible: s.collapsible,
        defaultExpanded: s.default_expanded,
        fields: s.fields_config.map((f, fieldIdx) => ({
          id: f.id || `field-${f.schemaPath.replace(/\./g, '-')}-${fieldIdx}`,
          schemaPath: f.schemaPath,
          customLabel: f.customLabel,
          customPlaceholder: f.customPlaceholder,
          customHint: f.customHint,
          prompt: f.prompt,
          width: (f.width || 'half') as 'full' | 'three-quarters' | 'two-thirds' | 'half' | 'third' | 'quarter',
          order: f.order || fieldIdx,
          readonly: f.readonly,
          defaultValue: f.defaultValue,
          required: f.required,
          isSelect: f.isSelect,
          selectOptions: f.selectOptions,
        })),
      })) || [];

    console.log('[FormBuilder] Converted saved sections:', savedSections);

    // Create template for this document mode with saved sections
    const formTemplate: FormTemplate = {
      id: documentModeId,
      name: formDefinitionData.type_name || queryTypeName || documentModeId,
      description: '',
      documentModeId: documentModeId,
      gfCode: formDefinitionData.gf_code || queryGfCode || '',
      typeName: formDefinitionData.type_name || queryTypeName || '',
      version: formDefinitionData.version || 1,
      isDraft: true,
      isPublished: false,
      status: 'draft',
      sections: savedSections,
      defaultValues: formDefinitionData.default_values || {},
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      createdBy: '',
      usageCount: 0,
    };

    initBuilder(formTemplate, formDefinition || []);

    // Load form width from API
    if (formDefinitionData.form_width) {
      setFormWidth(formDefinitionData.form_width);
      setInitialFormWidth(formDefinitionData.form_width);
      localStorage.setItem('formBuilder.formWidth', String(formDefinitionData.form_width));
    } else {
      // Set initial width to current value if not saved yet
      setInitialFormWidth(formWidth);
    }
  }, [isDefinitionFetched, documentModeId, queryTypeName, queryGfCode, formDefinition, formDefinitionData, initBuilder]);


  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        if (e.shiftKey) {
          redo();
        } else {
          undo();
        }
        e.preventDefault();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        handleSave();
        e.preventDefault();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo]);

  // Handlers
  const handleBack = useCallback(() => {
    if (isDirty || isFormWidthDirty) {
      if (window.confirm('Есть несохраненные изменения. Вы уверены, что хотите выйти?')) {
        navigate('/declarant/references?tab=json-templates', { replace: true });
      }
    } else {
      navigate('/declarant/references?tab=json-templates', { replace: true });
    }
  }, [isDirty, isFormWidthDirty, navigate]);

  const handleSave = useCallback(async () => {
    if (!template || !documentModeId) return;

    setIsSaving(true);
    try {
      // Convert sections to API format and save
      const sectionsToSave = template.sections.map((section, idx) => ({
        id: section.id,
        key: section.key,
        titleRu: section.titleRu,
        descriptionRu: section.descriptionRu,
        icon: section.icon,
        order: idx,
        columns: section.columns,
        collapsible: section.collapsible,
        defaultExpanded: section.defaultExpanded,
        fields: section.fields.map((field, fieldIdx) => ({
          id: field.id,
          schemaPath: field.schemaPath,
          customLabel: field.customLabel,
          customPlaceholder: field.customPlaceholder,
          customHint: field.customHint,
          prompt: field.prompt,
          width: field.width,
          order: fieldIdx,
          readonly: field.readonly,
          defaultValue: field.defaultValue,
          required: field.required,
          isSelect: field.isSelect,
          selectOptions: field.selectOptions,
        })),
      }));

      // Save sections
      await saveSections(documentModeId, sectionsToSave);

      // Save form width if changed
      if (isFormWidthDirty) {
        await saveFormWidth(documentModeId, formWidth);
        setInitialFormWidth(formWidth);
        setIsFormWidthDirty(false);
      }

      setIsDirty(false);
      console.log('[FormBuilder] Saved successfully');
    } catch (error) {
      console.error('Failed to save template:', error);
      alert('Ошибка сохранения. Проверьте консоль.');
    } finally {
      setIsSaving(false);
    }
  }, [template, documentModeId, setIsSaving, setIsDirty, isFormWidthDirty, formWidth]);


  // Drag and Drop handlers
  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const { active } = event;
      const dragData = active.data.current;

      if (dragData) {
        setDraggedItem({
          type: dragData.type,
          id: String(active.id),
          data: dragData.field || dragData.section,
          sourceSection: dragData.sectionId,
        });
      }
    },
    [setDraggedItem]
  );

  const handleDragOver = useCallback(
    (event: DragOverEvent) => {
      const { over } = event;

      if (over) {
        const overData = over.data.current;
        if (overData) {
          setDropTarget({
            type: overData.type,
            sectionId: overData.sectionId,
            index: overData.index,
          });
        }
      } else {
        setDropTarget(null);
      }
    },
    [setDropTarget]
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;

      if (over) {
        const activeData = active.data.current;
        const overData = over.data.current;

        if (activeData && overData) {
          // Добавление поля из дерева схемы в секцию
          if (activeData.type === 'schema-field' && overData.type === 'section') {
            addFieldToSection(overData.sectionId, activeData.field.path, overData.index);
          }

          // Добавление поля из дерева схемы на существующее поле (вставка рядом)
          if (activeData.type === 'schema-field' && overData.type === 'canvas-field') {
            addFieldToSection(overData.sectionId, activeData.field.path, overData.index);
          }

          // Перемещение поля canvas на другое поле canvas (сортировка внутри секции)
          if (activeData.type === 'canvas-field' && overData.type === 'canvas-field') {
            const fromIndex = activeData.index;
            const toIndex = overData.index;
            if (activeData.sectionId === overData.sectionId) {
              // Сортировка внутри одной секции
              if (fromIndex !== toIndex) {
                reorderFieldsInSection(activeData.sectionId, fromIndex, toIndex);
              }
            } else {
              // Перемещение между секциями
              moveField(
                activeData.sectionId,
                overData.sectionId,
                String(active.id),
                toIndex
              );
            }
          }

          // Перемещение поля на drop-зону секции
          if (activeData.type === 'canvas-field' && overData.type === 'section') {
            if (activeData.sectionId !== overData.sectionId) {
              moveField(
                activeData.sectionId,
                overData.sectionId,
                String(active.id),
                overData.index ?? 0
              );
            } else {
              // Reorder within section (drop на зону секции)
              const fromIndex = activeData.index;
              const toIndex = overData.index ?? 0;
              if (fromIndex !== toIndex) {
                reorderFieldsInSection(activeData.sectionId, fromIndex, toIndex);
              }
            }
          }
        }
      }

      setDraggedItem(null);
      setDropTarget(null);
    },
    [addFieldToSection, moveField, reorderFieldsInSection, setDraggedItem, setDropTarget]
  );

  // Loading state - wait for form definition to be fetched
  const isLoading = isStoreLoading || (documentModeId && !isDefinitionFetched);

  // Theme
  const theme = isDark
    ? {
        bg: 'bg-[#1a1a1e]',
        text: 'text-white',
        textMuted: 'text-gray-400',
        loadingBg: 'bg-[#1a1a1e]',
        cardBg: 'bg-[#232328]',
        border: 'border-white/10',
      }
    : {
        bg: 'bg-[#f4f4f4]',
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        loadingBg: 'bg-white',
        cardBg: 'bg-white',
        border: 'border-gray-200',
      };

  // Error state - no documentModeId provided
  if (!documentModeId) {
    return (
      <div className={cn('flex items-center justify-center h-screen', theme.loadingBg)}>
        <div className={cn('flex flex-col items-center gap-4 p-8 rounded-2xl', theme.cardBg, 'border', theme.border)}>
          <AlertCircle className="w-12 h-12 text-red-500" />
          <span className={cn('text-lg font-medium', theme.text)}>Не указан тип документа</span>
          <span className={theme.textMuted}>
            Выберите форму из справочника "Шаблоны JSON"
          </span>
          <button
            onClick={() => navigate('/declarant/references?tab=json-templates', { replace: true })}
            className="px-4 py-2 bg-accent-red text-white rounded-lg hover:bg-accent-red/90"
          >
            Вернуться назад
          </button>
        </div>
      </div>
    );
  }

  // Loading state
  if (isLoading || !template) {
    return (
      <div className={cn('flex items-center justify-center h-screen', theme.loadingBg)}>
        <div className="flex flex-col items-center gap-4">
          <Loader2 className={cn('w-8 h-8 animate-spin', isDark ? 'text-white' : 'text-gray-900')} />
          <span className={theme.text}>
            {isLoadingDefinition ? 'Загрузка схемы формы...' : 'Инициализация конструктора...'}
          </span>
        </div>
      </div>
    );
  }

  // Render content based on active tab
  const renderCanvasContent = () => {
    switch (activeTab) {
      case 'structure':
        return <FormCanvas isDark={isDark} formWidth={formWidth} />;
      case 'preview':
        return <FormPreview isDark={isDark} formWidth={formWidth} />;
      case 'history':
        return <HistoryPanel isDark={isDark} />;
      case 'versions':
        return <VersionsPanel isDark={isDark} />;
      default:
        return <FormCanvas isDark={isDark} formWidth={formWidth} />;
    }
  };

  return (
    <DndContext
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className={cn('h-screen', theme.bg)}>
        <BuilderLayout
          isDark={isDark}
          leftPanelWidth={leftPanelWidth}
          rightPanelWidth={rightPanelWidth}
          onPanelResize={setPanelWidths}
          header={
            <BuilderHeader
              templateName={template.name}
              version={template.version}
              isDraft={template.isDraft}
              isDirty={isDirty || isFormWidthDirty}
              isSaving={isSaving}
              activeTab={activeTab}
              isDark={isDark}
              loadedVersionLabel={loadedVersionLabel}
              formWidth={formWidth}
              onBack={handleBack}
              onSave={handleSave}
              onTabChange={setActiveTab}
              onToggleTheme={handleToggleTheme}
              onFormWidthChange={handleFormWidthChange}
            />
          }
          leftPanel={
            <StructurePanel
              isDark={isDark}
              isPreviewActive={activeTab === 'preview'}
              onTogglePreview={() => setActiveTab(activeTab === 'preview' ? 'structure' : 'preview')}
            />
          }
          canvas={renderCanvasContent()}
          rightPanel={<SchemaTree isDark={isDark} />}
        />
      </div>
      {/* Drag Overlay - visual feedback while dragging */}
      <DragOverlay dropAnimation={null}>
        {draggedItem && (
          <DragPreview
            draggedItem={draggedItem}
            isDark={isDark}
            getFieldByPath={getFieldByPath}
          />
        )}
      </DragOverlay>
    </DndContext>
  );
};

// =============================================================================
// DragPreview - Visual feedback during drag
// =============================================================================

const FIELD_TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  text: Type,
  number: Hash,
  date: Calendar,
  datetime: Calendar,
  select: List,
  checkbox: CheckSquare,
  textarea: TextIcon,
};

interface DragPreviewProps {
  draggedItem: any;
  isDark: boolean;
  getFieldByPath: (path: string) => any;
}

const DragPreview: React.FC<DragPreviewProps> = ({ draggedItem, isDark, getFieldByPath }) => {
  const theme = isDark
    ? {
        bg: 'bg-[#2a2a2e]',
        text: 'text-white',
        textMuted: 'text-gray-400',
        border: 'border-white/20',
      }
    : {
        bg: 'bg-white',
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        border: 'border-gray-300',
      };

  // For schema field being dragged
  if (draggedItem.type === 'schema-field') {
    const field = draggedItem.data;
    const Icon = FIELD_TYPE_ICONS[field?.field_type || 'text'] || Type;
    return (
      <div
        className={cn(
          'px-4 py-3 rounded-xl border-2 shadow-xl cursor-grabbing',
          theme.bg,
          theme.border,
          'ring-2 ring-accent-red'
        )}
        style={{ width: 280 }}
      >
        <div className="flex items-center gap-2">
          <GripVertical className={cn('w-4 h-4', theme.textMuted)} />
          <Icon className={cn('w-4 h-4', theme.textMuted)} />
          <span className={cn('font-medium truncate', theme.text)}>
            {field?.label_ru || field?.name || 'Поле'}
          </span>
        </div>
        <div className={cn('mt-1 text-xs font-mono', theme.textMuted)}>
          {field?.path || ''}
        </div>
      </div>
    );
  }

  // For canvas field being moved
  if (draggedItem.type === 'canvas-field') {
    const fieldConfig = draggedItem.data;
    const schemaField = getFieldByPath(fieldConfig?.schemaPath || '');
    const Icon = FIELD_TYPE_ICONS[schemaField?.field_type || 'text'] || Type;
    return (
      <div
        className={cn(
          'px-4 py-3 rounded-xl border-2 shadow-xl cursor-grabbing',
          theme.bg,
          theme.border,
          'ring-2 ring-accent-red'
        )}
        style={{ width: 280 }}
      >
        <div className="flex items-center gap-2">
          <GripVertical className={cn('w-4 h-4', theme.textMuted)} />
          <Icon className={cn('w-4 h-4', theme.textMuted)} />
          <span className={cn('font-medium truncate', theme.text)}>
            {fieldConfig?.customLabel || schemaField?.label_ru || fieldConfig?.schemaPath || 'Поле'}
          </span>
        </div>
      </div>
    );
  }

  return null;
};

export default FormBuilderPage;
