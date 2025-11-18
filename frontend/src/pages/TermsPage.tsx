
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Scale, Shield, AlertTriangle } from 'lucide-react';
import { GlassCard } from '@/components/design-system/GlassCard';

const TermsPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-dark-gray">
      {/* Шапка */}
      <header className="border-b border-white/10 bg-medium-gray/50 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center gap-4">
            
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-accent-red rounded-lg flex items-center justify-center">
                <Scale className="w-4 h-4 text-white" />
              </div>
              <h1 className="text-xl font-semibold text-white">Условия использования</h1>
            </div>
          </div>
        </div>
      </header>

      {/* Основной контент */}
      <main className="max-w-4xl mx-auto px-6 py-8">
        <GlassCard className="p-8 space-y-8">
          {/* Введение */}
          <div className="text-center space-y-4">
            <h2 className="text-2xl font-bold text-white">Условия использования WellWon</h2>
            <p className="text-gray-400">
              Последнее обновление: {new Date().toLocaleDateString('ru-RU')}
            </p>
          </div>

          {/* Разделы */}
          <div className="space-y-8">
            {/* 1. Принятие условий */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <div className="w-6 h-6 bg-accent-red/20 rounded-full flex items-center justify-center text-xs font-bold text-accent-red">1</div>
                Принятие условий
              </h3>
              <p className="text-gray-300 leading-relaxed">
                Добро пожаловать на платформу WellWon. Используя наш сервис, вы соглашаетесь с настоящими условиями использования. 
                Если вы не согласны с какими-либо условиями, пожалуйста, не используйте наш сервис.
              </p>
            </section>

            {/* 2. Описание сервиса */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <div className="w-6 h-6 bg-accent-red/20 rounded-full flex items-center justify-center text-xs font-bold text-accent-red">2</div>
                Описание сервиса
              </h3>
              <div className="text-gray-300 leading-relaxed space-y-3">
                <p>
                  WellWon — это платформа для оптимизации закупок и управления поставщиками, предоставляющая:
                </p>
                <ul className="list-disc list-inside space-y-2 ml-4">
                  <li>Автоматизированный поиск и сравнение поставщиков</li>
                  <li>Управление заказами и документооборотом</li>
                  <li>Аналитику и отчетность по закупкам</li>
                  <li>Интеграцию с внешними системами</li>
                </ul>
              </div>
            </section>

            {/* 3. Регистрация и аккаунт */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <div className="w-6 h-6 bg-accent-red/20 rounded-full flex items-center justify-center text-xs font-bold text-accent-red">3</div>
                Регистрация и аккаунт
              </h3>
              <div className="text-gray-300 leading-relaxed space-y-3">
                <p>При регистрации вы обязуетесь:</p>
                <ul className="list-disc list-inside space-y-2 ml-4">
                  <li>Предоставлять точную и актуальную информацию</li>
                  <li>Поддерживать безопасность вашего аккаунта</li>
                  <li>Немедленно уведомлять нас о любом несанкционированном доступе</li>
                  <li>Нести ответственность за все действия в вашем аккаунте</li>
                </ul>
              </div>
            </section>

            {/* 4. Правила использования */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <div className="w-6 h-6 bg-accent-red/20 rounded-full flex items-center justify-center text-xs font-bold text-accent-red">4</div>
                Правила использования
              </h3>
              <div className="text-gray-300 leading-relaxed space-y-3">
                <p>Запрещается использовать платформу для:</p>
                <ul className="list-disc list-inside space-y-2 ml-4">
                  <li>Нарушения законодательства РФ и международного права</li>
                  <li>Загрузки вредоносного программного обеспечения</li>
                  <li>Несанкционированного доступа к системам и данным</li>
                  <li>Спама или массовых рассылок</li>
                  <li>Нарушения прав интеллектуальной собственности</li>
                </ul>
              </div>
            </section>

            {/* 5. Интеллектуальная собственность */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <div className="w-6 h-6 bg-accent-red/20 rounded-full flex items-center justify-center text-xs font-bold text-accent-red">5</div>
                Интеллектуальная собственность
              </h3>
              <p className="text-gray-300 leading-relaxed">
                Все права на платформу WellWon, включая программное обеспечение, дизайн, логотипы и контент, 
                принадлежат нашей компании и защищены авторским правом и другими законами об интеллектуальной собственности.
              </p>
            </section>

            {/* 6. Ограничение ответственности */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <div className="w-6 h-6 bg-accent-red/20 rounded-full flex items-center justify-center text-xs font-bold text-accent-red">6</div>
                Ограничение ответственности
              </h3>
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4 flex gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                <div className="text-amber-200 text-sm leading-relaxed">
                  <p className="font-medium mb-2">Важное уведомление:</p>
                  <p>
                    Платформа предоставляется "как есть". Мы не несем ответственности за косвенные убытки, 
                    потерю данных или упущенную выгоду, возникшие в результате использования сервиса.
                  </p>
                </div>
              </div>
            </section>

            {/* 7. Изменение условий */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <div className="w-6 h-6 bg-accent-red/20 rounded-full flex items-center justify-center text-xs font-bold text-accent-red">7</div>
                Изменение условий
              </h3>
              <p className="text-gray-300 leading-relaxed">
                Мы оставляем за собой право изменять настоящие условия в любое время. 
                Уведомления об изменениях будут размещены на этой странице. 
                Продолжение использования сервиса после изменений означает ваше согласие с новыми условиями.
              </p>
            </section>

            {/* 8. Контактная информация */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <div className="w-6 h-6 bg-accent-red/20 rounded-full flex items-center justify-center text-xs font-bold text-accent-red">8</div>
                Контактная информация
              </h3>
              <div className="bg-accent-red/10 border border-accent-red/20 rounded-lg p-4">
                <p className="text-gray-300 leading-relaxed">
                  Если у вас есть вопросы относительно настоящих условий использования, 
                  пожалуйста, свяжитесь с нами по адресу:{' '}
                  <a href="mailto:legal@wellwon.hk" className="text-accent-red hover:text-accent-red/80 transition-colors">
                    legal@wellwon.hk
                  </a>
                </p>
              </div>
            </section>
          </div>

          {/* Подвал */}
          <div className="border-t border-white/10 pt-6 text-center">
            <p className="text-gray-400 text-sm">
              © {new Date().getFullYear()} WellWon. Все права защищены.
            </p>
          </div>
        </GlassCard>
      </main>
    </div>
  );
};

export default TermsPage;
