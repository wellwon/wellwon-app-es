import type { OrderSummaryData, DealInfo } from '@/types/deal-info';

// Генератор номеров сделок
export const generateDealNumber = (): string => {
  const randomNum = Math.floor(Math.random() * 99999).toString().padStart(5, '0');
  return `S${randomNum}`;
};

// Генератор демо заказа
export const generateOrderSummary = (dealNumber: string): OrderSummaryData => {
  return {
    dealNumber,
    product: {
      name: 'Беспроводные наушники Sony WH-1000XM5',
      price: 85000,
      quantity: 50,
      supplier: 'Electronics Hub Shanghai'
    },
    services: [
      {
        category: 'ТОВАР и ЗАКУПКА',
        items: [
          { name: 'Поиск и выбор товара', price: 5000, selected: true },
          { name: 'Выкуп товара у поставщика', price: 2550, selected: true },
          { name: 'Проверка качества', price: 3000, selected: true }
        ]
      },
      {
        category: 'ОПЛАТА',
        items: [
          { name: 'Валютные операции', price: 4250, selected: true },
          { name: 'Финансирование закупки', price: 0, selected: false },
          { name: 'Банковские гарантии', price: 8500, selected: false }
        ]
      },
      {
        category: 'ЛОГИСТИКА',
        items: [
          { name: 'Забор товара у поставщика', price: 12000, selected: true },
          { name: 'Складская обработка', price: 8500, selected: true },
          { name: 'Обрешётка и упаковка', price: 6000, selected: true },
          { name: 'Страхование груза', price: 4250, selected: true }
        ]
      },
      {
        category: 'ПОСЛЕДНЯЯ МИЛЯ',
        items: [
          { name: 'Фулфилмент', price: 15000, selected: false },
          { name: 'Доставка до склада', price: 18500, selected: true },
          { name: 'Самовывоз', price: 0, selected: false }
        ]
      }
    ],
    payment: {
      method: 'Банковский перевод (70% предоплата)',
      total: 85000,
      currency: '₽'
    },
    delivery: {
      address: 'г. Москва, Ленинградское шоссе, 16А стр.1',
      date: '15-20 марта 2024',
      method: 'Автодоставка до склада'
    },
    totalCost: 172050
  };
};

// Генератор информации о сделке
export const generateDealInfo = (dealNumber: string): DealInfo => {
  const products = [
    { name: 'Электроника и гаджеты', weight: 850, volume: 2.5, quantity: 100, cost: 125000 },
    { name: 'Детские игрушки', weight: 1200, volume: 4.2, quantity: 200, cost: 89000 },
    { name: 'Спортивные товары', weight: 2100, volume: 8.1, quantity: 150, cost: 245000 },
    { name: 'Текстиль и одежда', weight: 680, volume: 3.8, quantity: 300, cost: 156000 },
    { name: 'Автозапчасти', weight: 1850, volume: 5.2, quantity: 80, cost: 198000 }
  ];
  
  const product = products[Math.floor(Math.random() * products.length)];
  
  return {
    dealNumber,
    product: product.name,
    weight: product.weight,
    volume: product.volume,
    quantity: product.quantity,
    cost: product.cost,
    deliveryTime: '14-18 дней',
    deliveryAddress: 'Москва, склад на Ленинградке',
    services: [
      { name: 'Карго доставка', cost: 28500, status: 'paid' },
      { name: 'Таможенное оформление', cost: 15200, status: 'paid' },
      { name: 'Страхование груза', cost: 4800, status: 'pending' },
      { name: 'Складские услуги', cost: 6700, status: 'unpaid' },
      { name: 'Сертификация товара', cost: 12300, status: 'paid' }
    ],
    payments: [
      { name: 'Предоплата поставщику', amount: product.cost * 0.3, status: 'paid' },
      { name: 'Доплата за товар', amount: product.cost * 0.7, status: 'pending', dueDate: '15.02.2024' },
      { name: 'Оплата логистики', amount: 28500, status: 'paid' },
      { name: 'Таможенные платежи', amount: 23400, status: 'pending', dueDate: '20.02.2024' }
    ]
  };
};

// Генератор ответов ИИ
export const getAIResponse = (userMessage: string): string => {
  const responses = [
    "Отличный вопрос! Для решения этой задачи рекомендую следующие шаги...",
    "Это очень важная тема в современном бизнесе. Позвольте разобрать детально...",
    "На основе опыта наших клиентов, могу предложить несколько проверенных решений...",
    "Этот вопрос часто задают предприниматели. Вот что важно знать...",
    "Для эффективного решения этой задачи стоит рассмотреть комплексный подход..."
  ];
  return responses[Math.floor(Math.random() * responses.length)];
};