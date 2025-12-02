// =============================================================================
// FormCanvas - Центральная область редактирования формы
// =============================================================================

import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { Plus, FileText, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useFormBuilderStore } from '../../../stores/useFormBuilderStore';
import { CanvasSection } from './CanvasSection';

interface FormCanvasProps {
  isDark: boolean;
  formWidth?: number; // Ширина формы в %
}

export const FormCanvas: React.FC<FormCanvasProps> = ({ isDark, formWidth = 100 }) => {
  const { template, addSection, selectSection } = useFormBuilderStore();

  const theme = isDark
    ? {
        bg: 'bg-[#1a1a1e]',
        text: 'text-white',
        textMuted: 'text-gray-400',
        cardBg: 'bg-[#232328]',
        border: 'border-white/10',
        dropZone: 'border-dashed border-2 border-white/20 bg-white/5',
        dropZoneActive: 'border-accent-red bg-accent-red/10',
      }
    : {
        bg: 'bg-[#f4f4f4]',
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        cardBg: 'bg-white',
        border: 'border-gray-200',
        dropZone: 'border-dashed border-2 border-gray-300 bg-gray-50',
        dropZoneActive: 'border-accent-red bg-accent-red/10',
      };

  const handleAddSection = () => {
    addSection({
      key: `section_${Date.now()}`,
      titleRu: 'Новая секция',
      icon: 'FileText',
      columns: 2,
      collapsible: false,
      defaultExpanded: true,
    });
  };

  if (!template) return null;

  // Вычисляем ширину относительно базовой (56rem = 896px)
  // 100% = 56rem, 70% = 39.2rem, 130% = 72.8rem
  const baseWidth = 56; // rem
  const calculatedWidth = (baseWidth * formWidth) / 100;

  return (
    <div className={cn('h-full p-6 overflow-x-auto', theme.bg)}>
      <div
        className="mx-auto space-y-4"
        style={{
          maxWidth: `${calculatedWidth}rem`,
          width: '100%',
        }}
      >
        {/* Sections */}
        {template.sections.length === 0 ? (
          <EmptyState isDark={isDark} onAddSection={handleAddSection} />
        ) : (
          <>
            {template.sections.map((section, index) => (
              <CanvasSection
                key={section.id}
                section={section}
                index={index}
                isDark={isDark}
              />
            ))}

            {/* Add section button */}
            <button
              onClick={handleAddSection}
              className={cn(
                'w-full py-4 rounded-xl flex items-center justify-center gap-2',
                theme.dropZone,
                'hover:border-accent-red hover:bg-accent-red/5'
              )}
            >
              <Plus className={cn('w-5 h-5', theme.textMuted)} />
              <span className={cn('font-medium', theme.textMuted)}>Добавить секцию</span>
            </button>
          </>
        )}
      </div>
    </div>
  );
};

// =============================================================================
// EmptyState - Пустое состояние canvas
// =============================================================================

interface EmptyStateProps {
  isDark: boolean;
  onAddSection: () => void;
}

const EmptyState: React.FC<EmptyStateProps> = ({ isDark, onAddSection }) => {
  const theme = isDark
    ? {
        text: 'text-white',
        textMuted: 'text-gray-400',
        cardBg: 'bg-[#232328]',
        border: 'border-white/10',
      }
    : {
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        cardBg: 'bg-white',
        border: 'border-gray-200',
      };

  return (
    <div className={cn('rounded-2xl border p-12 text-center', theme.cardBg, theme.border)}>
      <div className={cn('w-16 h-16 mx-auto mb-6 rounded-2xl flex items-center justify-center',
        isDark ? 'bg-white/5' : 'bg-gray-100'
      )}>
        <FileText className={cn('w-8 h-8', theme.textMuted)} />
      </div>

      <h3 className={cn('text-xl font-semibold mb-2', theme.text)}>
        Начните создавать форму
      </h3>
      <p className={cn('mb-6 max-w-md mx-auto', theme.textMuted)}>
        Добавьте секцию, затем перетащите поля из правой панели, чтобы создать свою форму.
      </p>

      <div className="flex items-center justify-center gap-4">
        <Button onClick={onAddSection} className="gap-2">
          <Plus className="w-4 h-4" />
          Добавить секцию
        </Button>
      </div>
    </div>
  );
};

export default FormCanvas;
