/**
 * CreateDeclarationPage - Страница создания декларации
 * Интегрирована в DeclarantContent для Platform Pro
 */

import React, { useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { createDocflow, type CreateDocflowRequest, type DocflowResponse } from '../api';
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
  Loader2,
  Send,
} from 'lucide-react';

// Типы
interface CreateDeclarationState {
  direction: '' | 'IM' | 'EK' | 'TT';
  customsProcedure: string;
  feature: string;
  customsOffice: string;
  organization: string;
  declarant: string;
  transitType: string;
  transitFeature: string;
  selectedGoodsDocs: string[];
  selectedRegDocs: string[];
  rightPanelMode: 'upload' | 'journal';
}

interface ThemeConfig {
  page: string;
  text: {
    primary: string;
    secondary: string;
  };
  card: {
    background: string;
    border: string;
  };
  button: {
    default: string;
    danger: string;
  };
  table: {
    header: string;
    row: string;
    border: string;
  };
}

interface SelectOption {
  value: string;
  label: string;
}

interface DocumentItem {
  id: string;
  name?: string;
  type?: string;
  code?: string;
  number?: string;
  date?: string;
  status?: string;
  statusColor?: string;
  hasLink?: boolean;
  linkedGoods?: number;
  archived?: boolean;
  presentedWithDT?: boolean;
}

interface CreateDeclarationPageProps {
  state: CreateDeclarationState;
  onStateChange: (state: CreateDeclarationState) => void;
  isDark: boolean;
  theme: ThemeConfig;
  onCancel: () => void;
  onSave: () => void;
  onOpenDeclarationForm?: () => void;
}

// Мок-данные
const customsProceduresIM: SelectOption[] = [
  { value: '40', label: '40 - Выпуск для внутреннего потребления' },
  { value: '41', label: '41 - Свободная таможенная зона' },
  { value: '42', label: '42 - Переработка на таможенной территории' },
  { value: '51', label: '51 - Переработка вне таможенной территории' },
  { value: '53', label: '53 - Временный ввоз (допуск)' },
  { value: '63', label: '63 - Реимпорт' },
  { value: '78', label: '78 - Уничтожение' },
];

const customsProceduresEK: SelectOption[] = [
  { value: '10', label: '10 - Экспорт' },
  { value: '21', label: '21 - Реэкспорт' },
  { value: '22', label: '22 - Временный вывоз' },
  { value: '23', label: '23 - Переработка вне таможенной территории' },
  { value: '31', label: '31 - Свободная таможенная зона' },
  { value: '78', label: '78 - Уничтожение' },
];

const featuresData: SelectOption[] = [
  { value: 'none', label: 'Без особенностей' },
  { value: 'auto', label: 'АВ - Автомобили' },
  { value: 'alcohol', label: 'АЛ - Алкогольная продукция' },
  { value: 'tobacco', label: 'ТБ - Табачная продукция' },
  { value: 'food', label: 'ПП - Пищевая продукция' },
  { value: 'medicine', label: 'ЛС - Лекарственные средства' },
];

const transitTypesData: SelectOption[] = [
  { value: '80', label: '80 - Таможенный транзит' },
  { value: '81', label: '81 - Таможенный транзит (ТС)' },
  { value: '82', label: '82 - Международный транзит' },
  { value: '83', label: '83 - Внутренний транзит' },
];

const transitFeaturesData: SelectOption[] = [
  { value: 'none', label: 'Без особенностей' },
  { value: 'dangerous', label: 'ОГ - Опасные грузы' },
  { value: 'oversized', label: 'НГ - Негабаритные грузы' },
  { value: 'perishable', label: 'СП - Скоропортящиеся грузы' },
  { value: 'valuable', label: 'ЦГ - Ценные грузы' },
];

const customsOfficesData: SelectOption[] = [
  { value: 'central', label: '10000000 - Центральная акцизная таможня' },
  { value: 'moscow', label: '10129000 - Московская областная таможня' },
  { value: 'sheremetyevo', label: '10005000 - Шереметьевская таможня' },
  { value: 'domodedovo', label: '10002000 - Домодедовская таможня' },
  { value: 'vnukovo', label: '10001000 - Внуковская таможня' },
  { value: 'baltiysk', label: '10216000 - Балтийская таможня' },
  { value: 'spb', label: '10210000 - Санкт-Петербургская таможня' },
];

