import React from 'react';
import { TrendingUp, TrendingDown, ArrowUpRight } from 'lucide-react';
import { GlassCard } from '@/components/design-system';

const ProductTrendsContent = () => {
  const trends = [
    {
      category: 'Электроника',
      growth: '+15.2%',
      trend: 'up',
      volume: '₽2.4M',
      items: ['Смартфоны', 'Ноутбуки', 'Наушники']
    },
    {
      category: 'Одежда и обувь',
      growth: '+8.7%',
      trend: 'up',
      volume: '₽1.8M',
      items: ['Зимняя одежда', 'Спортивная обувь', 'Аксессуары']
    },
    {
      category: 'Товары для дома',
      growth: '-3.1%',
      trend: 'down',
      volume: '₽950K',
      items: ['Мебель', 'Текстиль', 'Декор']
    },
    {
      category: 'Автотовары',
      growth: '+22.4%',
      trend: 'up',
      volume: '₽3.2M',
      items: ['Шины', 'Автозапчасти', 'Аксессуары']
    }
  ];

  return (
    <div className="h-full bg-dark-gray p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white mb-2">Товарные тренды</h1>
          <p className="text-gray-400">Анализ популярности и роста товарных категорий</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {trends.map((trend, index) => (
          <GlassCard key={index} className="p-6 hover:bg-white/5 transition-colors">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">{trend.category}</h3>
              <div className={`flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium ${
                trend.trend === 'up' 
                  ? 'bg-green-500/20 text-green-400' 
                  : 'bg-red-500/20 text-red-400'
              }`}>
                {trend.trend === 'up' ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {trend.growth}
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Оборот за месяц</span>
                <span className="text-xl font-bold text-white">{trend.volume}</span>
              </div>

              <div>
                <p className="text-gray-400 text-sm mb-2">Популярные товары:</p>
                <div className="flex flex-wrap gap-2">
                  {trend.items.map((item, idx) => (
                    <span key={idx} className="bg-white/10 text-gray-300 px-2 py-1 rounded-lg text-xs">
                      {item}
                    </span>
                  ))}
                </div>
              </div>

              <button className="w-full flex items-center justify-center gap-2 bg-white/10 hover:bg-white/20 text-white py-2 rounded-lg transition-colors">
                Подробная аналитика
                <ArrowUpRight size={16} />
              </button>
            </div>
          </GlassCard>
        ))}
      </div>

      <GlassCard className="p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Рекомендации по закупкам</h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between p-3 bg-green-500/10 rounded-lg">
            <div>
              <p className="text-green-400 font-medium">Увеличить закупки автотоваров</p>
              <p className="text-gray-400 text-sm">Рост на 22.4%, высокий спрос</p>
            </div>
            <TrendingUp className="text-green-400" size={20} />
          </div>
          <div className="flex items-center justify-between p-3 bg-accent-red/10 rounded-lg border border-accent-red/20">
            <div>
              <p className="text-accent-red font-medium">Планировать сезонные товары</p>
              <p className="text-gray-400 text-sm">Подготовка к весенне-летнему сезону</p>
            </div>
            <ArrowUpRight className="text-accent-red" size={20} />
          </div>
        </div>
      </GlassCard>
    </div>
  );
};

export default ProductTrendsContent;