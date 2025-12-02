/**
 * DeclarationFormPage - Полная форма таможенной декларации на товары (ДТ)
 * Открывается по клику на "Декларация на товары" в пакете
 *
 * Структура разделов (слева навигация):
 * 1. Организации (графы 2, 8, 9, 14)
 * 2. Перевозка товаров (графы 15, 17, 18, 21, 25, 26, 29, 30)
 * 3. Условия сделки (графы 11, 20, 22, 23, 24)
 * 4. Товары (графы 31-47)
 * 5. Итог по товарам (графы 12, 22, B)
 * 6. Кто заполнил (графа 54)
 */

import React, { useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Building2,
  Truck,
  FileText,
  Package,
  Calculator,
  User,
  ChevronRight,
  Plus,
  Trash2,
  Save,
  ArrowLeft,
  Search,
  X,
} from 'lucide-react';

// =============================================================================
// Types
// =============================================================================

interface DeclarationFormState {
  // Организации
  sender: {
    name: string;
    address: {
      country: string;
      index: string;
      city: string;
      street: string;
    };
  };
  receiver: {
    name: string;
    inn: string;
    kpp: string;
    ogrn: string;
    address: string;
    sameAsDeclarant: boolean;
  };
  financialResponsible: {
    sameAsDeclarant: boolean;
    inn?: string;
    name?: string;
  };
  declarant: {
    name: string;
    inn: string;
    kpp: string;
    ogrn: string;
    address: string;
  };

  // Перевозка
  transport: {
    departureCountry: string;
    destinationCountry: string;
    borderAuthority: string;
    totalPlaces: number;
    inContainer: boolean;
    borderTransport: {
      type: string;
      number: string;
      count: number;
      registrationCountry: string;
    };
    arrivalTransport: {
      type: string;
    };
    goodsLocation: {
      place: string;
      svhLicense: string;
      customsPost: string;
      address: {
        country: string;
        region: string;
        city: string;
        street: string;
        house: string;
      };
    };
  };

  // Условия сделки
  dealTerms: {
    tradingCountry: string;
    deliveryTerms: {
      code: string;
      place: string;
    };
    transactionNature: string;
    transactionFeature: string;
    contractCurrency: string;
    currencyRate: {
      rate: number;
      amount: number;
      currency: string;
      date: string;
    };
  };

  // Товары (массив)
  goods: GoodItem[];

  // Кто заполнил
  filledBy: {
    person: string;
    isCustomsRepresentative: boolean;
    date: string;
  };
}

interface GoodItem {
  id: string;
  // Кодификация
  tnved: string;
  hasIntellectualProperty: boolean;
  intellectualProperty?: {
    type: string;
    registryNumber: string;
  };
  description: string;
  manufacturer: string;
  trademark: string;

  // Артикулы/позиции
  positions: {
    id: string;
    article: string;
    cryptoNumber: string;
  }[];

  // Упаковка и веса
  originCountry: string;
  packaging: {
    places: number;
    type: string;
  };
  netWeight: number;
  netWeightNoPackaging?: number;
  grossWeight: number;

  // Стоимость
  procedure: {
    main: string;
    previous: string;
  };
  price: number;
  customsValue: number;
  valuationMethod: string;
  statisticalValue: number;

  // Документы
  documents: {
    id: string;
    code: string;
    number: string;
    date: string;
  }[];

  // Платежи
  payments: {
    id: string;
    type: string; // 1010-сборы, 2010-пошлина, 5010-НДС
    basis: number;
    rate: string;
    amount: number;
    paymentMethod: string;
  }[];
}

interface DeclarationFormPageProps {
  isDark: boolean;
  onBack: () => void;
  onSave: () => void;
}

// =============================================================================
// Component
// =============================================================================

