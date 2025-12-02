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
  ChevronDown,
  ArrowLeft,
  FileJson,
  Sun,
  Moon,
  ScanText,
  Search,
  SlidersHorizontal,
  X
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  useDeclarantUIStore,
  useDeclarantIsDark,
  useDeclarantSidebarCollapsed,
  useDeclarantRowsPerPage,
} from '@/stores/useDeclarantUIStore';

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
  setActiveSection,
  isDark,
  toggleTheme
}: {
  collapsed: boolean;
  toggleSidebar: () => void;
  activeSection: string;
  setActiveSection: (id: string) => void;
  isDark: boolean;
  toggleTheme: () => void;
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

      {/* Theme Toggle - над профилем */}
      <div className="px-3 pb-3">
        {collapsed ? (
          <div className="flex justify-center">
            <button
              onClick={toggleTheme}
              className="group w-12 h-12 flex items-center justify-center rounded-xl border border-white/10 hover:bg-medium-gray/80 hover:border-accent-red/50"
              title={isDark ? "Светлая тема" : "Темная тема"}
            >
              {isDark ? (
                <Sun size={20} className="text-gray-400 group-hover:text-accent-red" />
              ) : (
                <Moon size={20} className="text-gray-400 group-hover:text-accent-red" />
              )}
            </button>
          </div>
        ) : (
          <button
            onClick={toggleTheme}
            className="w-full flex items-center px-3 py-2.5 rounded-xl text-gray-300 hover:text-white hover:bg-white/10"
          >
            {isDark ? <Sun size={20} className="mr-3" /> : <Moon size={20} className="mr-3" />}
            <span className="font-medium text-sm">{isDark ? 'Светлая тема' : 'Темная тема'}</span>
          </button>
        )}
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
  activeSection
}: {
  isDark: boolean;
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
      </div>
    </div>
  );
};

// =============================================================================
// Main DeclarantContent Component
// =============================================================================

