import { Button } from "@/components/ui/button";
import { useState } from "react";
import { Phone, Mail, MapPin, Clock, AlertCircle } from "lucide-react";
import { useUTMContext } from "@/contexts/UTMContext";
import { getUTMForAPI } from "@/utils/utmUtils";
import { sanitizeInput, validateEmail, validatePhone, checkRateLimit } from "@/utils/security";
import { logInfo } from "@/utils/logger";

const ContactForm = () => {
  const { utmParams } = useUTMContext();
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    company: '',
    message: ''
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.name.trim()) {
      newErrors.name = 'Имя обязательно для заполнения';
    } else if (formData.name.length < 2) {
      newErrors.name = 'Имя должно содержать минимум 2 символа';
    }
    
    if (!formData.email.trim()) {
      newErrors.email = 'Email обязателен для заполнения';
    } else if (!validateEmail(formData.email)) {
      newErrors.email = 'Некорректный формат email';
    }
    
    if (!formData.phone.trim()) {
      newErrors.phone = 'Телефон обязателен для заполнения';
    } else if (!validatePhone(formData.phone)) {
      newErrors.phone = 'Некорректный формат телефона';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (isSubmitting) return;
    
    // Проверка rate limiting
    if (!checkRateLimit('contact-form', 3, 60000)) {
      setErrors({ general: 'Слишком много попыток. Попробуйте через минуту.' });
      return;
    }
    
    if (!validateForm()) {
      return;
    }
    
    setIsSubmitting(true);
    setErrors({});
    
    try {
      // Санитизация данных перед отправкой
      const sanitizedData = {
        name: sanitizeInput(formData.name),
        email: sanitizeInput(formData.email),
        phone: sanitizeInput(formData.phone),
        company: sanitizeInput(formData.company),
        message: sanitizeInput(formData.message),
        ...getUTMForAPI(utmParams)
      };
      
      // Имитируем отправку данных на сервер
      logInfo('Отправка данных формы', { 
        component: 'ContactForm',
        metadata: sanitizedData 
      });
      
      // Симуляция запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Имитируем успешный ответ
      const result = { message: 'Заявка успешно отправлена! Мы свяжемся с вами в ближайшее время.' };

      // Очищаем форму после успешной отправки
      setFormData({
        name: '',
        email: '',
        phone: '',
        company: '',
        message: ''
      });

      // Показываем сообщение об успехе
      setErrors({ success: result.message });
      
    } catch (error) {
      setErrors({ general: 'Ошибка отправки формы. Попробуйте позже.' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    
    // Очищаем ошибку для поля при изменении
    if (errors[name]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[name];
        return newErrors;
      });
    }
    
    setFormData({
      ...formData,
      [name]: value
    });
  };

  return (
    <section id="contacts" className="px-6 lg:px-12 py-20 bg-medium-gray">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <div className="w-12 h-1 bg-accent-red mx-auto mb-6"></div>
          <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6">
            Свяжитесь с Нами
          </h2>
          <p className="text-gray-400 text-xl max-w-2xl mx-auto">
            Готовы обсудить финансирование вашего бизнеса? Свяжитесь с нашими экспертами
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-12">
          <div className="space-y-8">
            <div>
              <h3 className="text-2xl font-bold text-white mb-6">Контактная информация</h3>
              
              <div className="space-y-6">
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 bg-accent-red rounded-full flex items-center justify-center">
                    <Phone className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <div className="text-white font-semibold">Телефон</div>
                    <div className="text-gray-400">+7 (495) 123-45-67</div>
                  </div>
                </div>
                
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 bg-accent-red rounded-full flex items-center justify-center">
                    <Mail className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <div className="text-white font-semibold">Email</div>
                    <div className="text-gray-400">info@wellwon.hk</div>
                  </div>
                </div>
                
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 bg-accent-red rounded-full flex items-center justify-center">
                    <MapPin className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <div className="text-white font-semibold">Адрес</div>
                    <div className="text-gray-400">Москва, ул. Тверская, 15</div>
                  </div>
                </div>
                
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 bg-accent-red rounded-full flex items-center justify-center">
                    <Clock className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <div className="text-white font-semibold">Режим работы</div>
                    <div className="text-gray-400">Пн-Пт: 9:00 - 18:00</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-light-gray p-8 rounded-2xl">
            <h3 className="text-2xl font-bold text-white mb-6">Оставить заявку</h3>
            
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Показываем сообщения об ошибках и успехе */}
              {errors.general && (
                <div className="flex items-center space-x-2 text-red-400 bg-red-400/10 p-3 rounded-lg">
                  <AlertCircle className="w-5 h-5" />
                  <span>{errors.general}</span>
                </div>
              )}
              
              {errors.success && (
                <div className="flex items-center space-x-2 text-green-400 bg-green-400/10 p-3 rounded-lg">
                  <AlertCircle className="w-5 h-5" />
                  <span>{errors.success}</span>
                </div>
              )}
              
              {/* Скрытые поля с UTM параметрами */}
              {Object.entries(utmParams).map(([key, value]) => (
                value && (
                  <input
                    key={key}
                    type="hidden"
                    name={key}
                    value={sanitizeInput(value)}
                  />
                )
              ))}
              
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <input
                    type="text"
                    name="name"
                    placeholder="Ваше имя"
                    value={formData.name}
                    onChange={handleChange}
                    className={`w-full px-4 py-3 bg-dark-gray text-white rounded-lg border transition-colors ${
                      errors.name ? 'border-red-400' : 'border-gray-600 focus:border-accent-red'
                    } focus:outline-none`}
                    required
                    maxLength={100}
                  />
                  {errors.name && <p className="text-red-400 text-sm mt-1">{errors.name}</p>}
                </div>
                <div>
                  <input
                    type="email"
                    name="email"
                    placeholder="Email"
                    value={formData.email}
                    onChange={handleChange}
                    className={`w-full px-4 py-3 bg-dark-gray text-white rounded-lg border transition-colors ${
                      errors.email ? 'border-red-400' : 'border-gray-600 focus:border-accent-red'
                    } focus:outline-none`}
                    required
                    maxLength={100}
                  />
                  {errors.email && <p className="text-red-400 text-sm mt-1">{errors.email}</p>}
                </div>
              </div>
              
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <input
                    type="tel"
                    name="phone"
                    placeholder="Телефон"
                    value={formData.phone}
                    onChange={handleChange}
                    className={`w-full px-4 py-3 bg-dark-gray text-white rounded-lg border transition-colors ${
                      errors.phone ? 'border-red-400' : 'border-gray-600 focus:border-accent-red'
                    } focus:outline-none`}
                    required
                    maxLength={20}
                  />
                  {errors.phone && <p className="text-red-400 text-sm mt-1">{errors.phone}</p>}
                </div>
                <div>
                  <input
                    type="text"
                    name="company"
                    placeholder="Название компании"
                    value={formData.company}
                    onChange={handleChange}
                    className="w-full px-4 py-3 bg-dark-gray text-white rounded-lg border border-gray-600 focus:border-accent-red focus:outline-none transition-colors"
                    maxLength={100}
                  />
                </div>
              </div>
              
              <div>
                <textarea
                  name="message"
                  rows={4}
                  placeholder="Сообщение"
                  value={formData.message}
                  onChange={handleChange}
                  className="w-full px-4 py-3 bg-dark-gray text-white rounded-lg border border-gray-600 focus:border-accent-red focus:outline-none transition-colors resize-none"
                  maxLength={1000}
                ></textarea>
              </div>
              
              <Button 
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-accent-red hover:bg-accent-red-dark text-white py-3 rounded-lg transition-all duration-300 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
              >
                {isSubmitting ? 'Отправка...' : 'Отправить заявку'}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </section>
  );
};

export default ContactForm;
