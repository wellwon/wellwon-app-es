import React, { useState, memo } from 'react';
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

/**
 * TestAppPage - изолированная тестовая страница
 * Полная копия верстки "Декларация AI" с мок-данными
 * Без функционала, только визуал для тестирования дизайн-системы
 */

// Константы для навигации
const NAVIGATION_SECTIONS = [
  { id: 'dashboard', label: 'Dashboard', icon: BarChart3, active: true },
  { id: 'logistics', label: 'Логистика', icon: Truck, active: false },
  { id: 'finance', label: 'Финансы', icon: DollarSign, active: false },
  { id: 'analytics', label: 'Аналитика', icon: LineChart, active: false },
  { id: 'settings', label: 'Настройки', icon: Settings, active: false },
  { id: 'team', label: 'Команда', icon: Users, active: false },
] as const;

// Мок-данные для статистики
const mockStats = {
  total_batches: 6,
  completed_batches: 5,
  processing_batches: 0,
  total_documents: 55,
};

// Мок-данные для таблицы деклараций
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

/**
 * SidebarMock - статичная копия PlatformSidebar
 * Always uses dark theme regardless of main content theme
 */
const SidebarMock = memo(({
  collapsed,
  toggleSidebar
}: {
  collapsed: boolean;
  toggleSidebar: () => void
}) => {
  // Always dark theme
  const theme = {
    sidebar: 'bg-[#232328] border-gray-700',
    header: 'border-gray-700',
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

  return (
    <div className={`
      ${collapsed ? 'w-[60px]' : 'w-60'} 
      border-r flex flex-col h-screen transition-all duration-300
      ${theme.sidebar}
    `}>
      {/* Header with logo */}
      <div className={`h-16 flex items-center ${collapsed ? 'justify-center' : 'justify-between px-4'} border-b ${theme.header}`}>
        {/* Logo - shown only when expanded */}
        {!collapsed && (
          <div className="relative">
            <span className="text-accent-red font-black text-xl">Well</span>
            <span className="text-white font-black text-xl">Won</span>
            <span className="text-white text-xl font-extrabold"> Pro</span>
            <div className="absolute -bottom-0.5 left-0 w-10 h-0.5 bg-accent-red"></div>
          </div>
        )}
        
        {/* Toggle button */}
        <button 
          onClick={toggleSidebar}
          className={`h-8 w-8 p-0 rounded-lg transition-colors flex items-center justify-center ${theme.button.default}`}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto py-4 px-3">
        <div className="space-y-3">
          {/* Group header - only when expanded */}
          {!collapsed && (
            <div className={`text-xs font-semibold uppercase tracking-wider px-3 ${theme.text.secondary}`}>
              Основное
            </div>
          )}
          <div className={collapsed ? 'space-y-2' : 'space-y-1'}>
            {NAVIGATION_SECTIONS.slice(0, 2).map((section) => {
              const Icon = section.icon;
              
              if (collapsed) {
                // Compact version - icon only
                return (
                  <div 
                    key={section.id} 
                    className="relative flex justify-center cursor-pointer" 
                    title={section.label}
                  >
                    <div className={`
                      w-12 h-12 flex items-center justify-center rounded-xl transition-all duration-200
                      ${section.active 
                        ? 'bg-accent-red/20 border border-accent-red/30' 
                        : 'hover:bg-white/10'
                      }
                    `}>
                      <Icon size={20} className={section.active ? 'text-accent-red' : 'text-gray-400'} />
                    </div>
                  </div>
                );
              }
              
              // Full version - icon + text
              return (
                <div
                  key={section.id}
                  className={`
                    flex items-center px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200
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
          {/* Group header - only when expanded */}
          {!collapsed && (
            <div className={`text-xs font-semibold uppercase tracking-wider px-3 ${theme.text.secondary}`}>
              Управление
            </div>
          )}
          <div className={collapsed ? 'space-y-2' : 'space-y-1'}>
            {NAVIGATION_SECTIONS.slice(2).map((section) => {
              const Icon = section.icon;
              
              if (collapsed) {
                // Compact version - icon only
                return (
                  <div 
                    key={section.id} 
                    className="relative flex justify-center cursor-pointer" 
                    title={section.label}
                  >
                    <div className={`
                      w-12 h-12 flex items-center justify-center rounded-xl transition-all duration-200
                      ${section.active 
                        ? 'bg-accent-red/20 border border-accent-red/30' 
                        : 'hover:bg-white/10'
                      }
                    `}>
                      <Icon size={20} className={section.active ? 'text-accent-red' : 'text-gray-400'} />
                    </div>
                  </div>
                );
              }
              
              // Full version - icon + text
              return (
                <div
                  key={section.id}
                  className={`
                    flex items-center px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200
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
          
          {/* Text - only when expanded */}
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
});

SidebarMock.displayName = 'SidebarMock';

/**
 * HeaderBarMock - статичная копия HeaderBar
 */
const HeaderBarMock = memo(({ isDark, toggleTheme }: { isDark: boolean; toggleTheme: () => void }) => {
  const theme = isDark ? {
    header: 'bg-[#232328] border-gray-700',
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400'
    },
    button: {
      default: 'text-gray-300 hover:text-white hover:bg-white/10',
      active: 'bg-gray-100 text-gray-900 hover:bg-gray-200'
    }
  } : {
    header: 'bg-white border-gray-200 shadow-sm',
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
          <span className={`font-semibold ${theme.text.primary}`}>Декларация AI</span>
          <span className={`ml-2 ${theme.text.secondary}`}>• Управление декларациями</span>
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
        
        {/* Переключатель темы */}
        <div className="ml-2 w-px h-6 bg-gray-700/20" />
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
});

HeaderBarMock.displayName = 'HeaderBarMock';

export default function DeclarantPage() {
  const [isDark, setIsDark] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

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
    card: 'bg-[#232328] border-gray-700',
    button: {
      default: 'text-gray-300 hover:text-white hover:bg-white/10',
      danger: 'text-gray-300 hover:text-white hover:bg-white/10'
    },
    table: {
      header: 'border-gray-700',
      row: {
        divide: 'divide-gray-700',
        hover: 'hover:bg-[#232328]/30',
        full: 'divide-gray-700 hover:bg-[#232328]/30'
      },
      border: 'border-gray-700'
    }
  } : {
    page: 'bg-[#f4f4f4]',
    text: {
      primary: 'text-gray-900',
      secondary: 'text-[#6b7280]'
    },
    card: 'bg-white border-gray-200 shadow-sm',
    button: {
      default: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100',
      danger: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
    },
    table: {
      header: 'border-gray-200',
      row: {
        divide: 'divide-gray-200',
        hover: 'hover:bg-gray-50',
        full: 'divide-gray-200 hover:bg-gray-50'
      },
      border: 'border-gray-200'
    }
  };

  return (
    <div className={`flex h-screen ${theme.page}`}>
      {/* Sidebar слева */}
      <SidebarMock collapsed={sidebarCollapsed} toggleSidebar={toggleSidebar} />
      
      {/* Контент справа */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header сверху */}
        <HeaderBarMock isDark={isDark} toggleTheme={toggleTheme} />
        
        {/* Основной контент с таблицей */}
        <div className="flex-1 overflow-auto p-6 space-y-8">
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
          
          {/* Кнопки действий */}
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
          {/* Всего пакетов */}
          <div className={`rounded-2xl p-4 border ${theme.card}`}>
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

          {/* Завершено */}
          <div className={`rounded-2xl p-4 border ${theme.card}`}>
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

          {/* В обработке */}
          <div className={`rounded-2xl p-4 border ${theme.card}`}>
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

          {/* Всего документов */}
          <div className={`rounded-2xl p-4 border ${theme.card}`}>
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
        <div className={`rounded-2xl p-6 border ${theme.card}`}>
          <div className="space-y-4">
            {/* Заголовок таблицы */}
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

            {/* Таблица */}
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
                <tbody className={`divide-y ${theme.table.row.divide}`}>
                  {mockBatches.map((batch) => {
                    const Icon = batch.icon;
                    return (
                      <tr
                        key={batch.id}
                        className={`cursor-pointer ${theme.table.row.hover}`}
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

            {/* Футер таблицы */}
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

        {/* Информационный блок внизу */}
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
        </div>
      </div>
    </div>
  );
}
