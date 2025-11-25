// =============================================================================
// Declarant Content - Standalone Application for Platform Pro
// =============================================================================
// Полная копия верстки "Декларация AI" с мок-данными
// Включает собственный sidebar, header и переключатель темы

import React, { useState } from 'react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  FileText,
  CheckCircle,
  Clock,
  AlertCircle,
  Plus,
  Trash2,
  Download,
  Eye,
  Copy,
  Activity,
  BarChart3,
  Truck,
  DollarSign,
  LineChart,
  Settings,
  Users,
  ChevronLeft,
  ChevronRight,
  ArrowLeft,
  FileJson,
  Sun,
  Moon,
  ScanText
} from 'lucide-react';

// =============================================================================
// Mock Data
// =============================================================================

const mockStats = {
  total_batches: 6,
  completed_batches: 5,
  processing_batches: 0,
  total_documents: 55,
};

const mockBatches = [
  {
    id: '1',
    number: 'FTS-00104',
    status: 'completed',
    docs: '3/3',
    extracts: 3,
    date: '21 нояб. 2025, 11:25',
    icon: CheckCircle,
    iconColor: 'text-accent-green',
    statusText: 'Завершено'
  },
  {
    id: '2',
    number: 'FTS-00103',
    status: 'completed',
    docs: '4/4',
    extracts: 4,
    date: '14 нояб. 2025, 11:42',
    icon: CheckCircle,
    iconColor: 'text-accent-green',
    statusText: 'Завершено'
  },
  {
    id: '3',
    number: 'FTS-00102',
    status: 'error',
    docs: '0/3',
    extracts: 0,
    date: '09 нояб. 2025, 17:19',
    icon: AlertCircle,
    iconColor: 'text-accent-red',
    statusText: 'Ошибка'
  },
  {
    id: '4',
    number: 'FTS-00101',
    status: 'completed',
    docs: '3/3',
    extracts: 3,
    date: '09 нояб. 2025, 17:15',
    icon: CheckCircle,
    iconColor: 'text-accent-green',
    statusText: 'Завершено'
  },
  {
    id: '5',
    number: 'FTS-00100',
    status: 'completed',
    docs: '3/3',
    extracts: 3,
    date: '09 нояб. 2025, 09:58',
    icon: CheckCircle,
    iconColor: 'text-accent-green',
    statusText: 'Завершено'
  },
  {
    id: '6',
    number: 'FTS-00099',
    status: 'completed',
    docs: '3/3',
    extracts: 3,
    date: '09 нояб. 2025, 09:18',
    icon: CheckCircle,
    iconColor: 'text-accent-green',
    statusText: 'Завершено'
  },
  {
    id: '7',
    number: 'FTS-00098',
    status: 'processing',
    docs: '2/5',
    extracts: 2,
    date: '08 нояб. 2025, 15:30',
    icon: Clock,
    iconColor: 'text-amber-500',
    statusText: 'В обработке'
  },
  {
    id: '8',
    number: 'FTS-00097',
    status: 'completed',
    docs: '6/6',
    extracts: 6,
    date: '07 нояб. 2025, 14:22',
    icon: CheckCircle,
    iconColor: 'text-accent-green',
    statusText: 'Завершено'
  },
  {
    id: '9',
    number: 'FTS-00096',
    status: 'error',
    docs: '1/4',
    extracts: 1,
    date: '06 нояб. 2025, 10:45',
    icon: AlertCircle,
    iconColor: 'text-accent-red',
    statusText: 'Ошибка'
  },
  {
    id: '10',
    number: 'FTS-00095',
    status: 'completed',
    docs: '2/2',
    extracts: 2,
    date: '05 нояб. 2025, 16:18',
    icon: CheckCircle,
    iconColor: 'text-accent-green',
    statusText: 'Завершено'
  },
  {
    id: '11',
    number: 'FTS-00094',
    status: 'processing',
    docs: '0/3',
    extracts: 0,
    date: '04 нояб. 2025, 09:05',
    icon: Clock,
    iconColor: 'text-amber-500',
    statusText: 'В обработке'
  },
];

// =============================================================================
// SidebarMock Component
// =============================================================================

