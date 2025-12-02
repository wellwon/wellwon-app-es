// =============================================================================
// CanvasSection - Секция на canvas с поддержкой drop
// =============================================================================

import React, { useState } from 'react';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  ChevronDown,
  ChevronRight,
  Trash2,
  GripVertical,
  Plus,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFormBuilderStore } from '../../../stores/useFormBuilderStore';
import { CanvasField } from './CanvasField';
import type { FormSectionConfig } from '../../../types/form-builder';

interface CanvasSectionProps {
  section: FormSectionConfig;
  index: number;
  isDark: boolean;
}

export const CanvasSection: React.FC<CanvasSectionProps> = ({ section, index, isDark }) => {
  const {
    removeSection,
    updateSection,
  } = useFormBuilderStore();

  const [isExpanded, setIsExpanded] = useState(true);

  // Make section droppable for fields
  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: `section-drop-${section.id}`,
    data: {
      type: 'section',
      sectionId: section.id,
      index: section.fields.length,
    },
  });

  const theme = isDark
    ? {
        cardBg: 'bg-[#232328]',
        text: 'text-white',
        textMuted: 'text-gray-400',
        border: 'border-white/10',
        hover: 'hover:bg-white/5',
        dropActive: 'ring-2 ring-accent-red/50 bg-accent-red/5',
      }
    : {
        cardBg: 'bg-white',
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        border: 'border-gray-200',
        hover: 'hover:bg-gray-50',
        dropActive: 'ring-2 ring-accent-red/50 bg-accent-red/5',
      };

  // Всегда используем 12-колоночную сетку для гибкой ширины полей
  // Поля сами определяют свою ширину через col-span-* классы

  return (
    <div
      ref={setDropRef}
      className={cn(
        'rounded-2xl border ',
        theme.cardBg,
        theme.border,
        isOver && theme.dropActive
      )}
    >
      {/* Section Header */}
      <div
        className={cn(
          'flex items-center gap-3 px-4 py-3 cursor-pointer group',
          isExpanded && `border-b ${theme.border}`
        )}
      >
        {/* Drag handle */}
        <GripVertical
          className={cn('w-4 h-4 opacity-0 group-hover:opacity-50 cursor-grab', theme.textMuted)}
        />

        {/* Expand/collapse */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            setIsExpanded(!isExpanded);
          }}
          className="p-0.5"
        >
          {isExpanded ? (
            <ChevronDown className={cn('w-5 h-5', theme.textMuted)} />
          ) : (
            <ChevronRight className={cn('w-5 h-5', theme.textMuted)} />
          )}
        </button>

        {/* Title */}
        <input
          type="text"
          value={section.titleRu}
          onChange={(e) => updateSection(section.id, { titleRu: e.target.value })}
          onClick={(e) => e.stopPropagation()}
          className={cn(
            'flex-1 bg-transparent font-semibold text-lg border-none outline-none',
            theme.text
          )}
        />

        {/* Field count */}
        <span className={cn('text-sm', theme.textMuted)}>
          {section.fields.length} {section.fields.length === 1 ? 'поле' : 'полей'}
        </span>

        {/* Actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 ">
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (window.confirm('Удалить секцию?')) {
                removeSection(section.id);
              }
            }}
            className={cn('p-1.5 rounded-lg', theme.hover)}
            title="Удалить секцию"
          >
            <Trash2 className="w-4 h-4 text-accent-red" />
          </button>
        </div>
      </div>

      {/* Section Content */}
      {isExpanded && (
        <div className="p-4">
          {section.fields.length === 0 ? (
            <DropZone sectionId={section.id} isDark={isDark} isActive={isOver} />
          ) : (
            <SortableContext
              items={section.fields.map((f) => f.id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="grid grid-cols-12 gap-4">
                {section.fields.map((field, fieldIndex) => (
                  <CanvasField
                    key={field.id}
                    field={field}
                    sectionId={section.id}
                    index={fieldIndex}
                    isDark={isDark}
                  />
                ))}
              </div>

              {/* Drop zone at the end */}
              <DropZone
                sectionId={section.id}
                isDark={isDark}
                isActive={isOver}
                minimal
                index={section.fields.length}
              />
            </SortableContext>
          )}
        </div>
      )}
    </div>
  );
};

// =============================================================================
// DropZone - Зона для drop полей
// =============================================================================

interface DropZoneProps {
  sectionId: string;
  isDark: boolean;
  isActive: boolean;
  minimal?: boolean;
  index?: number;
}

const DropZone: React.FC<DropZoneProps> = ({ sectionId, isDark, isActive, minimal, index = 0 }) => {
  const { setNodeRef, isOver } = useDroppable({
    id: `dropzone-${sectionId}-${index}`,
    data: {
      type: 'section',
      sectionId,
      index,
    },
  });

  const theme = isDark
    ? {
        textMuted: 'text-gray-500',
        dropZone: 'border-dashed border-2 border-white/10',
        dropZoneActive: 'border-accent-red bg-accent-red/10',
      }
    : {
        textMuted: 'text-gray-400',
        dropZone: 'border-dashed border-2 border-gray-200',
        dropZoneActive: 'border-accent-red bg-accent-red/10',
      };

  // Minimal version - only show when dragging over
  if (minimal) {
    if (!isOver && !isActive) {
      // Invisible but still droppable
      return <div ref={setNodeRef} className="mt-2 h-2" />;
    }
    return (
      <div
        ref={setNodeRef}
        className={cn(
          'mt-4 py-2 rounded-lg  text-center',
          theme.dropZoneActive
        )}
      >
        <span className={cn('text-sm', theme.textMuted)}>
          Отпустите для добавления
        </span>
      </div>
    );
  }

  // Empty section - show compact message
  return (
    <div
      ref={setNodeRef}
      className={cn(
        'py-8 rounded-xl  flex flex-col items-center justify-center',
        theme.dropZone,
        (isOver || isActive) && theme.dropZoneActive
      )}
    >
      <Plus className={cn('w-6 h-6 mb-1', theme.textMuted)} />
      <span className={cn('text-sm', theme.textMuted)}>
        {isOver ? 'Отпустите для добавления' : 'Перетащите поле из дерева справа'}
      </span>
    </div>
  );
};

export default CanvasSection;
