import React from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, Package, Shield, Truck, Gift, FileText, Calculator } from 'lucide-react';

interface ServiceItem {
  id: string;
  name: string;
  description: string;
  price: number;
  duration?: string;
  popular?: boolean;
  icon: React.ComponentType<any>;
}

interface ServiceCategory {
  title: string;
  description: string;
  items: ServiceItem[];
}

const serviceCategories: ServiceCategory[] = [
  {
    title: "Логистические услуги",
    description: "Доставка и транспортировка грузов",
    items: [
      {
        id: "express-delivery",
        name: "Экспресс-доставка",
        description: "Ускоренная доставка за 7-10 дней",
        price: 8500,
        duration: "7-10 дней",
        popular: true,
        icon: Truck
      },
      {
        id: "standard-delivery", 
        name: "Стандартная доставка",
        description: "Обычная доставка за 14-21 день",
        price: 4500,
        duration: "14-21 день",
        icon: Package
      }
    ]
  },
  {
    title: "Страхование и безопасность",
    description: "Защита груза и финансовые гарантии",
    items: [
      {
        id: "cargo-insurance",
        name: "Страхование груза",
        description: "Полное страхование на сумму груза",
        price: 12500,
        popular: true,
        icon: Shield
      },
      {
        id: "quality-control",
        name: "Контроль качества",
        description: "Проверка качества перед отправкой",
        price: 6800,
        icon: CheckCircle
      }
    ]
  },
  {
    title: "Упаковка и обработка",
    description: "Подготовка товара к транспортировке",
    items: [
      {
        id: "premium-packaging",
        name: "Премиум упаковка",
        description: "Усиленная упаковка для хрупких товаров",
        price: 3200,
        icon: Gift
      },
      {
        id: "labeling",
        name: "Маркировка",
        description: "Нанесение штрих-кодов и этикеток",
        price: 1500,
        icon: FileText
      }
    ]
  },
  {
    title: "Дополнительные услуги",
    description: "Консультации и расчеты",
    items: [
      {
        id: "customs-clearance",
        name: "Таможенное оформление",
        description: "Полное таможенное сопровождение",
        price: 15000,
        popular: true,
        icon: FileText
      },
      {
        id: "cost-calculation",
        name: "Расчет стоимости",
        description: "Подробный расчет всех затрат",
        price: 2000,
        icon: Calculator
      }
    ]
  }
];

const ServicesCatalog = () => {
  const handleServiceSelect = (service: ServiceItem) => {
    // Здесь будет логика добавления услуги к заказу
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('ru-RU').format(price) + ' ₽';
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-8">
      {/* Заголовок */}
      <div className="text-center mb-12">
        <h2 className="text-3xl font-bold text-white mb-4">Каталог услуг</h2>
        <p className="text-gray-300 text-lg max-w-2xl mx-auto">
          Выберите дополнительные услуги для вашего заказа. Все услуги выполняются нашими проверенными партнерами.
        </p>
      </div>

      {/* Категории услуг */}
      <div className="space-y-12">
        {serviceCategories.map((category, categoryIndex) => (
          <div key={categoryIndex} className="space-y-6">
            {/* Заголовок категории */}
            <div className="text-center">
              <h3 className="text-2xl font-bold text-white mb-2">{category.title}</h3>
              <p className="text-gray-400">{category.description}</p>
            </div>

            {/* Услуги в категории */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {category.items.map((service) => {
                const IconComponent = service.icon;
                
                return (
                  <Card 
                    key={service.id}
                    className="bg-medium-gray border-white/10 hover:border-white/20 hover:-translate-y-1 transition-all duration-300 cursor-pointer group"
                    onClick={() => handleServiceSelect(service)}
                  >
                    <div className="p-6 space-y-4">
                      {/* Header с иконкой и бейджами */}
                      <div className="flex items-start justify-between">
                        <div className="w-12 h-12 bg-accent-red/20 border border-accent-red/30 rounded-xl flex items-center justify-center group-hover:bg-accent-red/30 transition-all duration-300">
                          <IconComponent size={24} className="text-accent-red" />
                        </div>
                        
                        {service.popular && (
                          <Badge className="bg-accent-red/20 text-accent-red border-accent-red/30 text-xs">
                            Популярно
                          </Badge>
                        )}
                      </div>

                      {/* Название и описание */}
                      <div className="space-y-2">
                        <h4 className="text-lg font-semibold text-white group-hover:text-accent-red transition-colors duration-300">
                          {service.name}
                        </h4>
                        <p className="text-gray-400 text-sm leading-relaxed">
                          {service.description}
                        </p>
                      </div>

                      {/* Детали */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-2xl font-bold text-white">
                            {formatPrice(service.price)}
                          </span>
                          {service.duration && (
                            <span className="text-sm text-gray-400">
                              {service.duration}
                            </span>
                          )}
                        </div>
                        
                        <Button 
                          className="w-full bg-accent-red/10 hover:bg-accent-red hover:text-white text-accent-red border border-accent-red/30 transition-all duration-300"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleServiceSelect(service);
                          }}
                        >
                          Добавить к заказу
                        </Button>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="text-center pt-8 border-t border-white/10">
        <p className="text-gray-400">
          Не нашли нужную услугу? <button className="text-accent-red hover:underline">Свяжитесь с нами</button> для индивидуального предложения.
        </p>
      </div>
    </div>
  );
};

export default ServicesCatalog;