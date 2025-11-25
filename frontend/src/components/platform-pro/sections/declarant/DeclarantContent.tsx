// =============================================================================
// Declarant Content - Standalone Application for Platform Pro
// =============================================================================
// Полная копия верстки "Декларация AI" с мок-данными
// Включает собственный sidebar, header и переключатель темы

import React, { useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  FileText,
  CheckCircle,
  Clock,
  AlertCircle,
  Plus,
  Trash2,
  Download,
  Eye,
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
  Moon
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
    { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
    { id: 'logistics', label: 'Логистика', icon: Truck },
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
          className={`h-8 w-8 p-0 rounded-lg flex items-center justify-center ${theme.button.default}`}
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
    dashboard: 'Dashboard',
    logistics: 'Логистика',
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
        <button className={`mr-4 h-8 px-3 flex items-center gap-2 rounded-lg ${theme.button.default}`}>
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
  const [isDark, setIsDark] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeSection, setActiveSection] = useState('dashboard');

  const toggleTheme = () => {
    setIsDark(!isDark);
  };

  const toggleSidebar = () => {
    setSidebarCollapsed(!sidebarCollapsed);
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
      row: 'divide-white/10 hover:bg-[#232328]/30',
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
            <div className="space-y-4">
              <div className={`flex items-center justify-between pb-4 border-b ${theme.table.border}`}>
                <h3 className={`text-lg font-semibold ${theme.text.primary}`}>
                  Пакеты деклараций
                </h3>
                <div className="flex items-center gap-2">
                  <span className={`text-sm ${theme.text.secondary}`}>
                    Всего: {mockBatches.length}
                  </span>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className={`border-b ${theme.table.border}`}>
                      <th className="text-left py-3 px-2 w-12">
                        <Checkbox className={`${isDark ? 'border-white/20' : 'border-gray-300'} data-[state=checked]:bg-accent-red data-[state=checked]:border-accent-red`} />
                      </th>
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
                    </tr>
                  </thead>
                  <tbody className={`divide-y ${theme.table.row.split(' ')[0]}`}>
                    {mockBatches.map((batch) => {
                      const Icon = batch.icon;
                      return (
                        <tr
                          key={batch.id}
                          className={`cursor-pointer ${theme.table.row.split(' ').slice(1).join(' ')}`}
                        >
                          <td className="py-4 px-2">
                            <Checkbox className={`${isDark ? 'border-white/20' : 'border-gray-300'} data-[state=checked]:bg-accent-red data-[state=checked]:border-accent-red`} />
                          </td>
                          <td className="py-4 px-4">
                            <span className={`font-mono font-medium ${theme.text.primary}`}>
                              {batch.number}
                            </span>
                          </td>
                          <td className="py-4 px-4">
                            <div className="flex items-center gap-2">
                              <Icon className={`w-4 h-4 ${batch.iconColor}`} />
                              <span className={`text-sm ${batch.iconColor}`}>
                                {batch.statusText}
                              </span>
                            </div>
                          </td>
                          <td className="py-4 px-4">
                            <span className={`font-mono text-sm ${theme.text.primary}`}>
                              {batch.docs}
                            </span>
                          </td>
                          <td className="py-4 px-4">
                            <span className={`font-mono text-sm ${theme.text.primary}`}>
                              {batch.extracts}
                            </span>
                          </td>
                          <td className="py-4 px-4">
                            <span className={`text-sm ${theme.text.secondary}`}>
                              {batch.date}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className={`flex items-center justify-between pt-4 border-t ${theme.table.border}`}>
                <div className={`text-sm ${theme.text.secondary}`}>
                  Показано {mockBatches.length} из {mockBatches.length} записей
                </div>
                <div className="flex items-center gap-2">
                  <button className={`px-3 py-1 ${isDark ? 'text-gray-500 bg-white/5' : 'text-gray-400 bg-gray-100'} rounded-lg text-sm cursor-not-allowed`} disabled>
                    Предыдущая
                  </button>
                  <div className={`px-3 py-1 rounded-lg bg-accent-red text-white text-sm font-medium ${isDark ? '' : 'shadow-sm'}`}>
                    1
                  </div>
                  <button className={`px-3 py-1 ${isDark ? 'text-gray-500 bg-white/5' : 'text-gray-400 bg-gray-100'} rounded-lg text-sm cursor-not-allowed`} disabled>
                    Следующая
                  </button>
                </div>
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
