import { useState, useEffect, memo, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { MessageCircle, TrendingUp, Shield, Clock, CheckCircle, Bell, ArrowRight } from "lucide-react";
import UTMLink from "@/components/shared/UTMLink";
import { logger } from "@/utils/logger";

const PlatformShowcase = memo(() => {
  const [activeDemo, setActiveDemo] = useState(0);
  const [typingText, setTypingText] = useState("");
  const [showNotification, setShowNotification] = useState(false);
  
  // Рефы для предотвращения множественных эффектов
  const typingIntervalRef = useRef<NodeJS.Timeout>();
  const nextDemoTimeoutRef = useRef<NodeJS.Timeout>();
  const notificationIntervalRef = useRef<NodeJS.Timeout>();
  const notificationTimeoutRef = useRef<NodeJS.Timeout>();
  const isMountedRef = useRef(true);
  
  const demoTexts = ["Анализируем ваши потребности...", "Ищем лучших поставщиков...", "Оптимизируем цены...", "Сделка готова!"];
  const metrics = [{
    value: "2.3млрд₽",
    label: "Сэкономлено клиентам",
    icon: TrendingUp
  }, {
    value: "15%",
    label: "Средняя экономия",
    icon: CheckCircle
  }, {
    value: "24ч",
    label: "Время поиска поставщика",
    icon: Clock
  }, {
    value: "500+",
    label: "Проверенных поставщиков",
    icon: Shield
  }];
  const features = ["ИИ-анализ потребностей", "Чат с поставщиками", "Автоматизация закупок", "Аналитика и отчеты"];

  // Обработчик нажатия кнопки контакта
  const handleContactClick = useCallback(() => {
    const contactsElement = document.getElementById('contacts');
    if (contactsElement) {
      contactsElement.scrollIntoView({
        behavior: 'smooth'
      });
    } else {
      logger.warn('Contacts element not found', { component: 'PlatformShowcase' });
    }
  }, []);

  // Эффект для unmounting
  useEffect(() => {
    isMountedRef.current = true;
    logger.debug('PlatformShowcase mounted', { component: 'PlatformShowcase' });
    
    return () => {
      isMountedRef.current = false;
      logger.debug('PlatformShowcase unmounting, clearing intervals', { component: 'PlatformShowcase' });
      
      // Очищаем все интервалы и таймауты
      if (typingIntervalRef.current) clearInterval(typingIntervalRef.current);
      if (nextDemoTimeoutRef.current) clearTimeout(nextDemoTimeoutRef.current);
      if (notificationIntervalRef.current) clearInterval(notificationIntervalRef.current);
      if (notificationTimeoutRef.current) clearTimeout(notificationTimeoutRef.current);
    };
  }, []);

  // Анимация печатания текста с оптимизацией
  useEffect(() => {
    if (!isMountedRef.current) return;
    
    const text = demoTexts[activeDemo];
    let currentIndex = 0;
    
    // Очищаем предыдущие таймауты
    if (typingIntervalRef.current) clearInterval(typingIntervalRef.current);
    if (nextDemoTimeoutRef.current) clearTimeout(nextDemoTimeoutRef.current);
    
    setTypingText("");
    
    typingIntervalRef.current = setInterval(() => {
      if (!isMountedRef.current) {
        clearInterval(typingIntervalRef.current!);
        return;
      }
      
      if (currentIndex < text.length) {
        setTypingText(prev => prev + text[currentIndex]);
        currentIndex++;
      } else {
        clearInterval(typingIntervalRef.current!);
        nextDemoTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current) {
            setActiveDemo(prev => (prev + 1) % demoTexts.length);
          }
        }, 3000);
      }
    }, 100);
  }, [activeDemo, demoTexts]);

  // Уведомления с паузой при неактивной вкладке  
  useEffect(() => {
    if (!isMountedRef.current) return;
    
    // Очищаем предыдущие интервалы
    if (notificationIntervalRef.current) clearInterval(notificationIntervalRef.current);
    if (notificationTimeoutRef.current) clearTimeout(notificationTimeoutRef.current);
    
    const startNotifications = () => {
      notificationIntervalRef.current = setInterval(() => {
        if (!isMountedRef.current) {
          clearInterval(notificationIntervalRef.current!);
          return;
        }
        
        if (!document.hidden) { // Только если вкладка активна
          setShowNotification(true);
          notificationTimeoutRef.current = setTimeout(() => {
            if (isMountedRef.current) {
              setShowNotification(false);
            }
          }, 3000);
        }
      }, 12000);
    };

    // Задержка запуска уведомлений для избежания конфликтов
    const startDelay = setTimeout(() => {
      if (isMountedRef.current) {
        startNotifications();
      }
    }, 2000);
    
    return () => {
      clearTimeout(startDelay);
    };
  }, []);
  return <section className="pt-32 pb-20 px-6 lg:px-12 relative overflow-hidden">
      {/* Декоративные элементы фона */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute top-20 left-20 w-96 h-96 bg-accent-red rounded-full blur-3xl animate-smooth-glow"></div>
        <div className="absolute bottom-20 right-20 w-64 h-64 bg-accent-red rounded-full blur-3xl animate-smooth-glow" style={{
        animationDelay: '3s'
      }}></div>
      </div>
      
      <div className="max-w-7xl mx-auto my-[50px] relative z-10">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Левая колонка - Контент */}
          <div className="text-center lg:text-left space-y-8">
            {/* Уведомление о новых возможностях */}
            <div className="inline-flex items-center glass-card px-6 py-3 rounded-full">
              <Bell className="w-4 h-4 text-text-gray-400 mr-2" />
              <span className="text-text-gray-400 text-sm font-semibold">Новая эра умных закупок</span>
            </div>
            
            {/* Главный заголовок */}
            <div>
              <h1 className="text-5xl lg:text-7xl font-black leading-none mb-6">
                <span className="text-text-white">Платформа</span>
                <br />
                <span className="text-accent-red">
                  Умных Закупок
                </span>
                <br />
                
              </h1>
              
              <p className="text-xl lg:text-2xl text-text-gray-400 mb-8 leading-relaxed">Революционная платформа для автоматизации закупок, финансирования и логистики</p>
            </div>

            {/* Ключевые возможности */}
            <div className="grid grid-cols-2 gap-4 mb-8">
              {features.map((feature, index) => <div key={index} className="flex items-center space-x-3 opacity-0 animate-fade-in" style={{
              animationDelay: `${index * 0.2}s`,
              animationFillMode: 'forwards'
            }}>
                  <div className="w-2 h-2 bg-accent-red rounded-full"></div>
                  <span className="text-text-gray-400 text-sm">{feature}</span>
                </div>)}
            </div>

            {/* Метрики */}
            
            
            {/* Кнопки действий */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
              <Button className="glass-button bg-accent-red text-text-white px-10 py-4 text-lg rounded-full transition-all duration-300 hover:scale-105 hover:shadow-xl hover-scale shadow-lg group" asChild>
                <UTMLink to="/platform">
                  Начать работу
                  <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
                </UTMLink>
              </Button>
              <Button variant="secondary" className="glass-button px-10 py-4 text-lg font-medium rounded-full transition-all duration-300 hover:scale-105 hover-scale" onClick={handleContactClick}>
                <MessageCircle className="w-5 h-5 mr-2" />
                Демонстрация
              </Button>
            </div>
          </div>
          
          {/* Правая колонка - 3D Анимированная платформа */}
          <div className="relative perspective-1000 ml-8">
            {/* 3D Контейнер для платформы */}
            <div className="relative transform-gpu transition-all duration-1000 preserve-3d rotate-x-12 rotate-y-6 hover:rotate-y-12 hover:rotate-x-6 hover:scale-105" style={{ willChange: 'transform' }}>
              {/* Основное изображение платформы */}
              <div className="relative glass-card rounded-3xl overflow-hidden transform-gpu">
                <img src="/lovable-uploads/cbad2c42-a62e-47df-944a-c4aa4c71236d.png" alt="WellWon Platform Interface" className="w-full h-auto rounded-2xl transform transition-all duration-700 hover:scale-105" />
                
                {/* Анимированные элементы поверх изображения */}
                <div className="absolute inset-0">
                  {/* Плавающие уведомления */}
                  {showNotification}
                  
                  {/* Анимированные точки активности */}
                  
                  <div className="absolute top-2/3 right-1/3 w-2 h-2 bg-accent-green rounded-full animate-pulse opacity-60" style={{
                  animationDelay: '1s'
                }}></div>
                  <div className="absolute bottom-1/4 left-1/3 w-2 h-2 bg-accent-green rounded-full animate-pulse opacity-70" style={{
                  animationDelay: '2s'
                }}></div>
                  
                  {/* Анимация печатания в чате */}
                  <div className="absolute bottom-1/3 right-1/4 glass-card p-2 rounded-lg animate-fade-in">
                    <div className="flex items-center space-x-1">
                      <div className="w-1 h-1 bg-accent-green rounded-full animate-pulse"></div>
                      <div className="w-1 h-1 bg-accent-green rounded-full animate-pulse" style={{
                      animationDelay: '0.2s'
                    }}></div>
                      <div className="w-1 h-1 bg-accent-green rounded-full animate-pulse" style={{
                      animationDelay: '0.4s'
                    }}></div>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* 3D Тень */}
              
            </div>
            
            {/* Плавающие элементы вокруг интерфейса */}
            <div className="absolute -top-6 -left-6 w-32 h-32 bg-accent-red/10 rounded-full blur-3xl animate-gentle-float"></div>
            <div className="absolute -bottom-6 -right-6 w-24 h-24 bg-accent-red/15 rounded-full blur-2xl animate-gentle-float" style={{
            animationDelay: '3s'
          }}></div>
            
            {/* Иконки функций */}
            <div className="absolute -left-8 top-1/4 glass-card p-3 rounded-xl animate-float">
              <TrendingUp className="w-6 h-6 text-accent-red" />
            </div>
            <div className="absolute -right-8 top-1/3 glass-card p-3 rounded-xl animate-float" style={{
            animationDelay: '1s'
          }}>
              <Shield className="w-6 h-6 text-accent-green" />
            </div>
            <div className="absolute -left-8 bottom-1/4 glass-card p-3 rounded-xl animate-float" style={{
            animationDelay: '2s'
          }}>
              <MessageCircle className="w-6 h-6 text-accent-red" />
            </div>
          </div>
        </div>
      </div>
    </section>;
});

PlatformShowcase.displayName = 'PlatformShowcase';

export default PlatformShowcase;