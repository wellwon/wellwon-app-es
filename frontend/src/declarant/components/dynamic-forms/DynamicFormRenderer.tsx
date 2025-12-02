// =============================================================================
// DynamicFormRenderer - Universal form renderer from JSON schema definitions
// =============================================================================

import React, { useState, useCallback, useMemo } from 'react';
import {
  FileText,
  Building2,
  Truck,
  Package,
  Calculator,
  User,
  ChevronRight,
  ChevronDown,
  AlertCircle,
  Globe,
  Flag,
  ScrollText,
  ClipboardCheck,
  PenTool,
  Landmark,
  MapPin,
  Phone,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type {
  FormDefinition,
  FieldDefinition,
  FormSection,
  FormState,
  FieldType,
} from '../../types/form-definitions';
import {
  TextField,
  NumberField,
  DateField,
  SelectField,
  CheckboxField,
  TextareaField,
  ObjectField,
  ArrayField,
} from './fields';

// =============================================================================
// Icon Mapping
// =============================================================================

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  FileText,
  Building2,
  Truck,
  Package,
  Calculator,
  User,
  Globe,
  Flag,
  ScrollText,
  ClipboardCheck,
  PenTool,
  Landmark,
  MapPin,
  Phone,
};

// =============================================================================
// Props
// =============================================================================

interface DynamicFormRendererProps {
  definition: FormDefinition;
  initialValues?: Record<string, unknown>;
  isDark: boolean;
  disabled?: boolean;
  onChange?: (values: Record<string, unknown>) => void;
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Get nested value from object using dot notation path
 */
function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  const parts = path.split('.');
  let current: unknown = obj;

  for (const part of parts) {
    if (current === null || current === undefined) return undefined;

    // Handle array index notation: field[0].name
    const arrayMatch = part.match(/^(.+)\[(\d+)\]$/);
    if (arrayMatch) {
      const [, key, index] = arrayMatch;
      current = (current as Record<string, unknown>)[key];
      if (Array.isArray(current)) {
        current = current[parseInt(index, 10)];
      } else {
        return undefined;
      }
    } else {
      current = (current as Record<string, unknown>)[part];
    }
  }

  return current;
}

/**
 * Set nested value in object using dot notation path (immutable)
 */
function setNestedValue(
  obj: Record<string, unknown>,
  path: string,
  value: unknown
): Record<string, unknown> {
  const result = { ...obj };
  const parts = path.split('.');
  let current = result;

  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i];

    // Handle array index notation
    const arrayMatch = part.match(/^(.+)\[(\d+)\]$/);
    if (arrayMatch) {
      const [, key, index] = arrayMatch;
      if (!(key in current)) {
        current[key] = [];
      }
      const arr = [...(current[key] as unknown[])];
      current[key] = arr;
      if (!arr[parseInt(index, 10)]) {
        arr[parseInt(index, 10)] = {};
      }
      current = arr[parseInt(index, 10)] as Record<string, unknown>;
    } else {
      if (!(part in current) || typeof current[part] !== 'object') {
        current[part] = {};
      } else {
        current[part] = { ...(current[part] as Record<string, unknown>) };
      }
      current = current[part] as Record<string, unknown>;
    }
  }

  const lastPart = parts[parts.length - 1];
  const lastArrayMatch = lastPart.match(/^(.+)\[(\d+)\]$/);
  if (lastArrayMatch) {
    const [, key, index] = lastArrayMatch;
    if (!(key in current)) {
      current[key] = [];
    }
    const arr = [...(current[key] as unknown[])];
    arr[parseInt(index, 10)] = value;
    current[key] = arr;
  } else {
    current[lastPart] = value;
  }

  return result;
}

// =============================================================================
// Component
// =============================================================================