const organizationsData: SelectOption[] = [
  { value: 'promtorg', label: 'ООО "Промторг"' },
  { value: 'techimport', label: 'ООО "ТехИмпорт"' },
  { value: 'euroservice', label: 'АО "ЕвроСервис"' },
  { value: 'globallogistics', label: 'ООО "Глобал Логистикс"' },
  { value: 'transsnab', label: 'ЗАО "ТрансСнаб"' },
];

const declarantsData: SelectOption[] = [
  { value: 'ivanov', label: 'Иванов Иван Иванович' },
  { value: 'petrov', label: 'Петров Пётр Петрович' },
  { value: 'sidorov', label: 'Сидоров Сидор Сидорович' },
  { value: 'kuznetsova', label: 'Кузнецова Мария Александровна' },
  { value: 'sokolova', label: 'Соколова Анна Викторовна' },
];

const mainDocumentsIMEK: DocumentItem[] = [
  { id: '1', name: 'Декларация на товары', status: 'Не заполнено', statusColor: 'text-accent-red', hasLink: true },
];

const mainDocumentsTT: DocumentItem[] = [
  { id: '1', name: 'Транзитная декларация', status: 'Не заполнено', statusColor: 'text-accent-red', hasLink: false },
];

const addMenuItemsIMEK = [
  'ДТС-3',
  'ДТС-4',
  'Декларирование в нерабочее время',
  'Карточка транспортного средства',
];

const addMenuItemsTT = [
  'Декларирование в нерабочее время',
];

const goodsDocuments: DocumentItem[] = [
  {
    id: '1',
    type: 'Контракт',
    code: '03011/0',
    number: 'RU-CN-2018/156',
    date: '15 декабря 2018',
    linkedGoods: 3,
    archived: true,
    presentedWithDT: false
  },
  {
    id: '2',
    type: 'Спецификация к контракту',
    code: '03012/0',
    number: 'SPEC-156/RU-01',
    date: '20 декабря 2018',
    linkedGoods: 3,
    archived: false,
    presentedWithDT: false
  },
  {
    id: '3',
    type: 'Инвойс',
    code: '04021/0',
    number: 'IN-156/RU-12',
    date: '27 декабря 2018',
    linkedGoods: 1,
    archived: true,
    presentedWithDT: false
  }
];

const registrationDocuments: DocumentItem[] = [
  {
    id: '1',
    type: 'Свидетельство о государственной регистрации юридического лица',
    code: '04011/0',
    number: '60 00554457',
    date: '4 июля 2010',
    archived: true,
    presentedWithDT: false
  },
  {
    id: '2',
    type: 'Устав',
    code: '04011/0',
    number: 'б/н',
    date: '4 июля 2010',
    archived: false,
    presentedWithDT: false
  },
  {
    id: '3',
    type: 'Выписка из приказа о назначении на должность единоличного исполнительного органа организации',
    code: '04011/0',
    number: '1-K',
    date: '4 июля 2010',
    archived: true,
    presentedWithDT: false
  },
  {
    id: '4',
    type: 'Свидетельство о постановке на учет в налоговом органе',
    code: '04011/0',
    number: '60 00554460',
    date: '4 июля 2010',
    archived: true,
    presentedWithDT: false
  },
  {
    id: '5',
    type: 'Трудовой договор',
    code: '04011/0',
    number: '1',
    date: '4 июля 2010',
    archived: false,
    presentedWithDT: false
  },
  {
    id: '6',
    type: 'Паспорт гражданина РФ',
    code: '09023/0',
    number: '4504 №452188',
    date: '4 июля 2010',
    archived: true,
    presentedWithDT: false
  },
  {
    id: '7',
    type: 'Решение единственного учредителя',
    code: '04011/0',
    number: '1',
    date: '4 июля 2010',
    archived: true,
    presentedWithDT: false
  },
];

