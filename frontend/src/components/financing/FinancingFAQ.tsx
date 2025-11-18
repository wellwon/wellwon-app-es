
import { 
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

const FinancingFAQ = () => {
  const faqs = [
    {
      question: "А если товар не продастся?",
      answer: "Мы работаем с проверенными товарными категориями и брендами. В случае если товар не продается в ожидаемые сроки, мы предоставляем консультации по оптимизации стратегии продаж, помогаем с ребрендингом или поиском новых каналов сбыта."
    },
    {
      question: "Это не слишком дорого?",
      answer: "Наши условия финансирования одни из самых выгодных на рынке. Мы предлагаем гибкие процентные ставки от 8% годовых и индивидуальный подход к каждому клиенту. Инвестиции в развитие бизнеса окупаются уже в первые месяцы работы."
    },
    {
      question: "А если поставщик обманет?",
      answer: "Мы работаем только с проверенными поставщиками, которые прошли тщательную проверку. Все контракты застрахованы, а поставки осуществляются через надежные логистические каналы. В случае форс-мажора предоставляем полную правовую поддержку."
    },
    {
      question: "Как я верну деньги, если что-то пойдет не так?",
      answer: "У нас предусмотрена гибкая система возврата средств. Мы предоставляем grace period на начальном этапе, возможность реструктуризации долга и индивидуальные планы погашения. Наша цель — ваш успех, поэтому мы всегда идем навстречу в сложных ситуациях."
    }
  ];

  return (
    <section className="py-32 px-6 lg:px-12 bg-gradient-to-br from-dark-gray via-medium-gray to-dark-gray">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-20 animate-fade-in">
          <div className="w-20 h-1 bg-accent-red mx-auto mb-8"></div>
          <h2 className="text-6xl lg:text-7xl font-black mb-8 leading-tight text-white">
            Частые <span className="text-accent-red">вопросы</span>
          </h2>
          
          <p className="text-xl text-gray-300 max-w-3xl mx-auto leading-relaxed">
            Ответы на самые популярные вопросы наших клиентов
          </p>
        </div>

        <Accordion type="single" collapsible className="w-full space-y-4">
          {faqs.map((faq, index) => (
            <AccordionItem 
              key={index} 
              value={`item-${index}`}
              className="bg-gradient-to-br from-light-gray/80 to-dark-gray/80 backdrop-blur-sm rounded-3xl border border-white/10 hover:border-white/20 hover:-translate-y-1 transition-all duration-300 overflow-hidden"
            >
              <AccordionTrigger className="px-8 py-6 text-left hover:no-underline group">
                <div className="flex items-center justify-between w-full">
                  <span className="text-lg font-semibold text-white group-hover:text-accent-red transition-colors flex items-center">
                    <span className="text-accent-red mr-3 text-xl">?</span>
                    {faq.question}
                  </span>
                </div>
              </AccordionTrigger>
              <AccordionContent className="px-8 pb-6">
                <p className="text-gray-300 leading-relaxed text-base">
                  {faq.answer}
                </p>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
};

export default FinancingFAQ;
