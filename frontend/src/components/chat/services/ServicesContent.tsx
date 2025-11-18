import React from 'react';
import { GlassCard } from '@/components/design-system/GlassCard';
import { Search, ShoppingCart, CreditCard, Landmark, Truck, Package, Wrench, Shield, Home, Users } from 'lucide-react';

const ServicesContent = () => {
  const serviceCategories = [
    {
      title: "Поиск и закупка товара",
      icon: Search,
      services: [
        {
          icon: Search,
          title: "Поиск товара",
          description: "Найдем нужный товар по вашим критериям",
          price: "от 5,000 ₽"
        },
        {
          icon: ShoppingCart,
          title: "Выкуп товара",
          description: "Покупка товара у поставщика",
          price: "3% от суммы"
        }
      ]
    },
    {
      title: "Финансовые услуги",
      icon: CreditCard,
      services: [
        {
          icon: CreditCard,
          title: "Оплата товара",
          description: "Оплата поставщику от вашего имени",
          price: "1% от суммы"
        },
        {
          icon: Landmark,
          title: "Финансирование",
          description: "Отсрочка платежа до 90 дней",
          price: "от 0.5% в день"
        }
      ]
    },
    {
      title: "Логистические услуги",
      icon: Truck,
      services: [
        {
          icon: Package,
          title: "Забор товара у поставщика",
          description: "Организуем забор товара со склада поставщика",
          price: "от 3,000 ₽"
        },
        {
          icon: Wrench,
          title: "Складская обработка",
          description: "Прием, проверка и подготовка к отправке",
          price: "150 ₽/кг"
        },
        {
          icon: Package,
          title: "Обрешётка",
          description: "Дополнительная упаковка для защиты",
          price: "от 2,000 ₽"
        },
        {
          icon: Shield,
          title: "Страховка",
          description: "Страхование груза на время перевозки",
          price: "0.5% от стоимости"
        }
      ]
    },
    {
      title: "Последняя миля",
      icon: Home,
      services: [
        {
          icon: Package,
          title: "Фулфилмент",
          description: "Полный цикл обработки заказов",
          price: "от 200 ₽/заказ"
        },
        {
          icon: Truck,
          title: "Доставка",
          description: "Доставка до двери получателя",
          price: "от 300 ₽"
        },
        {
          icon: Home,
          title: "Самовывоз",
          description: "Выдача с пункта самовывоза",
          price: "от 100 ₽"
        }
      ]
    }
  ];

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
          <Wrench size={20} className="text-accent-red" />
          Каталог услуг
        </h3>
        
        <div className="space-y-6">
          {serviceCategories.map((category, categoryIndex) => {
            const CategoryIcon = category.icon;
            
            return (
              <div key={categoryIndex}>
                <div className="flex items-center gap-2 mb-4">
                  <CategoryIcon size={18} className="text-accent-red" />
                  <h4 className="text-white font-medium">{category.title}</h4>
                </div>
                
                <div className="space-y-3">
                  {category.services.map((service, serviceIndex) => {
                    const ServiceIcon = service.icon;
                    
                    return (
                      <GlassCard key={serviceIndex} variant="default" className="p-4 hover:bg-white/5 transition-colors cursor-pointer">
                        <div className="flex items-start gap-3">
                          <div className="w-10 h-10 rounded-lg bg-accent-gray/20 flex items-center justify-center flex-shrink-0">
                            <ServiceIcon size={18} className="text-accent-gray" />
                          </div>
                          
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex-1">
                                <h5 className="text-white font-medium text-sm mb-1">{service.title}</h5>
                                <p className="text-gray-400 text-xs leading-relaxed">{service.description}</p>
                              </div>
                              <div className="text-right flex-shrink-0">
                                <span className="text-accent-green text-xs font-medium">{service.price}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </GlassCard>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
        
        <div className="mt-6 pt-4 border-t border-white/10">
          <p className="text-gray-400 text-xs text-center">
            Цены указаны ориентировочно. Точная стоимость рассчитывается индивидуально.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ServicesContent;