import { Zap, Timer, Gift } from "lucide-react";
import { useState, useEffect } from "react";
import { Loader } from '@/components/ui/loader';
const FinancingCTA = () => {
  const [timeLeft, setTimeLeft] = useState(30 * 60); // 30 минут в секундах
  const [isLoading, setIsLoading] = useState(true);
  useEffect(() => {
    // Инициализация компонента
    setIsLoading(false);

    // Исправленный таймер без зависимости от timeLeft
    const intervalId = setInterval(() => {
      setTimeLeft(prevTime => {
        if (prevTime <= 1) {
          clearInterval(intervalId);
          return 0;
        }
        return prevTime - 1;
      });
    }, 1000);
    return () => clearInterval(intervalId);
  }, []); // Пустой массив зависимостей - эффект выполняется только один раз

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
  };
  if (isLoading) {
    return (
      <section className="py-32 px-6 lg:px-12 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-accent-red via-accent-red to-accent-red-dark"></div>
        <div className="max-w-5xl mx-auto text-center relative z-10">
          <Loader size="lg" text="Загрузка предложения..." variant="spinner" />
        </div>
      </section>
    );
  }
  return <section className="py-32 px-6 lg:px-12 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-r from-accent-red via-accent-red to-accent-red-dark"></div>
      <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-transparent via-black/10 to-black/30"></div>
      
      {/* Оптимизированные анимированные элементы */}
      <div className="absolute top-20 right-20 w-32 h-32 border-2 border-white/20 rounded-3xl rotate-45 animate-pulse will-change-transform"></div>
      <div className="absolute bottom-20 left-20 w-24 h-24 border border-white/10 rounded-full animate-bounce will-change-transform" style={{
      animationDelay: '1s'
    }}></div>
      <div className="absolute top-1/2 right-1/4 w-16 h-16 bg-white/10 rounded-2xl animate-pulse will-change-auto" style={{
      animationDelay: '2s'
    }}></div>
      
      <div className="max-w-5xl mx-auto text-center relative z-10">
        {/* Заголовок */}
        <div className="animate-fade-in mb-16">
          <h2 className="text-6xl lg:text-7xl font-black text-white mb-4 leading-tight">
            Готовы к прорыву?
            <div className="inline-block ml-4">
              <Zap className="w-12 h-12 text-white animate-pulse" />
            </div>
          </h2>
        </div>

        {/* Купон */}
        <div className="animate-fade-in" style={{
        animationDelay: '0.3s'
      }}>
          {/* Стилизованный купон */}
          <div className="relative bg-white rounded-3xl p-12 max-w-4xl mx-auto shadow-2xl overflow-hidden">
            {/* Декоративные вырезы по бокам */}
            <div className="absolute left-0 top-1/2 transform -translate-y-1/2 w-8 h-16 bg-accent-red rounded-r-full"></div>
            <div className="absolute right-0 top-1/2 transform -translate-y-1/2 w-8 h-16 bg-accent-red rounded-l-full"></div>
            
            {/* Пунктирная линия по центру */}
            <div className="absolute left-8 right-8 top-1/2 transform -translate-y-1/2 border-t-2 border-dashed border-gray-300"></div>
            
            {/* Верхняя часть купона */}
            <div className="pb-8">
              {/* Иконка и заголовок */}
              <div className="flex items-center justify-center gap-4 mb-6">
                <Gift className="w-10 h-10 text-accent-red" />
                <h3 className="text-3xl lg:text-4xl font-black text-dark-gray">Дарим на первую сделку</h3>
              </div>
              
              {/* Основное предложение */}
              <div className="mb-6">
                <div className="text-8xl lg:text-9xl font-black text-accent-red mb-2">
                  100$
                </div>
                <div className="text-2xl lg:text-3xl font-bold text-dark-gray mb-4">
              </div>
                <div className="text-dark-gray/80 text-xl lg:text-2xl max-w-3xl mx-auto">Сниженный % и минимальная ставка на услуги </div>
              </div>
            </div>
            
            {/* Нижняя часть купона */}
            <div className="pt-8">
              {/* Таймер */}
              <div className="bg-accent-red/10 backdrop-blur-sm rounded-2xl p-6 mb-6 py-[36px]">
                <div className="flex items-center justify-center gap-3 mb-4">
                  <Timer className="w-6 h-6 text-accent-red" />
                  <div className="text-dark-gray/80 text-lg lg:text-xl">
                    Предложение действует:
                  </div>
                </div>
                <div className="text-6xl lg:text-7xl font-black text-accent-red tracking-wider">
                  {formatTime(timeLeft)}
                </div>
              </div>
              
              {/* Условия */}
              
            </div>
          </div>
        </div>
      </div>
    </section>;
};
export default FinancingCTA;