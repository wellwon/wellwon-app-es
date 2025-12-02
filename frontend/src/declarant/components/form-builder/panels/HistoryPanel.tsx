// =============================================================================
// HistoryPanel - Панель истории изменений
// =============================================================================

import React from 'react';
import { History, Undo2, Redo2, Clock, Plus, Trash2, Move, Edit3 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFormBuilderStore } from '../../../stores/useFormBuilderStore';

interface HistoryPanelProps {
  isDark: boolean;
}

export const HistoryPanel: React.FC<HistoryPanelProps> = ({ isDark }) => {
  const { history, historyIndex, undo, redo } = useFormBuilderStore();

  const theme = isDark
    ? {
        bg: 'bg-[#1a1a1e]',
        text: 'text-white',
        textMuted: 'text-gray-400',
        cardBg: 'bg-[#232328]',
        border: 'border-white/10',
        hover: 'hover:bg-white/5',
        current: 'bg-accent-red/20 border-accent-red',
        past: 'opacity-50',
      }
    : {
        bg: 'bg-[#f4f4f4]',
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        cardBg: 'bg-white',
        border: 'border-gray-200',
        hover: 'hover:bg-gray-100',
        current: 'bg-accent-red/10 border-accent-red',
        past: 'opacity-50',
      };

  const canUndo = historyIndex > 0;
  const canRedo = historyIndex < history.length - 1;

  // Generate action descriptions for history items
  const getActionDescription = (index: number): { icon: React.ReactNode; text: string } => {
    if (index === 0) {
      return {
        icon: <Plus className="w-4 h-4" />,
        text: 'Начальное состояние',
      };
    }

    // In a real implementation, you'd track action types
    // For now, we'll show generic descriptions
    const actions = [
      { icon: <Plus className="w-4 h-4 text-green-500" />, text: 'Добавлено поле' },
      { icon: <Move className="w-4 h-4 text-blue-500" />, text: 'Перемещено поле' },
      { icon: <Edit3 className="w-4 h-4 text-yellow-500" />, text: 'Изменены настройки' },
      { icon: <Trash2 className="w-4 h-4 text-red-500" />, text: 'Удален элемент' },
    ];

    return actions[index % actions.length];
  };

  const formatTime = (index: number): string => {
    // Mock time - in real implementation, store timestamps with history
    const minutesAgo = (history.length - index - 1) * 2;
    if (minutesAgo === 0) return 'Сейчас';
    if (minutesAgo < 60) return `${minutesAgo} мин назад`;
    return `${Math.floor(minutesAgo / 60)} ч назад`;
  };

  return (
    <div className={cn('h-full flex flex-col', theme.bg)}>
      {/* Header */}
      <div className={cn('p-4 border-b', theme.border)}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <History className={cn('w-5 h-5', theme.textMuted)} />
            <h3 className={cn('font-semibold', theme.text)}>История изменений</h3>
          </div>
          <span className={cn('text-sm', theme.textMuted)}>
            {history.length} {history.length === 1 ? 'запись' : 'записей'}
          </span>
        </div>

        {/* Undo/Redo buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={undo}
            disabled={!canUndo}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border transition-colors',
              theme.border,
              canUndo ? theme.hover : 'opacity-50 cursor-not-allowed'
            )}
          >
            <Undo2 className="w-4 h-4" />
            <span className={cn('text-sm', theme.text)}>Отменить</span>
          </button>
          <button
            onClick={redo}
            disabled={!canRedo}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border transition-colors',
              theme.border,
              canRedo ? theme.hover : 'opacity-50 cursor-not-allowed'
            )}
          >
            <Redo2 className="w-4 h-4" />
            <span className={cn('text-sm', theme.text)}>Повторить</span>
          </button>
        </div>
      </div>

      {/* History list */}
      <div className="flex-1 overflow-y-auto p-2">
        {history.length === 0 ? (
          <div className={cn('text-center py-12', theme.textMuted)}>
            <History className="w-12 h-12 mx-auto mb-4 opacity-30" />
            <p className="text-sm">История пуста</p>
            <p className="text-xs mt-1">Начните редактирование формы</p>
          </div>
        ) : (
          <div className="space-y-1">
            {history.map((_, index) => {
              const reverseIndex = history.length - 1 - index;
              const isCurrent = reverseIndex === historyIndex;
              const isPast = reverseIndex > historyIndex;
              const action = getActionDescription(reverseIndex);

              return (
                <div
                  key={reverseIndex}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-lg border transition-colors cursor-pointer',
                    isCurrent
                      ? theme.current
                      : cn(theme.border, theme.hover, isPast && theme.past)
                  )}
                  onClick={() => {
                    // Jump to this history point
                    const diff = historyIndex - reverseIndex;
                    if (diff > 0) {
                      for (let i = 0; i < diff; i++) undo();
                    } else if (diff < 0) {
                      for (let i = 0; i < Math.abs(diff); i++) redo();
                    }
                  }}
                >
                  {/* Action icon */}
                  <div className={cn('flex-shrink-0', theme.textMuted)}>
                    {action.icon}
                  </div>

                  {/* Action description */}
                  <div className="flex-1 min-w-0">
                    <p className={cn('text-sm truncate', theme.text)}>{action.text}</p>
                    <p className={cn('text-xs', theme.textMuted)}>
                      {formatTime(reverseIndex)}
                    </p>
                  </div>

                  {/* Current indicator */}
                  {isCurrent && (
                    <div className="w-2 h-2 rounded-full bg-accent-red flex-shrink-0" />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className={cn('p-3 border-t text-xs text-center', theme.border, theme.textMuted)}>
        <div className="flex items-center justify-center gap-4">
          <span>Ctrl+Z - Отмена</span>
          <span>Ctrl+Y - Повтор</span>
        </div>
      </div>
    </div>
  );
};

export default HistoryPanel;
