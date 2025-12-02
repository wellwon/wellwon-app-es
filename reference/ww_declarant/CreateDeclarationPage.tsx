/**
 * CreateDeclarationPage - Страница создания декларации
 * Выделена из TestAppPage для улучшения архитектуры
 */

import React from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  FileText,
  Plus,
  Trash2,
  Upload,
  Archive,
  MoreHorizontal,
  MoreVertical,
  Pencil,
  Link,
  Copy,
  HelpCircle,
  ArrowLeftRight,
  ArrowUpDown,
  ArrowDownToLine,
  ArrowUpFromLine,
  Route,
  ChevronDown,
} from 'lucide-react';
import type { CreateDeclarationPageProps } from './types';
import {
  customsProceduresIM,
  customsProceduresEK,
  featuresData,
  transitTypesData,
  transitFeaturesData,
  customsOfficesData,
  organizationsData,
  declarantsData,
  mainDocumentsIMEK,
  mainDocumentsTT,
  addMenuItemsIMEK,
  addMenuItemsTT,
  goodsDocuments,
  registrationDocuments,
} from './mock-data';

export const CreateDeclarationPage: React.FC<CreateDeclarationPageProps> = ({
  state,
  onDirectionChange,
  onCustomsProcedureChange,
  onFeatureChange,
  onCustomsOfficeChange,
  onOrganizationChange,
  onDeclarantChange,
  onTransitTypeChange,
  onTransitFeatureChange,
  onSelectedGoodsDocsChange,
  onSelectedRegDocsChange,
  isDark,
  theme,
  selectStyles,
  selectContentStyles,
  onCancel,
  onSave,
}) => {
  const {
    direction: createDirection,
    customsProcedure: createCustomsProcedure,
    feature: createFeature,
    customsOffice: createCustomsOffice,
    organization: createOrganization,
    declarant: createDeclarant,
    transitType: createTransitType,
    transitFeature: createTransitFeature,
    selectedGoodsDocs,
    selectedRegDocs,
  } = state;

  // Получить процедуры в зависимости от типа декларации
  const getCustomsProcedures = () => {
    if (createDirection === 'IM') return customsProceduresIM;
    if (createDirection === 'EK') return customsProceduresEK;
    return [];
  };

  // Получить документы в зависимости от типа декларации
  const getMainDocuments = () => {
    if (createDirection === 'TT') return mainDocumentsTT;
    if (createDirection === 'IM' || createDirection === 'EK') return mainDocumentsIMEK;
    return [];
  };

  // Получить пункты меню "Добавить" для основных документов
  const getAddMenuItems = () => {
    if (createDirection === 'TT') return addMenuItemsTT;
    if (createDirection === 'IM' || createDirection === 'EK') return addMenuItemsIMEK;
    return [];
  };

  // Функция для стилей чекбокса по типу декларации
  const getCheckboxClasses = (isChecked: boolean) => {
    if (!isChecked) {
      return 'rounded border-gray-400 data-[state=checked]:bg-transparent';
    }
    if (createDirection === 'IM') {
      return 'rounded border-accent-green bg-accent-green data-[state=checked]:bg-accent-green data-[state=checked]:border-accent-green';
    }
    if (createDirection === 'EK') {
      return 'rounded border-blue-600 bg-blue-600 data-[state=checked]:bg-blue-600 data-[state=checked]:border-blue-600';
    }
    if (createDirection === 'TT') {
      return 'rounded border-orange-500 bg-orange-500 data-[state=checked]:bg-orange-500 data-[state=checked]:border-orange-500';
    }
    return 'rounded border-gray-400';
  };

  // Динамический акцентный цвет в зависимости от типа декларации
  const getAccentColorClass = (type: 'text' | 'bg' | 'hover-bg' = 'text') => {
    const colors = {
      IM: { text: 'text-accent-green', bg: 'bg-accent-green', hoverBg: 'hover:bg-accent-green/90' },
      EK: { text: 'text-blue-500', bg: 'bg-blue-600', hoverBg: 'hover:bg-blue-600/90' },
      TT: { text: 'text-orange-500', bg: 'bg-orange-500', hoverBg: 'hover:bg-orange-500/90' },
    };
    const colorSet = colors[createDirection as keyof typeof colors] || colors.IM;
    if (type === 'text') return colorSet.text;
    if (type === 'bg') return colorSet.bg;
    return colorSet.hoverBg;
  };

  return (
    <div className="space-y-6">
      {/* Header создания декларации */}
      <div className={`-mx-6 -mt-6 px-6 py-4 ${theme.card.background} border-b ${theme.card.border}`}>
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className={`text-xl font-semibold ${theme.text.primary}`}>Промторг</h1>
              <button className={`p-1 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`}>
                <Pencil size={14} className={theme.text.secondary} />
              </button>
            </div>
            <div className={`text-sm ${theme.text.secondary} mt-1`}>
              Документ ещё не состоит ни в одной подборке{' '}
              <button className={`${getAccentColorClass('text')} hover:underline`}>Изменить</button>
            </div>
            <div className={`text-sm ${theme.text.secondary}`}>
              Создана 26 ноября 17:27{' '}
              <button className={`${getAccentColorClass('text')} hover:underline`}>Реквизиты декларации</button>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button className={`
              px-4 py-2 rounded-lg flex items-center gap-2 text-sm
              ${isDark ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}
            `}>
              <Archive size={16} />
              Разместить все документы в архиве
            </button>
            
            <button className={`
              px-4 py-2 rounded-lg flex items-center gap-2 text-sm
              ${isDark ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}
            `}>
              <Upload size={16} />
              Загрузить документы
            </button>
            
            <button className={`
              px-4 py-2 rounded-lg flex items-center gap-2 text-sm
              ${isDark ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}
            `}>
              <MoreHorizontal size={16} />
              Другие действия
            </button>
            
            {/* Индикатор типа декларации */}
            {createDirection && (
              <div className={`
                flex items-center justify-center
                px-4 py-2 rounded-xl min-h-[72px] min-w-[60px]
                ${createDirection === 'IM' ? 'bg-accent-green' : createDirection === 'EK' ? 'bg-blue-600' : 'bg-orange-500'}
                text-white font-bold
              `}>
                <span className="text-2xl font-bold whitespace-nowrap">
                  {createDirection === 'TT' 
                    ? (createTransitType || 'ТТ —')
                    : `${createDirection === 'IM' ? 'ИМ' : 'ЭК'} ${createCustomsProcedure || '—'}`
                  }
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Блок "Создание декларации" + Журнал сообщений в одной строке */}
      <div className="flex gap-6">
        {/* Левая часть - Создание декларации */}
        <div className={`flex-1 rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
          <h2 className={`text-lg font-semibold mb-6 ${theme.text.primary}`}>Создание декларации</h2>
        
        <div className="space-y-4">
          {/* Тип декларации - кнопки (только отображение, нельзя переключить) */}
          <div className="grid grid-cols-[240px_1fr] items-center gap-4">
            <label className={`text-sm ${theme.text.secondary}`}>Тип декларации [1]</label>
            <div className="flex gap-2">
              {/* ТТ - Транзит (оранжевый) */}
              <div
                className={`
                  px-4 py-2 rounded-lg text-sm font-medium border flex items-center gap-2 cursor-default
                  ${createDirection === 'TT'
                    ? 'bg-orange-500/20 text-orange-500 border-orange-500/30'
                    : isDark 
                      ? 'bg-white/5 text-gray-500 border-white/10 opacity-50'
                      : 'bg-gray-100 text-gray-400 border-gray-200 opacity-50'
                  }
                `}
              >
                <Route className="w-4 h-4" />
                ТТ - Транзит
              </div>
              
              {/* ЭК - Вывоз (синий) */}
              <div
                className={`
                  px-4 py-2 rounded-lg text-sm font-medium border flex items-center gap-2 cursor-default
                  ${createDirection === 'EK'
                    ? 'bg-blue-600/20 text-blue-500 border-blue-600/30'
                    : isDark 
                      ? 'bg-white/5 text-gray-500 border-white/10 opacity-50'
                      : 'bg-gray-100 text-gray-400 border-gray-200 opacity-50'
                  }
                `}
              >
                <ArrowUpFromLine className="w-4 h-4" />
                ЭК - Вывоз
              </div>
              
              {/* ИМ - Ввоз (зелёный) */}
              <div
                className={`
                  px-4 py-2 rounded-lg text-sm font-medium border flex items-center gap-2 cursor-default
                  ${createDirection === 'IM'
                    ? 'bg-accent-green/20 text-accent-green border-accent-green/30'
                    : isDark 
                      ? 'bg-white/5 text-gray-500 border-white/10 opacity-50'
                      : 'bg-gray-100 text-gray-400 border-gray-200 opacity-50'
                  }
                `}
              >
                <ArrowDownToLine className="w-4 h-4" />
                ИМ - Ввоз
              </div>
            </div>
          </div>

          {/* Поля для ИМ/ЭК: Таможенная процедура и Особенности */}
          {(createDirection === 'IM' || createDirection === 'EK') && (
            <>
              {/* Таможенная процедура */}
              <div className="grid grid-cols-[240px_1fr] items-center gap-4">
                <label className={`text-sm ${theme.text.secondary}`}>Таможенная процедура [1]</label>
                <Select value={createCustomsProcedure} onValueChange={(v) => {
                  onCustomsProcedureChange(v);
                  onFeatureChange('');
                }}>
                  <SelectTrigger className={selectStyles}>
                    <SelectValue placeholder="Заполните значение" />
                  </SelectTrigger>
                  <SelectContent className={selectContentStyles}>
                    {getCustomsProcedures().map(p => (
                      <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Особенности - всегда видимо для ИМ/ЭК */}
              <div className="grid grid-cols-[240px_1fr] items-center gap-4">
                <label className={`text-sm flex items-center gap-1 ${theme.text.secondary}`}>
                  Особенности [7]
                  <HelpCircle size={14} className={getAccentColorClass('text')} />
                </label>
                <Select value={createFeature} onValueChange={onFeatureChange}>
                  <SelectTrigger className={selectStyles}>
                    <SelectValue placeholder="Заполните значение" />
                  </SelectTrigger>
                  <SelectContent className={selectContentStyles}>
                    {featuresData.map(f => (
                      <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </>
          )}

          {/* Поля для ТТ: Вид перемещения и Особенности перемещения */}
          {createDirection === 'TT' && (
            <>
              {/* Вид перемещения */}
              <div className="grid grid-cols-[240px_1fr] items-center gap-4">
                <label className={`text-sm ${theme.text.secondary}`}>Вид перемещения [1]</label>
                <Select value={createTransitType} onValueChange={onTransitTypeChange}>
                  <SelectTrigger className={selectStyles}>
                    <SelectValue placeholder="Заполните значение" />
                  </SelectTrigger>
                  <SelectContent className={selectContentStyles}>
                    {transitTypesData.map(t => (
                      <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Особенности перемещения */}
              <div className="grid grid-cols-[240px_1fr] items-center gap-4">
                <label className={`text-sm flex items-center gap-1 ${theme.text.secondary}`}>
                  Особенности перемещения [1]
                  <HelpCircle size={14} className={getAccentColorClass('text')} />
                </label>
                <Select value={createTransitFeature} onValueChange={onTransitFeatureChange}>
                  <SelectTrigger className={selectStyles}>
                    <SelectValue placeholder="Заполните значение" />
                  </SelectTrigger>
                  <SelectContent className={selectContentStyles}>
                    {transitFeaturesData.map(f => (
                      <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </>
          )}

          {/* Таможенный орган */}
          <div className="grid grid-cols-[240px_1fr] items-center gap-4">
            <label className={`text-sm ${theme.text.secondary}`}>Таможенный орган</label>
            <Select value={createCustomsOffice} onValueChange={onCustomsOfficeChange}>
              <SelectTrigger className={selectStyles}>
                <SelectValue placeholder="Выберите таможенный орган" />
              </SelectTrigger>
              <SelectContent className={selectContentStyles}>
                {customsOfficesData.map(o => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Организация */}
          <div className="grid grid-cols-[240px_1fr] items-center gap-4">
            <label className={`text-sm ${theme.text.secondary}`}>Организация</label>
            <div className="flex gap-2">
              <Select value={createOrganization} onValueChange={onOrganizationChange}>
                <SelectTrigger className={`${selectStyles} flex-1`}>
                  <SelectValue placeholder="Выберите организацию" />
                </SelectTrigger>
                <SelectContent className={selectContentStyles}>
                  {organizationsData.map(o => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <button className={`p-2 rounded-lg hover:opacity-80 h-10 w-10 flex items-center justify-center border ${createDirection === 'IM' ? 'bg-accent-green/20 text-accent-green border-accent-green/30' : createDirection === 'EK' ? 'bg-blue-600/20 text-blue-500 border-blue-600/30' : 'bg-orange-500/20 text-orange-500 border-orange-500/30'}`}>
                <Plus size={18} />
              </button>
            </div>
          </div>

          {/* Заполнил декларацию */}
          <div className="grid grid-cols-[240px_1fr] items-center gap-4">
            <label className={`text-sm ${theme.text.secondary}`}>Заполнил декларацию</label>
            <div className="flex gap-2">
              <Select value={createDeclarant} onValueChange={onDeclarantChange}>
                <SelectTrigger className={`${selectStyles} flex-1`}>
                  <SelectValue placeholder="Выберите заполняющее лицо" />
                </SelectTrigger>
                <SelectContent className={selectContentStyles}>
                  {declarantsData.map(d => (
                    <SelectItem key={d.value} value={d.value}>{d.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <button className={`p-2 rounded-lg hover:opacity-80 h-10 w-10 flex items-center justify-center border ${createDirection === 'IM' ? 'bg-accent-green/20 text-accent-green border-accent-green/30' : createDirection === 'EK' ? 'bg-blue-600/20 text-blue-500 border-blue-600/30' : 'bg-orange-500/20 text-orange-500 border-orange-500/30'}`}>
                <Plus size={18} />
              </button>
            </div>
          </div>
        </div>

        </div>

        {/* Правая часть - Журнал сообщений */}
        <div className={`flex-1 rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className={`text-lg font-semibold ${theme.text.primary}`}>Журнал сообщений</h2>
            <button className={`${getAccentColorClass('text')} text-sm flex items-center gap-2 hover:underline`}>
              <FileText size={14} />
              Технический протокол обмена транзакциями с ТО
            </button>
          </div>
          
          <div className={`flex gap-6 py-4 border-t ${theme.table.border}`}>
            <span className={`text-sm ${theme.text.secondary} whitespace-nowrap`}>1 октября 2025</span>
            <div className="flex-1">
              <p className={`text-sm ${theme.text.primary}`}>
                С 1 октября 2025 вышла новая версия формата ФТС. Декларации созданные до этой даты не могут быть отправлены в таможенный орган...
              </p>
              <button className={`${getAccentColorClass('text')} text-sm mt-2 hover:underline`}>Скопировать</button>
            </div>
          </div>
        </div>
      </div>

      {/* Основные документы */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <div className="flex items-center justify-between mb-4">
          <h2 className={`text-lg font-semibold ${theme.text.primary}`}>Основные документы</h2>
          
          {/* Dropdown меню "Добавить" */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className={`
                px-3 py-1.5 rounded-lg text-sm flex items-center gap-2
                ${isDark ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}
              `}>
                <Plus size={14} />
                Добавить
                <ChevronDown size={14} />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent 
              align="end" 
              className={`min-w-[280px] ${isDark ? 'bg-[#1e1e22] border-white/10' : 'bg-white border-gray-200'}`}
            >
              {getAddMenuItems().map((item) => (
                <DropdownMenuItem 
                  key={item}
                  className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}
                >
                  {item}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        
        <div className={`border-t ${theme.table.border}`}>
          {getMainDocuments().map((doc) => (
            <div 
              key={doc.id} 
              className={`flex items-center justify-between py-3 border-b ${theme.table.border} cursor-pointer ${
                isDark ? 'hover:bg-white/5' : 'hover:bg-gray-50'
              }`}
              onClick={() => console.log('Открыть документ:', doc.name)}
            >
              <div className="flex items-center gap-2">
                <span className={`${theme.text.primary} hover:underline`}>{doc.name}</span>
                {doc.hasLink && <Link size={14} className={getAccentColorClass('text')} />}
              </div>
              <div className="flex items-center gap-4">
                <span className={doc.statusColor}>{doc.status}</span>
                {/* Action buttons */}
                <div className="flex items-center gap-1">
                  <button 
                    className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`} 
                    title="Просмотр"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <FileText size={16} className={theme.text.secondary} />
                  </button>
                  <button 
                    className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`} 
                    title="Редактировать"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Pencil size={16} className={theme.text.secondary} />
                  </button>
                  <button 
                    className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`} 
                    title="Удалить"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Trash2 size={16} className={theme.text.secondary} />
                  </button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button 
                        className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <MoreVertical size={16} className={theme.text.secondary} />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent 
                      align="end" 
                      className={`min-w-[280px] ${isDark ? 'bg-[#1e1e22] border-white/10' : 'bg-white border-gray-200'}`}
                    >
                      <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                        Скопировать данные из декларации
                      </DropdownMenuItem>
                      <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                        Создать копию документа
                      </DropdownMenuItem>
                      <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                        Создать шаблон
                      </DropdownMenuItem>
                      <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                        Переместить в «Регистрационные документы»
                      </DropdownMenuItem>
                      <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                        Скачать xml
                      </DropdownMenuItem>
                      <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                        Загрузить из xml
                      </DropdownMenuItem>
                      <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                        Создать документ после сканирования на ТПФК
                      </DropdownMenuItem>
                      <DropdownMenuSeparator className={isDark ? 'bg-white/10' : 'bg-gray-200'} />
                      <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer flex items-center gap-2`}>
                        <FileText size={14} />
                        Просмотреть печатную форму
                      </DropdownMenuItem>
                      <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer flex items-center gap-2`}>
                        <Pencil size={14} />
                        Изменить реквизиты
                      </DropdownMenuItem>
                      <DropdownMenuItem className={`text-accent-red hover:bg-red-500/10 cursor-pointer flex items-center gap-2`}>
                        <Trash2 size={14} />
                        Удалить
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Документы по товарам (графа 44) */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <div className="flex items-center justify-between mb-4">
          <h2 className={`text-lg font-semibold ${theme.text.primary}`}>
            Документы по товарам <span className={`font-normal ${theme.text.secondary}`}>графа 44</span>
          </h2>
          <div className="flex items-center gap-2">
            <button className={`
              px-3 py-1.5 rounded-lg text-sm flex items-center gap-2
              ${isDark ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}
            `}>
              <Plus size={14} />
              Добавить из списка
            </button>
            <button className={`
              px-3 py-1.5 rounded-lg text-sm flex items-center gap-2
              ${isDark ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}
            `}>
              <FileText size={14} />
              Создать несколько
              <ChevronDown size={14} />
            </button>
            <button className={`
              px-3 py-1.5 rounded-lg text-sm flex items-center gap-2
              ${isDark ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}
            `}>
              <Upload size={14} />
              Загрузить документы
            </button>
          </div>
        </div>
        
        {/* Панель действий при выборе документов по товарам */}
        {selectedGoodsDocs.length > 0 && (
          <div className={`flex items-center gap-4 py-3 px-4 mb-4 rounded-lg ${isDark ? 'bg-white/5' : 'bg-gray-50'}`}>
            <span className={`text-sm ${theme.text.secondary}`}>Выбрано: {selectedGoodsDocs.length}</span>
            <button className={`${getAccentColorClass('text')} text-sm flex items-center gap-1 hover:underline`}>
              <ArrowLeftRight size={14} />
              Связать с товарами
            </button>
            <button className={`${getAccentColorClass('text')} text-sm flex items-center gap-1 hover:underline`}>
              <ArrowUpDown size={14} />
              Перенести в регистрационные документы
            </button>
            <button className="text-accent-red text-sm flex items-center gap-1 hover:underline">
              <Trash2 size={14} />
              Удалить
            </button>
          </div>
        )}
        
        <table className="w-full">
          <thead>
            <tr className={`border-b ${theme.table.border}`}>
              <th className="w-10 py-3 text-left">
                  <Checkbox 
                    checked={selectedGoodsDocs.length === goodsDocuments.length && goodsDocuments.length > 0}
                    className={getCheckboxClasses(selectedGoodsDocs.length === goodsDocuments.length && goodsDocuments.length > 0)}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        onSelectedGoodsDocsChange(goodsDocuments.map(doc => doc.id));
                      } else {
                        onSelectedGoodsDocsChange([]);
                      }
                    }}
                  />
                </th>
                <th className={`w-[400px] py-3 text-left text-sm font-medium ${theme.text.secondary}`}>Документ</th>
                <th className={`py-3 text-left text-sm font-medium ${theme.text.secondary}`}>Статус</th>
              <th className="w-36 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {goodsDocuments.map((doc) => (
                <tr key={doc.id} className={`border-b ${theme.table.border} ${theme.table.row} ${
                  selectedGoodsDocs.includes(doc.id) ? (isDark ? 'bg-white/5' : 'bg-blue-50/50') : ''
                }`}>
                <td className="py-3">
                    <Checkbox 
                      checked={selectedGoodsDocs.includes(doc.id)}
                      className={getCheckboxClasses(selectedGoodsDocs.includes(doc.id))}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          onSelectedGoodsDocsChange([...selectedGoodsDocs, doc.id]);
                        } else {
                          onSelectedGoodsDocsChange(selectedGoodsDocs.filter(id => id !== doc.id));
                        }
                      }}
                    />
                  </td>
                  <td className="py-3">
                    <div className={`font-medium ${theme.text.primary}`}>{doc.type}</div>
                    <div className={`text-sm ${theme.text.secondary}`}>
                      {doc.code} № {doc.number} от {doc.date}
                    </div>
                    <div className={`text-sm ${theme.text.secondary}`}>
                      Указан в <span className={getAccentColorClass('text')}>{doc.linkedGoods} товаре</span>
                    </div>
                  </td>
                  <td className="py-3">
                    {doc.archived ? (
                      <div className={getAccentColorClass('text')}>Размещен в архиве</div>
                    ) : (
                      <div>
                        <div className="text-accent-yellow">Не размещен</div>
                        <button className={`${getAccentColorClass('text')} text-sm hover:underline mt-1`}>
                          Разместить в архиве
                        </button>
                      </div>
                    )}
                    {!doc.presentedWithDT && (
                      <div className={`text-sm ${theme.text.secondary} flex items-center gap-1`}>
                        не представляется с ДТ
                        <Copy size={12} className={`${getAccentColorClass('text')} cursor-pointer`} />
                      </div>
                    )}
                  </td>
                  <td className="py-3">
                    {/* Action buttons */}
                    <div className="flex items-center gap-1">
                      <button className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`} title="Просмотр">
                        <FileText size={16} className={theme.text.secondary} />
                      </button>
                      <button className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`} title="Редактировать">
                        <Pencil size={16} className={theme.text.secondary} />
                      </button>
                      <button className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`} title="Удалить">
                        <Trash2 size={16} className={theme.text.secondary} />
                      </button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`}>
                            <MoreVertical size={16} className={theme.text.secondary} />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent 
                          align="end" 
                          className={`min-w-[280px] ${isDark ? 'bg-medium-gray border-white/10' : 'bg-white border-gray-200'}`}
                        >
                          <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                            Скопировать данные из декларации
                          </DropdownMenuItem>
                          <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                            Создать копию документа
                          </DropdownMenuItem>
                          <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                            Создать шаблон
                          </DropdownMenuItem>
                          <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                            Переместить в «Регистрационные документы»
                          </DropdownMenuItem>
                          <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                            Скачать xml
                          </DropdownMenuItem>
                          <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                            Загрузить из xml
                          </DropdownMenuItem>
                          <DropdownMenuSeparator className={isDark ? 'bg-white/10' : 'bg-gray-200'} />
                          <DropdownMenuItem className={`text-accent-red hover:bg-red-500/10 cursor-pointer flex items-center gap-2`}>
                            <Trash2 size={14} />
                            Удалить
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
      </div>

      {/* Регистрационные документы (графа 44) */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <div className="flex items-center justify-between mb-4">
          <h2 className={`text-lg font-semibold ${theme.text.primary}`}>
            Регистрационные документы <span className={`font-normal ${theme.text.secondary}`}>графа 44</span>
          </h2>
          <div className="flex items-center gap-2">
            <button className={`
              px-3 py-1.5 rounded-lg text-sm flex items-center gap-2
              ${isDark ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}
            `}>
              <Plus size={14} />
              Добавить из списка
            </button>
            <button className={`
              px-3 py-1.5 rounded-lg text-sm flex items-center gap-2
              ${isDark ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}
            `}>
              <FileText size={14} />
              Создать несколько
              <ChevronDown size={14} />
            </button>
          </div>
        </div>
        
        {/* Панель действий при выборе регистрационных документов */}
        {selectedRegDocs.length > 0 && (
          <div className={`flex items-center gap-4 py-3 px-4 mb-4 rounded-lg ${isDark ? 'bg-white/5' : 'bg-gray-50'}`}>
            <span className={`text-sm ${theme.text.secondary}`}>Выбрано: {selectedRegDocs.length}</span>
            <button className={`${getAccentColorClass('text')} text-sm flex items-center gap-1 hover:underline`}>
              <ArrowUpDown size={14} />
              Перенести в документы по товарам
            </button>
            <button className="text-accent-red text-sm flex items-center gap-1 hover:underline">
              <Trash2 size={14} />
              Удалить
            </button>
          </div>
        )}
        
        <table className="w-full">
          <thead>
            <tr className={`border-b ${theme.table.border}`}>
              <th className="w-10 py-3 text-left">
                  <Checkbox 
                    checked={selectedRegDocs.length === registrationDocuments.length && registrationDocuments.length > 0}
                    className={getCheckboxClasses(selectedRegDocs.length === registrationDocuments.length && registrationDocuments.length > 0)}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        onSelectedRegDocsChange(registrationDocuments.map(doc => doc.id));
                      } else {
                        onSelectedRegDocsChange([]);
                      }
                    }}
                  />
                </th>
                <th className={`w-[400px] py-3 text-left text-sm font-medium ${theme.text.secondary}`}>Документ</th>
                <th className={`py-3 text-left text-sm font-medium ${theme.text.secondary}`}>Статус</th>
                <th className="w-36 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {registrationDocuments.map((doc) => (
                <tr key={doc.id} className={`border-b ${theme.table.border} ${theme.table.row} ${
                  selectedRegDocs.includes(doc.id) ? (isDark ? 'bg-white/5' : 'bg-blue-50/50') : ''
                }`}>
                  <td className="py-3">
                    <Checkbox 
                      checked={selectedRegDocs.includes(doc.id)}
                      className={getCheckboxClasses(selectedRegDocs.includes(doc.id))}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          onSelectedRegDocsChange([...selectedRegDocs, doc.id]);
                        } else {
                          onSelectedRegDocsChange(selectedRegDocs.filter(id => id !== doc.id));
                        }
                      }}
                    />
                  </td>
                  <td className="py-3">
                    <div className={`font-medium ${theme.text.primary}`}>{doc.type}</div>
                    <div className={`text-sm ${theme.text.secondary}`}>
                      {doc.code} № {doc.number} от {doc.date}
                    </div>
                  </td>
                  <td className="py-3">
                    {doc.archived ? (
                      <div className={getAccentColorClass('text')}>Размещен в архиве</div>
                    ) : (
                      <div>
                        <div className="text-accent-yellow">Не размещен</div>
                        <button className={`${getAccentColorClass('text')} text-sm hover:underline mt-1`}>
                          Разместить в архиве
                        </button>
                      </div>
                    )}
                    {!doc.presentedWithDT && (
                      <div className={`text-sm ${theme.text.secondary} flex items-center gap-1`}>
                        не представляется с ДТ
                        <Copy size={12} className={`${getAccentColorClass('text')} cursor-pointer`} />
                      </div>
                    )}
                  </td>
                  <td className="py-3">
                    {/* Action buttons */}
                    <div className="flex items-center gap-1">
                      <button className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`} title="Просмотр">
                        <FileText size={16} className={theme.text.secondary} />
                      </button>
                      <button className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`} title="Редактировать">
                        <Pencil size={16} className={theme.text.secondary} />
                      </button>
                      <button className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`} title="Удалить">
                        <Trash2 size={16} className={theme.text.secondary} />
                      </button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`}>
                            <MoreVertical size={16} className={theme.text.secondary} />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent 
                          align="end" 
                          className={`min-w-[280px] ${isDark ? 'bg-medium-gray border-white/10' : 'bg-white border-gray-200'}`}
                        >
                          <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                            Скопировать данные из декларации
                          </DropdownMenuItem>
                          <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                            Создать копию документа
                          </DropdownMenuItem>
                          <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                            Создать шаблон
                          </DropdownMenuItem>
                          <DropdownMenuItem className={`${isDark ? 'text-white hover:bg-white/10' : 'text-gray-900 hover:bg-gray-100'} cursor-pointer`}>
                            Переместить в «Документы по товарам»
                          </DropdownMenuItem>
                          <DropdownMenuSeparator className={isDark ? 'bg-white/10' : 'bg-gray-200'} />
                          <DropdownMenuItem className={`text-accent-red hover:bg-red-500/10 cursor-pointer flex items-center gap-2`}>
                            <Trash2 size={14} />
                            Удалить
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
      </div>

      {/* Кнопки действий */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className={`
              px-6 py-2 rounded-lg text-sm font-medium
              ${isDark ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}
            `}
          >
            Отменить
          </button>
          <button
            onClick={onSave}
            className={`
              px-6 py-2 rounded-lg text-sm font-medium text-white
              ${createDirection === 'IM' ? 'bg-accent-green hover:bg-accent-green/90' : createDirection === 'EK' ? 'bg-blue-600 hover:bg-blue-600/90' : 'bg-orange-500 hover:bg-orange-500/90'}
            `}
          >
            Сохранить изменения
          </button>
        </div>
      </div>
    </div>
  );
};
