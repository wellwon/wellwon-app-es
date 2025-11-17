import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Shield, Lock, Eye, Database } from 'lucide-react';
import { GlassCard } from '@/components/design-system/GlassCard';
const PrivacyPage: React.FC = () => {
  const navigate = useNavigate();
  return <div className="min-h-screen bg-dark-gray">
      {/* Шапка */}
      <header className="border-b border-white/10 bg-medium-gray/50 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center gap-4">
            
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-accent-red rounded-lg flex items-center justify-center">
                <Shield className="w-4 h-4 text-white" />
              </div>
              <h1 className="text-xl font-semibold text-white">Политика конфиденциальности</h1>
            </div>
          </div>
        </div>
      </header>

      {/* Основной контент */}
      <main className="max-w-4xl mx-auto px-6 py-8">
        <GlassCard className="p-8 space-y-8">
          {/* Введение */}
          <div className="text-center space-y-4">
            <h2 className="text-2xl font-bold text-white">Политика конфиденциальности WellWon</h2>
            <p className="text-gray-400">
              Последнее обновление: {new Date().toLocaleDateString('ru-RU')}
            </p>
            <div className="bg-accent-red/10 border border-accent-red/20 rounded-lg p-4">
              <p className="text-accent-red text-sm">
                Мы серьезно относимся к защите ваших персональных данных и соблюдаем требования 152-ФЗ "О персональных данных"
              </p>
            </div>
          </div>

          {/* Разделы */}
          <div className="space-y-8">
            {/* 1. Какие данные мы собираем */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <Database className="w-5 h-5 text-accent-red" />
                Какие данные мы собираем
              </h3>
              <div className="text-gray-300 leading-relaxed space-y-3">
                <p>Мы можем собирать следующие категории персональных данных:</p>
                
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="bg-medium-gray/50 rounded-lg p-4 space-y-2">
                    <h4 className="font-medium text-white">Регистрационные данные</h4>
                    <ul className="text-sm text-gray-300 space-y-1">
                      <li>• Имя и фамилия</li>
                      <li>• Email адрес</li>
                      <li>• Номер телефона</li>
                      <li>• Название компании</li>
                    </ul>
                  </div>
                  
                  <div className="bg-medium-gray/50 rounded-lg p-4 space-y-2">
                    <h4 className="font-medium text-white">Технические данные</h4>
                    <ul className="text-sm text-gray-300 space-y-1">
                      <li>• IP-адрес</li>
                      <li>• Данные браузера</li>
                      <li>• Информация об устройстве</li>
                      <li>• Cookies и пиксели отслеживания</li>
                    </ul>
                  </div>
                </div>
              </div>
            </section>

            {/* 2. Как мы используем данные */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <Eye className="w-5 h-5 text-accent-red" />
                Как мы используем ваши данные
              </h3>
              <div className="text-gray-300 leading-relaxed space-y-3">
                <p>Мы используем собранные данные для:</p>
                <div className="grid gap-3">
                  <div className="flex gap-3 p-3 bg-accent-red/5 border-l-2 border-accent-red/30 rounded">
                    <div className="w-2 h-2 bg-accent-red rounded-full mt-2 flex-shrink-0"></div>
                    <div>
                      <p className="font-medium text-white">Предоставление сервиса</p>
                      <p className="text-sm text-gray-300">Создание аккаунта, обработка заказов, техническая поддержка</p>
                    </div>
                  </div>
                  
                  <div className="flex gap-3 p-3 bg-accent-red/5 border-l-2 border-accent-red/30 rounded">
                    <div className="w-2 h-2 bg-accent-red rounded-full mt-2 flex-shrink-0"></div>
                    <div>
                      <p className="font-medium text-white">Улучшение платформы</p>
                      <p className="text-sm text-gray-300">Анализ использования, разработка новых функций</p>
                    </div>
                  </div>
                  
                  <div className="flex gap-3 p-3 bg-accent-red/5 border-l-2 border-accent-red/30 rounded">
                    <div className="w-2 h-2 bg-accent-red rounded-full mt-2 flex-shrink-0"></div>
                    <div>
                      <p className="font-medium text-white">Коммуникация</p>
                      <p className="text-sm text-gray-300">Отправка уведомлений, маркетинговых материалов (с согласия)</p>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* 3. Правовые основания */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white">Правовые основания обработки</h3>
              <div className="text-gray-300 leading-relaxed space-y-3">
                <p>Обработка персональных данных осуществляется на следующих правовых основаниях:</p>
                <ul className="list-disc list-inside space-y-2 ml-4">
                  <li>Согласие субъекта персональных данных</li>
                  <li>Исполнение договора, стороной которого является субъект</li>
                  <li>Соблюдение правовых обязательств</li>
                  <li>Защита жизненно важных интересов</li>
                </ul>
              </div>
            </section>

            {/* 4. Защита данных */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <Lock className="w-5 h-5 text-accent-red" />
                Как мы защищаем ваши данные
              </h3>
              <div className="text-gray-300 leading-relaxed space-y-3">
                <p>Мы применяем современные технологии защиты информации:</p>
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                      <span className="text-sm font-medium text-white">SSL/TLS шифрование</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                      <span className="text-sm font-medium text-white">Двухфакторная аутентификация</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                      <span className="text-sm font-medium text-white">Регулярные аудиты безопасности</span>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                      <span className="text-sm font-medium text-white">Ограниченный доступ к данным</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                      <span className="text-sm font-medium text-white">Резервное копирование</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                      <span className="text-sm font-medium text-white">Мониторинг инцидентов</span>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* 5. Ваши права */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white">Ваши права</h3>
              <div className="text-gray-300 leading-relaxed">
                <p className="mb-4">В соответствии с законодательством РФ, вы имеете следующие права:</p>
                <div className="grid gap-3">
                  {[{
                  title: 'Право на доступ',
                  desc: 'Получение информации о обработке ваших данных'
                }, {
                  title: 'Право на исправление',
                  desc: 'Внесение изменений в неточные данные'
                }, {
                  title: 'Право на удаление',
                  desc: 'Запрос на удаление персональных данных'
                }, {
                  title: 'Право на ограничение',
                  desc: 'Ограничение обработки в определенных случаях'
                }, {
                  title: 'Право на переносимость',
                  desc: 'Получение данных в структурированном формате'
                }, {
                  title: 'Право на возражение',
                  desc: 'Возражение против обработки данных'
                }].map((right, index) => <div key={index} className="bg-medium-gray/30 rounded-lg p-3">
                      <h4 className="font-medium text-white">{right.title}</h4>
                      <p className="text-sm text-gray-300">{right.desc}</p>
                    </div>)}
                </div>
              </div>
            </section>

            {/* 6. Cookies */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white">Использование Cookies</h3>
              <div className="text-gray-300 leading-relaxed space-y-3">
                <p>Мы используем cookies для улучшения работы сайта:</p>
                <div className="grid md:grid-cols-3 gap-4">
                  <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
                    <h4 className="font-medium text-blue-400 mb-2">Необходимые</h4>
                    <p className="text-sm text-gray-300">Обеспечивают базовую функциональность</p>
                  </div>
                  <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4">
                    <h4 className="font-medium text-yellow-400 mb-2">Аналитические</h4>
                    <p className="text-sm text-gray-300">Помогают понять использование сайта</p>
                  </div>
                  <div className="bg-purple-500/10 border border-purple-500/20 rounded-lg p-4">
                    <h4 className="font-medium text-purple-400 mb-2">Маркетинговые</h4>
                    <p className="text-sm text-gray-300">Для персонализации рекламы</p>
                  </div>
                </div>
              </div>
            </section>

            {/* 7. Контакты */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white">Контактная информация</h3>
              <div className="bg-accent-red/10 border border-accent-red/20 rounded-lg p-6">
                <p className="text-gray-300 mb-4">
                  По вопросам обработки персональных данных обращайтесь:
                </p>
                <div className="space-y-2 text-sm">
                  <div className="flex gap-2">
                    <span className="text-gray-400">Email:</span>
                    <a href="mailto:privacy@wellwon.hk" className="text-accent-red hover:text-accent-red/80 transition-colors">
                      privacy@wellwon.hk
                    </a>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-400">Телефон:</span>
                    <a href="tel:+78001234567" className="text-accent-red hover:text-accent-red/80 transition-colors">
                      +7 (800) 123-45-67
                    </a>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-400">Почтовый адрес:</span>
                    <span className="text-gray-300">г. Москва, ул. Примерная, д. 1, офис 100</span>
                  </div>
                </div>
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
    </div>;
};
export default PrivacyPage;