const SidebarMock = ({
  collapsed,
  toggleSidebar,
  activeSection,
  setActiveSection
}: {
  collapsed: boolean;
  toggleSidebar: () => void;
  activeSection: string;
  setActiveSection: (id: string) => void;
}) => {
  const theme = {
    sidebar: 'bg-[#232328] border-white/10',
    header: 'border-white/10',
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400'
    },
    button: {
      default: 'text-gray-300 hover:text-white hover:bg-white/10',
      active: 'bg-accent-red/20 text-white border-accent-red/30'
    },
    profile: 'bg-white/5 hover:bg-white/10'
  };

  const sections = [
    { id: 'dashboard', label: 'Декларации AI', icon: ScanText },
    { id: 'logistics', label: 'Документы', icon: FileText },
    { id: 'finance', label: 'Финансы', icon: DollarSign },
    { id: 'analytics', label: 'Аналитика', icon: LineChart },
    { id: 'settings', label: 'Настройки', icon: Settings },
    { id: 'team', label: 'Команда', icon: Users },
  ].map(s => ({ ...s, active: s.id === activeSection }));

  return (
    <div className={`
      ${collapsed ? 'w-20' : 'w-[264px]'}
      border-r flex flex-col h-screen
      ${theme.sidebar}
    `}>
      {/* Header with logo */}
      <div className={`h-16 flex items-center ${collapsed ? 'justify-center' : 'justify-between px-4'} border-b ${theme.header}`}>
        {!collapsed && (
          <div className="relative">
            <span className="text-accent-red font-black text-xl">Well</span>
            <span className="text-white font-black text-xl">Won</span>
            <span className="text-white text-xl font-extrabold"> Pro</span>
            <div className="absolute -bottom-0.5 left-0 w-10 h-0.5 bg-accent-red"></div>
          </div>
        )}

        <button
          onClick={toggleSidebar}
          className="h-8 w-8 rounded-lg flex items-center justify-center bg-white/5 border border-white/10 hover:border-white/20 hover:scale-105 transition-all text-gray-400 hover:text-white hover:bg-white/10"
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto py-4 px-3">
        <div className="space-y-3">
          {!collapsed && (
            <div className={`text-xs font-semibold uppercase tracking-wider px-3 ${theme.text.secondary}`}>
              Основное
            </div>
          )}
          <div className={collapsed ? 'space-y-2' : 'space-y-1'}>
            {sections.slice(0, 2).map((section) => {
              const Icon = section.icon;

              if (collapsed) {
                return (
                  <div
                    key={section.id}
                    className="group relative flex justify-center cursor-pointer"
                    title={section.label}
                    onClick={() => setActiveSection(section.id)}
                  >
                    <div className={`
                      w-12 h-12 flex items-center justify-center rounded-xl border
                      ${section.active
                        ? 'bg-accent-red/20 border-accent-red/30'
                        : 'border-white/10 hover:bg-medium-gray/80 hover:border-accent-red/50'
                      }
                    `}>
                      <Icon size={20} className={section.active ? 'text-accent-red' : 'text-gray-400 group-hover:text-accent-red'} />
                    </div>
                  </div>
                );
              }

              return (
                <div
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={`
                    flex items-center px-3 py-2.5 rounded-xl cursor-pointer
                    ${section.active
                      ? `${theme.button.active} border shadow-sm`
                      : theme.button.default
                    }
                  `}
                >
                  <Icon size={20} className="mr-3" />
                  <span className="font-medium text-sm">{section.label}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="space-y-3 mt-6">
          {!collapsed && (
            <div className={`text-xs font-semibold uppercase tracking-wider px-3 ${theme.text.secondary}`}>
              Управление
            </div>
          )}
          <div className={collapsed ? 'space-y-2' : 'space-y-1'}>
            {sections.slice(2).map((section) => {
              const Icon = section.icon;

              if (collapsed) {
                return (
                  <div
                    key={section.id}
                    className="group relative flex justify-center cursor-pointer"
                    title={section.label}
                    onClick={() => setActiveSection(section.id)}
                  >
                    <div className={`
                      w-12 h-12 flex items-center justify-center rounded-xl border
                      ${section.active
                        ? 'bg-accent-red/20 border-accent-red/30'
                        : 'border-white/10 hover:bg-medium-gray/80 hover:border-accent-red/50'
                      }
                    `}>
                      <Icon size={20} className={section.active ? 'text-accent-red' : 'text-gray-400 group-hover:text-accent-red'} />
                    </div>
                  </div>
                );
              }

              return (
                <div
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={`
                    flex items-center px-3 py-2.5 rounded-xl cursor-pointer
                    ${section.active
                      ? `${theme.button.active} border shadow-sm`
                      : theme.button.default
                    }
                  `}
                >
                  <Icon size={20} className="mr-3" />
                  <span className="font-medium text-sm">{section.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Profile at bottom */}
      <div className={`border-t p-3 ${theme.header}`}>
        <div className={`flex ${collapsed ? 'justify-center' : 'items-center gap-3'} p-2 rounded-lg cursor-pointer ${theme.profile}`}>
          <Avatar className="h-9 w-9">
            <AvatarFallback className="bg-accent-red/20 text-accent-red font-semibold text-sm">
              ТП
            </AvatarFallback>
          </Avatar>

          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">Тестовый Пользователь</p>
              <p className="text-xs text-gray-400 truncate">test@example.com</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// =============================================================================
// HeaderBarMock Component
// =============================================================================

const HeaderBarMock = ({
  isDark,
  toggleTheme,
  activeSection
}: {
  isDark: boolean;
  toggleTheme: () => void;
  activeSection: string;
}) => {
  const sectionLabels: Record<string, string> = {
    dashboard: 'Декларации AI',
    logistics: 'Документы',
    finance: 'Финансы',
    analytics: 'Аналитика',
    settings: 'Настройки',
    team: 'Команда'
  };

  const theme = isDark ? {
    header: 'bg-[#232328] border-white/10',
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400'
    },
    button: {
      default: 'text-gray-300 hover:text-white hover:bg-white/10',
      active: 'bg-gray-100 text-gray-900 hover:bg-gray-200'
    }
  } : {
    header: 'bg-white border-gray-300 shadow-sm',
    text: {
      primary: 'text-gray-900',
      secondary: 'text-[#6b7280]'
    },
    button: {
      default: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100',
      active: 'bg-gray-100 text-gray-900 hover:bg-gray-200 shadow-sm'
    }
  };

  return (
    <div className={`h-16 border-b flex items-center justify-between ${theme.header}`}>
      <div className="flex items-center px-6">
        <button
          className={`mr-4 h-8 px-3 flex items-center gap-2 rounded-xl border ${
            isDark
              ? 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/10 hover:text-white hover:border-white/20'
              : 'bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200 hover:text-gray-900'
          }`}
          aria-label="Назад"
        >
          <ArrowLeft size={16} />
          <span className="text-sm">Назад</span>
        </button>

        <div className="flex items-center gap-2 text-sm">
          <span className={theme.text.secondary}>Платформа</span>
          <span className={theme.text.secondary}>/</span>
          <span className={`font-semibold ${theme.text.primary}`}>{sectionLabels[activeSection]}</span>
        </div>
      </div>

      <div className="flex items-center gap-2 px-6">
        <button className={`px-3 py-2 rounded-lg flex items-center gap-2 ${theme.button.default}`}>
          <FileText className="w-4 h-4" />
          Декларации
        </button>
        <button className={`px-3 py-2 rounded-lg flex items-center gap-2 ${theme.button.default}`}>
          <FileJson className="w-4 h-4" />
          Шаблоны
        </button>

        <div className={`ml-2 w-px h-6 ${isDark ? 'bg-white/10' : 'bg-gray-300'}`} />
        <button
          onClick={toggleTheme}
          className={`p-2 rounded-lg ${theme.button.default}`}
          aria-label={isDark ? "Переключить на светлую тему" : "Переключить на темную тему"}
        >
          {isDark ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </div>
    </div>
  );
};

// =============================================================================
// Main DeclarantContent Component
// =============================================================================

const DeclarantContent: React.FC = () => {
  const [isDark, setIsDark] = useState(() => {
    const saved = sessionStorage.getItem('declarant-theme-dark');
    return saved ? JSON.parse(saved) : false;
  });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const saved = sessionStorage.getItem('declarant-sidebar-collapsed');
    return saved ? JSON.parse(saved) : false;
  });
  const [activeSection, setActiveSection] = useState('dashboard');
  const [rowsPerPage, setRowsPerPage] = useState(() => {
    const saved = sessionStorage.getItem('declarant-rows-per-page');
    return saved ? Number(saved) : 10;
  });
  const [currentPage, setCurrentPage] = useState(1);

  const toggleTheme = () => {
    const newValue = !isDark;
    setIsDark(newValue);
    sessionStorage.setItem('declarant-theme-dark', JSON.stringify(newValue));
  };

  const toggleSidebar = () => {
    const newValue = !sidebarCollapsed;
    setSidebarCollapsed(newValue);
    sessionStorage.setItem('declarant-sidebar-collapsed', JSON.stringify(newValue));
  };

  // Пагинация
  const totalItems = mockBatches.length;
  const totalPages = Math.ceil(totalItems / rowsPerPage);
  const startIndex = (currentPage - 1) * rowsPerPage;
  const endIndex = Math.min(startIndex + rowsPerPage, totalItems);
  const paginatedBatches = mockBatches.slice(startIndex, endIndex);

  const handleRowsPerPageChange = (value: string) => {
    const newValue = Number(value);
    setRowsPerPage(newValue);
    setCurrentPage(1);
    sessionStorage.setItem('declarant-rows-per-page', value);
  };

  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page);
    }
  };

  const theme = isDark ? {
    page: 'bg-[#1a1a1e]',
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400'
    },
    card: {
      background: 'bg-[#232328]',
      border: 'border-white/10'
    },
    button: {
      default: 'text-gray-300 hover:text-white hover:bg-white/10',
      danger: 'text-gray-300 hover:text-white hover:bg-white/10'
    },
    table: {
      header: 'border-white/10',
      row: 'divide-white/10 hover:bg-white/5',
      border: 'border-white/10'
    }
  } : {
    page: 'bg-[#f4f4f4]',
    text: {
      primary: 'text-gray-900',
      secondary: 'text-[#6b7280]'
    },
    card: {
      background: 'bg-white',
      border: 'border-gray-300 shadow-sm'
    },
    button: {
      default: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100',
      danger: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
    },
    table: {
      header: 'border-gray-300',
      row: 'divide-gray-300 hover:bg-gray-50',
      border: 'border-gray-300'
    }
  };

  const renderContent = (section: string) => {
    if (section === 'dashboard') {
      return (
        <>
          {/* Заголовок и кнопки действий */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className={`text-2xl font-bold mb-1 ${theme.text.primary}`}>
                Декларация AI
              </h2>
              <p className={`text-sm ${theme.text.secondary}`}>
                Управление пакетной обработкой деклараций ФТС 3.0
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button className={`px-3 py-2 rounded-lg flex items-center gap-2 ${theme.button.danger}`}>
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
              <button className={`px-4 py-2 bg-accent-red text-white rounded-lg hover:bg-accent-red/90 flex items-center gap-2 ${isDark ? '' : 'shadow-sm'}`}>
                <Plus className="w-4 h-4" />
                Создать пакет
              </button>
            </div>
          </div>

          {/* Карточки статистики */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className={`rounded-2xl p-4 border ${theme.card.background} ${theme.card.border}`}>
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-xl bg-accent-red/10">
                  <FileText className="w-5 h-5 text-accent-red" />
                </div>
                <div>
                  <p className={`text-sm ${theme.text.secondary}`}>Всего пакетов</p>
                  <p className={`text-2xl font-bold font-mono ${theme.text.primary}`}>
                    {mockStats.total_batches}
                  </p>
                </div>
              </div>
            </div>

            <div className={`rounded-2xl p-4 border ${theme.card.background} ${theme.card.border}`}>
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-xl bg-[#13b981]/10">
                  <CheckCircle className="w-5 h-5 text-[#13b981]" />
                </div>
                <div>
                  <p className={`text-sm ${theme.text.secondary}`}>Завершено</p>
                  <p className={`text-2xl font-bold font-mono ${theme.text.primary}`}>
                    {mockStats.completed_batches}
                  </p>
                </div>
              </div>
            </div>

            <div className={`rounded-2xl p-4 border ${theme.card.background} ${theme.card.border}`}>
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-xl bg-[#f59e0b]/10">
                  <Clock className="w-5 h-5 text-[#f59e0b]" />
                </div>
                <div>
                  <p className={`text-sm ${theme.text.secondary}`}>В обработке</p>
                  <p className={`text-2xl font-bold font-mono ${theme.text.primary}`}>
                    {mockStats.processing_batches}
                  </p>
                </div>
              </div>
            </div>

            <div className={`rounded-2xl p-4 border ${theme.card.background} ${theme.card.border}`}>
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-xl bg-[#a855f7]/10">
                  <Activity className="w-5 h-5 text-[#a855f7]" />
                </div>
                <div>
                  <p className={`text-sm ${theme.text.secondary}`}>Документов</p>
                  <p className={`text-2xl font-bold font-mono ${theme.text.primary}`}>
                    {mockStats.total_documents}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Таблица деклараций */}
          <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className={`border-b ${theme.table.border}`}>
                    <th className={`text-left py-3 px-4 text-xs font-medium uppercase tracking-wider ${theme.text.secondary}`}>
                        Номер пакета
                      </th>
                      <th className={`text-left py-3 px-4 text-xs font-medium uppercase tracking-wider ${theme.text.secondary}`}>
                        Статус
                      </th>
                      <th className={`text-left py-3 px-4 text-xs font-medium uppercase tracking-wider ${theme.text.secondary}`}>
                        Документы
                      </th>
                      <th className={`text-left py-3 px-4 text-xs font-medium uppercase tracking-wider ${theme.text.secondary}`}>
                        Извлечения
                      </th>
                      <th className={`text-left py-3 px-4 text-xs font-medium uppercase tracking-wider ${theme.text.secondary}`}>
                        Создан
                      </th>
                      <th className={`text-right py-3 px-4 text-xs font-medium uppercase tracking-wider ${theme.text.secondary}`}>
                        Действия
                      </th>
                    </tr>
                  </thead>
                  <tbody className={`divide-y ${theme.table.row.split(' ')[0]}`}>
                    {paginatedBatches.map((batch) => {
                      const Icon = batch.icon;
                      return (
                        <tr
                          key={batch.id}
                          className={`cursor-pointer ${theme.table.row.split(' ').slice(1).join(' ')}`}
                        >
                          <td className="py-3 px-4">
                            <span className={`font-mono text-sm ${theme.text.primary}`}>
                              {batch.number}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-2">
                              <Icon className={`w-4 h-4 ${batch.iconColor}`} />
                              <span className={`text-sm ${batch.iconColor}`}>
                                {batch.statusText}
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <span className={`text-sm ${theme.text.primary}`}>
                              {batch.docs}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <span className={`text-sm ${theme.text.primary}`}>
                              {batch.extracts}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <span className={`text-sm ${theme.text.secondary}`}>
                              {batch.date}
                            </span>
                          </td>
                          <td className="py-3 pl-4 pr-0 text-right">
                            <div className="flex items-center gap-2 justify-end">
                              {/* Кнопка копирования - glass стиль */}
                              <button
                                className={`h-8 px-3 rounded-lg flex items-center justify-center border ${
                                  isDark
                                    ? 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/10 hover:text-white hover:border-white/20'
                                    : 'bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200 hover:text-gray-900'
                                }`}
                                aria-label="Копировать"
                              >
                                <Copy className="h-4 w-4" />
                              </button>

                              {/* Кнопка удаления - accent-red стиль */}
                              <button
                                className="h-8 px-3 rounded-lg flex items-center justify-center bg-accent-red/10 text-accent-red border border-accent-red/20 hover:bg-accent-red/20 hover:border-accent-red/25"
                                aria-label="Удалить"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
            </div>

            <div className={`flex items-center justify-between pt-4 border-t ${theme.table.border}`}>
              {/* Выбор количества строк */}
              <div className="flex items-center gap-2">
                <Select value={String(rowsPerPage)} onValueChange={handleRowsPerPageChange}>
                  <SelectTrigger className={`w-[70px] h-8 focus:outline-none focus:ring-0 focus:ring-offset-0 focus:ring-transparent ${
                    isDark
                      ? 'bg-[#232328] border-white/10 text-white focus:border-white/10 data-[state=open]:border-white/10'
                      : 'bg-white border-gray-200 text-gray-900 focus:border-gray-200 data-[state=open]:border-gray-200'
                  }`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className={isDark
                    ? 'bg-[#232328] border-white/10'
                    : 'bg-white border-gray-200'
                  }>
                    <SelectItem value="10" className={isDark
                      ? 'focus:bg-white/10 focus:text-white text-white'
                      : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'
                    }>10</SelectItem>
                    <SelectItem value="20" className={isDark
                      ? 'focus:bg-white/10 focus:text-white text-white'
                      : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'
                    }>20</SelectItem>
                    <SelectItem value="50" className={isDark
                      ? 'focus:bg-white/10 focus:text-white text-white'
                      : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'
                    }>50</SelectItem>
                    <SelectItem value="100" className={isDark
                      ? 'focus:bg-white/10 focus:text-white text-white'
                      : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'
                    }>100</SelectItem>
                  </SelectContent>
                </Select>
                <span className={`text-sm ${theme.text.secondary}`}>строк на странице</span>
              </div>

              {/* Информация о записях */}
              <div className={`text-sm ${theme.text.secondary}`}>
                Показано {startIndex + 1}-{endIndex} из {totalItems} записей
              </div>

              {/* Кнопки навигации */}
              <div className="flex items-center gap-1">
                <button
                  disabled={currentPage === 1}
                  onClick={() => goToPage(currentPage - 1)}
                  className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                    currentPage === 1
                      ? isDark
                        ? 'text-gray-600 bg-white/5 cursor-not-allowed'
                        : 'text-gray-400 bg-gray-100 cursor-not-allowed'
                      : isDark
                        ? 'text-gray-300 bg-white/5 hover:bg-white/10 cursor-pointer'
                        : 'text-gray-600 bg-gray-100 hover:bg-gray-200 cursor-pointer'
                  }`}
                >
                  <ChevronLeft size={16} />
                </button>

                {/* Номера страниц */}
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                  <button
                    key={page}
                    onClick={() => goToPage(page)}
                    className={`w-8 h-8 rounded-lg text-sm font-medium ${
                      currentPage === page
                        ? 'bg-accent-red text-white'
                        : isDark
                          ? 'text-gray-300 bg-white/5 hover:bg-white/10'
                          : 'text-gray-600 bg-gray-100 hover:bg-gray-200'
                    }`}
                  >
                    {page}
                  </button>
                ))}

                <button
                  disabled={currentPage === totalPages}
                  onClick={() => goToPage(currentPage + 1)}
                  className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                    currentPage === totalPages
                      ? isDark
                        ? 'text-gray-600 bg-white/5 cursor-not-allowed'
                        : 'text-gray-400 bg-gray-100 cursor-not-allowed'
                      : isDark
                        ? 'text-gray-300 bg-white/5 hover:bg-white/10 cursor-pointer'
                        : 'text-gray-600 bg-gray-100 hover:bg-gray-200 cursor-pointer'
                  }`}
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          </div>

          {/* Информационный блок */}
          <div className={`rounded-2xl p-4 border ${isDark ? 'bg-red-900/20 border-red-800/30' : 'bg-red-50 border-red-200'}`}>
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-accent-red mt-0.5 flex-shrink-0" />
              <div>
                <p className={`text-sm font-medium mb-1 ${theme.text.primary}`}>
                  Тестовая страница дизайн-системы
                </p>
                <p className={`text-sm ${theme.text.secondary}`}>
                  Эта страница создана для визуальной демонстрации компонентов UI Kit и дизайн-системы WellWon.
                  Все данные являются статическими моками и не связаны с реальными декларациями.
                </p>
              </div>
            </div>
          </div>
        </>
      );
    }

    // Заглушки для остальных разделов
    const placeholders: Record<string, { icon: typeof Truck; title: string }> = {
      logistics: { icon: Truck, title: 'Логистика' },
      finance: { icon: DollarSign, title: 'Финансы' },
      analytics: { icon: LineChart, title: 'Аналитика' },
      settings: { icon: Settings, title: 'Настройки' },
      team: { icon: Users, title: 'Команда' }
    };

    const placeholder = placeholders[section];
    if (!placeholder) return null;

    const Icon = placeholder.icon;

    return (
      <div className="flex items-center justify-center h-full">
        <div className={`text-center p-12 rounded-2xl border ${theme.card.background} ${theme.card.border}`}>
          <Icon size={64} className={`mx-auto mb-4 ${theme.text.secondary}`} />
          <h2 className={`text-2xl font-bold mb-2 ${theme.text.primary}`}>{placeholder.title}</h2>
          <p className={theme.text.secondary}>Раздел в разработке</p>
        </div>
      </div>
    );
  };

  return (
    <div className={`flex h-screen ${theme.page}`}>
      {/* Sidebar */}
      <SidebarMock
        collapsed={sidebarCollapsed}
        toggleSidebar={toggleSidebar}
        activeSection={activeSection}
        setActiveSection={setActiveSection}
      />

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <HeaderBarMock
          isDark={isDark}
          toggleTheme={toggleTheme}
          activeSection={activeSection}
        />

        {/* Content */}
        <div className="flex-1 overflow-auto p-6 space-y-8">
          {renderContent(activeSection)}
        </div>
      </div>
    </div>
  );
};

export default DeclarantContent;
