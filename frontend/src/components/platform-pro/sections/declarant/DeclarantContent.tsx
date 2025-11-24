// =============================================================================
// Declarant Content - Main Component
// =============================================================================

import React from 'react';
import { usePlatformPro } from '@/contexts/PlatformProContext';
import { useDeclarant } from '@/hooks/useDeclarant';
import { FileText, Plus, Download, Trash2, Eye } from 'lucide-react';

const DeclarantContent: React.FC = () => {
  const { isDark } = usePlatformPro();
  const {
    batches,
    stats,
    isLoading,
    selectedBatchIds,
  } = useDeclarant();

  const theme = isDark ? {
    page: 'bg-[#1a1a1e]',
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400',
    },
    card: 'bg-[#232328] border-gray-700',
    button: {
      default: 'text-gray-300 hover:text-white hover:bg-white/10',
      danger: 'text-gray-300 hover:text-white hover:bg-white/10',
    },
  } : {
    page: 'bg-[#f4f4f4]',
    text: {
      primary: 'text-gray-900',
      secondary: 'text-[#6b7280]',
    },
    card: 'bg-white border-gray-200 shadow-sm',
    button: {
      default: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100',
      danger: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100',
    },
  };

  if (isLoading) {
    return (
      <div className={`flex items-center justify-center h-full ${theme.page}`}>
        <div className={theme.text.primary}>Загрузка данных...</div>
      </div>
    );
  }

  return (
    <div className={`flex-1 overflow-auto p-6 space-y-8 ${theme.page}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className={`text-2xl font-bold mb-1 ${theme.text.primary}`}>
            Декларация AI
          </h2>
          <p className={`text-sm ${theme.text.secondary}`}>
            Управление пакетной обработкой деклараций ФТС 3.0
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <button
            className={`px-3 py-2 rounded-lg flex items-center gap-2 ${theme.button.danger}`}
            disabled={selectedBatchIds.length === 0}
          >
            <Trash2 className="w-4 h-4" />
            Удалить
          </button>
          <button className={`px-3 py-2 rounded-lg flex items-center gap-2 ${theme.button.default}`}>
            <Download className="w-4 h-4" />
            Экспорт
          </button>
          <button className={`px-3 py-2 rounded-lg flex items-center gap-2 ${theme.button.default}`}>
            <Eye className="w-4 h-4" />
            Просмотр
          </button>
          <button
            className={`px-4 py-2 bg-accent-red text-white rounded-lg hover:bg-accent-red/90 flex items-center gap-2 ${
              isDark ? '' : 'shadow-sm'
            }`}
          >
            <Plus className="w-4 h-4" />
            Создать пакет
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className={`rounded-2xl p-4 border ${theme.card}`}>
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-accent-red/10">
                <FileText className="w-5 h-5 text-accent-red" />
              </div>
              <div>
                <p className={`text-sm ${theme.text.secondary}`}>Всего пакетов</p>
                <p className={`text-2xl font-bold font-mono ${theme.text.primary}`}>
                  {stats.total_batches}
                </p>
              </div>
            </div>
          </div>

          <div className={`rounded-2xl p-4 border ${theme.card}`}>
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-[#13b981]/10">
                <FileText className="w-5 h-5 text-[#13b981]" />
              </div>
              <div>
                <p className={`text-sm ${theme.text.secondary}`}>Завершено</p>
                <p className={`text-2xl font-bold font-mono ${theme.text.primary}`}>
                  {stats.completed_batches}
                </p>
              </div>
            </div>
          </div>

          <div className={`rounded-2xl p-4 border ${theme.card}`}>
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-[#f59e0b]/10">
                <FileText className="w-5 h-5 text-[#f59e0b]" />
              </div>
              <div>
                <p className={`text-sm ${theme.text.secondary}`}>В обработке</p>
                <p className={`text-2xl font-bold font-mono ${theme.text.primary}`}>
                  {stats.processing_batches}
                </p>
              </div>
            </div>
          </div>

          <div className={`rounded-2xl p-4 border ${theme.card}`}>
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-[#a855f7]/10">
                <FileText className="w-5 h-5 text-[#a855f7]" />
              </div>
              <div>
                <p className={`text-sm ${theme.text.secondary}`}>Документов</p>
                <p className={`text-2xl font-bold font-mono ${theme.text.primary}`}>
                  {stats.total_documents}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Table Placeholder */}
      <div className={`rounded-2xl p-6 border ${theme.card}`}>
        <div className="space-y-4">
          <div className={`flex items-center justify-between pb-4 border-b border-gray-700`}>
            <h3 className={`text-lg font-semibold ${theme.text.primary}`}>
              Пакеты деклараций
            </h3>
            <div className="flex items-center gap-2">
              <span className={`text-sm ${theme.text.secondary}`}>
                Всего: {batches.length}
              </span>
            </div>
          </div>

          {/* Simple table */}
          <div className="space-y-2">
            {batches.map((batch) => (
              <div
                key={batch.id}
                className={`p-4 rounded-lg border ${theme.card} hover:bg-white/5 cursor-pointer`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className={`font-mono font-medium ${theme.text.primary}`}>
                      {batch.number}
                    </span>
                    <span className={`ml-4 text-sm ${theme.text.secondary}`}>
                      {batch.documents_processed}/{batch.documents_total} документов
                    </span>
                  </div>
                  <div className={`text-sm ${theme.text.secondary}`}>
                    {new Date(batch.created_at).toLocaleDateString('ru-RU')}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DeclarantContent;
