import { Calculator, TrendingUp, DollarSign, Target, Zap, Shield, Trophy, Rocket, AlertTriangle, ArrowRight, CheckCircle, Users, Clock } from "lucide-react";
import { useState, useEffect } from "react";

const FinancingCalculator = () => {
  const [turnover, setTurnover] = useState(500000);
  const [margin, setMargin] = useState(30);
  const [sellDays, setSellDays] = useState(30);
  const [cycles, setCycles] = useState(8);
  const [results, setResults] = useState({
    extraProfit: 0,
    extraProfitPercent: 0,
    newPurchaseSize: 0,
    leverageCostPerCycle: 0,
    leverageROI: 0,
    currentPurchaseSize: 0,
    currentProfitPerCycle: 0,
    currentYearlyProfit: 0,
    currentROE: 0,
    netProfitPerCycle: 0,
    netYearlyProfit: 0,
    newROE: 0
  });
  const calculate = () => {
    const leverageRate = 0.015;
    const ownShare = 0.3;
    const leverageShare = 0.7;
    const currentPurchaseSize = turnover;
    const currentProfitPerCycle = turnover * (margin / 100);
    const currentYearlyProfit = currentProfitPerCycle * cycles;
    const currentROE = currentYearlyProfit / turnover * 100;
    const newPurchaseSize = turnover / ownShare;
    const leverageAmount = newPurchaseSize * leverageShare;
    const grossProfitPerCycle = newPurchaseSize * (margin / 100);
    const leverageCostPerCycle = leverageAmount * leverageRate;
    const netProfitPerCycle = grossProfitPerCycle - leverageCostPerCycle;
    const netYearlyProfit = netProfitPerCycle * cycles;
    const newROE = netYearlyProfit / turnover * 100;
    const extraProfit = netYearlyProfit - currentYearlyProfit;
    const extraProfitPercent = currentYearlyProfit > 0 ? Math.round(extraProfit / currentYearlyProfit * 100) : 0;
    const totalLeverageCostYear = leverageCostPerCycle * cycles;
    const leverageROI = totalLeverageCostYear > 0 ? Math.round(extraProfit / totalLeverageCostYear * 100) : 0;
    setResults({
      extraProfit,
      extraProfitPercent,
      newPurchaseSize,
      leverageCostPerCycle,
      leverageROI,
      currentPurchaseSize,
      currentProfitPerCycle,
      currentYearlyProfit,
      currentROE,
      netProfitPerCycle,
      netYearlyProfit,
      newROE
    });
  };
  useEffect(() => {
    calculate();
  }, [turnover, margin, sellDays, cycles]);
  const formatMoney = (amount: number) => {
    if (isNaN(amount) || amount === null || amount === undefined) {
      return '0 ₽';
    }
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };
  const scrollToContacts = () => {
    document.getElementById('contacts')?.scrollIntoView({
      behavior: 'smooth'
    });
  };
  return <section className="px-6 lg:px-12 bg-gradient-to-br from-medium-gray via-dark-gray to-medium-gray py-[55px]">
      <div className="max-w-7xl mx-auto">
        {/* Заголовок секции */}
        <div className="text-center mb-16">
          <div className="w-20 h-1 bg-accent-red mx-auto mb-8"></div>
          <h2 className="text-5xl lg:text-6xl font-black text-white mb-6">
            Давайте <span className="text-accent-red">посчитаем</span>
          </h2>
          <p className="text-xl text-gray-300 max-w-3xl mx-auto leading-relaxed">
            Сколько дополнительной прибыли вы заработаете с кредитным плечом
          </p>
        </div>

        {/* Калькулятор */}
        <div className="grid lg:grid-cols-2 gap-8 mb-16">
          {/* Панель ввода */}
          <div className="bg-gradient-to-br from-light-gray/60 to-dark-gray/60 backdrop-blur-xl p-8 rounded-3xl border border-white/10">
            <div className="flex items-center mb-8">
              <div className="w-12 h-12 bg-accent-red/20 rounded-2xl flex items-center justify-center mr-4">
                <Calculator className="w-6 h-6 text-accent-red" />
              </div>
              <h3 className="text-2xl font-bold text-white">Добавьте данные для расчёта</h3>
            </div>

            <div className="space-y-6">
              <div>
                <label className="block text-white font-semibold mb-3">Сколько у вас денег в обороте?</label>
                <div className="relative">
                  <input type="text" value={turnover} onChange={e => setTurnover(Number(e.target.value.replace(/\D/g, '')))} className="w-full bg-medium-gray/50 border border-white/20 rounded-2xl px-6 py-4 pr-12 text-white text-lg font-semibold focus:outline-none focus:border-accent-red/50 focus:bg-medium-gray/70 transition-all duration-300" placeholder="500000" />
                  <span className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 font-medium">₽</span>
                </div>
              </div>

              <div>
                <label className="block text-white font-semibold mb-3">
                  Какая у вас маржинальность?
                </label>
                <div className="relative">
                  <input type="text" value={margin} onChange={e => setMargin(Number(e.target.value.replace(/\D/g, '')))} className="w-full bg-medium-gray/50 border border-white/20 rounded-2xl px-6 py-4 pr-12 text-white text-lg font-semibold focus:outline-none focus:border-accent-red/50 focus:bg-medium-gray/70 transition-all duration-300" placeholder="30" />
                  <span className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 font-medium">%</span>
                </div>
              </div>

              <div>
                <label className="block text-white font-semibold mb-3">
                  За сколько дней продаете товар после покупки?
                </label>
                <div className="relative">
                  <input type="text" value={sellDays} onChange={e => setSellDays(Number(e.target.value.replace(/\D/g, '')))} className="w-full bg-medium-gray/50 border border-white/20 rounded-2xl px-6 py-4 pr-16 text-white text-lg font-semibold focus:outline-none focus:border-accent-red/50 focus:bg-medium-gray/70 transition-all duration-300" placeholder="30" />
                  <span className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 font-medium">дней</span>
                </div>
              </div>

              <div>
                <label className="block text-white font-semibold mb-3">
                  Сколько таких циклов делаете за год?
                </label>
                <div className="relative">
                  <input type="text" value={cycles} onChange={e => setCycles(Number(e.target.value.replace(/\D/g, '')))} className="w-full bg-medium-gray/50 border border-white/20 rounded-2xl px-6 py-4 pr-20 text-white text-lg font-semibold focus:outline-none focus:border-accent-red/50 focus:bg-medium-gray/70 transition-all duration-300" placeholder="8" />
                  <span className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 font-medium">циклов</span>
                </div>
              </div>
            </div>
          </div>

          {/* Панель результатов - серый стиль с зелёными акцентами */}
          <div className="bg-gradient-to-br from-light-gray/60 to-dark-gray/60 backdrop-blur-xl p-8 rounded-3xl border border-white/10">
            <div className="flex items-center mb-8">
              <div className="w-12 h-12 bg-accent-green/20 rounded-2xl flex items-center justify-center mr-4">
                <TrendingUp className="w-6 h-6 text-accent-green" />
              </div>
              <h3 className="text-2xl font-bold text-white">Ваша выгода от кредитного плеча</h3>
            </div>

            {/* Главная метрика */}
            <div className="text-center mb-8 p-6 bg-white/5 rounded-2xl border border-accent-green/30">
              <div className="text-gray-400 text-sm uppercase tracking-wider mb-2">
                Дополнительная прибыль в год
              </div>
              <div className="text-4xl font-black text-accent-green mb-2 animate-smooth-glow">
                {formatMoney(results.extraProfit)}
              </div>
              <div className="text-accent-green font-semibold">
                Это на {results.extraProfitPercent}% больше текущей прибыли!
              </div>
            </div>

            {/* Метрики в сетке - увеличиваем высоту плиток */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/5 rounded-xl p-6 border border-white/10 hover:border-accent-green/40 transition-all duration-300 min-h-[120px] flex flex-col justify-center">
                <div className="text-gray-400 text-xs uppercase tracking-wider mb-2">
                  Новый размер закупки
                </div>
                <div className="text-lg font-bold text-accent-green">
                  {formatMoney(results.newPurchaseSize)}
                </div>
              </div>
              <div className="bg-white/5 rounded-xl p-6 border border-white/10 hover:border-accent-green/40 transition-all duration-300 min-h-[120px] flex flex-col justify-center">
                <div className="text-gray-400 text-xs uppercase tracking-wider mb-2">
                  Ваша доля в сделке
                </div>
                <div className="text-lg font-bold text-accent-green">30%</div>
              </div>
              <div className="bg-white/5 rounded-xl p-6 border border-white/10 hover:border-accent-green/40 transition-all duration-300 min-h-[120px] flex flex-col justify-center">
                <div className="text-gray-400 text-xs uppercase tracking-wider mb-2">
                  Стоимость за цикл
                </div>
                <div className="text-lg font-bold text-accent-green">
                  {formatMoney(results.leverageCostPerCycle)}
                </div>
              </div>
              <div className="bg-white/5 rounded-xl p-6 border border-white/10 hover:border-accent-green/40 transition-all duration-300 min-h-[120px] flex flex-col justify-center">
                <div className="text-gray-400 text-xs uppercase tracking-wider mb-2">
                  ROI кредитного плеча
                </div>
                <div className="text-lg font-bold text-accent-green">{results.leverageROI}%</div>
              </div>
            </div>
          </div>
        </div>

        {/* Сравнение с красивыми заголовками */}
        <div className="bg-gradient-to-br from-light-gray/50 to-dark-gray/50 backdrop-blur-xl p-8 rounded-3xl border border-white/10 mb-16">
          {/* Красивые заголовки Было/Стало - отцентрированы по карточкам */}
          <div className="relative mb-8">
            <div className="grid lg:grid-cols-2 gap-8">
              <div className="flex justify-center">
                <div className="text-center">
                  <div className="w-16 h-16 bg-accent-red/20 rounded-2xl flex items-center justify-center mx-auto mb-3">
                    <AlertTriangle className="w-8 h-8 text-accent-red" />
                  </div>
                  <h3 className="text-3xl font-bold text-accent-red">Было</h3>
                  <p className="text-gray-400 text-sm mt-1">Ограниченные возможности</p>
                </div>
              </div>
              
              <div className="flex justify-center">
                <div className="text-center">
                  <div className="w-16 h-16 bg-accent-green/20 rounded-2xl flex items-center justify-center mx-auto mb-3">
                    <Rocket className="w-8 h-8 text-accent-green" />
                  </div>
                  <h3 className="text-3xl font-bold text-accent-green">Стало</h3>
                  <p className="text-gray-400 text-sm mt-1">Безграничные возможности</p>
                </div>
              </div>
            </div>
            
            {/* Простая стрелка между Было и Стало */}
            <div className="hidden lg:flex absolute top-8 left-1/2 transform -translate-x-1/2 items-center">
              <ArrowRight className="w-8 h-8 text-gray-400" />
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-8">
            {/* Сейчас - красный стиль с основным акцентным красным */}
            <div className="bg-gradient-to-br from-accent-red/15 to-accent-red/10 border border-accent-red/30 rounded-2xl p-8 hover:scale-105 transition-all duration-300">
              <div className="text-center mb-8">
                <h4 className="text-2xl font-bold text-accent-red mb-2">Сейчас: только свои деньги</h4>
              </div>

              <div className="space-y-4">
                <div className="flex justify-between items-center p-6 bg-white/5 rounded-xl min-h-[80px]">
                  <span className="text-gray-300">Размер закупки</span>
                  <span className="text-accent-red font-bold">{formatMoney(results.currentPurchaseSize)}</span>
                </div>
                <div className="flex justify-between items-center p-6 bg-white/5 rounded-xl min-h-[80px]">
                  <span className="text-gray-300">Прибыль за цикл</span>
                  <span className="text-accent-red font-bold">{formatMoney(results.currentProfitPerCycle)}</span>
                </div>
                <div className="flex justify-between items-center p-6 bg-white/5 rounded-xl min-h-[80px]">
                  <span className="text-gray-300">Прибыль в год</span>
                  <span className="text-accent-red font-bold">{formatMoney(results.currentYearlyProfit)}</span>
                </div>
                <div className="flex justify-between items-center p-6 bg-white/5 rounded-xl min-h-[80px]">
                  <span className="text-gray-300">Эффективность капитала</span>
                  <span className="text-accent-red font-bold">{Math.round(results.currentROE)}%</span>
                </div>
              </div>
            </div>

            {/* С плечом - зеленый стиль с accent-green */}
            <div className="bg-gradient-to-br from-accent-green/15 to-accent-green/10 border border-accent-green/30 rounded-2xl p-8 hover:scale-105 transition-all duration-300">
              <div className="text-center mb-8">
                <h4 className="text-2xl font-bold text-accent-green mb-2">С нашим плечом: турбо-режим</h4>
              </div>

              <div className="space-y-4">
                <div className="flex justify-between items-center p-6 bg-white/5 rounded-xl min-h-[80px]">
                  <span className="text-gray-300">Размер закупки</span>
                  <span className="text-accent-green font-bold">{formatMoney(results.newPurchaseSize)}</span>
                </div>
                <div className="flex justify-between items-center p-6 bg-white/5 rounded-xl min-h-[80px]">
                  <span className="text-gray-300">Прибыль за цикл (чистая)</span>
                  <span className="text-accent-green font-bold">{formatMoney(results.netProfitPerCycle)}</span>
                </div>
                <div className="flex justify-between items-center p-6 bg-white/5 rounded-xl min-h-[80px]">
                  <span className="text-gray-300">Прибыль в год (чистая)</span>
                  <span className="text-accent-green font-bold">{formatMoney(results.netYearlyProfit)}</span>
                </div>
                <div className="flex justify-between items-center p-6 bg-white/5 rounded-xl min-h-[80px]">
                  <span className="text-gray-300">Эффективность капитала</span>
                  <span className="text-accent-green font-bold">{Math.round(results.newROE)}%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Новая кнопка CTA с зелёным бордером */}
          <div className="text-center mt-12 pt-8 border-t border-white/10">
            <button onClick={scrollToContacts} className="text-white font-bold px-12 py-4 rounded-2xl text-xl hover:scale-105 hover:shadow-2xl transition-all duration-300 bg-[#1d1d20] border-2 border-accent-green">
              Запустить турбо-режим сегодня
            </button>
          </div>
        </div>

        {/* Преимущества */}
        <div className="bg-gradient-to-br from-accent-red/5 to-blue-500/5 backdrop-blur-xl p-8 rounded-3xl border border-accent-red/10 mb-16">
          <div className="text-center mb-12">
            <div className="w-20 h-1 bg-accent-red mx-auto mb-8"></div>
            <h3 className="text-5xl lg:text-6xl font-black text-white mb-6">
              Почему это <span className="text-accent-red">эффективно?</span>
            </h3>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div className="bg-white/5 p-6 rounded-2xl border border-white/10 hover:border-white/20 hover:-translate-y-1 transition-all duration-300">
              <Zap className="w-10 h-10 text-accent-red mb-4" />
              <h4 className="text-xl font-bold text-white mb-3">Мгновенное масштабирование</h4>
              <p className="text-gray-300">Увеличивайте закупки в 3 раза без поиска инвесторов или кредитов в банке</p>
            </div>

            <div className="bg-white/5 p-6 rounded-2xl border border-white/10 hover:border-white/20 hover:-translate-y-1 transition-all duration-300">
              <DollarSign className="w-10 h-10 text-accent-red mb-4" />
              <h4 className="text-xl font-bold text-white mb-3">Низкая стоимость капитала</h4>
              <p className="text-gray-300">Всего от 1% за сделку без поручителей, бюрократии и других проблем</p>
            </div>

            <div className="bg-white/5 p-6 rounded-2xl border border-white/10 hover:border-white/20 hover:-translate-y-1 transition-all duration-300">
              <Target className="w-10 h-10 text-accent-red mb-4" />
              <h4 className="text-xl font-bold text-white mb-3">Простая схема</h4>
              <p className="text-gray-300">Пример: вы оплачиваете 30% предоплату, мы доплачиваем 70% на фабрику.</p>
            </div>

            <div className="bg-white/5 p-6 rounded-2xl border border-white/10 hover:border-white/20 hover:-translate-y-1 transition-all duration-300">
              <TrendingUp className="w-10 h-10 text-accent-red mb-4" />
              <h4 className="text-xl font-bold text-white mb-3">Без ограничений</h4>
              <p className="text-gray-300">Нет лимитов по количеству сделок, работайте столько, сколько нужно</p>
            </div>

            <div className="bg-white/5 p-6 rounded-2xl border border-white/10 hover:border-white/20 hover:-translate-y-1 transition-all duration-300">
              <Shield className="w-10 h-10 text-accent-red mb-4" />
              <h4 className="text-xl font-bold text-white mb-3">Минимальные риски</h4>
              <p className="text-gray-300">Вы рискуете только предоплатой, а получаете прибыль с полной суммы</p>
            </div>

            <div className="bg-white/5 p-6 rounded-2xl border border-white/10 hover:border-white/20 hover:-translate-y-1 transition-all duration-300">
              <Trophy className="w-10 h-10 text-accent-red mb-4" />
              <h4 className="text-xl font-bold text-white mb-3">Конкурентное преимущество</h4>
              <p className="text-gray-300">Больше товара {'>'}больше продаж {'>'}больше оборот {'>'}доминирование в нише</p>
            </div>
          </div>
        </div>

        {/* Блок "Как это устроено" - компактный статейный формат */}
        <div className="bg-gradient-to-br from-light-gray/60 to-dark-gray/60 backdrop-blur-xl p-12 rounded-3xl border border-white/10">
          <div className="text-center mb-12">
            <div className="w-20 h-1 bg-accent-red mx-auto mb-8"></div>
            <h3 className="text-4xl lg:text-5xl font-black text-white mb-6">
              Как это <span className="text-accent-red">работает?</span>
            </h3>
          </div>

          <div className="max-w-4xl mx-auto space-y-8">
            {/* Основной текстовый блок */}
            <div className="prose prose-lg prose-invert max-w-none">
              <p className="text-gray-300 text-lg leading-relaxed mb-6">
                <strong className="text-white">В хорошем бизнесе денег всегда нехватает...</strong>
              </p>
              <p className="text-gray-300 text-lg leading-relaxed mb-6">
                Каждый предприниматель понимает, чтобы масштабироваться, нужно увеличить оборачиваемость его товарной массы. 
                Снизить запасы на складах, за счёт быстрой логистики и получить конкурентное преимущество за счёт регулярных объёмов закупок у поставщика.
              </p>
              <p className="text-gray-300 text-lg leading-relaxed mb-6">
                Именно на этом сконцентрирован наш торговый дом WellWon. Наша миссия - помочь партнёрам масштабировать их бизнес 
                за счёт нашей компетенции и финансового плеча.
              </p>
              <p className="text-gray-300 text-lg leading-relaxed mb-8">
                Мы понимаем, что взять кредиты в банках сейчас очень сложно, нужно предоставлять тонны документов, 
                оформлять залоги и поручительства. Чтобы решить все эти проблемы, мы вывели на рынок услугу <span className="text-accent-red font-semibold">"Товарное финансирование"</span>.
              </p>
              <p className="text-lg leading-relaxed mb-8 text-left font-normal text-gray-300">
                Мы убрали всю бюрократию, чтобы решение о финансировании принималось за считанные минуты.
              </p>
            </div>

            {/* Процесс работы */}
            <div className="bg-white/5 p-8 rounded-2xl border border-white/10">
              <h4 className="text-2xl font-bold text-white mb-6 text-center">Все максимально просто:</h4>
              
              <div className="space-y-4 text-gray-300 text-lg leading-relaxed">
                <p><span className="text-accent-red font-bold">1.</span> Мы проверяем ликвидность груза и согласовываем ставку за финансирования (от 1%)</p>
                <p><span className="text-accent-red font-bold">2.</span> Отдел рисков утверждает размер предоплаты клиента (например: 30% клиент, 70% мы)</p>
                <p><span className="text-accent-red font-bold">3.</span> Далее, мы объединяем суммы и платим на фабрику</p>
                <p><span className="text-accent-red font-bold">4.</span> Пока груз готовят, мы сканируем рынок логистики, чтобы получить самые низкие ставки и готовим груз к отправке на одном из 3 складов</p>
                <p><span className="text-accent-red font-bold">5.</span> Когда груз прибыл на наш фулфилмент в Москве, клиент может его забрать, отправить по любому адресу или оставить на фулфилменте для обработки</p>
              </div>
            </div>

            {/* Ключевые особенности */}
            <div className="text-center">
              <p className="text-gray-300 text-lg leading-relaxed mb-4 text-left">
                • Высокая частотность перевозок (минимум 3-5 фур в неделю)<br />
                • Груз бесшовно перемещается в формате склад-склад<br />
                • Всю обработку, контроль и решение проблем берём на себя
              </p>
              <p className="text-lg text-gray-300 font-normal text-left">
                Мы предоставляем комплексную систему работы с Китаем. Это позволяет существенно экономить. 
                Больше не нужно заказывать услуги у разных подрядчиков. Все в одном месте - дешевле.
              </p>
            </div>

            {/* CTA как часть статьи - с красным градиентом и декоративными элементами */}
            <div className="relative bg-gradient-to-r from-accent-red to-accent-red/80 rounded-3xl p-12 text-center mt-12 overflow-hidden">
              {/* Декоративные элементы - уменьшенные версии */}
              <div className="absolute top-4 left-4 w-16 h-16 bg-white/10 rounded-full blur-2xl"></div>
              <div className="absolute bottom-4 right-4 w-24 h-24 bg-white/5 rounded-full blur-2xl"></div>
              <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-32 h-32 bg-white/5 rounded-full blur-3xl"></div>
              
              {/* Дополнительный слой градиента для глубины */}
              <div className="absolute inset-0 bg-gradient-to-br from-transparent via-black/10 to-black/30 rounded-3xl"></div>
              
              {/* Контент поверх декоративных элементов */}
              <div className="relative z-10">
                <h4 className="text-3xl font-bold text-white mb-4">
                  Готовы увеличить прибыль в 3 раза?
                </h4>
                <p className="text-xl text-white/90 mb-8">
                  Начните использовать кредитное плечо уже сегодня
                </p>
                <button onClick={scrollToContacts} className="bg-white text-accent-red font-bold px-12 py-4 rounded-2xl text-xl hover:scale-105 hover:shadow-2xl transition-all duration-300">
                  Подать заявку на финансирование
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>;
};

export default FinancingCalculator;