export const DynamicFormRenderer: React.FC<DynamicFormRendererProps> = ({
  definition,
  initialValues = {},
  isDark,
  disabled = false,
  onChange,
}) => {
  // State
  const [formState, setFormState] = useState<FormState>({
    values: { ...definition.default_values, ...initialValues },
    errors: {},
    touched: {},
    isDirty: false,
  });

  const [activeSection, setActiveSection] = useState<string>(
    definition.sections[0]?.section_key || ''
  );

  const [expandedSections, setExpandedSections] = useState<Set<string>>(() => {
    return new Set(
      definition.sections
        .filter((s) => s.default_expanded)
        .map((s) => s.section_key)
    );
  });

  // Value getter
  const getValue = useCallback(
    (path: string): unknown => {
      return getNestedValue(formState.values, path);
    },
    [formState.values]
  );

  // Value setter
  const setValue = useCallback(
    (path: string, value: unknown) => {
      setFormState((prev) => {
        const newValues = setNestedValue(prev.values, path, value);
        onChange?.(newValues);
        return {
          ...prev,
          values: newValues,
          touched: { ...prev.touched, [path]: true },
          isDirty: true,
        };
      });
    },
    [onChange]
  );

  // Touch field
  const touchField = useCallback((path: string) => {
    setFormState((prev) => ({
      ...prev,
      touched: { ...prev.touched, [path]: true },
    }));
  }, []);

  // Build field map for quick lookup
  const fieldMap = useMemo(() => {
    const map = new Map<string, FieldDefinition>();

    const addToMap = (fields: FieldDefinition[]) => {
      for (const field of fields) {
        map.set(field.path, field);
        if (field.children) {
          addToMap(field.children);
        }
      }
    };

    addToMap(definition.fields);
    return map;
  }, [definition.fields]);

  // Render a single field
  const renderField = useCallback(
    (field: FieldDefinition, _parentPath?: string): React.ReactNode => {
      const value = getValue(field.path);
      const error = formState.errors[field.path];

      const commonProps = {
        field,
        value,
        error,
        onChange: (val: unknown) => setValue(field.path, val),
        onBlur: () => touchField(field.path),
        isDark,
        disabled,
      };

      switch (field.field_type as FieldType) {
        case 'text':
          return <TextField key={field.path} {...commonProps} />;
        case 'number':
          return <NumberField key={field.path} {...commonProps} />;
        case 'date':
        case 'datetime':
          return <DateField key={field.path} {...commonProps} />;
        case 'select':
          return <SelectField key={field.path} {...commonProps} />;
        case 'checkbox':
          return <CheckboxField key={field.path} {...commonProps} />;
        case 'textarea':
          return <TextareaField key={field.path} {...commonProps} />;
        case 'object':
          return (
            <ObjectField
              key={field.path}
              {...commonProps}
              renderField={renderField}
            />
          );
        case 'array':
          return (
            <ArrayField
              key={field.path}
              {...commonProps}
              renderField={renderField}
            />
          );
        default:
          return <TextField key={field.path} {...commonProps} />;
      }
    },
    [getValue, setValue, touchField, formState.errors, isDark, disabled]
  );

  // Helper to find a field by path (handles nested paths like "ContractTerms.DealSign")
  const findFieldByPath = useCallback(
    (path: string): FieldDefinition | undefined => {
      // First try direct lookup
      const direct = fieldMap.get(path);
      if (direct) return direct;

      // If not found, try to navigate nested structure
      // e.g., "ContractTerms.DealSign" -> find ContractTerms, then DealSign in its children
      const parts = path.split('.');
      if (parts.length === 1) return undefined;

      let current: FieldDefinition | undefined;

      for (let i = 0; i < parts.length; i++) {
        const partPath = parts.slice(0, i + 1).join('.');
        const found = fieldMap.get(partPath);

        if (found) {
          current = found;
        } else if (current?.children) {
          // Look in children
          const childName = parts[i];
          current = current.children.find((c) => c.name === childName);
        } else {
          return undefined;
        }
      }

      return current;
    },
    [fieldMap]
  );

  // Render section content
  const renderSectionContent = useCallback(
    (section: FormSection) => {
      const fields: FieldDefinition[] = [];

      for (const path of section.field_paths) {
        // Try to find field by exact path first
        let field = fieldMap.get(path);

        if (!field) {
          // Try to find nested field
          field = findFieldByPath(path);
        }

        if (!field) {
          // Path might be a top-level object - find it in definition.fields
          field = definition.fields.find(
            (f) => f.path === path || f.name === path
          );
        }

        if (field) {
          fields.push(field);
        }
      }

      // If no direct matches found, fallback to original logic
      if (fields.length === 0) {
        const fallbackFields = definition.fields.filter((f) =>
          section.field_paths.some(
            (path) => f.path === path || f.path.startsWith(path + '.')
          )
        );
        fields.push(...fallbackFields);
      }

      if (fields.length === 0) {
        return (
          <div className={cn('text-sm text-center py-4', isDark ? 'text-gray-500' : 'text-gray-400')}>
            <AlertCircle className="w-5 h-5 mx-auto mb-2" />
            Нет полей в этой секции
          </div>
        );
      }

      return (
        <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${section.columns}, 1fr)` }}>
          {fields.map((field) => (
            <div key={field.path} className={field.field_type === 'object' || field.field_type === 'array' ? 'col-span-full' : ''}>
              {renderField(field)}
            </div>
          ))}
        </div>
      );
    },
    [fieldMap, definition.fields, renderField, isDark, findFieldByPath]
  );

  // Toggle section expansion
  const toggleSection = useCallback((sectionKey: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionKey)) {
        next.delete(sectionKey);
      } else {
        next.add(sectionKey);
      }
      return next;
    });
  }, []);

  // Theme classes (matching DESIGN_SYSTEM.md)
  const theme = isDark
    ? {
        bg: 'bg-[#1a1a1e]',
        cardBg: 'bg-[#232328]',
        text: 'text-white',
        textSecondary: 'text-gray-400',
        border: 'border-white/10',
        hoverBg: 'hover:bg-white/5',
      }
    : {
        bg: 'bg-[#f4f4f4]',
        cardBg: 'bg-white',
        text: 'text-gray-900',
        textSecondary: 'text-gray-600',
        border: 'border-gray-300',
        hoverBg: 'hover:bg-gray-100',
      };

  // If no sections defined, render all fields directly
  if (definition.sections.length === 0) {
    return (
      <div className={cn('p-6', theme.bg)}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {definition.fields.map((field) => (
            <div key={field.path} className={field.field_type === 'object' || field.field_type === 'array' ? 'col-span-full' : ''}>
              {renderField(field)}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={cn('flex h-full', theme.bg)}>
      {/* Left Sidebar - Navigation */}
      <div className={cn('w-64 border-r p-4 space-y-1 overflow-y-auto', theme.border)}>
        {definition.sections.map((section) => {
          const IconComponent = ICON_MAP[section.icon] || FileText;
          const isActive = activeSection === section.section_key;

          return (
            <button
              key={section.section_key}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl',
                'transition-colors text-left text-sm font-medium',
                isActive
                  ? 'bg-accent-red/20 text-accent-red'
                  : cn(theme.textSecondary, theme.hoverBg)
              )}
              onClick={() => setActiveSection(section.section_key)}
            >
              <IconComponent className="w-5 h-5 flex-shrink-0" />
              <span className="truncate">{section.title_ru}</span>
            </button>
          );
        })}
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        {definition.sections.map((section) => {
          const isExpanded = expandedSections.has(section.section_key);
          const isActive = activeSection === section.section_key;

          // Only show active section or collapsible sections
          if (!isActive && !section.collapsible) return null;

          return (
            <div
              key={section.section_key}
              id={section.section_key}
              className={cn('mb-6', !isActive && 'hidden')}
            >
              <div className={cn('rounded-2xl border', theme.cardBg, theme.border)}>
                {/* Section Header */}
                <div
                  className={cn(
                    'flex items-center justify-between p-4',
                    section.collapsible && 'cursor-pointer',
                    isExpanded && cn('border-b', theme.border)
                  )}
                  onClick={() => section.collapsible && toggleSection(section.section_key)}
                >
                  <div>
                    <h3 className={cn('text-lg font-semibold', theme.text)}>
                      {section.title_ru}
                    </h3>
                    {section.description_ru && (
                      <p className={cn('text-sm mt-0.5', theme.textSecondary)}>
                        {section.description_ru}
                      </p>
                    )}
                  </div>

                  {section.collapsible && (
                    <div className={theme.textSecondary}>
                      {isExpanded ? (
                        <ChevronDown className="w-5 h-5" />
                      ) : (
                        <ChevronRight className="w-5 h-5" />
                      )}
                    </div>
                  )}
                </div>

                {/* Section Content */}
                {(!section.collapsible || isExpanded) && (
                  <div className="p-4">{renderSectionContent(section)}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default DynamicFormRenderer;
