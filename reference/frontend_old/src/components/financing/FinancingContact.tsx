import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useUTMContext } from "@/contexts/UTMContext";
import { generateTelegramBotLink } from "@/utils/telegramUtils";
import { MessageCircle, Mail, Phone } from "lucide-react";
import { useState, useEffect } from "react";
import QRCode from "qrcode";
import { logger } from '@/utils/logger';

const FinancingContact = () => {
  const { utmParams } = useUTMContext();
  const [qrCodeUrl, setQrCodeUrl] = useState<string>("");
  
  const telegramLink = generateTelegramBotLink({
    utmParams,
    pageSource: 'financing',
    customMessage: 'Здравствуйте! Интересует финансирование торговых операций'
  });

  // Генерируем QR код при изменении UTM параметров
  useEffect(() => {
    const generateQR = async () => {
      try {
        const qrUrl = await QRCode.toDataURL(telegramLink, {
          width: 180,
          margin: 1,
          color: {
            dark: '#ea3857',
            light: '#ffffff'
          }
        });
        setQrCodeUrl(qrUrl);
      } catch (error) {
        if (import.meta.env.DEV) {
          logger.error('Error generating QR code', error, { component: 'FinancingContact' });
        }
      }
    };
    generateQR();
  }, [telegramLink]);
  
  const handleTelegramClick = () => {
    window.open(telegramLink, '_blank');
  };

  // Увеличенный SVG лого компонент
  const WellWonLogo = ({
    size = 80
  }: {
    size?: number;
  }) => <svg width={size} height={size} viewBox="0 0 512 512" className={`w-${Math.round(size / 4)} h-${Math.round(size / 4)}`}>
      <path fill="#ea3857" d="M256,16C123.5,16,16,123.5,16,256s107.5,240,240,240,240-107.5,240-240S388.5,16,256,16ZM256,457.6c-111.3,0-201.6-90.2-201.6-201.6S144.7,54.4,256,54.4s201.6,90.2,201.6,201.6-90.2,201.6-240,201.6ZM311.3,188.7l48.2,28.1-1,121.5-105.4,61.3-47.2-28.1,106.4-60.2-1-122.5ZM199.8,200.7l1,122.5-48.2-28.1,1-121.5,105.4-61.3,47.2,28.1-106.4,60.2Z" />
    </svg>;

  // SVG логотип WellWon как в навигации
  const WellWonTextLogo = () => <div className="flex flex-col leading-tight">
      <div className="text-accent-red text-2xl font-black tracking-tight relative">
        <span className="text-accent-red">Well</span>
        <span className="text-white">Won</span>
        <div className="absolute -bottom-1 left-0 w-8 h-0.5 bg-accent-red"></div>
      </div>
    </div>;
  return (
    <section id="contacts" className="py-12 px-6 lg:px-12 bg-gradient-to-br from-dark-gray via-medium-gray to-dark-gray relative overflow-hidden">
      {/* Декоративные элементы фона */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_50%,rgba(60,60,70,0.15),transparent_70%)]"></div>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_20%,rgba(80,80,90,0.08),transparent_60%)]"></div>
      <div className="absolute top-20 left-10 w-72 h-72 bg-light-gray/20 rounded-full blur-3xl"></div>
      <div className="absolute bottom-20 right-10 w-96 h-96 bg-medium-gray/30 rounded-full blur-3xl"></div>
      
      <div className="max-w-7xl mx-auto relative z-10">
        {/* Заголовок секции */}
        <div className="text-center mb-12 animate-fade-in">
          <div className="w-20 h-1 bg-accent-red mx-auto mb-8"></div>
          
          <h2 className="text-6xl lg:text-7xl font-black mb-4 leading-tight text-white">
            Запросить
          </h2>
          <h3 className="text-6xl lg:text-7xl font-black mb-8 leading-tight text-accent-red">
            Финансирование
          </h3>
          
          <p className="text-2xl text-gray-300 max-w-4xl mx-auto leading-relaxed font-light">Заполнить заявку и продолжить общение удобнее в Telegram App</p>
        </div>

        {/* Основной блок Telegram */}
        <Card className="overflow-hidden bg-gradient-to-br from-light-gray/30 to-medium-gray/20 backdrop-blur-2xl border border-light-gray/20 hover:border-light-gray/40 transition-all duration-700 group animate-fade-in mb-12 shadow-2xl shadow-black/20 rounded-3xl">
          <CardContent className="p-0">
            <div className="grid lg:grid-cols-2 items-stretch min-h-[600px]">
              {/* Левая часть - информация, кнопка и контакты */}
              <div className="p-12 flex flex-col justify-center space-y-6 relative bg-dark-gray rounded-l-3xl">
                {/* Декоративные элементы */}
                <div className="absolute top-8 right-8 w-20 h-20 bg-gradient-to-br from-medium-gray/30 to-transparent rounded-full animate-pulse"></div>
                
                {/* Логотип WellWon */}
                <div className="flex items-center space-x-6">
                  <div className="w-28 h-28 bg-gradient-to-br from-medium-gray to-light-gray rounded-3xl flex items-center justify-center shadow-2xl shadow-medium-gray/20 group-hover:scale-110 transition-transform duration-500 border border-medium-gray/30">
                    <WellWonLogo size={80} />
                  </div>
                  <div>
                    <WellWonTextLogo />
                    <p className="text-gray-300 font-bold text-xl mt-2">
                      Финансирование торговых операций
                    </p>
                  </div>
                </div>
                
                {/* Описание */}
                <div className="space-y-6">
                  <p className="text-gray-200 leading-relaxed text-2xl font-extrabold">Создайте заявку на финансирование в WellWon Telegram App за пару минут</p>
                  
                  <div className="space-y-4">
                    <div className="flex items-start text-gray-200 group/item">
                      <div className="w-8 h-8 bg-gray-500 rounded-full mr-4 shadow-lg shadow-medium-gray/30 group-hover/item:scale-125 transition-transform duration-300 flex items-center justify-center flex-shrink-0">
                        <span className="text-white font-bold text-sm">1</span>
                      </div>
                      <span className="text-lg group-hover/item:text-white transition-colors">Перейдите по кнопке или QR коду</span>
                    </div>
                    <div className="flex items-start text-gray-200 group/item">
                      <div className="w-8 h-8 bg-gray-500 rounded-full mr-4 shadow-lg shadow-medium-gray/30 group-hover/item:scale-125 transition-transform duration-300 flex items-center justify-center flex-shrink-0">
                        <span className="text-white font-bold text-sm">2</span>
                      </div>
                      <span className="text-lg group-hover/item:text-white transition-colors">Отправьте заготовленное сообщение</span>
                    </div>
                    <div className="flex items-start text-gray-200 group/item">
                      <div className="w-8 h-8 bg-gray-500 rounded-full mr-4 shadow-lg shadow-medium-gray/30 group-hover/item:scale-125 transition-transform duration-300 flex items-center justify-center flex-shrink-0">
                        <span className="text-white font-bold text-sm">3</span>
                      </div>
                      <span className="text-lg group-hover/item:text-white transition-colors">Мы поможем оформить заявку</span>
                    </div>
                    <div className="flex items-start text-gray-200 group/item">
                      <div className="w-8 h-8 bg-gray-500 rounded-full mr-4 shadow-lg shadow-medium-gray/30 group-hover/item:scale-125 transition-transform duration-300 flex items-center justify-center flex-shrink-0">
                        <span className="text-white font-bold text-sm">4</span>
                      </div>
                      <span className="text-lg group-hover/item:text-white transition-colors">Направим Вам решение и ответим на все вопросы</span>
                    </div>
                  </div>
                </div>

                {/* Кнопка Telegram */}
                <div className="relative">
                  <Button onClick={handleTelegramClick} className="w-full py-3 text-base font-bold rounded-2xl h-16 bg-white hover:bg-gray-100 text-dark-gray border-0 shadow-2xl hover:shadow-3xl transform hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 relative overflow-hidden group/btn hover:text-dark-gray">
                    <span className="relative z-10 flex items-center justify-center">
                      Создать заявку в Telegram
                      <svg className="w-4 h-4 ml-2 group-hover/btn:translate-x-1 group-hover/btn:rotate-12 transition-transform duration-300" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                      </svg>
                    </span>
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-gray-200/30 to-transparent -translate-x-full group-hover/btn:translate-x-full transition-transform duration-700"></div>
                    <div className="absolute inset-0 bg-gradient-to-br from-white/90 to-gray-50/90 opacity-0 group-hover/btn:opacity-100 transition-opacity duration-300"></div>
                  </Button>
                </div>

                {/* Дополнительные контакты */}
                <div className="space-y-4 pt-3 border-t border-light-gray/20">
                  <p className="text-gray-400 text-base font-medium mb-4">
                    Альтернативные способы связи:
                  </p>
                  
                  <div className="grid grid-cols-2 gap-4">
                    {/* Email */}
                    <div className="flex items-center space-x-4 p-4 bg-gradient-to-r from-dark-gray/90 to-medium-gray/80 rounded-3xl border border-light-gray/20 hover:border-white/25 hover:-translate-y-1 transition-all duration-300 group/contact">
                      <div className="w-10 h-10 bg-gradient-to-br from-accent-red/20 to-accent-red/10 rounded-xl flex items-center justify-center shadow-2xl shadow-medium-gray/30 group-hover/contact:scale-110 transition-transform duration-300">
                        <Mail className="w-5 h-5 text-accent-red" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-gray-400 text-sm">Email</p>
                        <a href="mailto:info@wellwon.hk" className="text-white text-base font-semibold hover:text-accent-red transition-colors duration-300 truncate block">
                          info@wellwon.hk
                        </a>
                      </div>
                    </div>

                    {/* Телефон */}
                    <div className="flex items-center space-x-4 p-4 bg-gradient-to-r from-dark-gray/90 to-medium-gray/80 rounded-3xl border border-light-gray/20 hover:border-white/25 hover:-translate-y-1 transition-all duration-300 group/contact">
                      <div className="w-10 h-10 bg-gradient-to-br from-accent-red/20 to-accent-red/10 rounded-xl flex items-center justify-center shadow-2xl shadow-medium-gray/30 group-hover/contact:scale-110 transition-transform duration-300">
                        <Phone className="w-5 h-5 text-accent-red" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-gray-400 text-sm">Телефон</p>
                        <a href="tel:+85292911173" className="text-white text-base font-semibold hover:text-accent-red transition-colors duration-300 truncate block">
                          +852 9291 1173
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Правая часть - iPhone мокап с диагональными полосами */}
              <div className="p-16 flex justify-center items-center relative bg-gradient-to-br from-gray-300 via-gray-400 to-gray-500 rounded-r-3xl overflow-hidden">
                {/* Базовый светло-серый фон */}
                <div className="absolute inset-0">
                  {/* Основной светло-серый градиент */}
                  <div className="absolute inset-0 bg-gradient-to-br from-gray-300 via-gray-400 to-gray-500"></div>
                  
                  {/* Диагональные полосы */}
                  <div className="absolute inset-0 bg-[repeating-linear-gradient(45deg,transparent,transparent_40px,rgba(255,255,255,0.03)_40px,rgba(255,255,255,0.03)_80px)]"></div>
                  <div className="absolute inset-0 bg-[repeating-linear-gradient(-45deg,transparent,transparent_60px,rgba(0,0,0,0.02)_60px,rgba(0,0,0,0.02)_120px)]"></div>
                  
                  {/* Тонкие дополнительные слои для глубины */}
                  <div className="absolute inset-0 bg-gradient-to-tr from-gray-300/80 via-transparent to-gray-200/40"></div>
                  <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.08),transparent_70%)]"></div>
                </div>

                <div className="relative transform hover:scale-105 transition-transform duration-500 z-10">
                  {/* iPhone корпус */}
                  <div className="relative w-80 h-[640px] bg-black rounded-[3.5rem] p-4 shadow-2xl shadow-black/50">
                    {/* Экран iPhone */}
                    <div className="w-full h-full bg-gradient-to-br from-dark-gray to-dark-gray rounded-[3rem] overflow-hidden relative">
                      {/* Статус бар */}
                      <div className="h-14 bg-black/20 backdrop-blur-sm flex items-center justify-between px-8 text-white text-base font-semibold border-b border-white/10">
                        <span>9:41</span>
                        <div className="flex space-x-2">
                          <div className="w-5 h-3 bg-white rounded-sm opacity-60"></div>
                          <div className="w-5 h-3 bg-white rounded-sm opacity-80"></div>
                          <div className="w-7 h-3 bg-green-500 rounded-sm"></div>
                        </div>
                      </div>
                      
                      {/* Контент приложения */}
                      <div className="flex-1 h-full bg-gradient-to-br from-dark-gray to-dark-gray p-6 flex flex-col items-center justify-center text-white relative">
                        {/* Фоновые декоративные элементы */}
                        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(60,60,70,0.1),transparent_50%)]"></div>
                        
                        {/* Логотип приложения */}
                        <div className="w-24 h-24 bg-gradient-to-br from-light-gray to-medium-gray rounded-3xl flex items-center justify-center mb-6 shadow-xl shadow-light-gray/20 animate-breathing border border-light-gray/30">
                          <WellWonLogo size={62} />
                        </div>
                        
                        {/* SVG логотип как в навигации */}
                        <div className="mb-3 scale-75">
                          <div className="flex flex-col leading-tight">
                            <div className="text-accent-red text-2xl font-black tracking-tight relative">
                              <span className="text-accent-red">Well</span>
                              <span className="text-white">Won</span>
                              <div className="absolute -bottom-1 left-0 w-8 h-0.5 bg-accent-red"></div>
                            </div>
                          </div>
                        </div>
                        <p className="text-sm text-gray-300 text-center mb-8 px-4">Финансирование торговых операций</p>
                        
                        {/* QR код */}
                        {qrCodeUrl && <div className="bg-white p-4 rounded-2xl shadow-2xl shadow-black/20 mb-4 transform hover:scale-105 transition-transform duration-300">
                            <img src={qrCodeUrl} alt="QR код для Telegram бота" className="w-40 h-40" />
                          </div>}
                        
                        <p className="text-xs text-gray-400 text-center px-6 leading-relaxed">
                          Сканируйте QR-код
                        </p>
                      </div>
                    </div>
                    
                    {/* Home indicator */}
                    <div className="absolute bottom-3 left-1/2 transform -translate-x-1/2 w-36 h-1.5 bg-white rounded-full"></div>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
};

export default FinancingContact;