const DeclarantContent: React.FC = () => {
  // UI state from Zustand store (persisted automatically)
  const isDark = useDeclarantIsDark();
  const sidebarCollapsed = useDeclarantSidebarCollapsed();
  const rowsPerPage = Number(useDeclarantRowsPerPage());
  const toggleTheme = useDeclarantUIStore((s) => s.toggleTheme);
  const toggleSidebar = useDeclarantUIStore((s) => s.toggleSidebar);
  const setRowsPerPage = useDeclarantUIStore((s) => s.setRowsPerPage);

  // Local state (ephemeral - not persisted)
  const [activeSection, setActiveSection] = useState('dashboard');
  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState('all');
  const [dateFilter, setDateFilter] = useState('all');

  // Новые фильтры
  const [mainDocumentFilter, setMainDocumentFilter] = useState('all');
  const [procedureCodeFilter, setProcedureCodeFilter] = useState('all');
  const [featureFilter, setFeatureFilter] = useState('all');
  const [recipientFilter, setRecipientFilter] = useState('all');
  const [senderFilter, setSenderFilter] = useState('all');
  const [registrationDateFilter, setRegistrationDateFilter] = useState('all');
  const [documentTypeFilter, setDocumentTypeFilter] = useState('all');
  const [documentFilter, setDocumentFilter] = useState('all');
  const [documentDateFilter, setDocumentDateFilter] = useState('all');

  // Пагинация
  const totalItems = mockBatches.length;
  const totalPages = Math.ceil(totalItems / rowsPerPage);
  const startIndex = (currentPage - 1) * rowsPerPage;
  const endIndex = Math.min(startIndex + rowsPerPage, totalItems);
  const paginatedBatches = mockBatches.slice(startIndex, endIndex);

  const handleRowsPerPageChange = (value: string) => {
    setRowsPerPage(value); // Store handles persistence
    setCurrentPage(1);
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

          {/* Секция фильтров */}
          <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
            <div>
              <div className="flex items-center gap-3">
                {/* Поиск */}
                <div className="relative flex-1">
                  <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme.text.secondary}`} />
                  <Input
                    placeholder="Поиск декларации..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className={`pl-10 h-10 rounded-xl transition-none ${
                      isDark
                        ? 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500'
                        : 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400'
                    }`}
                  />
                </div>

                {/* Кнопка фильтров */}
                <button
                  onClick={() => setFiltersOpen(!filtersOpen)}
                  className={`flex items-center gap-2 px-4 h-10 rounded-xl border ${
                    isDark
                      ? 'bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white border-white/10'
                      : 'bg-gray-100 hover:bg-gray-200 text-gray-600 hover:text-gray-900 border-gray-300'
                  }`}
                >
                  <SlidersHorizontal size={16} />
                  <span className="font-medium">Фильтры</span>
                  <ChevronDown size={16} className={`transition-transform ${filtersOpen ? 'rotate-180' : ''}`} />
                </button>

                {/* Кнопка сброса фильтров - показывается только при активных фильтрах */}
                {(searchQuery !== '' ||
                  mainDocumentFilter !== 'all' ||
                  procedureCodeFilter !== 'all' ||
                  featureFilter !== 'all' ||
                  recipientFilter !== 'all' ||
                  senderFilter !== 'all' ||
                  registrationDateFilter !== 'all' ||
                  documentTypeFilter !== 'all' ||
                  documentFilter !== 'all' ||
                  documentDateFilter !== 'all') && (
                  <button
                    onClick={() => {
                      setMainDocumentFilter('all');
                      setProcedureCodeFilter('all');
                      setFeatureFilter('all');
                      setRecipientFilter('all');
                      setSenderFilter('all');
                      setRegistrationDateFilter('all');
                      setDocumentTypeFilter('all');
                      setDocumentFilter('all');
                      setDocumentDateFilter('all');
                      setSearchQuery('');
                    }}
                    className="flex items-center justify-center w-10 h-10 rounded-lg bg-accent-red/10 text-accent-red border border-accent-red/20 hover:bg-accent-red/20 hover:border-accent-red/30"
                    title="Сбросить фильтры"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>

              {/* Раскрывающиеся фильтры */}
              <Collapsible open={filtersOpen} onOpenChange={setFiltersOpen}>
                <CollapsibleContent className="pt-4">
                  <div className="space-y-4">
                    {/* Первый ряд: Основной документ, Код процедуры, Особенность */}
                    <div className="grid grid-cols-3 gap-4">
                      {/* Основной документ */}
                      <div className="space-y-1.5">
                        <label className={`text-sm ${theme.text.primary}`}>Основной документ</label>
                        <Select value={mainDocumentFilter} onValueChange={setMainDocumentFilter}>
                          <SelectTrigger className={`w-full h-10 focus:outline-none focus:ring-0 transition-none ${
                            isDark
                              ? 'bg-[#1e1e22] border-white/10 text-white'
                              : 'bg-gray-50 border-gray-300 text-gray-900'
                          }`}>
                            <SelectValue placeholder="Все" />
                          </SelectTrigger>
                          <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                            <SelectItem value="all" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Все</SelectItem>
                            <SelectItem value="dt" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>ДТ</SelectItem>
                            <SelectItem value="ets" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>ЭТС</SelectItem>
                            <SelectItem value="td" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>ТД</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Код процедуры */}
                      <div className="space-y-1.5">
                        <label className={`text-sm ${theme.text.primary}`}>Код процедуры</label>
                        <Select value={procedureCodeFilter} onValueChange={setProcedureCodeFilter}>
                          <SelectTrigger className={`w-full h-10 focus:outline-none focus:ring-0 transition-none ${
                            isDark
                              ? 'bg-[#1e1e22] border-white/10 text-white'
                              : 'bg-gray-50 border-gray-300 text-gray-900'
                          }`}>
                            <SelectValue placeholder="Все" />
                          </SelectTrigger>
                          <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                            <SelectItem value="all" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Все</SelectItem>
                            <SelectItem value="10" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>10 - Выпуск для внутреннего потребления</SelectItem>
                            <SelectItem value="40" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>40 - Экспорт</SelectItem>
                            <SelectItem value="31" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>31 - Реэкспорт</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Особенность */}
                      <div className="space-y-1.5">
                        <label className={`text-sm ${theme.text.primary}`}>Особенность</label>
                        <Select value={featureFilter} onValueChange={setFeatureFilter}>
                          <SelectTrigger className={`w-full h-10 focus:outline-none focus:ring-0 transition-none ${
                            isDark
                              ? 'bg-[#1e1e22] border-white/10 text-white'
                              : 'bg-gray-50 border-gray-300 text-gray-900'
                          }`}>
                            <SelectValue placeholder="Все" />
                          </SelectTrigger>
                          <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                            <SelectItem value="all" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Все</SelectItem>
                            <SelectItem value="standard" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Стандартная</SelectItem>
                            <SelectItem value="urgent" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Срочная</SelectItem>
                            <SelectItem value="special" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Особая</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    {/* Второй ряд: Получатель, Отправитель, Дата регистрации */}
                    <div className="grid grid-cols-3 gap-4">
                      {/* Получатель */}
                      <div className="space-y-1.5">
                        <label className={`text-sm ${theme.text.primary}`}>Получатель</label>
                        <Select value={recipientFilter} onValueChange={setRecipientFilter}>
                          <SelectTrigger className={`w-full h-10 focus:outline-none focus:ring-0 transition-none ${
                            isDark
                              ? 'bg-[#1e1e22] border-white/10 text-white'
                              : 'bg-gray-50 border-gray-300 text-gray-900'
                          }`}>
                            <SelectValue placeholder="Все" />
                          </SelectTrigger>
                          <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                            <SelectItem value="all" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Все</SelectItem>
                            <SelectItem value="company1" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>ООО "Компания 1"</SelectItem>
                            <SelectItem value="company2" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>ООО "Компания 2"</SelectItem>
                            <SelectItem value="company3" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>АО "Компания 3"</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Отправитель */}
                      <div className="space-y-1.5">
                        <label className={`text-sm ${theme.text.primary}`}>Отправитель</label>
                        <Select value={senderFilter} onValueChange={setSenderFilter}>
                          <SelectTrigger className={`w-full h-10 focus:outline-none focus:ring-0 transition-none ${
                            isDark
                              ? 'bg-[#1e1e22] border-white/10 text-white'
                              : 'bg-gray-50 border-gray-300 text-gray-900'
                          }`}>
                            <SelectValue placeholder="Все" />
                          </SelectTrigger>
                          <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                            <SelectItem value="all" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Все</SelectItem>
                            <SelectItem value="sender1" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>China Export Ltd.</SelectItem>
                            <SelectItem value="sender2" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Germany Trade GmbH</SelectItem>
                            <SelectItem value="sender3" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>USA Supplies Inc.</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Дата регистрации */}
                      <div className="space-y-1.5">
                        <label className={`text-sm ${theme.text.primary}`}>Дата регистрации</label>
                        <Select value={registrationDateFilter} onValueChange={setRegistrationDateFilter}>
                          <SelectTrigger className={`w-full h-10 focus:outline-none focus:ring-0 transition-none ${
                            isDark
                              ? 'bg-[#1e1e22] border-white/10 text-white'
                              : 'bg-gray-50 border-gray-300 text-gray-900'
                          }`}>
                            <SelectValue placeholder="За все время" />
                          </SelectTrigger>
                          <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                            <SelectItem value="all" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>За все время</SelectItem>
                            <SelectItem value="today" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Сегодня</SelectItem>
                            <SelectItem value="week" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>За неделю</SelectItem>
                            <SelectItem value="month" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>За месяц</SelectItem>
                            <SelectItem value="quarter" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>За квартал</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    {/* Третий ряд: Вид документа, Документ, Дата документа */}
                    <div className="grid grid-cols-3 gap-4">
                      {/* Вид документа */}
                      <div className="space-y-1.5">
                        <label className={`text-sm ${theme.text.primary}`}>Вид документа</label>
                        <Select value={documentTypeFilter} onValueChange={setDocumentTypeFilter}>
                          <SelectTrigger className={`w-full h-10 focus:outline-none focus:ring-0 transition-none ${
                            isDark
                              ? 'bg-[#1e1e22] border-white/10 text-white'
                              : 'bg-gray-50 border-gray-300 text-gray-900'
                          }`}>
                            <SelectValue placeholder="Все" />
                          </SelectTrigger>
                          <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                            <SelectItem value="all" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Все</SelectItem>
                            <SelectItem value="contract" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Контракт</SelectItem>
                            <SelectItem value="invoice" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Инвойс</SelectItem>
                            <SelectItem value="certificate" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Сертификат</SelectItem>
                            <SelectItem value="license" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Лицензия</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Документ */}
                      <div className="space-y-1.5">
                        <label className={`text-sm ${theme.text.primary}`}>Документ</label>
                        <Select value={documentFilter} onValueChange={setDocumentFilter}>
                          <SelectTrigger className={`w-full h-10 focus:outline-none focus:ring-0 transition-none ${
                            isDark
                              ? 'bg-[#1e1e22] border-white/10 text-white'
                              : 'bg-gray-50 border-gray-300 text-gray-900'
                          }`}>
                            <SelectValue placeholder="Все" />
                          </SelectTrigger>
                          <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                            <SelectItem value="all" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Все</SelectItem>
                            <SelectItem value="doc1" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Документ №1234</SelectItem>
                            <SelectItem value="doc2" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Документ №5678</SelectItem>
                            <SelectItem value="doc3" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Документ №9012</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Дата документа */}
                      <div className="space-y-1.5">
                        <label className={`text-sm ${theme.text.primary}`}>Дата документа</label>
                        <Select value={documentDateFilter} onValueChange={setDocumentDateFilter}>
                          <SelectTrigger className={`w-full h-10 focus:outline-none focus:ring-0 transition-none ${
                            isDark
                              ? 'bg-[#1e1e22] border-white/10 text-white'
                              : 'bg-gray-50 border-gray-300 text-gray-900'
                          }`}>
                            <SelectValue placeholder="За все время" />
                          </SelectTrigger>
                          <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                            <SelectItem value="all" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>За все время</SelectItem>
                            <SelectItem value="today" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>Сегодня</SelectItem>
                            <SelectItem value="week" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>За неделю</SelectItem>
                            <SelectItem value="month" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>За месяц</SelectItem>
                            <SelectItem value="quarter" className={isDark ? 'focus:bg-white/10 focus:text-white text-white' : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900'}>За квартал</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                </CollapsibleContent>
              </Collapsible>
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
                  <SelectTrigger className={`w-[70px] h-8 focus:outline-none focus:ring-0 transition-none ${
                    isDark
                      ? 'bg-[#1e1e22] border-white/10 text-white'
                      : 'bg-gray-50 border-gray-200 text-gray-900'
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
        isDark={isDark}
        toggleTheme={toggleTheme}
      />

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <HeaderBarMock
          isDark={isDark}
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
