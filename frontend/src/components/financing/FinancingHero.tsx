
import { Button } from "@/components/ui/button";
import { ArrowRight, DollarSign, Zap, CheckCircle, Percent } from "lucide-react";
import AnimatedCreditCard from "./AnimatedCreditCard";

const FinancingHero = () => {
  const scrollToContacts = () => {
    document.getElementById('contacts')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <section className="pt-32 pb-20 px-6 lg:px-12 relative overflow-hidden bg-gradient-to-br from-dark-gray to-medium-gray">
      <div className="max-w-7xl mx-auto relative z-10">
        <div className="text-center space-y-12">
          <div className="animate-fade-in">
            <div className="inline-flex items-center bg-light-gray/50 backdrop-blur-sm px-6 rounded-full mb-12 border border-accent-red/20 py-[11px] my-0">
              <Zap className="w-5 h-5 text-accent-red mr-2" />
              <span className="text-accent-red font-semibold">Забудьте о кассовых разрывах!</span>
            </div>
            
            <h1 className="text-7xl font-black leading-none mb-3 py-[15px] lg:text-8xl text-white">
              Финансируем до 100%
            </h1>
            <h2 className="text-7xl font-black leading-none mb-16 lg:text-8xl text-accent-red">
              стоимости груза
            </h2>
            
            {/* Секция с анимированной кредитной картой и булетами */}
            <div className="flex flex-col lg:flex-row items-center justify-center gap-12 max-w-6xl mx-auto mb-12">
              {/* Анимированная кредитная карта */}
              <div className="flex-shrink-0">
                <AnimatedCreditCard />
              </div>
              
              {/* Булеты и кнопки справа от карты */}
              <div className="text-2xl text-gray-300 leading-relaxed space-y-6">
                <div className="flex items-start gap-4 text-left">
                  <div className="w-2 h-2 bg-accent-red rounded-full mt-3 flex-shrink-0"></div>
                  <span>Одобрение лимита финансирования без бюрократии</span>
                </div>
                <div className="flex items-start gap-4 text-left">
                  <div className="w-2 h-2 bg-accent-red rounded-full mt-3 flex-shrink-0"></div>
                  <span>Ставка финансирования от 1% без скрытых комиссий</span>
                </div>
                <div className="flex items-start gap-4 text-left">
                  <div className="w-2 h-2 bg-accent-red rounded-full mt-3 flex-shrink-0"></div>
                  <span>Оплата на фабрику «день в день», выгодный курс</span>
                </div>
                
                {/* Кнопки как 4-я строка, выровненная по булетам */}
                <div className="flex flex-col sm:flex-row gap-4 pt-4 ml-6">
                  <Button 
                    variant="accent" 
                    className="text-lg font-normal rounded-full py-[20px] px-[28px]"
                    onClick={scrollToContacts}
                  >
                    Запросить финансирование
                    <ArrowRight className="w-5 h-5 ml-2" />
                  </Button>
                  
                  <Button variant="secondary" className="px-6 py-4 text-base font-medium rounded-full">
                    Как это работает?
                  </Button>
                </div>
              </div>
            </div>
          </div>
          
          <div style={{animationDelay: '0.6s'}} className="grid md:grid-cols-4 gap-8 max-w-5xl mx-auto pt-8 animate-fade-in py-[30px]">
            <div className="bg-gradient-to-br from-light-gray/80 to-dark-gray/80 backdrop-blur-sm rounded-3xl border border-white/10 p-8 hover:border-white/20 hover:-translate-y-1 transition-all duration-300">
              <div className="w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                <DollarSign className="w-16 h-16 text-accent-red stroke-1" />
              </div>
              <h3 className="text-white font-bold text-lg mb-2">До 100%</h3>
              <p className="text-gray-400 text-sm">финансирования</p>
            </div>
            
            <div className="bg-gradient-to-br from-light-gray/80 to-dark-gray/80 backdrop-blur-sm rounded-3xl border border-white/10 p-8 hover:border-white/20 hover:-translate-y-1 transition-all duration-300">
              <div className="w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                <Percent className="w-16 h-16 text-accent-red stroke-1" />
              </div>
              <h3 className="text-white font-bold text-lg mb-2">Ставка от 1%</h3>
              <p className="text-gray-400 text-sm">стоимости сделки</p>
            </div>
            
            <div className="bg-gradient-to-br from-light-gray/80 to-dark-gray/80 backdrop-blur-sm rounded-3xl border border-white/10 p-8 hover:border-white/20 hover:-translate-y-1 transition-all duration-300">
              <div className="w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                <Zap className="w-16 h-16 text-accent-red stroke-1" />
              </div>
              <h3 className="text-white font-bold text-lg mb-2">Деньги на товар</h3>
              <p className="text-gray-400 text-sm">день в день</p>
            </div>
            
            <div className="bg-gradient-to-br from-light-gray/80 to-dark-gray/80 backdrop-blur-sm rounded-3xl border border-white/10 p-8 hover:border-white/20 hover:-translate-y-1 transition-all duration-300">
              <div className="w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                <CheckCircle className="w-16 h-16 text-accent-red stroke-1" />
              </div>
              <h3 className="text-white font-bold text-lg mb-2">Одобрение</h3>
              <p className="text-gray-400 text-sm">без бюрократии</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default FinancingHero;