export const CreateDeclarationPage: React.FC<CreateDeclarationPageProps> = ({
  state,
  onStateChange,
  isDark,
  theme,
  onCancel,
  onSave,
  onOpenDeclarationForm,
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

  // Хелперы для обновления состояния
  const updateState = (updates: Partial<CreateDeclarationState>) => {
    onStateChange({ ...state, ...updates });
  };

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

  // ========== Docflow API State ==========
  const [isCreatingDocflow, setIsCreatingDocflow] = useState(false);
  const [docflowResponse, setDocflowResponse] = useState<DocflowResponse | null>(null);
  const [docflowError, setDocflowError] = useState<string | null>(null);

  // Маппинг направления на kontur_id type для API
  // Согласно справочнику: Ввоз=1, Вывоз=3, Транзит=24
  const directionToType: Record<string, number> = {
    'IM': 1,   // Ввоз (kontur_id=1)
    'EK': 3,   // Вывоз (kontur_id=3)
    'TT': 24,  // Таможенный транзит (kontur_id=24)
  };

  // Маппинг процедур (код -> kontur_id)
  // ИМ процедуры: 40->1, 51->2, 53->3, и т.д.
  // ЭК процедуры: 10->7, 21->8, 22->9, и т.д.
  const procedureToKonturId: Record<string, number> = {
    // ИМ процедуры
    '40': 1,   // Выпуск для внутреннего потребления
    '51': 2,   // Переработка на таможенной территории
    '53': 3,   // Временный ввоз
    '63': 4,   // Реимпорт
    '78': 5,   // Уничтожение (ИМ)
    '41': 6,   // Свободная таможенная зона (ИМ)
    '42': 2,   // Переработка на ТТ (аналог 51)
    // ЭК процедуры
    '10': 7,   // Экспорт
    '21': 8,   // Реэкспорт
    '22': 9,   // Временный вывоз
    '23': 10,  // Переработка вне ТТ
    '31': 11,  // Свободная таможенная зона (ЭК)
  };

  // Маппинг таможенных органов (мок-данные -> коды)
  const customsCodeMap: Record<string, number> = {
    'central': 10000000,
    'moscow': 10129000,
    'sheremetyevo': 10005000,
    'domodedovo': 10002000,
    'vnukovo': 10001000,
    'baltiysk': 10216000,
    'spb': 10210000,
  };

  // Маппинг организаций и сотрудников (мок -> реальные kontur_id)
  // TODO: Получать из справочников через API
  const organizationKonturIdMap: Record<string, string> = {
    'promtorg': '49e99c39-7ba1-48f0-a7be-0fcf92ed5c78',  // Демо-участник ВЭД
    'techimport': '49e99c39-7ba1-48f0-a7be-0fcf92ed5c78',
    'euroservice': '49e99c39-7ba1-48f0-a7be-0fcf92ed5c78',
    'globallogistics': '49e99c39-7ba1-48f0-a7be-0fcf92ed5c78',
    'transsnab': '49e99c39-7ba1-48f0-a7be-0fcf92ed5c78',
  };

  const employeeKonturIdMap: Record<string, string> = {
    'ivanov': '223f7665-52f0-4b00-8fa2-ba8b0d6dd536',     // Иванов Иван Иванович
    'petrov': '223f7665-52f0-4b00-8fa2-ba8b0d6dd536',
    'sidorov': '223f7665-52f0-4b00-8fa2-ba8b0d6dd536',
    'kuznetsova': '54355797-19d4-454c-967c-eef65b030b65', // Ладик Ольга Александровна
    'sokolova': '54355797-19d4-454c-967c-eef65b030b65',
  };

  // Проверка заполненности всех обязательных полей для активации кнопки
  const isFormValid = (): boolean => {
    // Базовые обязательные поля
    if (!createDirection || !createCustomsOffice || !createOrganization || !createDeclarant) {
      return false;
    }
    // Для ИМ/ЭК нужна процедура
    if ((createDirection === 'IM' || createDirection === 'EK') && !createCustomsProcedure) {
      return false;
    }
    // Для ТТ нужен вид перемещения
    if (createDirection === 'TT' && !createTransitType) {
      return false;
    }
    return true;
  };

  const canCreateDocflow = isFormValid();

  // Функция создания пакета декларации
  const handleCreateDocflow = async () => {
    // Валидация обязательных полей (дополнительная проверка)
    if (!canCreateDocflow) {
      setDocflowError('Заполните все обязательные поля');
      return;
    }

    setIsCreatingDocflow(true);
    setDocflowError(null);
    setDocflowResponse(null);

    try {
      const request: CreateDocflowRequest = {
        type: directionToType[createDirection] ?? 1,
        procedure: procedureToKonturId[createCustomsProcedure] ?? 1,
        customs: customsCodeMap[createCustomsOffice] || 10129000,
        organization_id: organizationKonturIdMap[createOrganization] || createOrganization,
        employee_id: employeeKonturIdMap[createDeclarant] || createDeclarant,
      };

      // Добавляем особенности если выбраны
      if (createFeature && createFeature !== 'none') {
        // TODO: маппинг особенностей на singularity ID
      }

      console.log('Creating docflow with request:', request);
      const response = await createDocflow(request);
      setDocflowResponse(response);
    } catch (error) {
      console.error('Error creating docflow:', error);
      setDocflowError(error instanceof Error ? error.message : 'Произошла ошибка при создании пакета');
    } finally {
      setIsCreatingDocflow(false);
    }
  };

  // Стили для Select
  const selectStyles = `h-10 rounded-xl transition-none focus:outline-none focus:ring-0 ${
    isDark
      ? 'bg-[#1e1e22] border-white/10 text-white'
      : 'bg-gray-50 border-gray-300 text-gray-900'
  }`;

  const selectContentStyles = isDark
    ? 'bg-[#232328] border-white/10'
    : 'bg-white border-gray-200';

  const selectItemStyles = isDark
    ? 'focus:bg-white/10 focus:text-white text-white'
    : 'focus:bg-gray-100 focus:text-gray-900 text-gray-900';

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
                  <Select value={createCustomsProcedure} onValueChange={(v) => updateState({ customsProcedure: v, feature: '' })}>
                    <SelectTrigger className={selectStyles}>
                      <SelectValue placeholder="Заполните значение" />
                    </SelectTrigger>
                    <SelectContent className={selectContentStyles}>
                      {getCustomsProcedures().map(p => (
                        <SelectItem key={p.value} value={p.value} className={selectItemStyles}>{p.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Особенности */}
                <div className="grid grid-cols-[240px_1fr] items-center gap-4">
                  <label className={`text-sm flex items-center gap-1 ${theme.text.secondary}`}>
                    Особенности [7]
                    <HelpCircle size={14} className={getAccentColorClass('text')} />
                  </label>
                  <Select value={createFeature} onValueChange={(v) => updateState({ feature: v })}>
                    <SelectTrigger className={selectStyles}>
                      <SelectValue placeholder="Заполните значение" />
                    </SelectTrigger>
                    <SelectContent className={selectContentStyles}>
                      {featuresData.map(f => (
                        <SelectItem key={f.value} value={f.value} className={selectItemStyles}>{f.label}</SelectItem>
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
                  <Select value={createTransitType} onValueChange={(v) => updateState({ transitType: v })}>
                    <SelectTrigger className={selectStyles}>
                      <SelectValue placeholder="Заполните значение" />
                    </SelectTrigger>
                    <SelectContent className={selectContentStyles}>
                      {transitTypesData.map(t => (
                        <SelectItem key={t.value} value={t.value} className={selectItemStyles}>{t.label}</SelectItem>
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
                  <Select value={createTransitFeature} onValueChange={(v) => updateState({ transitFeature: v })}>
                    <SelectTrigger className={selectStyles}>
                      <SelectValue placeholder="Заполните значение" />
                    </SelectTrigger>
                    <SelectContent className={selectContentStyles}>
                      {transitFeaturesData.map(f => (
                        <SelectItem key={f.value} value={f.value} className={selectItemStyles}>{f.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}

            {/* Таможенный орган */}
            <div className="grid grid-cols-[240px_1fr] items-center gap-4">
              <label className={`text-sm ${theme.text.secondary}`}>Таможенный орган</label>
              <Select value={createCustomsOffice} onValueChange={(v) => updateState({ customsOffice: v })}>
                <SelectTrigger className={selectStyles}>
                  <SelectValue placeholder="Выберите таможенный орган" />
                </SelectTrigger>
                <SelectContent className={selectContentStyles}>
                  {customsOfficesData.map(o => (
                    <SelectItem key={o.value} value={o.value} className={selectItemStyles}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Организация */}
            <div className="grid grid-cols-[240px_1fr] items-center gap-4">
              <label className={`text-sm ${theme.text.secondary}`}>Организация</label>
              <div className="flex gap-2">
                <Select value={createOrganization} onValueChange={(v) => updateState({ organization: v })}>
                  <SelectTrigger className={`${selectStyles} flex-1`}>
                    <SelectValue placeholder="Выберите организацию" />
                  </SelectTrigger>
                  <SelectContent className={selectContentStyles}>
                    {organizationsData.map(o => (
                      <SelectItem key={o.value} value={o.value} className={selectItemStyles}>{o.label}</SelectItem>
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
                <Select value={createDeclarant} onValueChange={(v) => updateState({ declarant: v })}>
                  <SelectTrigger className={`${selectStyles} flex-1`}>
                    <SelectValue placeholder="Выберите заполняющее лицо" />
                  </SelectTrigger>
                  <SelectContent className={selectContentStyles}>
                    {declarantsData.map(d => (
                      <SelectItem key={d.value} value={d.value} className={selectItemStyles}>{d.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <button className={`p-2 rounded-lg hover:opacity-80 h-10 w-10 flex items-center justify-center border ${createDirection === 'IM' ? 'bg-accent-green/20 text-accent-green border-accent-green/30' : createDirection === 'EK' ? 'bg-blue-600/20 text-blue-500 border-blue-600/30' : 'bg-orange-500/20 text-orange-500 border-orange-500/30'}`}>
                  <Plus size={18} />
                </button>
              </div>
            </div>

            {/* Кнопка создания пакета декларации */}
            <div className="grid grid-cols-[240px_1fr] items-center gap-4 pt-4 mt-4 border-t border-white/10">
              <div></div>
              <div className="flex flex-col gap-2">
                <button
                  onClick={handleCreateDocflow}
                  disabled={!canCreateDocflow || isCreatingDocflow}
                  className={`
                    px-6 py-3 rounded-xl text-sm font-medium text-white flex items-center justify-center gap-2 w-full
                    ${canCreateDocflow
                      ? (createDirection === 'IM' ? 'bg-accent-green hover:bg-accent-green/90' : createDirection === 'EK' ? 'bg-blue-600 hover:bg-blue-600/90' : 'bg-orange-500 hover:bg-orange-500/90')
                      : (isDark ? 'bg-white/10 text-gray-500' : 'bg-gray-200 text-gray-400')
                    }
                    disabled:opacity-50 disabled:cursor-not-allowed transition-colors
                  `}
                >
                  {isCreatingDocflow ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      Создание пакета...
                    </>
                  ) : (
                    <>
                      <Send size={18} />
                      Создать пакет декларации
                    </>
                  )}
                </button>

                {/* Подсказка когда кнопка неактивна */}
                {!canCreateDocflow && (
                  <p className={`text-xs ${theme.text.secondary}`}>
                    Заполните все обязательные поля для создания пакета
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Правая часть - Загрузчик документов / Журнал сообщений */}
        <div className={`flex-1 rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className={`text-lg font-semibold ${theme.text.primary}`}>
              {state.rightPanelMode === 'upload' ? 'Загрузка документов' : 'Журнал сообщений'}
            </h2>
            <button
              onClick={() => onStateChange({
                ...state,
                rightPanelMode: state.rightPanelMode === 'upload' ? 'journal' : 'upload'
              })}
              className={`text-sm flex items-center gap-2 px-3 py-1.5 rounded-lg border ${
                isDark
                  ? 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/10'
                  : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
              }`}
            >
              {state.rightPanelMode === 'upload' ? (
                <>
                  <FileText size={14} />
                  Журнал сообщений
                </>
              ) : (
                <>
                  <Upload size={14} />
                  Загрузка документов
                </>
              )}
            </button>
          </div>

          {state.rightPanelMode === 'upload' ? (
            /* Режим загрузки документов */
            <div className="flex flex-col h-[calc(100%-3rem)]">
              <label
                className={`
                  flex-1 border-2 border-dashed rounded-xl flex flex-col items-center justify-center gap-3 p-6
                  transition-colors cursor-pointer
                  ${isDark
                    ? 'border-white/20 hover:border-white/40 hover:bg-white/[0.02]'
                    : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
                  }
                `}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.currentTarget.classList.add(isDark ? 'border-white/40' : 'border-gray-400');
                  e.currentTarget.classList.add(isDark ? 'bg-white/[0.02]' : 'bg-gray-50');
                }}
                onDragLeave={(e) => {
                  e.currentTarget.classList.remove(isDark ? 'border-white/40' : 'border-gray-400');
                  e.currentTarget.classList.remove(isDark ? 'bg-white/[0.02]' : 'bg-gray-50');
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.currentTarget.classList.remove(isDark ? 'border-white/40' : 'border-gray-400');
                  e.currentTarget.classList.remove(isDark ? 'bg-white/[0.02]' : 'bg-gray-50');
                  // Handle dropped files
                  const files = Array.from(e.dataTransfer.files);
                  console.log('Dropped files:', files);
                }}
              >
                <div className={`p-4 rounded-full ${
                  isDark ? 'bg-white/10' : 'bg-gray-100'
                }`}>
                  <Upload size={24} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
                </div>
                <div className="text-center">
                  <p className={`text-sm font-medium ${theme.text.primary}`}>
                    Перетащите файлы сюда
                  </p>
                  <p className={`text-xs ${theme.text.secondary} mt-1`}>
                    или нажмите для выбора
                  </p>
                </div>
                <input
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    const files = Array.from(e.target.files || []);
                    console.log('Selected files:', files);
                  }}
                />
              </label>
              <p className={`text-xs ${theme.text.secondary} mt-3 text-center`}>
                Поддерживаемые форматы: PDF, XML, JPG, PNG, XLSX, DOCX
              </p>
            </div>
          ) : (
            /* Режим журнала сообщений */
            <div className="flex flex-col h-[calc(100%-3rem)]">
              <div className="flex-1">
                <div className={`flex gap-6 py-4 border-t ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
                  <span className={`text-sm ${theme.text.secondary} whitespace-nowrap`}>1 октября 2025</span>
                  <div className="flex-1">
                    <p className={`text-sm ${theme.text.primary}`}>
                      С 1 октября 2025 вышла новая версия формата ФТС. Декларации созданные до этой даты не могут быть отправлены в таможенный орган...
                    </p>
                    <button className={`${getAccentColorClass('text')} text-sm mt-2 hover:underline`}>Скопировать</button>
                  </div>
                </div>
              </div>
              <div className={`pt-4 border-t ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
                <button className={`${getAccentColorClass('text')} text-sm flex items-center gap-2 hover:underline`}>
                  <FileText size={14} />
                  Технический протокол обмена транзакциями с ТО
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* DEBUG: API Response (временная плашка) */}
      {(docflowError || docflowResponse) && (
        <div className={`rounded-2xl p-6 border-2 border-dashed ${isDark ? 'border-yellow-500/50 bg-yellow-500/5' : 'border-yellow-400 bg-yellow-50'}`}>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-yellow-500 text-xs font-mono px-2 py-0.5 rounded bg-yellow-500/20">DEBUG</span>
            <h3 className={`text-sm font-semibold ${theme.text.primary}`}>
              Ответ API Kontur
            </h3>
          </div>

          {docflowError && (
            <div className={`p-4 rounded-lg ${isDark ? 'bg-red-500/10 border border-red-500/30' : 'bg-red-50 border border-red-200'}`}>
              <p className="text-accent-red font-medium text-sm">Ошибка</p>
              <p className={`text-sm mt-1 ${theme.text.secondary}`}>{docflowError}</p>
            </div>
          )}

          {docflowResponse && (
            <div className={`p-4 rounded-lg ${isDark ? 'bg-accent-green/10 border border-accent-green/30' : 'bg-green-50 border border-green-200'}`}>
              <p className="text-accent-green font-medium text-sm mb-2">Пакет успешно создан!</p>
              <pre className={`text-xs overflow-auto p-3 rounded font-mono ${isDark ? 'bg-black/50' : 'bg-gray-100'} ${theme.text.primary}`}>
                {JSON.stringify(docflowResponse, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

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
              className={`min-w-[280px] ${isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}`}
            >
              {getAddMenuItems().map((item) => (
                <DropdownMenuItem
                  key={item}
                  className={`${isDark ? 'text-white focus:bg-white/10 focus:text-white' : 'text-gray-900 focus:bg-gray-100 focus:text-gray-900'} cursor-pointer`}
                >
                  {item}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="-mx-6 -mb-6">
          {(() => {
            const docs = getMainDocuments();
            return docs.map((doc, index) => {
              const isLast = index === docs.length - 1;
              return (
                <div
                  key={doc.id}
                  onClick={() => {
                    // Если это "Декларация на товары" и есть hasLink, открываем форму
                    if (doc.hasLink && onOpenDeclarationForm) {
                      onOpenDeclarationForm();
                    }
                  }}
                  className={`
                    flex items-center justify-between py-3 px-6 cursor-pointer
                    ${!isLast ? `border-b ${isDark ? 'border-white/10' : 'border-gray-200'}` : ''}
                    ${isDark ? 'hover:bg-white/[0.03]' : 'hover:bg-[#f4f4f6]'}
                    ${isLast ? 'rounded-b-2xl' : ''}
                  `}
                >
                  <div className="flex items-center gap-2">
                    <span className={theme.text.primary}>{doc.name}</span>
                    {doc.hasLink && <Link size={14} className={getAccentColorClass('text')} />}
                  </div>
                  <div className="flex items-center gap-4">
                    <span className={doc.statusColor}>{doc.status}</span>
                    {/* Action buttons */}
                    <div className="flex items-center gap-1">
                      <button
                        className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`}
                        title="Просмотр"
                      >
                        <FileText size={16} className={theme.text.secondary} />
                      </button>
                      <button
                        className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`}
                        title="Редактировать"
                      >
                        <Pencil size={16} className={theme.text.secondary} />
                      </button>
                      <button
                        className={`p-1.5 rounded ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`}
                        title="Удалить"
                      >
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
                          <DropdownMenuSeparator className={isDark ? 'bg-white/10' : 'bg-gray-200'} />
                          <DropdownMenuItem className="text-accent-red hover:bg-red-500/10 cursor-pointer flex items-center gap-2">
                            <Trash2 size={14} />
                            Удалить
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                </div>
              );
            });
          })()}
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

        <div className="-mx-6 -mb-6">
          <table className="w-full table-fixed">
            <colgroup>
              <col className="w-14" />
              <col className="w-[45%]" />
              <col />
              <col className="w-32" />
            </colgroup>
            <thead>
              <tr className={`border-b ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
                <th className="py-3 pl-6 pr-2 text-left">
                  <Checkbox
                    checked={selectedGoodsDocs.length === goodsDocuments.length && goodsDocuments.length > 0}
                    className={getCheckboxClasses(selectedGoodsDocs.length === goodsDocuments.length && goodsDocuments.length > 0)}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        updateState({ selectedGoodsDocs: goodsDocuments.map(doc => doc.id) });
                      } else {
                        updateState({ selectedGoodsDocs: [] });
                      }
                    }}
                  />
                </th>
                <th className={`py-3 pr-4 text-left text-sm font-medium ${theme.text.secondary}`}>Документ</th>
                <th className={`py-3 pr-4 text-left text-sm font-medium ${theme.text.secondary}`}>Статус</th>
                <th className="py-3 pr-6"></th>
              </tr>
            </thead>
            <tbody>
              {goodsDocuments.map((doc, index) => {
                const isLast = index === goodsDocuments.length - 1;
                const isSelected = selectedGoodsDocs.includes(doc.id);
                return (
                  <tr
                    key={doc.id}
                    className={`
                      group cursor-pointer
                      ${!isLast ? `border-b ${isDark ? 'border-white/10' : 'border-gray-200'}` : ''}
                      ${isSelected
                        ? (isDark ? 'bg-white/5' : 'bg-blue-50/50')
                        : (isDark ? 'hover:bg-white/[0.03]' : 'hover:bg-[#f4f4f6]')
                      }
                      ${isLast ? 'rounded-b-2xl' : ''}
                    `}
                  >
                    <td className={`py-3 pl-6 pr-2 align-top ${isLast ? 'rounded-bl-2xl' : ''}`}>
                      <Checkbox
                        checked={isSelected}
                        className={getCheckboxClasses(isSelected)}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            updateState({ selectedGoodsDocs: [...selectedGoodsDocs, doc.id] });
                          } else {
                            updateState({ selectedGoodsDocs: selectedGoodsDocs.filter(id => id !== doc.id) });
                          }
                        }}
                      />
                    </td>
                    <td className="py-3 pr-4 align-top">
                      <div className={`font-medium ${theme.text.primary}`}>{doc.type}</div>
                      <div className={`text-sm ${theme.text.secondary}`}>
                        {doc.code} № {doc.number} от {doc.date}
                      </div>
                      <div className={`text-sm ${theme.text.secondary}`}>
                        Указан в <span className={getAccentColorClass('text')}>{doc.linkedGoods} товаре</span>
                      </div>
                    </td>
                    <td className="py-3 pr-4 align-top">
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
                    <td className={`py-3 pr-6 align-top ${isLast ? 'rounded-br-2xl' : ''}`}>
                      <div className="flex items-center gap-1 justify-end">
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
                            <DropdownMenuSeparator className={isDark ? 'bg-white/10' : 'bg-gray-200'} />
                            <DropdownMenuItem className="text-accent-red hover:bg-red-500/10 cursor-pointer flex items-center gap-2">
                              <Trash2 size={14} />
                              Удалить
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
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

        <div className="-mx-6 -mb-6">
          <table className="w-full table-fixed">
            <colgroup>
              <col className="w-14" />
              <col className="w-[45%]" />
              <col />
              <col className="w-32" />
            </colgroup>
            <thead>
              <tr className={`border-b ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
                <th className="py-3 pl-6 pr-2 text-left">
                  <Checkbox
                    checked={selectedRegDocs.length === registrationDocuments.length && registrationDocuments.length > 0}
                    className={getCheckboxClasses(selectedRegDocs.length === registrationDocuments.length && registrationDocuments.length > 0)}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        updateState({ selectedRegDocs: registrationDocuments.map(doc => doc.id) });
                      } else {
                        updateState({ selectedRegDocs: [] });
                      }
                    }}
                  />
                </th>
                <th className={`py-3 pr-4 text-left text-sm font-medium ${theme.text.secondary}`}>Документ</th>
                <th className={`py-3 pr-4 text-left text-sm font-medium ${theme.text.secondary}`}>Статус</th>
                <th className="py-3 pr-6"></th>
              </tr>
            </thead>
            <tbody>
              {registrationDocuments.map((doc, index) => {
                const isLast = index === registrationDocuments.length - 1;
                const isSelected = selectedRegDocs.includes(doc.id);
                return (
                  <tr
                    key={doc.id}
                    className={`
                      group cursor-pointer
                      ${!isLast ? `border-b ${isDark ? 'border-white/10' : 'border-gray-200'}` : ''}
                      ${isSelected
                        ? (isDark ? 'bg-white/5' : 'bg-blue-50/50')
                        : (isDark ? 'hover:bg-white/[0.03]' : 'hover:bg-[#f4f4f6]')
                      }
                      ${isLast ? 'rounded-b-2xl' : ''}
                    `}
                  >
                    <td className={`py-3 pl-6 pr-2 align-top ${isLast ? 'rounded-bl-2xl' : ''}`}>
                      <Checkbox
                        checked={isSelected}
                        className={getCheckboxClasses(isSelected)}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            updateState({ selectedRegDocs: [...selectedRegDocs, doc.id] });
                          } else {
                            updateState({ selectedRegDocs: selectedRegDocs.filter(id => id !== doc.id) });
                          }
                        }}
                      />
                    </td>
                    <td className="py-3 pr-4 align-top">
                      <div className={`font-medium ${theme.text.primary}`}>{doc.type}</div>
                      <div className={`text-sm ${theme.text.secondary}`}>
                        {doc.code} № {doc.number} от {doc.date}
                      </div>
                    </td>
                    <td className="py-3 pr-4 align-top">
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
                    <td className={`py-3 pr-6 align-top ${isLast ? 'rounded-br-2xl' : ''}`}>
                      <div className="flex items-center gap-1 justify-end">
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
                            <DropdownMenuSeparator className={isDark ? 'bg-white/10' : 'bg-gray-200'} />
                          <DropdownMenuItem className="text-accent-red hover:bg-red-500/10 cursor-pointer flex items-center gap-2">
                            <Trash2 size={14} />
                            Удалить
                          </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
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

export default CreateDeclarationPage;
