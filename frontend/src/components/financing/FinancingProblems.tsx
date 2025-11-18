
import { X, AlertTriangle, Clock, DollarSign, Users } from "lucide-react";

const FinancingProblems = () => {
  return (
    <section id="problems" className="px-6 lg:px-12 bg-medium-gray border-t border-light-gray/20 py-[55px]">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <div className="w-20 h-1 bg-accent-red mx-auto mb-8"></div>
          <h2 className="text-5xl lg:text-6xl font-black mb-8 text-white animate-fade-in">
            Узнаете эти <span className="text-accent-red">проблемы?</span>
          </h2>
          
          <p className="text-xl text-gray-300 max-w-3xl mx-auto leading-relaxed animate-fade-in">Ваш бизнес может развиваться быстрее, если убрать эти препятствия</p>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          {/* Финансовые боли */}
          <div className="group bg-gradient-to-br from-light-gray/30 to-dark-gray/30 backdrop-blur-xl p-8 rounded-3xl border border-accent-red/20 transition-all duration-500 hover:border-accent-red/50 hover:scale-[1.02] hover:bg-gradient-to-br hover:from-light-gray/50 hover:to-dark-gray/50">
            <div className="flex items-center mb-8">
              <div className="w-16 h-16 bg-accent-red/20 rounded-2xl flex items-center justify-center mr-6 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                <DollarSign className="w-8 h-8 text-accent-red group-hover:text-white transition-colors" />
              </div>
              <h3 className="text-2xl font-bold text-white group-hover:text-accent-red transition-colors">
                Финансовые боли
              </h3>
            </div>
            
            <div className="space-y-4">
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300">
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Маркетплейсы задерживают выплаты</span>
              </div>
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300" style={{
              transitionDelay: '50ms'
            }}>
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Возникают кассовые разрывы</span>
              </div>
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300" style={{
              transitionDelay: '100ms'
            }}>
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Банки отказывают в выдаче кредитов</span>
              </div>
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300" style={{
              transitionDelay: '150ms'
            }}>
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Требуют справки и залоги</span>
              </div>
            </div>
          </div>

          {/* Проблемы с поставщиками */}
          <div className="group bg-gradient-to-br from-light-gray/30 to-dark-gray/30 backdrop-blur-xl p-8 rounded-3xl border border-accent-red/20 transition-all duration-500 hover:border-accent-red/50 hover:scale-[1.02] hover:bg-gradient-to-br hover:from-light-gray/50 hover:to-dark-gray/50">
            <div className="flex items-center mb-8">
              <div className="w-16 h-16 bg-accent-red/20 rounded-2xl flex items-center justify-center mr-6 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                <Users className="w-8 h-8 text-accent-red group-hover:text-white transition-colors" />
              </div>
              <h3 className="text-2xl font-bold text-white group-hover:text-accent-red transition-colors">
                Проблемы с поставщиками
              </h3>
            </div>
            
            <div className="space-y-4">
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300">
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Товар готов к отгрузке, а денег на оплату нет</span>
              </div>
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300" style={{
              transitionDelay: '50ms'
            }}>
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Товары отправляются не вовремя</span>
              </div>
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300" style={{
              transitionDelay: '100ms'
            }}>
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Упускаются выгодные возможности и тренды</span>
              </div>
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300" style={{
              transitionDelay: '150ms'
            }}>
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Длительный цикл сделки между закупками</span>
              </div>
            </div>
          </div>

          {/* Замороженные средства */}
          <div className="group bg-gradient-to-br from-light-gray/30 to-dark-gray/30 backdrop-blur-xl p-8 rounded-3xl border border-accent-red/20 transition-all duration-500 hover:border-accent-red/50 hover:scale-[1.02] hover:bg-gradient-to-br hover:from-light-gray/50 hover:to-dark-gray/50">
            <div className="flex items-center mb-8">
              <div className="w-16 h-16 bg-accent-red/20 rounded-2xl flex items-center justify-center mr-6 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                <AlertTriangle className="w-8 h-8 text-accent-red group-hover:text-white transition-colors" />
              </div>
              <h3 className="text-2xl font-bold text-white group-hover:text-accent-red transition-colors">
                Замороженные средства
              </h3>
            </div>
            
            <div className="space-y-4">
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300">
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Деньги заморожены в пути на от 2-6 недель</span>
              </div>
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300" style={{
              transitionDelay: '50ms'
            }}>
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Низкая оборачиваемость капитала</span>
              </div>
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300" style={{
              transitionDelay: '100ms'
            }}>
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Приходится закупать больше, чем нужно</span>
              </div>
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300" style={{
              transitionDelay: '150ms'
            }}>
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Невозможно масштабироваться</span>
              </div>
            </div>
          </div>

          {/* Эмоциональные страхи */}
          <div className="group bg-gradient-to-br from-light-gray/30 to-dark-gray/30 backdrop-blur-xl p-8 rounded-3xl border border-accent-red/20 transition-all duration-500 hover:border-accent-red/50 hover:scale-[1.02] hover:bg-gradient-to-br hover:from-light-gray/50 hover:to-dark-gray/50">
            <div className="flex items-center mb-8">
              <div className="w-16 h-16 bg-accent-red/20 rounded-2xl flex items-center justify-center mr-6 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                <Clock className="w-8 h-8 text-accent-red group-hover:text-white transition-colors" />
              </div>
              <h3 className="text-2xl font-bold text-white group-hover:text-accent-red transition-colors">Потери для бизнеса</h3>
            </div>
            
            <div className="space-y-4">
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300">
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Конкуренты обгоняют, потому что у них есть деньги</span>
              </div>
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300" style={{
              transitionDelay: '50ms'
            }}>
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Скорость и доходность падает</span>
              </div>
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300" style={{
              transitionDelay: '100ms'
            }}>
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Нельзя получить лучшие цены на объеме</span>
              </div>
              <div className="flex items-start group-hover:translate-x-2 transition-transform duration-300" style={{
              transitionDelay: '150ms'
            }}>
                <div className="w-6 h-6 bg-accent-red/80 rounded-full flex items-center justify-center mr-4 mt-0.5 flex-shrink-0 group-hover:bg-accent-red group-hover:scale-110 transition-all duration-300">
                  <X className="w-3 h-3 text-white" />
                </div>
                <span className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Стресс от постоянной нехватки денег в обороте</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default FinancingProblems;
