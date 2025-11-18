import { useStaggeredInView } from '@/hooks/useStaggeredInView';
import { Target, ShoppingCart, DollarSign, CreditCard, Truck, ClipboardCheck, TrendingUp } from 'lucide-react';
import { Button } from '@/components/ui/button';

const RoadmapSection = () => {
  const roadmapSteps = [
    {
      id: 1,
      icon: Target,
      title: "Что продавать?",
      description: "Анализ рынка, поиск востребованных товаров и ниш. Исследование конкурентов и определение уникального торгового предложения.",
      side: "left" as const
    },
    {
      id: 2,
      icon: ShoppingCart,
      title: "Где купить?",
      description: "Поиск надежных поставщиков, заводов-производителей. Налаживание прямых контактов с производителями и оптовыми компаниями.",
      side: "right" as const
    },
    {
      id: 3,
      icon: DollarSign,
      title: "Где взять деньги?",
      description: "Финансирование закупок, кредитование торговых операций, факторинг. Получение оборотных средств для развития бизнеса.",
      side: "left" as const
    },
    {
      id: 4,
      icon: CreditCard,
      title: "Как оплатить?",
      description: "Организация международных платежей, валютное законодательство, аккредитивы. Безопасные способы расчетов с поставщиками.",
      side: "right" as const
    },
    {
      id: 5,
      icon: Truck,
      title: "Как привезти?",
      description: "Логистика и доставка товаров, выбор транспортных компаний, страхование грузов. Оптимизация логистических расходов.",
      side: "left" as const
    },
    {
      id: 6,
      icon: ClipboardCheck,
      title: "Как растаможить?",
      description: "Таможенное оформление, декларирование товаров, расчет пошлин и налогов. Сопровождение всех таможенных процедур.",
      side: "right" as const
    },
    {
      id: 7,
      icon: TrendingUp,
      title: "Как быстро продать?",
      description: "Маркетинговые стратегии, поиск покупателей, ценообразование. Быстрое продвижение товаров и увеличение оборачиваемости.",
      side: "left" as const
    }
  ];

  const { visibleItems, setRef } = useStaggeredInView(roadmapSteps.length, {
    threshold: 0.05,
    rootMargin: '100px',
    debounceMs: 50
  });

  return (
    <section className="py-20 bg-[#1a1a1d] relative overflow-hidden">
      <div className="max-w-6xl mx-auto px-6 lg:px-12">
        {/* Section Header */}
        <div className="text-center mb-20">
          <h2 className="text-4xl lg:text-5xl font-black text-white mb-6">
            Дорожная Карта{' '}
            <span className="text-accent-red">Вашего Бизнеса</span>
          </h2>
          <p className="text-xl text-gray-300 max-w-4xl mx-auto leading-relaxed">
            WellWon - это сервис, который поддерживает Ваш бизнес на каждом этапе
          </p>
        </div>

        {/* Roadmap Steps */}
        <div className="relative max-w-5xl mx-auto">
          {/* Desktop Layout */}
          <div className="hidden lg:block">
            {roadmapSteps.map((step, index) => {
              const Icon = step.icon;
              const isVisible = visibleItems[index];
              
              return (
                <div
                  key={step.id}
                  ref={setRef(index)}
                  className={`relative mb-24 flex items-center min-h-[100px] transition-all duration-700 ease-out ${
                    isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
                  }`}
                  style={{
                    justifyContent: step.side === 'left' ? 'flex-end' : 'flex-start',
                    paddingRight: step.side === 'left' ? 'calc(50% + 40px)' : '0',
                    paddingLeft: step.side === 'right' ? 'calc(50% + 40px)' : '0'
                  }}
                >
                  {/* Beautiful Step Number - для левых карточек СЛЕВА от карточки (со стороны линии) */}
                  {step.side === 'left' && (
                    <div
                      className={`absolute transition-all duration-700 ease-out ${
                        isVisible ? 'opacity-100 scale-100 rotate-0' : 'opacity-0 scale-50 rotate-45'
                      }`}
                      style={{
                        left: '-80px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        transitionDelay: isVisible ? '1800ms' : '0ms'
                      }}
                    >
                      <div className="w-20 h-20 bg-gradient-to-br from-accent-red/20 to-accent-red/5 border border-accent-red/30 rounded-2xl flex items-center justify-center backdrop-blur-sm">
                        <span className="text-4xl font-black text-accent-red">{step.id}</span>
                      </div>
                    </div>
                  )}

                  {/* Beautiful Step Number - для правых карточек СПРАВА от карточки (со стороны линии) */}
                  {step.side === 'right' && (
                    <div
                      className={`absolute transition-all duration-700 ease-out ${
                        isVisible ? 'opacity-100 scale-100 rotate-0' : 'opacity-0 scale-50 rotate-45'
                      }`}
                      style={{
                        right: '-80px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        transitionDelay: isVisible ? '1800ms' : '0ms'
                      }}
                    >
                      <div className="w-20 h-20 bg-gradient-to-br from-accent-red/20 to-accent-red/5 border border-accent-red/30 rounded-2xl flex items-center justify-center backdrop-blur-sm">
                        <span className="text-4xl font-black text-accent-red">{step.id}</span>
                      </div>
                    </div>
                  )}

                  {/* Connection Line - теперь для всех карточек */}
                  <div
                    className={`absolute h-1 z-10 transition-all duration-1500 ease-out ${
                      isVisible ? 'animate-draw-line-left opacity-100' : 'opacity-0'
                    } ${
                      step.side === 'left'
                        ? 'bg-gradient-to-l from-transparent via-accent-red to-accent-red'
                        : 'bg-gradient-to-r from-transparent via-accent-red to-accent-red'
                    }`}
                    style={{
                      top: '50%',
                      transform: 'translateY(-50%)',
                      transformOrigin: step.side === 'left' ? 'right center' : 'left center',
                      [step.side === 'left' ? 'right' : 'left']: '-20px',
                      width: 'calc(50% + 40px)',
                      transitionDelay: isVisible ? '300ms' : '0ms',
                      animationDelay: isVisible ? '300ms' : '0ms'
                    }}
                  />

                  {/* Step Card */}
                  <div className="group relative max-w-sm w-full">
                    <div className="bg-gradient-to-br from-white/10 to-white/5 backdrop-blur-xl border border-accent-red/20 rounded-2xl p-8 transition-all duration-300 hover:bg-gradient-to-br hover:from-white/15 hover:to-white/8 hover:border-white/25 hover:-translate-y-2 hover:shadow-2xl hover:shadow-black/20">
                      {/* Connection Point */}
                      <div
                        className={`absolute w-3 h-3 bg-accent-red rounded-full border-2 border-dark-gray shadow-lg transition-all duration-500 ${
                          isVisible ? 'scale-100 opacity-100' : 'scale-0 opacity-0'
                        } ${step.side === 'left' ? '-right-1.5' : '-left-1.5'}`}
                        style={{
                          top: '50%',
                          transform: 'translateY(-50%)',
                          transitionDelay: isVisible ? '100ms' : '0ms'
                        }}
                      />

                      {/* Icon */}
                      <div className="w-12 h-12 bg-gradient-to-br from-accent-red to-accent-red/80 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300 shadow-lg shadow-accent-red/40">
                        <Icon className="w-6 h-6 text-white" />
                      </div>

                      {/* Content */}
                      <h3 className="text-2xl font-bold text-white mb-4">{step.title}</h3>
                      <p className="text-gray-300 mb-6 leading-relaxed">{step.description}</p>
                      
                      <Button className="bg-accent-red hover:bg-accent-red/90 text-white px-6 py-2 rounded-full transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:shadow-accent-red/30">
                        Подробнее
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Mobile Layout */}
          <div className="lg:hidden space-y-12">
            {roadmapSteps.map((step, index) => {
              const Icon = step.icon;
              const isVisible = visibleItems[index];
              
              return (
                <div
                  key={step.id}
                  ref={setRef(index)}
                  className={`relative transition-all duration-700 ease-out ${
                    isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
                  }`}
                >
                  {/* Vertical Connection Line - оставляем условие для мобильной версии */}
                  {index < roadmapSteps.length - 1 && (
                    <div
                      className={`absolute left-6 top-24 w-1 h-12 bg-gradient-to-b from-accent-red to-transparent rounded-full transition-all duration-1200 ease-out ${
                        isVisible ? 'animate-draw-line-mobile opacity-80' : 'opacity-0'
                      }`}
                      style={{
                        transformOrigin: 'top center',
                        transitionDelay: isVisible ? '300ms' : '0ms',
                        animationDelay: isVisible ? '300ms' : '0ms'
                      }}
                    />
                  )}

                  {/* Step Card */}
                  <div className="flex items-start space-x-6">
                    {/* Step Number Circle */}
                    <div
                      className={`flex-shrink-0 w-12 h-12 bg-accent-red rounded-full flex items-center justify-center text-white font-bold text-lg transition-all duration-500 ${
                        isVisible ? 'scale-100 opacity-100' : 'scale-0 opacity-0'
                      }`}
                    >
                      {step.id}
                    </div>

                    {/* Card Content */}
                    <div className="flex-1 bg-gradient-to-br from-white/10 to-white/5 backdrop-blur-xl border border-accent-red/20 rounded-2xl p-6 hover:bg-gradient-to-br hover:from-white/15 hover:to-white/8 hover:border-white/25 hover:-translate-y-1 transition-all duration-300">
                      <div className="flex items-center space-x-4 mb-4">
                        <div className="w-10 h-10 bg-gradient-to-br from-accent-red to-accent-red/80 rounded-lg flex items-center justify-center">
                          <Icon className="w-5 h-5 text-white" />
                        </div>
                        <h3 className="text-xl font-bold text-white">{step.title}</h3>
                      </div>
                      
                      <p className="text-gray-300 mb-4 leading-relaxed">{step.description}</p>
                      
                      <Button className="bg-accent-red hover:bg-accent-red/90 text-white px-4 py-2 rounded-full text-sm transition-all duration-300">
                        Подробнее
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
};

export default RoadmapSection;
