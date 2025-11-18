
import React from 'react';

const AnimatedCreditCard = () => {
  return (
    <div className="relative">
      <div className="w-96 h-56 lg:w-[440px] lg:h-64 perspective-1000">
        <div className="relative w-full h-full transition-all duration-1000 ease-out transform-style-preserve-3d hover:rotate-y-12 hover:rotate-x-6 hover:scale-105 animate-breathing">
          {/* Основная карта */}
          <div className="absolute inset-0 bg-gradient-to-br from-light-gray via-medium-gray to-dark-gray rounded-2xl shadow-2xl overflow-hidden border border-white/20">
            {/* Фоновый паттерн */}
            <div className="absolute inset-0 opacity-10">
              <div className="absolute top-4 right-4 w-16 h-16 rounded-full bg-accent-red/20"></div>
              <div className="absolute bottom-4 left-4 w-12 h-12 rounded-full bg-white/10"></div>
              <div className="absolute top-1/2 left-1/2 w-32 h-32 rounded-full bg-accent-red/5 transform -translate-x-1/2 -translate-y-1/2"></div>
            </div>
            
            {/* Контент карты */}
            <div className="relative z-10 p-6 h-full flex flex-col justify-between text-white">
              {/* Верхняя часть */}
              <div className="flex justify-between items-start -mt-[15px] py-0">
                <div>
                  <div className="text-xs font-medium opacity-70 mb-1 tracking-wider my-[8px]">ТОВАРНОЕ ФИНАНСИРОВАНИЕ</div>
                </div>
                <div className="text-right">
                  <div className="text-xl font-bold">
                    <span className="text-accent-red">Well</span><span className="text-white">Won</span>
                  </div>
                  <div className="w-12 h-0.5 bg-accent-red mt-1"></div>
                </div>
              </div>
              
              {/* Средняя часть - заголовки в одной строке */}
              <div className="flex justify-between items-start mb-0 my-[15px] py-0">
                <div className="text-xs opacity-70">ID КЛИЕНТА</div>
                <div className="text-xs opacity-70">ЛИМИТ ФИНАНСИРОВАНИЯ</div>
              </div>
              
              {/* Средняя часть - значения */}
              <div className="flex justify-between items-end">
                <div>
                  <div className="text-lg font-black">579</div>
                </div>
                <div className="text-right">
                  <div className="text-3xl lg:text-3xl font-black">150 000 $</div>
                </div>
              </div>
              
              {/* Разделительная линия */}
              <div className="w-full h-px bg-white/20 my-1"></div>
              
              {/* Нижняя часть */}
              <div className="flex justify-between items-end text-sm mt-1 py-0 my-0">
                <div>
                  <div className="text-xs opacity-70 mb-1">СТАВКА</div>
                  <div className="font-bold text-lg">1%</div>
                </div>
                <div className="text-center">
                  <div className="text-xs opacity-70 mb-1">ПРЕДОПЛАТА</div>
                  <div className="font-bold text-lg">0%</div>
                </div>
                <div className="text-right">
                  <div className="text-xs opacity-70 mb-1">ДЕЙСТВУЕТ ДО</div>
                  <div className="font-bold text-lg">12/26</div>
                </div>
              </div>
            </div>
            
            {/* Блик при наведении */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent transform -translate-x-full transition-transform duration-1000 hover:translate-x-full"></div>
          </div>
          
          {/* Световой эффект подсветки с плавной пульсацией */}
          <div className="absolute inset-0 bg-gradient-radial from-accent-red/30 via-accent-red/10 to-transparent rounded-2xl blur-2xl scale-110 opacity-0 transition-all duration-1000 ease-in-out hover:opacity-80 hover:scale-125 hover:animate-smooth-glow"></div>
        </div>
      </div>
    </div>
  );
};

export default AnimatedCreditCard;
