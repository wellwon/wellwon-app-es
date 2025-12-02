// =============================================================================
// DynamicFormPage - Page wrapper for dynamic form rendering
// =============================================================================

import React, { useState, useEffect, useCallback } from 'react';
import {
  Save,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  FileText,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { DynamicFormRenderer } from '@/declarant/components/dynamic-forms/DynamicFormRenderer';
import { getFormDefinition, syncFormDefinition } from '@/declarant/api/form-definitions-api';
import type { FormDefinition } from '@/declarant/types/form-definitions';

// =============================================================================
// Props
// =============================================================================

interface DynamicFormPageProps {
  documentModeId: string;
  gfCode?: string;
  typeName?: string;
  isDark: boolean;
  onBack: () => void;
  onSave?: (values: Record<string, unknown>) => void;
}

// =============================================================================
// Component
// =============================================================================

export const DynamicFormPage: React.FC<DynamicFormPageProps> = ({
  documentModeId,
  gfCode,
  typeName,
  isDark,
  onBack,
  onSave,
}) => {
  // State
  const [definition, setDefinition] = useState<FormDefinition | null>(null);
  const [formValues, setFormValues] = useState<Record<string, unknown>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);

  // Theme
  const theme = isDark
    ? {
        bg: 'bg-[#1a1a1e]',
        cardBg: 'bg-[#232328]',
        text: 'text-white',
        textSecondary: 'text-gray-400',
        textMuted: 'text-gray-500',
        border: 'border-white/10',
        button: {
          primary: 'bg-accent-red text-white hover:bg-accent-red/90',
          secondary: 'bg-white/5 border-white/10 text-gray-300 hover:bg-white/10',
          ghost: 'text-gray-300 hover:text-white hover:bg-white/10',
        },
      }
    : {
        bg: 'bg-[#f4f4f4]',
        cardBg: 'bg-white',
        text: 'text-gray-900',
        textSecondary: 'text-gray-600',
        textMuted: 'text-gray-400',
        border: 'border-gray-300',
        button: {
          primary: 'bg-accent-red text-white hover:bg-accent-red/90 shadow-sm',
          secondary: 'bg-gray-50 border-gray-300 text-gray-600 hover:bg-gray-100',
          ghost: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100',
        },
      };

  // Load form definition
  const loadDefinition = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const def = await getFormDefinition(documentModeId);
      setDefinition(def);
      setFormValues(def.default_values || {});
    } catch (err) {
      console.error('Error loading form definition:', err);
      // Try to sync from API if not found
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        (err as { response?: { status?: number } }).response?.status === 404
      ) {
        setError('Форма не найдена. Попробуйте синхронизировать.');
      } else {
        setError(getErrorMessage(err));
      }
    } finally {
      setIsLoading(false);
    }
  }, [documentModeId]);

  // Sync form definition from Kontur API
  const handleSync = async () => {
    setIsSyncing(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const result = await syncFormDefinition(documentModeId);
      if (result.success) {
        const updated = result.forms_created + result.forms_updated;
        setSuccessMessage(result.message || `Форма синхронизирована: ${updated} обновлено`);
        await loadDefinition();
      } else {
        setError(result.message || 'Ошибка синхронизации');
      }
    } catch (err) {
      console.error('Error syncing form definition:', err);
      setError(getErrorMessage(err));
    } finally {
      setIsSyncing(false);
    }
  };

  // Handle form value changes
  const handleFormChange = (values: Record<string, unknown>) => {
    setFormValues(values);
    setIsDirty(true);
  };

  // Handle save
  const handleSave = async () => {
    if (!onSave) return;

    setIsSaving(true);
    setError(null);
    try {
      await onSave(formValues);
      setIsDirty(false);
      setSuccessMessage('Данные сохранены');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      console.error('Error saving form:', err);
      setError(getErrorMessage(err));
    } finally {
      setIsSaving(false);
    }
  };

  // Initial load
  useEffect(() => {
    loadDefinition();
  }, [loadDefinition]);

  // Clear messages after timeout
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  return (
    <div className={cn('flex flex-col h-full', theme.bg)}>
      {/* Header */}
      <div className={cn('flex items-center justify-between px-6 py-4 border-b', theme.cardBg, theme.border)}>
        <div className="flex items-center gap-4">
          {/* Title */}
          <div>
            <div className="flex items-center gap-2">
              <FileText className={cn('w-5 h-5', theme.textSecondary)} />
              <h1 className={cn('text-lg font-semibold', theme.text)}>
                {typeName || definition?.type_name || 'Форма документа'}
              </h1>
            </div>
            <div className={cn('flex items-center gap-2 text-sm', theme.textMuted)}>
              {gfCode && (
                <>
                  <span className="font-mono">{gfCode}</span>
                  <span>•</span>
                </>
              )}
              <span className="font-mono">{documentModeId}</span>
              {definition?.version && (
                <>
                  <span>•</span>
                  <span>v{definition.version}</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Sync button */}
          <button
            onClick={handleSync}
            disabled={isSyncing}
            className={cn(
              'h-9 px-3 flex items-center gap-2 rounded-xl border',
              theme.button.secondary
            )}
          >
            <RefreshCw className={cn('w-4 h-4', isSyncing && 'animate-spin')} />
            <span className="text-sm">{isSyncing ? 'Синхронизация...' : 'Синхронизировать'}</span>
          </button>

          {/* Save button */}
          {onSave && (
            <button
              onClick={handleSave}
              disabled={isSaving || !isDirty}
              className={cn(
                'h-9 px-4 flex items-center gap-2 rounded-xl',
                isDirty ? theme.button.primary : theme.button.secondary,
                (!isDirty || isSaving) && 'opacity-50 cursor-not-allowed'
              )}
            >
              <Save className="w-4 h-4" />
              <span className="text-sm font-medium">
                {isSaving ? 'Сохранение...' : 'Сохранить'}
              </span>
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      {(error || successMessage) && (
        <div className="px-6 pt-4">
          {error && (
            <div
              className={cn(
                'p-3 rounded-xl flex items-center gap-3',
                isDark ? 'bg-red-500/10 text-red-400' : 'bg-red-50 text-red-700'
              )}
            >
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm flex-1">{error}</span>
              <button
                onClick={() => setError(null)}
                className="p-1 rounded hover:bg-black/10"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
          {successMessage && (
            <div
              className={cn(
                'p-3 rounded-xl flex items-center gap-3',
                isDark ? 'bg-green-500/10 text-green-400' : 'bg-green-50 text-green-700'
              )}
            >
              <CheckCircle className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm flex-1">{successMessage}</span>
              <button
                onClick={() => setSuccessMessage(null)}
                className="p-1 rounded hover:bg-black/10"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-full">
            <RefreshCw className={cn('w-8 h-8 animate-spin mb-4', theme.textSecondary)} />
            <p className={cn('text-sm', theme.textSecondary)}>Загрузка формы...</p>
          </div>
        ) : !definition ? (
          <div className="flex flex-col items-center justify-center h-full">
            <AlertCircle className={cn('w-12 h-12 mb-4', theme.textMuted)} />
            <p className={cn('text-lg font-medium mb-2', theme.text)}>
              Форма не найдена
            </p>
            <p className={cn('text-sm mb-4', theme.textSecondary)}>
              Определение формы для {documentModeId} не найдено в базе данных
            </p>
            <button
              onClick={handleSync}
              disabled={isSyncing}
              className={cn(
                'h-10 px-4 flex items-center gap-2 rounded-xl',
                theme.button.primary
              )}
            >
              <RefreshCw className={cn('w-4 h-4', isSyncing && 'animate-spin')} />
              <span className="text-sm font-medium">
                {isSyncing ? 'Загрузка из Kontur API...' : 'Загрузить из Kontur API'}
              </span>
            </button>
          </div>
        ) : (
          <DynamicFormRenderer
            definition={definition}
            initialValues={formValues}
            isDark={isDark}
            onChange={handleFormChange}
          />
        )}
      </div>
    </div>
  );
};

// =============================================================================
// Helpers
// =============================================================================

function getErrorMessage(err: unknown): string {
  if (err && typeof err === 'object') {
    const axiosErr = err as {
      response?: { data?: { detail?: string } };
      message?: string;
    };
    if (axiosErr.response?.data?.detail) {
      return axiosErr.response.data.detail;
    }
    if (axiosErr.message) {
      return axiosErr.message;
    }
  }
  return 'Неизвестная ошибка';
}

export default DynamicFormPage;
