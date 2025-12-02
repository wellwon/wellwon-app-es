// =============================================================================
// VersionsPanel - Панель версий шаблона
// =============================================================================

import React, { useState, useEffect, useCallback } from 'react';
import {
  GitBranch,
  Clock,
  Check,
  Trash2,
  Save,
  Download,
  Loader2,
  RefreshCw,
  Layers,
  FileText,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useFormBuilderStore } from '../../../stores/useFormBuilderStore';
import {
  getFormVersions,
  createFormVersion,
  restoreFormVersion,
  deleteFormVersion,
  type FormDefinitionVersion,
} from '../../../api/form-templates-api';

interface VersionsPanelProps {
  isDark: boolean;
}

export const VersionsPanel: React.FC<VersionsPanelProps> = ({ isDark }) => {
  const { template, setLoadedVersionLabel } = useFormBuilderStore();
  const [versions, setVersions] = useState<FormDefinitionVersion[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isRestoring, setIsRestoring] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const documentModeId = template?.documentModeId;

  const theme = isDark
    ? {
        bg: 'bg-[#1a1a1e]',
        text: 'text-white',
        textMuted: 'text-gray-400',
        textSecondary: 'text-gray-500',
        cardBg: 'bg-[#232328]',
        border: 'border-white/10',
        hover: 'hover:bg-white/5',
        versionBg: 'bg-[#232328]',
        currentBadge: 'bg-green-500/20 text-green-400',
      }
    : {
        bg: 'bg-[#f4f4f4]',
        text: 'text-gray-900',
        textMuted: 'text-gray-500',
        textSecondary: 'text-gray-400',
        cardBg: 'bg-white',
        border: 'border-gray-200',
        hover: 'hover:bg-gray-50',
        versionBg: 'bg-white',
        currentBadge: 'bg-green-500/20 text-green-600',
      };

  // Load versions
  const loadVersions = useCallback(async () => {
    if (!documentModeId) return;

    setIsLoading(true);
    setError(null);
    try {
      const data = await getFormVersions(documentModeId);
      setVersions(data);
    } catch (err: any) {
      console.error('Error loading versions:', err);
      setError('Ошибка загрузки версий');
    } finally {
      setIsLoading(false);
    }
  }, [documentModeId]);

  useEffect(() => {
    loadVersions();
  }, [loadVersions]);

  // Create new version
  const handleCreateVersion = async () => {
    if (!documentModeId) return;

    setIsCreating(true);
    setError(null);
    try {
      await createFormVersion(documentModeId);
      await loadVersions();
    } catch (err: any) {
      console.error('Error creating version:', err);
      setError('Ошибка создания версии');
    } finally {
      setIsCreating(false);
    }
  };

  // Restore version
  const handleRestoreVersion = async (version: FormDefinitionVersion) => {
    if (!documentModeId) return;

    const versionLabel = version.version_label || `Версия ${version.version_number}`;
    if (!window.confirm(`Загрузить "${versionLabel}"? Текущие изменения будут потеряны.`)) {
      return;
    }

    setIsRestoring(version.version_number);
    setError(null);
    try {
      await restoreFormVersion(documentModeId, version.version_number);
      // Save version label to store before reload
      if (setLoadedVersionLabel) {
        localStorage.setItem('formBuilder.loadedVersionLabel', versionLabel);
      }
      // Reload the page to get updated sections
      window.location.reload();
    } catch (err: any) {
      console.error('Error restoring version:', err);
      setError('Ошибка восстановления версии');
      setIsRestoring(null);
    }
  };

  // Delete version
  const handleDeleteVersion = async (e: React.MouseEvent, version: FormDefinitionVersion) => {
    e.stopPropagation();
    if (!documentModeId) return;

    const versionLabel = version.version_label || `Версия ${version.version_number}`;
    if (!window.confirm(`Удалить "${versionLabel}"?`)) {
      return;
    }

    try {
      await deleteFormVersion(documentModeId, version.version_number);
      await loadVersions();
    } catch (err: any) {
      console.error('Error deleting version:', err);
      setError(err.response?.data?.detail || 'Ошибка удаления версии');
    }
  };

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className={cn('h-full flex flex-col', theme.bg)}>
      {/* Header */}
      <div className={cn('p-4 border-b', theme.border)}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <GitBranch className={cn('w-5 h-5', theme.textMuted)} />
            <h3 className={cn('font-semibold', theme.text)}>Версии шаблона</h3>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={loadVersions}
            disabled={isLoading}
            className={cn('h-8 w-8', isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100')}
          >
            <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
          </Button>
        </div>

        {/* Кнопка Сохранить версию - красная */}
        <Button
          size="sm"
          onClick={handleCreateVersion}
          disabled={isCreating || !documentModeId}
          className="w-full gap-2 bg-accent-red hover:bg-accent-red/90 text-white"
        >
          {isCreating ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Сохранить версию
        </Button>

        {/* Error message */}
        {error && (
          <div className="mt-3 p-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-500 text-sm">
            {error}
          </div>
        )}
      </div>

      {/* Versions list */}
      <div className="flex-1 overflow-y-auto p-3">
        {isLoading ? (
          <div className={cn('flex items-center justify-center py-12', theme.textMuted)}>
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
        ) : versions.length === 0 ? (
          <div className={cn('text-center py-12', theme.textMuted)}>
            <GitBranch className="w-12 h-12 mx-auto mb-4 opacity-30" />
            <p className="text-sm">Нет сохраненных версий</p>
            <p className="text-xs mt-1">Нажмите "Сохранить версию" для создания</p>
          </div>
        ) : (
          <div className="space-y-2">
            {versions.map((version) => {
              const isRestoringThis = isRestoring === version.version_number;
              const versionLabel = version.version_label || `Версия ${version.version_number}`;

              return (
                <div
                  key={version.id}
                  className={cn(
                    'rounded-xl border p-3',
                    theme.versionBg,
                    theme.border
                  )}
                >
                  {/* Row 1: Version name + Current badge + Load button */}
                  <div className="flex items-center gap-2">
                    {/* Version name */}
                    <span className={cn('font-medium flex-1 truncate', theme.text)}>
                      {versionLabel}
                    </span>

                    {/* Current badge */}
                    {version.is_current && (
                      <span className={cn(
                        'flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
                        theme.currentBadge
                      )}>
                        <Check className="w-3 h-3" />
                        Текущая
                      </span>
                    )}

                    {/* Load button (only for non-current versions) */}
                    {!version.is_current && (
                      <button
                        onClick={() => handleRestoreVersion(version)}
                        disabled={isRestoringThis}
                        className={cn(
                          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium',
                          'bg-accent-red text-white hover:bg-accent-red/90',
                          'disabled:opacity-50'
                        )}
                      >
                        {isRestoringThis ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Download className="w-3 h-3" />
                        )}
                        Загрузить
                      </button>
                    )}

                    {/* Delete button (only for non-current versions) */}
                    {!version.is_current && (
                      <button
                        onClick={(e) => handleDeleteVersion(e, version)}
                        className={cn(
                          'p-1.5 rounded-lg text-accent-red hover:bg-accent-red/10'
                        )}
                        title="Удалить версию"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>

                  {/* Row 2: Date + Stats */}
                  <div className={cn('flex items-center gap-4 mt-2 text-xs', theme.textSecondary)}>
                    {/* Date */}
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDate(version.created_at)}
                    </span>

                    {/* Separator */}
                    <span>•</span>

                    {/* Sections count */}
                    <span className="flex items-center gap-1">
                      <Layers className="w-3 h-3" />
                      {version.sections_count} секций
                    </span>

                    {/* Separator */}
                    <span>•</span>

                    {/* Fields count */}
                    <span className="flex items-center gap-1">
                      <FileText className="w-3 h-3" />
                      {version.fields_count} полей
                    </span>
                  </div>

                  {/* Change description if exists */}
                  {version.change_description && (
                    <p className={cn('text-xs mt-2 italic', theme.textMuted)}>
                      {version.change_description}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className={cn('p-3 border-t text-xs text-center', theme.border, theme.textMuted)}>
        Сохраняйте версии перед важными изменениями
      </div>
    </div>
  );
};

export default VersionsPanel;
