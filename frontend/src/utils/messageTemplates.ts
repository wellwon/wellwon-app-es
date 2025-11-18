export interface MessageTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  template_data: {
    type: string;
    title: string;
    description: string;
    image_url?: string;
    image_position?: 'left' | 'right' | 'top' | 'bottom';
    image_format?: 'square' | 'vertical' | 'full-width';
    buttons: Array<{
      text: string;
      action: string;
      style?: string;
    }>;
  };
}

// Шаблоны сообщений по категориям
export const MESSAGE_TEMPLATES_BY_CATEGORY: Record<string, MessageTemplate[]> = {
  'основные': [
    {
      id: 'activate-account',
      name: 'Активация аккаунта',
      description: 'Помощь в активации аккаунта через Telegram',
      category: 'основные',
      template_data: {
        type: 'interactive',
        title: '✅ Активирую ваш аккаунт',
        description: 'Активируем ваш аккаунт через Telegram для быстрого доступа к платформе WellWon:',
        buttons: [
          { text: '📱 Связать Telegram', action: 'link_telegram' },
          { text: '🔐 Получить код', action: 'get_activation_code' },
          { text: '💬 Поддержка', action: 'contact_support' }
        ]
      }
    },
    {
      id: 'platform-intro',
      name: 'Знакомство с платформой',
      description: 'Введение в возможности платформы',
      category: 'основные',
      template_data: {
        type: 'interactive',
        title: '👋 Добро пожаловать в WellWon!',
        description: 'Рад приветствовать вас на нашей платформе! Давайте знакомиться с возможностями:',
        buttons: [
          { text: '🎯 Поставить задачу', action: 'create_task' },
          { text: '🔍 Найти исполнителя', action: 'find_performer' },
          { text: '💬 Задать вопрос', action: 'ask_question' }
        ]
      }
    }
  ],
  'поиск товара': [
    {
      id: 'search-product',
      name: 'Поиск товара',
      description: 'Помощь в поиске нужного товара',
      category: 'поиск товара',
      template_data: {
        type: 'interactive',
        title: '🔍 Найдем нужный товар',
        description: 'Опишите что вы ищете, и я помогу найти лучшие варианты с подходящими условиями:',
        buttons: [
          { text: 'Описать товар', action: 'describe_product' },
          { text: 'Сравнить цены', action: 'compare_prices' },
          { text: 'Найти производителя', action: 'find_manufacturer' }
        ]
      }
    },
    {
      id: 'product-specs',
      name: 'Характеристики товара',
      description: 'Запрос детальных характеристик',
      category: 'поиск товара',
      template_data: {
        type: 'interactive',
        title: '📋 Узнаем все характеристики',
        description: 'Получите подробную информацию о товаре: технические характеристики, сертификаты, условия поставки:',
        buttons: [
          { text: 'Технические данные', action: 'tech_specs' },
          { text: 'Сертификаты', action: 'certificates' },
          { text: 'Условия поставки', action: 'delivery_terms' }
        ]
      }
    }
  ],
  'финансы': [
    {
      id: 'price-request',
      name: 'Запрос цен',
      description: 'Получение актуальных цен и условий',
      category: 'финансы',
      template_data: {
        type: 'interactive',
        title: '💰 Узнаем лучшие цены',
        description: 'Получите актуальные цены от проверенных поставщиков с выгодными условиями:',
        buttons: [
          { text: 'Запросить КП', action: 'request_quote' },
          { text: 'Сравнить предложения', action: 'compare_offers' },
          { text: 'Обсудить условия', action: 'discuss_terms' }
        ]
      }
    },
    {
      id: 'payment-terms',
      name: 'Условия оплаты',
      description: 'Информация о способах и условиях оплаты',
      category: 'финансы',
      template_data: {
        type: 'interactive',
        title: '💳 Удобные способы оплаты',
        description: 'Выберите подходящий способ оплаты. Мы предлагаем гибкие условия для вашего бизнеса:',
        buttons: [
          { text: 'Банковский перевод', action: 'bank_transfer' },
          { text: 'Отсрочка платежа', action: 'payment_delay' },
          { text: 'Аккредитив', action: 'letter_of_credit' }
        ]
      }
    }
  ],
  'логистика': [
    {
      id: 'delivery-calculation',
      name: 'Расчет доставки',
      description: 'Расчет стоимости и сроков доставки',
      category: 'логистика',
      template_data: {
        type: 'interactive',
        title: '🚛 Рассчитаем доставку',
        description: 'Узнайте стоимость и сроки доставки до вашего склада. Выберите оптимальный вариант:',
        buttons: [
          { text: 'Экспресс доставка', action: 'express_delivery' },
          { text: 'Экономная доставка', action: 'economy_delivery' },
          { text: 'Выбрать дату', action: 'schedule_delivery' }
        ]
      }
    },
    {
      id: 'transport-method',
      name: 'Способ доставки',
      description: 'Выбор оптимального способа транспортировки',
      category: 'логистика',
      template_data: {
        type: 'interactive',
        title: '🌍 Выберем способ доставки',
        description: 'Подберем оптимальный способ транспортировки с учетом груза, расстояния и бюджета:',
        buttons: [
          { text: 'Автотранспорт', action: 'road_transport' },
          { text: 'Железная дорога', action: 'rail_transport' },
          { text: 'Авиаперевозки', action: 'air_transport' },
          { text: 'Морские контейнеры', action: 'sea_transport' }
        ]
      }
    }
  ],
  'последняя миля': [
    {
      id: 'address-clarification',
      name: 'Уточнение адреса',
      description: 'Уточнение деталей адреса доставки',
      category: 'последняя миля',
      template_data: {
        type: 'interactive',
        title: '📍 Уточним адрес доставки',
        description: 'Для точной доставки нужно уточнить детали адреса и условий приемки груза:',
        buttons: [
          { text: 'Уточнить адрес', action: 'clarify_address' },
          { text: 'Время приемки', action: 'reception_time' },
          { text: 'Контактное лицо', action: 'contact_person' }
        ]
      }
    },
    {
      id: 'delivery-time',
      name: 'Время доставки',
      description: 'Согласование времени и даты доставки',
      category: 'последняя миля',
      template_data: {
        type: 'interactive',
        title: '⏰ Согласуем время доставки',
        description: 'Выберите удобное время для получения груза. Мы подстроимся под ваш график:',
        buttons: [
          { text: 'Утром (9:00-12:00)', action: 'morning_delivery' },
          { text: 'Днем (12:00-15:00)', action: 'afternoon_delivery' },
          { text: 'Вечером (15:00-18:00)', action: 'evening_delivery' },
          { text: 'Выбрать дату', action: 'custom_time' }
        ]
      }
    }
  ]
};

// Экспорт для совместимости
export const MESSAGE_TEMPLATES: MessageTemplate[] = Object.values(MESSAGE_TEMPLATES_BY_CATEGORY).flat();