export const DeclarationFormPage: React.FC<DeclarationFormPageProps> = ({
  isDark,
  onBack,
  onSave,
}) => {
  const [activeSection, setActiveSection] = useState<
    'organizations' | 'transport' | 'dealTerms' | 'goods' | 'totals' | 'filledBy'
  >('organizations');

  const [formState, setFormState] = useState<DeclarationFormState>({
    sender: {
      name: '',
      address: {
        country: '',
        index: '',
        city: '',
        street: '',
      },
    },
    receiver: {
      name: '',
      inn: '',
      kpp: '',
      ogrn: '',
      address: '',
      sameAsDeclarant: false,
    },
    financialResponsible: {
      sameAsDeclarant: true,
    },
    declarant: {
      name: '',
      inn: '',
      kpp: '',
      ogrn: '',
      address: '',
    },
    transport: {
      departureCountry: '',
      destinationCountry: '',
      borderAuthority: '',
      totalPlaces: 0,
      inContainer: false,
      borderTransport: {
        type: '',
        number: '',
        count: 1,
        registrationCountry: '',
      },
      arrivalTransport: {
        type: '',
      },
      goodsLocation: {
        place: '',
        svhLicense: '',
        customsPost: '',
        address: {
          country: '',
          region: '',
          city: '',
          street: '',
          house: '',
        },
      },
    },
    dealTerms: {
      tradingCountry: '',
      deliveryTerms: {
        code: '',
        place: '',
      },
      transactionNature: '',
      transactionFeature: '',
      contractCurrency: '',
      currencyRate: {
        rate: 0,
        amount: 1,
        currency: '',
        date: new Date().toISOString().split('T')[0],
      },
    },
    goods: [],
    filledBy: {
      person: '',
      isCustomsRepresentative: false,
      date: new Date().toISOString().split('T')[0],
    },
  });

  // Theme object
  const theme = isDark
    ? {
        page: 'bg-[#1a1a1e]',
        card: { background: 'bg-[#232328]', border: 'border-white/10' },
        text: { primary: 'text-white', secondary: 'text-gray-400' },
        input: {
          background: 'bg-[#1e1e22]',
          border: 'border-white/10',
          text: 'text-white',
          placeholder: 'placeholder:text-gray-500',
          hover: 'hover:border-white/20',
        },
        button: {
          default: 'text-gray-300 hover:text-white hover:bg-white/10',
          glass: 'bg-white/5 border-white/10 text-gray-300 hover:bg-white/10 hover:text-white hover:border-white/20',
        },
      }
    : {
        page: 'bg-[#f4f4f4]',
        card: { background: 'bg-white', border: 'border-gray-300 shadow-sm' },
        text: { primary: 'text-gray-900', secondary: 'text-gray-600' },
        input: {
          background: 'bg-gray-50',
          border: 'border-gray-300',
          text: 'text-gray-900',
          placeholder: 'placeholder:text-gray-400',
          hover: 'hover:border-gray-400',
        },
        button: {
          default: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100',
          glass: 'bg-gray-100 border-gray-200 text-gray-600 hover:bg-gray-200 hover:text-gray-900',
        },
      };

  // Navigation items
  const navItems = [
    { id: 'organizations', icon: Building2, label: 'Организации', grafas: '2, 8, 9, 14' },
    { id: 'transport', icon: Truck, label: 'Перевозка товаров', grafas: '15-30' },
    { id: 'dealTerms', icon: FileText, label: 'Условия сделки', grafas: '11, 20-24' },
    { id: 'goods', icon: Package, label: 'Товары', grafas: '31-47' },
    { id: 'totals', icon: Calculator, label: 'Итог по товарам', grafas: '12, 22, B' },
    { id: 'filledBy', icon: User, label: 'Кто заполнил', grafas: '54' },
  ] as const;

  // Input styles
  const inputStyles = `h-10 w-full rounded-xl border px-3 py-2 text-sm
    focus:outline-none focus:ring-0 transition-none
    ${theme.input.background} ${theme.input.border} ${theme.input.text} ${theme.input.placeholder} ${theme.input.hover}`;

  const labelStyles = `text-sm font-medium ${theme.text.primary}`;

  // Helper: Add good item
  const addGoodItem = () => {
    const newGood: GoodItem = {
      id: Date.now().toString(),
      tnved: '',
      hasIntellectualProperty: false,
      description: '',
      manufacturer: '',
      trademark: '',
      positions: [{ id: Date.now().toString(), article: '', cryptoNumber: '' }],
      originCountry: '',
      packaging: { places: 0, type: '' },
      netWeight: 0,
      grossWeight: 0,
      procedure: { main: '', previous: '' },
      price: 0,
      customsValue: 0,
      valuationMethod: '1',
      statisticalValue: 0,
      documents: [],
      payments: [],
    };
    setFormState((prev) => ({ ...prev, goods: [...prev.goods, newGood] }));
  };

  // Helper: Remove good item
  const removeGoodItem = (id: string) => {
    setFormState((prev) => ({
      ...prev,
      goods: prev.goods.filter((g) => g.id !== id),
    }));
  };

  // =============================================================================
  // Render Sections
  // =============================================================================

  const renderOrganizations = () => (
    <div className="space-y-6">
      {/* [2] Отправитель */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <h3 className={`text-lg font-semibold mb-4 ${theme.text.primary}`}>[2] Отправитель</h3>
        <div className="space-y-4">
          <div>
            <label className={labelStyles}>Наименование</label>
            <input
              type="text"
              className={inputStyles}
              value={formState.sender.name}
              onChange={(e) =>
                setFormState((prev) => ({
                  ...prev,
                  sender: { ...prev.sender, name: e.target.value },
                }))
              }
              placeholder="Введите название компании (латиницей)"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelStyles}>Страна</label>
              <input type="text" className={inputStyles} placeholder="Например, FR" />
            </div>
            <div>
              <label className={labelStyles}>Индекс</label>
              <input type="text" className={inputStyles} placeholder="75001" />
            </div>
          </div>
          <div>
            <label className={labelStyles}>Город</label>
            <input type="text" className={inputStyles} placeholder="Paris" />
          </div>
          <div>
            <label className={labelStyles}>Улица, дом</label>
            <input type="text" className={inputStyles} placeholder="Rue de Rivoli, 12" />
          </div>
        </div>
      </div>

      {/* [8] Получатель */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <div className="flex items-center justify-between mb-4">
          <h3 className={`text-lg font-semibold ${theme.text.primary}`}>[8] Получатель</h3>
          <label className="flex items-center gap-2 cursor-pointer">
            <Checkbox
              checked={formState.receiver.sameAsDeclarant}
              onCheckedChange={(checked) =>
                setFormState((prev) => ({
                  ...prev,
                  receiver: { ...prev.receiver, sameAsDeclarant: !!checked },
                }))
              }
              className="rounded"
            />
            <span className={`text-sm ${theme.text.secondary}`}>Совпадает с Декларантом</span>
          </label>
        </div>
        <div className="space-y-4">
          <div>
            <label className={labelStyles}>Наименование организации</label>
            <input type="text" className={inputStyles} placeholder="ООО «Ромашка»" />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className={labelStyles}>ИНН *</label>
              <input type="text" className={inputStyles} maxLength={12} placeholder="1234567890" />
            </div>
            <div>
              <label className={labelStyles}>КПП</label>
              <input type="text" className={inputStyles} maxLength={9} placeholder="123456789" />
            </div>
            <div>
              <label className={labelStyles}>ОГРН</label>
              <input type="text" className={inputStyles} maxLength={13} placeholder="1234567890123" />
            </div>
          </div>
          <div>
            <label className={labelStyles}>Адрес регистрации</label>
            <input type="text" className={inputStyles} placeholder="г. Москва, ул. Ленина, д. 1" />
          </div>
        </div>
      </div>

      {/* [9] Ответственный за финансовое урегулирование */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <div className="flex items-center justify-between mb-4">
          <h3 className={`text-lg font-semibold ${theme.text.primary}`}>
            [9] Ответственный за финансовое урегулирование
          </h3>
          <label className="flex items-center gap-2 cursor-pointer">
            <Checkbox
              checked={formState.financialResponsible.sameAsDeclarant}
              onCheckedChange={(checked) =>
                setFormState((prev) => ({
                  ...prev,
                  financialResponsible: { sameAsDeclarant: !!checked },
                }))
              }
              className="rounded"
            />
            <span className={`text-sm ${theme.text.secondary}`}>Совпадает с Декларантом</span>
          </label>
        </div>
        {!formState.financialResponsible.sameAsDeclarant && (
          <div className="space-y-4">
            <div>
              <label className={labelStyles}>ИНН</label>
              <input type="text" className={inputStyles} maxLength={12} />
            </div>
            <div>
              <label className={labelStyles}>Наименование</label>
              <input type="text" className={inputStyles} />
            </div>
          </div>
        )}
      </div>

      {/* [14] Декларант */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <h3 className={`text-lg font-semibold mb-4 ${theme.text.primary}`}>[14] Декларант</h3>
        <div className="space-y-4">
          <div>
            <label className={labelStyles}>Наименование организации</label>
            <input type="text" className={inputStyles} placeholder="ООО «Ромашка»" />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className={labelStyles}>ИНН *</label>
              <input type="text" className={inputStyles} maxLength={12} placeholder="1234567890" />
            </div>
            <div>
              <label className={labelStyles}>КПП</label>
              <input type="text" className={inputStyles} maxLength={9} placeholder="123456789" />
            </div>
            <div>
              <label className={labelStyles}>ОГРН</label>
              <input type="text" className={inputStyles} maxLength={13} placeholder="1234567890123" />
            </div>
          </div>
          <div>
            <label className={labelStyles}>Юридический адрес</label>
            <input type="text" className={inputStyles} placeholder="г. Москва, ул. Ленина, д. 1" />
          </div>
        </div>
      </div>
    </div>
  );

  const renderTransport = () => (
    <div className="space-y-6">
      {/* Страны и орган */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <h3 className={`text-lg font-semibold mb-4 ${theme.text.primary}`}>Маршрут и орган въезда</h3>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelStyles}>[15] Страна отправления</label>
              <Select>
                <SelectTrigger className={inputStyles}>
                  <SelectValue placeholder="Выберите страну" />
                </SelectTrigger>
                <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                  <SelectItem value="FR" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                    Франция
                  </SelectItem>
                  <SelectItem value="DE" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                    Германия
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className={labelStyles}>[17] Страна назначения</label>
              <Select>
                <SelectTrigger className={inputStyles}>
                  <SelectValue placeholder="Выберите страну" />
                </SelectTrigger>
                <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                  <SelectItem value="RU" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                    Россия
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <label className={labelStyles}>[29] Орган въезда на границе</label>
            <input type="text" className={inputStyles} placeholder="10005000 - Шереметьевская таможня" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelStyles}>[6] Всего мест</label>
              <input type="number" className={inputStyles} min={0} />
            </div>
            <div className="flex items-center pt-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <Checkbox className="rounded" />
                <span className={`text-sm ${theme.text.primary}`}>[19] Перевозка в контейнере</span>
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* [21/25] Транспортное средство на границе */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <h3 className={`text-lg font-semibold mb-4 ${theme.text.primary}`}>
          [21/25] Транспортное средство на границе
        </h3>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelStyles}>Вид транспорта</label>
              <Select>
                <SelectTrigger className={inputStyles}>
                  <SelectValue placeholder="Выберите вид" />
                </SelectTrigger>
                <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                  <SelectItem value="40" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                    40 - Воздушный
                  </SelectItem>
                  <SelectItem value="30" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                    30 - Автомобильный
                  </SelectItem>
                  <SelectItem value="20" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                    20 - Железнодорожный
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className={labelStyles}>Номер рейса/ТС</label>
              <input type="text" className={inputStyles} placeholder="SU0750" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelStyles}>Количество ТС</label>
              <input type="number" className={inputStyles} min={1} defaultValue={1} />
            </div>
            <div>
              <label className={labelStyles}>Страна регистрации ТС</label>
              <Select>
                <SelectTrigger className={inputStyles}>
                  <SelectValue placeholder="Выберите страну" />
                </SelectTrigger>
                <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                  <SelectItem value="RU" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                    Россия
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </div>

      {/* [18/26] ТС при прибытии в ТО */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <h3 className={`text-lg font-semibold mb-4 ${theme.text.primary}`}>
          [18/26] ТС при прибытии в таможенный орган
        </h3>
        <div>
          <label className={labelStyles}>Вид транспорта</label>
          <Select>
            <SelectTrigger className={inputStyles}>
              <SelectValue placeholder="Выберите вид" />
            </SelectTrigger>
            <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
              <SelectItem value="30" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                30 - Автомобильный
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* [30] Местонахождение товаров */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <h3 className={`text-lg font-semibold mb-4 ${theme.text.primary}`}>[30] Местонахождение товаров</h3>
        <div className="space-y-4">
          <div>
            <label className={labelStyles}>Место</label>
            <Select>
              <SelectTrigger className={inputStyles}>
                <SelectValue placeholder="Выберите тип места" />
              </SelectTrigger>
              <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                <SelectItem value="svh" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                  СВХ
                </SelectItem>
                <SelectItem value="ztk" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                  ЗТК
                </SelectItem>
                <SelectItem value="receiver" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                  Склад получателя
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className={labelStyles}>СВХ (Лицензия)</label>
            <input type="text" className={inputStyles} placeholder="Номер свидетельства СВХ" />
          </div>
          <div>
            <label className={labelStyles}>Таможенный пост</label>
            <input type="text" className={inputStyles} placeholder="10005000" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelStyles}>Регион</label>
              <input type="text" className={inputStyles} placeholder="Московская область" />
            </div>
            <div>
              <label className={labelStyles}>Город</label>
              <input type="text" className={inputStyles} placeholder="Москва" />
            </div>
          </div>
          <div>
            <label className={labelStyles}>Улица, дом</label>
            <input type="text" className={inputStyles} placeholder="ул. Ленина, д. 1" />
          </div>
        </div>
      </div>
    </div>
  );

  const renderDealTerms = () => (
    <div className="space-y-6">
      {/* Торгующая страна и условия */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <h3 className={`text-lg font-semibold mb-4 ${theme.text.primary}`}>Торгующая страна и условия поставки</h3>
        <div className="space-y-4">
          <div>
            <label className={labelStyles}>[11] Торгующая страна</label>
            <Select>
              <SelectTrigger className={inputStyles}>
                <SelectValue placeholder="Выберите страну" />
              </SelectTrigger>
              <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                <SelectItem value="FR" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                  Франция
                </SelectItem>
                <SelectItem value="DE" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                  Германия
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelStyles}>[20] Код условия поставки</label>
              <Select>
                <SelectTrigger className={inputStyles}>
                  <SelectValue placeholder="Выберите Incoterms" />
                </SelectTrigger>
                <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                  <SelectItem value="EXW" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                    EXW - Ex Works
                  </SelectItem>
                  <SelectItem value="FCA" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                    FCA - Free Carrier
                  </SelectItem>
                  <SelectItem value="CIP" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                    CIP - Carriage and Insurance Paid
                  </SelectItem>
                  <SelectItem value="DAP" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                    DAP - Delivered at Place
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className={labelStyles}>Географический пункт</label>
              <input type="text" className={inputStyles} placeholder="MOCKBA" />
            </div>
          </div>
        </div>
      </div>

      {/* Характер сделки */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <h3 className={`text-lg font-semibold mb-4 ${theme.text.primary}`}>Характер сделки</h3>
        <div className="space-y-4">
          <div>
            <label className={labelStyles}>[24] Характер сделки</label>
            <Select>
              <SelectTrigger className={inputStyles}>
                <SelectValue placeholder="Выберите характер" />
              </SelectTrigger>
              <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                <SelectItem value="010" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                  010 - Возмездная поставка
                </SelectItem>
                <SelectItem value="020" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                  020 - Безвозмездная поставка
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className={labelStyles}>[24] Особенности сделки</label>
            <Select>
              <SelectTrigger className={inputStyles}>
                <SelectValue placeholder="Выберите особенность" />
              </SelectTrigger>
              <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                <SelectItem value="00" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                  00 - Без особенностей
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Валюта и курс */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <h3 className={`text-lg font-semibold mb-4 ${theme.text.primary}`}>Валюта контракта</h3>
        <div className="space-y-4">
          <div>
            <label className={labelStyles}>[22] Валюта контракта</label>
            <Select>
              <SelectTrigger className={inputStyles}>
                <SelectValue placeholder="Выберите валюту" />
              </SelectTrigger>
              <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                <SelectItem value="EUR" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                  EUR - Евро
                </SelectItem>
                <SelectItem value="USD" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                  USD - Доллар США
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className={labelStyles}>[23] Курс валюты</label>
            <div className={`p-3 rounded-xl ${theme.input.background} ${theme.input.border}`}>
              <p className={`text-sm ${theme.text.primary}`}>
                <span className="font-mono">92.4276</span> ₽ за <span className="font-mono">1</span> EUR на{' '}
                {new Date().toLocaleDateString('ru-RU')}
              </p>
              <p className={`text-xs mt-1 ${theme.text.secondary}`}>
                Автоматически подтягивается по дате подачи
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderGoods = () => (
    <div className="space-y-6">
      {/* Кнопка добавления товара */}
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className={`text-lg font-semibold ${theme.text.primary}`}>Товары</h3>
            <p className={`text-sm ${theme.text.secondary}`}>Графы 31-47</p>
          </div>
          <button
            onClick={addGoodItem}
            className={`px-4 h-10 rounded-xl flex items-center gap-2 text-sm font-medium
              bg-accent-red text-white hover:bg-accent-red/90 ${!isDark ? 'shadow-sm' : ''}`}
          >
            <Plus className="w-4 h-4" />
            Добавить товар
          </button>
        </div>
      </div>

      {/* Список товаров */}
      {formState.goods.length === 0 ? (
        <div className={`rounded-2xl p-12 border ${theme.card.background} ${theme.card.border} text-center`}>
          <Package className={`w-12 h-12 mx-auto mb-4 ${theme.text.secondary}`} />
          <p className={`text-sm ${theme.text.secondary}`}>Товары не добавлены. Нажмите "Добавить товар"</p>
        </div>
      ) : (
        formState.goods.map((good, index) => (
          <div key={good.id} className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
            {/* Header товара */}
            <div className="flex items-center justify-between mb-6">
              <h4 className={`text-lg font-semibold ${theme.text.primary}`}>Товар #{index + 1}</h4>
              <button
                onClick={() => removeGoodItem(good.id)}
                className="h-8 px-3 rounded-lg flex items-center justify-center
                  bg-accent-red/10 text-accent-red border border-accent-red/20
                  hover:bg-accent-red/20 hover:border-accent-red/30"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>

            {/* Кодификация и описание */}
            <div className="mb-6">
              <h5 className={`text-md font-semibold mb-3 ${theme.text.primary}`}>Кодификация и описание</h5>
              <div className="space-y-4">
                <div>
                  <label className={labelStyles}>[33] Код товара (ТН ВЭД) *</label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      className={inputStyles}
                      maxLength={10}
                      placeholder="1234567890"
                    />
                    <button
                      className={`h-10 px-3 rounded-xl border flex items-center gap-2 text-sm font-medium ${theme.button.glass}`}
                    >
                      <Search className="w-4 h-4" />
                      Поиск
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox className="rounded" />
                  <label className={`text-sm ${theme.text.primary}`}>Интеллектуальная собственность</label>
                </div>
                <div>
                  <label className={labelStyles}>[31] Описание товара *</label>
                  <textarea
                    className={`${inputStyles} min-h-[100px]`}
                    placeholder="Полное наименование, характеристики, материал..."
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelStyles}>Производитель</label>
                    <input type="text" className={inputStyles} placeholder="Schneider Electric" />
                  </div>
                  <div>
                    <label className={labelStyles}>Товарный знак</label>
                    <input type="text" className={inputStyles} placeholder="Schneider" />
                  </div>
                </div>
              </div>
            </div>

            {/* Упаковка и веса */}
            <div className="mb-6">
              <h5 className={`text-md font-semibold mb-3 ${theme.text.primary}`}>Упаковка и веса</h5>
              <div className="space-y-4">
                <div>
                  <label className={labelStyles}>[34] Страна происхождения</label>
                  <Select>
                    <SelectTrigger className={inputStyles}>
                      <SelectValue placeholder="Выберите страну" />
                    </SelectTrigger>
                    <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                      <SelectItem value="FR" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                        Франция
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className={labelStyles}>[31.2] Мест</label>
                    <input type="number" className={inputStyles} min={0} />
                  </div>
                  <div>
                    <label className={labelStyles}>Тип упаковки</label>
                    <Select>
                      <SelectTrigger className={inputStyles}>
                        <SelectValue placeholder="Выберите" />
                      </SelectTrigger>
                      <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                        <SelectItem value="box" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                          Коробки
                        </SelectItem>
                        <SelectItem value="pallet" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                          Паллеты
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelStyles}>[38] Вес нетто (кг)</label>
                    <input type="number" className={inputStyles} step="0.001" min={0} />
                  </div>
                  <div>
                    <label className={labelStyles}>[35] Вес брутто (кг)</label>
                    <input type="number" className={inputStyles} step="0.001" min={0} />
                  </div>
                </div>
              </div>
            </div>

            {/* Стоимость */}
            <div className="mb-6">
              <h5 className={`text-md font-semibold mb-3 ${theme.text.primary}`}>Стоимость</h5>
              <div className="space-y-4">
                <div>
                  <label className={labelStyles}>[37] Процедура</label>
                  <div className="grid grid-cols-2 gap-4">
                    <Select>
                      <SelectTrigger className={inputStyles}>
                        <SelectValue placeholder="Основная" />
                      </SelectTrigger>
                      <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                        <SelectItem value="40" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                          40 - Выпуск для внутр. потребления
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <Select>
                      <SelectTrigger className={inputStyles}>
                        <SelectValue placeholder="Предшествующая" />
                      </SelectTrigger>
                      <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                        <SelectItem value="00" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                          00 - Нет
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelStyles}>[42] Цена товара</label>
                    <input type="number" className={inputStyles} step="0.01" min={0} placeholder="В валюте контракта" />
                  </div>
                  <div>
                    <label className={labelStyles}>[45] Таможенная стоимость (₽)</label>
                    <input type="number" className={inputStyles} step="0.01" min={0} placeholder="Автоматический расчет" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelStyles}>[43] Метод определения ТС</label>
                    <Select>
                      <SelectTrigger className={inputStyles}>
                        <SelectValue placeholder="Выберите метод" />
                      </SelectTrigger>
                      <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                        <SelectItem value="1" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                          Метод 1 - По стоимости сделки
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className={labelStyles}>[46] Статистическая стоимость (USD)</label>
                    <input type="number" className={inputStyles} step="0.01" min={0} placeholder="Автоматический расчет" />
                  </div>
                </div>
              </div>
            </div>

            {/* Документы */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-3">
                <h5 className={`text-md font-semibold ${theme.text.primary}`}>[44] Документы</h5>
                <button
                  className={`px-3 h-8 rounded-lg flex items-center gap-2 text-sm font-medium ${theme.button.glass}`}
                >
                  <Plus className="w-3 h-3" />
                  Добавить
                </button>
              </div>
              <div className={`rounded-xl border ${theme.input.border} overflow-hidden`}>
                <table className="w-full">
                  <thead className={isDark ? 'bg-white/5' : 'bg-gray-50'}>
                    <tr className={`text-xs ${theme.text.secondary}`}>
                      <th className="px-3 py-2 text-left">Код</th>
                      <th className="px-3 py-2 text-left">Номер</th>
                      <th className="px-3 py-2 text-left">Дата</th>
                      <th className="px-3 py-2 text-right"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {good.documents.length === 0 ? (
                      <tr>
                        <td colSpan={4} className={`px-3 py-6 text-center text-sm ${theme.text.secondary}`}>
                          Документы не добавлены
                        </td>
                      </tr>
                    ) : (
                      good.documents.map((doc) => (
                        <tr key={doc.id} className={`border-t ${theme.input.border}`}>
                          <td className={`px-3 py-2 text-sm ${theme.text.primary}`}>{doc.code}</td>
                          <td className={`px-3 py-2 text-sm ${theme.text.primary}`}>{doc.number}</td>
                          <td className={`px-3 py-2 text-sm ${theme.text.primary}`}>{doc.date}</td>
                          <td className="px-3 py-2 text-right">
                            <button className="text-accent-red hover:text-accent-red/80">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Платежи */}
            <div>
              <h5 className={`text-md font-semibold mb-3 ${theme.text.primary}`}>[47] Исчисление платежей</h5>
              <div className={`rounded-xl border ${theme.input.border} overflow-hidden`}>
                <table className="w-full">
                  <thead className={isDark ? 'bg-white/5' : 'bg-gray-50'}>
                    <tr className={`text-xs ${theme.text.secondary}`}>
                      <th className="px-3 py-2 text-left">Вид</th>
                      <th className="px-3 py-2 text-left">Основа начисления</th>
                      <th className="px-3 py-2 text-left">Ставка</th>
                      <th className="px-3 py-2 text-left">Сумма (₽)</th>
                      <th className="px-3 py-2 text-left">СП</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className={`border-t ${theme.input.border}`}>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary}`}>1010 - Сборы</td>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary}`}>—</td>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary}`}>—</td>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary} font-mono`}>0.00</td>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary}`}>ИУ</td>
                    </tr>
                    <tr className={`border-t ${theme.input.border}`}>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary}`}>2010 - Пошлина</td>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary} font-mono`}>0.00</td>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary}`}>5%</td>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary} font-mono`}>0.00</td>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary}`}>ИУ</td>
                    </tr>
                    <tr className={`border-t ${theme.input.border}`}>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary}`}>5010 - НДС</td>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary} font-mono`}>0.00</td>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary}`}>20%</td>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary} font-mono`}>0.00</td>
                      <td className={`px-3 py-2 text-sm ${theme.text.primary}`}>ИУ</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );

  const renderTotals = () => (
    <div className="space-y-6">
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <h3 className={`text-lg font-semibold mb-6 ${theme.text.primary}`}>Сводная информация по декларации</h3>
        <div className="space-y-6">
          {/* Общая стоимость */}
          <div>
            <label className={`text-sm ${theme.text.secondary} block mb-2`}>[22] Общая сумма (в валюте контракта)</label>
            <div className={`p-4 rounded-xl ${isDark ? 'bg-white/5' : 'bg-gray-50'}`}>
              <p className={`text-2xl font-bold ${theme.text.primary} font-mono`}>0.00 EUR</p>
            </div>
          </div>

          {/* Общая таможенная стоимость */}
          <div>
            <label className={`text-sm ${theme.text.secondary} block mb-2`}>[12] Общая таможенная стоимость (₽)</label>
            <div className={`p-4 rounded-xl ${isDark ? 'bg-white/5' : 'bg-gray-50'}`}>
              <p className={`text-2xl font-bold ${theme.text.primary} font-mono`}>0.00 ₽</p>
            </div>
          </div>

          {/* Платежи */}
          <div>
            <label className={`text-sm ${theme.text.secondary} block mb-3`}>[B] Подробности подсчета</label>
            <div className={`rounded-xl border ${theme.input.border} overflow-hidden`}>
              <table className="w-full">
                <thead className={isDark ? 'bg-white/5' : 'bg-gray-50'}>
                  <tr className={`text-sm ${theme.text.secondary}`}>
                    <th className="px-4 py-3 text-left">Вид платежа</th>
                    <th className="px-4 py-3 text-right">Сумма (₽)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className={`border-t ${theme.input.border}`}>
                    <td className={`px-4 py-3 text-sm ${theme.text.primary}`}>Таможенные сборы</td>
                    <td className={`px-4 py-3 text-sm ${theme.text.primary} font-mono text-right`}>0.00</td>
                  </tr>
                  <tr className={`border-t ${theme.input.border}`}>
                    <td className={`px-4 py-3 text-sm ${theme.text.primary}`}>Таможенная пошлина</td>
                    <td className={`px-4 py-3 text-sm ${theme.text.primary} font-mono text-right`}>0.00</td>
                  </tr>
                  <tr className={`border-t ${theme.input.border}`}>
                    <td className={`px-4 py-3 text-sm ${theme.text.primary}`}>НДС</td>
                    <td className={`px-4 py-3 text-sm ${theme.text.primary} font-mono text-right`}>0.00</td>
                  </tr>
                  <tr className={`border-t ${theme.input.border} ${isDark ? 'bg-white/5' : 'bg-gray-50'}`}>
                    <td className={`px-4 py-3 text-sm font-semibold ${theme.text.primary}`}>Итого к уплате</td>
                    <td className={`px-4 py-3 text-sm font-semibold ${theme.text.primary} font-mono text-right`}>0.00</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Реквизиты плательщика */}
          <div>
            <label className={`text-sm ${theme.text.secondary} block mb-2`}>Реквизиты плательщика</label>
            <div className={`p-4 rounded-xl ${isDark ? 'bg-white/5' : 'bg-gray-50'}`}>
              <p className={`text-sm ${theme.text.primary}`}>ИНН: {formState.declarant.inn || '—'}</p>
              <p className={`text-sm ${theme.text.primary}`}>Наименование: {formState.declarant.name || '—'}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderFilledBy = () => (
    <div className="space-y-6">
      <div className={`rounded-2xl p-6 border ${theme.card.background} ${theme.card.border}`}>
        <h3 className={`text-lg font-semibold mb-4 ${theme.text.primary}`}>[54] Лицо, заполнившее декларацию</h3>
        <div className="space-y-4">
          <div className="flex items-center gap-2 mb-4">
            <Checkbox
              checked={formState.filledBy.isCustomsRepresentative}
              onCheckedChange={(checked) =>
                setFormState((prev) => ({
                  ...prev,
                  filledBy: { ...prev.filledBy, isCustomsRepresentative: !!checked },
                }))
              }
              className="rounded"
            />
            <label className={`text-sm ${theme.text.primary}`}>Декларация заполняется таможенным представителем</label>
          </div>
          <div>
            <label className={labelStyles}>ФИО и паспортные данные</label>
            <Select>
              <SelectTrigger className={inputStyles}>
                <SelectValue placeholder="Выберите сотрудника" />
              </SelectTrigger>
              <SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
                <SelectItem value="ivanov" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                  Иванов Иван Иванович
                </SelectItem>
                <SelectItem value="petrov" className={isDark ? 'text-white focus:bg-white/10' : 'text-gray-900 focus:bg-gray-100'}>
                  Петров Пётр Петрович
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className={labelStyles}>Дата заполнения</label>
            <input
              type="date"
              className={inputStyles}
              value={formState.filledBy.date}
              onChange={(e) =>
                setFormState((prev) => ({
                  ...prev,
                  filledBy: { ...prev.filledBy, date: e.target.value },
                }))
              }
            />
          </div>
        </div>
      </div>
    </div>
  );

  // =============================================================================
  // Main Render
  // =============================================================================

  return (
    <div className={`min-h-screen ${theme.page}`}>
      <div className="flex h-screen overflow-hidden">
        {/* Left Navigation */}
        <div className={`w-80 border-r ${theme.card.border} ${theme.card.background} flex flex-col`}>
          {/* Header */}
          <div className="p-6 border-b border-white/10">
            <button
              onClick={onBack}
              className={`flex items-center gap-2 text-sm ${theme.button.default} mb-4`}
            >
              <ArrowLeft className="w-4 h-4" />
              Вернуться к пакету
            </button>
            <h2 className={`text-xl font-semibold ${theme.text.primary}`}>Декларация на товары</h2>
            <p className={`text-sm ${theme.text.secondary} mt-1`}>ДТ № —</p>
          </div>

          {/* Navigation items */}
          <nav className="flex-1 overflow-y-auto p-4">
            <div className="space-y-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeSection === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveSection(item.id as typeof activeSection)}
                    className={`
                      w-full flex items-center justify-between px-4 py-3 rounded-xl text-sm font-medium transition-all
                      ${
                        isActive
                          ? 'bg-accent-red/10 border border-accent-red/30 text-accent-red'
                          : isDark
                          ? 'text-gray-300 hover:text-white hover:bg-white/10'
                          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                      }
                    `}
                  >
                    <div className="flex items-center gap-3">
                      <Icon className="w-5 h-5" />
                      <div className="text-left">
                        <div>{item.label}</div>
                        <div className={`text-xs ${isActive ? 'text-accent-red/70' : theme.text.secondary}`}>
                          {item.grafas}
                        </div>
                      </div>
                    </div>
                    <ChevronRight className={`w-4 h-4 ${isActive ? 'opacity-100' : 'opacity-0'}`} />
                  </button>
                );
              })}
            </div>
          </nav>

          {/* Footer with save button */}
          <div className="p-4 border-t border-white/10">
            <button
              onClick={onSave}
              className={`w-full h-10 rounded-xl flex items-center justify-center gap-2 text-sm font-medium
                bg-accent-red text-white hover:bg-accent-red/90 ${!isDark ? 'shadow-sm' : ''}`}
            >
              <Save className="w-4 h-4" />
              Сохранить декларацию
            </button>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-8">
            {activeSection === 'organizations' && renderOrganizations()}
            {activeSection === 'transport' && renderTransport()}
            {activeSection === 'dealTerms' && renderDealTerms()}
            {activeSection === 'goods' && renderGoods()}
            {activeSection === 'totals' && renderTotals()}
            {activeSection === 'filledBy' && renderFilledBy()}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DeclarationFormPage;
