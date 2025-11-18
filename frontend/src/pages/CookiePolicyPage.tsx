import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Cookie, Settings, Eye, BarChart3, Target } from 'lucide-react';
import { GlassCard } from '@/components/design-system/GlassCard';
const CookiePolicyPage: React.FC = () => {
  const navigate = useNavigate();
  return <div className="min-h-screen bg-dark-gray">
      {/* Шапка */}
      <header className="border-b border-white/10 bg-medium-gray/50 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center gap-4">
            
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-accent-red rounded-lg flex items-center justify-center">
                <Cookie className="w-4 h-4 text-white" />
              </div>
              <h1 className="text-xl font-semibold text-white">Политика использования файлов cookie</h1>
            </div>
          </div>
        </div>
      </header>

      {/* Основной контент */}
      <main className="max-w-4xl mx-auto px-6 py-8">
        <GlassCard className="p-8 space-y-8">
          {/* Введение */}
          <div className="text-center space-y-4">
            <h2 className="text-2xl font-bold text-white">Политика cookie WellWon</h2>
            <p className="text-gray-400">
              Последнее обновление: {new Date().toLocaleDateString('ru-RU')}
            </p>
            <div className="bg-accent-red/10 border border-accent-red/20 rounded-lg p-4">
              <p className="text-accent-red text-sm">
                Мы используем файлы cookie для улучшения работы нашего сайта и предоставления персонализированного опыта
              </p>
            </div>
          </div>

          {/* Разделы */}
          <div className="space-y-8">
            {/* 1. Что такое cookies */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <Cookie className="w-5 h-5 text-accent-red" />
                Что такое файлы cookie
              </h3>
              <div className="text-gray-300 leading-relaxed space-y-3">
                <p>
                  Файлы cookie — это небольшие текстовые файлы, которые сайты сохраняют на вашем устройстве 
                  для запоминания информации о ваших предпочтениях и активности. Они помогают нам обеспечивать 
                  лучший опыт использования нашего сайта.
                </p>
              </div>
            </section>

            {/* 2. Типы cookies */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <Settings className="w-5 h-5 text-accent-red" />
                Типы файлов cookie, которые мы используем
              </h3>
              
              <div className="grid gap-6">
                {/* Необходимые */}
                <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
                      <Settings className="w-4 h-4 text-white" />
                    </div>
                    <h4 className="text-lg font-semibold text-blue-400">Необходимые cookie</h4>
                  </div>
                  <p className="text-gray-300 mb-3">
                    Эти файлы cookie критически важны для работы сайта и не могут быть отключены. 
                    Они обычно устанавливаются в ответ на ваши действия, такие как вход в систему или заполнение форм.
                  </p>
                  <div className="space-y-2">
                    <p className="text-sm text-gray-400"><strong>Примеры:</strong></p>
                    <ul className="text-sm text-gray-300 space-y-1 ml-4">
                      <li>• Аутентификация пользователя</li>
                      <li>• Безопасность сессии</li>
                      <li>• Настройки языка</li>
                      <li>• Корзина покупок</li>
                    </ul>
                  </div>
                </div>

                {/* Аналитические */}
                <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-8 h-8 bg-yellow-500 rounded-lg flex items-center justify-center">
                      <BarChart3 className="w-4 h-4 text-white" />
                    </div>
                    <h4 className="text-lg font-semibold text-yellow-400">Аналитические cookie</h4>
                  </div>
                  <p className="text-gray-300 mb-3">
                    Помогают нам понять, как посетители взаимодействуют с сайтом, собирая и предоставляя 
                    информацию анонимно. Эти данные помогают нам улучшать работу сайта.
                  </p>
                  <div className="space-y-2">
                    <p className="text-sm text-gray-400"><strong>Что мы отслеживаем:</strong></p>
                    <ul className="text-sm text-gray-300 space-y-1 ml-4">
                      <li>• Количество посещений</li>
                      <li>• Время, проведенное на сайте</li>
                      <li>• Популярные страницы</li>
                      <li>• Источники трафика</li>
                    </ul>
                  </div>
                </div>

                {/* Рекламные */}
                <div className="bg-purple-500/10 border border-purple-500/20 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-8 h-8 bg-purple-500 rounded-lg flex items-center justify-center">
                      <Target className="w-4 h-4 text-white" />
                    </div>
                    <h4 className="text-lg font-semibold text-purple-400">Рекламные cookie</h4>
                  </div>
                  <p className="text-gray-300 mb-3">
                    Используются для показа релевантной рекламы и отслеживания эффективности рекламных кампаний. 
                    Могут использоваться для создания профиля ваших интересов.
                  </p>
                  <div className="space-y-2">
                    <p className="text-sm text-gray-400"><strong>Цели использования:</strong></p>
                    <ul className="text-sm text-gray-300 space-y-1 ml-4">
                      <li>• Персонализация рекламы</li>
                      <li>• Ретаргетинг</li>
                      <li>• Измерение эффективности</li>
                      <li>• Ограничение частоты показов</li>
                    </ul>
                  </div>
                </div>

                {/* Предпочтения */}
                <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center">
                      <Eye className="w-4 h-4 text-white" />
                    </div>
                    <h4 className="text-lg font-semibold text-green-400">Cookie предпочтений</h4>
                  </div>
                  <p className="text-gray-300 mb-3">
                    Позволяют сайту запоминать информацию, которая влияет на поведение или внешний вид сайта, 
                    например, ваш предпочитаемый язык или регион.
                  </p>
                  <div className="space-y-2">
                    <p className="text-sm text-gray-400"><strong>Что запоминается:</strong></p>
                    <ul className="text-sm text-gray-300 space-y-1 ml-4">
                      <li>• Языковые настройки</li>
                      <li>• Тема оформления</li>
                      <li>• Региональные настройки</li>
                      <li>• Персональные настройки интерфейса</li>
                    </ul>
                  </div>
                </div>
              </div>
            </section>

            {/* 3. Управление cookies */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white">Как управлять файлами cookie</h3>
              <div className="text-gray-300 leading-relaxed space-y-4">
                <p>
                  Вы можете контролировать и/или удалять файлы cookie по своему усмотрению. 
                  Подробности смотрите на сайте aboutcookies.org.
                </p>
                
                <div className="bg-medium-gray/50 rounded-lg p-4 space-y-3">
                  <h4 className="font-medium text-white">Способы управления:</h4>
                  <ul className="text-sm text-gray-300 space-y-2 ml-4">
                    <li>• <strong>Через наш сайт:</strong> Используйте настройки cookie на нашем сайте</li>
                    <li>• <strong>Через браузер:</strong> Измените настройки в вашем браузере</li>
                    <li>• <strong>Удаление:</strong> Вы можете удалить все сохраненные cookie</li>
                    <li>• <strong>Блокировка:</strong> Предотвратите установку новых cookie</li>
                  </ul>
                </div>

                <div className="bg-accent-red/10 border border-accent-red/20 rounded-lg p-4">
                  <p className="text-accent-red text-sm">
                    <strong>Внимание:</strong> Отключение некоторых типов cookie может повлиять на работу сайта 
                    и доступность определенных функций.
                  </p>
                </div>
              </div>
            </section>

            {/* 4. Сторонние сервисы */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white">Сторонние сервисы</h3>
              <div className="text-gray-300 leading-relaxed space-y-3">
                <p>Мы используем следующие сторонние сервисы, которые могут устанавливать собственные cookie:</p>
                
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="bg-medium-gray/30 rounded-lg p-4">
                    <h4 className="font-medium text-white mb-2">Yandex.Metrica</h4>
                    <p className="text-sm text-gray-300">Веб-аналитика и отслеживание поведения пользователей</p>
                  </div>
                  
                  <div className="bg-medium-gray/30 rounded-lg p-4">
                    <h4 className="font-medium text-white mb-2">Google Analytics</h4>
                    <p className="text-sm text-gray-300">Анализ трафика и поведения пользователей</p>
                  </div>
                </div>
              </div>
            </section>

            {/* 5. Контакты */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white">Вопросы по cookie</h3>
              <div className="bg-accent-red/10 border border-accent-red/20 rounded-lg p-6">
                <p className="text-gray-300 mb-4">
                  Если у вас есть вопросы о нашем использовании файлов cookie, обращайтесь:
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
                    <a href="tel:+85292911173" className="text-accent-red hover:text-accent-red/80 transition-colors">
                      +852 9291 1173
                    </a>
                  </div>
                </div>
              </div>
            </section>
          </div>

          {/* Подвал */}
          <div className="border-t border-white/10 pt-6 text-center">
            <p className="text-gray-400 text-sm">
              © {new Date().getFullYear()} WellWon Limited. Все права защищены.
            </p>
          </div>
        </GlassCard>
      </main>
    </div>;
};
export default CookiePolicyPage;