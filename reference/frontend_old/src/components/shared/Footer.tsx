import { Facebook, Twitter, Linkedin, Instagram, Phone, Mail, MapPin } from "lucide-react";
const Footer = () => {
  const socialLinks = [{
    icon: Facebook,
    href: "#",
    label: "Facebook"
  }, {
    icon: Twitter,
    href: "#",
    label: "Twitter"
  }, {
    icon: Linkedin,
    href: "#",
    label: "LinkedIn"
  }, {
    icon: Instagram,
    href: "#",
    label: "Instagram"
  }];
  const quickLinks = [{
    name: "Услуги",
    href: "#services"
  }, {
    name: "О нас",
    href: "#about"
  }, {
    name: "Отзывы",
    href: "#testimonials"
  }, {
    name: "Контакты",
    href: "#contacts"
  }];
  const services = [{
    name: "Инвестиционное финансирование",
    href: "#"
  }, {
    name: "Корпоративное кредитование",
    href: "#"
  }, {
    name: "Быстрые займы",
    href: "#"
  }, {
    name: "Проектное финансирование",
    href: "#"
  }];
  return <footer className="bg-gradient-to-b from-dark-gray to-black py-20 px-6 lg:px-12 relative overflow-hidden">
      <div className="absolute top-0 left-1/4 w-80 h-80 bg-accent-red/5 rounded-full blur-3xl"></div>
      <div className="absolute bottom-0 right-1/4 w-64 h-64 bg-accent-red/10 rounded-full blur-3xl"></div>
      
      <div className="max-w-7xl mx-auto relative z-10">
        <div className="grid lg:grid-cols-4 gap-12 mb-16">
          <div className="lg:col-span-1">
            <div className="text-accent-red text-4xl font-black tracking-tight mb-6 relative">
              Well<span className="text-white">Won</span>
              <div className="absolute -bottom-1 left-0 w-12 h-0.5 bg-accent-red"></div>
            </div>
            <p className="text-gray-400 mb-8 leading-relaxed">Выведем ваш бизнес на новый уровень. Снизим затраты и увеличим оборачиваемость.</p>
            <div className="flex space-x-4">
              {socialLinks.map((social, index) => <a key={index} href={social.href} aria-label={social.label} className="w-12 h-12 bg-accent-red rounded-xl flex items-center justify-center text-white hover:scale-110 hover:brightness-110 transition-all duration-300">
                  <social.icon className="w-5 h-5" />
                </a>)}
            </div>
          </div>
          
          <div>
            <h4 className="text-white text-xl font-bold mb-6">Быстрые ссылки</h4>
            <ul className="space-y-4">
              {quickLinks.map((link, index) => <li key={index}>
                  <a href={link.href} className="text-gray-300 hover:text-accent-red transition-colors duration-300 relative group">
                    {link.name}
                    <div className="absolute -bottom-1 left-0 w-0 h-0.5 bg-accent-red group-hover:w-full transition-all duration-300"></div>
                  </a>
                </li>)}
            </ul>
          </div>
          
          <div>
            <h4 className="text-white text-xl font-bold mb-6">Услуги</h4>
            <ul className="space-y-4">
              {services.map((service, index) => <li key={index}>
                  <a href={service.href} className="text-gray-300 hover:text-accent-red transition-colors duration-300 relative group">
                    {service.name}
                    <div className="absolute -bottom-1 left-0 w-0 h-0.5 bg-accent-red group-hover:w-full transition-all duration-300"></div>
                  </a>
                </li>)}
            </ul>
          </div>
          
          <div>
            <h4 className="text-white text-xl font-bold mb-6">Контакты</h4>
            <div className="space-y-4">
              <div className="flex items-start">
                <Phone className="w-4 h-4 text-accent-red mr-3 mt-0.5" />
                <div>
                  <p className="text-white font-semibold">+852 9291 1173</p>
                  <p className="text-gray-400 text-sm">С 11:00 до 19:00</p>
                </div>
              </div>
              <div className="flex items-start">
                <Mail className="w-4 h-4 text-accent-red mr-3 mt-0.5" />
                <div>
                  <p className="text-white font-semibold">info@wellwon.hk</p>
                  <p className="text-gray-400 text-sm">Ответим в течение часа</p>
                </div>
              </div>
              <div className="flex items-start">
                <MapPin className="w-6 h-6 text-accent-red mr-3 mt-0.5" />
                <div>
                  <p className="text-white font-semibold text-sm mx-px">RM 1921, 19/F STAR HSE 3 SALISBURY RD TSIM SHA TSUI</p>
                  <p className="text-gray-400 text-sm px-px">HONG KONG</p>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div className="border-t border-gray-700 pt-8">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <p className="text-gray-400 mb-4 md:mb-0">© 2025 WellWon Limited. Все права защищены.</p>
            <div className="flex space-x-8">
              <a href="/privacy" className="text-gray-400 hover:text-accent-red transition-colors">
                Политика конфиденциальности
              </a>
              <a href="/terms" className="text-gray-400 hover:text-accent-red transition-colors">
                Условия использования
              </a>
              <a href="/cookie-policy" className="text-gray-400 hover:text-accent-red transition-colors">
                Политика cookie
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>;
};
export default Footer;