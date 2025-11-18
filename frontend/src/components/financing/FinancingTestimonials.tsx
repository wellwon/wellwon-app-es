import { Quote } from "lucide-react";
const FinancingTestimonials = () => {
  const testimonials = [{
    name: "Алексей Прохоров",
    company: "ООО «Инфинити»",
    position: "Генеральный директор",
    text: "Благодаря WellWon мы смогли вывести наш бренд бритвенных принадлежностей «Того» на новый уровень. Лимит финансирования в $180,000 позволил нам значительно расширить ассортимент и увеличить объемы закупок. Теперь мы можем конкурировать с крупными игроками рынка и предлагать клиентам качественную продукцию по доступным ценам.",
    avatar: "/lovable-uploads/8f2f8c62-7efb-4ce0-9dcd-b00d7ebf45fd.png",
    financing: "$180,000"
  }, {
    name: "Марк Рыболовлев",
    company: "ДМ-Групп",
    position: "Генеральный директор",
    text: "WellWon стали нашими надежными партнерами в масштабировании бизнеса. Товарооборот превысил 100 млн рублей в месяц! Лимит в $250,000 помог не только развить ВБ Альянс, но и запустить совершенно новое направление — бренд наливных гантелей «Руки базуки». Профессиональный подход команды и гибкие условия финансирования — это именно то, что нужно растущему бизнесу.",
    avatar: "/lovable-uploads/e7990051-ee47-48db-81c2-710d3a823eb0.png",
    financing: "$250,000"
  }, {
    name: "Егор Макаренко",
    company: "ООО «Макл»",
    position: "Генеральный директор",
    text: "Результат превзошел все ожидания — за год сотрудничества с WellWon мы масштабировали бизнес в 3,2 раза! Лимит финансирования $110,000 дал нам возможность делать крупные закупки с хорошими скидками и быстро реагировать на изменения рынка. За не 6 месяцев мы увеличили оборот в несколько раз, а проблема с выпадающими остатками ушла в прошлое. Надеемся за 2025 год выйти на 400млн выручки",
    avatar: "/lovable-uploads/6ed58d87-b55a-4bc6-9bd5-b9b1a09f8e69.png",
    financing: "$110,000"
  }, {
    name: "Пётр Козьмин",
    company: "ООО «Окки»",
    position: "Генеральный директор",
    text: "WellWon помогли нам организовать полный цикл официальных перевозок и выйти на международный рынок. Лимит в $170,000 позволил структурировать все логистические процессы и работать с крупными оптовыми поставками. Больше никаких задержек в цепочке поставок — все четко, быстро и прозрачно. Рекомендую всем, кто работает с международными перевозками!",
    avatar: "/lovable-uploads/53e00aa2-50f8-427c-b463-09047dc10043.png",
    financing: "$170,000"
  }];
  return <section className="py-32 px-6 lg:px-12 bg-light-gray border-t border-medium-gray/20">
      <div className="max-w-7xl mx-auto relative z-10">
        <div className="text-center mb-20 animate-fade-in">
          <div className="w-20 h-1 bg-accent-red mx-auto mb-8"></div>
          <h2 className="text-5xl lg:text-6xl font-black mb-8 leading-tight text-white">
            Наши <span className="text-accent-red">партнёры</span>
          </h2>
          
          <p className="text-xl text-gray-300 max-w-3xl mx-auto leading-relaxed">Узнайте, что говорят о нас наши партнёры</p>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          {testimonials.map((testimonial, index) => <div key={index} className="bg-gradient-to-br from-dark-gray/90 to-medium-gray/90 backdrop-blur-xl p-8 rounded-3xl border border-accent-red/10 hover:border-white/20 hover:-translate-y-1 transition-all duration-500 animate-fade-in group" style={{
          animationDelay: `${index * 0.1}s`
        }}>
              <div className="flex items-start justify-between mb-6">
                <div className="flex items-start">
                  <div className="w-16 h-16 rounded-2xl overflow-hidden mr-4 flex-shrink-0 border-2 border-accent-red/20">
                    <img src={testimonial.avatar} alt={testimonial.name} className="w-full h-full object-cover" />
                  </div>
                  <div className="flex-1">
                    <h4 className="text-xl font-bold text-white mb-1 group-hover:text-accent-red transition-colors">
                      {testimonial.name}
                    </h4>
                    <p className="text-gray-400 text-sm mb-1">{testimonial.position}</p>
                    <p className="text-accent-red font-semibold text-sm">{testimonial.company}</p>
                  </div>
                </div>
                <Quote className="w-8 h-8 text-accent-red/30" />
              </div>
              
              <p className="text-gray-300 leading-relaxed mb-6 text-lg">
                "{testimonial.text}"
              </p>
              
              <div className="border-t border-accent-red/20 pt-4">
                <p className="text-gray-400 text-sm font-medium">Выдано финансирования - {testimonial.financing}</p>
              </div>
            </div>)}
        </div>
      </div>
    </section>;
};
export default FinancingTestimonials;
