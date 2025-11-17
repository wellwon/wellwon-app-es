import { memo } from 'react';
import { BarChart3, TrendingUp, Search, Truck, Package, Warehouse, ShoppingCart, DollarSign, Zap, ShoppingBag } from "lucide-react";
import { Button } from "@/components/ui/button";

const ServicesGrid = memo(() => {
  const serviceCategories = [{
    id: 'analytics',
    title: 'Аналитика',
    icon: BarChart3,
    iconBg: 'bg-green-500',
    services: [{
      title: 'Товарные тренды',
      description: 'Анализ рыночных тенденций и прогнозирование спроса'
    }, {
      title: 'Поиск поставщиков',
      description: 'Профессиональный поиск и верификация поставщиков'
    }, {
      title: 'Контроль и отчёты',
      description: 'Мониторинг качества и детальная отчетность'
    }]
  }, {
    id: 'logistics',
    title: 'Логистика',
    icon: Truck,
    iconBg: 'bg-blue-500',
    services: [{
      title: '"Белое карго" с документами',
      description: 'Официальная доставка с полным пакетом документов'
    }, {
      title: '"Быстрое карго"',
      description: 'Экспресс-доставка для срочных грузов'
    }, {
      title: 'Складские услуги',
      description: 'Хранение и управление товарными запасами'
    }, {
      title: 'Фулфилмент',
      description: 'Полный цикл обработки и отправки заказов'
    }]
  }, {
    id: 'finance',
    title: 'Финансы',
    icon: DollarSign,
    iconBg: 'bg-purple-500',
    services: [{
      title: 'Финансирование',
      description: 'Кредитование и инвестиционная поддержка'
    }, {
      title: 'Экспресс платежи',
      description: 'Мгновенные денежные переводы и операции'
    }]
  }];
  return <section className="py-24 px-6 lg:px-12 bg-gradient-to-b from-medium-gray to-dark-gray">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <div className="w-20 h-1 bg-accent-red mx-auto mb-8"></div>
          <h2 className="text-5xl lg:text-6xl text-white mb-6 font-extrabold">
            Наши <span className="font-black text-accent-red">Услуги</span>
          </h2>
          <p className="text-xl text-gray-300 max-w-3xl mx-auto">
            Полный спектр логистических и торговых решений для вашего бизнеса
          </p>
        </div>

        {/* Services Grid */}
        <div className="grid lg:grid-cols-3 gap-8 mb-16">
          {serviceCategories.map(category => <div key={category.id} className="bg-gradient-to-br from-light-gray/80 to-dark-gray/80 backdrop-blur-sm rounded-3xl border border-white/10 overflow-hidden hover:border-white/20 hover:-translate-y-1 transition-all duration-300 group">
              {/* Category Header */}
              <div className="p-8 border-b border-white/10">
                <div className="flex items-center space-x-4 mb-4">
                  <div className={`w-16 h-16 ${category.iconBg} rounded-2xl flex items-center justify-center group-hover:scale-110 transition-transform duration-300`}>
                    <category.icon className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-2xl font-bold text-white">{category.title}</h3>
                </div>
              </div>

              {/* Services List */}
              <div className="p-8 space-y-6">
                {category.services.map((service, index) => <div key={index} className="group/service">
                    <h4 className="text-lg font-semibold text-white mb-2 group-hover/service:text-accent-red transition-colors">
                      {service.title}
                    </h4>
                    <p className="text-gray-300 text-sm leading-relaxed">
                      {service.description}
                    </p>
                    {index < category.services.length - 1 && <div className="mt-4 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent"></div>}
                  </div>)}
              </div>

              {/* Action Button */}
              
            </div>)}
        </div>

        {/* Bottom CTA */}
        <div className="text-center">
          <div className="bg-gradient-to-r from-accent-red/10 via-accent-red/5 to-accent-red/10 rounded-2xl p-8 border border-accent-red/20">
            <h3 className="text-2xl font-bold text-white mb-4">
              Нужна консультация по услугам?
            </h3>
            <p className="text-gray-300 mb-6 max-w-2xl mx-auto">
              Наши эксперты помогут подобрать оптимальное решение для вашего бизнеса
            </p>
            <Button variant="accent" size="lg" className="px-8">
              Получить консультацию
            </Button>
          </div>
        </div>
      </div>
    </section>;
});

ServicesGrid.displayName = 'ServicesGrid';

export default ServicesGrid;