
import { Check, Rocket, Clock, Shield, TrendingUp } from "lucide-react";

const FinancingSolution = () => {
  return (
    <section id="solution" className="px-6 lg:px-12 bg-dark-gray border-t border-light-gray/20 py-[85px]">
      <div className="max-w-7xl mx-auto">
        {/* Заголовок секции */}
        <div className="text-center mb-16">
          <div className="w-20 h-1 bg-accent-red mx-auto mb-8"></div>
          <div className="flex items-center justify-center mb-8">
            <h2 className="text-5xl lg:text-6xl font-black text-white animate-fade-in">
              Мы предлагаем <span className="text-accent-red">решение</span>
            </h2>
          </div>
          <p className="text-xl text-gray-300 max-w-3xl mx-auto leading-relaxed animate-fade-in">Простой и быстрый способ масштабировать ваш бизнес</p>
        </div>

        {/* Процесс - 3 карточки */}
        <div className="grid lg:grid-cols-3 gap-8 mb-16">
          {/* Карточка 1 */}
          <div className="group bg-gradient-to-br from-light-gray/40 to-medium-gray/40 backdrop-blur-xl p-8 rounded-3xl border border-accent-red/20 transition-all duration-500 hover:border-white/25 hover:-translate-y-1 hover:bg-gradient-to-br hover:from-light-gray/60 hover:to-medium-gray/60">
            <div className="flex items-center justify-center mb-6">
              <div className="w-12 h-12 bg-accent-red rounded-full flex items-center justify-center text-white font-black text-xl group-hover:scale-110 transition-transform duration-300">
                1
              </div>
            </div>
            <h3 className="text-2xl font-bold text-white mb-4 group-hover:text-accent-red transition-colors">Подаете простую заявку за 2 минуты</h3>
            <p className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Мы проверяем вашу компанию и утверждаем условия финансирования</p>
          </div>

          {/* Карточка 2 */}
          <div className="group bg-gradient-to-br from-light-gray/40 to-medium-gray/40 backdrop-blur-xl p-8 rounded-3xl border border-accent-red/20 transition-all duration-500 hover:border-white/25 hover:-translate-y-1 hover:bg-gradient-to-br hover:from-light-gray/60 hover:to-medium-gray/60">
            <div className="flex items-center justify-center mb-6">
              <div className="w-12 h-12 bg-accent-red rounded-full flex items-center justify-center text-white font-black text-xl group-hover:scale-110 transition-transform duration-300">
                2
              </div>
            </div>
            <h3 className="text-2xl font-bold text-white mb-4 group-hover:text-accent-red transition-colors">Мы оплачиваем до 100% стоимости товара</h3>
            <p className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">В соответствии с утверждёнными условиями финансирования</p>
          </div>

          {/* Карточка 3 */}
          <div className="group bg-gradient-to-br from-light-gray/40 to-medium-gray/40 backdrop-blur-xl p-8 rounded-3xl border border-accent-red/20 transition-all duration-500 hover:border-white/25 hover:-translate-y-1 hover:bg-gradient-to-br hover:from-light-gray/60 hover:to-medium-gray/60">
            <div className="flex items-center justify-center mb-6">
              <div className="w-12 h-12 bg-accent-red rounded-full flex items-center justify-center text-white font-black text-xl group-hover:scale-110 transition-transform duration-300">
                3
              </div>
            </div>
            <h3 className="text-2xl font-bold text-white mb-4 group-hover:text-accent-red transition-colors">Вы оплачиваете груз когда он фактически прибыл</h3>
            <p className="text-gray-300 leading-relaxed group-hover:text-white transition-colors">Оплата осуществляется после фактической отгрузки товара</p>
          </div>
        </div>
      </div>
    </section>
  );
};

export default FinancingSolution;
