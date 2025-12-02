// =============================================================================
// BuilderHeader - Toolbar для конструктора форм
// =============================================================================

import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Save,
  Upload,
  Eye,
  Download,
  Loader2,
  Sun,
  Moon,
  Minus,
  Plus,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import type { BuilderTab } from '../../types/form-builder';

interface BuilderHeaderProps {
  templateName: string;
  version: number;
  isDraft: boolean;
  isDirty: boolean;
  isSaving: boolean;
  activeTab: BuilderTab;
  isDark: boolean;
  loadedVersionLabel?: string | null; // Название загруженной версии
  formWidth: number; // Ширина формы в %
  onBack: () => void;
  onSave: () => void;
  onTabChange: (tab: BuilderTab) => void;
  onToggleTheme?: () => void;
  onExport?: () => void;
  onImport?: () => void;
  onFormWidthChange: (width: number) => void;
}

export const BuilderHeader: React.FC<BuilderHeaderProps> = ({
  templateName,
  version,
  isDraft,
  isDirty,
  isSaving,
  activeTab,
  isDark,
  loadedVersionLabel,
  formWidth,
  onBack,
  onSave,
  onTabChange,
  onToggleTheme,
  onExport,
  onImport,
  onFormWidthChange,
}) => {
  const navigate = useNavigate();

  const theme = isDark
    ? {
        bg: 'bg-[#232328]',
        text: 'text-white',
        textMuted: 'text-gray-400',
        border: 'border-white/10',
        tabActive: 'bg-white/10 text-white',
        tabInactive: 'text-gray-400 hover:text-white hover:bg-white/5',
      }
    : {
        bg: 'bg-white',
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        border: 'border-gray-200',
        tabActive: 'bg-gray-100 text-gray-900',
        tabInactive: 'text-gray-500 hover:text-gray-900 hover:bg-gray-50',
      };

  // Табы без "Структура" - это экран по умолчанию
  // Повторное нажатие на Предпросмотр возвращает к структуре
  const tabs: { key: BuilderTab; label: string; icon?: boolean }[] = [
    { key: 'preview', label: 'Предпросмотр', icon: true },
    { key: 'versions', label: 'Версии' },
  ];

  // Обработчик клика по табу - повторное нажатие на preview возвращает на structure
  const handleTabClick = (tabKey: BuilderTab) => {
    if (tabKey === activeTab && tabKey === 'preview') {
      onTabChange('structure');
    } else if (tabKey === activeTab && tabKey === 'versions') {
      onTabChange('structure');
    } else {
      onTabChange(tabKey);
    }
  };

  // Навигация назад к справочнику JSON схем
  const handleBack = () => {
    if (isDirty) {
      if (window.confirm('Есть несохраненные изменения. Вы уверены, что хотите выйти?')) {
        navigate('/declarant/references?tab=json-templates', { replace: true });
      }
    } else {
      navigate('/declarant/references?tab=json-templates', { replace: true });
    }
  };

  // Обработчик изменения ширины (шаг 2%, диапазон 70-130%)
  const handleWidthChange = (delta: number) => {
    const newWidth = Math.max(70, Math.min(130, formWidth + delta));
    onFormWidthChange(newWidth);
  };

  return (
    <div className={cn('px-4 py-3', theme.bg)}>
      {/* Single row layout */}
      <div className="flex items-center justify-between gap-4">
        {/* Left side - Back, Theme, Tabs */}
        <div className="flex items-center gap-3">
          {/* Back button - styled per reference */}
          <button
            onClick={handleBack}
            className={cn(
              'h-8 px-3 flex items-center gap-2 rounded-xl border text-sm',
              isDark
                ? 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/10 hover:text-white hover:border-white/20'
                : 'bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200 hover:text-gray-900 hover:border-gray-300'
            )}
            aria-label="Назад"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Назад</span>
          </button>

          <div className={cn('h-6 w-px', isDark ? 'bg-white/20' : 'bg-gray-300')} />

          {/* Tabs inline - toggle behavior + Export/Import */}
          <div className="flex items-center gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => handleTabClick(tab.key)}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-sm font-medium',
                  activeTab === tab.key ? theme.tabActive : theme.tabInactive
                )}
              >
                {tab.icon && <Eye className="w-4 h-4 inline mr-1.5" />}
                {tab.label}
              </button>
            ))}

            {/* Export button */}
            <button
              onClick={onExport}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-1.5',
                theme.tabInactive
              )}
            >
              <Download className="w-4 h-4" />
              Экспорт
            </button>

            {/* Import button */}
            <button
              onClick={onImport}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-1.5',
                theme.tabInactive
              )}
            >
              <Upload className="w-4 h-4" />
              Импорт
            </button>
          </div>
        </div>

        {/* Center - Title */}
        <div className="flex items-center gap-2">
          <h1 className={cn('text-lg font-semibold truncate', theme.text)}>
            {templateName || 'Новый шаблон'}
          </h1>
          <span className={cn('text-sm', theme.textMuted)}>
            v{version}
            {isDraft && ' (черновик)'}
            {isDirty && ' •'}
          </span>
          {/* Loaded version badge */}
          {loadedVersionLabel && (
            <span className={cn(
              'flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
              'bg-blue-500/20 text-blue-400'
            )}>
              📦 {loadedVersionLabel}
            </span>
          )}
        </div>

        {/* Right side - Form width slider, Save, Menu */}
        <div className="flex items-center gap-2">
          {/* Form width slider with +/- buttons (50-150%, center at 100%) */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => handleWidthChange(-2)}
              disabled={formWidth <= 70}
              className={cn(
                'p-1 rounded',
                formWidth <= 70 ? 'opacity-30 cursor-not-allowed' : '',
                isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'
              )}
              title="Уменьшить ширину"
            >
              <Minus className={cn('w-3.5 h-3.5', theme.textMuted)} />
            </button>

            <input
              type="range"
              min={70}
              max={130}
              step={2}
              value={formWidth}
              onChange={(e) => onFormWidthChange(parseInt(e.target.value, 10))}
              className={cn(
                'w-24 h-1.5 rounded-lg appearance-none cursor-pointer',
                isDark ? 'bg-white/20' : 'bg-gray-300',
                '[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent-red [&::-webkit-slider-thumb]:cursor-pointer',
                '[&::-moz-range-thumb]:w-3 [&::-moz-range-thumb]:h-3 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-accent-red [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:border-0'
              )}
              title="Ширина формы (100% по центру)"
            />

            <button
              onClick={() => handleWidthChange(2)}
              disabled={formWidth >= 130}
              className={cn(
                'p-1 rounded',
                formWidth >= 130 ? 'opacity-30 cursor-not-allowed' : '',
                isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'
              )}
              title="Увеличить ширину"
            >
              <Plus className={cn('w-3.5 h-3.5', theme.textMuted)} />
            </button>

            <span className={cn('text-xs ml-1 min-w-[36px]', theme.textMuted)}>
              {formWidth}%
            </span>
          </div>

          <div className={cn('h-6 w-px', isDark ? 'bg-white/20' : 'bg-gray-300')} />

          {/* Сохранить - синяя кнопка при изменениях, серая когда нет */}
          <Button
            size="sm"
            onClick={onSave}
            disabled={!isDirty || isSaving}
            className={cn(
              'gap-2',
              isDirty
                ? 'bg-blue-600 text-white hover:bg-blue-700 border-blue-600'
                : isDark
                  ? 'bg-[#1e1e22] border border-white/10 text-gray-500'
                  : 'bg-gray-100 border border-gray-300 text-gray-400'
            )}
          >
            {isSaving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Сохранить
          </Button>

          {/* Theme toggle button - gray, no red hover */}
          {onToggleTheme && (
            <button
              onClick={onToggleTheme}
              className={cn(
                'w-8 h-8 flex items-center justify-center rounded-lg',
                isDark
                  ? 'hover:bg-white/10'
                  : 'hover:bg-gray-100'
              )}
              title={isDark ? 'Светлая тема' : 'Тёмная тема'}
            >
              {isDark ? (
                <Sun className="w-4 h-4 text-gray-400" />
              ) : (
                <Moon className="w-4 h-4 text-gray-500" />
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default BuilderHeader;
